"""Per-user settings management — DB-stored with YAML fallback for lite mode."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config import load_communication_styles, load_contacts_config, load_label_ids
from src.db.connection import Database
from src.db.models import SettingsRepository

logger = logging.getLogger(__name__)


class UserSettings:
    """Manages per-user settings, backed by DB with YAML fallback."""

    def __init__(self, db: Database, user_id: int):
        self.repo = SettingsRepository(db)
        self.user_id = user_id

    def get(self, key: str, default: Any = None) -> Any:
        val = self.repo.get(self.user_id, key)
        return val if val is not None else default

    def set(self, key: str, value: Any) -> None:
        self.repo.set(self.user_id, key, value)

    def get_all(self) -> dict[str, Any]:
        return self.repo.get_all(self.user_id)

    @property
    def communication_styles(self) -> dict[str, Any]:
        """Get styles — DB first, then YAML fallback."""
        db_val = self.get("communication_styles")
        if db_val:
            return db_val
        return load_communication_styles()

    @property
    def contacts(self) -> dict[str, Any]:
        """Get contacts config — DB first, then YAML fallback."""
        db_val = self.get("contacts")
        if db_val:
            return db_val
        return load_contacts_config()

    @property
    def blacklist(self) -> list[str]:
        contacts = self.contacts
        return contacts.get("blacklist", [])

    @property
    def sign_off_name(self) -> str:
        return self.get("sign_off_name", "")

    @property
    def default_language(self) -> str:
        return self.get("default_language", "cs")

    def import_from_yaml(self) -> None:
        """Import settings from YAML config files into the database."""
        styles = load_communication_styles()
        if styles:
            self.set("communication_styles", styles)
            logger.info("Imported communication_styles for user %d", self.user_id)

        contacts = load_contacts_config()
        if contacts:
            self.set("contacts", contacts)
            logger.info("Imported contacts config for user %d", self.user_id)

        label_ids = load_label_ids()
        if label_ids:
            self.set("label_ids_yaml", label_ids)
            logger.info("Imported label_ids for user %d", self.user_id)
