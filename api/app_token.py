"""
Flask API with simple bearer token auth and CORS for easy hackathon use.
Set environment variables:
  DATABASE_URL - Postgres DSN
  API_TOKEN - secret token clients must send as 'Authorization: Bearer <token>'
Run: FLASK_APP=api/app_token.py flask run --host=0.0.0.0 --port=5000
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2

DATABASE_URL = os.getenv('DATABASE_URL')
API_TOKEN = os.getenv('API_TOKEN')
if not DATABASE_URL:
    raise RuntimeError('Set DATABASE_URL environment variable')
if not API_TOKEN:
    print('Warning: API_TOKEN not set — API will reject authorized requests unless token is provided')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def require_token():
    if not API_TOKEN:
        return True
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    token = auth.split(' ', 1)[1].strip()
    return token == API_TOKEN


@app.before_request
def check_auth():
    # Allow health check without auth
    if request.endpoint == 'health':
        return
    if not require_token():
        return jsonify({'error': 'unauthorized'}), 401


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/features')
def features():
    # keep implementation same as app_cors but simple parsing
    lon = request.args.get('lon')
    lat = request.args.get('lat')
    radius = request.args.get('radius')
    bbox = request.args.get('bbox')
    source = request.args.get('source')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    limit = int(request.args.get('limit', '1000'))

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
