"""
SQL Generator — Gemini-powered (PRD §10.1–10.4).

- System prompt constraints: SELECT-only, use only provided schema,
  never invent columns/tables, tenant scoping left to backend.
- Temperature 0.1–0.2 for deterministic output.
- Retry prompt for retryable errors (§10.4).
"""
import httpx
from app.core.config import get_settings
from app.db import data_access as db
from typing import Optional

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

SYSTEM_PROMPT = """You are a SQL generation assistant for a business analytics tool.

CONSTRAINTS:
- Output ONLY a single SELECT statement. No explanations, no markdown, no commentary.
- Use ONLY the tables and columns provided in the schema context below. Never invent tables or columns.
- Never add tenant_id or workspace_id filters — the backend injects these automatically.
- Never use DELETE, UPDATE, INSERT, DROP, ALTER, CREATE, TRUNCATE, COPY, or any DDL/DML.
- Never use CTEs that wrap non-SELECT operations.
- Never query information_schema, pg_catalog, or system tables.
- Always use PostgreSQL dialect.
- If you cannot answer the question with the given schema, output: SELECT 'NO_ANSWER' AS reason
- When comparing periods, use explicit date ranges.
- Use meaningful aliases for computed columns.

FEW-SHOT EXAMPLES:

User: What were the top 5 products by revenue last month?
SELECT p.name AS product_name, SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
JOIN orders o ON o.id = oi.order_id
WHERE o.created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
  AND o.created_at < DATE_TRUNC('month', CURRENT_DATE)
GROUP BY p.name
ORDER BY total_revenue DESC
LIMIT 5;

User: How many orders did each store process this week?
SELECT s.name AS store_name, COUNT(o.id) AS order_count
FROM orders o
JOIN stores s ON s.id = o.store_id
WHERE o.created_at >= DATE_TRUNC('week', CURRENT_DATE)
GROUP BY s.name
ORDER BY order_count DESC;

User: What is the refund rate by category?
SELECT
  c.name AS category,
  COUNT(CASE WHEN o.status = 'refunded' THEN 1 END)::float / COUNT(o.id) * 100 AS refund_rate_pct
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
JOIN categories c ON c.id = p.category_id
GROUP BY c.name
ORDER BY refund_rate_pct DESC;"""


async def generate_sql(
    question: str,
    schema_chunks: list[dict],
    conversation_context: Optional[str] = None,
    error_context: Optional[str] = None,
    failed_sql: Optional[str] = None,
) -> str:
    """
    Generate a SQL query from a natural language question.

    Args:
        question: The user's natural language question
        schema_chunks: Retrieved schema chunks from ChromaDB
        conversation_context: Compressed conversation context (last 2 turns + summary)
        error_context: Error message from a previous failed query (for retry)
        failed_sql: The SQL that failed (for retry)

    Returns:
        A single SELECT statement
    """
    settings = get_settings()

    # Build schema context from retrieved chunks
    schema_text = "\n\n".join([chunk["document"] for chunk in schema_chunks])

    # Build the prompt
    prompt_parts = [SYSTEM_PROMPT, f"\nSchema context:\n{schema_text}"]

    if conversation_context:
        prompt_parts.append(f"\nConversation context:\n{conversation_context}")

    if error_context and failed_sql:
        prompt_parts.append(f"""
Your previous query failed with this error: {error_context}
Previous SQL: {failed_sql}
Please generate a corrected SELECT statement that avoids this error.""")

    prompt_parts.append(f"\nCurrent question: {question}")
    prompt_parts.append("\nOutput: a single SELECT statement only.")

    full_prompt = "\n".join(prompt_parts)

    # Call Gemini API with §7.2 retry + backoff
    import asyncio
    last_error = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    GEMINI_API_URL,
                    params={"key": settings.gemini_api_key},
                    json={
                        "contents": [{"parts": [{"text": full_prompt}]}],
                        "generationConfig": {
                            "temperature": 0.15,
                            "maxOutputTokens": 1024,
                            "topP": 0.8,
                            "topK": 40,
                        },
                    },
                )

                if response.status_code == 429:
                    # Rate limited — backoff and retry
                    await asyncio.sleep(2 ** attempt)
                    continue

                if response.status_code != 200:
                    raise Exception(f"Gemini API error: {response.status_code} - {response.text}")

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise Exception("No response from Gemini API")

                sql_text = candidates[0]["content"]["parts"][0]["text"].strip()

                if sql_text.startswith("```"):
                    lines = sql_text.split("\n")
                    sql_text = "\n".join(lines[1:-1]).strip()

                # §10.5: Save prompt version
                try:
                    await db.save_prompt_version("sql_generation", "v1", full_prompt[:2000])
                except Exception:
                    pass

                return sql_text

        except httpx.TimeoutException as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(1 * (attempt + 1))
                continue
            raise Exception(f"Gemini API timeout after retries: {e}")
        except Exception as e:
            if attempt < 2 and "503" in str(e):
                await asyncio.sleep(2 ** attempt)
                continue
            raise

    raise Exception(f"Gemini API failed after retries: {last_error}")
