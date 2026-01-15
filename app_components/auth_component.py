"""
AgriVision Pro V3 - Authentication Component
=============================================
Handles GEE authentication with credentials upload.
"""

import streamlit as st
import ee
import json
from pathlib import Path


class AuthComponent:
    """Authentication component for Google Earth Engine."""
    
    def __init__(self):
        """Initialize auth component."""
        self.initialized = False
    
    def render(self) -> bool:
        """
        Render authentication UI.
        
        Returns:
            True if authentication is successful
        """
        st.markdown("### 🔐 Google Earth Engine Authentication")
        
        # Check if already authenticated
        if self._check_existing_auth():
            return True
        
        # Authentication methods
        st.info("""
        📁 **Credentials file location:** `~/.config/earthengine/credentials`
        
        To get credentials, run in terminal: `earthengine authenticate`
        """)
        
        auth_method = st.radio(
            "Choose authentication method:",
            ["📁 Upload Credentials File", "🔑 Paste Credentials JSON"],
            horizontal=True,
            key="auth_method"
        )
        
        if auth_method == "📁 Upload Credentials File":
            return self._render_file_upload()
        else:
            return self._render_json_paste()
    
    def _check_existing_auth(self) -> bool:
        """Check if EE is already initialized."""
        try:
            # Try Streamlit secrets first
            if hasattr(st, 'secrets') and 'gee_service_account' in st.secrets:
                creds_data = dict(st.secrets['gee_service_account'])
                return self._initialize_with_service_account(creds_data)
            
            # Check session state
            if st.session_state.get('gee_authenticated', False):
                ee.Number(1).getInfo()
                return True
        except Exception:
            pass
        return False
    
    def _render_file_upload(self) -> bool:
        """Render file upload authentication."""
        uploaded_file = st.file_uploader(
            "Upload your credentials file:",
            type=None,  # Accept all file types
            help="Usually found at ~/.config/earthengine/credentials (no extension)",
            key="creds_file_upload"
        )
        
        project_id = st.text_input(
            "GEE Project ID (optional but recommended):",
            placeholder="ee-your-project-id",
            key="project_id_input"
        )
        
        if uploaded_file is not None:
            try:
                creds_content = uploaded_file.read().decode('utf-8')
                creds_data = json.loads(creds_content)
                
                if st.button("🚀 Authenticate", type="primary", key="auth_btn"):
                    success, message = self._authenticate(creds_data, project_id)
                    if success:
                        st.success("✅ " + message)
                        st.session_state.gee_authenticated = True
                        st.session_state.gee_credentials = creds_data
                        st.session_state.gee_project_id = project_id
                        return True
                    else:
                        st.error("❌ " + message)
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON file")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        
        return False
    
    def _render_json_paste(self) -> bool:
        """Render JSON paste authentication."""
        creds_json = st.text_area(
            "Paste your credentials JSON:",
            height=200,
            placeholder='{"refresh_token": "...", ...}',
            key="creds_json_input"
        )
        
        project_id = st.text_input(
            "GEE Project ID (optional but recommended):",
            placeholder="ee-your-project-id",
            key="project_id_paste"
        )
        
        if creds_json and st.button("🚀 Authenticate", type="primary", key="auth_paste_btn"):
            try:
                creds_data = json.loads(creds_json)
                success, message = self._authenticate(creds_data, project_id)
                if success:
                    st.success("✅ " + message)
                    st.session_state.gee_authenticated = True
                    st.session_state.gee_credentials = creds_data
                    st.session_state.gee_project_id = project_id
                    return True
                else:
                    st.error("❌ " + message)
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON format")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        
        return False
    
    def _authenticate(self, creds_data: dict, project_id: str = None) -> tuple:
        """
        Authenticate with Earth Engine.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Service account authentication
            if 'private_key' in creds_data and 'client_email' in creds_data:
                return self._initialize_with_service_account(creds_data, project_id)
            
            # OAuth refresh token authentication
            elif 'refresh_token' in creds_data:
                return self._initialize_with_refresh_token(creds_data, project_id)
            
            else:
                return False, "Unrecognized credentials format"
            
        except Exception as e:
            return False, f"Authentication failed: {str(e)}"
    
    def _initialize_with_service_account(self, creds_data: dict, project_id: str = None) -> tuple:
        """Initialize with service account credentials."""
        try:
            import google.oauth2.service_account
            
            credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            
            proj = project_id or creds_data.get('project_id')
            if proj:
                ee.Initialize(credentials, project=proj, opt_url='https://earthengine-highvolume.googleapis.com')
            else:
                ee.Initialize(credentials, opt_url='https://earthengine-highvolume.googleapis.com')
            
            # Test connection
            ee.Number(1).getInfo()
            return True, "Service account authentication successful!"
            
        except Exception as e:
            return False, f"Service account error: {str(e)}"
    
    def _initialize_with_refresh_token(self, creds_data: dict, project_id: str = None) -> tuple:
        """
        Initialize with OAuth refresh token credentials.
        Uses ref app pattern: write to ~/.config/earthengine/credentials and let EE discover it.
        """
        try:
            import os
            
            # Write credentials to the standard EE location
            ee_creds_dir = os.path.expanduser("~/.config/earthengine")
            os.makedirs(ee_creds_dir, exist_ok=True)
            
            ee_creds_path = os.path.join(ee_creds_dir, "credentials")
            
            # Write the credentials file
            with open(ee_creds_path, "w", encoding="utf-8") as f:
                json.dump(creds_data, f)
            
            # Initialize EE - it will discover the credentials file automatically
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
            
            # Test connection
            ee.Number(1).getInfo()
            return True, "OAuth authentication successful!"
            
        except Exception as e:
            return False, f"OAuth error: {str(e)}"


def ensure_ee_initialized() -> bool:
    """
    Ensure Earth Engine is initialized.
    Returns True if ready, False otherwise.
    """
    import os
    
    try:
        # Quick test
        ee.Number(1).getInfo()
        return True
    except Exception:
        pass
    
    # Try to reinitialize from session state
    if st.session_state.get('gee_credentials'):
        try:
            creds = st.session_state.gee_credentials
            project_id = st.session_state.get('gee_project_id')
            
            if 'private_key' in creds:
                # Service account
                import google.oauth2.service_account
                credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                    creds,
                    scopes=['https://www.googleapis.com/auth/earthengine']
                )
                ee.Initialize(credentials, project=project_id or creds.get('project_id'))
                return True
            elif 'refresh_token' in creds:
                # OAuth - write to file and let EE discover it
                ee_creds_dir = os.path.expanduser("~/.config/earthengine")
                os.makedirs(ee_creds_dir, exist_ok=True)
                ee_creds_path = os.path.join(ee_creds_dir, "credentials")
                
                with open(ee_creds_path, "w", encoding="utf-8") as f:
                    json.dump(creds, f)
                
                if project_id:
                    ee.Initialize(project=project_id)
                else:
                    ee.Initialize()
                return True
        except Exception:
            pass
    
    # Try Streamlit secrets
    try:
        if hasattr(st, 'secrets') and 'gee_service_account' in st.secrets:
            import google.oauth2.service_account
            creds_data = dict(st.secrets['gee_service_account'])
            credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            ee.Initialize(credentials, project=creds_data.get('project_id'))
            return True
    except Exception:
        pass
    
    # Try default initialization (if user already has credentials locally)
    try:
        ee.Initialize()
        ee.Number(1).getInfo()
        return True
    except Exception:
        pass
    
    return False
