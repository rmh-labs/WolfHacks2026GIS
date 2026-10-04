import os
import requests
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# USGS 3DEP Elevation API for querying elevation (Meters/Feet)
USGS_ELEVATION_URL = "https://epqs.nationalmap.gov/v1/json"

def get_point_elevation(lat, lon):
    """Query USGS 3DEP API for precise point elevation in meters."""
    params = {
        'x': lon,
        'y': lat,
        'units': 'Meters',
        'output': 'json'
    }
    try:
        resp = requests.get(USGS_ELEVATION_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get('value', 0))
    except Exception:
        return 0.0

def fetch_high_zones_around_points(coordinates_list):
    """
    Takes a list of coastal/low-lying (lat, lon) coordinates and filters
    for safe high-ground zones (Elevation > 30 meters / 100 feet).
    """
    records = []
    for idx, (lat, lon, label) in enumerate(coordinates_list):
        elevation_m = get_point_elevation(lat, lon)
        
        # Safe High Zone Threshold: Elevation > 30m above sea level
        if elevation_m >= 30.0:
            records.append({
                'facility_id': f"HIGH-ZONE-{idx+1}",
                'name': f"High Ground Refuge - {label}",
                'facility_type': 'High Zone / Safe Elevation',
                'status': 'OPEN',
                'capacity': 0,
                'address': f"Elevation: {round(elevation_m * 3.28084, 1)} ft above sea level",
                'latitude': round(lat, 5),
                'longitude': round(lon, 5),
                'geometry': Point(lon, lat)
            })

    if not records:
        return gpd.GeoDataFrame()

    return gpd.GeoDataFrame(records, geometry='geometry', crs="EPSG:4326")

def sync_high_zones_to_tiger():
    # Example candidate evacuation assembly points near coastal areas
    coastal_checkpoints = [
        (34.0195, -118.4912, "Santa Monica Hills"),
        (37.8044, -122.4721, "Presidio High Ground"),
        (25.7617, -80.1918, "Miami Ridge"),
        (47.6062, -122.3321, "Seattle First Hill")
    ]
    
    gdf = fetch_high_zones_around_points(coastal_checkpoints)
    if gdf.empty:
        print("No high zones meeting safety criteria found.")
        return

    db_url = os.getenv(
        "TIGER_CLOUD_URL",
        "postgresql://tsdbadmin:nddk8ftawo1cqq2f@mmsuny0be8.rlx5eobeob.tsdb.cloud.timescale.com:37279/tsdb?sslmode=require"
    )
    engine = create_engine(db_url)

    gdf.to_postgis("safe_zones", engine, if_exists="append", index=False)
    print(f"Successfully synced {len(gdf)} verified high zones to Tiger Cloud!")

if __name__ == "__main__":
    sync_high_zones_to_tiger()