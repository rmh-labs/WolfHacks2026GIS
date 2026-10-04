"""
Flask API with CORS enabled to serve observations as GeoJSON from PostGIS.
This file is an improved version of api/app.py that allows cross-origin requests
from static sites (e.g., your GoDaddy-hosted HTML).

Endpoints:
- GET /features  -> GeoJSON FeatureCollection (query by lon/lat+radius OR bbox)
- GET /feature/<id> -> single Feature by id

Configure DATABASE_URL environment variable and run as:
  FLASK_APP=api/app_cors.py flask run --host=0.0.0.0 --port=5000

Notes:
- Install flask-cors (pip install flask-cors) or add to your requirements.
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('Set DATABASE_URL environment variable')

app = Flask(__name__)
# Allow cross-origin requests from any origin (adjust in production)
CORS(app, resources={r"/*": {"origins": "*"}})


def get_conn():
    return psycopg2.connect(DATABASE_URL)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/features')
def features():
    """Return GeoJSON FeatureCollection.
    Query options (choose one):
      - lon, lat, radius (meters)
      - bbox = minLon,minLat,maxLon,maxLat
    Optional: source, start_time, end_time, limit
    """
    # Parse params
    lon = request.args.get('lon')
    lat = request.args.get('lat')
    radius = request.args.get('radius')
    bbox = request.args.get('bbox')
    source = request.args.get('source')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    limit = int(request.args.get('limit', '1000'))

    # Build SQL
    where_clauses = []
    params = []

    if bbox:
        try:
            minx, miny, maxx, maxy = [float(x) for x in bbox.split(',')]
            where_clauses.append("geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)")
            params.extend([minx, miny, maxx, maxy])
        except Exception:
            return jsonify({'error': 'invalid bbox format'}), 400
    elif lon and lat and radius:
        try:
            lonf = float(lon); latf = float(lat); r = float(radius)
            where_clauses.append("ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s),4326)::geography, %s)")
            params.extend([lonf, latf, r])
        except Exception:
            return jsonify({'error': 'invalid lon/lat/radius'}), 400
    else:
        # No spatial filter provided — restrict in production
        pass

    if source:
        where_clauses.append("source = %s")
        params.append(source)
    if start_time:
        where_clauses.append("obs_time >= %s")
        params.append(start_time)
    if end_time:
        where_clauses.append("obs_time <= %s")
        params.append(end_time)

    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    sql = f"""
    SELECT json_build_object(
      'type', 'FeatureCollection',
      'features', COALESCE(json_agg(feature), '[]'::json)
    ) FROM (
      SELECT json_build_object(
        'type','Feature',
        'geometry', ST_AsGeoJSON(geom)::json,
        'properties', to_jsonb(row) - 'geom'
      ) AS feature
      FROM (
        SELECT id, source, obs_time, properties, geom
        FROM observations
        {where_sql}
        ORDER BY obs_time DESC NULLS LAST
        LIMIT %s
      ) row
    ) feature;
    """

    params.append(limit)

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        res = cur.fetchone()[0]
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/feature/<feature_id>')
def get_feature(feature_id):
    sql = """
    SELECT json_build_object(
      'type','Feature',
      'geometry', ST_AsGeoJSON(geom)::json,
      'properties', to_jsonb(row) - 'geom'
    ) FROM (
      SELECT id, source, obs_time, properties, geom
      FROM observations
      WHERE id = %s
      LIMIT 1
    ) row;
    """
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql, (feature_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            return jsonify({'error': 'not found'}), 404
        return jsonify(row[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
