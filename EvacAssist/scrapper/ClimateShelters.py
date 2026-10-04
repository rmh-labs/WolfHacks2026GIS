import requests
import pandas as pd
from shapely.geometry import Point

def fetch_climate_shelters():
    """Fetches cooling/warming shelters from OpenStreetMap with fast multi-mirror fallback."""
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    query = """
    [out:json][timeout:10];
    (
      node["amenity"="shelter"](32.0,-118.0,42.0,-80.0);
      node["social_facility"="shelter"](32.0,-118.0,42.0,-80.0);
    );
    out body 50 qt;
    """
    headers = {
        "User-Agent": "EvacAssistApp/1.0"
    }
    
    for url in endpoints:
        try:
            response = requests.post(url, data={"data": query}, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
            data = response.json()

            records = []
            for element in data.get("elements", []):
                lat = element.get("lat")
                lon = element.get("lon")
                if not lat or not lon:
                    continue

                tags = element.get("tags", {})
                osm_id = element.get("id")
                name = tags.get("name") or "Emergency Climate Shelter"

                records.append({
                    "facility_id": f"osm_{osm_id}",
                    "name": name.title(),
                    "facility_type": "Climate Shelter",
                    "status": "OPEN",
                    "capacity": 50,
                    "address": tags.get("addr:street", "Community Location"),
                    "latitude": lat,
                    "longitude": lon,
                    "geometry": Point(lon, lat)
                })
            df = pd.DataFrame(records)
            if not df.empty:
                print(f"  [CLIMATE SHELTERS] Successfully fetched {len(df)} records.")
                return df
        except Exception:
            continue

    print("  [CLIMATE SHELTERS NOTICE] Overpass servers busy; skipping shelters for this cycle.")
    return pd.DataFrame()