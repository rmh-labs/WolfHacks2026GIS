"""
Simple Flask API to serve observations as GeoJSON from PostGIS.
Configure DATABASE_URL environment variable (Postgres DSN).
Run: FLASK_APP=api/app.py flask run --host=0.0.0.0 --port=5000
"""
from flask import Flask, request, jsonify
import os
import psycopg2
import psycopg2.extras

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('Set DATABASE_URL environment variable')

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/features')
def features():
    """Return GeoJSON FeatureCollection for points near a given lon/lat.
    Query params: lon, lat, radius (meters), limit
    """
    try:
        lon = float(request.args.get('lon', '0'))
        lat = float(request.args.get('lat', '0'))
        radius = float(request.args.get('radius', '10000'))
        limit = int(request.args.get('limit', '1000'))
    except Exception:
        return jsonify({'error': 'invalid numeric parameters'}), 400

    sql = """
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
        WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
        ORDER BY obs_time DESC NULLS LAST
        LIMIT %s
      ) row
    ) feature;
    """

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(sql, (lon, lat, radius, limit))
        res = cur.fetchone()[0]
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
