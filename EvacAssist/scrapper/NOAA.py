import uuid
import requests
import geopandas as gpd
from shapely.geometry import shape

NOAA_ALERTS_URL = "https://api.weather.gov/alerts/active?severity=Severe,Extreme"
HEADERS = {
    "User-Agent": "EvacAssist (resilience@example.com)",
    "Accept": "application/geo+json"
}

SEVERITY_MAP = {
    "Extreme": 5,
    "Severe": 4,
    "Moderate": 3,
    "Minor": 2,
    "Unknown": 1
}

def fetch_noaa_disasters():
    """Fetch active severe NOAA alerts and return a formatted GeoDataFrame."""
    try:
        resp = requests.get(NOAA_ALERTS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching NOAA alerts: {e}")
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
        except Exception as e:
            continue

        records.append({
            'event_id': props.get('id', str(uuid.uuid4())),
            'event_type': props.get('event', 'Weather Alert'),
            'severity': SEVERITY_MAP.get(props.get('severity'), 3),
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

    gdf = gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")
    return gdf

import os
from sqlalchemy import create_engine

def sync_noaa_to_tiger():
    """Fetches NOAA alerts and writes them straight into Tiger Cloud database."""
    gdf = fetch_noaa_disasters()
    if gdf.empty:
        print("No active alerts found to sync.")
        return

    db_url = os.getenv(
        "TIGER_CLOUD_URL",
        "postgresql://tsdbadmin:nddk8ftawo1cqq2f@mmsuny0be8.rlx5eobeob.tsdb.cloud.timescale.com:37279/tsdb?sslmode=require"
    )
    engine = create_engine(db_url)

    # Automatically writes the GeoDataFrame into the PostgreSQL/PostGIS database table
    gdf.to_postgis("disaster_events", engine, if_exists="replace", index=False)
    print(f"Successfully synced {len(gdf)} active NOAA alerts to Tiger Cloud!")

if __name__ == "__main__":
    sync_noaa_to_tiger()