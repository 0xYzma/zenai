"""
Auth routes — §13

POST /auth/register, POST /auth/login, GET /auth/me
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.auth import create_user, authenticate, verify_token, hash_password
from app.db import data_access as db
from app.core.logger import logger

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    access_token: str
    refresh_token: str


@router.post("/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    try:
        # Save to real Postgres
        user = await db.create_user(req.email, hash_password(req.password))
        # Generate tokens using auth service
        from app.services.auth import _create_access_token, _create_refresh_token
        access_token = _create_access_token(user["id"], user["email"])
        refresh_token = _create_refresh_token(user["id"])
        logger.auth_event("register", user_id=user["id"], email=req.email)
        return AuthResponse(
            user_id=user["id"],
            email=user["email"],
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=400, detail="Email already registered")
        logger.auth_event("register_failed", email=req.email, success=False)
        import traceback
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}\n{traceback.format_exc()}")


@router.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await db.get_user_by_email(req.email)
    if not user:
        logger.auth_event("login_failed", email=req.email, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    from app.services.auth import verify_password
    if not verify_password(req.password, user["password_hash"]):
        logger.auth_event("login_failed", email=req.email, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    from app.services.auth import _create_access_token, _create_refresh_token
    access_token = _create_access_token(user["id"], user["email"])
    refresh_token = _create_refresh_token(user["id"])
    logger.auth_event("login", user_id=user["id"], email=req.email)
    return AuthResponse(
        user_id=user["id"],
        email=user["email"],
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/auth/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"user_id": user["id"], "email": user["email"]}
