"""
Auth Service — JWT-based authentication (PRD §13).

- Email/password auth (OAuth deferred to Phase 2 per PRD)
- JWT session + refresh token
- Roles: owner, admin, viewer
- Password hashing with bcrypt
"""
import jwt
import bcrypt
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.core.config import get_settings

settings = get_settings()

# In-memory user store for Phase 5 (replaced by ZenAI Postgres in production)
_users: dict[str, dict] = {}  # email -> user data
_user_sessions: dict[str, dict] = {}  # user_id -> sessions

ACCESS_TOKEN_EXPIRY_MINUTES = 1440
REFRESH_TOKEN_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_user(email: str, password: str) -> dict:
    """Create a new user account."""
    if email.lower() in _users:
        raise ValueError("Email already registered")

    user_id = str(uuid.uuid4())
    hashed = hash_password(password)

    user = {
        "id": user_id,
        "email": email.lower(),
        "password_hash": hashed,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _users[email.lower()] = user

    # Generate tokens
    access_token = _create_access_token(user_id, email)
    refresh_token = _create_refresh_token(user_id)

    return {
        "user_id": user_id,
        "email": email.lower(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def authenticate(email: str, password: str) -> Optional[dict]:
    """Authenticate a user and return tokens."""
    user = _users.get(email.lower())
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    access_token = _create_access_token(user["id"], user["email"])
    refresh_token = _create_refresh_token(user["id"])

    return {
        "user_id": user["id"],
        "email": user["email"],
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
