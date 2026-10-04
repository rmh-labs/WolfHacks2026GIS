import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# Tiger Cloud PostGIS Connection String
DB_URL = os.getenv(
    "TIGER_CLOUD_URL",
    "postgresql://tsdbadmin:nddk8ftawo1cqq2f@mmsuny0be8.rlx5eobeob.tsdb.cloud.timescale.com:37279/tsdb?sslmode=require"
)

def get_db_engine():
    """Returns a SQLAlchemy engine connected to Tiger Cloud."""
    try:
        engine = create_engine(DB_URL, pool_pre_ping=True)
        return engine
    except Exception as e:
        print(f"Failed to create database engine: {e}")
        raise e