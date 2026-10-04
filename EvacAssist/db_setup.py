from sqlalchemy import text
from config import get_db_engine

def setup_tiger_cloud_database():
    """Enable PostGIS and initialize target tables and spatial indexes."""
    print("Connecting to Tiger Cloud PostGIS database...")
    engine = get_db_engine()

    with engine.connect() as conn:
        # Step 1: Enable PostGIS Extension
        print("Enabling PostGIS extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        conn.commit()

        # Step 2: Drop any existing outdated tables
        print("Resetting table structures...")
        conn.execute(text("""
            DROP TABLE IF EXISTS disaster_events CASCADE;
            DROP TABLE IF EXISTS safe_zones CASCADE;
            DROP TABLE IF EXISTS evacuation_routes CASCADE;
        """))
        conn.commit()

        # Step 3: Create full tables with spatial geometry columns
        print("Creating PostGIS schemas...")
        schema_sql = """
        -- 1. Table for active disaster hazards and alerts
        CREATE TABLE disaster_events (
            event_id VARCHAR(255) PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            severity INT CHECK (severity BETWEEN 1 AND 5),
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            title TEXT,
            area_description TEXT,
            effective_time TIMESTAMPTZ,
            expires_time TIMESTAMPTZ,
            geometry GEOMETRY(Geometry, 4326),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- 2. Table for safe zones, shelters, medical centers, and response hubs
        CREATE TABLE safe_zones (
            facility_id VARCHAR(255) PRIMARY KEY,
            name TEXT NOT NULL,
            facility_type VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'OPEN',
            capacity INT DEFAULT 0,
            address TEXT,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            geometry GEOMETRY(Point, 4326),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- 3. Table for evacuation corridors and road safety data
        CREATE TABLE evacuation_routes (
            route_id VARCHAR(255) PRIMARY KEY,
            route_name TEXT NOT NULL,
            state VARCHAR(50),
            status VARCHAR(50) DEFAULT 'ACTIVE',
            hazard_type VARCHAR(100),
            geometry GEOMETRY(Geometry, 4326),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Spatial GIST Indexes for rapid geographic queries
        CREATE INDEX idx_disaster_events_geom ON disaster_events USING GIST (geometry);
        CREATE INDEX idx_safe_zones_geom ON safe_zones USING GIST (geometry);
        CREATE INDEX idx_evacuation_routes_geom ON evacuation_routes USING GIST (geometry);
        """
        conn.execute(text(schema_sql))
        conn.commit()

    print("Tiger Cloud database successfully initialized!")

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("WARNING: Running this script will DROP ALL EXISTING TABLES")
    print("and reset your Tiger Cloud PostGIS database schema.")
    print("=" * 60)
    
    confirmation = input("\nAre you sure you want to proceed? Type 'RESET' to confirm: ")
    
    if confirmation.strip() == "RESET":
        setup_tiger_cloud_database()
    else:
        print("\nOperation cancelled. No changes were made to the database.")