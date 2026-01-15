"""
AgriVision Pro V3 - Download Utilities Module
==============================================
Image export and download functions.
"""

import streamlit as st
import ee
import geemap
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import io


def export_image_as_geotiff(
    image: ee.Image,
    aoi: ee.Geometry,
    scale: int,
    filename: str = "export"
) -> Optional[bytes]:
    """
    Export an Earth Engine image as GeoTIFF.
    
    Args:
        image: Earth Engine image to export
        aoi: Area of interest geometry
        scale: Export resolution in meters
        filename: Base filename for export
    
    Returns:
        Bytes of the GeoTIFF file or None if failed
    """
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / f"{filename}.tif"
            
            geemap.ee_export_image(
                image,
                filename=str(out_path),
                scale=scale,
                region=aoi,
                file_per_band=False
            )
            
            if out_path.exists() and out_path.stat().st_size > 0:
                with open(out_path, 'rb') as f:
                    return f.read()
            return None
            
    except Exception as e:
        st.warning(f"Export failed: {str(e)[:100]}")
        return None


def get_download_url(
    image: ee.Image,
    aoi: ee.Geometry,
    scale: int,
    name: str = "export"
) -> Optional[str]:
    """
    Get a download URL for an Earth Engine image.
    
    Args:
        image: Earth Engine image
        aoi: Area of interest
        scale: Export scale in meters
        name: Export name
    
    Returns:
        Download URL or None if failed
    """
    try:
        url = image.getDownloadURL({
            'name': name,
            'scale': scale,
            'region': aoi,
            'format': 'GEO_TIFF'
        })
        return url
    except Exception as e:
        st.warning(f"Could not generate download URL: {str(e)[:100]}")
        return None


def create_download_button(
    data: bytes,
    filename: str,
    label: str = "📥 Download",
    mime: str = "image/tiff"
) -> None:
    """Create a Streamlit download button."""
    st.download_button(
        label=label,
        data=data,
        file_name=filename,
        mime=mime
    )
