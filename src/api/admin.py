"""Admin API routes — user management, settings, watch management."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.db.connection import get_db
from src.db.models import EmailRepository, LabelRepository, SyncStateRepository, UserRepository
from src.gmail.client import GmailService
from src.sync.watch import WatchManager
from src.users.onboarding import OnboardingService
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


@router.post("/reset")
async def reset_database() -> dict:
    """Reset transient data — clears jobs, emails, events, sync state.

    Preserves user accounts, labels, and settings.
    """
    db = get_db()
    tables = ["jobs", "emails", "email_events", "sync_state"]
    deleted = {}
    for table in tables:
        row = db.execute_one(f"SELECT count(*) as cnt FROM {table}")  # noqa: S608
        deleted[table] = row["cnt"] if row else 0
        db.execute_write(f"DELETE FROM {table}")  # noqa: S608

    total = sum(deleted.values())
    logger.warning("Database reset: deleted %d rows across %s", total, deleted)
    return {"deleted": deleted, "total": total}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --- Auth & Watch Management ---


@router.post("/auth/init")
async def init_auth(request: Request, display_name: str | None = None, migrate_v1: bool = True) -> dict:
    """Bootstrap OAuth and onboard the first user.

    In personal_oauth mode:
    1. Triggers the OAuth browser consent flow (if no token.json yet)
    2. Gets the user's email from Gmail profile
    3. Onboards the user (provisions labels, imports settings)

    Query params:
        display_name: Optional display name for the user
        migrate_v1: If true, imports label IDs from config/label_ids.yml (default: true)
    """
    config = request.app.state.config
    gmail_service = GmailService(config)

    # This triggers the browser OAuth flow if no token exists
    try:
        client = gmail_service.for_user()
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile = client.get_profile()
    email = profile.get("emailAddress")
    if not email:
        raise HTTPException(status_code=500, detail="Could not get email from Gmail profile")

    db = get_db()
    onboarding = OnboardingService(db)

    if migrate_v1:
        user_id = onboarding.onboard_from_existing_config(email, client, display_name)
    else:
        user_id = onboarding.onboard_user(email, client, display_name)

    return {
        "user_id": user_id,
        "email": email,
        "onboarded": True,
        "migrated_v1": migrate_v1,
    }


@router.post("/watch")
async def register_watch(request: Request, user_id: int | None = None) -> dict:
    """Register Gmail watch() for push notifications.

    If user_id is provided, registers for that user only.
    If omitted, registers for all active users.
    """
    config = request.app.state.config
    topic = config.sync.pubsub_topic

    if not topic:
        raise HTTPException(
            status_code=400,
            detail="No pubsub_topic configured in config/app.yml sync section",
        )

    db = get_db()
    gmail_service = GmailService(config)
    watch_mgr = WatchManager(db, gmail_service, topic)

    if user_id is not None:
        users_repo = UserRepository(db)
        user = users_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        success = watch_mgr.renew_watch(user.id, user.email)
        return {"user_id": user.id, "email": user.email, "watch_registered": success}

    results = watch_mgr.renew_all_watches()
    return {"results": results}


@router.get("/watch/status")
async def watch_status() -> list[dict]:
    """Show watch state for all users."""
    db = get_db()
    users_repo = UserRepository(db)
    sync_repo = SyncStateRepository(db)
    users = users_repo.get_active_users()

    statuses = []
    for user in users:
        state = sync_repo.get(user.id)
        statuses.append({
            "user_id": user.id,
            "email": user.email,
            "last_history_id": state["last_history_id"] if state else None,
            "last_sync_at": state["last_sync_at"] if state else None,
            "watch_expiration": state["watch_expiration"] if state else None,
            "watch_resource_id": state["watch_resource_id"] if state else None,
        })
    return statuses
