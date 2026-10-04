"""
Async ETL script to fetch from external APIs (NOAA / OpenMap), normalize, and upsert into PostGIS (Postgres).
Configure via environment variables:
  DATABASE_URL - PostgreSQL DSN (e.g. postgresql://user:pass@host:port/dbname)
  SOURCE_URLS - optional JSON list of URLs or you can edit SOURCE_LIST below

Usage: python etl/etl.py

Notes:
- This script expects incoming geo data either as GeoJSON FeatureCollection or as a list of dicts where each dict
  contains geometry information (lat/lon or GeoJSON geometry).
- It upserts into the "observations" table from migrations/001_create_observations.sql
"""
import os
import asyncio
import aiohttp
import asyncpg
import json
import hashlib
from datetime import datetime
from typing import List, Tuple, Optional

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_DSN")
# Replace these with the actual NOAA / OpenMap endpoints you intend to poll
# Example placeholders: ['https://api.noaa.gov/whatever', 'https://openmap.api/whatever']
SOURCE_LIST = os.getenv("SOURCE_URLS_JSON")
if SOURCE_LIST:
    try:
        SOURCE_URLS = json.loads(SOURCE_LIST)
    except Exception:
        SOURCE_URLS = []
else:
    SOURCE_URLS = []

# Config
BATCH_SIZE = 500
SLEEP_SECONDS = 5

UPSERT_SQL = """
INSERT INTO observations (id, source, obs_time, properties, geom)
VALUES ($1, $2, $3, $4::jsonb, ST_SetSRID(ST_GeomFromGeoJSON($5::json),4326))
ON CONFLICT (id) DO UPDATE
  SET source = EXCLUDED.source,
      obs_time = EXCLUDED.obs_time,
      properties = observations.properties || EXCLUDED.properties,
      geom = EXCLUDED.geom;
"""

async def fetch_json(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url, timeout=30) as r:
            r.raise_for_status()
            return await r.json()
    except Exception as e:
        print(f"fetch error for {url}: {e}")
        return None


def make_uid(source: str, lat: float, lon: float, obs_time: Optional[datetime], raw_id: Optional[str] = None) -> str:
    if raw_id:
        return f"{source}:{raw_id}"
    key = f"{source}:{lat}:{lon}:{obs_time.isoformat() if obs_time else ''}"
    return hashlib.sha1(key.encode()).hexdigest()


def extract_geometry_and_props(feature: dict) -> Optional[Tuple[float,float,Optional[str],dict]]:
    """Try to extract (lat, lon, raw_id, properties_dict) from various shapes of payloads."""
    # Case 1: GeoJSON Feature
    if feature.get('type') == 'Feature' and 'geometry' in feature:
        geom = feature['geometry']
        props = feature.get('properties') or {}
        raw_id = props.get('id') or props.get('identifier')
        # only handle Point geometry here for simplicity
        if geom and geom.get('type') == 'Point' and isinstance(geom.get('coordinates'), (list, tuple)):
            lon, lat = geom['coordinates'][0], geom['coordinates'][1]
            return lat, lon, raw_id, props
        return None

    # Case 2: FeatureCollection
    if feature.get('type') == 'FeatureCollection' and 'features' in feature:
        # caller should iterate over features
        return None

    # Case 3: simple dict with lat/lon keys
    lat_keys = ['lat', 'latitude', 'y']
    lon_keys = ['lon', 'lng', 'longitude', 'x']
    lat = None
    lon = None
    for k in lat_keys:
        if k in feature:
            try:
                lat = float(feature[k])
                break
            except Exception:
                pass
    for k in lon_keys:
        if k in feature:
            try:
                lon = float(feature[k])
                break
            except Exception:
                pass
    if lat is not None and lon is not None:
        raw_id = feature.get('id') or feature.get('identifier')
        return lat, lon, raw_id, feature

    # Nothing matched
    return None


def normalize_timestamp(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        # try ISO formats
        return datetime.fromisoformat(val)
    except Exception:
        try:
            # fallback: parse as int unix timestamp
            ts = int(val)
            return datetime.utcfromtimestamp(ts)
        except Exception:
            return None


def normalize_record(source: str, lat: float, lon: float, raw_id: Optional[str], props: dict) -> Optional[Tuple[str,str,Optional[datetime],str,str]]:
    # validate coordinates
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    obs_time = None
    # try common timestamp keys
    for k in ('time','timestamp','obs_time','date','datetime'):
        if k in props:
            obs_time = normalize_timestamp(props.get(k))
            break
    uid = make_uid(source, lat, lon, obs_time, raw_id)
    # normalize keys to lowercase to make merges consistent
    properties = {str(k).lower(): v for k, v in props.items()}
    geom_geojson = json.dumps({"type": "Point", "coordinates": [lon, lat]})
    return (uid, source, obs_time, json.dumps(properties), geom_geojson)

async def upsert_batch(conn: asyncpg.Connection, records: List[Tuple]):
    if not records:
        return
    # chunk to avoid very large executemany calls
    for i in range(0, len(records), BATCH_SIZE):
        chunk = records[i:i+BATCH_SIZE]
        try:
            await conn.executemany(UPSERT_SQL, chunk)
        except Exception as e:
            print(f"upsert error: {e}")

async def process_source_payload(source_url: str, payload) -> List[Tuple]:
    # convert payload into list of normalized tuples for upsert
    recs = []
    if payload is None:
        return recs
    # If it's a FeatureCollection
    if isinstance(payload, dict) and payload.get('type') == 'FeatureCollection':
        for feat in payload.get('features', []) or []:
            out = extract_geometry_and_props(feat)
            if out:
                rec = normalize_record(source_url, *out)
                if rec: recs.append(rec)
        return recs
    # If the payload has a top-level 'features' key that's a list
    if isinstance(payload, dict) and 'features' in payload and isinstance(payload['features'], list):
        for feat in payload['features']:
            out = extract_geometry_and_props(feat)
            if out:
                rec = normalize_record(source_url, *out)
                if rec: recs.append(rec)
        return recs
    # If it's a list of dicts
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            out = extract_geometry_and_props(item)
            if out:
                rec = normalize_record(source_url, *out)
                if rec: recs.append(rec)
        return recs
    # If single dict with lat/lon
    if isinstance(payload, dict):
        out = extract_geometry_and_props(payload)
        if out:
            rec = normalize_record(source_url, *out)
            if rec: recs.append(rec)
    return recs

async def etl_loop(db_dsn: str, source_urls: List[str]):
    if not db_dsn:
        raise RuntimeError("DATABASE_URL must be set in environment")
    if not source_urls:
        print("No source URLs provided. Set SOURCE_URLS in code or SOURCE_URLS_JSON env var.")

    pool = await asyncpg.create_pool(db_dsn, min_size=1, max_size=5)
    async with aiohttp.ClientSession() as session:
        try:
            while True:
                tasks = [fetch_json(session, url) for url in source_urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                all_recs = []
                for url, payload in zip(source_urls, results):
                    if isinstance(payload, Exception) or payload is None:
                        continue
                    recs = await process_source_payload(url, payload)
                    # tag source by a short name
                    tagged = []
                    for r in recs:
                        # r is (uid, source, obs_time, properties_json, geom_geojson)
                        uid, _, obs_time, props_json, geom_json = r
                        tagged.append((uid, url, obs_time, props_json, geom_json))
                    all_recs.extend(tagged)

                if all_recs:
                    async with pool.acquire() as conn:
                        await upsert_batch(conn, all_recs)
                        print(f"Upserted {len(all_recs)} records")
                await asyncio.sleep(SLEEP_SECONDS)
        except asyncio.CancelledError:
            pass
        finally:
            await pool.close()


if __name__ == '__main__':
    import signal
    import sys

    # If the environment variable SOURCE_URLS_JSON isn't set, the script will not fetch anything.
    # For quick testing, you can edit SOURCE_URLS above or set env var SOURCE_URLS_JSON

    loop = asyncio.get_event_loop()
    main_task = loop.create_task(etl_loop(DATABASE_URL, SOURCE_URLS))

    def _shutdown(sig, frame):
        print("Shutting down ETL...")
        main_task.cancel()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"ETL fatal error: {e}")
    finally:
        loop.close()
