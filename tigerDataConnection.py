import asyncpg
import asyncio

CONNECTION = "postgres://tsdbadmin:<TIMESCALE_DB_PASSWORD>@mmsuny0be8.rlx5eobeob.tsdb.cloud.timescale.com:37279/tsdb?sslmode=require"


async def main():
    conn = await asyncpg.connect(CONNECTION)
    extensions = await conn.fetch("select extname, extversion from pg_extension")
    for extension in extensions:
        print(extension)
    await conn.close()

asyncio.run(main())

print("Connection successful!")