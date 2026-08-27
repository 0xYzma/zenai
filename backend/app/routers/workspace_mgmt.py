"""
Workspace Management routes — §5.2, §5.3, §12

POST /workspaces, GET /workspaces, POST /{id}/members, GET /{id}/members, GET /{id}/logs
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth import verify_token
from app.db import data_access as db
from app.core.logger import logger

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str


class MemberInvite(BaseModel):
    email: str
    role: str = "viewer"

class TimezoneUpdate(BaseModel):
    timezone: str


def _get_user_id(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@router.post("")
async def create_workspace(req: WorkspaceCreate, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    ws = await db.create_workspace(req.name, user_id)
    return ws


@router.get("")
async def list_workspaces(authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    workspaces = await db.list_workspaces_for_user(user_id)
    return {"workspaces": workspaces}


@router.post("/{workspace_id}/members")
async def invite_member(workspace_id: str, req: MemberInvite, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can invite")
    if req.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")
    result = await db.add_workspace_member(workspace_id, req.email, req.role)
    return {"status": "invited", **result}


@router.get("/{workspace_id}/members")
async def list_members(workspace_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")
    members = await db.list_workspace_members(workspace_id)
    return {"members": members}


@router.get("/{workspace_id}/logs")
async def get_query_logs(workspace_id: str, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if not role:
        raise HTTPException(status_code=403, detail="Not a member")
    logs = await db.get_query_logs(workspace_id)
    return {"logs": logs}


@router.patch("/{workspace_id}/timezone")
async def update_timezone(workspace_id: str, req: TimezoneUpdate, authorization: Optional[str] = Header(None)):
    user_id = _get_user_id(authorization)
    role = await db.is_workspace_member(workspace_id, user_id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners and admins can change settings")
    await db.update_workspace_timezone(workspace_id, req.timezone)
    return {"status": "updated", "timezone": req.timezone}
