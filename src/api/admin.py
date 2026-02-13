"""Admin API routes — user management, settings."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.connection import get_db
from src.db.models import EmailRepository, UserRepository, LabelRepository
from src.users.settings import UserSettings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class UserCreate(BaseModel):
    email: str
    display_name: str | None = None


class SettingUpdate(BaseModel):
    key: str
    value: Any


@router.get("/users")
async def list_users() -> list[dict]:
    db = get_db()
    repo = UserRepository(db)
    users = repo.get_active_users()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "onboarded_at": str(u.onboarded_at) if u.onboarded_at else None,
        }
        for u in users
    ]


@router.post("/users")
async def create_user(body: UserCreate) -> dict:
    db = get_db()
    repo = UserRepository(db)
    existing = repo.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user_id = repo.create(body.email, body.display_name)
    return {"id": user_id, "email": body.email}


@router.get("/users/{user_id}/settings")
async def get_user_settings(user_id: int) -> dict:
    db = get_db()
    settings = UserSettings(db, user_id)
    return settings.get_all()


@router.put("/users/{user_id}/settings")
async def update_setting(user_id: int, body: SettingUpdate) -> dict:
    db = get_db()
    settings = UserSettings(db, user_id)
    settings.set(body.key, body.value)
    return {"ok": True}


@router.get("/users/{user_id}/labels")
async def get_user_labels(user_id: int) -> dict:
    db = get_db()
    labels = LabelRepository(db)
    return labels.get_labels(user_id)


@router.get("/users/{user_id}/emails")
async def get_user_emails(user_id: int, status: str | None = None, classification: str | None = None) -> list[dict]:
    db = get_db()
    repo = EmailRepository(db)
    if status:
        return repo.get_by_status(user_id, status)
    elif classification:
        return repo.get_by_classification(user_id, classification)
    else:
        return repo.get_by_status(user_id, "pending")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
