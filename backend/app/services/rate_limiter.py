"""
Rate Limiter — Redis-based, §17.

Rate limits /chat endpoint per workspace.
Default: 30 requests per minute per workspace.
"""
import time
from typing import Optional
from app.core.redis import get_redis_client
from app.core.logger import logger

DEFAULT_RATE_LIMIT = 30  # requests
DEFAULT_WINDOW_SECONDS = 60  # per minute


async def check_rate_limit(workspace_id: str, limit: int = DEFAULT_RATE_LIMIT,
                           window: int = DEFAULT_WINDOW_SECONDS) -> bool:
    """
    Check if workspace has exceeded rate limit.
    Returns True if allowed, False if blocked.
    Uses Redis sliding window counter.
    """
    try:
        redis = get_redis_client()
        key = f"ratelimit:chat:{workspace_id}"
        now = time.time()

        pipe = redis.pipeline()
        # Remove entries outside the window
        pipe.zremrangebyscore(key, 0, now - window)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Set expiry
        pipe.expire(key, window)

        results = await pipe.execute()
        request_count = results[2]

        if request_count > limit:
            logger.rate_limit(workspace_id, user_id=None, blocked=True)
            return False

        return True
    except Exception:
        # If Redis is unavailable, allow the request (fail open)
        return True


async def get_rate_limit_info(workspace_id: str, limit: int = DEFAULT_RATE_LIMIT,
                              window: int = DEFAULT_WINDOW_SECONDS) -> dict:
    """Get current rate limit info for a workspace."""
    try:
        redis = get_redis_client()
        key = f"ratelimit:chat:{workspace_id}"
        now = time.time()

        await redis.zremrangebyscore(key, 0, now - window)
        count = await redis.zcard(key)

        return {
            "limit": limit,
            "remaining": max(0, limit - count),
            "window_seconds": window,
            "reset_at": int(now + window),
        }
    except Exception:
        return {"limit": limit, "remaining": limit, "window_seconds": window}
