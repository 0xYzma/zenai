"""
Credential Encryption — §17 (encrypted credentials at rest).

Uses Fernet symmetric encryption from cryptography library.
Key stored in ZENAI_ENCRYPTION_KEY env var.
"""
import os
import base64
from typing import Optional

# In production, this comes from env var. For dev, we auto-generate.
_encryption_key: Optional[str] = None


def _get_key() -> str:
    global _encryption_key
    if _encryption_key is None:
        _encryption_key = os.environ.get("ZENAI_ENCRYPTION_KEY", "")
        if not _encryption_key:
            # Fallback static key for dev so restarts don't lose data
            _encryption_key = "dGVzdF9kZXYfZmFsbGJhY2tfa2V5XzEyMzQ1Njc4OTA="
    return _encryption_key


def encrypt_credentials(host: str, port: int, db_name: str, username: str, password: str) -> str:
    """
    Encrypt database credentials into a single string for storage.
    Format: base64(encrypted JSON)
    """
    import json
    from cryptography.fernet import Fernet

    key = _get_key()
    if isinstance(key, str):
        key = key.encode()

    payload = json.dumps({
        "host": host,
        "port": port,
        "db_name": db_name,
        "username": username,
        "password": password,
    })

    f = Fernet(key)
    encrypted = f.encrypt(payload.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """
    Decrypt stored credentials back to dict.
    Returns: {host, port, db_name, username, password}
    """
    import json
    from cryptography.fernet import Fernet

    key = _get_key()
    if isinstance(key, str):
        key = key.encode()

    f = Fernet(key)
    decrypted = f.decrypt(base64.urlsafe_b64decode(encrypted.encode()))
    return json.loads(decrypted)


def _append_ssl(url: str, host: str) -> str:
    if "neon.tech" in host or "supabase.co" in host:
        return f"{url}?sslmode=require"
    return url


def build_asyncpg_url(creds: dict) -> str:
    """Build asyncpg connection URL from decrypted credentials."""
    url = f"postgresql://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['db_name']}"
    return _append_ssl(url, creds['host'])


def build_sync_url(creds: dict) -> str:
    """Build synchronous psycopg2 URL from decrypted credentials."""
    url = f"postgresql://{creds['username']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['db_name']}"
    return _append_ssl(url, creds['host'])
