"""
Chat routes — §5.1, §12

POST /workspaces/{id}/chat — streamed Q&A (with rate limiting §17, logging §16)
GET  /workspaces/{id}/chat/{session_id} — conversation history
POST /workspaces/{id}/chat/{message_id}/feedback — thumbs up/down (§12)
GET  /workspaces/{id}/chat/{message_id}/download — download query results as CSV
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io
import csv
from app.services.chat_pipeline import process_chat
from app.services.rate_limiter import check_rate_limit, get_rate_limit_info
from app.services.auth import verify_token
from app.db import data_access as db
from app.core.logger import logger
import json
import uuid

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    rating: str  # 'up' | 'down'
    comment: Optional[str] = None


def _get_user_id(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


# Pool cache — rebuilt from connections on startup
_pools: dict = {}


@router.post("/{workspace_id}/chat")
async def chat(workspace_id: str, req: ChatRequest, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)

    # §17: Rate limiting
    allowed = await check_rate_limit(workspace_id)
    if not allowed:
        rate_info = await get_rate_limit_info(workspace_id)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {rate_info['window_seconds']}s.",
            headers={"Retry-After": str(rate_info["window_seconds"])},
        )

    # §5.2: Verify membership
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    # Check connection exists
    conn = await db.get_connection(workspace_id)
    if not conn:
        raise HTTPException(status_code=400, detail="No database connection. Connect first.")

    # Rebuild pool if not cached
    if workspace_id not in _pools:
        from app.services.encryption import decrypt_credentials, build_asyncpg_url
        import asyncpg
        creds = decrypt_credentials(conn["encrypted_credentials"])
        pool = await asyncpg.create_pool(build_asyncpg_url(creds), min_size=1, max_size=5)
        _pools[workspace_id] = pool

    session_id = req.session_id or str(uuid.uuid4())

    async def event_stream():
        async for chunk in process_chat(
            workspace_id=workspace_id,
            session_id=session_id,
            question=req.question,
            user_id=user_id,
            pools=_pools,
        ):
            yield chunk

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Session-Id": session_id, "Cache-Control": "no-cache"},
    )


@router.get("/{workspace_id}/chat/{session_id}")
async def get_chat_history(workspace_id: str, session_id: str,
                           authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    messages = await db.get_chat_history(session_id)
    return {"session_id": session_id, "messages": messages}


@router.get("/{workspace_id}/chat/{message_id}/download")
async def download_raw_results(workspace_id: str, message_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")
        
    msg = await db.get_chat_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    sql = msg.get("generated_sql")
    if not sql:
        raise HTTPException(status_code=400, detail="No SQL generated for this message")
        
    pool = _pools.get(workspace_id)
    if not pool:
        conn = await db.get_connection(workspace_id)
        if not conn:
            raise HTTPException(status_code=400, detail="No database connection.")
        from app.services.encryption import decrypt_credentials, build_asyncpg_url
        import asyncpg
        creds = decrypt_credentials(conn["encrypted_credentials"])
        pool = await asyncpg.create_pool(build_asyncpg_url(creds), min_size=1, max_size=5)
        _pools[workspace_id] = pool
        
    from app.services.query_executor import execute_query
    result = await execute_query(pool, sql)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
        
    def iter_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(result.columns)
        for row in result.rows:
            writer.writerow(row)
        yield output.getvalue()

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=results_{message_id}.csv"}
    )



@router.post("/{workspace_id}/chat/{message_id}/feedback")
async def submit_feedback(workspace_id: str, message_id: str, req: FeedbackRequest,
                          authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")

    if req.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'")

    fb_id = await db.save_feedback(message_id, req.rating, req.comment)
    return {"status": "saved", "feedback_id": fb_id}
