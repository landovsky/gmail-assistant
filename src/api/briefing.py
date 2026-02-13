"""Briefing API — per-user inbox summary/dashboard."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.db.connection import get_db
from src.db.models import EmailRepository, UserRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/briefing/{user_email}")
async def get_briefing(user_email: str) -> dict:
    """Get inbox briefing/summary for a user."""
    db = get_db()
    users = UserRepository(db)
    user = users.get_by_email(user_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    emails = EmailRepository(db)

    # Build summary by classification
    summary = {}
    for classification in ("needs_response", "action_required", "payment_request", "fyi", "waiting"):
        items = emails.get_by_classification(user.id, classification)
        active = [e for e in items if e["status"] not in ("sent", "archived")]
        summary[classification] = {
            "total": len(items),
            "active": len(active),
            "items": [
                {
                    "thread_id": e["gmail_thread_id"],
                    "subject": e.get("subject", ""),
                    "sender": e.get("sender_email", ""),
                    "status": e.get("status", ""),
                    "confidence": e.get("confidence", ""),
                }
                for e in active[:10]
            ],
        }

    # Pending drafts
    pending = emails.get_pending_drafts(user.id)

    return {
        "user": user.email,
        "summary": summary,
        "pending_drafts": len(pending),
        "action_items": summary["needs_response"]["active"] + summary["action_required"]["active"],
    }
