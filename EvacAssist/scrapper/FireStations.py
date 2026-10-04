import requests
import pandas as pd
from shapely.geometry import Point

def fetch_fire_stations():
    """Fetches Fire Stations from HIFLD ArcGIS endpoint."""
    url = "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Fire_Stations/FeatureServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
        "resultRecordCount": 250
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            print(f"  [FIRE STATIONS API ERROR] {data['error'].get('message')}")
            return pd.DataFrame()

        records = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            geom = feature.get("geometry", {}) or {}
            lon, lat = geom.get("x"), geom.get("y")
            if lon is None or lat is None:
                continue

            facility_id = attrs.get("OBJECTID") or f"{lat}_{lon}"
            name = attrs.get("NAME") or "Fire Station"
            address = f"{attrs.get('ADDRESS', '')}, {attrs.get('CITY', '')}, {attrs.get('STATE', '')}".strip(", ")

            records.append({
                "facility_id": f"fire_{facility_id}",
                "name": name,
                "facility_type": "Fire Station",
                "status": "OPEN",
                "capacity": 0,
                "address": address if address != "" else "Address unavailable",
                "latitude": lat,
                "longitude": lon,
                "geometry": Point(lon, lat)
            })
        df = pd.DataFrame(records)
        print(f"  [FIRE STATIONS] Successfully fetched {len(df)} records.")
        return df
    except Exception as e:
        print(f"  [FIRE STATIONS ERROR] {e}")
        return pd.DataFrame()