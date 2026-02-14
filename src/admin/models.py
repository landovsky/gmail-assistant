"""SQLAlchemy models for admin UI — read-only view wrappers over existing tables."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, relationship


class EpochOrDatetime(TypeDecorator):
    """Handle datetime columns that may store epoch-millis integers or ISO strings."""

    impl = String
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, int):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class UserModel(Base):
    """User model for admin UI."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String)
    is_active = Column(Integer, default=1)
    onboarded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    labels = relationship("UserLabelModel", back_populates="user")
    settings = relationship("UserSettingModel", back_populates="user")
    emails = relationship("EmailModel", back_populates="user")
    llm_calls = relationship("LLMCallModel", back_populates="user")


class UserLabelModel(Base):
    """User label mappings for admin UI."""

    __tablename__ = "user_labels"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    label_key = Column(String, primary_key=True)
    gmail_label_id = Column(String, nullable=False)
    gmail_label_name = Column(String)

    # Relationships
    user = relationship("UserModel", back_populates="labels")


class UserSettingModel(Base):
    """User settings for admin UI."""

    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    setting_key = Column(String, primary_key=True)
    setting_value = Column(Text)

    # Relationships
    user = relationship("UserModel", back_populates="settings")


class SyncStateModel(Base):
    """Gmail sync state for admin UI."""

    __tablename__ = "sync_state"

    # user_id is the actual PK in the schema
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    last_history_id = Column(String)
    last_sync_at = Column(DateTime)
    watch_resource_id = Column(String)
    watch_expiration = Column(EpochOrDatetime)


class EmailModel(Base):
    """Email record for admin UI."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gmail_thread_id = Column(String, nullable=False)
    gmail_message_id = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    sender_name = Column(String)
    subject = Column(String)
    snippet = Column(String)
    received_at = Column(EpochOrDatetime)
    classification = Column(String, nullable=False)
    confidence = Column(String, default="medium")
    reasoning = Column(Text)
    detected_language = Column(String, default="cs")
    resolved_style = Column(String, default="business")
    message_count = Column(Integer, default=1)
    status = Column(String, default="pending")
    draft_id = Column(String)
    rework_count = Column(Integer, default=0)
    last_rework_instruction = Column(Text)
    vendor_name = Column(String)
    processed_at = Column(DateTime)
    drafted_at = Column(DateTime)
    acted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("UserModel", back_populates="emails")


class EmailEventModel(Base):
    """Email event audit log for admin UI."""

    __tablename__ = "email_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    gmail_thread_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    detail = Column(Text)
    label_id = Column(String)
    draft_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # No FK to emails — linked by gmail_thread_id at query time


class LLMCallModel(Base):
    """LLM call log for admin UI."""

    __tablename__ = "llm_calls"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    gmail_thread_id = Column(String)
    call_type = Column(String, nullable=False)
    model = Column(String, nullable=False)
    system_prompt = Column(Text)
    user_message = Column(Text)
    response_text = Column(Text)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserModel", back_populates="llm_calls")


class JobModel(Base):
    """Job queue for admin UI."""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_type = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    payload = Column(Text)
    status = Column(String, default="pending")
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
