"""
Scheduler for background tasks like daily schema auto-refresh (§5.3).
"""
import asyncio
import asyncpg
from app.core.logger import logger
from app.db import data_access as db
from app.services.schema_introspector import introspect_schema
from app.services.schema_embedder import embed_schema
from app.services.encryption import build_asyncpg_url, decrypt_credentials


async def run_daily_schema_refresh():
    """Iterates all workspaces with connections and re-introspects their schemas."""
    logger.logger.info("Starting daily schema auto-refresh...")
    connections = await db.get_all_connections()
    
    for conn in connections:
        workspace_id = conn["workspace_id"]
        try:
            creds = decrypt_credentials(conn["encrypted_credentials"])
            async_url = build_asyncpg_url(creds)
            pool = await asyncpg.create_pool(async_url, min_size=1, max_size=2)
            
            try:
                schema_map = await introspect_schema(pool, workspace_id)
                # Since we don't know the user's specific table selection here, 
                # we index all tables by default or we'd need to save table selections.
                # PRD says "diff-based auto-refresh". For MVP, re-index all currently saved tables.
                
                # Fetch currently saved tables to only re-index those
                existing_tables = await db.get_schema_map(workspace_id)
                saved_table_names = {t["table_name"] for t in existing_tables}
                
                if saved_table_names:
                    schema_map.tables = [t for t in schema_map.tables if t.name in saved_table_names]
                
                embed_schema(schema_map)
                await db.save_schema_map(workspace_id, schema_map.tables)
                await db.increment_schema_version(workspace_id)
                logger.logger.info(f"Schema refreshed for workspace {workspace_id}")
            finally:
                await pool.close()
                
        except Exception as e:
            logger.logger.error(f"Failed to refresh schema for workspace {workspace_id}: {e}")

    logger.logger.info("Finished daily schema auto-refresh.")


def start_schema_refresh_scheduler():
    """Starts the background task for daily schema auto-refresh."""
    async def refresh_loop():
        while True:
            # Sleep 24 hours
            await asyncio.sleep(24 * 60 * 60)
            await run_daily_schema_refresh()
            
    asyncio.create_task(refresh_loop())
