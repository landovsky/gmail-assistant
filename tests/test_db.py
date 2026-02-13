"""Tests for database layer."""

import tempfile
from pathlib import Path

import pytest

from src.config import AppConfig, DatabaseConfig, DatabaseBackend
from src.db.connection import Database
from src.db.models import (
    EmailRecord,
    EmailRepository,
    EventRepository,
    JobRepository,
    LabelRepository,
    SettingsRepository,
    UserRepository,
)


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    config = AppConfig()
    config.database = DatabaseConfig(
        backend=DatabaseBackend.SQLITE,
        sqlite_path=tmp_path / "test.db",
    )
    database = Database(config)
    database.initialize_schema()
    return database


class TestUserRepository:
    def test_create_and_get(self, db):
        repo = UserRepository(db)
        user_id = repo.create("test@example.com", "Test User")
        assert user_id > 0

        user = repo.get_by_email("test@example.com")
        assert user is not None
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"

    def test_get_nonexistent(self, db):
        repo = UserRepository(db)
        assert repo.get_by_email("nobody@example.com") is None

    def test_get_active_users(self, db):
        repo = UserRepository(db)
        repo.create("user1@example.com")
        repo.create("user2@example.com")
        users = repo.get_active_users()
        assert len(users) == 2


class TestLabelRepository:
    def test_set_and_get(self, db):
        UserRepository(db).create("test@example.com")
        repo = LabelRepository(db)
        repo.set_label(1, "needs_response", "Label_34", "🤖 AI/Needs Response")
        repo.set_label(1, "fyi", "Label_39", "🤖 AI/FYI")

        labels = repo.get_labels(1)
        assert labels["needs_response"] == "Label_34"
        assert labels["fyi"] == "Label_39"


class TestEmailRepository:
    def test_upsert_and_get(self, db):
        UserRepository(db).create("test@example.com")
        repo = EmailRepository(db)

        record = EmailRecord(
            user_id=1,
            gmail_thread_id="thread_123",
            gmail_message_id="msg_456",
            sender_email="sender@example.com",
            subject="Test Subject",
            classification="needs_response",
            confidence="high",
        )
        repo.upsert(record)

        result = repo.get_by_thread(1, "thread_123")
        assert result is not None
        assert result["classification"] == "needs_response"
        assert result["sender_email"] == "sender@example.com"

    def test_get_pending_drafts(self, db):
        UserRepository(db).create("test@example.com")
        repo = EmailRepository(db)

        for i in range(3):
            record = EmailRecord(
                user_id=1,
                gmail_thread_id=f"thread_{i}",
                gmail_message_id=f"msg_{i}",
                sender_email="sender@example.com",
                classification="needs_response" if i < 2 else "fyi",
            )
            repo.upsert(record)

        pending = repo.get_pending_drafts(1)
        assert len(pending) == 2

    def test_update_status(self, db):
        UserRepository(db).create("test@example.com")
        repo = EmailRepository(db)

        record = EmailRecord(
            user_id=1,
            gmail_thread_id="thread_1",
            gmail_message_id="msg_1",
            sender_email="sender@example.com",
            classification="needs_response",
        )
        repo.upsert(record)
        repo.update_status(1, "thread_1", "drafted")

        result = repo.get_by_thread(1, "thread_1")
        assert result["status"] == "drafted"


class TestEventRepository:
    def test_log_and_retrieve(self, db):
        UserRepository(db).create("test@example.com")
        repo = EventRepository(db)

        repo.log(1, "thread_1", "classified", "needs_response (high)")
        repo.log(1, "thread_1", "draft_created", "Draft with business style")

        events = repo.get_thread_events(1, "thread_1")
        assert len(events) == 2
        assert events[0]["event_type"] == "classified"
        assert events[1]["event_type"] == "draft_created"


class TestJobRepository:
    def test_enqueue_and_claim(self, db):
        UserRepository(db).create("test@example.com")
        repo = JobRepository(db)

        repo.enqueue("classify", 1, {"message_id": "msg_1"})
        job = repo.claim_next()

        assert job is not None
        assert job.job_type == "classify"
        assert job.payload["message_id"] == "msg_1"

    def test_claim_empty_queue(self, db):
        repo = JobRepository(db)
        assert repo.claim_next() is None

    def test_complete_job(self, db):
        UserRepository(db).create("test@example.com")
        repo = JobRepository(db)

        repo.enqueue("sync", 1)
        job = repo.claim_next()
        repo.complete(job.id)

        # Should not be claimable again
        assert repo.claim_next() is None

    def test_retry_job(self, db):
        UserRepository(db).create("test@example.com")
        repo = JobRepository(db)

        repo.enqueue("classify", 1)
        job = repo.claim_next()
        repo.retry(job.id, "temporary error")

        # Should be claimable again
        job2 = repo.claim_next()
        assert job2 is not None
        assert job2.attempts == 2


class TestSettingsRepository:
    def test_set_and_get(self, db):
        UserRepository(db).create("test@example.com")
        repo = SettingsRepository(db)

        repo.set(1, "default_language", "cs")
        assert repo.get(1, "default_language") == "cs"

    def test_get_nonexistent(self, db):
        repo = SettingsRepository(db)
        assert repo.get(999, "missing") is None

    def test_json_value(self, db):
        UserRepository(db).create("test@example.com")
        repo = SettingsRepository(db)

        styles = {"default": "business", "styles": {"formal": {"rules": ["be polite"]}}}
        repo.set(1, "communication_styles", styles)

        result = repo.get(1, "communication_styles")
        assert result["default"] == "business"
        assert "formal" in result["styles"]
