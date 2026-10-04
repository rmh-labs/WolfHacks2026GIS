import requests
import pandas as pd
from shapely.geometry import LineString

def fetch_evacuation_routes():
    """Fetches designated evacuation corridors from ArcGIS FeatureServer."""
    url = "https://services3.arcgis.com/21H3muniXm83m5hZ/ArcGIS/rest/services/Evacuation_Routes/FeatureServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
        "resultRecordCount": 200
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            print(f"  [EVACUATION ROUTES API ERROR] {data['error'].get('message')}")
            return pd.DataFrame()

        records = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            geom = feature.get("geometry", {}) or {}
            paths = geom.get("paths", [])
            
            if not paths or len(paths[0]) < 2:
                continue

            line_coords = [(pt[0], pt[1]) for pt in paths[0]]
            route_id = attrs.get("OBJECTID") or attrs.get("ROUTE_NUM") or str(hash(str(line_coords)))
            route_name = attrs.get("NAME") or attrs.get("ROUTE_NUM") or "Evacuation Corridor"

            records.append({
                "route_id": f"route_{route_id}",
                "route_name": route_name,
                "state": attrs.get("STATE", "US"),
                "status": "ACTIVE",
                "hazard_type": "General Evacuation",
                "geometry": LineString(line_coords)
            })
        df = pd.DataFrame(records)
        print(f"  [EVACUATION ROUTES] Successfully fetched {len(df)} records.")
        return df
    except Exception as e:
        print(f"  [EVACUATION ROUTES ERROR] {e}")
        return pd.DataFrame()