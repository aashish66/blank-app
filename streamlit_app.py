"""
AgriVision Pro V3 - Main Application
=====================================
Satellite Vegetation Analysis Platform

A comprehensive platform for analyzing vegetation health using
satellite imagery from Google Earth Engine.

Features:
- Satellite Analysis (NDVI, EVI, SAVI, etc.)
- Compare Images (temporal comparison)
- Time Series Analysis
- Image Download/Export
"""

import streamlit as st

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="AgriVision Pro - Vegetation Analysis",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': 'https://github.com/aashish66/AgriVision_Pro',
        'Report a bug': 'https://github.com/aashish66/AgriVision_Pro/issues',
        'About': '# AgriVision Pro V3\nSatellite vegetation analysis platform!'
    }
)

# Import libraries
import ee
from datetime import datetime, timedelta
import json

# Import app components
from app_components.auth_component import AuthComponent, ensure_ee_initialized
from app_components.aoi_component import AOIComponent
from app_components.time_series import TimeSeriesComponent
from app_components.visitor_stats import VisitorStatsComponent
from app_components.theme_utils import apply_theme_css

# Import core modules
from core.satellite_data import (
    get_sentinel2_collection, get_landsat89_collection,
    get_landsat57_collection, get_modis_collection,
    get_scale_for_sensor, get_adaptive_scale_for_area,
    get_image_list, get_single_image
)
from core.vegetation_indices import (
    calculate_index, get_available_indices, get_index_vis_params
)
from core.map_utils import display_ee_map
from core.download_utils import get_download_url, create_download_button

# Apply theme CSS
apply_theme_css()


# =============================================================================
# Session State Initialization
# =============================================================================

if 'app_mode' not in st.session_state:
    st.session_state.app_mode = None  # None = landing, 'satellite', 'compare', 'help'
if 'gee_authenticated' not in st.session_state:
    st.session_state.gee_authenticated = False


# =============================================================================
# Landing Page
# =============================================================================

def render_landing_page():
    """Render the landing page with tool selection."""
    
    # Hero section
    st.markdown("""
    <div class="landing-hero">
        <div style="font-size: 4rem; margin-bottom: 1rem;">🌾</div>
        <h1 class="landing-title">AgriVision Pro</h1>
        <p class="landing-subtitle">
            Advanced Satellite Vegetation Analysis Platform<br>
            Powered by Google Earth Engine
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Features
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-item">
            <div class="feature-icon">🛰️</div>
            <strong>4 Satellites</strong><br>
            <small>Sentinel-2, Landsat 8/9, Landsat 5/7, MODIS</small>
        </div>
        <div class="feature-item">
            <div class="feature-icon">📊</div>
            <strong>7+ Indices</strong><br>
            <small>NDVI, EVI, SAVI, NDWI, NDMI, GNDVI, NBR</small>
        </div>
        <div class="feature-item">
            <div class="feature-icon">🗺️</div>
            <strong>Interactive Maps</strong><br>
            <small>Real-time visualization</small>
        </div>
        <div class="feature-item">
            <div class="feature-icon">📈</div>
            <strong>Time Series</strong><br>
            <small>Trend analysis over time</small>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🧰 Select a Tool")
    
    # Tool cards - 2 rows
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="tool-card">
            <span class="tool-icon">🛰️</span>
            <div class="tool-title">Satellite Analysis</div>
            <div class="tool-description">
                Analyze vegetation indices from satellite imagery.
                Generate maps and time series for your area of interest.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🛰️ Open Satellite Analysis", type="primary", use_container_width=True, key="btn_satellite"):
            st.session_state.app_mode = 'satellite'
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="tool-card">
            <span class="tool-icon">🔄</span>
            <div class="tool-title">Compare Images</div>
            <div class="tool-description">
                Compare vegetation changes between two dates or sensors.
                Visualize differences and track changes over time.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 Open Compare Images", type="primary", use_container_width=True, key="btn_compare"):
            st.session_state.app_mode = 'compare'
            st.rerun()
    
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("""
        <div class="tool-card">
            <span class="tool-icon">🚁</span>
            <div class="tool-title">Drone Image Analysis</div>
            <div class="tool-description">
                Upload drone/camera images for vegetation analysis.
                Supports RGB and multispectral imagery.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚁 Open Drone Analysis", type="primary", use_container_width=True, key="btn_drone"):
            st.session_state.app_mode = 'drone'
            st.rerun()
    
    with col4:
        st.markdown("""
        <div class="tool-card">
            <span class="tool-icon">❓</span>
            <div class="tool-title">Help & Info</div>
            <div class="tool-description">
                Learn about vegetation indices, data sources, 
                and how to use the platform effectively.
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("❓ Open Help", type="primary", use_container_width=True, key="btn_help"):
            st.session_state.app_mode = 'help'
            st.rerun()
    
    # Visitor stats footer
    visitor_stats = VisitorStatsComponent()
    visitor_stats.render_footer()


# =============================================================================
# Authentication Page
# =============================================================================

def render_auth_page():
    """Render authentication page."""
    st.markdown("""
    <div class="landing-hero">
        <div style="font-size: 3rem; margin-bottom: 1rem;">🔐</div>
        <h1 class="landing-title">Authentication Required</h1>
        <p class="landing-subtitle">
            Connect to Google Earth Engine to access satellite data
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    auth_component = AuthComponent()
    if auth_component.render():
        st.success("🎉 Authentication successful!")
        st.info("🔄 Loading platform...")
        import time
        time.sleep(1)
        st.rerun()


# =============================================================================
# Satellite Analysis Page
# =============================================================================

def render_satellite_analysis():
    """Render satellite analysis page."""
    
    # Back button
    if st.button("← Back to Home", key="back_satellite"):
        st.session_state.app_mode = None
        st.rerun()
    
    st.title("🛰️ Satellite Analysis")
    st.markdown("Analyze vegetation indices from satellite imagery")
    
    # Check authentication
    if not ensure_ee_initialized():
        st.warning("⚠️ Please authenticate with Google Earth Engine")
        render_auth_page()
        return
    
    # Step 1: AOI Selection
    st.markdown('<div class="step-header"><strong>Step 1:</strong> Select Area of Interest</div>', unsafe_allow_html=True)
    aoi_component = AOIComponent(session_prefix="sat_")
    aoi = aoi_component.render()
    
    if aoi is None:
        st.info("👆 Please select and confirm an area of interest to continue")
        return
    
    # Step 2: Parameters
    st.markdown('<div class="step-header"><strong>Step 2:</strong> Configure Analysis</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sensor = st.selectbox(
            "🛰️ Satellite Sensor:",
            ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"],
            key="sat_sensor"
        )
    
    with col2:
        indices = list(get_available_indices().keys())
        if sensor == "MODIS":
            indices = ["NDVI", "EVI"]  # MODIS has built-in indices
        selected_index = st.selectbox("📊 Vegetation Index:", indices, key="sat_index")
    
    with col3:
        max_cloud = st.slider("☁️ Max Cloud Cover:", 0, 100, 30, key="sat_cloud")
    
    col1, col2 = st.columns(2)
    
    with col1:
        default_start = datetime.now() - timedelta(days=90)
        start_date = st.date_input("📅 Start Date:", default_start, key="sat_start")
    
    with col2:
        end_date = st.date_input("📅 End Date:", datetime.now(), key="sat_end")
    
    # Resolution selection
    area_km2 = st.session_state.get('sat_aoi_area_km2', 100)
    auto_scale = get_adaptive_scale_for_area(area_km2, sensor)
    
    resolution_mode = st.radio(
        "🎯 Resolution Mode:",
        ["Auto (recommended)", "Manual"],
        horizontal=True,
        key="sat_res_mode"
    )
    
    if resolution_mode == "Manual":
        user_scale = st.slider(
            "Resolution (meters):",
            10, 5000, auto_scale,
            help="Higher values = faster processing, lower detail",
            key="sat_scale"
        )
        if area_km2 > 1000 and user_scale < 100:
            st.warning("⚠️ Fine resolution on large areas may be slow or fail. Consider using auto mode.")
    else:
        user_scale = auto_scale
        st.info(f"📍 Auto-selected resolution: {user_scale}m (based on {area_km2:.1f} km² area)")
    
    # Composite type
    composite_type = st.radio(
        "🖼️ Image Type:",
        ["Median Composite", "Mean Composite", "Single Date"],
        horizontal=True,
        key="sat_composite"
    )
    
    # Generate button
    if st.button("🗺️ Generate Vegetation Map", type="primary", key="sat_generate"):
        _generate_vegetation_map(
            aoi, sensor, selected_index, str(start_date), str(end_date),
            max_cloud, user_scale, composite_type
        )
    
    # Time Series Section
    st.markdown("---")
    st.markdown('<div class="step-header"><strong>Step 3:</strong> Time Series Analysis (Optional)</div>', unsafe_allow_html=True)
    
    if st.checkbox("📈 Enable Time Series Analysis", key="sat_ts_enable"):
        with st.spinner("Loading available images..."):
            images = get_image_list(sensor, str(start_date), str(end_date), aoi, max_cloud)
        
        if images:
            ts_component = TimeSeriesComponent(session_prefix="sat_")
            ts_component.render(aoi, images, sensor, selected_index)
        else:
            st.warning("No images found for time series analysis")


def _generate_vegetation_map(aoi, sensor, index_name, start_date, end_date, 
                              max_cloud, scale, composite_type):
    """Generate and display vegetation map."""
    
    with st.spinner(f"Generating {index_name} map..."):
        try:
            # Get collection
            if sensor == "Sentinel-2":
                collection = get_sentinel2_collection(start_date, end_date, aoi, max_cloud)
            elif sensor == "Landsat 8/9":
                collection = get_landsat89_collection(start_date, end_date, aoi, max_cloud)
            elif sensor == "Landsat 5/7":
                collection = get_landsat57_collection(start_date, end_date, aoi, max_cloud)
            else:
                collection = get_modis_collection(start_date, end_date, aoi, max_cloud)
            
            # Check collection size
            count = collection.size().getInfo()
            if count == 0:
                st.error("❌ No images found. Try a different date range or cloud threshold.")
                return
            
            st.info(f"📷 Found {count} images")
            
            # Create composite
            if composite_type == "Median Composite":
                image = collection.median().clip(aoi)
                title = f"{index_name} (Median Composite)"
            elif composite_type == "Mean Composite":
                image = collection.mean().clip(aoi)
                title = f"{index_name} (Mean Composite)"
            else:
                image = collection.first().clip(aoi)
                title = f"{index_name} (Single Image)"
            
            # Calculate index
            index_image = calculate_index(image, index_name, sensor)
            band_name = index_image.bandNames().getInfo()[0]
            
            # Get default vis params
            default_vmin, default_vmax, palette = get_index_vis_params(index_name)
            vmin, vmax = default_vmin, default_vmax
            
            # Try to calculate stats (silent fallback)
            try:
                stats = index_image.reduceRegion(
                    reducer=ee.Reducer.percentile([5, 95]),
                    geometry=aoi,
                    scale=scale,
                    maxPixels=1e9,
                    bestEffort=True
                ).getInfo()
                
                vmin_raw = stats.get(f'{band_name}_p5')
                vmax_raw = stats.get(f'{band_name}_p95')
                
                if vmin_raw is not None and vmax_raw is not None:
                    vmin = vmin_raw
                    vmax = vmax_raw
            except Exception:
                pass  # Silent fallback to defaults
            
            vis_params = {
                'bands': [band_name],
                'min': vmin,
                'max': vmax,
                'palette': palette
            }
            
            # Get center
            try:
                centroid = aoi.centroid().getInfo()['coordinates']
                center = [centroid[1], centroid[0]]
            except Exception:
                center = [39.0, -98.0]
            
            # Display map
            display_ee_map(
                center=center,
                zoom=12,
                ee_image=index_image,
                vis_params=vis_params,
                layer_name=title,
                aoi=aoi,
                height=500
            )
            
            st.success(f"✅ {index_name} map generated! (Resolution: {scale}m)")
            st.markdown(f"**Legend:** 🔴 Low ({vmin:.2f}) → 🟡 Moderate → 🟢 High ({vmax:.2f})")
            
            # Download option
            with st.expander("📥 Download Options"):
                if st.button("Generate Download URL", key="sat_download"):
                    url = get_download_url(index_image, aoi, scale, f"{index_name}_map")
                    if url:
                        st.markdown(f"[📥 Download GeoTIFF]({url})")
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# =============================================================================
# Compare Images Page
# =============================================================================

def render_compare_images():
    """Render compare images page."""
    
    # Back button
    if st.button("← Back to Home", key="back_compare"):
        st.session_state.app_mode = None
        st.rerun()
    
    st.title("🔄 Compare Images")
    st.markdown("Compare vegetation changes between two dates or sensors")
    
    # Check authentication
    if not ensure_ee_initialized():
        st.warning("⚠️ Please authenticate with Google Earth Engine")
        render_auth_page()
        return
    
    # Step 1: AOI Selection
    st.markdown('<div class="step-header"><strong>Step 1:</strong> Select Area of Interest</div>', unsafe_allow_html=True)
    aoi_component = AOIComponent(session_prefix="cmp_")
    aoi = aoi_component.render()
    
    if aoi is None:
        st.info("👆 Please select and confirm an area of interest to continue")
        return
    
    # Step 2: Comparison Mode
    st.markdown('<div class="step-header"><strong>Step 2:</strong> Configure Comparison</div>', unsafe_allow_html=True)
    
    mode = st.radio(
        "Compare:",
        ["Two Dates (Same Sensor)", "Two Sensors (Same Dates)"],
        horizontal=True,
        key="cmp_mode"
    )
    
    sensors = ["Sentinel-2", "Landsat 8/9", "Landsat 5/7", "MODIS"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📅 Image 1**")
        sensor1 = st.selectbox("Sensor:", sensors, key="cmp_sensor1")
        date1_start = st.date_input("Start Date:", datetime.now() - timedelta(days=180), key="cmp_date1_start")
        date1_end = st.date_input("End Date:", datetime.now() - timedelta(days=90), key="cmp_date1_end")
    
    with col2:
        st.markdown("**📅 Image 2**")
        if mode == "Two Dates (Same Sensor)":
            sensor2 = sensor1
            st.info(f"Using: {sensor1}")
        else:
            sensor2 = st.selectbox("Sensor:", sensors, key="cmp_sensor2")
        date2_start = st.date_input("Start Date:", datetime.now() - timedelta(days=90), key="cmp_date2_start")
        date2_end = st.date_input("End Date:", datetime.now(), key="cmp_date2_end")
    
    # Index selection
    st.markdown('<div class="step-header"><strong>Step 3:</strong> Vegetation Index</div>', unsafe_allow_html=True)
    indices = list(get_available_indices().keys())
    selected_index = st.selectbox("Select Index:", indices, key="cmp_index")
    
    # Generate comparison
    if st.button("🗺️ Generate Comparison", type="primary", key="cmp_generate"):
        _generate_comparison(
            aoi, sensor1, sensor2, selected_index,
            str(date1_start), str(date1_end),
            str(date2_start), str(date2_end)
        )


def _generate_comparison(aoi, sensor1, sensor2, index_name, 
                         d1_start, d1_end, d2_start, d2_end):
    """Generate comparison maps."""
    
    with st.spinner("Generating comparison..."):
        try:
            # Get collections
            if sensor1 == "Sentinel-2":
                col1 = get_sentinel2_collection(d1_start, d1_end, aoi, 30)
            elif sensor1 == "Landsat 8/9":
                col1 = get_landsat89_collection(d1_start, d1_end, aoi, 30)
            elif sensor1 == "Landsat 5/7":
                col1 = get_landsat57_collection(d1_start, d1_end, aoi, 30)
            else:
                col1 = get_modis_collection(d1_start, d1_end, aoi)
            
            if sensor2 == "Sentinel-2":
                col2 = get_sentinel2_collection(d2_start, d2_end, aoi, 30)
            elif sensor2 == "Landsat 8/9":
                col2 = get_landsat89_collection(d2_start, d2_end, aoi, 30)
            elif sensor2 == "Landsat 5/7":
                col2 = get_landsat57_collection(d2_start, d2_end, aoi, 30)
            else:
                col2 = get_modis_collection(d2_start, d2_end, aoi)
            
            # Check sizes
            if col1.size().getInfo() == 0 or col2.size().getInfo() == 0:
                st.error("❌ No images found for one or both date ranges.")
                return
            
            # Create composites
            img1 = col1.median().clip(aoi)
            img2 = col2.median().clip(aoi)
            
            # Calculate indices
            idx1 = calculate_index(img1, index_name, sensor1)
            idx2 = calculate_index(img2, index_name, sensor2)
            
            # Get center
            try:
                centroid = aoi.centroid().getInfo()['coordinates']
                center = [centroid[1], centroid[0]]
            except Exception:
                center = [39.0, -98.0]
            
            # Vis params
            vmin, vmax, palette = get_index_vis_params(index_name)
            vis_params = {'bands': [index_name], 'min': vmin, 'max': vmax, 'palette': palette}
            
            st.markdown('<div class="step-header"><strong>Results</strong></div>', unsafe_allow_html=True)
            
            # Side by side maps
            col1_ui, col2_ui = st.columns(2)
            
            with col1_ui:
                st.markdown(f"**Image 1** ({d1_start} to {d1_end})")
                display_ee_map(
                    center=center, zoom=11,
                    ee_image=idx1, vis_params=vis_params,
                    layer_name=f"{index_name} - Image 1",
                    aoi=aoi, height=350,
                    key="cmp_map1"
                )
            
            with col2_ui:
                st.markdown(f"**Image 2** ({d2_start} to {d2_end})")
                display_ee_map(
                    center=center, zoom=11,
                    ee_image=idx2, vis_params=vis_params,
                    layer_name=f"{index_name} - Image 2",
                    aoi=aoi, height=350,
                    key="cmp_map2"
                )
            
            # Difference map
            st.markdown("### 📊 Difference Map (Image 2 - Image 1)")
            
            diff = idx2.subtract(idx1).rename('Difference')
            diff_vis = {
                'bands': ['Difference'],
                'min': -0.3, 'max': 0.3,
                'palette': ['d73027', 'f46d43', 'fdae61', 'ffffbf', 'a6d96a', '66bd63', '1a9850']
            }
            
            display_ee_map(
                center=center, zoom=11,
                ee_image=diff, vis_params=diff_vis,
                layer_name="Change",
                aoi=aoi, height=400,
                key="cmp_diff"
            )
            
            st.markdown("""
            **Legend:**
            - 🟢 **Green**: Vegetation increased
            - ⚪ **White/Yellow**: No significant change  
            - 🔴 **Red**: Vegetation decreased
            """)
            
            st.success("✅ Comparison complete!")
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# =============================================================================
# Drone Image Analysis Page
# =============================================================================

# RGB-based vegetation indices (no NIR needed)
RGB_INDICES = {
    "ExG": "Excess Green - highlights vegetation",
    "ExR": "Excess Red - highlights stressed vegetation",
    "ExGR": "Excess Green minus Red - vegetation vs soil",
    "GRVI": "Green-Red Vegetation Index",
    "MGRVI": "Modified GRVI - enhanced contrast",
    "RGBVI": "RGB Vegetation Index - normalized"
}

# Multispectral indices (requires NIR band)
MULTISPECTRAL_INDICES = {
    "NDVI": "Normalized Difference Vegetation Index",
    "EVI": "Enhanced Vegetation Index",
    "SAVI": "Soil Adjusted Vegetation Index",
    "NDWI": "Normalized Difference Water Index",
    "GNDVI": "Green NDVI",
}


def calculate_rgb_index(img_array, index_name):
    """Calculate RGB-based vegetation index."""
    import numpy as np
    
    r = img_array[:, :, 0].astype(np.float32) / 255.0
    g = img_array[:, :, 1].astype(np.float32) / 255.0
    b = img_array[:, :, 2].astype(np.float32) / 255.0
    
    eps = 1e-7
    
    if index_name == "ExG":
        return 2 * g - r - b
    elif index_name == "ExR":
        return 1.4 * r - g
    elif index_name == "ExGR":
        exg = 2 * g - r - b
        exr = 1.4 * r - g
        return exg - exr
    elif index_name == "GRVI":
        return (g - r) / (g + r + eps)
    elif index_name == "MGRVI":
        g2, r2 = g ** 2, r ** 2
        return (g2 - r2) / (g2 + r2 + eps)
    elif index_name == "RGBVI":
        g2, br = g ** 2, b * r
        return (g2 - br) / (g2 + br + eps)
    else:
        return 2 * g - r - b


def calculate_multispectral_index(img_array, index_name, band_mapping):
    """Calculate multispectral vegetation index."""
    import numpy as np
    
    eps = 1e-7
    
    # Extract bands based on mapping
    r = img_array[:, :, band_mapping['red']].astype(np.float32)
    g = img_array[:, :, band_mapping['green']].astype(np.float32)
    nir = img_array[:, :, band_mapping['nir']].astype(np.float32)
    
    # Normalize to 0-1 if 8-bit
    if r.max() > 1:
        r, g, nir = r / 255.0, g / 255.0, nir / 255.0
    
    if index_name == "NDVI":
        return (nir - r) / (nir + r + eps)
    elif index_name == "EVI":
        b = img_array[:, :, band_mapping.get('blue', 2)].astype(np.float32)
        if b.max() > 1:
            b = b / 255.0
        return 2.5 * (nir - r) / (nir + 6 * r - 7.5 * b + 1 + eps)
    elif index_name == "SAVI":
        L = 0.5
        return (1 + L) * (nir - r) / (nir + r + L + eps)
    elif index_name == "NDWI":
        return (g - nir) / (g + nir + eps)
    elif index_name == "GNDVI":
        return (nir - g) / (nir + g + eps)
    else:
        return (nir - r) / (nir + r + eps)


def create_colormap_image(data, colormap='RdYlGn'):
    """Apply colormap to data array."""
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    
    vmin, vmax = np.nanpercentile(data[~np.isnan(data)], [2, 98])
    normalized = np.clip((data - vmin) / (vmax - vmin + 1e-7), 0, 1)
    
    cmap = cm.get_cmap(colormap)
    colored = cmap(normalized)
    
    return (colored[:, :, :3] * 255).astype(np.uint8)


def render_drone_analysis():
    """Render drone image analysis page."""
    import numpy as np
    from PIL import Image
    import io
    
    # Back button
    if st.button("← Back to Home", key="back_drone"):
        st.session_state.app_mode = None
        st.rerun()
    
    st.title("🚁 Drone Image Analysis")
    st.markdown("Analyze your own drone or camera images using vegetation indices")
    st.caption("*This page does NOT require Google Earth Engine authentication*")
    
    # Image type selection
    image_type = st.radio(
        "Image Type:",
        ["📷 RGB Image", "🔬 Multispectral Image"],
        horizontal=True,
        key="drone_image_type"
    )
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Upload Settings")
        
        uploaded_file = st.file_uploader(
            "Choose an image:",
            type=['jpg', 'jpeg', 'png', 'tif', 'tiff'],
            key="drone_upload_file"
        )
        
        if image_type == "📷 RGB Image":
            selected_index = st.selectbox(
                "RGB Index:",
                list(RGB_INDICES.keys()),
                format_func=lambda x: f"{x} - {RGB_INDICES[x]}",
                key="drone_rgb_index"
            )
            st.info(f"**{selected_index}**: {RGB_INDICES[selected_index]}")
        else:
            selected_index = st.selectbox(
                "Multispectral Index:",
                list(MULTISPECTRAL_INDICES.keys()),
                format_func=lambda x: f"{x} - {MULTISPECTRAL_INDICES[x]}",
                key="drone_ms_index"
            )
            st.info(f"**{selected_index}**: {MULTISPECTRAL_INDICES[selected_index]}")
            
            # Band mapping for multispectral
            st.markdown("**Band Mapping:**")
            st.caption("Specify which band number contains each channel (0-indexed)")
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                red_band = st.number_input("Red", 0, 10, 0, key="drone_red_band")
            with c2:
                green_band = st.number_input("Green", 0, 10, 1, key="drone_green_band")
            with c3:
                blue_band = st.number_input("Blue", 0, 10, 2, key="drone_blue_band")
            with c4:
                nir_band = st.number_input("NIR", 0, 10, 3, key="drone_nir_band")
        
        process_btn = st.button("🔬 Calculate Index", type="primary", use_container_width=True, key="drone_process")
    
    with col2:
        st.subheader("Results")
        
        if uploaded_file:
            try:
                img = Image.open(uploaded_file)
                if img.mode not in ['RGB', 'RGBA']:
                    if img.mode == 'L':
                        img = img.convert('RGB')
                
                img_array = np.array(img)
                
                # Show original
                st.image(img_array if img_array.shape[-1] <= 4 else img_array[:,:,:3], 
                        caption="Original Image", use_container_width=True)
                
                if process_btn:
                    with st.spinner("Calculating index..."):
                        try:
                            if image_type == "📷 RGB Image":
                                # RGB processing
                                if len(img_array.shape) == 2:
                                    st.error("RGB processing requires a color image")
                                    return
                                if img_array.shape[-1] == 4:
                                    img_array = img_array[:, :, :3]
                                
                                result = calculate_rgb_index(img_array, selected_index)
                            else:
                                # Multispectral processing
                                band_mapping = {
                                    'red': red_band,
                                    'green': green_band,
                                    'blue': blue_band,
                                    'nir': nir_band
                                }
                                
                                if img_array.shape[-1] <= max(band_mapping.values()):
                                    st.error(f"Image has {img_array.shape[-1]} bands, but you specified band {max(band_mapping.values())}")
                                    return
                                
                                result = calculate_multispectral_index(img_array, selected_index, band_mapping)
                            
                            # Create colormap visualization
                            result_image = create_colormap_image(result, 'RdYlGn')
                            
                            st.image(result_image, caption=f"{selected_index} Result", use_container_width=True)
                            
                            # Statistics
                            col_s1, col_s2, col_s3 = st.columns(3)
                            col_s1.metric("Min", f"{np.nanmin(result):.3f}")
                            col_s2.metric("Mean", f"{np.nanmean(result):.3f}")
                            col_s3.metric("Max", f"{np.nanmax(result):.3f}")
                            
                            # Download
                            st.markdown("---")
                            st.markdown("**💾 Download:**")
                            
                            result_pil = Image.fromarray(result_image)
                            buf = io.BytesIO()
                            result_pil.save(buf, format='PNG')
                            
                            st.download_button(
                                label="📥 Download Result PNG",
                                data=buf.getvalue(),
                                file_name=f"{selected_index}_result.png",
                                mime="image/png",
                                key="drone_download"
                            )
                            
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")
                st.info("Please try a smaller image (<10MB) or different format")
        else:
            st.info("👆 Upload an image to get started!")
            
            st.markdown("""
            **Supported formats:**
            - JPEG/JPG, PNG
            - TIFF/TIF (drone imagery, including multispectral)
            
            **For RGB images:**
            - Standard camera or drone photos
            - Works with ExG, GRVI, and other RGB indices
            
            **For Multispectral images:**
            - Multi-band TIFFs from drone sensors
            - Specify band mapping for R, G, B, NIR
            - Calculate NDVI, EVI, SAVI, etc.
            """)


# =============================================================================
# Help Page
# =============================================================================

def render_help_page():
    """Render help page."""
    
    # Back button
    if st.button("← Back to Home", key="back_help"):
        st.session_state.app_mode = None
        st.rerun()
    
    st.title("❓ Help & Information")
    
    st.markdown("""
    ## 🌾 About AgriVision Pro
    
    AgriVision Pro is a satellite vegetation analysis platform powered by Google Earth Engine.
    It allows you to analyze vegetation health using various satellite sensors and indices.
    
    ---
    
    ## 📊 Vegetation Indices
    
    | Index | Full Name | Best For |
    |-------|-----------|----------|
    | **NDVI** | Normalized Difference Vegetation Index | General vegetation health |
    | **EVI** | Enhanced Vegetation Index | Dense vegetation, reduces atmospheric effects |
    | **SAVI** | Soil Adjusted Vegetation Index | Areas with visible soil |
    | **NDWI** | Normalized Difference Water Index | Water content in vegetation |
    | **NDMI** | Normalized Difference Moisture Index | Vegetation moisture stress |
    | **GNDVI** | Green NDVI | Chlorophyll estimation |
    | **NBR** | Normalized Burn Ratio | Fire/burn damage assessment |
    
    ---
    
    ## 🛰️ Satellite Sensors
    
    | Sensor | Resolution | Coverage | Best For |
    |--------|------------|----------|----------|
    | **Sentinel-2** | 10-20m | 2015-present | High detail analysis |
    | **Landsat 8/9** | 30m | 2013-present | Medium resolution |
    | **Landsat 5/7** | 30m | 1984-2012 | Historical analysis |
    | **MODIS** | 250m | 2000-present | Large-scale monitoring |
    
    ---
    
    ## 🚁 Drone Image Analysis
    
    **RGB Indices (no NIR needed):**
    | Index | Description |
    |-------|-------------|
    | **ExG** | Excess Green - highlights vegetation |
    | **GRVI** | Green-Red Vegetation Index |
    | **RGBVI** | RGB Vegetation Index |
    
    **Multispectral Indices (requires NIR):**
    - Upload multi-band TIFF with NIR band
    - Specify band mapping (R, G, B, NIR positions)
    - Calculate NDVI, EVI, SAVI, etc.
    
    ---
    
    ## 🔐 Authentication
    
    To use AgriVision Pro satellite features:
    
    1. **Get credentials**: Run `earthengine authenticate` in terminal
    2. **Find credentials**: `~/.config/earthengine/credentials`
    3. **Upload**: Upload the credentials file when prompted
    
    *Note: Drone Image Analysis does NOT require authentication*
    """)


# =============================================================================
# Main App Router
# =============================================================================

def main():
    """Main application entry point."""
    
    # Check authentication first
    if not st.session_state.get('gee_authenticated', False):
        # Try auto-auth from secrets
        try:
            if hasattr(st, 'secrets') and 'gee_service_account' in st.secrets:
                if ensure_ee_initialized():
                    st.session_state.gee_authenticated = True
        except Exception:
            pass
    
    # Route to appropriate page
    app_mode = st.session_state.get('app_mode')
    
    if app_mode is None:
        # Check if authenticated, show auth page if not
        if not st.session_state.get('gee_authenticated', False):
            render_auth_page()
        else:
            render_landing_page()
    
    elif app_mode == 'satellite':
        render_satellite_analysis()
    
    elif app_mode == 'compare':
        render_compare_images()
    
    elif app_mode == 'drone':
        render_drone_analysis()
    
    elif app_mode == 'help':
        render_help_page()
    
    else:
        render_landing_page()


# Run the app
if __name__ == "__main__":
    main()

