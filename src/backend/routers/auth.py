"""
Authentication endpoints for the High School Management System API
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..database import teachers_collection, verify_password
from ..security import (
    bearer_scheme,
    create_session,
    delete_session,
    get_current_teacher,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


class LoginRequest(BaseModel):
    """Credentials sent in the request body so they never reach access logs"""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def _public_profile(teacher: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": teacher["username"],
        "display_name": teacher["display_name"],
        "role": teacher["role"]
    }


@router.post("/login")
def login(payload: LoginRequest) -> Dict[str, Any]:
    """Login a teacher account and start a session"""
    teacher = teachers_collection.find_one({"_id": payload.username})

    # Verify password using Argon2 verifier from database.py
    if not teacher or not verify_password(teacher.get("password", ""), payload.password):
        raise HTTPException(
            status_code=401, detail="Invalid username or password")

    return {
        "token": create_session(teacher["username"]),
        **_public_profile(teacher)
    }


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict[str, str]:
    """End the current session"""
    if credentials:
        delete_session(credentials.credentials)

    return {"message": "Logged out"}


@router.get("/check-session")
def check_session(
    teacher: Dict[str, Any] = Depends(get_current_teacher)
) -> Dict[str, Any]:
    """Return the profile tied to the session token"""
    return _public_profile(teacher)
