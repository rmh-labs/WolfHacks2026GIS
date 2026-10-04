import requests
import pandas as pd
from shapely.geometry import Point

def fetch_nifc_wildfires():
    """Fetches active NIFC wildfire incidents from ArcGIS REST API."""
    url = "https://services3.arcgis.com/T4QD1APIMaJWJuE/arcgis/rest/services/WFIGS_Incident_Locations/FeatureServer/0/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 300
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        records = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            geom = feature.get("geometry", {})
            
            lon, lat = geom.get("x"), geom.get("y")
            if lon is None or lat is None:
                continue
                
            incident_name = attrs.get("IncidentName") or attrs.get("poly_IncidentName") or "Active Wildfire"
            irwin_id = attrs.get("IrwinID") or attrs.get("OBJECTID") or str(hash(incident_name))
            acres = attrs.get("DailyAcres") or attrs.get("IncidentSize") or 0
            
            severity = 1
            if acres > 10000: severity = 5
            elif acres > 1000: severity = 4
            elif acres > 100: severity = 3
            elif acres > 10: severity = 2

            records.append({
                "event_id": f"nifc_{irwin_id}",
                "event_type": "Wildfire",
                "severity": severity,
                "latitude": lat,
                "longitude": lon,
                "title": f"Wildfire: {incident_name}",
                "area_description": f"Burnt area estimate: {acres} acres",
                "effective_time": pd.Timestamp.now(tz="UTC"),
                "expires_time": pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2),
                "geometry": Point(lon, lat)
            })
        return pd.DataFrame(records)
    except Exception as e:
        print(f"  [NIFC ERROR] {e}")
        return pd.DataFrame()