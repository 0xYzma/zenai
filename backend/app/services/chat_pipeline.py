"""
Chat Pipeline — §4.2 (full orchestrator with all § fixes).

1. Cache check (§9)
2. Schema retrieval (ChromaDB)
3. Conversation context compression (§5.4)
4. SQL generation (Gemini)
5. SQL validation (§8)
6. Tenant scoping injection (§8, §17)
7. Cost estimation (EXPLAIN)
8. Query execution (read-only, row cap, timeout)
9. Retry on retryable errors (§7.1 — once)
10. Result processing (Pandas — tiered + deterministic chart data)
11. Reasoning (Gemini — explanation, insights, confidence, chart_type)
12. Conversation summary update (§5.4)
13. Log to query_logs
14. Cache store (§9)
"""
import time
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, AsyncGenerator
from dataclasses import dataclass, field

import asyncpg

from app.services.schema_embedder import retrieve_relevant_tables
from app.services.sql_generator import generate_sql
from app.services.sql_validator import validate_sql, is_retryable_error, ValidationError
from app.services.query_executor import execute_query, estimate_cost
from app.services.result_processor import process_result
from app.services.reasoning import generate_reasoning
from app.services.conversation_compressor import generate_summary
from app.services.tenant_scoping import inject_tenant_scope
from app.services.cache import get_cached_answer, set_cached_answer, build_cache_key
from app.db import data_access as db
from app.core.logger import logger


async def process_chat(
    workspace_id: str,
    session_id: str,
    question: str,
    user_id: str,
    pools: dict[str, asyncpg.Pool],
) -> AsyncGenerator[str, None]:
    """Main chat pipeline — yields streamed response chunks."""
    start_time = time.monotonic()

    logger.chat_start(workspace_id, session_id, question)

    # Get or create session in real DB
    session = await db.get_or_create_session(workspace_id, session_id, user_id)
    recent_turns = await db.get_recent_turns(session_id, limit=2)
    conversation_context = _build_conversation_context(session.get("summary", ""), recent_turns)

    # ── Step 1: Cache check (§9) ────────────────────────────────────────
    ws = await db.get_workspace(workspace_id)
    schema_version = ws["schema_version"] if ws else 1
    cache_key = build_cache_key(workspace_id, question, schema_version)

    cached = await get_cached_answer(workspace_id, cache_key)
    if cached:
        logger.cache_hit(workspace_id, cache_key)
        yield json.dumps({
            "type": "answer",
            "answer": cached.get("answer", ""),
            "insights": cached.get("insights", []),
            "generated_sql": cached.get("generated_sql"),
            "chart_type": cached.get("chart_type", "none"),
            "chart_data": cached.get("chart_data"),
            "confidence": cached.get("confidence", "medium"),
            "execution_ms": 0,
            "row_count": cached.get("row_count", 0),
            "cached": True,
        }, default=str) + "\n"
        return

    logger.cache_miss(workspace_id, cache_key)

    # ── Step 2: Schema retrieval ─────────────────────────────────────────
    yield json.dumps({"type": "status", "message": "Searching schema..."}) + "\n"
    schema_chunks = retrieve_relevant_tables(workspace_id, question, top_k=5)

    if not schema_chunks:
        yield json.dumps({
            "type": "answer",
            "answer": "I don't have data that answers this — no matching table found.",
            "confidence": "low", "chart_type": "none", "chart_data": None, "insights": [],
        }) + "\n"
        return

    avg_similarity = sum(c["similarity"] for c in schema_chunks) / len(schema_chunks)

    # ── Step 3: Generate SQL ─────────────────────────────────────────────
    yield json.dumps({"type": "status", "message": "Generating SQL..."}) + "\n"
    sql_gen_start = time.monotonic()
    try:
        sql = await generate_sql(question, schema_chunks, conversation_context)
    except Exception as e:
        yield json.dumps({
            "type": "answer", "answer": f"AI service unavailable: {e}",
            "confidence": "low", "chart_type": "none", "chart_data": None, "insights": [],
        }) + "\n"
        return
    logger.sql_generated(workspace_id, sql, int((time.monotonic() - sql_gen_start) * 1000))

    # ── Step 4: Validate SQL (§8) ────────────────────────────────────────
    yield json.dumps({"type": "status", "message": "Validating SQL..."}) + "\n"
    try:
        validated_sql = validate_sql(sql)
    except ValidationError as e:
        yield json.dumps({
            "type": "answer", "answer": f"SQL invalid: {e.message}",
            "confidence": "low", "generated_sql": sql,
            "chart_type": "none", "chart_data": None, "insights": [],
        }) + "\n"
        return
    logger.sql_validated(workspace_id, validated_sql, True)

    # ── Step 5: Tenant scoping (§8, §17) ────────────────────────────────
    # Inject workspace_id filter server-side — never left to LLM
    scoped_sql = inject_tenant_scope(validated_sql, workspace_id)

    # ── Step 6: Cost estimation (§4.3 step 10) ──────────────────────────
    yield json.dumps({"type": "status", "message": "Estimating query cost..."}) + "\n"
    pool = pools.get(workspace_id)
    if not pool:
        yield json.dumps({
            "type": "answer", "answer": "No database connection.",
            "confidence": "low", "chart_type": "none", "chart_data": None, "insights": [],
        }) + "\n"
        return

    estimated_cost, explain_text = await estimate_cost(pool, scoped_sql)

    if estimated_cost > 100000.0 and estimated_cost != float("inf"):
        yield json.dumps({"type": "status", "message": "Query too broad — rewriting..."}) + "\n"
        try:
            sql = await generate_sql(
                question, schema_chunks, conversation_context,
                error_context=f"Cost too high ({estimated_cost:.0f}). Add date filters or LIMIT.",
                failed_sql=scoped_sql,
            )
            validated_sql = validate_sql(sql)
            scoped_sql = inject_tenant_scope(validated_sql, workspace_id)
            estimated_cost, _ = await estimate_cost(pool, scoped_sql)
        except Exception:
            pass

    # ── Step 7: Execute query ────────────────────────────────────────────
    yield json.dumps({"type": "status", "message": "Executing query..."}) + "\n"
    result = await execute_query(pool, scoped_sql)

    # ── Step 8: Retry on retryable errors (§7.1 — once) ─────────────────
    retries = 0
    if not result.success and result.error_class and is_retryable_error(result.error):
        yield json.dumps({"type": "status", "message": "Retrying with corrected SQL..."}) + "\n"
        logger.query_retry(workspace_id, result.error, 1)
        try:
            sql = await generate_sql(
                question, schema_chunks, conversation_context,
                error_context=result.error, failed_sql=scoped_sql,
            )
            validated_sql = validate_sql(sql)
            scoped_sql = inject_tenant_scope(validated_sql, workspace_id)
            result = await execute_query(pool, scoped_sql)
            retries += 1
        except Exception:
            pass

    total_exec_ms = int((time.monotonic() - start_time) * 1000)

    # ── Step 9: Handle execution failure ─────────────────────────────────
    if not result.success:
        error_msg = result.error or "Query failed"
        if result.error_class == "timeout":
            error_msg = "Query took too long — try narrowing to a specific time range."
        elif result.error_class == "permission_denied":
            error_msg = "Permission denied — check database role access."
        elif result.error_class in ("unknown_column", "unknown_table"):
            error_msg = f"Data doesn't exist: {result.error}"

        logger.query_error(workspace_id, result.error, result.error_class or "unknown")

        await db.save_query_log(workspace_id, scoped_sql, 0, total_exec_ms, estimated_cost, "error")
        await db.save_chat_message(session_id, "assistant", error_msg, generated_sql=scoped_sql, confidence="low")

        yield json.dumps({
            "type": "answer", "answer": error_msg, "generated_sql": scoped_sql,
            "confidence": "low", "execution_ms": total_exec_ms,
            "chart_type": "none", "chart_data": None, "insights": [],
        }, default=str) + "\n"
        return

    # ── Step 10: Process results (Pandas — §6) ──────────────────────────
    yield json.dumps({"type": "status", "message": "Processing results..."}) + "\n"
    processed = process_result(result.columns, result.rows, question)

    # ── Step 11: Reasoning (Gemini — §10.3) ─────────────────────────────
    yield json.dumps({"type": "status", "message": "Generating explanation..."}) + "\n"
    reasoning = await generate_reasoning(
        question=question,
        summary=processed.summary,
        chart_type_from_pandas=processed.chart_type,
        conversation_context=conversation_context,
    )

    # ── Step 12: Confidence (§5.6 — computed) ───────────────────────────
    # §5.6: "Whether the question required a compressed/older conversation summary
    # (slightly lowers confidence vs. fresh context)"
    used_compressed_summary = bool(session.get("summary")) and not recent_turns
    if avg_similarity < 0.6:
        confidence = "low"
    elif retries > 0:
        confidence = "medium"
    elif result.row_count == 0:
        confidence = "low"
    elif used_compressed_summary:
        confidence = "medium"  # §5.6: compressed context lowers confidence
    else:
        confidence = reasoning.get("confidence_signal", "medium")

    answer_text = reasoning.get("summary", f"Query returned {result.row_count} rows.")
    insights = reasoning.get("insights", [])
    chart_type = reasoning.get("chart_type", processed.chart_type)

    if result.capped:
        answer_text += f"\n\n_Note: Results capped at {result.row_count} rows._"

    # ── Step 13: Store everything ────────────────────────────────────────
    log_status = "retried" if retries > 0 else "success"
    await db.save_query_log(workspace_id, scoped_sql, result.row_count, total_exec_ms, estimated_cost, log_status)
    msg_id = await db.save_chat_message(
        session_id, "assistant", answer_text,
        generated_sql=scoped_sql, result_summary=processed.summary,
        chart_type=chart_type, chart_data=processed.chart_data,
        confidence=confidence,
    )

    # ── Step 14: Update conversation summary (§5.4) ─────────────────────
    try:
        new_summary = await generate_summary(session.get("summary", ""), question, answer_text)
        await db.update_session_summary(session_id, new_summary)
    except Exception:
        pass  # Summary generation is best-effort

    # ── Step 15: Cache result (§9) ──────────────────────────────────────
    cache_answer = {
        "answer": answer_text, "insights": insights, "generated_sql": scoped_sql,
        "chart_type": chart_type, "chart_data": processed.chart_data,
        "confidence": confidence, "row_count": result.row_count,
    }
    await set_cached_answer(workspace_id, cache_key, cache_answer, ttl_minutes=30)
    logger.cache_set(workspace_id, cache_key, 30)

    # ── Stream final answer ──────────────────────────────────────────────
    response_data = {
        "type": "answer",
        "message_id": msg_id,
        "answer": answer_text,
        "insights": insights,
        "generated_sql": scoped_sql,
        "chart_type": chart_type,
        "chart_data": processed.chart_data,
        "confidence": confidence,
        "execution_ms": total_exec_ms,
        "estimated_cost": estimated_cost if estimated_cost != float("inf") else None,
        "schema_similarity": round(avg_similarity, 3),
        "row_count": result.row_count,
        "retries": retries,
    }

    yield json.dumps(response_data, default=str) + "\n"

    logger.chat_complete(workspace_id, session_id, total_exec_ms, confidence, chart_type, result.row_count)


def _build_conversation_context(summary: str, recent_turns: list[dict]) -> str:
    """Build conversation context from DB session data (§5.4)."""
    parts = []
    if summary:
        parts.append(f"Session summary: {summary}")
    if recent_turns:
        parts.append("Recent turns:")
        for turn in recent_turns:
            parts.append(f"  Q: {turn.get('content', '')[:200]}")
            parts.append(f"  SQL: {turn.get('generated_sql', '')[:200]}")
    return "\n".join(parts) if parts else ""
