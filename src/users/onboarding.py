"""User onboarding — label provisioning, settings init, initial sync."""

from __future__ import annotations

import logging
from typing import Any

from src.config import AppConfig, load_communication_styles, load_contacts_config, load_label_ids
from src.db.connection import Database
from src.db.models import (
    LabelRepository,
    SyncStateRepository,
    UserRepository,
)
from src.gmail.client import UserGmailClient
from src.users.settings import UserSettings

logger = logging.getLogger(__name__)

# The 8 AI labels to provision
AI_LABELS = {
    "parent": "🤖 AI",
    "needs_response": "🤖 AI/Needs Response",
    "outbox": "🤖 AI/Outbox",
    "rework": "🤖 AI/Rework",
    "action_required": "🤖 AI/Action Required",
    "payment_request": "🤖 AI/Payment Requests",
    "fyi": "🤖 AI/FYI",
    "waiting": "🤖 AI/Waiting",
    "done": "🤖 AI/Done",
}


class OnboardingService:
    """Handles user onboarding: label provisioning, settings init."""

    def __init__(self, db: Database):
        self.db = db
        self.users = UserRepository(db)
        self.labels_repo = LabelRepository(db)
        self.sync_state = SyncStateRepository(db)

    def onboard_user(
        self,
        email: str,
        gmail_client: UserGmailClient,
        display_name: str | None = None,
    ) -> int:
        """Full onboarding flow for a new user.

        1. Create user record
        2. Provision Gmail labels
        3. Initialize settings from YAML defaults
        4. Initialize sync state
        5. Mark onboarded

        Returns user_id.
        """
        # 1. Create user
        existing = self.users.get_by_email(email)
        if existing:
            logger.info("User %s already exists (id=%d)", email, existing.id)
            user_id = existing.id
        else:
            user_id = self.users.create(email, display_name)
            logger.info("Created user %s (id=%d)", email, user_id)

        # 2. Provision labels
        self._provision_labels(user_id, gmail_client)

        # 3. Initialize settings
        self._init_settings(user_id)

        # 4. Initialize sync state
        profile = gmail_client.get_profile()
        history_id = profile.get("historyId", "0")
        self.sync_state.upsert(user_id, str(history_id))

        # 5. Mark onboarded
        self.users.mark_onboarded(user_id)

        logger.info("Onboarding complete for %s (user_id=%d)", email, user_id)
        return user_id

    def onboard_from_existing_config(
        self,
        email: str,
        gmail_client: UserGmailClient,
        display_name: str | None = None,
    ) -> int:
        """Onboard using existing config/label_ids.yml (v1 migration path).

        Skips label creation — imports existing label IDs from YAML.
        """
        existing = self.users.get_by_email(email)
        if existing:
            user_id = existing.id
        else:
            user_id = self.users.create(email, display_name)

        # Import label IDs from YAML
        label_ids = load_label_ids()
        for key, gmail_id in label_ids.items():
            if key in AI_LABELS and gmail_id != "Label_XXXX":
                self.labels_repo.set_label(user_id, key, gmail_id, AI_LABELS.get(key, key))

        # Initialize settings
        self._init_settings(user_id)

        # Sync state
        profile = gmail_client.get_profile()
        history_id = profile.get("historyId", "0")
        self.sync_state.upsert(user_id, str(history_id))

        self.users.mark_onboarded(user_id)
        logger.info("Onboarded %s from existing config (user_id=%d)", email, user_id)
        return user_id

    def _provision_labels(self, user_id: int, gmail_client: UserGmailClient) -> None:
        """Create Gmail labels and store their IDs."""
        for key, name in AI_LABELS.items():
            label_id = gmail_client.get_or_create_label(name)
            if label_id:
                self.labels_repo.set_label(user_id, key, label_id, name)
                logger.info("Label %s → %s", name, label_id)
            else:
                logger.error("Failed to provision label: %s", name)

    def _init_settings(self, user_id: int) -> None:
        """Initialize user settings from YAML defaults."""
        settings = UserSettings(self.db, user_id)
        settings.import_from_yaml()
