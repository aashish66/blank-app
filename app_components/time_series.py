"""
AgriVision Pro V3 - Time Series Component
==========================================
Time series analysis and visualization using Plotly.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import ee
from typing import List, Dict
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.satellite_data import get_single_image, get_scale_for_sensor
from core.vegetation_indices import calculate_index


class TimeSeriesComponent:
    """Component for time series analysis."""
    
    def __init__(self, session_prefix: str = ""):
        """Initialize time series component."""
        self.prefix = session_prefix
    
    def render(
        self,
        aoi: ee.Geometry,
        images: List[Dict],
        sensor: str,
        index_name: str
    ) -> bool:
        """
        Render time series analysis.
        
        Args:
            aoi: Area of interest geometry
            images: List of image info dicts
            sensor: Sensor name
            index_name: Vegetation index to analyze
        
        Returns:
            True if analysis successful
        """
        st.subheader("📈 Time Series Analysis")
        
        if not images or len(images) < 2:
            st.info("Need at least 2 images for time series analysis.")
            return False
        
        st.info(f"Analyzing {len(images)} images for {index_name} trends")
        
        # Image limit slider
        max_images = st.slider(
            "Number of images to analyze:",
            2, min(len(images), 30), min(20, len(images)),
            key=f"{self.prefix}ts_limit"
        )
        
        if st.button("📊 Generate Time Series", type="primary", key=f"{self.prefix}gen_ts"):
            return self._generate_time_series(aoi, images[:max_images], sensor, index_name)
        
        return False
    
    def _generate_time_series(
        self,
        aoi: ee.Geometry,
        images: List[Dict],
        sensor: str,
        index_name: str
    ) -> bool:
        """Generate time series chart."""
        progress = st.progress(0, text="Calculating time series...")
        
        try:
            dates = []
            values = []
            scale = get_scale_for_sensor(sensor)
            
            for i, img_info in enumerate(images):
                progress.progress((i + 1) / len(images), text=f"Processing image {i+1}/{len(images)}...")
                
                try:
                    img = get_single_image(sensor, img_info['id'], aoi)
                    if img is None:
                        continue
                    
                    idx_img = calculate_index(img, index_name, sensor)
                    band_name = idx_img.bandNames().getInfo()[0]
                    
                    # Calculate mean over AOI with bestEffort=True
                    mean_val = idx_img.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=aoi,
                        scale=scale,
                        maxPixels=1e9,
                        bestEffort=True
                    ).getInfo()
                    
                    val = mean_val.get(band_name) or mean_val.get(index_name)
                    
                    if val is not None:
                        dates.append(img_info['date'])
                        values.append(val)
                        
                except Exception:
                    continue
            
            progress.empty()
            
            if not dates or not values:
                st.warning("⚠️ Could not calculate time series values.")
                return False
            
            # Create DataFrame
            df = pd.DataFrame({
                'Date': pd.to_datetime(dates),
                index_name: values
            }).sort_values('Date')
            
            # Create chart
            fig = px.line(
                df, x='Date', y=index_name,
                markers=True,
                title=f"{index_name} Time Series"
            )
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title=index_name,
                hovermode='x unified',
                template='plotly_white'
            )
            
            # Add trend line
            if len(df) >= 3:
                try:
                    z = pd.to_numeric(df['Date']).values
                    coeffs = np.polyfit(z, df[index_name].values, 1)
                    trend_y = coeffs[0] * z + coeffs[1]
                    fig.add_trace(go.Scatter(
                        x=df['Date'], y=trend_y,
                        mode='lines',
                        name='Trend',
                        line=dict(dash='dash', color='red')
                    ))
                except Exception:
                    pass
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Statistics
            self._show_statistics(df, index_name)
            
            # Data table
            with st.expander("📋 View Data Table"):
                st.dataframe(df.set_index('Date'), use_container_width=True)
            
            # CSV download
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                f"{index_name}_timeseries.csv",
                "text/csv",
                key=f"{self.prefix}download_csv"
            )
            
            return True
            
        except Exception as e:
            progress.empty()
            st.error(f"❌ Error: {str(e)}")
            return False
    
    def _show_statistics(self, df: pd.DataFrame, index_name: str):
        """Display statistics for the time series."""
        st.markdown("**📊 Statistics:**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        values = df[index_name]
        
        col1.metric("Mean", f"{values.mean():.3f}")
        col2.metric("Std Dev", f"{values.std():.3f}")
        col3.metric("Min", f"{values.min():.3f}")
        col4.metric("Max", f"{values.max():.3f}")
        
        # Trend direction
        if len(values) >= 3:
            try:
                z = np.arange(len(values))
                slope, _ = np.polyfit(z, values.values, 1)
                
                if slope > 0.01:
                    st.success("📈 **Trend: Increasing** (vegetation improving)")
                elif slope < -0.01:
                    st.warning("📉 **Trend: Decreasing** (vegetation declining)")
                else:
                    st.info("➡️ **Trend: Stable** (minimal change)")
            except Exception:
                pass
