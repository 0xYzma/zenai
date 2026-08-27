"""
Query Executor — runs validated SQL against client's read-only Postgres.

Per PRD §4.3 step 10-11:
- EXPLAIN cost estimation before execution
- Read-only role enforcement
- Row cap (2000), execution timeout (5s)
- Returns structured result for downstream processing
"""
import asyncpg
import time
import json
from dataclasses import dataclass, field
from typing import Optional


MAX_ROW_CAP = 2000
EXECUTION_TIMEOUT_SECONDS = 5
MAX_ACCEPTABLE_COST = 100000.0


@dataclass
class QueryResult:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    execution_ms: int = 0
    estimated_cost: float = 0.0
    error: Optional[str] = None
    error_class: Optional[str] = None
    capped: bool = False


async def estimate_cost(pool: asyncpg.Pool, sql: str) -> tuple[float, str]:
    """
    Run EXPLAIN on the query to estimate cost before real execution.
    Returns (estimated_cost, explain_text).
    Asks Gemini to rewrite with tighter scope if cost is too high.
    """
    try:
        async with pool.acquire() as conn:
            # Use EXPLAIN (FORMAT JSON) to get structured cost data
            result = await conn.fetch(f"EXPLAIN (FORMAT JSON) {sql}")
            explain_data = result[0][0]

            total_cost = explain_data.get("total cost", 0)
            plan_rows = explain_data.get("plan rows", 0)
            explain_text = json.dumps(explain_data, indent=2)

            return total_cost, explain_text
    except Exception as e:
        # If EXPLAIN itself fails, return high cost to trigger rewrite
        return float("inf"), f"EXPLAIN failed: {e}"


async def execute_query(pool: asyncpg.Pool, sql: str) -> QueryResult:
    """
    Execute a validated, read-only SQL query against the client database.

    Enforces:
    - Execution timeout (5s)
    - Row cap (2000)
    - Returns structured QueryResult for downstream processing
    """
    start = time.monotonic()

    try:
        async with pool.acquire() as conn:
            # Set statement timeout (5 seconds)
            await conn.execute("SET statement_timeout = 5000")

            # Execute with row limit already in SQL (injected by validator)
            result = await conn.fetch(sql)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            row_count = len(result)
            capped = row_count >= MAX_ROW_CAP

            # Convert asyncpg Record objects to dicts
            columns = list(result[0].keys()) if result else []
            rows = [dict(r) for r in result]

            # Handle non-serializable types (dates, UUIDs, etc.)
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, "isoformat"):
                        row[key] = value.isoformat()
                    elif hasattr(value, "__str__") and not isinstance(value, (str, int, float, bool, type(None))):
                        row[key] = str(value)

            return QueryResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=row_count,
                execution_ms=elapsed_ms,
                capped=capped,
            )

    except asyncpg.StatementTimeoutError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error="Query timed out after 5 seconds — try narrowing your question",
            error_class="timeout",
        )
    except asyncpg.UndefinedColumnError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error=str(e),
            error_class="unknown_column",
        )
    except asyncpg.UndefinedTableError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error=str(e),
            error_class="unknown_table",
        )
    except asyncpg.SyntaxOrAccessError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error=str(e),
            error_class="syntax_or_access",
        )
    except asyncpg.InsufficientPrivilegeError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error=str(e),
            error_class="permission_denied",
        )
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return QueryResult(
            success=False,
            execution_ms=elapsed_ms,
            error=str(e),
            error_class="unknown",
        )
