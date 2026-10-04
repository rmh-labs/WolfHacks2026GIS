Overview

This repository contains:
- migrations/001_create_observations.sql : PostGIS migration to create the `observations` table and indexes
- etl/etl.py : async ETL script fetching external APIs (NOAA/OpenMap), normalizing and upserting into PostGIS
- api/app.py : Flask API returning GeoJSON FeatureCollection for nearby observations
- requirements.txt : Python dependencies

Quick start

1) Install dependencies (use virtualenv or conda env):
   pip install -r requirements.txt

2) Configure environment:
   export DATABASE_URL="postgresql://user:pass@host:port/dbname"
   Optionally set SOURCE_URLS_JSON to a JSON array of source URLs for the ETL script, e.g.:
   export SOURCE_URLS_JSON='["https://example.com/noaa.geojson","https://example.com/openmap.json"]'

3) Run DB migration (use psql):
   psql "$DATABASE_URL" -f migrations/001_create_observations.sql

4) Run ETL (near real-time loop):
   python etl/etl.py

5) Run API server:
   FLASK_APP=api/app.py flask run --host=0.0.0.0 --port=5000

API

GET /features?lon=<lon>&lat=<lat>&radius=<meters>&limit=<n>
- Returns a GeoJSON FeatureCollection of observations within radius (meters) of lon/lat.

Notes and next steps

- You must populate SOURCE_URLS_JSON with real NOAA/OpenMap endpoints that return GeoJSON or lists of dicts.
- Improve the ETL parsing (normalize_record / extract_geometry_and_props) to match the exact API payload shapes you use.
- Consider using LISTEN/NOTIFY or a WebSocket server to push updates to clients for true real-time.
- Add retries/backoff and robust error handling for production.
- Use a connection pool and tune batch sizes and SLEEP_SECONDS for your near-real-time needs.

