"""
AgriVision Pro V3 - AOI Component
==================================
Area of Interest selection with 3 methods:
1. Draw on Map
2. Upload GeoJSON
3. Enter Coordinates
"""

import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import ee
import json
from typing import Optional, Dict, Any


class AOIComponent:
    """Area of Interest selection component."""
    
    def __init__(self, session_prefix: str = "", title: str = "📍 Select Area of Interest"):
        """Initialize AOI component."""
        self.prefix = session_prefix
        self.title = title
        self.geometry_key = f"{session_prefix}aoi_geometry"
        self.confirmed_key = f"{session_prefix}aoi_confirmed"
        self.area_key = f"{session_prefix}aoi_area_km2"
    
    def render(self) -> Optional[ee.Geometry]:
        """
        Render AOI selection UI.
        
        Returns:
            ee.Geometry if confirmed, None otherwise
        """
        st.subheader(self.title)
        
        # Check if AOI already confirmed
        if st.session_state.get(self.confirmed_key, False):
            geometry = st.session_state.get(self.geometry_key)
            if geometry:
                area = st.session_state.get(self.area_key, 0)
                st.success(f"✅ Area of interest confirmed ({area:.2f} km²)")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Change Area", key=f"{self.prefix}change_aoi"):
                        st.session_state[self.confirmed_key] = False
                        st.rerun()
                
                return geometry
        
        # Selection method tabs
        method = st.radio(
            "Select method:",
            ["🗺️ Draw on Map", "📁 Upload GeoJSON", "📐 Enter Coordinates"],
            horizontal=True,
            key=f"{self.prefix}aoi_method"
        )
        
        if method == "🗺️ Draw on Map":
            return self._render_draw_method()
        elif method == "📁 Upload GeoJSON":
            return self._render_upload_method()
        else:
            return self._render_coordinates_method()
    
    def _render_draw_method(self) -> Optional[ee.Geometry]:
        """Render draw on map method."""
        st.info("👆 Use the drawing tools on the map to select your area")
        
        # Create map with drawing tools
        m = folium.Map(location=[39.0, -98.0], zoom_start=4)
        
        # Add tile layers
        folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri', name='Satellite'
        ).add_to(m)
        
        # Add drawing tools
        Draw(
            export=False,
            position='topright',
            draw_options={
                'polyline': False,
                'rectangle': {'shapeOptions': {'color': '#ff7f0e', 'fillOpacity': 0.3}},
                'polygon': {'shapeOptions': {'color': '#1f77b4', 'fillOpacity': 0.3}},
                'circle': False,
                'marker': False,
                'circlemarker': False
            }
        ).add_to(m)
        
        folium.LayerControl().add_to(m)
        
        # Render map
        map_data = st_folium(
            m, width=700, height=400,
            key=f"{self.prefix}draw_map",
            returned_objects=["all_drawings"]
        )
        
        # Check for drawings
        if map_data.get('all_drawings') and len(map_data['all_drawings']) > 0:
            latest = map_data['all_drawings'][-1]
            geometry_dict = latest.get('geometry')
            
            if geometry_dict:
                st.success(f"📍 Shape detected: {geometry_dict.get('type', 'Unknown')}")
                
                if st.button("✅ Confirm This Area", type="primary", key=f"{self.prefix}confirm_draw"):
                    return self._confirm_geometry(geometry_dict)
        
        return None
    
    def _render_upload_method(self) -> Optional[ee.Geometry]:
        """Render GeoJSON upload method."""
        uploaded_file = st.file_uploader(
            "Upload GeoJSON or JSON file:",
            type=['geojson', 'json'],
            key=f"{self.prefix}geojson_upload"
        )
        
        if uploaded_file:
            try:
                content = uploaded_file.read().decode('utf-8')
                geojson_data = json.loads(content)
                
                # Extract geometry
                if geojson_data.get('type') == 'FeatureCollection':
                    features = geojson_data.get('features', [])
                    if features:
                        geometry_dict = features[0].get('geometry')
                        st.success(f"✅ Found {len(features)} feature(s)")
                    else:
                        st.error("No features found in file")
                        return None
                elif geojson_data.get('type') == 'Feature':
                    geometry_dict = geojson_data.get('geometry')
                    st.success("✅ Feature loaded")
                else:
                    geometry_dict = geojson_data
                    st.success("✅ Geometry loaded")
                
                if st.button("✅ Use This Area", type="primary", key=f"{self.prefix}confirm_upload"):
                    return self._confirm_geometry(geometry_dict)
                    
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON file")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        
        return None
    
    def _render_coordinates_method(self) -> Optional[ee.Geometry]:
        """Render coordinate input method."""
        st.info("Enter bounding box coordinates (WGS84)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Southwest Corner:**")
            min_lon = st.number_input("Min Longitude", value=-98.0, format="%.6f", key=f"{self.prefix}min_lon")
            min_lat = st.number_input("Min Latitude", value=35.0, format="%.6f", key=f"{self.prefix}min_lat")
        
        with col2:
            st.markdown("**Northeast Corner:**")
            max_lon = st.number_input("Max Longitude", value=-97.0, format="%.6f", key=f"{self.prefix}max_lon")
            max_lat = st.number_input("Max Latitude", value=36.0, format="%.6f", key=f"{self.prefix}max_lat")
        
        # Buffer option
        use_buffer = st.checkbox("Use point with buffer instead", key=f"{self.prefix}use_buffer")
        
        if use_buffer:
            center_lon = st.number_input("Center Longitude", value=-98.0, format="%.6f", key=f"{self.prefix}center_lon")
            center_lat = st.number_input("Center Latitude", value=35.0, format="%.6f", key=f"{self.prefix}center_lat")
            buffer_km = st.slider("Buffer (km)", 1, 50, 10, key=f"{self.prefix}buffer_km")
            
            if st.button("✅ Create Area", type="primary", key=f"{self.prefix}confirm_buffer"):
                try:
                    point = ee.Geometry.Point([center_lon, center_lat])
                    geometry = point.buffer(buffer_km * 1000)
                    return self._store_and_confirm(geometry)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        else:
            valid = min_lon < max_lon and min_lat < max_lat
            if not valid:
                st.error("❌ Min values must be less than max values")
            
            if st.button("✅ Create Area", type="primary", disabled=not valid, key=f"{self.prefix}confirm_coords"):
                try:
                    geometry = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                    return self._store_and_confirm(geometry)
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        return None
    
    def _confirm_geometry(self, geometry_dict: Dict) -> Optional[ee.Geometry]:
        """Convert geometry dict to EE geometry and store."""
        try:
            geometry = ee.Geometry(geometry_dict)
            return self._store_and_confirm(geometry)
        except Exception as e:
            st.error(f"❌ Error creating geometry: {str(e)}")
            return None
    
    def _store_and_confirm(self, geometry: ee.Geometry) -> ee.Geometry:
        """Store geometry in session state and confirm."""
        try:
            # Calculate area
            area_km2 = geometry.area().divide(1e6).getInfo()
            
            # Store in session state
            st.session_state[self.geometry_key] = geometry
            st.session_state[self.confirmed_key] = True
            st.session_state[self.area_key] = area_km2
            
            st.success(f"✅ Area confirmed: {area_km2:.2f} km²")
            st.rerun()
            return geometry
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            return None
