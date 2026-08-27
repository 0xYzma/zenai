"""
ZenAI Backend — FastAPI Application Entry Point

All phases complete. §16 observability, §13 password reset, metrics endpoint.
"""
import time
import uuid
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.core.config import get_settings
from app.core.logger import logger
from app.core.redis import get_redis_client
from app.db.data_access import get_zenai_conn
from app.routers import workspaces, chat, auth, workspace_mgmt, internal
from app.security.delegation import require_internal_service

settings = get_settings()
settings.validate_runtime_configuration()

app = FastAPI(
    title="ZenAI Backend",
    description="AI copilot for business data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3100"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── §16: Request Metrics ────────────────────────────────────────────────
_metrics = {
    "request_count": 0,
    "error_count": 0,
    "total_latency_ms": 0,
    "start_time": datetime.now(timezone.utc),
}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    _metrics["request_count"] += 1

    logger.request_start(request_id, request.method, request.url.path)

    response = await call_next(request)

    duration_ms = int((time.time() - start) * 1000)
    _metrics["total_latency_ms"] += duration_ms
    if response.status_code >= 400:
        _metrics["error_count"] += 1

    logger.request_end(request_id, response.status_code, duration_ms)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    return response


# ── §16: Metrics Endpoint ───────────────────────────────────────────────
@app.get("/metrics", dependencies=[Depends(require_internal_service)])
async def get_metrics():
    uptime_seconds = (datetime.now(timezone.utc) - _metrics["start_time"]).total_seconds()
    avg_latency = (
        _metrics["total_latency_ms"] / _metrics["request_count"]
        if _metrics["request_count"] > 0 else 0
    )
    return {
        "request_count": _metrics["request_count"],
        "error_count": _metrics["error_count"],
        "error_rate": round(_metrics["error_count"] / max(_metrics["request_count"], 1) * 100, 2),
        "avg_latency_ms": round(avg_latency, 1),
        "uptime_seconds": round(uptime_seconds),
    }


# ── §13: Password Reset ────────────────────────────────────────────────
class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

async def forgot_password(req: PasswordResetRequest):
    from app.services.password_reset import create_reset_token
    from app.services.email import send_reset_email
    token = create_reset_token(req.email)
    send_reset_email(req.email, token)
    return {"message": "If an account exists with this email, a reset link has been sent."}


async def reset_password(req: PasswordResetConfirm):
    from app.services.password_reset import verify_reset_token
    from app.services.auth import hash_password
    from app.db import data_access as db
    email = verify_reset_token(req.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = await db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    # Update password
    import asyncpg
    conn = await asyncpg.connect(settings.zenai_database_url)
    try:
        await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hash_password(req.new_password), uuid.UUID(user["id"]))
    finally:
        await conn.close()
    return {"message": "Password updated"}


app.add_api_route(
    "/auth/forgot-password", forgot_password, methods=["POST"]
)
app.add_api_route(
    "/auth/reset-password", reset_password, methods=["POST"]
)


# ── §5.3: Schema Auto-Refresh (scheduled daily) ────────────────────────
@app.on_event("startup")
async def startup_event():
    if settings.enable_text_to_sql:
        from app.services.scheduler import start_schema_refresh_scheduler
        start_schema_refresh_scheduler()


# ── Routers ─────────────────────────────────────────────────────────────
app.include_router(internal.router, prefix="/internal/v1", tags=["internal"])

app.include_router(auth.router, tags=["auth"])
app.include_router(workspace_mgmt.router, prefix="/workspaces", tags=["workspace-management"])
app.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
app.include_router(chat.router, prefix="/workspaces", tags=["chat"])


@app.get("/health/live")
async def health_live():
    return {"status": "ok", "version": "1.0.0", "mode": settings.zenai_mode}


@app.get("/health")
async def health_check():
    """Backward-compatible public liveness endpoint."""
    return await health_live()


@app.get("/health/ready", dependencies=[Depends(require_internal_service)])
async def health_ready():
    dependencies = {
        "postgres": "unavailable",
        "redis": "required" if settings.require_redis_for_readiness else "not_required",
    }
    try:
        conn = await get_zenai_conn()
        try:
            await conn.fetchval("SELECT 1")
            dependencies["postgres"] = "ok"
        finally:
            await conn.close()
    except Exception:
        logger.error("readiness_dependency_failed", "postgres unavailable")

    if settings.require_redis_for_readiness:
        try:
            await get_redis_client().ping()
            dependencies["redis"] = "ok"
        except Exception:
            dependencies["redis"] = "unavailable"
            logger.error("readiness_dependency_failed", "redis unavailable")

    ready = dependencies["postgres"] == "ok" and dependencies["redis"] != "unavailable"
    payload = {
        "status": "ready" if ready else "not_ready",
        "version": "1.0.0",
        "mode": settings.zenai_mode,
        "dependencies": dependencies,
    }
    return payload if ready else JSONResponse(status_code=503, content=payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.debug)
