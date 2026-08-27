import asyncpg
from app.core.config import get_settings
from contextlib import asynccontextmanager


async def get_zenai_pool() -> asyncpg.Pool:
    settings = get_settings()
    return await asyncpg.create_pool(settings.zenai_database_url, min_size=2, max_size=10)


async def get_target_pool() -> asyncpg.Pool:
    settings = get_settings()
    return await asyncpg.create_pool(settings.target_database_url, min_size=1, max_size=5)


async def test_connection(database_url: str) -> bool:
    try:
        conn = await asyncpg.connect(database_url)
        await conn.fetchval("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False
