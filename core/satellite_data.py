"""
AgriVision Pro V3 - Satellite Data Module
==========================================
Handles satellite data retrieval from Google Earth Engine.
Supports: Sentinel-2, Landsat 8/9, Landsat 5/7, MODIS
"""

import streamlit as st
import ee
from typing import List, Dict, Optional


# =============================================================================
# Cloud Masking Functions
# =============================================================================

def mask_sentinel2_clouds(image):
    """Apply cloud mask to Sentinel-2 SR image using SCL band."""
    scl = image.select('SCL')
    mask = scl.neq(3).And(scl.neq(9)).And(scl.neq(10))
    return image.updateMask(mask).divide(10000)


def mask_landsat_clouds(image):
    """Apply cloud mask to Landsat Collection 2 image using QA_PIXEL."""
    qa = image.select('QA_PIXEL')
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
    return image.updateMask(cloud_mask).multiply(0.0000275).add(-0.2)


def mask_modis_clouds(image):
    """Apply quality mask to MODIS image."""
    qa = image.select('SummaryQA')
    mask = qa.eq(0)
    return image.updateMask(mask).multiply(0.0001)


# =============================================================================
# Collection Retrieval Functions
# =============================================================================

def get_sentinel2_collection(start_date: str, end_date: str, aoi: ee.Geometry, 
                              max_cloud: int = 30) -> ee.ImageCollection:
    """Get Sentinel-2 Surface Reflectance collection."""
    return (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterDate(start_date, end_date)
            .filterBounds(aoi)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud))
            .map(mask_sentinel2_clouds)
            .select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12'],
                   ['blue', 'green', 'red', 'red_edge1', 'red_edge2', 'red_edge3', 
                    'nir', 'red_edge4', 'swir1', 'swir2']))


def get_landsat89_collection(start_date: str, end_date: str, aoi: ee.Geometry,
                              max_cloud: int = 30) -> ee.ImageCollection:
    """Get Landsat 8/9 Collection 2 Surface Reflectance."""
    l8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
          .filterDate(start_date, end_date)
          .filterBounds(aoi)
          .filter(ee.Filter.lt('CLOUD_COVER', max_cloud))
          .map(mask_landsat_clouds))
    
    l9 = (ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')
          .filterDate(start_date, end_date)
          .filterBounds(aoi)
          .filter(ee.Filter.lt('CLOUD_COVER', max_cloud))
          .map(mask_landsat_clouds))
    
    return (l8.merge(l9)
            .select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
                   ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']))


def get_landsat57_collection(start_date: str, end_date: str, aoi: ee.Geometry,
                              max_cloud: int = 30) -> ee.ImageCollection:
    """Get Landsat 5/7 Collection 2 Surface Reflectance (historical data)."""
    l5 = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
          .filterDate(start_date, end_date)
          .filterBounds(aoi)
          .filter(ee.Filter.lt('CLOUD_COVER', max_cloud))
          .map(mask_landsat_clouds))
    
    l7 = (ee.ImageCollection('LANDSAT/LE07/C02/T1_L2')
          .filterDate(start_date, end_date)
          .filterBounds(aoi)
          .filter(ee.Filter.lt('CLOUD_COVER', max_cloud))
          .map(mask_landsat_clouds))
    
    return (l5.merge(l7)
            .select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
                   ['blue', 'green', 'red', 'nir', 'swir1', 'swir2']))


def get_modis_collection(start_date: str, end_date: str, aoi: ee.Geometry,
                          max_cloud: int = 100) -> ee.ImageCollection:
    """Get MODIS Terra Vegetation Indices (MOD13Q1 - 250m, 16-day)."""
    return (ee.ImageCollection('MODIS/061/MOD13Q1')
            .filterDate(start_date, end_date)
            .filterBounds(aoi)
            .map(mask_modis_clouds)
            .select(['NDVI', 'EVI'], ['ndvi', 'evi']))


# =============================================================================
# Scale and Resolution Functions
# =============================================================================

def get_scale_for_sensor(sensor: str) -> int:
    """Get appropriate scale (resolution) for sensor."""
    scales = {
        "Sentinel-2": 10,
        "Landsat 8/9": 30,
        "Landsat 5/7": 30,
        "MODIS": 250
    }
    return scales.get(sensor, 30)


def get_adaptive_scale_for_area(area_km2: float, sensor: str) -> int:
    """
    Get adaptive scale based on AOI size (ref app pattern).
    Larger areas use coarser resolution to prevent GEE memory issues.
    """
    base_scale = get_scale_for_sensor(sensor)
    
    if area_km2 > 50000:  # Very large (country scale)
        return max(5000, base_scale)
    elif area_km2 > 10000:  # Large (regional)
        return max(2000, base_scale)
    elif area_km2 > 1000:  # Medium (state)
        return max(500, base_scale)
    elif area_km2 > 100:  # Small-medium (county)
        return max(100, base_scale)
    else:  # Small (farm)
        return base_scale


# =============================================================================
# Image List and Single Image Retrieval
# =============================================================================

@st.cache_data(ttl=3600, show_spinner="Searching for images...")
def get_image_list(sensor: str, start_date: str, end_date: str, 
                   _aoi, max_cloud: int = 100, limit: int = 100) -> List[Dict]:
    """Get list of available images with metadata."""
    aoi = _aoi
    
    if sensor == "Sentinel-2":
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterDate(start_date, end_date)
                     .filterBounds(aoi)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', max_cloud)))
        date_prop = 'system:time_start'
        cloud_prop = 'CLOUDY_PIXEL_PERCENTAGE'
    elif sensor == "Landsat 8/9":
        collection = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
                     .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
                     .filterDate(start_date, end_date)
                     .filterBounds(aoi)
                     .filter(ee.Filter.lt('CLOUD_COVER', max_cloud)))
        date_prop = 'system:time_start'
        cloud_prop = 'CLOUD_COVER'
    elif sensor == "Landsat 5/7":
        collection = (ee.ImageCollection('LANDSAT/LT05/C02/T1_L2')
                     .merge(ee.ImageCollection('LANDSAT/LE07/C02/T1_L2'))
                     .filterDate(start_date, end_date)
                     .filterBounds(aoi)
                     .filter(ee.Filter.lt('CLOUD_COVER', max_cloud)))
        date_prop = 'system:time_start'
        cloud_prop = 'CLOUD_COVER'
    else:  # MODIS
        collection = (ee.ImageCollection('MODIS/061/MOD13Q1')
                     .filterDate(start_date, end_date)
                     .filterBounds(aoi))
        date_prop = 'system:time_start'
        cloud_prop = None
    
    collection = collection.sort('system:time_start', False).limit(limit)
    
    def extract_info(img):
        date = ee.Date(img.get(date_prop)).format('YYYY-MM-dd')
        cloud = img.get(cloud_prop) if cloud_prop else 0
        return ee.Feature(None, {
            'id': img.id(),
            'date': date,
            'cloud_cover': cloud
        })
    
    features = collection.map(extract_info).getInfo()
    
    return [
        {
            'id': f['properties']['id'],
            'date': f['properties']['date'],
            'cloud_cover': round(f['properties']['cloud_cover'] or 0, 1)
        }
        for f in features.get('features', [])
    ]


def get_single_image(sensor: str, image_id: str, aoi: ee.Geometry) -> Optional[ee.Image]:
    """Get a single image by ID with cloud masking applied."""
    try:
        if sensor == "Sentinel-2":
            img = ee.Image(f'COPERNICUS/S2_SR_HARMONIZED/{image_id}')
            img = mask_sentinel2_clouds(img)
            img = img.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12'],
                            ['blue', 'green', 'red', 'red_edge1', 'red_edge2', 'red_edge3',
                             'nir', 'red_edge4', 'swir1', 'swir2'])
        elif sensor == "Landsat 8/9":
            img = ee.Image(image_id)
            img = mask_landsat_clouds(img)
            img = img.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'],
                            ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
        elif sensor == "Landsat 5/7":
            img = ee.Image(image_id)
            img = mask_landsat_clouds(img)
            img = img.select(['SR_B1', 'SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B7'],
                            ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'])
        else:  # MODIS
            img = ee.Image(f'MODIS/061/MOD13Q1/{image_id}')
            img = img.multiply(0.0001).select(['NDVI', 'EVI'], ['ndvi', 'evi'])
        
        return img.clip(aoi)
    
    except Exception:
        return None
