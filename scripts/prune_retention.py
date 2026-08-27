"""
Retention cleanup for ZenAI integrated mode.

Deletes conversation data and SaaS audit rows past their configured
retention windows in bounded batches so that large tables do not lock.

Run daily via a scheduled job:
    python -m scripts.prune_retention

Environment must have ZENAI_DATABASE_URL set.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def _prune_table(
    conn: asyncpg.Connection,
    table: str,
    timestamp_col: str,
    cutoff: datetime,
    label: str,
) -> int:
    """Delete rows older than cutoff in BATCH_SIZE chunks. Returns total deleted."""
    total = 0
    while True:
        result = await conn.execute(
            f"""
            DELETE FROM {table}
            WHERE {timestamp_col} < $1
              AND ctid IN (
                SELECT ctid FROM {table}
                WHERE {timestamp_col} < $1
                LIMIT {BATCH_SIZE}
              )
            """,
            cutoff,
        )
        # asyncpg returns "DELETE N"
        deleted = int(result.split()[-1])
        total += deleted
        logger.info(f"  {label}: deleted batch of {deleted} (total so far: {total})")
        if deleted < BATCH_SIZE:
            break
    return total


async def run_prune() -> None:
    settings = get_settings()

    db_url = settings.zenai_database_url
    if not db_url:
        raise RuntimeError("ZENAI_DATABASE_URL is not configured")

    # asyncpg wants postgresql:// not postgresql+asyncpg://
    pg_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )

    conv_cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.conversation_retention_days
    )

    logger.info(
        f"Starting retention prune  conv_cutoff={conv_cutoff.date()}"
    )

    conn = await asyncpg.connect(pg_url)
    try:
        # ── ZenAI conversation history ────────────────────────────────────────
        # Cascade deletes messages, feedback, and snapshots automatically.
        n = await _prune_table(
            conn,
            "integrated_conversations",
            "updated_at",
            conv_cutoff,
            "integrated_conversations",
        )
        logger.info(f"Conversations pruned: {n}")

        # ── SaaS-side tables (NOT in this database) ───────────────────────────
        # The following tables live on the SaaS database and must be pruned
        # by a separate job that has access to the SaaS database URL:
        #
        #   ai_active_requests  — expired leases (self-healing: pruned on each
        #                         reservation attempt, but also clean up via:
        #     DELETE FROM ai_active_requests WHERE expires_at <= NOW();
        #
        #   ai_action_audit     — 90-day audit log:
        #     DELETE FROM ai_action_audit
        #     WHERE created_at < NOW() - INTERVAL '90 days';
        #
        # Schedule these on the SaaS database via pg_cron or a dedicated job
        # using SAAS_DATABASE_URL — do NOT run them through this script.


    finally:
        await conn.close()

    logger.info("Retention prune complete.")


if __name__ == "__main__":
    asyncio.run(run_prune())
