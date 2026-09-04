"""
Session handling for the High School Management System API

Sessions are opaque random tokens sent in the ``Authorization: Bearer`` header.
Only a hash of each token is stored, so a database leak cannot be replayed.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import sessions_collection, teachers_collection

SESSION_LIFETIME = timedelta(hours=8)

# auto_error is disabled so a missing header returns our own 401 message
bearer_scheme = HTTPBearer(auto_error=False)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(username: str) -> str:
    """Create a session for a teacher and return the token to send to the client"""
    token = secrets.token_urlsafe(32)
    sessions_collection.insert_one({
        "_id": _hash_token(token),
        "username": username,
        "expires_at": datetime.now(timezone.utc) + SESSION_LIFETIME
    })
    return token


def delete_session(token: str) -> None:
    """Invalidate a session token"""
    sessions_collection.delete_one({"_id": _hash_token(token)})


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict[str, Any]:
    """FastAPI dependency that resolves the signed in teacher, or raises 401"""
    if credentials is None:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")

    session = sessions_collection.find_one(
        {"_id": _hash_token(credentials.credentials)})

    # The TTL index cleans up lazily, so re-check the expiry here
    if session:
        expires_at = session["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            session = None

    teacher = teachers_collection.find_one(
        {"_id": session["username"]}) if session else None

    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return teacher
