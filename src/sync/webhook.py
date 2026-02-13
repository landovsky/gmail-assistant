"""Pub/Sub webhook handler for Gmail push notifications."""

from __future__ import annotations

import base64
import json
import logging

from src.db.connection import Database
from src.db.models import JobRepository, UserRepository

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles Gmail Pub/Sub push notifications."""

    def __init__(self, db: Database):
        self.db = db
        self.users = UserRepository(db)
        self.jobs = JobRepository(db)

    def handle_notification(self, body: dict) -> bool:
        """Process a Pub/Sub push notification.

        Notification format:
        {
          "message": {
            "data": base64({emailAddress: "user@org.com", historyId: 12345}),
            "messageId": "...",
            "publishTime": "..."
          },
          "subscription": "projects/.../subscriptions/..."
        }
        """
        try:
            message = body.get("message", {})
            data_b64 = message.get("data", "")
            if not data_b64:
                logger.warning("Empty notification data")
                return False

            data = json.loads(base64.b64decode(data_b64))
            email_address = data.get("emailAddress", "")
            history_id = str(data.get("historyId", ""))

            if not email_address:
                logger.warning("No emailAddress in notification")
                return False

            # Look up user
            user = self.users.get_by_email(email_address)
            if not user:
                logger.warning("Unknown user in notification: %s", email_address)
                return False

            # Queue sync job
            self.jobs.enqueue("sync", user.id, {"history_id": history_id})
            logger.info("Queued sync for %s (history_id=%s)", email_address, history_id)
            return True

        except Exception as e:
            logger.error("Failed to process notification: %s", e)
            return False
