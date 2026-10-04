import os
import requests
import geopandas as gpd
from shapely.geometry import shape
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# NOAA Active Tsunami Endpoint
TSUNAMI_ALERTS_URL = "https://api.weather.gov/alerts/active?event=Tsunami%20Warning,Tsunami%20Advisory,Tsunami%20Watch"
HEADERS = {
    "User-Agent": "EvacAssist (resilience@example.com)",
    "Accept": "application/geo+json"
}

SEVERITY_MAP = {
    "Extreme": 5,
    "Severe": 5,
    "Moderate": 4,
    "Minor": 3,
    "Unknown": 3
}

def fetch_tsunami_alerts():
    """Fetch active Tsunami alerts from NOAA/NTWC and return a GeoDataFrame."""
    try:
        resp = requests.get(TSUNAMI_ALERTS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching Tsunami alerts: {e}")
        return gpd.GeoDataFrame()

    features = data.get('features', []) or []
    records = []

    for feat in features:
        props = feat.get('properties', {}) or {}
        geom = feat.get('geometry')

        if not geom:
            continue

        try:
            poly_geometry = shape(geom)
            centroid = poly_geometry.centroid
        except Exception:
            continue

        records.append({
            'event_id': props.get('id', f"TSUNAMI-{props.get('event')}"),
            'event_type': props.get('event', 'Tsunami Alert'),
            'severity': SEVERITY_MAP.get(props.get('severity'), 4),
            'latitude': round(centroid.y, 5),
            'longitude': round(centroid.x, 5),
            'title': props.get('headline') or props.get('event'),
            'area_description': props.get('areaDesc'),
            'effective_time': props.get('effective'),
            'expires_time': props.get('expires'),
            'geometry': poly_geometry
        })

    if not records:
        return gpd.GeoDataFrame()

    return gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

def sync_tsunami_to_tiger():
    gdf = fetch_tsunami_alerts()
    if gdf.empty:
        print("No active tsunami warnings found.")
        return

    db_url = os.getenv(
        "TIGER_CLOUD_URL",
        "postgresql://tsdbadmin:nddk8ftawo1cqq2f@mmsuny0be8.rlx5eobeob.tsdb.cloud.timescale.com:37279/tsdb?sslmode=require"
    )
    engine = create_engine(db_url)

    gdf.to_postgis("disaster_events", engine, if_exists="append", index=False)
    print(f"Successfully synced {len(gdf)} active tsunami alerts to Tiger Cloud!")

if __name__ == "__main__":
    sync_tsunami_to_tiger()