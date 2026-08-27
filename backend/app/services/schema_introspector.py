"""
Schema Introspector — reads information_schema from the client's Postgres DB.

Per PRD §4.3 step 2 and §11 schema_maps table:
- Reads tables, columns, types, PKs, FKs, nullability, indexes
- Samples distinct values for low-cardinality columns (status/enum-like)
- Returns a structured SchemaMap ready for ChromaDB embedding
"""
import asyncpg
import json
from typing import Optional
from app.models.schema import ColumnInfo, TableInfo, SchemaMap


MAX_CARDINALITY_THRESHOLD = 20  # columns with <=20 distinct values get sampled
SAMPLE_LIMIT = 20               # max distinct values to fetch per column


async def introspect_schema(pool: asyncpg.Pool, workspace_id: str) -> SchemaMap:
    """Introspect a client database and return a full SchemaMap."""
    async with pool.acquire() as conn:
        tables = await _get_tables(conn)
        table_infos = []

        for table_name in tables:
            columns = await _get_columns(conn, table_name)
            foreign_keys = await _get_foreign_keys(conn, table_name)
            row_count = await _get_row_count(conn, table_name)

            # Sample distinct values for low-cardinality columns
            for col in columns:
                if col.data_type in ("text", "varchar", "character varying", "char", "character", "enum"):
                    distinct_count = await _get_distinct_count(conn, table_name, col.name)
                    if distinct_count <= MAX_CARDINALITY_THRESHOLD:
                        col.sample_values = await _sample_distinct_values(
                            conn, table_name, col.name
                        )

            table_infos.append(TableInfo(
                name=table_name,
                columns=columns,
                row_count=row_count,
                foreign_keys=foreign_keys,
            ))

        return SchemaMap(workspace_id=workspace_id, tables=table_infos)


async def _get_tables(conn: asyncpg.Connection) -> list[str]:
    """Get all user tables, excluding system schemas."""
    rows = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    return [r["table_name"] for r in rows]


async def _get_columns(conn: asyncpg.Connection, table_name: str) -> list[ColumnInfo]:
    """Get all columns for a table with type info, nullability, and key info."""
    rows = await conn.fetch("""
        SELECT
            c.column_name,
            c.data_type,
            c.is_nullable,
            CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key,
            CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END AS is_foreign_key,
            fk.foreign_table AS references_table,
            fk.foreign_column AS references_column,
            col_description(
                (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass,
                c.ordinal_position
            ) AS column_comment
        FROM information_schema.columns c
        LEFT JOIN (
            SELECT ku.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
                AND tc.table_schema = ku.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = $1
              AND tc.table_schema = 'public'
        ) pk ON pk.column_name = c.column_name
        LEFT JOIN (
            SELECT
                ku.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
                AND tc.table_schema = ku.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = $1
              AND tc.table_schema = 'public'
        ) fk ON fk.column_name = c.column_name
        WHERE c.table_name = $1
          AND c.table_schema = 'public'
        ORDER BY c.ordinal_position
    """, table_name)

    return [
        ColumnInfo(
            name=r["column_name"],
            data_type=r["data_type"],
            is_nullable=r["is_nullable"] == "YES",
            is_primary_key=r["is_primary_key"],
            is_foreign_key=r["is_foreign_key"],
            references_table=r["references_table"],
            references_column=r["references_column"],
            column_comment=r["column_comment"],
        )
        for r in rows
    ]


async def _get_foreign_keys(conn: asyncpg.Connection, table_name: str) -> list[dict]:
    """Get all foreign key relationships for a table."""
    rows = await conn.fetch("""
        SELECT
            ku.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage ku
            ON tc.constraint_name = ku.constraint_name
            AND tc.table_schema = ku.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = $1
          AND tc.table_schema = 'public'
    """, table_name)

    return [
        {
            "column": r["column_name"],
            "references_table": r["foreign_table"],
            "references_column": r["foreign_column"],
        }
        for r in rows
    ]


async def _get_row_count(conn: asyncpg.Connection, table_name: str) -> int:
    """Get approximate row count (fast, uses pg_stat)."""
    try:
        count = await conn.fetchval(f"""
            SELECT reltuples::bigint
            FROM pg_class
            WHERE relname = $1
        """, table_name)
        return max(count or 0, 0)
    except Exception:
        return 0


async def _get_distinct_count(conn: asyncpg.Connection, table_name: str, column_name: str) -> int:
    """Get the count of distinct values for a column."""
    try:
        count = await conn.fetchval(
            f'SELECT COUNT(DISTINCT "{column_name}") FROM "{table_name}"'
        )
        return count or 0
    except Exception:
        return 0


async def _sample_distinct_values(
    conn: asyncpg.Connection, table_name: str, column_name: str
) -> list[str]:
    """Sample distinct values from a low-cardinality column."""
    try:
        rows = await conn.fetch(
            f'SELECT DISTINCT "{column_name}"::text FROM "{table_name}" LIMIT $1',
            SAMPLE_LIMIT
        )
        return [r[0] for r in rows if r[0] is not None]
    except Exception:
        return []
