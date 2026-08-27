"""
Query Cache — §9 (Fixed, time-window + schema-version aware).

Cache key = hash(workspace_id + normalized_question + time_window_bucket + schema_version)
TTL: 15-60 minutes.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional
from app.db import data_access as db
from app.core.logger import logger

# Date-sensitive keywords that trigger daily buckets instead of hourly
DATE_KEYWORDS = [
    "today", "yesterday", "this week", "last week", "this month", "last month",
    "this year", "last year", "this quarter", "last quarter",
    "current", "so far", "year to date", "ytd",
]


def _normalize_question(question: str) -> str:
    """Normalize question for consistent hashing."""
    q = question.lower().strip()
    q = re.sub(r'\s+', ' ', q)
    return q


def _is_date_sensitive(question: str) -> bool:
    """Detect if question contains date-sensitive keywords."""
    q = question.lower()
    return any(kw in q for kw in DATE_KEYWORDS)


def _get_time_window_bucket(is_date_sensitive: bool) -> str:
    """
    Generate time window bucket for cache key.
    Date-sensitive → daily bucket (YYYY-MM-DD)
    Others → hourly bucket (YYYY-MM-DD-HH)
    """
    now = datetime.now(timezone.utc)
    if is_date_sensitive:
        return now.strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d-%H")


def build_cache_key(workspace_id: str, question: str, schema_version: int) -> str:
    """
    Build §9-compliant cache key.
    key = hash(workspace_id + normalized_question + time_window_bucket + schema_version)
    """
    normalized = _normalize_question(question)
    is_date = _is_date_sensitive(question)
    bucket = _get_time_window_bucket(is_date_sensitive=is_date)

    raw = f"{workspace_id}:{normalized}:{bucket}:v{schema_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def get_cached_answer(workspace_id: str, cache_key: str) -> Optional[dict]:
    """Get cached answer from ZenAI Postgres (§9)."""
    try:
        cached = await db.get_cached_answer(workspace_id, cache_key)
        if cached:
            # Parse the stored JSON string back to dict
            if isinstance(cached, str):
                return json.loads(cached)
            return cached
    except Exception:
        pass
    return None


async def set_cached_answer(workspace_id: str, cache_key: str, answer: dict, ttl_minutes: int = 30):
    """Store answer in cache with TTL (§9)."""
    try:
        await db.set_cached_answer(workspace_id, cache_key, answer, ttl_minutes)
    except Exception:
        pass
