"""
Data Access Layer — replaces all in-memory dicts with real Postgres queries.

Every function uses parameterized queries (asyncpg) to prevent SQL injection.
All queries are scoped to workspace_id where applicable (§8 tenant scoping).
"""
import asyncpg
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.core.config import get_settings

async def get_zenai_conn() -> asyncpg.Connection:
    """Get a connection to ZenAI's own database."""
    return await asyncpg.connect(get_settings().zenai_database_url)


# ── Users ──────────────────────────────────────────────────────────────

async def create_user(email: str, password_hash: str) -> dict:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            """INSERT INTO users (id, email, password_hash)
               VALUES ($1, $2, $3)
               RETURNING id::text, email, created_at""",
            uuid.uuid4(), email.lower(), password_hash,
        )
        return dict(row)
    finally:
        await conn.close()


async def get_user_by_email(email: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id::text, email, password_hash, created_at FROM users WHERE email = $1",
            email.lower(),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id::text, email, created_at FROM users WHERE id = $1",
            uuid.UUID(user_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


# ── Workspaces ─────────────────────────────────────────────────────────

async def create_workspace(name: str, owner_id: str) -> dict:
    conn = await get_zenai_conn()
    try:
        ws_id = str(uuid.uuid4())
        row = await conn.fetchrow(
            """INSERT INTO workspaces (id, name, owner_id)
               VALUES ($1, $2, $3)
               RETURNING id::text, name, owner_id::text, schema_version, created_at""",
            uuid.UUID(ws_id), name, uuid.UUID(owner_id),
        )
        # Auto-add owner as member
        await conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, user_id, role)
               VALUES ($1, $2, $3, 'owner')""",
            uuid.uuid4(), uuid.UUID(ws_id), uuid.UUID(owner_id),
        )
        return dict(row)
    finally:
        await conn.close()


async def list_workspaces_for_user(user_id: str) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            """SELECT w.id::text, w.name, w.owner_id::text, w.schema_version, w.created_at, wm.role
               FROM workspaces w
               JOIN workspace_members wm ON wm.workspace_id = w.id
               WHERE wm.user_id = $1
               ORDER BY w.created_at DESC""",
            uuid.UUID(user_id),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_workspace(workspace_id: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id::text, name, owner_id::text, schema_version, timezone, created_at FROM workspaces WHERE id = $1",
            uuid.UUID(workspace_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def update_workspace_timezone(workspace_id: str, tz: str):
    conn = await get_zenai_conn()
    try:
        await conn.execute("UPDATE workspaces SET timezone = $1 WHERE id = $2", tz, uuid.UUID(workspace_id))
    finally:
        await conn.close()


async def delete_workspace(workspace_id: str) -> bool:
    """Delete a workspace and all its cascade-linked rows."""
    conn = await get_zenai_conn()
    try:
        result = await conn.execute("DELETE FROM workspaces WHERE id = $1", uuid.UUID(workspace_id))
        return result == "DELETE 1"
    finally:
        await conn.close()


async def is_workspace_member(workspace_id: str, user_id: str) -> Optional[str]:
    """Check if user is a member. Returns role or None."""
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "SELECT role FROM workspace_members WHERE workspace_id = $1 AND user_id = $2",
            uuid.UUID(workspace_id), uuid.UUID(user_id),
        )
        return row["role"] if row else None
    finally:
        await conn.close()


async def add_workspace_member(workspace_id: str, email: str, role: str) -> dict:
    conn = await get_zenai_conn()
    try:
        user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email.lower())
        if not user:
            raise ValueError(f"User {email} not found")
        await conn.execute(
            """INSERT INTO workspace_members (id, workspace_id, user_id, role)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (workspace_id, user_id) DO NOTHING""",
            uuid.uuid4(), uuid.UUID(workspace_id), user["id"], role,
        )
        return {"email": email, "role": role}
    finally:
        await conn.close()


async def list_workspace_members(workspace_id: str) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            """SELECT wm.user_id::text, u.email, wm.role, wm.invited_at
               FROM workspace_members wm
               JOIN users u ON u.id = wm.user_id
               WHERE wm.workspace_id = $1""",
            uuid.UUID(workspace_id),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Connections ────────────────────────────────────────────────────────

async def save_connection(workspace_id: str, encrypted_creds: str, host: str, port: int, db_name: str, read_only_role: str = None) -> dict:
    conn = await get_zenai_conn()
    try:
        # Delete existing connection for this workspace
        await conn.execute("DELETE FROM connections WHERE workspace_id = $1", uuid.UUID(workspace_id))
        row = await conn.fetchrow(
            """INSERT INTO connections (id, workspace_id, host, port, db_name, encrypted_credentials, read_only_role, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'connected')
               RETURNING id::text, host, port, db_name, status, created_at""",
            uuid.uuid4(), uuid.UUID(workspace_id), host, port, db_name, encrypted_creds, read_only_role,
        )
        return dict(row)
    finally:
        await conn.close()


async def get_connection(workspace_id: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "SELECT id::text, workspace_id::text, host, port, db_name, encrypted_credentials, read_only_role, status FROM connections WHERE workspace_id = $1",
            uuid.UUID(workspace_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_all_connections() -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            "SELECT workspace_id::text, host, port, db_name, encrypted_credentials FROM connections"
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def delete_connection(workspace_id: str) -> bool:
    conn = await get_zenai_conn()
    try:
        result = await conn.execute("DELETE FROM connections WHERE workspace_id = $1", uuid.UUID(workspace_id))
        return result == "DELETE 1"
    finally:
        await conn.close()


async def update_connection_status(workspace_id: str, status: str):
    conn = await get_zenai_conn()
    try:
        await conn.execute("UPDATE connections SET status = $1 WHERE workspace_id = $2", status, uuid.UUID(workspace_id))
    finally:
        await conn.close()


# ── Schema Maps ────────────────────────────────────────────────────────

async def save_schema_map(workspace_id: str, tables: list) -> int:
    """Save schema map rows. Returns count of rows saved."""
    conn = await get_zenai_conn()
    try:
        await conn.execute("DELETE FROM schema_maps WHERE workspace_id = $1", uuid.UUID(workspace_id))
        count = 0
        for table in tables:
            for col in table.columns:
                await conn.execute(
                    """INSERT INTO schema_maps (id, workspace_id, table_name, column_name, data_type,
                       is_nullable, is_primary_key, is_foreign_key, references_table, references_column,
                       sample_values, column_comment, last_synced_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())""",
                    uuid.uuid4(), uuid.UUID(workspace_id), table.name, col.name, col.data_type,
                    col.is_nullable, col.is_primary_key, col.is_foreign_key,
                    col.references_table, col.references_column,
                    json.dumps(col.sample_values) if col.sample_values else None, col.column_comment,
                )
                count += 1
        return count
    finally:
        await conn.close()


async def get_schema_map(workspace_id: str) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM schema_maps WHERE workspace_id = $1 ORDER BY table_name, column_name",
            uuid.UUID(workspace_id),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def increment_schema_version(workspace_id: str) -> int:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            "UPDATE workspaces SET schema_version = schema_version + 1 WHERE id = $1 RETURNING schema_version",
            uuid.UUID(workspace_id),
        )
        return row["schema_version"] if row else 1
    finally:
        await conn.close()


# ── Chat Sessions ──────────────────────────────────────────────────────

async def get_or_create_session(workspace_id: str, session_id: str, user_id: str) -> dict:
    conn = await get_zenai_conn()
    try:
        # Check if session exists and hasn't expired
        row = await conn.fetchrow(
            """SELECT id::text, summary, created_at, expires_at
               FROM chat_sessions WHERE id = $1 AND workspace_id = $2""",
            uuid.UUID(session_id), uuid.UUID(workspace_id),
        )

        if row and row["expires_at"] and row["expires_at"] > datetime.now(timezone.utc):
            return dict(row)

        # Create new session
        # Create new session - asyncpg expects naive datetimes
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
        new_row = await conn.fetchrow(
            """INSERT INTO chat_sessions (id, workspace_id, user_id, summary, expires_at)
               VALUES ($1, $2, $3, '', $4)
               ON CONFLICT (id) DO UPDATE SET summary = '', expires_at = $4
               RETURNING id::text, summary, created_at, expires_at""",
            uuid.UUID(session_id), uuid.UUID(workspace_id), uuid.UUID(user_id), expires,
        )
        return dict(new_row)
    finally:
        await conn.close()


async def update_session_summary(session_id: str, summary: str):
    conn = await get_zenai_conn()
    try:
        await conn.execute(
            "UPDATE chat_sessions SET summary = $1 WHERE id = $2",
            summary, uuid.UUID(session_id),
        )
    finally:
        await conn.close()


async def get_recent_turns(session_id: str, limit: int = 2) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            """SELECT content, generated_sql, result_summary
               FROM chat_messages
               WHERE session_id = $1 AND role = 'assistant'
               ORDER BY created_at DESC LIMIT $2""",
            uuid.UUID(session_id), limit,
        )
        return [dict(r) for r in reversed(rows)]
    finally:
        await conn.close()


# ── Chat Messages ──────────────────────────────────────────────────────

async def save_chat_message(session_id: str, role: str, content: str,
                            generated_sql: str = None, result_summary: dict = None,
                            chart_type: str = None, chart_data: list = None,
                            confidence: str = None) -> str:
    conn = await get_zenai_conn()
    try:
        msg_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO chat_messages (id, session_id, role, content, generated_sql,
               result_summary, chart_type, chart_data, confidence)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            uuid.UUID(msg_id), uuid.UUID(session_id), role, content,
            generated_sql, json.dumps(result_summary) if result_summary else None,
            chart_type, json.dumps(chart_data) if chart_data else None, confidence,
        )
        return msg_id
    finally:
        await conn.close()


async def get_chat_history(session_id: str) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            """SELECT id::text, role, content, generated_sql, chart_type, chart_data, confidence, created_at
               FROM chat_messages WHERE session_id = $1 ORDER BY created_at""",
            uuid.UUID(session_id),
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_chat_message(message_id: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            """SELECT id::text, session_id::text, role, content, generated_sql, created_at
               FROM chat_messages WHERE id = $1""",
            uuid.UUID(message_id),
        )
        return dict(row) if row else None
    finally:
        await conn.close()


# ── Query Logs ─────────────────────────────────────────────────────────

async def save_query_log(workspace_id: str, sql_text: str, row_count: int,
                         execution_ms: int, estimated_cost: float, status: str):
    conn = await get_zenai_conn()
    try:
        await conn.execute(
            """INSERT INTO query_logs (id, workspace_id, sql_text, row_count, execution_ms, estimated_cost, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            uuid.uuid4(), uuid.UUID(workspace_id), sql_text,
            row_count, execution_ms, estimated_cost, status,
        )
    finally:
        await conn.close()


async def get_query_logs(workspace_id: str, limit: int = 50) -> list[dict]:
    conn = await get_zenai_conn()
    try:
        rows = await conn.fetch(
            """SELECT id::text, sql_text, row_count, execution_ms, estimated_cost, status, created_at
               FROM query_logs WHERE workspace_id = $1 ORDER BY created_at DESC LIMIT $2""",
            uuid.UUID(workspace_id), limit,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Query Cache (§9) ───────────────────────────────────────────────────

async def get_cached_answer(workspace_id: str, cache_key: str) -> Optional[dict]:
    conn = await get_zenai_conn()
    try:
        row = await conn.fetchrow(
            """SELECT answer FROM query_cache
               WHERE workspace_id = $1 AND cache_key = $2 AND expires_at > NOW()""",
            uuid.UUID(workspace_id), cache_key,
        )
        if row and row["answer"]:
            return json.loads(row["answer"])
        return None
    finally:
        await conn.close()


async def set_cached_answer(workspace_id: str, cache_key: str, answer: dict, ttl_minutes: int = 30):
    conn = await get_zenai_conn()
    try:
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=ttl_minutes)
        await conn.execute(
            """INSERT INTO query_cache (id, workspace_id, cache_key, answer, expires_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (workspace_id, cache_key)
               DO UPDATE SET answer = $4, expires_at = $5, created_at = NOW()""",
            uuid.uuid4(), uuid.UUID(workspace_id), cache_key, json.dumps(answer), expires,
        )
    finally:
        await conn.close()


# ── Feedback ───────────────────────────────────────────────────────────

async def save_feedback(message_id: str, rating: str, comment: str = None) -> str:
    conn = await get_zenai_conn()
    try:
        fb_id = str(uuid.uuid4())
        await conn.execute(
            """INSERT INTO feedback (id, message_id, rating, comment)
               VALUES ($1, $2, $3, $4)""",
            uuid.UUID(fb_id), uuid.UUID(message_id), rating, comment,
        )
        return fb_id
    finally:
        await conn.close()


# ── Prompt Versions (§10.5) ────────────────────────────────────────────

async def save_prompt_version(prompt_type: str, version: str, template: str):
    conn = await get_zenai_conn()
    try:
        await conn.execute(
            """INSERT INTO prompt_versions (id, prompt_type, version, template)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (prompt_type, version) DO UPDATE SET template = $4""",
            uuid.uuid4(), prompt_type, version, template,
        )
    finally:
        await conn.close()
