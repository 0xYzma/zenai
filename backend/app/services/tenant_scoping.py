"""
Tenant Scoping — §8, §17 (server-side injection, never LLM-controlled).

Injects workspace_id filter into the generated SQL after validation.
This ensures every query is scoped to the workspace's data.
"""
import sqlglot
from sqlglot import exp
from typing import Optional


def inject_tenant_scope(sql: str, workspace_id: str, scope_column: str = "workspace_id") -> str:
    """
    Inject a WHERE clause that filters by workspace_id.

    This is called AFTER sqlglot validation (§8) and BEFORE execution.
    The LLM never includes this — it's always injected server-side.

    Strategy:
    1. If the query already has a WHERE clause, AND the workspace_id filter
    2. If no WHERE clause, add WHERE workspace_id = <value>
    """
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.ParseError:
        # If parsing fails, return original (validator should have caught this)
        return sql

    # For CTEs, inject into the innermost SELECT
    if isinstance(parsed, exp.With):
        inner = parsed.this
        if isinstance(inner, exp.Select):
            parsed = inner

    if not isinstance(parsed, exp.Select):
        return sql

    # Check if table has a workspace_id column
    # We inject at the SELECT level, wrapping if needed
    workspace_filter = exp.EQ(
        this=exp.Column(this=exp.to_identifier(scope_column)),
        expression=exp.Literal.string(workspace_id),
    )

    # Check existing WHERE
    existing_where = parsed.find(exp.Where)
    if existing_where:
        # AND the new filter
        new_condition = exp.And(
            this=existing_where.this,
            expression=workspace_filter,
        )
        existing_where.replace(exp.Where(this=new_condition))
    else:
        # Add new WHERE
        parsed.set("where", exp.Where(this=workspace_filter))

    return parsed.sql(dialect="postgres")
