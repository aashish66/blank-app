# AgriVision Pro V3

🌾 **Satellite Vegetation Analysis Platform** powered by Google Earth Engine

## Features

- **4 Satellite Sensors**: Sentinel-2, Landsat 8/9, Landsat 5/7, MODIS
- **7+ Vegetation Indices**: NDVI, EVI, SAVI, NDWI, NDMI, GNDVI, NBR
- **Interactive Maps**: Real-time visualization with Folium
- **Time Series Analysis**: Track vegetation trends over time
- **Image Comparison**: Compare changes between dates/sensors
- **Dynamic Resolution**: Auto-scales based on area size
- **GeoTIFF Export**: Download analysis results

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Earth Engine Credentials
Run in terminal:
```bash
earthengine authenticate
```
Credentials are saved to: `~/.config/earthengine/credentials`

### 3. Run the App
```bash
streamlit run streamlit_app.py
```

## Project Structure

```
AgriVision_Pro_Version3/
├── streamlit_app.py          # Main application
├── requirements.txt          # Dependencies
├── core/                     # Core modules
│   ├── satellite_data.py     # Satellite collections
│   ├── vegetation_indices.py # Index calculations
│   ├── map_utils.py          # Map display
│   └── download_utils.py     # Export functions
├── app_components/           # UI components
│   ├── auth_component.py     # Authentication
│   ├── aoi_component.py      # Area selection
│   ├── time_series.py        # Time series charts
│   └── visitor_stats.py      # Visitor counter
└── .streamlit/
    └── config.toml           # Streamlit config
```

## Deployment on Streamlit Cloud

1. Push to GitHub
2. Connect to Streamlit Cloud
3. Add secrets for service account (optional):

```toml
[gee_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
# ... rest of service account JSON
```

## License

MIT License
