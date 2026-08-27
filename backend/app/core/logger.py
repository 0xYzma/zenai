"""
Structured Logger — §16 (Observability).

Structured JSON logs per request: workspace_id, question, generated SQL,
execution time, estimated cost, status.
"""
import json
import logging
import time
from typing import Optional
from datetime import datetime, timezone


class StructuredLogger:
    """JSON structured logger for ZenAI observability."""

    def __init__(self, name: str = "zenai"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(handler)

    def _log(self, level: str, event_name: str, **kwargs):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "event": event_name,
            **kwargs,
        }
        self.logger.info(json.dumps(entry, default=str))

    def request_start(self, request_id: str, method: str, path: str, workspace_id: str = None):
        self._log("INFO", "request_start",
                  request_id=request_id, method=method, path=path,
                  workspace_id=workspace_id)

    def request_end(self, request_id: str, status_code: int, duration_ms: int):
        self._log("INFO", "request_end",
                  request_id=request_id, status_code=status_code,
                  duration_ms=duration_ms)

    def chat_start(self, workspace_id: str, session_id: str, question: str):
        self._log("INFO", "chat_start",
                  workspace_id=workspace_id, session_id=session_id,
                  question=question[:200])

    def sql_generated(self, workspace_id: str, sql: str, generation_ms: int):
        self._log("INFO", "sql_generated",
                  workspace_id=workspace_id, sql=sql[:500],
                  generation_ms=generation_ms)

    def sql_validated(self, workspace_id: str, sql: str, valid: bool):
        self._log("INFO", "sql_validated",
                  workspace_id=workspace_id, sql=sql[:500], valid=valid)

    def query_executed(self, workspace_id: str, sql: str, row_count: int,
                       execution_ms: int, estimated_cost: float, status: str):
        self._log("INFO", "query_executed",
                  workspace_id=workspace_id, sql=sql[:500],
                  row_count=row_count, execution_ms=execution_ms,
                  estimated_cost=estimated_cost, status=status)

    def query_retry(self, workspace_id: str, error: str, retry_count: int):
        self._log("WARN", "query_retry",
                  workspace_id=workspace_id, error=error[:300],
                  retry_count=retry_count)

    def query_error(self, workspace_id: str, error: str, error_class: str):
        self._log("ERROR", "query_error",
                  workspace_id=workspace_id, error=error[:300],
                  error_class=error_class)

    def cache_hit(self, workspace_id: str, cache_key: str):
        self._log("INFO", "cache_hit",
                  workspace_id=workspace_id, cache_key=cache_key)

    def cache_miss(self, workspace_id: str, cache_key: str):
        self._log("INFO", "cache_miss",
                  workspace_id=workspace_id, cache_key=cache_key)

    def cache_set(self, workspace_id: str, cache_key: str, ttl_minutes: int):
        self._log("INFO", "cache_set",
                  workspace_id=workspace_id, cache_key=cache_key,
                  ttl_minutes=ttl_minutes)

    def chat_start(self, workspace_id: str, session_id: str, question: str):
        self._log("INFO", "chat_start",
                  workspace_id=workspace_id, session_id=session_id,
                  question=question)

    def chat_complete(self, workspace_id: str, session_id: str, total_ms: int,
                      confidence: str, chart_type: str, row_count: int):
        self._log("INFO", "chat_complete",
                  workspace_id=workspace_id, session_id=session_id,
                  total_ms=total_ms, confidence=confidence,
                  chart_type=chart_type, row_count=row_count)

    def auth_event(self, event: str, user_id: str = None, email: str = None, success: bool = True):
        self._log("INFO", "auth_event",
                  auth_action=event, user_id=user_id, email=email, success=success)

    def rate_limit(self, workspace_id: str, user_id: str, blocked: bool):
        self._log("WARN", "rate_limit",
                  workspace_id=workspace_id, user_id=user_id, blocked=blocked)

    def error(self, event: str, error: str, **kwargs):
        self._log("ERROR", event, error=error[:500], **kwargs)


logger = StructuredLogger()
