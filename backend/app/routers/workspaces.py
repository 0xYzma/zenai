"""
Workspace & Connection routes — §5.2, §5.3

POST /workspaces/{id}/connect — save + test client DB connection (credentials encrypted)
POST /workspaces/{id}/introspect — trigger schema introspection + embedding
GET  /workspaces/{id}/schema — view schema map
DELETE /workspaces/{id}/connection — remove connection
GET  /workspaces/{id}/search — debug schema retrieval
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.schemas.api import (
    ConnectionCreate, ConnectionTestResponse,
    IntrospectRequest, IntrospectResponse,
    SchemaResponse, SchemaTableResponse,
)
from app.services.schema_introspector import introspect_schema
from app.services.schema_embedder import embed_schema, delete_workspace_embeddings, retrieve_relevant_tables
from app.services.encryption import encrypt_credentials, decrypt_credentials, build_asyncpg_url, build_sync_url
from app.services.auth import verify_token
from app.db import data_access as db
from app.core.logger import logger
import asyncpg
from app.models.schema import ColumnInfo, TableInfo, SchemaMap

router = APIRouter()

# Pool cache (runtime only — connections rebuilt on startup)
_pools: dict[str, asyncpg.Pool] = {}


def _get_user_id(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@router.post("/{workspace_id}/connect", response_model=ConnectionTestResponse)
async def connect_database(workspace_id: str, conn_info: ConnectionCreate, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    # Encrypt credentials (§17)
    encrypted_creds = encrypt_credentials(
        conn_info.host, conn_info.port, conn_info.db_name,
        conn_info.username, conn_info.password,
    )

    # Test connection with sync URL
    sync_url = build_sync_url({
        "host": conn_info.host, "port": conn_info.port,
        "db_name": conn_info.db_name, "username": conn_info.username,
        "password": conn_info.password,
    })
    try:
        import psycopg2
        conn = psycopg2.connect(sync_url)
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect: {e}")

    # Create pool
    async_url = build_asyncpg_url({
        "host": conn_info.host, "port": conn_info.port,
        "db_name": conn_info.db_name, "username": conn_info.username,
        "password": conn_info.password,
    })
    pool = await asyncpg.create_pool(async_url, min_size=1, max_size=5)
    _pools[workspace_id] = pool

    # Save to real DB
    await db.save_connection(workspace_id, encrypted_creds, conn_info.host, conn_info.port, conn_info.db_name)

    # Fetch tables and column counts
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.table_name, count(c.column_name) as column_count
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
            GROUP BY t.table_name
            ORDER BY t.table_name
        """)
        table_count = len(rows)
        tables = [{"name": r["table_name"], "column_count": r["column_count"]} for r in rows]

    logger.query_executed(workspace_id, "SELECT tables (connection test)", 1, 0, 0, "success")
    return ConnectionTestResponse(
        connected=True,
        message=f"Connected successfully. Found {table_count} tables.",
        table_count=table_count,
        tables=tables,
    )


@router.post("/{workspace_id}/introspect", response_model=IntrospectResponse)
async def trigger_introspect(workspace_id: str, req: IntrospectRequest = IntrospectRequest(),
                             authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    pool = _pools.get(workspace_id)
    if not pool:
        conn = await db.get_connection(workspace_id)
        if not conn:
            raise HTTPException(status_code=400, detail="No connection. Connect first.")
        creds = decrypt_credentials(conn["encrypted_credentials"])
        pool = await asyncpg.create_pool(build_asyncpg_url(creds), min_size=1, max_size=5)
        _pools[workspace_id] = pool

    schema_map = await introspect_schema(pool, workspace_id)
    if req.tables:
        schema_map.tables = [t for t in schema_map.tables if t.name in req.tables]

    chunks_embedded = embed_schema(schema_map)
    total_columns = sum(len(t.columns) for t in schema_map.tables)

    # Save to real DB
    await db.save_schema_map(workspace_id, schema_map.tables)
    new_version = await db.increment_schema_version(workspace_id)

    return IntrospectResponse(
        workspace_id=workspace_id,
        tables_embedded=chunks_embedded,
        total_columns=total_columns,
        version=new_version,
        status="embedded",
    )


@router.get("/{workspace_id}/schema", response_model=SchemaResponse)
async def get_schema(workspace_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    rows = await db.get_schema_map(workspace_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No schema found. Run introspection first.")

    # Group by table_name
    tables_dict: dict[str, dict] = {}
    for r in rows:
        tname = r["table_name"]
        if tname not in tables_dict:
            tables_dict[tname] = {"name": tname, "columns": [], "row_count": 0, "foreign_keys": []}
        tables_dict[tname]["columns"].append({
            "name": r["column_name"],
            "data_type": r["data_type"],
            "is_nullable": r["is_nullable"],
            "is_primary_key": r["is_primary_key"],
            "is_foreign_key": r["is_foreign_key"],
            "references_table": r["references_table"],
            "references_column": r["references_column"],
            "sample_values": r.get("sample_values", []),
            "column_comment": r["column_comment"],
        })

    ws = await db.get_workspace(workspace_id)
    return SchemaResponse(
        workspace_id=workspace_id,
        version=ws["schema_version"] if ws else 1,
        tables=[SchemaTableResponse(**t) for t in tables_dict.values()],
    )


@router.delete("/{workspace_id}/connection")
async def delete_connection(workspace_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    pool = _pools.pop(workspace_id, None)
    if pool:
        await pool.close()
    delete_workspace_embeddings(workspace_id)
    await db.delete_connection(workspace_id)
    return {"status": "deleted"}


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only the workspace owner can delete it")

    # Close connection pool if exists
    pool = _pools.pop(workspace_id, None)
    if pool:
        await pool.close()

    # Delete embeddings
    delete_workspace_embeddings(workspace_id)

    # Delete from database (cascades to members, connections, schema_maps, etc.)
    deleted = await db.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return {"status": "deleted"}


@router.get("/{workspace_id}/search")
async def search_schema(workspace_id: str, q: str, top_k: int = 5):
    results = retrieve_relevant_tables(workspace_id, q, top_k=top_k, threshold=0.0)
    return {"query": q, "results": results}
