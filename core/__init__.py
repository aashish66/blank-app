"""
AgriVision Pro V3 - Core Module
================================
Core utilities for satellite data and vegetation analysis.
"""

from .satellite_data import (
    get_sentinel2_collection,
    get_landsat89_collection,
    get_landsat57_collection,
    get_modis_collection,
    get_scale_for_sensor,
    get_image_list,
    get_single_image,
)

from .vegetation_indices import (
    calculate_index,
    get_available_indices,
    get_index_vis_params,
    VEGETATION_INDICES,
)

from .map_utils import display_ee_map

__all__ = [
    'get_sentinel2_collection',
    'get_landsat89_collection',
    'get_landsat57_collection',
    'get_modis_collection',
    'get_scale_for_sensor',
    'get_image_list',
    'get_single_image',
    'calculate_index',
    'get_available_indices',
    'get_index_vis_params',
    'VEGETATION_INDICES',
    'display_ee_map',
]
