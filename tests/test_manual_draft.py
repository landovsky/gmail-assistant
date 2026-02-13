"""Tests for the manual draft request feature.

Covers:
- Sync engine detection of needs_response label addition
- Gmail client get_thread_draft() method
- Worker _handle_manual_draft() handler
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.gmail.models import Draft, HistoryRecord, Message, Thread
from src.sync.engine import SyncEngine, SyncResult


def _make_message(
    msg_id: str = "msg_1",
    thread_id: str = "thread_1",
    sender_email: str = "sender@example.com",
    sender_name: str = "Sender",
    subject: str = "Test Subject",
    body: str = "Hello, this is a test.",
) -> Message:
    return Message(
        id=msg_id,
        thread_id=thread_id,
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        body=body,
        internal_date="1700000000000",
        headers={"Message-ID": f"<{msg_id}@mail.gmail.com>"},
    )


def _make_thread(thread_id: str = "thread_1", messages: list[Message] | None = None) -> Thread:
    if messages is None:
        messages = [_make_message(thread_id=thread_id)]
    return Thread(id=thread_id, messages=messages)


def _make_draft(
    draft_id: str = "draft_1",
    thread_id: str = "thread_1",
    body: str = "politely decline",
) -> Draft:
    msg = _make_message(msg_id="draft_msg_1", thread_id=thread_id, body=body)
    return Draft(id=draft_id, message=msg, thread_id=thread_id)


class TestSyncEngineNeedsResponseDetection:
    """Test that _process_history_record detects needs_response label additions."""

    def test_needs_response_label_queues_manual_draft(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {
            "needs_response": "Label_NR",
            "done": "Label_Done",
            "rework": "Label_Rework",
            "waiting": "Label_Waiting",
        }

        record = HistoryRecord(
            id="12345",
            labels_added=[{"message_id": "msg_1", "label_ids": ["Label_NR"]}],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result)

        engine.jobs.enqueue.assert_called_once_with(
            "manual_draft", 1, {"message_id": "msg_1"}
        )
        assert result.label_changes == 1
        assert result.jobs_queued == 1

    def test_done_label_does_not_trigger_manual_draft(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {
            "needs_response": "Label_NR",
            "done": "Label_Done",
            "rework": "Label_Rework",
            "waiting": "Label_Waiting",
        }

        record = HistoryRecord(
            id="12345",
            labels_added=[{"message_id": "msg_1", "label_ids": ["Label_Done"]}],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result)

        # Should enqueue cleanup for done, not manual_draft
        engine.jobs.enqueue.assert_called_once_with(
            "cleanup", 1, {"message_id": "msg_1", "action": "done"}
        )

    def test_both_done_and_needs_response_labels_queue_both(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {
            "needs_response": "Label_NR",
            "done": "Label_Done",
            "rework": "Label_Rework",
            "waiting": "Label_Waiting",
        }

        record = HistoryRecord(
            id="12345",
            labels_added=[
                {"message_id": "msg_1", "label_ids": ["Label_Done", "Label_NR"]},
            ],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result)

        assert engine.jobs.enqueue.call_count == 2
        assert result.label_changes == 2

    def test_no_needs_response_label_configured(self):
        """If needs_response label is not in label_ids, nothing happens."""
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {
            "done": "Label_Done",
            "rework": "Label_Rework",
        }

        record = HistoryRecord(
            id="12345",
            labels_added=[{"message_id": "msg_1", "label_ids": ["Label_NR"]}],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result)

        engine.jobs.enqueue.assert_not_called()


class TestGetThreadDraft:
    """Test UserGmailClient.get_thread_draft() method."""

    def test_finds_matching_draft(self):
        client = MagicMock()
        draft_minimal = Draft(id="draft_1", thread_id="thread_1")
        draft_full = _make_draft(draft_id="draft_1", thread_id="thread_1", body="my notes")
        client.list_drafts.return_value = [draft_minimal]
        client.get_draft.return_value = draft_full

        # Call the actual method logic (simulating it since we can't easily
        # instantiate a real UserGmailClient without Gmail API)
        from src.gmail.client import UserGmailClient

        result = UserGmailClient.get_thread_draft(client, "thread_1")
        client.list_drafts.assert_called_once()
        client.get_draft.assert_called_once_with("draft_1")
        assert result == draft_full

    def test_no_matching_draft(self):
        client = MagicMock()
        draft_other = Draft(id="draft_1", thread_id="thread_other")
        client.list_drafts.return_value = [draft_other]

        from src.gmail.client import UserGmailClient

        result = UserGmailClient.get_thread_draft(client, "thread_1")
        client.list_drafts.assert_called_once()
        client.get_draft.assert_not_called()
        assert result is None

    def test_no_drafts_at_all(self):
        client = MagicMock()
        client.list_drafts.return_value = []

        from src.gmail.client import UserGmailClient

        result = UserGmailClient.get_thread_draft(client, "thread_1")
        assert result is None

    def test_multiple_drafts_returns_first_match(self):
        client = MagicMock()
        draft1 = Draft(id="draft_1", thread_id="thread_other")
        draft2 = Draft(id="draft_2", thread_id="thread_1")
        draft3 = Draft(id="draft_3", thread_id="thread_1")
        client.list_drafts.return_value = [draft1, draft2, draft3]
        client.get_draft.return_value = _make_draft(draft_id="draft_2")

        from src.gmail.client import UserGmailClient

        UserGmailClient.get_thread_draft(client, "thread_1")
        client.get_draft.assert_called_once_with("draft_2")


class TestHandleManualDraft:
    """Test WorkerPool._handle_manual_draft() handler."""

    def _make_worker(self):
        """Create a WorkerPool with all dependencies mocked."""
        from src.tasks.workers import WorkerPool

        pool = MagicMock(spec=WorkerPool)
        pool.emails = MagicMock()
        pool.events = MagicMock()
        pool.labels_repo = MagicMock()
        pool.draft_engine = MagicMock()
        pool.context_gatherer = None
        pool.db = MagicMock()
        return pool

    @pytest.mark.asyncio
    async def test_manual_draft_new_email_with_instructions(self):
        """Email not in DB, user provides notes draft with instructions."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail_client = MagicMock()
        msg = _make_message()
        thread = _make_thread()
        user_draft = _make_draft(body="politely decline, suggest next month")

        gmail_client.get_message.return_value = msg
        gmail_client.get_thread.return_value = thread
        gmail_client.get_thread_draft.return_value = user_draft
        gmail_client.create_draft.return_value = "new_draft_id"

        pool.emails.get_by_thread.side_effect = [None, {"sender_email": "sender@example.com", "sender_name": "Sender", "subject": "Test Subject", "resolved_style": "business"}]
        pool.labels_repo.get_labels.return_value = {
            "needs_response": "Label_NR",
            "outbox": "Label_OB",
        }

        with patch("src.tasks.workers.UserSettings") as mock_settings_cls:
            settings = MagicMock()
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings_cls.return_value = settings

            pool.draft_engine.generate_draft.return_value = "AI generated reply body"

            await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        # Should upsert a new record
        pool.emails.upsert.assert_called_once()
        record = pool.emails.upsert.call_args[0][0]
        assert record.classification == "needs_response"
        assert record.reasoning == "Manually requested by user"

        # Should generate draft with user instructions
        pool.draft_engine.generate_draft.assert_called_once()
        call_kwargs = pool.draft_engine.generate_draft.call_args[1]
        assert call_kwargs["user_instructions"] == "politely decline, suggest next month"

        # Should trash user's notes draft
        gmail_client.trash_draft.assert_called_once_with("draft_1")

        # Should create AI draft
        gmail_client.create_draft.assert_called_once()

        # Should move labels
        gmail_client.batch_modify_labels.assert_called_once()

        # Should update DB
        pool.emails.update_draft.assert_called_once_with(1, "thread_1", "new_draft_id")

        # Should log event
        pool.events.log.assert_called_once()
        assert "draft_created" in pool.events.log.call_args[0]

    @pytest.mark.asyncio
    async def test_manual_draft_existing_fyi_email(self):
        """Email exists in DB as FYI, should reclassify to needs_response."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail_client = MagicMock()
        msg = _make_message()
        thread = _make_thread()

        gmail_client.get_message.return_value = msg
        gmail_client.get_thread.return_value = thread
        gmail_client.get_thread_draft.return_value = None  # No user draft
        gmail_client.create_draft.return_value = "new_draft_id"

        existing_record = {
            "gmail_message_id": "msg_1",
            "sender_email": "sender@example.com",
            "sender_name": "Sender",
            "subject": "Test Subject",
            "snippet": "snippet",
            "received_at": "1700000000000",
            "classification": "fyi",
            "status": "pending",
            "resolved_style": "business",
            "detected_language": "cs",
        }
        pool.emails.get_by_thread.side_effect = [existing_record, existing_record]
        pool.labels_repo.get_labels.return_value = {
            "needs_response": "Label_NR",
            "outbox": "Label_OB",
        }

        with patch("src.tasks.workers.UserSettings") as mock_settings_cls:
            settings = MagicMock()
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings_cls.return_value = settings

            pool.draft_engine.generate_draft.return_value = "AI reply"

            await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        # Should reclassify via upsert
        pool.emails.upsert.assert_called_once()
        record = pool.emails.upsert.call_args[0][0]
        assert record.classification == "needs_response"
        assert "Reclassified" in record.reasoning

        # No user instructions (no draft found)
        call_kwargs = pool.draft_engine.generate_draft.call_args[1]
        assert call_kwargs["user_instructions"] is None

        # Should not trash any draft (none existed)
        gmail_client.trash_draft.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_draft_skips_already_drafted(self):
        """If email is already drafted, skip."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail_client = MagicMock()
        gmail_client.get_message.return_value = _make_message()

        pool.emails.get_by_thread.return_value = {
            "status": "drafted",
            "classification": "needs_response",
        }

        await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        # Should not proceed
        pool.draft_engine.generate_draft.assert_not_called()
        gmail_client.create_draft.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_draft_no_message_id(self):
        """Empty message_id should return early."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {}

        gmail_client = MagicMock()

        await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        gmail_client.get_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_manual_draft_with_scissors_marker(self):
        """User draft with ✂️ marker — extract instruction from above marker."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail_client = MagicMock()
        msg = _make_message()
        thread = _make_thread()
        user_draft = _make_draft(body="politely decline\n\n✂️\n\nsome old content")

        gmail_client.get_message.return_value = msg
        gmail_client.get_thread.return_value = thread
        gmail_client.get_thread_draft.return_value = user_draft
        gmail_client.create_draft.return_value = "new_draft_id"

        pool.emails.get_by_thread.side_effect = [
            None,
            {"sender_email": "sender@example.com", "sender_name": "Sender",
             "subject": "Test", "resolved_style": "business"},
        ]
        pool.labels_repo.get_labels.return_value = {
            "needs_response": "Label_NR",
            "outbox": "Label_OB",
        }

        with patch("src.tasks.workers.UserSettings") as mock_settings_cls:
            settings = MagicMock()
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings_cls.return_value = settings

            pool.draft_engine.generate_draft.return_value = "AI reply"

            await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        call_kwargs = pool.draft_engine.generate_draft.call_args[1]
        assert call_kwargs["user_instructions"] == "politely decline"

    @pytest.mark.asyncio
    async def test_manual_draft_message_not_found(self):
        """If Gmail message doesn't exist, return early."""
        from src.tasks.workers import WorkerPool

        pool = self._make_worker()

        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_missing"}

        gmail_client = MagicMock()
        gmail_client.get_message.return_value = None

        await WorkerPool._handle_manual_draft(pool, job, gmail_client)

        pool.emails.get_by_thread.assert_not_called()
