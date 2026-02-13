"""Watch renewal — keeps Gmail push notifications active."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.db.connection import Database
from src.db.models import LabelsRepository, SyncStateRepository, UserRepository
from src.gmail.client import GmailService

logger = logging.getLogger(__name__)


class WatchManager:
    """Manages Gmail watch() subscriptions for push notifications."""

    def __init__(self, db: Database, gmail_service: GmailService, pubsub_topic: str):
        self.db = db
        self.users = UserRepository(db)
        self.sync_state = SyncStateRepository(db)
        self.gmail_service = gmail_service
        self.pubsub_topic = pubsub_topic

    def renew_all_watches(self) -> dict[str, bool]:
        """Renew watch() for all active users. Returns {email: success}."""
        results = {}
        users = self.users.get_active_users()

        for user in users:
            success = self.renew_watch(user.id, user.email)
            results[user.email] = success

        return results

    def renew_watch(self, user_id: int, user_email: str) -> bool:
        """Renew watch() for a single user."""
        if not self.pubsub_topic:
            logger.debug("No Pub/Sub topic configured, skipping watch for %s", user_email)
            return False

        try:
            client = self.gmail_service.for_user(user_email)

            # Include INBOX + user-action labels so Gmail pushes notifications
            # for both new mail and manual label changes (needs_response, rework, done)
            labels_repo = LabelsRepository(self.db)
            label_ids = labels_repo.get_labels(user_id)
            watch_labels = ["INBOX"]
            for key in ("needs_response", "rework", "done"):
                if lid := label_ids.get(key):
                    watch_labels.append(lid)

            response = client.watch(self.pubsub_topic, label_ids=watch_labels)

            if response:
                self.sync_state.set_watch(
                    user_id, response.history_id, response.expiration
                )
                logger.info("Watch renewed for %s (expires %s)", user_email, response.expiration)
                return True
            return False

        except Exception as e:
            logger.error("Failed to renew watch for %s: %s", user_email, e)
            return False

    def get_expiring_watches(self, hours_before: int = 24) -> list[int]:
        """Get user IDs whose watches expire within N hours."""
        threshold = datetime.now(timezone.utc) + timedelta(hours=hours_before)
        rows = self.db.execute(
            "SELECT user_id FROM sync_state WHERE watch_expiration < ? AND watch_expiration IS NOT NULL",
            (threshold.isoformat(),),
        )
        return [r["user_id"] for r in rows]
