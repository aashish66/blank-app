"""
AgriVision Pro V3 - Image Processing Utilities
===============================================
Functions for processing uploaded images and calculating RGB-based indices.
"""

import numpy as np
from PIL import Image
import io
from typing import Tuple, Optional


def load_uploaded_image(uploaded_file) -> Optional[np.ndarray]:
    """
    Load an uploaded image file into a numpy array.
    
    Args:
        uploaded_file: Streamlit uploaded file object
    
    Returns:
        Numpy array of shape (H, W, 3) or None if failed
    """
    try:
        image = Image.open(uploaded_file)
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return np.array(image)
    except Exception:
        return None


def calculate_rgb_ndvi(image: np.ndarray) -> np.ndarray:
    """
    Calculate RGB-based NDVI using (NIR - Red) / (NIR + Red).
    For RGB images, we approximate NIR using the green channel.
    
    Formula: (Green - Red) / (Green + Red)
    
    Args:
        image: RGB image array (H, W, 3)
    
    Returns:
        NDVI array (H, W) with values -1 to 1
    """
    red = image[:, :, 0].astype(float)
    green = image[:, :, 1].astype(float)
    
    # Avoid division by zero
    denominator = green + red
    denominator[denominator == 0] = 1
    
    ndvi = (green - red) / denominator
    return ndvi


def calculate_rgb_vari(image: np.ndarray) -> np.ndarray:
    """
    Calculate Visible Atmospherically Resistant Index (VARI).
    
    Formula: (Green - Red) / (Green + Red - Blue)
    
    Args:
        image: RGB image array (H, W, 3)
    
    Returns:
        VARI array (H, W)
    """
    red = image[:, :, 0].astype(float)
    green = image[:, :, 1].astype(float)
    blue = image[:, :, 2].astype(float)
    
    denominator = green + red - blue
    denominator[denominator == 0] = 1
    
    vari = (green - red) / denominator
    return np.clip(vari, -1, 1)


def calculate_rgb_gli(image: np.ndarray) -> np.ndarray:
    """
    Calculate Green Leaf Index (GLI).
    
    Formula: (2*Green - Red - Blue) / (2*Green + Red + Blue)
    
    Args:
        image: RGB image array (H, W, 3)
    
    Returns:
        GLI array (H, W) with values -1 to 1
    """
    red = image[:, :, 0].astype(float)
    green = image[:, :, 1].astype(float)
    blue = image[:, :, 2].astype(float)
    
    numerator = 2 * green - red - blue
    denominator = 2 * green + red + blue
    denominator[denominator == 0] = 1
    
    gli = numerator / denominator
    return np.clip(gli, -1, 1)


def calculate_rgb_exg(image: np.ndarray) -> np.ndarray:
    """
    Calculate Excess Green Index (ExG).
    
    Formula: 2*Green - Red - Blue
    
    Args:
        image: RGB image array (H, W, 3)
    
    Returns:
        ExG array (H, W), normalized to 0-1 range
    """
    red = image[:, :, 0].astype(float) / 255
    green = image[:, :, 1].astype(float) / 255
    blue = image[:, :, 2].astype(float) / 255
    
    exg = 2 * green - red - blue
    # Normalize to 0-1 range
    exg = (exg + 1) / 2
    return np.clip(exg, 0, 1)


def calculate_rgb_ngrdi(image: np.ndarray) -> np.ndarray:
    """
    Calculate Normalized Green-Red Difference Index (NGRDI).
    
    Formula: (Green - Red) / (Green + Red)
    Same as RGB-NDVI but commonly used name.
    
    Args:
        image: RGB image array (H, W, 3)
    
    Returns:
        NGRDI array (H, W) with values -1 to 1
    """
    return calculate_rgb_ndvi(image)


def calculate_rgb_index(image: np.ndarray, index_name: str) -> np.ndarray:
    """
    Calculate specified RGB-based vegetation index.
    
    Args:
        image: RGB image array (H, W, 3)
        index_name: Name of index to calculate
    
    Returns:
        Index array (H, W)
    """
    calculators = {
        'RGB-NDVI': calculate_rgb_ndvi,
        'VARI': calculate_rgb_vari,
        'GLI': calculate_rgb_gli,
        'ExG': calculate_rgb_exg,
        'NGRDI': calculate_rgb_ngrdi,
    }
    
    calculator = calculators.get(index_name, calculate_rgb_ndvi)
    return calculator(image)


def create_colormap_image(
    data: np.ndarray,
    vmin: float = None,
    vmax: float = None,
    cmap_name: str = 'RdYlGn'
) -> Image.Image:
    """
    Create a colored image from index data using a colormap.
    
    Args:
        data: 2D array of index values
        vmin: Minimum value for colormap
        vmax: Maximum value for colormap
        cmap_name: Matplotlib colormap name
    
    Returns:
        PIL Image with colormap applied
    """
    import matplotlib.pyplot as plt
    from matplotlib import cm
    
    if vmin is None:
        vmin = np.nanpercentile(data, 5)
    if vmax is None:
        vmax = np.nanpercentile(data, 95)
    
    # Normalize data
    normalized = (data - vmin) / (vmax - vmin)
    normalized = np.clip(normalized, 0, 1)
    
    # Apply colormap
    cmap = cm.get_cmap(cmap_name)
    colored = cmap(normalized)
    
    # Convert to 8-bit RGB
    rgb = (colored[:, :, :3] * 255).astype(np.uint8)
    
    return Image.fromarray(rgb)


# Available RGB indices with descriptions
RGB_INDICES = {
    'RGB-NDVI': {
        'name': 'RGB-based NDVI',
        'formula': '(Green - Red) / (Green + Red)',
        'description': 'Approximates NDVI using visible bands only. Good for basic vegetation detection.',
        'range': (-1, 1)
    },
    'VARI': {
        'name': 'Visible Atmospherically Resistant Index',
        'formula': '(Green - Red) / (Green + Red - Blue)',
        'description': 'Designed to minimize atmospheric effects in RGB imagery.',
        'range': (-1, 1)
    },
    'GLI': {
        'name': 'Green Leaf Index',
        'formula': '(2*Green - Red - Blue) / (2*Green + Red + Blue)',
        'description': 'Emphasizes green vegetation in RGB images.',
        'range': (-1, 1)
    },
    'ExG': {
        'name': 'Excess Green Index',
        'formula': '2*Green - Red - Blue',
        'description': 'Simple excess green calculation for vegetation detection.',
        'range': (0, 1)
    },
    'NGRDI': {
        'name': 'Normalized Green-Red Difference Index',
        'formula': '(Green - Red) / (Green + Red)',
        'description': 'Normalized difference between green and red bands.',
        'range': (-1, 1)
    }
}


def get_rgb_indices() -> dict:
    """Get available RGB-based indices."""
    return RGB_INDICES
