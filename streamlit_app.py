# =============================================================================
# SEN2GREENERY - AGRICULTURAL VEGETATION ANALYSIS APP (Enhanced Version)
# =============================================================================
# Features:
# - Draw AOI on map OR upload shapefile/GeoJSON OR enter coordinates
# - Browse all available images with date and cloud cover
# - Select specific images for analysis
# - Compare two images (same or different satellite)
# =============================================================================

import streamlit as st
import os
from pathlib import Path

# Prevent geemap/earthengine from auto-authenticating on import
os.environ['EARTHENGINE_PROJECT'] = ''

import ee
import geemap.foliumap as geemap
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import datetime
import numpy as np
from PIL import Image
import io
import json
import zipfile
import tempfile
import pandas as pd

# Import our utility modules
from utils.indices import (
    calculate_ndvi, calculate_savi, calculate_evi, 
    calculate_gndvi, calculate_ndmi, calculate_ndre,
    get_available_indices
)
from utils.sensors import (
    get_sentinel2_collection, get_landsat89_collection, get_landsat57_collection,
    get_modis_collection, get_sensor_info, get_band_names, 
    SENTINEL2_BANDS, LANDSAT89_BANDS, LANDSAT57_BANDS, MODIS_BANDS
)
from utils.image_processing import (
    load_uploaded_image, calculate_rgb_index, create_colormap_image, get_rgb_indices
)

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="AgriVision Pro - Vegetation Analysis",
    page_icon="🌾",
    layout="wide"
)

# =============================================================================
# AUTHENTICATION: Users must authenticate with their own GEE account
# Options:
# 1. Upload credentials file (from ~/.config/earthengine/credentials)
# 2. Sign in with Google (OAuth)
# =============================================================================
import os
from pathlib import Path

# No longer using OAuth - credentials file upload only

def initialize_with_refresh_token(cred_data, project_id=None):
    """Initialize GEE using refresh token or service account credentials from uploaded file"""
    try:
        # Detect credential type
        is_service_account = 'type' in cred_data and cred_data['type'] == 'service_account'
        has_refresh_token = 'refresh_token' in cred_data
        
        # Try service account first
        if is_service_account or ('private_key' in cred_data and 'service_account_email' in cred_data):
            try:
                import google.auth.service_account
                credentials = google.auth.service_account.Credentials.from_service_account_info(
                    cred_data,
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                
                proj_id = project_id or cred_data.get('project_id')
                if proj_id:
                    ee.Initialize(credentials, project=proj_id, opt_url='https://earthengine-highvolume.googleapis.com')
                else:
                    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
                return True, None
            except Exception as sa_err:
                if has_refresh_token:
                    pass  # Fall through to OAuth attempt
                else:
                    return False, f"Service account error: {str(sa_err)[:80]}"
        
        # Try OAuth/refresh token
        if has_refresh_token:
            try:
                import google.oauth2.credentials
                
                refresh_token = cred_data.get('refresh_token')
                
                if not refresh_token:
                    return False, "Refresh token missing. Run: earthengine authenticate"
                
                # Google's official Earth Engine OAuth app credentials
                # These are the public client credentials used by earthengine CLI
                credentials = google.oauth2.credentials.Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id='517222506229-vsmmajv5gipbgpkq0jvlg5830gon1p60.apps.googleusercontent.com',
                    client_secret='d-FL95Q19q7MQmFJt7KUw2N7',
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                
                if project_id:
                    ee.Initialize(credentials, project=project_id, opt_url='https://earthengine-highvolume.googleapis.com')
                else:
                    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
                return True, None
            except Exception as oauth_err:
                error_str = str(oauth_err)
                if 'invalid_client' in error_str:
                    return False, "Invalid client error. Your credentials may be expired. Run: earthengine authenticate"
                else:
                    return False, f"Authentication error: {error_str[:80]}"
        
        # No recognized credential type
        return False, "Unrecognized credential format. Need refresh_token or service account."
    
    except Exception as e:
        return False, f"Error: {str(e)[:80]}"


def initialize_with_credentials_content(credentials_content: str, project_id: str = None):
    """Initialize Earth Engine from the uploaded credentials file content.

    Handles both:
    - Service account key files (has "private_key" and "client_email")
    - User credentials files created by `earthengine authenticate` (has "refresh_token")

    Returns (success: bool, error: Optional[str])
    """
    try:
        # Try parse JSON
        creds_data = json.loads(credentials_content)

        # Service account key file
        if isinstance(creds_data, dict) and ('private_key' in creds_data and 'client_email' in creds_data):
            try:
                import google.oauth2.service_account
                credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                    creds_data,
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                proj_id = project_id or creds_data.get('project_id')
                if proj_id:
                    ee.Initialize(credentials, project=proj_id, opt_url='https://earthengine-highvolume.googleapis.com')
                else:
                    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
                # Store in session for persistence
                st.session_state.gee_project_used = proj_id
                return True, None
            except Exception as sa_err:
                return False, f"Service account init failed: {str(sa_err)[:120]}"

        # User OAuth credentials (has refresh_token)
        elif isinstance(creds_data, dict) and 'refresh_token' in creds_data:
            try:
                import google.oauth2.credentials
                
                # Use the OAuth client info from the credentials file if present,
                # otherwise use the standard Earth Engine OAuth client
                client_id = creds_data.get('client_id', '517222506229-vsmmajv5gipbgpkq0jvlg5830gon1p60.apps.googleusercontent.com')
                client_secret = creds_data.get('client_secret', 'd-FL95Q19q7MQmFJt7KUw2N7')
                
                credentials = google.oauth2.credentials.Credentials(
                    token=None,
                    refresh_token=creds_data['refresh_token'],
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                
                if project_id:
                    ee.Initialize(credentials, project=project_id, opt_url='https://earthengine-highvolume.googleapis.com')
                    st.session_state.gee_project_used = project_id
                else:
                    ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
                
                # Store credentials content in session for re-auth on rerun
                st.session_state.gee_credentials_content = credentials_content
                st.session_state.gee_project_id = project_id
                return True, None
            except Exception as oauth_err:
                return False, f"OAuth init failed: {str(oauth_err)[:120]}"
        
        else:
            return False, "Unrecognized credential format. Need refresh_token or service account."

    except json.JSONDecodeError:
        return False, "Uploaded file is not valid JSON"
    except Exception as e:
        return False, f"Error processing credentials: {str(e)[:120]}"

def try_auto_initialize():
    def exchange_code_for_token(auth_code, project_id=None):
        """Exchange OAuth authorization code for refresh token and initialize GEE"""
        try:
            import requests
        
            CLIENT_ID = '517222506229-vsmmajv5gipbgpkq0jvlg5830gon1p60.apps.googleusercontent.com'
            CLIENT_SECRET = 'd-FL95Q19q7MQmFJt7KUw2N7'
        
            # Exchange code for tokens
            token_url = 'https://oauth2.googleapis.com/token'
            payload = {
                'code': auth_code.strip(),
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'grant_type': 'authorization_code'
            }
        
            response = requests.post(token_url, data=payload)
            token_data = response.json()
        
            if 'error' in token_data:
                error_msg = token_data.get('error_description', token_data.get('error', 'Unknown error'))
                return False, error_msg
        
            if 'refresh_token' not in token_data:
                return False, "No refresh token received. Make sure you authorized offline access."
        
            # Use the refresh token to authenticate with GEE
            cred_data = {
                'refresh_token': token_data['refresh_token'],
                'token_uri': 'https://oauth2.googleapis.com/token',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            }
        
            return initialize_with_refresh_token(cred_data, project_id)
    
        except Exception as e:
            error_str = str(e)
            if 'invalid_grant' in error_str:
                return False, "Invalid or expired authorization code. Try again from Step 1."
            return False, f"Token exchange failed: {error_str[:100]}"

    """
    Try to auto-initialize GEE from default credential locations.
    Returns (success, method) tuple.
    """
    # Check if already initialized (with timeout to prevent hangs)
    try:
        ee.Number(1).getInfo(timeout=5)
        return True, "already_initialized"
    except:
        pass
    
    # Try default credential locations
    default_paths = [
        Path.home() / '.config' / 'earthengine' / 'credentials',
        Path.home() / '.earthengine' / 'credentials'
    ]
    
    for cred_path in default_paths:
        if cred_path.exists():
            try:
                with open(cred_path, 'r') as f:
                    cred_data = json.load(f)
                if 'refresh_token' in cred_data:
                    success, error = initialize_with_refresh_token(cred_data)
                    if success:
                        return True, "local_credentials"
            except:
                pass
    
    # Try default initialization
    try:
        ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')
        return True, "default"
    except:
        pass
    
    return False, None

# Session state for GEE authentication status
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False
if 'gee_auth_method' not in st.session_state:
    st.session_state.gee_auth_method = None
if 'gee_init_attempted' not in st.session_state:
    st.session_state.gee_init_attempted = False

# Initialize GEE once per session (try auto-initialize from local credentials)
# Skip auto-init on Streamlit Cloud - users must authenticate manually there
# Detect cloud by checking multiple indicators
is_cloud = (
    os.environ.get('STREAMLIT_SHARING_MODE') or 
    os.environ.get('STREAMLIT_SERVER_HEADLESS') or
    '/mount/src' in str(Path.home()) or  # Streamlit Cloud home path
    os.environ.get('HOME', '').startswith('/mount/')
)

if not st.session_state.gee_authenticated and not st.session_state.gee_init_attempted:
    st.session_state.gee_init_attempted = True
    
    # First, try to re-authenticate from session state (for Streamlit reruns)
    if 'gee_credentials_content' in st.session_state and 'gee_project_id' in st.session_state:
        try:
            success, error = initialize_with_credentials_content(
                st.session_state.gee_credentials_content,
                st.session_state.gee_project_id
            )
            if success:
                st.session_state.gee_authenticated = True
                st.session_state.gee_auth_method = 'cached_credentials'
        except Exception:
            pass  # Fall through to manual auth
    
    # If still not authenticated, try Streamlit secrets (for cloud deployment)
    if not st.session_state.gee_authenticated and is_cloud:
        # Debug: Check for secrets
        secrets_found = False
        gee_creds = None
        
        try:
            # Try different secret formats
            if hasattr(st, 'secrets'):
                # Format 1: Nested TOML [gee_credentials] section
                if 'gee_credentials' in st.secrets:
                    gee_creds = dict(st.secrets['gee_credentials'])
                    secrets_found = True
                # Format 2: JSON string in gee_service_account
                elif 'gee_service_account' in st.secrets:
                    gee_creds = json.loads(st.secrets['gee_service_account'])
                    secrets_found = True
                # Format 3: Individual keys at root level
                elif 'private_key' in st.secrets and 'client_email' in st.secrets:
                    gee_creds = dict(st.secrets)
                    secrets_found = True
        except Exception as e:
            st.session_state.gee_error = f"Error reading secrets: {str(e)[:100]}"
        
        st.session_state.secrets_debug = f"Cloud: True, Secrets found: {secrets_found}"
        
        if secrets_found and gee_creds:
            try:
                import google.oauth2.service_account
                
                # Debug: Show project being used
                project_id = gee_creds.get('project_id', 'NOT FOUND')
                st.session_state.secrets_project = project_id
                
                credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                    gee_creds,
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                
                if project_id and project_id != 'NOT FOUND':
                    ee.Initialize(credentials, project=project_id, opt_url='https://earthengine-highvolume.googleapis.com')
                    st.session_state.gee_authenticated = True
                    st.session_state.gee_auth_method = 'streamlit_secrets'
                    st.session_state.gee_project_used = project_id
                else:
                    st.session_state.gee_error = "No project_id found in secrets"
            except Exception as e:
                # Store error for display
                st.session_state.gee_error = f"Secrets init failed: {str(e)[:200]}"
        elif not secrets_found:
            st.session_state.gee_error = "No GEE credentials found in Streamlit secrets. Add [gee_credentials] section."
    else:
        # Only try auto-initialize locally (cloud has no local credentials)
        try:
            success, method = try_auto_initialize()
            if success:
                st.session_state.gee_authenticated = True
                st.session_state.gee_auth_method = method
        except Exception:
            pass  # Silently fail on cloud

gee_available = st.session_state.gee_authenticated

# =============================================================================
# SESSION STATE - Store user selections
# =============================================================================
if 'aoi' not in st.session_state:
    st.session_state.aoi = None
if 'available_images' not in st.session_state:
    st.session_state.available_images = []
if 'selected_image_1' not in st.session_state:
    st.session_state.selected_image_1 = None
if 'selected_image_2' not in st.session_state:
    st.session_state.selected_image_2 = None

# =============================================================================
# VISITOR ANALYTICS (DISABLED FOR PERFORMANCE)
# =============================================================================
# Visitor analytics has been disabled as it adds file I/O overhead on every page load
# To re-enable, set ENABLE_ANALYTICS = True below
ENABLE_ANALYTICS = False
ANALYTICS_FILE = Path(__file__).parent / "visitor_analytics.json"

def load_analytics():
    """Load visitor analytics from JSON file (disabled for performance)"""
    if not ENABLE_ANALYTICS:
        return {'visits': []}
    try:
        if ANALYTICS_FILE.exists():
            with open(ANALYTICS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {'visits': []}

def save_analytics(data):
    """Save visitor analytics to JSON file (disabled for performance)"""
    if not ENABLE_ANALYTICS:
        return
    try:
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def record_visit():
    """Record a new visit with timestamp (disabled for performance)"""
    if not ENABLE_ANALYTICS:
        return
    try:
        data = load_analytics()
        now = datetime.datetime.now()
        visit = {
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'month': now.strftime('%Y-%m'),
            'year': now.strftime('%Y')
        }
        data['visits'].append(visit)
        save_analytics(data)
    except:
        pass

def get_visit_stats():
    """Get visit statistics by day, month, year"""
    data = load_analytics()
    visits = data.get('visits', [])
    
    if not visits:
        return {'total': 0, 'daily': {}, 'monthly': {}, 'yearly': {}}
    
    daily = {}
    monthly = {}
    yearly = {}
    
    for v in visits:
        d = v.get('date', 'unknown')
        m = v.get('month', 'unknown')
        y = v.get('year', 'unknown')
        
        daily[d] = daily.get(d, 0) + 1
        monthly[m] = monthly.get(m, 0) + 1
        yearly[y] = yearly.get(y, 0) + 1
    
    return {
        'total': len(visits),
        'daily': daily,
        'monthly': monthly,
        'yearly': yearly
    }

# Record this visit (only once per session)
if 'visit_recorded' not in st.session_state:
    try:
        record_visit()
        st.session_state.visit_recorded = True
    except Exception:
        # Silently fail if analytics fails
        st.session_state.visit_recorded = True

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

@st.cache_data(ttl=3600)
def parse_geojson(geojson_data):
    """Parse GeoJSON data and return ee.Geometry"""
    if isinstance(geojson_data, str):
        geojson_data = json.loads(geojson_data)
    
    if geojson_data['type'] == 'FeatureCollection':
        features = geojson_data['features']
        if len(features) > 0:
            geometry = features[0]['geometry']
        else:
            return None
    elif geojson_data['type'] == 'Feature':
        geometry = geojson_data['geometry']
    else:
        geometry = geojson_data
    
    return ee.Geometry(geometry)


def parse_shapefile_zip(uploaded_zip):
    """Parse uploaded shapefile zip and return ee.Geometry"""
    try:
        import geopandas as gpd
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Extract zip
            with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
            
            # Find .shp file
            shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
            if not shp_files:
                return None
            
            # Read shapefile
            gdf = gpd.read_file(os.path.join(tmpdir, shp_files[0]))
            
            # Convert to GeoJSON
            geojson = json.loads(gdf.to_json())
            return parse_geojson(geojson)
    except ImportError:
        st.error("Please install geopandas: pip install geopandas")
        return None
    except Exception as e:
        st.error(f"Error reading shapefile: {str(e)}")
        return None


@st.cache_data(ttl=3600, show_spinner="Searching for images...")
def get_image_list(sensor, start_date, end_date, _aoi, max_cloud=100):
    """Get list of available images with metadata (limited to 100 for performance)"""
    aoi = _aoi
    
    if sensor == "Sentinel-2":
        collection = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
        cloud_property = 'CLOUDY_PIXEL_PERCENTAGE'
        use_cloud_filter = True
    elif sensor == "Landsat 8/9":
        collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').merge(
            ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
        )
        cloud_property = 'CLOUD_COVER'
        use_cloud_filter = True
    elif sensor == "MODIS":
        collection = ee.ImageCollection('MODIS/061/MOD09A1')
        cloud_property = None  # MODIS 8-day composites don't have cloud property
        use_cloud_filter = False
    else:  # Landsat 5/7
        collection = ee.ImageCollection('LANDSAT/LT05/C02/T1_L2').merge(
            ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
        )
        cloud_property = 'CLOUD_COVER'
        use_cloud_filter = True
    
    # Filter collection
    filtered = collection \
        .filterDate(str(start_date), str(end_date)) \
        .filterBounds(aoi)
    
    # Apply cloud filter only if applicable
    if use_cloud_filter and cloud_property:
        filtered = filtered.filter(ee.Filter.lte(cloud_property, max_cloud))
    
    # PERFORMANCE: Limit to 100 most recent images
    filtered = filtered.sort('system:time_start', False).limit(100)
    
    # Get image info - optimized for performance
    try:
        # Get count first to show user
        count = filtered.size().getInfo()
        if count == 0:
            return []
        
        # Batch process image info
        def get_image_info(img):
            img_id = img.get('system:index')
            if cloud_property:
                cloud_val = img.get(cloud_property)
            else:
                cloud_val = 0
            return ee.Feature(None, {
                'id': img_id,
                'date': img.date().format('YYYY-MM-dd'),
                'cloud_cover': cloud_val,
                'sensor': sensor
            })
        
        info_collection = filtered.map(get_image_info)
        info_list = info_collection.getInfo()['features']
        return [f['properties'] for f in info_list]
    except ee.EEException as e:
        st.error(f"Earth Engine error: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Error fetching images: {str(e)}")
        return []


@st.cache_data(ttl=3600)
def get_single_image(sensor, image_id, _aoi):
    """Get a single image by ID using system:index"""
    aoi = _aoi
    try:
        # Use filter by system:index to get the exact image
        if sensor == "Sentinel-2":
            collection = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')
        elif sensor == "Landsat 8/9":
            collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').merge(
                ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
            )
        elif sensor == "MODIS":
            collection = ee.ImageCollection('MODIS/061/MOD09A1')
            # Apply scaling for MODIS
            collection = collection.map(lambda img: img.select(['sur_refl_b.*']).multiply(0.0001).copyProperties(img, img.propertyNames()))
        else:  # Landsat 5/7
            collection = ee.ImageCollection('LANDSAT/LT05/C02/T1_L2').merge(
                ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
            )
        
        # Filter by system:index to get the specific image
        filtered = collection.filter(ee.Filter.eq('system:index', image_id))
        img = ee.Image(filtered.first())
        
        return img.clip(aoi)
    except Exception as e:
        st.error(f"Error loading image {image_id}: {str(e)}")
        return None


@st.cache_data(ttl=3600)
def calculate_index_for_image(_image, index_name, sensor):
    """Calculate vegetation index for a given image"""
    image = _image
    bands = get_band_names(sensor)
    
    if sensor == "Sentinel-2":
        nir, red, green, blue = bands['nir'], bands['red'], bands['green'], bands['blue']
        swir = bands.get('swir1')
        rededge = bands.get('rededge1')
    else:
        nir, red, green, blue = bands['nir'], bands['red'], bands['green'], bands['blue']
        swir = bands.get('swir1')
        rededge = None
    
    if index_name == "NDVI":
        return calculate_ndvi(image, nir, red)
    elif index_name == "SAVI":
        return calculate_savi(image, nir, red)
    elif index_name == "EVI":
        return calculate_evi(image, nir, red, blue)
    elif index_name == "GNDVI":
        return calculate_gndvi(image, nir, green)
    elif index_name == "NDMI" and swir:
        return calculate_ndmi(image, nir, swir)
    elif index_name == "NDRE" and rededge:
        return calculate_ndre(image, nir, rededge)
    else:
        return calculate_ndvi(image, nir, red)  # Default to NDVI


# =============================================================================
# LOGIN-FIRST APPROACH: Block app until authenticated on cloud
# =============================================================================
if is_cloud and not st.session_state.gee_authenticated:
    # Show dedicated authentication page
    st.markdown("""
    <style>
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
        100% { transform: translateY(0px); }
    }
    .auth-hero {
        text-align: center;
        padding: 3rem 2rem;
        background: linear-gradient(135deg, #1a5f2a 0%, #2e8b3e 50%, #4ade80 100%);
        border-radius: 20px;
        color: white;
        margin: 1rem 0 2rem 0;
        box-shadow: 0 15px 40px rgba(46, 139, 62, 0.3);
    }
    .auth-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        animation: float 4s ease-in-out infinite;
        display: inline-block;
    }
    .auth-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .auth-subtitle {
        font-size: 1.1rem;
        opacity: 0.95;
        margin-bottom: 1.5rem;
    }
    .auth-badge {
        display: inline-block;
        background: rgba(255, 255, 255, 0.2);
        padding: 0.5rem 1.5rem;
        border-radius: 50px;
        font-size: 0.9rem;
    }
    </style>
    <div class="auth-hero">
        <div class="auth-icon">🌾</div>
        <div class="auth-title">AgriVision Pro</div>
        <div class="auth-subtitle">Agricultural Vegetation Analysis powered by Google Earth Engine</div>
        <div class="auth-badge">🔐 Authentication Required</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("## 🔐 Google Earth Engine Authentication")
    st.info("To use this application, you need to authenticate with Google Earth Engine using your own credentials.")
    
    # Initialize project ID
    if 'gee_project_id' not in st.session_state:
        st.session_state.gee_project_id = ''
    
    # Project ID input
    project_id = st.text_input(
        "📋 Your GEE Project ID:",
        value=st.session_state.gee_project_id,
        placeholder="e.g., ee-yourproject",
        help="Required. Find this in your Google Cloud Console or GEE Code Editor."
    )
    st.session_state.gee_project_id = project_id
    
    if not project_id:
        st.warning("⚠️ Project ID is required")
    
    st.markdown("---")
    
    # Authentication method tabs
    auth_tab1, auth_tab2 = st.tabs(["📁 Upload Credentials File (Recommended)", "💻 Local Development"])
    
    with auth_tab1:
        st.markdown("### Upload Your Earth Engine Credentials")
        
        import platform
        system = platform.system()
        if system == "Windows":
            creds_path = f"C:\\Users\\[USERNAME]\\.config\\earthengine\\credentials"
        elif system == "Darwin":
            creds_path = "~/.config/earthengine/credentials"
        else:
            creds_path = "~/.config/earthengine/credentials"
        
        st.info(f"""
        📂 **Your credentials file is at:**
        `{creds_path}`
        
        **Tip:** Copy this path, navigate to it in your file explorer, and upload the `credentials` file below.
        """)
        
        uploaded_file = st.file_uploader(
            "Upload Earth Engine Credentials File",
            type=None,
            help="Upload the file named 'credentials' (no extension) from the path above"
        )
        
        with st.expander("📋 First time? How to get your credentials file"):
            st.markdown("""
            **Prerequisites:**
            - Google Earth Engine Account → [Sign up FREE](https://earthengine.google.com/signup/)
            - Python installed → [python.org](https://python.org)
            
            **One-Time Setup:**
            1. Open Terminal/Command Prompt
            2. Install Earth Engine API:
               ```bash
               pip install earthengine-api
               ```
            3. Authenticate:
               ```bash
               earthengine authenticate
               ```
            4. Follow the browser link and log in
            5. Your credentials file is now saved locally
            6. Upload it here to use this app!
            """)
        
        if uploaded_file is not None:
            try:
                raw = uploaded_file.read()
                if isinstance(raw, bytes):
                    credentials_content = raw.decode('utf-8')
                else:
                    credentials_content = str(raw)
                
                st.success("✅ Credentials file loaded!")
                
                if st.button("🚀 Connect to Google Earth Engine", type="primary", disabled=not project_id, use_container_width=True):
                    with st.spinner("🔄 Authenticating..."):
                        success, error = initialize_with_credentials_content(credentials_content, project_id)
                        if success:
                            st.session_state.gee_authenticated = True
                            st.session_state.gee_auth_method = "uploaded_credentials"
                            st.success("✅ Successfully authenticated!")
                            st.balloons()
                            import time
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"❌ Authentication failed: {error}")
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)[:100]}")
    
    with auth_tab2:
        st.markdown("### Local Development Only")
        st.warning("""
        ⚠️ **This method only works if you:**
        - Are running the app locally with `streamlit run streamlit_app.py`
        - Have already run `earthengine authenticate` on your machine
        
        **If using the hosted website, use the "Upload Credentials File" tab instead.**
        """)
        
        if st.button("Try Local Authentication", disabled=not project_id, use_container_width=True):
            with st.spinner("🔄 Checking local credentials..."):
                success, method = try_auto_initialize()
                if success:
                    st.session_state.gee_authenticated = True
                    st.session_state.gee_auth_method = method or 'local_credentials'
                    st.success("✅ Authenticated using local credentials!")
                    st.rerun()
                else:
                    st.error("❌ Local authentication failed. Please use the Upload method on cloud.")
    
    # Show any errors
    if 'gee_error' in st.session_state:
        st.error(f"Authentication error: {st.session_state.gee_error}")
    
    st.markdown("---")
    st.info("🌍 **Once authenticated**, you'll have access to satellite vegetation analysis, image comparison, and more!")
    
    # Stop here - don't show the rest of the app until authenticated
    st.stop()

# =============================================================================
# SIDEBAR - Navigation (only shown after authentication)
# =============================================================================
st.sidebar.title("🌾 AgriVision Pro")
st.sidebar.markdown("Satellite & Drone Vegetation Analysis")
st.sidebar.markdown("---")

# =============================================================================
# GEE AUTHENTICATION - Users authenticate with their own GEE account
# =============================================================================
st.sidebar.subheader("🔐 GEE Authentication")
st.sidebar.caption("*Use your own GEE credentials*")

# Initialize project ID in session state
if 'gee_project_id' not in st.session_state:
    st.session_state.gee_project_id = ''

# Show current authentication status
if st.session_state.gee_authenticated:
    st.sidebar.success("✅ Connected to Google Earth Engine")
    auth_method = st.session_state.gee_auth_method
    if auth_method == "uploaded_credentials":
        st.sidebar.caption("📁 Using uploaded credentials")
    elif auth_method in ["local_credentials", "default", "already_initialized"]:
        st.sidebar.caption("🏠 Using local credentials")
    elif auth_method == "streamlit_secrets":
        st.sidebar.caption("🔑 Using Streamlit Secrets")
        if 'gee_project_used' in st.session_state:
            st.sidebar.caption(f"Project: {st.session_state.gee_project_used}")
    elif auth_method == "oauth":
        st.sidebar.caption("🌐 Using OAuth")
    else:
        st.sidebar.caption(f"Method: {auth_method}")
    
    # Option to disconnect/re-authenticate
    if st.sidebar.button("🔄 Sign Out / Re-authenticate"):
        st.session_state.gee_authenticated = False
        st.session_state.gee_init_attempted = False
        if 'gee_error' in st.session_state:
            del st.session_state['gee_error']
        if 'uploaded_credentials' in st.session_state:
            del st.session_state['uploaded_credentials']
        st.rerun()
else:
    # Not authenticated - show authentication options
    st.sidebar.warning("⚠️ Not Connected")
    
    # Show debug info on cloud
    if is_cloud:
        st.sidebar.error("🔒 **Streamlit Cloud Detected**")
        
        # Show secrets debug info
        if 'secrets_debug' in st.session_state:
            st.sidebar.caption(st.session_state.secrets_debug)
        if 'secrets_project' in st.session_state:
            st.sidebar.caption(f"Project from secrets: {st.session_state.secrets_project}")
        if 'gee_error' in st.session_state:
            st.sidebar.error(f"Error: {st.session_state.gee_error}")
        
        st.sidebar.markdown("""
        **Setup Required:**
        1. Go to **Manage app** → **Settings** → **Secrets**
        2. Add your GEE service account credentials in TOML format:
        
        ```toml
        [gee_credentials]
        type = "service_account"
        project_id = "your-project-id"
        private_key = "..."
        client_email = "..."
        ```
        3. Save and **Reboot app**
        """)
        
        if st.sidebar.button("🔄 Retry Authentication"):
            st.session_state.gee_init_attempted = False
            st.session_state.gee_authenticated = False
            if 'gee_error' in st.session_state:
                del st.session_state['gee_error']
            st.rerun()
    else:
        # Local environment - show manual auth options
        st.sidebar.info("**You need a Google Earth Engine account** to use this app.")
        
        # Project ID input (required for GEE)
        project_id = st.sidebar.text_input(
            "📋 Your GEE Project ID:",
            value=st.session_state.gee_project_id,
            placeholder="e.g., ee-yourproject",
            help="Required. Find this in your GEE Console."
        )
        st.session_state.gee_project_id = project_id
        
        if not project_id:
            st.sidebar.caption("⚠️ Project ID required")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**🔑 Authentication Options**")

        auth_method = st.sidebar.radio(
            "Choose authentication method:",
            [
                "🏠 Local (run `earthengine authenticate` on this machine)",
                "📁 Upload Credentials File"
            ],
            key="auth_method_select"
        )

    st.sidebar.markdown("---")

    if auth_method.startswith("🏠"):
        st.sidebar.info("Use credentials already present on this machine (local auth)")
        if st.sidebar.button("Try Local Authentication", use_container_width=True, disabled=not project_id):
            with st.spinner("🔄 Checking local credentials..."):
                success, method = try_auto_initialize()
                if success:
                    st.session_state.gee_authenticated = True
                    st.session_state.gee_auth_method = method or 'local_credentials'
                    st.sidebar.success("✅ Authenticated using local credentials")
                    st.balloons()
                    st.rerun()
                else:
                    st.sidebar.error("❌ Local authentication failed. Try uploading credentials or paste a refresh token.")

    elif auth_method.startswith("📁"):
        st.sidebar.caption("Upload your Earth Engine credentials file (the file named 'credentials')")
        uploaded_file = st.sidebar.file_uploader(
            "📁 Select credentials file",
            type=None,
            help="Upload the file named 'credentials' from ~/.config/earthengine/",
            label_visibility="collapsed"
        )

        if uploaded_file is not None:
            try:
                raw = uploaded_file.read()
                # uploaded_file.read() returns bytes
                if isinstance(raw, bytes):
                    credentials_content = raw.decode('utf-8')
                else:
                    credentials_content = str(raw)

                st.session_state.uploaded_credentials = True
                st.sidebar.success("✅ File loaded (preview hidden for security)")

                if st.sidebar.button("🔗 Connect to Google Earth Engine", use_container_width=True, disabled=not project_id):
                    with st.spinner("🔄 Initializing with uploaded credentials..."):
                        success, error = initialize_with_credentials_content(credentials_content, project_id)
                        if success:
                            st.session_state.gee_authenticated = True
                            st.session_state.gee_auth_method = "uploaded_credentials"
                            st.sidebar.success("✅ Successfully authenticated!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Connection failed")
                            st.sidebar.error(f"Error: {error}")
            except Exception as e:
                st.sidebar.error(f"❌ Error reading file: {str(e)[:100]}")

    st.sidebar.markdown("---")

    # Help / guidance
    with st.sidebar.expander("❓ Credentials Help"):
        st.markdown("""
        - **Local**: Run `earthengine authenticate` on the machine running this app.
        - **Upload**: Upload the file named `credentials` created by `earthengine authenticate`.
        """)
    
    # Show error if any
    if 'gee_error' in st.session_state and st.session_state.gee_error:
        st.sidebar.error(f"❌ {st.session_state.gee_error[:120]}...")

st.sidebar.markdown("---")

# Navigation (only show if authenticated, or show all for Upload Image which doesn't need GEE)
page = st.sidebar.radio(
    "Select Tool:",
    ["🛰️ Satellite Analysis", 
     "🔄 Compare Images",
     "📷 Upload Image", 
     "📊 Visitor Stats",
     "❓ Help"]
)

# Clear old session state when switching pages to save memory
if 'last_page' not in st.session_state:
    st.session_state.last_page = page
elif st.session_state.last_page != page:
    # Clear page-specific session state
    keys_to_clear = ['available_images', 'selected_image_1', 'selected_image_2',
                     'images1', 'images2', 'compare_img1', 'compare_img2']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.last_page = page
    
    # Reinitialize essential session state variables
    if 'available_images' not in st.session_state:
        st.session_state.available_images = []
    if 'selected_image_1' not in st.session_state:
        st.session_state.selected_image_1 = None
    if 'selected_image_2' not in st.session_state:
        st.session_state.selected_image_2 = None

st.sidebar.markdown("---")
st.sidebar.info("**v2.0** - Multi-sensor | Draw AOI | Compare Images")

# =============================================================================
# PAGE 1: SATELLITE ANALYSIS (Enhanced Layout)
# =============================================================================
if page == "🛰️ Satellite Analysis":
    st.title("🛰️ Satellite Imagery Analysis")
    
    if not gee_available:
        # Check if we're on Streamlit Cloud
        if os.environ.get('STREAMLIT_SHARING_MODE') or os.environ.get('STREAMLIT_SERVER_HEADLESS'):
            st.error("⚠️ **Google Earth Engine Authentication Required**")
            st.markdown("""
            This app is running on Streamlit Cloud and needs GEE Service Account credentials.
            
            **To fix this:**
            1. The app admin needs to add GEE Service Account credentials to Streamlit Secrets
            2. See `STREAMLIT_CLOUD_SETUP.md` in the repository for detailed instructions
            3. Or use the app locally by running `streamlit run app.py` on your computer
            
            **For app admin:** Go to [Manage App](https://share.streamlit.io/) → Settings → Secrets
            """)
        else:
            st.error("⚠️ **Google Earth Engine not authenticated.**")
            st.markdown("""
            **To authenticate locally:**
            1. Run in terminal: `earthengine authenticate`
            2. Follow the instructions to authenticate
            3. Restart this app
            
            See `AUTHENTICATION_GUIDE.md` for detailed instructions.
            """)
        st.stop()
    
    # -------------------------------------------------------------------------
    # SECTION 1: Define Area of Interest
    # -------------------------------------------------------------------------
    st.subheader("1️⃣ Define Area of Interest")
    
    aoi_method = st.radio(
        "How to define your area:",
        ["📍 Coordinates + Buffer", "📁 Upload File (GeoJSON/Shapefile)", "✏️ Draw on Map"],
        horizontal=True,
        key="sat_aoi_method"
    )
    
    aoi = None
    map_center = [39.0, -98.0]
    map_zoom = 5
    
    if aoi_method == "📍 Coordinates + Buffer":
        col_coord1, col_coord2, col_coord3 = st.columns(3)
        with col_coord1:
            lat = st.number_input("Latitude:", value=39.0, min_value=-90.0, max_value=90.0, key="sat_lat")
        with col_coord2:
            lon = st.number_input("Longitude:", value=-98.0, min_value=-180.0, max_value=180.0, key="sat_lon")
        with col_coord3:
            buffer_km = st.slider("Buffer (km):", min_value=1, max_value=50, value=10, key="sat_buf")
        
        point = ee.Geometry.Point([lon, lat])
        aoi = point.buffer(buffer_km * 1000)
        map_center = [lat, lon]
        map_zoom = 10
    
    elif aoi_method == "📁 Upload File (GeoJSON/Shapefile)":
        uploaded_file = st.file_uploader(
            "Upload GeoJSON or Shapefile (zip):",
            type=['geojson', 'json', 'zip'],
            key="sat_upload"
        )
        
        if uploaded_file:
            if uploaded_file.name.endswith('.zip'):
                aoi = parse_shapefile_zip(uploaded_file)
            else:
                geojson_str = uploaded_file.read().decode('utf-8')
                aoi = parse_geojson(geojson_str)
            
            if aoi:
                try:
                    centroid = aoi.centroid().getInfo()['coordinates']
                    map_center = [centroid[1], centroid[0]]
                    map_zoom = 10
                except:
                    pass
    
    else:  # Draw on Map
        st.info("👇 **Draw a polygon or rectangle on the map below.** Use the drawing tools on the left side of the map.")
        
        # Create a folium map with drawing controls
        draw_map = folium.Map(location=[39.0, -98.0], zoom_start=5)
        
        # Add drawing controls
        draw = Draw(
            export=False,
            draw_options={
                'polyline': False,
                'polygon': True,
                'rectangle': True,
                'circle': False,
                'marker': False,
                'circlemarker': False
            },
            edit_options={'edit': False}
        )
        draw.add_to(draw_map)
        
        # Display map and capture drawings
        output = st_folium(draw_map, width=700, height=400, key="draw_map_sat")
        
        # Process drawn geometry
        if output and output.get('all_drawings'):
            drawings = output['all_drawings']
            if drawings and len(drawings) > 0:
                last_drawing = drawings[-1]  # Get the most recent drawing
                geom_type = last_drawing.get('geometry', {}).get('type')
                coords = last_drawing.get('geometry', {}).get('coordinates')
                
                if geom_type == 'Polygon' and coords:
                    # Convert to EE geometry
                    aoi = ee.Geometry.Polygon(coords)
                    try:
                        centroid = aoi.centroid().getInfo()['coordinates']
                        map_center = [centroid[1], centroid[0]]
                        map_zoom = 12
                    except:
                        map_center = [39.0, -98.0]
                        map_zoom = 10
                    st.success(f"✅ Polygon captured! ({len(coords[0])} points)")
        
        if aoi is None:
            st.warning("⚠️ Please draw a polygon or rectangle on the map above")
    
    # AOI Preview Map with Confirm Button
    if aoi is not None:
        if st.button("✅ Confirm AOI & Show on Map", type="primary"):
            st.session_state.confirmed_aoi = aoi
            st.session_state.aoi_center = map_center
            st.success("✅ Area of Interest confirmed!")
    
    # Show AOI preview map
    if 'confirmed_aoi' in st.session_state and st.session_state.confirmed_aoi is not None:
        st.markdown("**📍 Your Area of Interest:**")
        preview_map = geemap.Map(center=st.session_state.aoi_center, zoom=11)
        # Create an outline image from the AOI geometry
        aoi_fc = ee.FeatureCollection([ee.Feature(st.session_state.confirmed_aoi)])
        aoi_outline = ee.Image().byte().paint(featureCollection=aoi_fc, color=1, width=2)
        preview_map.addLayer(aoi_outline, {'palette': ['blue']}, 'AOI Boundary')
        preview_map.centerObject(st.session_state.confirmed_aoi)
        preview_map.to_streamlit(height=300)
    
    st.markdown("---")
    
    # -------------------------------------------------------------------------
    # SECTION 2: Select Satellite & Dates
    # -------------------------------------------------------------------------
    st.subheader("2️⃣ Select Satellite & Dates")
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    
    with col_s1:
        sensor = st.selectbox("Satellite:", ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"])
    
    today = datetime.date.today()
    # Set default date range based on sensor
    if sensor == "MODIS":
        # MODIS: 8-day composites, suggest 3-6 months
        default_start = today - datetime.timedelta(days=90)
        date_info = "📅 MODIS uses 8-day composites. Available from Feb 2000 to present."
    elif sensor == "Landsat 5/7":
        # Landsat 5/7: Historical data
        default_start = datetime.date(1990, 1, 1)
        date_info = "📅 Landsat 5/7 available from 1984 to 2012. Select historical dates."
    else:
        # Sentinel-2 and Landsat 8/9: Recent data
        default_start = today - datetime.timedelta(days=30)
        if sensor == "Sentinel-2":
            date_info = "📅 Sentinel-2 available from June 2015 to present."
        else:
            date_info = "📅 Landsat 8/9 available from April 2013 to present."
    
    st.info(date_info)
    
    with col_s2:
        start_date = st.date_input("Start:", value=default_start)
    with col_s3:
        end_date = st.date_input("End:", value=today)
    with col_s4:
        max_cloud = st.slider("Max Cloud %:", 0, 100, 30)
    
    # Add composite option
    st.markdown("**Image Composite Option:**")
    col_c1, col_c2 = st.columns([2, 3])
    with col_c1:
        composite_option = st.radio(
            "Use:",
            ["Individual Image", "Mean Composite", "Median Composite"],
            key="composite_sat"
        )
    with col_c2:
        if composite_option != "Individual Image":
            st.info(f"Will use {composite_option.split()[0].lower()} of all images in date range")
    
    st.markdown("---")
    
    # -------------------------------------------------------------------------
    # SECTION 3: Browse Available Images
    # -------------------------------------------------------------------------
    st.subheader("3️⃣ Browse Available Images")
    
    confirmed_aoi = st.session_state.get('confirmed_aoi', None)
    
    if confirmed_aoi is not None:
        if st.button("🔍 Search Images", type="primary"):
            images = get_image_list(sensor, start_date, end_date, confirmed_aoi, max_cloud)
            st.session_state.available_images = images
            if images:
                st.success(f"Found {len(images)} images!")
            else:
                st.warning("No images found. Try different dates or increase cloud %.")
    else:
        st.warning("⚠️ Please confirm your Area of Interest first (click the button above)")
    
    # Display available images in a cleaner format
    if 'available_images' in st.session_state and st.session_state.available_images:
        st.markdown("**Select an image:**")
        # Limit display to first 50 images to prevent performance issues
        max_display = min(50, len(st.session_state.available_images))
        image_options = []
        for img in st.session_state.available_images[:max_display]:
            cloud = img.get('cloud_cover', 'N/A')
            if isinstance(cloud, (int, float)):
                cloud = f"{cloud:.1f}%"
            image_options.append(f"📅 {img['date']} | ☁️ {cloud}")
        
        if len(st.session_state.available_images) > max_display:
            st.info(f"ℹ️ Showing first {max_display} of {len(st.session_state.available_images)} images")
        
        selected_idx = st.selectbox("Available Images:", range(len(image_options)), format_func=lambda x: image_options[x])
        st.session_state.selected_image_1 = st.session_state.available_images[selected_idx]
    
    st.markdown("---")
    
    # -------------------------------------------------------------------------
    # SECTION 4: Calculate Index & Generate Map
    # -------------------------------------------------------------------------
    st.subheader("4️⃣ Calculate Vegetation Index")
    
    col_idx1, col_idx2 = st.columns([1, 2])
    
    with col_idx1:
        if sensor == "Sentinel-2":
            index_options = ["NDVI", "SAVI", "EVI", "GNDVI", "NDMI", "NDRE"]
        else:
            index_options = ["NDVI", "SAVI", "EVI", "GNDVI", "NDMI"]
        
        selected_index = st.selectbox("Vegetation Index:", index_options)
    
    with col_idx2:
        st.info(f"**{selected_index}** will be calculated for the selected image/composite")
    
    generate_btn = st.button("🗺️ Generate Vegetation Map", type="primary", use_container_width=True)
    
    # -------------------------------------------------------------------------
    # RESULT MAP - Displayed below the button
    # -------------------------------------------------------------------------
    if generate_btn and confirmed_aoi:
        st.markdown("---")
        st.subheader("📊 Result Map")
        
        with st.spinner("Generating vegetation map..."):
            try:
                # Get image based on composite option
                if composite_option == "Individual Image":
                    # If a specific image is selected, use it
                    if st.session_state.selected_image_1:
                        img_info = st.session_state.selected_image_1
                        image = get_single_image(sensor, img_info['id'], confirmed_aoi)
                        if image is None:
                            st.error("Failed to load the selected image. Please try another image.")
                            st.stop()
                        title_suffix = f" ({img_info['date']})"
                    else:
                        st.warning("⚠️ Please search and select an image first")
                        st.stop()
                else:
                    # Use composite (mean or median)
                    if sensor == "Sentinel-2":
                        collection = get_sentinel2_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                    elif sensor == "Landsat 8/9":
                        collection = get_landsat89_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                    elif sensor == "MODIS":
                        collection = get_modis_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                    else:
                        collection = get_landsat57_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                    
                    if composite_option == "Mean Composite":
                        image = collection.mean().clip(confirmed_aoi)
                        title_suffix = " (Mean Composite)"
                    else:
                        image = collection.median().clip(confirmed_aoi)
                        title_suffix = " (Median Composite)"
                
                # Calculate index
                index_image = calculate_index_for_image(image, selected_index, sensor)
                
                # Visualization
                vis_params = {
                    'min': -0.2, 'max': 0.8,
                    'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
                }
                
                # Create result map
                result_map = geemap.Map(center=st.session_state.aoi_center, zoom=12)
                # Create an outline image from the AOI geometry
                aoi_fc = ee.FeatureCollection([ee.Feature(confirmed_aoi)])
                aoi_outline = ee.Image().byte().paint(featureCollection=aoi_fc, color=1, width=2)
                result_map.addLayer(aoi_outline, {'palette': ['blue']}, 'AOI Boundary')
                result_map.addLayer(index_image, vis_params, f'{selected_index}{title_suffix}')
                result_map.centerObject(confirmed_aoi)
                result_map.to_streamlit(height=500)
                
                st.success(f"✅ {selected_index} map generated successfully!")
                
                # Legend
                st.markdown("""
                **Legend:** 🔴 Low vegetation (-0.2) → 🟡 Moderate → 🟢 High vegetation (0.8)
                """)
                
                # Download options
                st.markdown("---")
                st.subheader("💾 Download Image")
                col_dl1, col_dl2 = st.columns(2)
                
                with col_dl1:
                    if st.button("📥 Download as PNG", key="dl_png_sat"):
                        try:
                            # Get the thumbnail URL
                            url = index_image.getThumbURL({
                                'min': -0.2, 'max': 0.8,
                                'palette': ['d73027', 'fc8d59', 'fee08b', 'd9ef8b', '91cf60', '1a9850'],
                                'dimensions': 512,
                                'format': 'png'
                            })
                            st.markdown(f"[🔗 Click here to download PNG]({url})")
                        except Exception as e:
                            st.error(f"Error generating PNG: {str(e)}")
                
                with col_dl2:
                    if st.button("📥 Download as GeoTIFF", key="dl_tiff_sat"):
                        try:
                            url = index_image.getDownloadURL({
                                'scale': 30,
                                'crs': 'EPSG:4326',
                                'fileFormat': 'GeoTIFF',
                                'region': confirmed_aoi
                            })
                            st.markdown(f"[🔗 Click here to download GeoTIFF]({url})")
                        except Exception as e:
                            st.error(f"Error generating GeoTIFF: {str(e)}")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    # -------------------------------------------------------------------------
    # SECTION 5: Time Series Analysis
    # -------------------------------------------------------------------------
    if 'available_images' in st.session_state and st.session_state.available_images and confirmed_aoi:
        st.markdown("---")
        st.subheader("📈 Time Series Analysis")
        
        if len(st.session_state.available_images) > 1:
            st.info(f"Analyzing {len(st.session_state.available_images)} images over time")
            
            if st.button("📊 Generate Time Series Chart", type="primary"):
                with st.spinner("Calculating time series..."):
                    try:
                        # Calculate index for all images
                        dates = []
                        values = []
                        
                        for img_info in st.session_state.available_images[:20]:  # Limit to 20 for performance
                            img = get_single_image(sensor, img_info['id'], confirmed_aoi)
                            if img is not None:
                                idx_img = calculate_index_for_image(img, selected_index, sensor)
                                # Calculate mean value over AOI
                                mean_val = idx_img.reduceRegion(
                                    reducer=ee.Reducer.mean(),
                                    geometry=confirmed_aoi,
                                    scale=30,
                                    maxPixels=1e9
                                ).getInfo()
                                
                                if selected_index in mean_val or 'NDVI' in mean_val:
                                    val = mean_val.get(selected_index, mean_val.get('NDVI'))
                                    if val is not None:
                                        dates.append(img_info['date'])
                                        values.append(val)
                        
                        if dates and values:
                            # Create DataFrame
                            import pandas as pd
                            df_ts = pd.DataFrame({'Date': dates, selected_index: values})
                            df_ts['Date'] = pd.to_datetime(df_ts['Date'])
                            df_ts = df_ts.sort_values('Date')
                            
                            # Plot
                            st.line_chart(df_ts.set_index('Date'))
                            
                            # Show statistics
                            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                            col_s1.metric("Min", f"{df_ts[selected_index].min():.3f}")
                            col_s2.metric("Max", f"{df_ts[selected_index].max():.3f}")
                            col_s3.metric("Mean", f"{df_ts[selected_index].mean():.3f}")
                            col_s4.metric("Std Dev", f"{df_ts[selected_index].std():.3f}")
                            
                            # Show data table
                            with st.expander("📋 View Data Table"):
                                st.dataframe(df_ts, use_container_width=True)
                        else:
                            st.warning("Could not calculate time series values")
                    except Exception as e:
                        st.error(f"Error generating time series: {str(e)}")
        else:
            st.info("Need at least 2 images for time series analysis")
    
    # -------------------------------------------------------------------------
    # SECTION 6: Variable Comparison
    # -------------------------------------------------------------------------
    if 'available_images' in st.session_state and st.session_state.available_images and confirmed_aoi:
        st.markdown("---")
        st.subheader("🔬 Variable Comparison")
        st.info("Compare different vegetation indices to understand various aspects of vegetation health")
        
        # Define available indices based on sensor
        if sensor == "Sentinel-2":
            available_indices = {
                "NDVI": "Normalized Difference Vegetation Index - General vegetation health",
                "SAVI": "Soil Adjusted Vegetation Index - Reduces soil brightness influence",
                "EVI": "Enhanced Vegetation Index - Better for dense vegetation",
                "GNDVI": "Green NDVI - Sensitive to chlorophyll content",
                "NDMI": "Normalized Difference Moisture Index - Water stress detection",
                "NDRE": "Normalized Difference Red Edge - Nitrogen content"
            }
        else:
            available_indices = {
                "NDVI": "Normalized Difference Vegetation Index - General vegetation health",
                "SAVI": "Soil Adjusted Vegetation Index - Reduces soil brightness influence",
                "EVI": "Enhanced Vegetation Index - Better for dense vegetation",
                "GNDVI": "Green NDVI - Sensitive to chlorophyll content",
                "NDMI": "Normalized Difference Moisture Index - Water stress detection"
            }
        
        # Select indices to compare
        available_indices_list = list(available_indices.keys())
        col_idx1, col_idx2 = st.columns(2)
        with col_idx1:
            compare_index_1 = st.selectbox("Select First Index", available_indices_list, index=0, key="comp_idx_1")
        with col_idx2:
            compare_index_2 = st.selectbox("Select Second Index", available_indices_list, index=1, key="comp_idx_2")
        
        if st.button("🔍 Compare Indices", type="primary"):
            if compare_index_1 == compare_index_2:
                st.warning("⚠️ Please select different indices to compare")
            else:
                with st.spinner(f"Comparing {compare_index_1} vs {compare_index_2}..."):
                    try:
                        # Get image based on composite option
                        if composite_option == "Individual Image" and st.session_state.selected_image_1:
                            img_info = st.session_state.selected_image_1
                            image = get_single_image(sensor, img_info['id'], confirmed_aoi)
                            img_date = img_info['date']
                        else:
                            # Use composite
                            if sensor == "Sentinel-2":
                                collection = get_sentinel2_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                            elif sensor == "Landsat 8/9":
                                collection = get_landsat89_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                            elif sensor == "MODIS":
                                collection = get_modis_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                            else:
                                collection = get_landsat57_collection(str(start_date), str(end_date), confirmed_aoi, max_cloud)
                            
                            if composite_option == "Mean Composite":
                                image = collection.mean().clip(confirmed_aoi)
                                img_date = f"{start_date} to {end_date} (Mean)"
                            else:
                                image = collection.median().clip(confirmed_aoi)
                                img_date = f"{start_date} to {end_date} (Median)"
                        
                        if image is not None:
                            # Calculate both indices
                            idx_img_1 = calculate_index_for_image(image, compare_index_1, sensor)
                            idx_img_2 = calculate_index_for_image(image, compare_index_2, sensor)
                            
                            # Get statistics for both indices
                            stats_1 = idx_img_1.reduceRegion(
                                reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
                                geometry=confirmed_aoi, scale=30, maxPixels=1e9
                            ).getInfo()
                            
                            stats_2 = idx_img_2.reduceRegion(
                                reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
                                geometry=confirmed_aoi, scale=30, maxPixels=1e9
                            ).getInfo()
                            
                            # Display side-by-side maps
                            st.markdown(f"**Date/Period:** {img_date}")
                            col_m1, col_m2 = st.columns(2)
                            
                            # Get map center from session state or calculate from AOI
                            if 'aoi_center' in st.session_state:
                                map_center = st.session_state.aoi_center
                            else:
                                # Calculate center from AOI
                                try:
                                    centroid = confirmed_aoi.centroid().getInfo()['coordinates']
                                    map_center = [centroid[1], centroid[0]]
                                except:
                                    map_center = [39.0, -98.0]
                            
                            with col_m1:
                                st.markdown(f"**{compare_index_1}**")
                                map1 = geemap.Map(center=map_center, zoom=12, basemap="SATELLITE")
                                map1.addLayer(idx_img_1, {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}, compare_index_1)
                                map1.centerObject(confirmed_aoi)
                                map1.to_streamlit(height=400)
                                
                                # Stats
                                st.metric("Mean", f"{stats_1.get(f'{compare_index_1}_mean', 0):.3f}")
                                col_min, col_max = st.columns(2)
                                col_min.metric("Min", f"{stats_1.get(f'{compare_index_1}_min', 0):.3f}")
                                col_max.metric("Max", f"{stats_1.get(f'{compare_index_1}_max', 0):.3f}")
                            
                            with col_m2:
                                st.markdown(f"**{compare_index_2}**")
                                map2 = geemap.Map(center=map_center, zoom=12, basemap="SATELLITE")
                                map2.addLayer(idx_img_2, {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']}, compare_index_2)
                                map2.centerObject(confirmed_aoi)
                                map2.to_streamlit(height=400)
                                
                                # Stats
                                st.metric("Mean", f"{stats_2.get(f'{compare_index_2}_mean', 0):.3f}")
                                col_min, col_max = st.columns(2)
                                col_min.metric("Min", f"{stats_2.get(f'{compare_index_2}_min', 0):.3f}")
                                col_max.metric("Max", f"{stats_2.get(f'{compare_index_2}_max', 0):.3f}")
                            
                            # Interpretation guide
                            with st.expander("📖 Interpretation Guide"):
                                st.markdown(f"""
                                **{compare_index_1}:** {available_indices[compare_index_1]}
                                
                                **{compare_index_2}:** {available_indices[compare_index_2]}
                                
                                **How to interpret:**
                                - Higher values generally indicate healthier/denser vegetation
                                - Compare spatial patterns to identify areas with different vegetation characteristics
                                - Different indices emphasize different aspects (chlorophyll content, moisture, biomass, etc.)
                                """)
                        else:
                            st.error("Failed to load image for comparison")
                    except Exception as e:
                        st.error(f"Error comparing indices: {str(e)}")

# =============================================================================
# PAGE 2: COMPARE IMAGES
# =============================================================================
elif page == "🔄 Compare Images":
    st.title("🔄 Compare Two Images")
    st.markdown("Compare vegetation indices between two different dates or sensors")
    
    if not gee_available:
        if os.environ.get('STREAMLIT_SHARING_MODE') or os.environ.get('STREAMLIT_SERVER_HEADLESS'):
            st.error("⚠️ Google Earth Engine Authentication Required - See app admin for setup")
        else:
            st.error("⚠️ Google Earth Engine not authenticated. Run `earthengine authenticate` first.")
        st.stop()
    
    # AOI Setup - Full options like Satellite Analysis
    st.subheader("1️⃣ Define Area of Interest")
    
    aoi_method_cmp = st.radio(
        "How to define your area:",
        ["📍 Coordinates + Buffer", "📁 Upload File (GeoJSON/Shapefile)", "✏️ Draw on Map"],
        key="cmp_aoi_method",
        horizontal=True
    )
    
    aoi = None
    cmp_map_center = [39.0, -98.0]
    
    if aoi_method_cmp == "📍 Coordinates + Buffer":
        col_aoi1, col_aoi2, col_aoi3 = st.columns(3)
        with col_aoi1:
            lat = st.number_input("Latitude:", value=39.0, key="cmp_lat")
        with col_aoi2:
            lon = st.number_input("Longitude:", value=-98.0, key="cmp_lon")
        with col_aoi3:
            buffer_km = st.slider("Buffer (km):", 1, 30, 10, key="cmp_buf")
        
        aoi = ee.Geometry.Point([lon, lat]).buffer(buffer_km * 1000)
        cmp_map_center = [lat, lon]
    
    elif aoi_method_cmp == "📁 Upload File (GeoJSON/Shapefile)":
        uploaded_file_cmp = st.file_uploader(
            "Upload GeoJSON or Shapefile (zip):",
            type=['geojson', 'json', 'zip'],
            key="cmp_upload"
        )
        
        if uploaded_file_cmp:
            if uploaded_file_cmp.name.endswith('.zip'):
                aoi = parse_shapefile_zip(uploaded_file_cmp)
            else:
                geojson_str = uploaded_file_cmp.read().decode('utf-8')
                aoi = parse_geojson(geojson_str)
            
            if aoi:
                try:
                    centroid = aoi.centroid().getInfo()['coordinates']
                    cmp_map_center = [centroid[1], centroid[0]]
                except:
                    pass
    
    else:  # Draw on Map
        st.info("👇 **Draw a polygon or rectangle on the map below.**")
        
        # Create a folium map with drawing controls
        cmp_draw_map = folium.Map(location=[39.0, -98.0], zoom_start=5)
        
        # Add drawing controls
        cmp_draw = Draw(
            export=False,
            draw_options={
                'polyline': False,
                'polygon': True,
                'rectangle': True,
                'circle': False,
                'marker': False,
                'circlemarker': False
            },
            edit_options={'edit': False}
        )
        cmp_draw.add_to(cmp_draw_map)
        
        # Display map and capture drawings
        cmp_output = st_folium(cmp_draw_map, width=700, height=350, key="draw_map_cmp")
        
        # Process drawn geometry
        if cmp_output and cmp_output.get('all_drawings'):
            cmp_drawings = cmp_output['all_drawings']
            if cmp_drawings and len(cmp_drawings) > 0:
                cmp_last_drawing = cmp_drawings[-1]
                cmp_geom_type = cmp_last_drawing.get('geometry', {}).get('type')
                cmp_coords = cmp_last_drawing.get('geometry', {}).get('coordinates')
                
                if cmp_geom_type == 'Polygon' and cmp_coords:
                    aoi = ee.Geometry.Polygon(cmp_coords)
                    try:
                        centroid = aoi.centroid().getInfo()['coordinates']
                        cmp_map_center = [centroid[1], centroid[0]]
                    except:
                        cmp_map_center = [39.0, -98.0]
                    st.success(f"✅ Polygon captured! ({len(cmp_coords[0])} points)")
        
        if aoi is None:
            st.warning("⚠️ Please draw a polygon or rectangle on the map above")
    
    # Confirm AOI Button and Preview Map
    if aoi is not None:
        if st.button("✅ Confirm AOI & Show on Map", type="primary", key="cmp_confirm"):
            st.session_state.compare_confirmed_aoi = aoi
            st.session_state.compare_aoi_center = cmp_map_center
            st.success("✅ Area of Interest confirmed!")
    
    # Show AOI preview map
    if 'compare_confirmed_aoi' in st.session_state and st.session_state.compare_confirmed_aoi is not None:
        st.markdown("**📍 Your Area of Interest:**")
        cmp_preview_map = geemap.Map(center=st.session_state.compare_aoi_center, zoom=11)
        # Create an outline image from the AOI geometry
        aoi_fc = ee.FeatureCollection([ee.Feature(st.session_state.compare_confirmed_aoi)])
        aoi_outline = ee.Image().byte().paint(featureCollection=aoi_fc, color=1, width=2)
        cmp_preview_map.addLayer(aoi_outline, {'palette': ['blue']}, 'AOI Boundary')
        cmp_preview_map.centerObject(st.session_state.compare_confirmed_aoi)
        cmp_preview_map.to_streamlit(height=250)
        aoi = st.session_state.compare_confirmed_aoi
    
    st.markdown("---")
    
    # SECTION 2: Sensor Selection Option
    st.subheader("2️⃣ Sensor Selection")
    
    sensor_mode = st.radio(
        "Compare:",
        ["Same Sensor (both images)", "Different Sensors (cross-sensor comparison)"],
        horizontal=True,
        key="sensor_mode"
    )
    
    if sensor_mode == "Same Sensor (both images)":
        # Single sensor and date range for both
        st.markdown("**Select sensor and date range for both images:**")
        col_sensor, col_date1, col_date2, col_cloud = st.columns(4)
        
        with col_sensor:
            sensor_cmp = st.selectbox("Satellite:", ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"], key="sensor_cmp")
        
        # Set default dates based on sensor
        today_cmp = datetime.date.today()
        if sensor_cmp == "MODIS":
            default_start_cmp = today_cmp - datetime.timedelta(days=90)
        elif sensor_cmp == "Landsat 5/7":
            default_start_cmp = datetime.date(1990, 1, 1)
            today_cmp = datetime.date(2012, 5, 5)  # Landsat 5/7 end date
        else:
            default_start_cmp = today_cmp - datetime.timedelta(days=60)
        
        with col_date1:
            start_date_cmp = st.date_input("Start Date:", value=default_start_cmp, key="cmp_start")
        with col_date2:
            end_date_cmp = st.date_input("End Date:", value=today_cmp, key="cmp_end")
        with col_cloud:
            cloud_cmp = st.slider("Max Cloud %:", 0, 100, 30, key="cloud_cmp")
        
        # Search for images once
        if aoi is not None:
            if st.button("🔍 Search Images", type="primary", key="search_cmp"):
                with st.spinner("Searching for images..."):
                    images = get_image_list(sensor_cmp, start_date_cmp, end_date_cmp, aoi, cloud_cmp)
                    st.session_state.compare_images = images
                    st.session_state.compare_sensor1 = sensor_cmp
                    st.session_state.compare_sensor2 = sensor_cmp
                    if images:
                        st.success(f"✅ Found {len(images)} images!")
                    else:
                        st.warning("⚠️ No images found. Try different dates or increase cloud %.")
        else:
            st.warning("⚠️ Please confirm your AOI first")
    
    else:  # Different Sensors
        st.markdown("**Select sensors and date ranges separately:**")
        
        col1, col2 = st.columns(2)
        
        # Sensor 1
        with col1:
            st.markdown("**📡 Sensor 1**")
            sensor1 = st.selectbox("Satellite:", ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"], key="sensor1_diff")
            
            # Set defaults based on sensor 1
            today1 = datetime.date.today()
            if sensor1 == "MODIS":
                default_start1 = today1 - datetime.timedelta(days=90)
            elif sensor1 == "Landsat 5/7":
                default_start1 = datetime.date(1990, 1, 1)
                today1 = datetime.date(2012, 5, 5)
            else:
                default_start1 = today1 - datetime.timedelta(days=60)
            
            start1 = st.date_input("Start Date:", value=default_start1, key="start1")
            end1 = st.date_input("End Date:", value=today1, key="end1")
            cloud1 = st.slider("Max Cloud %:", 0, 100, 30, key="cloud1")
            
            if aoi is not None:
                if st.button("🔍 Search", key="search1_diff"):
                    with st.spinner("Searching..."):
                        images1 = get_image_list(sensor1, start1, end1, aoi, cloud1)
                        st.session_state.compare_images1 = images1
                        st.session_state.compare_sensor1 = sensor1
                        if images1:
                            st.success(f"✅ Found {len(images1)} images!")
                        else:
                            st.warning("⚠️ No images found.")
            else:
                st.warning("⚠️ Confirm AOI first")
        
        # Sensor 2
        with col2:
            st.markdown("**📡 Sensor 2**")
            sensor2 = st.selectbox("Satellite:", ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"], key="sensor2_diff")
            
            # Set defaults based on sensor 2
            today2 = datetime.date.today()
            if sensor2 == "MODIS":
                default_start2 = today2 - datetime.timedelta(days=90)
            elif sensor2 == "Landsat 5/7":
                default_start2 = datetime.date(1990, 1, 1)
                today2 = datetime.date(2012, 5, 5)
            else:
                default_start2 = today2 - datetime.timedelta(days=60)
            
            start2 = st.date_input("Start Date:", value=default_start2, key="start2")
            end2 = st.date_input("End Date:", value=today2, key="end2")
            cloud2 = st.slider("Max Cloud %:", 0, 100, 30, key="cloud2")
            
            if aoi is not None:
                if st.button("🔍 Search", key="search2_diff"):
                    with st.spinner("Searching..."):
                        images2 = get_image_list(sensor2, start2, end2, aoi, cloud2)
                        st.session_state.compare_images2 = images2
                        st.session_state.compare_sensor2 = sensor2
                        if images2:
                            st.success(f"✅ Found {len(images2)} images!")
                        else:
                            st.warning("⚠️ No images found.")
            else:
                st.warning("⚠️ Confirm AOI first")
    
    st.markdown("---")
    
    # SECTION 3: Select what to compare
    st.subheader("3️⃣ Select Images or Composites to Compare")
    
    # Check if we have images available
    has_images_same = 'compare_images' in st.session_state and st.session_state.compare_images
    has_images_diff = ('compare_images1' in st.session_state and st.session_state.compare_images1) or \
                      ('compare_images2' in st.session_state and st.session_state.compare_images2)
    
    if has_images_same or has_images_diff:
        col1, col2 = st.columns(2)
        
        # IMAGE 1 Selection
        with col1:
            st.markdown("**📊 Image/Composite 1**")
            
            # Get images for sensor 1
            if sensor_mode == "Same Sensor (both images)":
                images_for_1 = st.session_state.get('compare_images', [])
            else:
                images_for_1 = st.session_state.get('compare_images1', [])
            
            if images_for_1:
                img1_type = st.radio(
                    "Type:",
                    ["Individual Image", "Composite (Mean)", "Composite (Median)"],
                    key="img1_type"
                )
                
                if img1_type == "Individual Image":
                    selected1 = st.selectbox(
                        "Select image:",
                        images_for_1,
                        format_func=lambda x: f"{x['date']} (☁️ {x.get('cloud_cover', 'N/A'):.1f}%)" if isinstance(x.get('cloud_cover'), (int, float)) else f"{x['date']}",
                        key="sel1_cmp"
                    )
                    st.session_state.compare_img1 = selected1
                    st.session_state.compare_img1_type = "individual"
                else:
                    composite_type = "mean" if "Mean" in img1_type else "median"
                    st.session_state.compare_img1_type = composite_type
                    st.info(f"Will use {composite_type.upper()} of {len(images_for_1)} images")
            else:
                st.warning("⚠️ Search for images first")
        
        # IMAGE 2 Selection
        with col2:
            st.markdown("**📊 Image/Composite 2**")
            
            # Get images for sensor 2
            if sensor_mode == "Same Sensor (both images)":
                images_for_2 = st.session_state.get('compare_images', [])
            else:
                images_for_2 = st.session_state.get('compare_images2', [])
            
            if images_for_2:
                img2_type = st.radio(
                    "Type:",
                    ["Individual Image", "Composite (Mean)", "Composite (Median)"],
                    key="img2_type"
                )
                
                if img2_type == "Individual Image":
                    selected2 = st.selectbox(
                        "Select image:",
                        images_for_2,
                        format_func=lambda x: f"{x['date']} (☁️ {x.get('cloud_cover', 'N/A'):.1f}%)" if isinstance(x.get('cloud_cover'), (int, float)) else f"{x['date']}",
                        key="sel2_cmp"
                    )
                    st.session_state.compare_img2 = selected2
                    st.session_state.compare_img2_type = "individual"
                else:
                    composite_type = "mean" if "Mean" in img2_type else "median"
                    st.session_state.compare_img2_type = composite_type
                    st.info(f"Will use {composite_type.upper()} of {len(images_for_2)} images")
            else:
                st.warning("⚠️ Search for images first")
    else:
        st.info("👆 Search for images first to enable selection")
    
    st.markdown("---")
    
    # SECTION 4: Index selection and comparison
    st.subheader("4️⃣ Calculate & Compare")
    index_options = ["NDVI", "SAVI", "EVI", "GNDVI"]
    selected_index = st.selectbox("Vegetation Index:", index_options, key="cmp_idx")
    
    if st.button("🔄 Generate Comparison", type="primary", use_container_width=True):
        if aoi and ('compare_img1_type' in st.session_state and 'compare_img2_type' in st.session_state):
            with st.spinner("Generating comparison maps..."):
                try:
                    col_m1, col_m2 = st.columns(2)
                    
                    # Get sensors for each image
                    sensor1 = st.session_state.get('compare_sensor1', 'Sentinel-2')
                    sensor2 = st.session_state.get('compare_sensor2', 'Sentinel-2')
                    
                    # IMAGE 1
                    with col_m1:
                        if st.session_state.get('compare_img1_type') == "individual" and 'compare_img1' in st.session_state:
                            img1 = get_single_image(sensor1, st.session_state.compare_img1['id'], aoi)
                            title1 = f"**{st.session_state.compare_img1['date']}**\n({sensor1})"
                        else:
                            # Get collection for sensor 1
                            if sensor_mode == "Same Sensor (both images)":
                                if sensor_cmp == "Sentinel-2":
                                    collection1 = get_sentinel2_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                elif sensor_cmp == "Landsat 8/9":
                                    collection1 = get_landsat89_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                elif sensor_cmp == "MODIS":
                                    collection1 = get_modis_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                else:
                                    collection1 = get_landsat57_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                            else:
                                if sensor1 == "Sentinel-2":
                                    collection1 = get_sentinel2_collection(str(start1), str(end1), aoi, cloud1)
                                elif sensor1 == "Landsat 8/9":
                                    collection1 = get_landsat89_collection(str(start1), str(end1), aoi, cloud1)
                                elif sensor1 == "MODIS":
                                    collection1 = get_modis_collection(str(start1), str(end1), aoi, cloud1)
                                else:
                                    collection1 = get_landsat57_collection(str(start1), str(end1), aoi, cloud1)
                            
                            if st.session_state.get('compare_img1_type') == "mean":
                                img1 = collection1.mean().clip(aoi)
                                title1 = f"**Mean Composite**\n({sensor1})"
                            else:
                                img1 = collection1.median().clip(aoi)
                                title1 = f"**Median Composite**\n({sensor1})"
                        
                        st.markdown(title1)
                        map_center = st.session_state.get('compare_aoi_center', [39.0, -98.0])
                        m1 = geemap.Map(center=map_center, zoom=11)
                        
                        if img1 is not None:
                            idx1 = calculate_index_for_image(img1, selected_index, sensor1)
                            vis = {'min': -0.2, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
                            m1.addLayer(idx1, vis, f'{selected_index} - Image 1')
                            m1.centerObject(aoi)
                            m1.to_streamlit(height=400)
                        else:
                            st.error("Failed to load Image 1")
                    
                    # IMAGE 2
                    with col_m2:
                        if st.session_state.get('compare_img2_type') == "individual" and 'compare_img2' in st.session_state:
                            img2 = get_single_image(sensor2, st.session_state.compare_img2['id'], aoi)
                            title2 = f"**{st.session_state.compare_img2['date']}**\n({sensor2})"
                        else:
                            # Get collection for sensor 2
                            if sensor_mode == "Same Sensor (both images)":
                                if sensor_cmp == "Sentinel-2":
                                    collection2 = get_sentinel2_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                elif sensor_cmp == "Landsat 8/9":
                                    collection2 = get_landsat89_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                elif sensor_cmp == "MODIS":
                                    collection2 = get_modis_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                                else:
                                    collection2 = get_landsat57_collection(str(start_date_cmp), str(end_date_cmp), aoi, cloud_cmp)
                            else:
                                if sensor2 == "Sentinel-2":
                                    collection2 = get_sentinel2_collection(str(start2), str(end2), aoi, cloud2)
                                elif sensor2 == "Landsat 8/9":
                                    collection2 = get_landsat89_collection(str(start2), str(end2), aoi, cloud2)
                                elif sensor2 == "MODIS":
                                    collection2 = get_modis_collection(str(start2), str(end2), aoi, cloud2)
                                else:
                                    collection2 = get_landsat57_collection(str(start2), str(end2), aoi, cloud2)
                            
                            if st.session_state.get('compare_img2_type') == "mean":
                                img2 = collection2.mean().clip(aoi)
                                title2 = f"**Mean Composite**\n({sensor2})"
                            else:
                                img2 = collection2.median().clip(aoi)
                                title2 = f"**Median Composite**\n({sensor2})"
                        
                        st.markdown(title2)
                        m2 = geemap.Map(center=map_center, zoom=11)
                        
                        if img2 is not None:
                            idx2 = calculate_index_for_image(img2, selected_index, sensor2)
                            m2.addLayer(idx2, vis, f'{selected_index} - Image 2')
                            m2.centerObject(aoi)
                            m2.to_streamlit(height=400)
                        else:
                            st.error("Failed to load Image 2")
                    
                    # Difference map
                    st.subheader("5️⃣ Difference Map (Image 2 - Image 1)")
                    m3 = geemap.Map(center=map_center, zoom=11)
                    diff = idx2.subtract(idx1).rename('Difference')
                    diff_vis = {'min': -0.3, 'max': 0.3, 'palette': ['red', 'white', 'green']}
                    m3.addLayer(diff, diff_vis, 'NDVI Change')
                    # Create an outline image from the AOI geometry
                    aoi_fc = ee.FeatureCollection([ee.Feature(aoi)])
                    aoi_outline = ee.Image().byte().paint(featureCollection=aoi_fc, color=1, width=2)
                    m3.addLayer(aoi_outline, {'palette': ['blue']}, 'AOI')
                    m3.centerObject(aoi)
                    m3.to_streamlit(height=400)
                    
                    st.info("🟢 Green = Vegetation increased | ⚪ White = No change | 🔴 Red = Vegetation decreased")
                    
                    # Download options
                    st.markdown("---")
                    st.subheader("💾 Download Options")
                    
                    col_d1, col_d2, col_d3 = st.columns(3)
                    
                    with col_d1:
                        st.markdown("**Image 1**")
                        if st.button("📥 PNG", key="dl1_png"):
                            try:
                                url = idx1.getThumbURL({
                                    'min': -0.2, 'max': 0.8,
                                    'palette': ['red', 'yellow', 'green'],
                                    'dimensions': 512,
                                    'format': 'png'
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        
                        if st.button("📥 GeoTIFF", key="dl1_tiff"):
                            try:
                                url = idx1.getDownloadURL({
                                    'scale': 30,
                                    'crs': 'EPSG:4326',
                                    'fileFormat': 'GeoTIFF',
                                    'region': aoi
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    
                    with col_d2:
                        st.markdown("**Image 2**")
                        if st.button("📥 PNG", key="dl2_png"):
                            try:
                                url = idx2.getThumbURL({
                                    'min': -0.2, 'max': 0.8,
                                    'palette': ['red', 'yellow', 'green'],
                                    'dimensions': 512,
                                    'format': 'png'
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        
                        if st.button("📥 GeoTIFF", key="dl2_tiff"):
                            try:
                                url = idx2.getDownloadURL({
                                    'scale': 30,
                                    'crs': 'EPSG:4326',
                                    'fileFormat': 'GeoTIFF',
                                    'region': aoi
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    
                    with col_d3:
                        st.markdown("**Difference Map**")
                        if st.button("📥 PNG", key="dl_diff_png"):
                            try:
                                url = diff.getThumbURL({
                                    'min': -0.3, 'max': 0.3,
                                    'palette': ['red', 'white', 'green'],
                                    'dimensions': 512,
                                    'format': 'png'
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        
                        if st.button("📥 GeoTIFF", key="dl_diff_tiff"):
                            try:
                                url = diff.getDownloadURL({
                                    'scale': 30,
                                    'crs': 'EPSG:4326',
                                    'fileFormat': 'GeoTIFF',
                                    'region': aoi
                                })
                                st.markdown(f"[🔗 Download]({url})", unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    
                    # Time Series Comparison
                    if sensor_mode == "Same Sensor (both images)":
                        st.markdown("---")
                        st.subheader("📈 Time Series Analysis")
                        
                        # Get all images for time series
                        images_for_ts = st.session_state.get('compare_images', [])
                        
                        if len(images_for_ts) > 2:
                            if st.button("📊 Generate Time Series Chart", key="ts_compare"):
                                with st.spinner("Calculating time series..."):
                                    try:
                                        dates = []
                                        values = []
                                        sensor_ts = st.session_state.get('compare_sensor1', sensor_cmp)
                                        
                                        for img_info in images_for_ts[:20]:  # Limit to 20
                                            img = get_single_image(sensor_ts, img_info['id'], aoi)
                                            if img is not None:
                                                idx_img = calculate_index_for_image(img, selected_index, sensor_ts)
                                                mean_val = idx_img.reduceRegion(
                                                    reducer=ee.Reducer.mean(),
                                                    geometry=aoi,
                                                    scale=30,
                                                    maxPixels=1e9
                                                ).getInfo()
                                                
                                                val = mean_val.get(selected_index, mean_val.get('NDVI'))
                                                if val is not None:
                                                    dates.append(img_info['date'])
                                                    values.append(val)
                                        
                                        if dates and values:
                                            import pandas as pd
                                            df_ts = pd.DataFrame({'Date': dates, selected_index: values})
                                            df_ts['Date'] = pd.to_datetime(df_ts['Date'])
                                            df_ts = df_ts.sort_values('Date')
                                            
                                            st.line_chart(df_ts.set_index('Date'))
                                            
                                            col_s1, col_s2, col_s3 = st.columns(3)
                                            col_s1.metric("Mean", f"{df_ts[selected_index].mean():.3f}")
                                            col_s2.metric("Min", f"{df_ts[selected_index].min():.3f}")
                                            col_s3.metric("Max", f"{df_ts[selected_index].max():.3f}")
                                            
                                            with st.expander("📋 View Data"):
                                                st.dataframe(df_ts, use_container_width=True)
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                        else:
                            st.info("Need at least 3 images for time series")
                    
                except Exception as e:
                    st.error(f"Error generating comparison: {str(e)}")
        else:
            st.warning("⚠️ Please search for images first and select what to compare!")

# =============================================================================
# PAGE 3: UPLOAD IMAGE
# =============================================================================
elif page == "📷 Upload Image":
    st.title("📷 Upload Image Analysis")
    st.markdown("Analyze your own drone or camera images using RGB-based vegetation indices")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Upload Settings")
        
        uploaded_file = st.file_uploader(
            "Choose an image:",
            type=['jpg', 'jpeg', 'png', 'tif', 'tiff']
        )
        
        rgb_indices = get_rgb_indices()
        selected_rgb_index = st.selectbox(
            "RGB Index:",
            list(rgb_indices.keys()),
            format_func=lambda x: f"{x} - {rgb_indices[x]}"
        )
        
        process_btn = st.button("🔬 Calculate", type="primary", use_container_width=True)
    
    with col2:
        st.subheader("Results")
        
        if uploaded_file:
            try:
                img_array = load_uploaded_image(uploaded_file)
                st.image(img_array, caption="Original Image", use_container_width=True)
                
                if process_btn:
                    try:
                        result = calculate_rgb_index(img_array, selected_rgb_index)
                        result_image = create_colormap_image(result, 'RdYlGn')
                        st.image(result_image, caption=f"{selected_rgb_index} Result", use_container_width=True)
                        
                        col_s1, col_s2, col_s3 = st.columns(3)
                        col_s1.metric("Min", f"{np.nanmin(result):.3f}")
                        col_s2.metric("Mean", f"{np.nanmean(result):.3f}")
                        col_s3.metric("Max", f"{np.nanmax(result):.3f}")
                    except Exception as e:
                        st.error(f"Error calculating index: {str(e)}")
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
                st.info("Please try a smaller image (< 10MB) or different format")
        else:
            st.info("👆 Upload an image to get started!")

# =============================================================================
# PAGE 4: HELP
# =============================================================================
elif page == "❓ Help":
    st.title("❓ Help")
    
    st.markdown("""
    ## Quick Start
    
    ### 1. Define Your Area
    - **Coordinates**: Enter lat/lon and buffer distance
    - **Upload File**: Upload GeoJSON or zipped Shapefile
    - **Draw on Map**: Use drawing tools directly
    
    ### 2. Search for Images
    - Select satellite and date range
    - Set maximum cloud cover
    - Click "Search Images" to see all available scenes
    
    ### 3. Select Specific Images
    - Browse the list of available images
    - See date and cloud cover for each
    - Click "Select" to choose an image
    
    ### 4. Compare Two Images
    - Go to "🔄 Compare Images" page
    - Search for images at two different dates
    - Generate side-by-side comparison
    - View the difference map (change detection)
    
    ## Vegetation Indices
    
    | Index | Best For |
    |-------|----------|
    | NDVI | General vegetation health |
    | SAVI | Sparse vegetation |
    | EVI | Dense forests |
    | GNDVI | Chlorophyll content |
    | NDMI | Water stress |
    | NDRE | Crop health (Sentinel-2) |
    """)

# =============================================================================
# PAGE 5: VISITOR STATS
# =============================================================================
elif page == "📊 Visitor Stats":
    st.title("📊 Visitor Analytics")
    st.markdown("Track how many people have used this app")
    
    try:
        stats = get_visit_stats()
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Visits", stats['total'])
        with col2:
            today = datetime.date.today().strftime('%Y-%m-%d')
            today_visits = stats['daily'].get(today, 0)
            st.metric("Today", today_visits)
        with col3:
            this_month = datetime.date.today().strftime('%Y-%m')
            month_visits = stats['monthly'].get(this_month, 0)
            st.metric("This Month", month_visits)
        
        st.markdown("---")
        
        # View selector
        view_type = st.radio("View by:", ["Daily", "Monthly", "Yearly"], horizontal=True)
        
        if view_type == "Daily":
            data = stats['daily']
            title = "Daily Visits (Last 30 days)"
        elif view_type == "Monthly":
            data = stats['monthly']
            title = "Monthly Visits"
        else:
            data = stats['yearly']
            title = "Yearly Visits"
        
        if data:
            # Convert to DataFrame for chart
            df = pd.DataFrame(list(data.items()), columns=['Date', 'Visits'])
            df = df.sort_values('Date')
            
            # Show chart
            st.subheader(title)
            st.bar_chart(df.set_index('Date'))
            
            # Show data table
            with st.expander("📋 View Data Table"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No visit data available yet. Come back later!")
    except Exception as e:
        st.error(f"Error loading analytics: {str(e)}")
        st.info("Analytics data may be unavailable")

# =============================================================================
# FOOTER
# =============================================================================
st.sidebar.markdown("---")
st.sidebar.markdown("**AgriVision Pro v2.0**")
st.sidebar.markdown("🛰️ Satellite | 🚁 Drone | 📊 Analysis")
