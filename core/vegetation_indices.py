"""
AgriVision Pro V3 - Vegetation Indices Module
==============================================
Calculate vegetation indices from satellite imagery.
"""

import ee
from typing import Dict, Tuple


# =============================================================================
# Index Definitions
# =============================================================================

VEGETATION_INDICES = {
    "NDVI": {
        "name": "Normalized Difference Vegetation Index",
        "description": "Most common vegetation index. Values: -1 to 1 (healthy vegetation > 0.3)",
        "formula": "(NIR - Red) / (NIR + Red)",
        "range": (-1, 1)
    },
    "EVI": {
        "name": "Enhanced Vegetation Index",
        "description": "Improved sensitivity in high biomass areas.",
        "formula": "2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)",
        "range": (-1, 1)
    },
    "SAVI": {
        "name": "Soil Adjusted Vegetation Index",
        "description": "Minimizes soil brightness influences.",
        "formula": "1.5 * (NIR - Red) / (NIR + Red + 0.5)",
        "range": (-1.5, 1.5)
    },
    "NDWI": {
        "name": "Normalized Difference Water Index",
        "description": "Detects water content in vegetation.",
        "formula": "(Green - NIR) / (Green + NIR)",
        "range": (-1, 1)
    },
    "NDMI": {
        "name": "Normalized Difference Moisture Index",
        "description": "Sensitive to moisture levels in vegetation canopy.",
        "formula": "(NIR - SWIR1) / (NIR + SWIR1)",
        "range": (-1, 1)
    },
    "GNDVI": {
        "name": "Green NDVI",
        "description": "Sensitive to chlorophyll concentration.",
        "formula": "(NIR - Green) / (NIR + Green)",
        "range": (-1, 1)
    },
    "NBR": {
        "name": "Normalized Burn Ratio",
        "description": "Detects burned areas and fire severity.",
        "formula": "(NIR - SWIR2) / (NIR + SWIR2)",
        "range": (-1, 1)
    }
}


# =============================================================================
# Index Calculation Functions
# =============================================================================

def calculate_ndvi(image: ee.Image) -> ee.Image:
    """Calculate NDVI."""
    return image.normalizedDifference(['nir', 'red']).rename('NDVI')


def calculate_evi(image: ee.Image) -> ee.Image:
    """Calculate EVI."""
    return image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {
            'NIR': image.select('nir'),
            'RED': image.select('red'),
            'BLUE': image.select('blue')
        }
    ).rename('EVI')


def calculate_savi(image: ee.Image, L: float = 0.5) -> ee.Image:
    """Calculate SAVI with adjustable L factor."""
    return image.expression(
        '(1 + L) * (NIR - RED) / (NIR + RED + L)',
        {
            'NIR': image.select('nir'),
            'RED': image.select('red'),
            'L': L
        }
    ).rename('SAVI')


def calculate_ndwi(image: ee.Image) -> ee.Image:
    """Calculate NDWI."""
    return image.normalizedDifference(['green', 'nir']).rename('NDWI')


def calculate_ndmi(image: ee.Image) -> ee.Image:
    """Calculate NDMI."""
    return image.normalizedDifference(['nir', 'swir1']).rename('NDMI')


def calculate_gndvi(image: ee.Image) -> ee.Image:
    """Calculate Green NDVI."""
    return image.normalizedDifference(['nir', 'green']).rename('GNDVI')


def calculate_nbr(image: ee.Image) -> ee.Image:
    """Calculate Normalized Burn Ratio."""
    return image.normalizedDifference(['nir', 'swir2']).rename('NBR')


# =============================================================================
# Generic Index Calculator
# =============================================================================

def calculate_index(image: ee.Image, index_name: str, sensor: str = None) -> ee.Image:
    """Calculate specified vegetation index."""
    # For MODIS which already has NDVI/EVI
    if sensor == "MODIS":
        if index_name == "NDVI":
            return image.select('ndvi').rename('NDVI')
        elif index_name == "EVI":
            return image.select('evi').rename('EVI')
    
    calculators = {
        'NDVI': calculate_ndvi,
        'EVI': calculate_evi,
        'SAVI': calculate_savi,
        'NDWI': calculate_ndwi,
        'NDMI': calculate_ndmi,
        'GNDVI': calculate_gndvi,
        'NBR': calculate_nbr
    }
    
    calculator = calculators.get(index_name, calculate_ndvi)
    return calculator(image)


def get_available_indices(sensor: str = None) -> Dict:
    """Get available indices, optionally filtered by sensor capability."""
    return VEGETATION_INDICES


def get_index_vis_params(index_name: str) -> Tuple[float, float, list]:
    """Get visualization parameters for an index."""
    veg_palette = ['d73027', 'fc8d59', 'fee08b', 'd9ef8b', '91cf60', '1a9850']
    water_palette = ['8c510a', 'd8b365', 'f6e8c3', 'c7eae5', '5ab4ac', '01665e']
    burn_palette = ['1a9850', '91cf60', 'fee08b', 'fc8d59', 'd73027', '4d4d4d']
    
    params = {
        'NDVI': (-0.2, 0.8, veg_palette),
        'EVI': (-0.2, 0.8, veg_palette),
        'SAVI': (-0.2, 0.8, veg_palette),
        'NDWI': (-0.5, 0.5, water_palette),
        'NDMI': (-0.5, 0.5, water_palette),
        'GNDVI': (-0.2, 0.8, veg_palette),
        'NBR': (-0.5, 0.5, burn_palette)
    }
    
    return params.get(index_name, (-0.2, 0.8, veg_palette))
