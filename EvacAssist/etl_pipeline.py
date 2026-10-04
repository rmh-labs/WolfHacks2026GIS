import pandas as pd
import geopandas as gpd
from sqlalchemy import text
from config import get_db_engine

# Import scrapers from scrapper module
from scrapper.USGS import fetch_usgs_earthquakes
from scrapper.Wildfires import fetch_nifc_wildfires
from scrapper.Tsunami import fetch_tsunami_alerts
from scrapper.FIRMS import fetch_nasa_firms
from scrapper.Hospitals import fetch_hospitals
from scrapper.FireStations import fetch_fire_stations
from scrapper.Police import fetch_police_stations
from scrapper.ClimateShelters import fetch_climate_shelters
from scrapper.EvacuationRoutes import fetch_evacuation_routes
from scrapper.HighZones import fetch_high_zones_around_points

# ==========================================
# DATA CLEANING & TRANSFORMATION PIPELINE
# ==========================================

def clean_disaster_events(df):
    """Clean and transform disaster event records."""
    if df is None or df.empty:
        return gpd.GeoDataFrame()

    # Drop missing primary keys or invalid coordinates
    df = df.dropna(subset=['event_id', 'latitude', 'longitude']).copy()
    df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(-180, 180))]

    # Standardize string fields
    df['title'] = df['title'].fillna('Active Incident').str.strip()
    df['area_description'] = df['area_description'].fillna('Location details pending').str.strip()
    df['severity'] = df['severity'].fillna(1).astype(int).clip(lower=1, upper=5)

    # Standardize timestamps
    for time_col in ['effective_time', 'expires_time']:
        if time_col in df.columns:
            df[time_col] = pd.to_datetime(df[time_col], errors='coerce', utc=True)

    # Round coordinates
    df['latitude'] = df['latitude'].round(5)
    df['longitude'] = df['longitude'].round(5)

    # Deduplicate by primary key
    df = df.drop_duplicates(subset=['event_id'], keep='last')

    # Convert to GeoDataFrame & validate geometries
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    gdf['geometry'] = gdf['geometry'].make_valid()
    return gdf


def clean_safe_zones(df):
    """Clean and transform safe zone and shelter facility records."""
    if df is None or df.empty:
        return gpd.GeoDataFrame()

    df = df.dropna(subset=['facility_id', 'latitude', 'longitude']).copy()
    df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(-180, 180))]

    df['name'] = df['name'].fillna('Refuge Center').str.strip()
    df['facility_type'] = df['facility_type'].fillna('Emergency Shelter').str.strip()
    df['status'] = df['status'].fillna('OPEN').str.upper()
    df['capacity'] = df['capacity'].fillna(0).astype(int)
    df['address'] = df['address'].fillna('Address Not Listed').str.strip()

    df['latitude'] = df['latitude'].round(5)
    df['longitude'] = df['longitude'].round(5)
    df = df.drop_duplicates(subset=['facility_id'], keep='last')

    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    gdf['geometry'] = gdf['geometry'].make_valid()
    return gdf


def clean_evacuation_routes(df):
    """Clean and transform evacuation corridor linear geometries."""
    if df is None or df.empty:
        return gpd.GeoDataFrame()

    df = df.dropna(subset=['route_id']).copy()
    df['route_name'] = df['route_name'].fillna('Evacuation Route').str.strip()
    df['status'] = df['status'].fillna('ACTIVE').str.upper()

    df = df.drop_duplicates(subset=['route_id'], keep='last')

    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
    gdf['geometry'] = gdf['geometry'].make_valid()
    return gdf

# ==========================================
# TIGER CLOUD UPSERT ENGINE
# ==========================================

def upsert_to_tiger_cloud(gdf, table_name, pk_field):
    """Upserts clean GeoDataFrame to Tiger Cloud using a temporary staging table."""
    if gdf is None or gdf.empty:
        print(f"--> Skipping {table_name}: No new data available.")
        return

    engine = get_db_engine()
    staging_table = f"staging_{table_name}"

    print(f"--> Staging {len(gdf)} clean records into '{staging_table}'...")
    gdf.to_postgis(staging_table, engine, if_exists="replace", index=False)

    non_pk_cols = [c for c in gdf.columns if c not in ['geometry', pk_field]]
    update_assignments = ", ".join([f"{col} = EXCLUDED.{col}" for col in non_pk_cols])
    all_cols = ", ".join(gdf.columns)

    upsert_sql = f"""
    INSERT INTO {table_name} ({all_cols})
    SELECT {all_cols} FROM {staging_table}
    ON CONFLICT ({pk_field})
    DO UPDATE SET {update_assignments}, updated_at = NOW();

    DROP TABLE IF EXISTS {staging_table};
    """

    with engine.connect() as conn:
        conn.execute(text(upsert_sql))
        conn.commit()

    print(f"--> Successfully synced {len(gdf)} records into '{table_name}'!")

# ==========================================
# PIPELINE EXECUTION
# ==========================================

def run_full_pipeline():
    print("==================================================")
    print("STARTING EVACASSIST ETL DATA PIPELINE")
    print("==================================================")

    # 1. DISASTER EVENTS PIPELINE
    print("\n[1/3] Extracting and processing Disaster Events...")
    disaster_dfs = []
    
    for name, fetch_fn in [
        ("USGS Earthquakes", fetch_usgs_earthquakes),
        ("NIFC Wildfires", fetch_nifc_wildfires),
        ("Tsunami Alerts", fetch_tsunami_alerts),
        ("NASA FIRMS Hotspots", fetch_nasa_firms)
    ]:
        try:
            print(f"    Fetching {name}...")
            data = fetch_fn()
            if not data.empty:
                disaster_dfs.append(data)
        except Exception as e:
            print(f"    Error fetching {name}: {e}")

    if disaster_dfs:
        combined_disasters = pd.concat(disaster_dfs, ignore_index=True)
        cleaned_disasters = clean_disaster_events(combined_disasters)
        upsert_to_tiger_cloud(cleaned_disasters, "disaster_events", "event_id")

    # 2. SAFE ZONES PIPELINE
    print("\n[2/3] Extracting and processing Safe Zones & Infrastructure...")
    safe_zone_dfs = []
    
    # Candidate coastal points for High Zone elevation queries
    sample_coastal_points = [
        (34.0195, -118.4912, "Santa Monica"),
        (37.8044, -122.4721, "Presidio SF"),
        (25.7617, -80.1918, "Miami Ridge")
    ]

    safe_zone_sources = [
        ("Hospitals", fetch_hospitals),
        ("Fire Stations", fetch_fire_stations),
        ("Police Stations", fetch_police_stations),
        ("Climate Shelters", fetch_climate_shelters),
        ("High Elevation Zones", lambda: fetch_high_zones_around_points(sample_coastal_points))
    ]

    for name, fetch_fn in safe_zone_sources:
        try:
            print(f"    Fetching {name}...")
            data = fetch_fn()
            if not data.empty:
                safe_zone_dfs.append(data)
        except Exception as e:
            print(f"    Error fetching {name}: {e}")

    if safe_zone_dfs:
        combined_safe_zones = pd.concat(safe_zone_dfs, ignore_index=True)
        cleaned_safe_zones = clean_safe_zones(combined_safe_zones)
        upsert_to_tiger_cloud(cleaned_safe_zones, "safe_zones", "facility_id")

    # 3. EVACUATION ROUTES PIPELINE
    print("\n[3/3] Extracting and processing Evacuation Corridors...")
    try:
        raw_routes = fetch_evacuation_routes()
        cleaned_routes = clean_evacuation_routes(raw_routes)
        upsert_to_tiger_cloud(cleaned_routes, "evacuation_routes", "route_id")
    except Exception as e:
        print(f"    Error fetching Evacuation Routes: {e}")

    print("\n==================================================")
    print("ETL PIPELINE COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_full_pipeline()