"""
Password Reset — §13 (placeholder for Phase 2 OAuth).

For MVP, returns a token-based reset link.
In production, this sends an email via SendGrid/SES.
"""
import uuid
from datetime import datetime, timezone, timedelta

# In-memory reset tokens (replaced by DB in production)
_reset_tokens: dict[str, dict] = {}


def create_reset_token(email: str) -> str:
    """Generate a password reset token. In production, send via email."""
    token = str(uuid.uuid4())
    _reset_tokens[token] = {
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
    }
    return token


def verify_reset_token(token: str) -> str | None:
    """Verify a reset token. Returns email if valid, None otherwise."""
    data = _reset_tokens.get(token)
    if not data:
        return None
    if data["used"]:
        return None
    if datetime.now(timezone.utc) > data["expires_at"]:
        return None
    data["used"] = True
    return data["email"]
