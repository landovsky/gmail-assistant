"""Application configuration — env vars, YAML files, defaults."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


def _repo_root() -> Path:
    """Find the repository root (directory containing pyproject.toml)."""
    current = Path(__file__).resolve().parent.parent
    if (current / "pyproject.toml").exists():
        return current
    return Path.cwd()


REPO_ROOT = _repo_root()


class AuthMode(str, Enum):
    SERVICE_ACCOUNT = "service_account"
    PERSONAL_OAUTH = "personal_oauth"


class DatabaseBackend(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class AuthConfig(BaseSettings):
    mode: AuthMode = AuthMode.PERSONAL_OAUTH
    credentials_file: Path = REPO_ROOT / "config" / "credentials.json"
    token_file: Path = REPO_ROOT / "config" / "token.json"
    service_account_file: Path = REPO_ROOT / "config" / "service-account-key.json"
    scopes: list[str] = ["https://www.googleapis.com/auth/gmail.modify"]

    model_config = {"env_prefix": "GMA_AUTH_"}


class DatabaseConfig(BaseSettings):
    backend: DatabaseBackend = DatabaseBackend.SQLITE
    sqlite_path: Path = REPO_ROOT / "data" / "inbox.db"
    postgresql_url: str = ""

    model_config = {"env_prefix": "GMA_DB_"}


class LLMSettings(BaseSettings):
    classify_model: str = "claude-haiku-4-5-20251001"
    draft_model: str = "claude-sonnet-4-5-20250929"
    max_classify_tokens: int = 256
    max_draft_tokens: int = 2048

    model_config = {"env_prefix": "GMA_LLM_"}


class SyncConfig(BaseSettings):
    pubsub_topic: str = ""
    fallback_interval_minutes: int = 15
    history_max_results: int = 100
    full_sync_days: int = 10

    model_config = {"env_prefix": "GMA_SYNC_"}


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    webhook_secret: str = ""
    log_level: str = "info"
    worker_concurrency: int = 3

    model_config = {"env_prefix": "GMA_SERVER_"}


class AppConfig(BaseSettings):
    """Top-level application configuration."""

    auth: AuthConfig = Field(default_factory=AuthConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    # Sentry
    sentry_dsn: str = ""

    # Paths
    config_dir: Path = REPO_ROOT / "config"
    data_dir: Path = REPO_ROOT / "data"
    log_dir: Path = REPO_ROOT / "logs"

    model_config = {"env_prefix": "GMA_"}

    @classmethod
    def from_yaml(cls, path: Path | None = None) -> AppConfig:
        """Load config from YAML file, with env var overrides."""
        if path is None:
            path = REPO_ROOT / "config" / "app.yml"

        values: dict[str, Any] = {}
        if path.exists():
            with open(path) as f:
                values = yaml.safe_load(f) or {}

        return cls(**values)


def load_yaml_config(filename: str) -> dict[str, Any]:
    """Load a YAML config file from the config directory."""
    path = REPO_ROOT / "config" / filename
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_contacts_config() -> dict[str, Any]:
    """Load contacts.yml with style overrides, domain overrides, blacklist."""
    return load_yaml_config("contacts.yml")


def load_communication_styles() -> dict[str, Any]:
    """Load communication_styles.yml."""
    return load_yaml_config("communication_styles.yml")


def load_label_ids() -> dict[str, str]:
    """Load label_ids.yml mapping."""
    return load_yaml_config("label_ids.yml")
