import io
import requests
import pandas as pd
from shapely.geometry import Point

def fetch_nasa_firms():
    """Fetches 24h thermal hotspot data from NASA FIRMS."""
    url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv"
    headers = {"User-Agent": "EvacAssist/1.0"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        
        if df.empty:
            return pd.DataFrame()

        records = []
        for idx, row in df.iterrows():
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
            confidence = row.get("confidence", 50)
            
            try:
                conf_val = int(confidence)
            except (ValueError, TypeError):
                conf_val = 50

            severity = min(5, max(1, int(conf_val / 20)))

            records.append({
                "event_id": f"firms_{idx}_{lat}_{lon}",
                "event_type": "Wildfire Hotspot",
                "severity": severity,
                "latitude": lat,
                "longitude": lon,
                "title": "NASA FIRMS Thermal Hotspot",
                "area_description": f"Thermal anomaly detected (Confidence: {conf_val}%)",
                "effective_time": pd.Timestamp.now(tz="UTC"),
                "expires_time": pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=24),
                "geometry": Point(lon, lat)
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"  [FIRMS ERROR] {e}")
        return pd.DataFrame()