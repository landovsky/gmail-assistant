"""Webhook API routes — Gmail Pub/Sub push notifications."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from src.db.connection import get_db
from src.sync.webhook import WebhookHandler

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook/gmail")
async def gmail_webhook(request: Request) -> Response:
    """Receive Gmail Pub/Sub push notifications.

    Google Pub/Sub sends POST with:
    {
      "message": {
        "data": "<base64>",
        "messageId": "...",
        "publishTime": "..."
      },
      "subscription": "projects/.../subscriptions/..."
    }
    """
    try:
        body = await request.json()
        handler = WebhookHandler(get_db())
        success = handler.handle_notification(body)

        if success:
            return Response(status_code=200)
        else:
            return Response(status_code=400, content="Invalid notification")

    except Exception as e:
        logger.error("Webhook error: %s", e)
        return Response(status_code=500, content="Internal error")
