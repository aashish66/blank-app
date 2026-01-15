"""
AgriVision Pro V3 - Map Utilities Module
=========================================
Map display functions using Folium and st_folium.
"""

import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import time


def display_ee_map(
    center: list,
    zoom: int,
    ee_image: ee.Image = None,
    vis_params: dict = None,
    layer_name: str = "Layer",
    aoi: ee.Geometry = None,
    height: int = 500,
    key: str = None
) -> None:
    """
    Display an Earth Engine image on a Folium map using st_folium.
    
    Args:
        center: [lat, lon] center point
        zoom: Zoom level
        ee_image: Earth Engine image to display
        vis_params: Visualization parameters
        layer_name: Name for the layer
        aoi: Optional AOI geometry to show boundary
        height: Map height in pixels
        key: Unique key for the map component
    """
    # Ensure center is [lat, lon] format
    if isinstance(center, list) and len(center) == 2:
        if abs(center[0]) > 90:  # Longitude is first (GEE default)
            center = [center[1], center[0]]
    
    try:
        # Create base map
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles=None,
            control_scale=True
        )
        
        # Add base layers
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='OpenStreetMap',
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            control=True
        ).add_to(m)
        
        # Add GEE layer if provided
        gee_layer_added = False
        if ee_image is not None and vis_params is not None:
            try:
                # Ensure palette colors don't have # prefix
                if 'palette' in vis_params and isinstance(vis_params['palette'], list):
                    vis_params['palette'] = [
                        c.replace('#', '') if isinstance(c, str) else c 
                        for c in vis_params['palette']
                    ]
                
                map_id_dict = ee_image.getMapId(vis_params)
                tiles_url = map_id_dict['tile_fetcher'].url_format
                
                folium.TileLayer(
                    tiles=tiles_url,
                    attr='Google Earth Engine',
                    name=layer_name,
                    overlay=True,
                    control=True,
                    show=True
                ).add_to(m)
                gee_layer_added = True
                
            except Exception as e:
                st.error(f"❌ Could not load GEE layer: {str(e)[:100]}")
        
        # Add AOI boundary if provided
        if aoi is not None:
            try:
                aoi_geojson = aoi.getInfo()
                folium.GeoJson(
                    aoi_geojson,
                    name='Study Area',
                    style_function=lambda x: {
                        'fillColor': 'transparent',
                        'color': '#0066FF',
                        'weight': 3,
                        'fillOpacity': 0
                    }
                ).add_to(m)
            except Exception:
                pass  # Silently ignore AOI boundary errors
        
        # Add layer control
        folium.LayerControl(position='topright', collapsed=False).add_to(m)
        
        # Generate unique key if not provided
        if key is None:
            key = f"map_{layer_name.replace(' ', '_')}_{int(time.time() * 1000) % 100000}"
        
        # Render map with st_folium
        st_folium(m, width=700, height=height, key=key, returned_objects=[])
        
        if gee_layer_added:
            st.caption(f"✅ {layer_name} layer loaded")
        
    except Exception as e:
        st.error(f"❌ Map rendering error: {str(e)}")
