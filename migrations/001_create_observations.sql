-- Enable PostGIS (requires superuser in some hosting environments)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS observations (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  obs_time TIMESTAMPTZ,
  properties JSONB,
  geom GEOMETRY(Geometry,4326)
);

-- Spatial index
CREATE INDEX IF NOT EXISTS observations_geom_gist ON observations USING GIST (geom);

-- Time index
CREATE INDEX IF NOT EXISTS observations_time_idx ON observations (obs_time);

-- Optional: keep a smaller index for source + time queries
CREATE INDEX IF NOT EXISTS observations_source_time_idx ON observations (source, obs_time);
