"""
Announcement endpoints for the High School Management System API
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument

from ..database import announcements_collection
from ..security import get_current_teacher

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)

MAX_TITLE_LENGTH = 100
MAX_MESSAGE_LENGTH = 500


class AnnouncementPayload(BaseModel):
    """Fields accepted when creating or updating an announcement"""

    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    expiration_date: datetime
    start_date: Optional[datetime] = None

    @field_validator("title", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be blank")
        return stripped


def _to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize a datetime to a timezone-aware UTC value"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_object_id(announcement_id: str) -> ObjectId:
    try:
        return ObjectId(announcement_id)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=404, detail="Announcement not found") from None


def _serialize(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a stored announcement into a JSON friendly dictionary"""
    start_date = _to_utc(document.get("start_date"))
    expiration_date = _to_utc(document.get("expiration_date"))

    return {
        "id": str(document["_id"]),
        "title": document.get("title", ""),
        "message": document.get("message", ""),
        "start_date": start_date.isoformat() if start_date else None,
        "expiration_date": expiration_date.isoformat() if expiration_date else None,
        "created_by": document.get("created_by")
    }


def _validate_dates(payload: AnnouncementPayload) -> Dict[str, Optional[datetime]]:
    """Validate the announcement window and return normalized dates"""
    start_date = _to_utc(payload.start_date)
    expiration_date = _to_utc(payload.expiration_date)

    if start_date and expiration_date <= start_date:
        raise HTTPException(
            status_code=400,
            detail="Expiration date must be after the start date")

    if expiration_date <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Expiration date must be in the future")

    return {"start_date": start_date, "expiration_date": expiration_date}


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get announcements that are currently visible to everyone"""
    now = datetime.now(timezone.utc)
    query = {
        "expiration_date": {"$gt": now},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": now}}
        ]
    }

    cursor = announcements_collection.find(query).sort("expiration_date", 1)
    return [_serialize(document) for document in cursor]


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_announcements(
    teacher: Dict[str, Any] = Depends(get_current_teacher)
) -> List[Dict[str, Any]]:
    """Get every announcement, including expired ones - requires authentication"""
    cursor = announcements_collection.find().sort("expiration_date", -1)
    return [_serialize(document) for document in cursor]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    payload: AnnouncementPayload,
    teacher: Dict[str, Any] = Depends(get_current_teacher)
) -> Dict[str, Any]:
    """Create a new announcement - requires authentication"""
    dates = _validate_dates(payload)

    document = {
        "title": payload.title,
        "message": payload.message,
        "start_date": dates["start_date"],
        "expiration_date": dates["expiration_date"],
        "created_by": teacher["_id"],
        "created_at": datetime.now(timezone.utc)
    }

    try:
        result = announcements_collection.insert_one(document)
    except Exception:
        logger.exception("Failed to create announcement")
        raise HTTPException(
            status_code=500, detail="Unable to save the announcement")

    document["_id"] = result.inserted_id
    return _serialize(document)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher: Dict[str, Any] = Depends(get_current_teacher)
) -> Dict[str, Any]:
    """Update an existing announcement - requires authentication"""
    dates = _validate_dates(payload)
    object_id = _parse_object_id(announcement_id)

    try:
        updated = announcements_collection.find_one_and_update(
            {"_id": object_id},
            {"$set": {
                "title": payload.title,
                "message": payload.message,
                "start_date": dates["start_date"],
                "expiration_date": dates["expiration_date"]
            }},
            return_document=ReturnDocument.AFTER
        )
    except Exception:
        logger.exception("Failed to update announcement %s", announcement_id)
        raise HTTPException(
            status_code=500, detail="Unable to save the announcement")

    if not updated:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return _serialize(updated)


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(
    announcement_id: str,
    teacher: Dict[str, Any] = Depends(get_current_teacher)
) -> Dict[str, str]:
    """Delete an announcement - requires authentication"""
    object_id = _parse_object_id(announcement_id)

    try:
        result = announcements_collection.delete_one({"_id": object_id})
    except Exception:
        logger.exception("Failed to delete announcement %s", announcement_id)
        raise HTTPException(
            status_code=500, detail="Unable to delete the announcement")

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
