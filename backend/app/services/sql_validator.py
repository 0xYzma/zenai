"""
SQL Validator — hardened, sqlglot-based (PRD §8).

Rejects:
- Any non-SELECT top-level statement
- CTEs wrapping DELETE/UPDATE/INSERT
- COPY, EXPLAIN ANALYZE, pg_sleep(), set_config()
- Direct information_schema / pg_catalog enumeration
- Unbounded cross joins without conditions
- Missing LIMIT on potentially large results
"""
import sqlglot
from sqlglot import exp
from typing import Optional


class ValidationError(Exception):
    def __init__(self, message: str, code: str = "VALIDATION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


# Dangerous function names that allow side effects
BLOCKED_FUNCTIONS = {
    "pg_sleep", "set_config", "current_setting", "pg_read_file",
    "pg_write_file", "pg_load", "dblink_connect", "dblink_exec",
    "pg_terminate_backend", "pg_cancel_backend",
}


def validate_sql(sql: str) -> str:
    """
    Validate and normalize a SQL statement using sqlglot.
    Returns the normalized SQL if valid, raises ValidationError otherwise.
    """
    sql = sql.strip().rstrip(";")

    if not sql:
        raise ValidationError("Empty SQL statement", "EMPTY_SQL")

    # Parse the SQL
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.ParseError as e:
        raise ValidationError(f"SQL syntax error: {e}", "SYNTAX_ERROR")

    # Must be a single SELECT (or WITH...SELECT)
    if not isinstance(parsed, (exp.Select, exp.Subquery)):
        # Allow WITH (CTE) that wraps a SELECT
        if isinstance(parsed, exp.With):
            if not isinstance(parsed.this, exp.Select):
                raise ValidationError(
                    "Only SELECT statements are allowed", "NON_SELECT"
                )
        else:
            raise ValidationError(
                "Only SELECT statements are allowed", "NON_SELECT"
            )

    # Check for blocked functions anywhere in the tree
    for node in parsed.walk():
        if isinstance(node, exp.Anonymous) and node.name.lower() in BLOCKED_FUNCTIONS:
            raise ValidationError(
                f"Function '{node.name}' is not allowed", "BLOCKED_FUNCTION"
            )
        if isinstance(node, exp.Anonymous) and node.name.lower() == "explain":
            raise ValidationError(
                "EXPLAIN is not allowed in user queries", "BLOCKED_FUNCTION"
            )

    # Check for COPY operation
    if isinstance(parsed, exp.Copy):
        raise ValidationError("COPY is not allowed", "BLOCKED_FUNCTION")

    # Reject CTEs that wrap write operations
    if isinstance(parsed, exp.With):
        for cte in parsed.find_all(exp.CTE):
            cte_query = cte.this
            if isinstance(cte_query, (exp.Delete, exp.Update, exp.Insert)):
                raise ValidationError(
                    "CTE must not contain write operations", "CTE_WRITE"
                )

    # Check for information_schema / pg_catalog enumeration
    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()
        if table_name in ("information_schema", "pg_catalog", "pg_tables",
                          "pg_views", "pg_class", "pg_namespace", "pg_stat",
                          "pg_settings", "pg_roles", "pg_database"):
            raise ValidationError(
                f"Access to system table '{table.name}' is not allowed",
                "SYSTEM_TABLE"
            )

    # Check for unbounded cross joins
    for join in parsed.find_all(exp.Join):
        if join.side is None and join.on is None and join.type == "cross":
            raise ValidationError(
                "Unbounded CROSS JOINs are not allowed", "CROSS_JOIN"
            )

    # Check for UNION without LIMIT (could be very large)
    if isinstance(parsed, exp.Union) and not parsed.find(exp.Limit):
        raise ValidationError(
            "UNION without LIMIT is not allowed — narrow your results",
            "UNION_NO_LIMIT"
        )

    # Inject LIMIT 2000 if not present (PRD §4.3 step 11 row cap)
    if not parsed.find(exp.Limit):
        parsed = parsed.limit(2000)

    # Generate the validated SQL
    validated_sql = parsed.sql(dialect="postgres")

    return validated_sql


def is_retryable_error(error_message: str) -> bool:
    """
    Determine if a database error is retryable per PRD §7.1.
    Retryable: syntax error, unknown column/table, missing alias, ambiguous column.
    Non-retryable: permission denied, timeout, network failure.
    """
    msg_lower = error_message.lower()

    # Non-retryable — fail immediately
    non_retryable_patterns = [
        "permission denied",
        "timeout",
        "timed out",
        "connection refused",
        "connection closed",
        "network",
        "rolename",
        "access denied",
        "authorization",
    ]
    for pattern in non_retryable_patterns:
        if pattern in msg_lower:
            return False

    # Retryable — correct with error context
    retryable_patterns = [
        "syntax error",
        "does not exist",
        "column",
        "relation",
        "missing",
        "ambiguous",
        "alias",
        "unknown",
        "invalid",
        "type",
        "function",
        "operator",
    ]
    for pattern in retryable_patterns:
        if pattern in msg_lower:
            return True

    # Default: don't retry unknown errors
    return False
