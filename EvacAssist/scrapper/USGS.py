import requests
import pandas as pd
from shapely.geometry import Point

def fetch_usgs_earthquakes():
    """Fetches recent earthquake events from the USGS GeoJSON feed."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        records = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [0, 0, 0])
            
            lon, lat = coords[0], coords[1]
            mag = props.get("mag", 0.0) or 0.0
            
            # Map earthquake magnitude to a 1-5 severity scale
            severity = min(5, max(1, int(mag)))
            
            records.append({
                "event_id": f"usgs_{feature.get('id')}",
                "event_type": "Earthquake",
                "severity": severity,
                "latitude": lat,
                "longitude": lon,
                "title": props.get("title", "Earthquake Event"),
                "area_description": props.get("place", "Unknown Location"),
                "effective_time": pd.to_datetime(props.get("time"), unit="ms", utc=True) if props.get("time") else None,
                "expires_time": pd.to_datetime(props.get("updated"), unit="ms", utc=True) if props.get("updated") else None,
                "geometry": Point(lon, lat)
            })
        
        df = pd.DataFrame(records)
        print(f"  [USGS] Successfully fetched {len(df)} earthquake records.")
        return df
        
    except Exception as e:
        print(f"  [USGS ERROR] Failed to fetch earthquake data: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    df = fetch_usgs_earthquakes()
    print(df.head())