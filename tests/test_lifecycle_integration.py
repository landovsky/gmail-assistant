"""Tests for lifecycle manager methods and worker handlers.

Covers:
- LifecycleManager.handle_done: removes AI labels + INBOX, updates DB
- LifecycleManager.handle_sent_detection: detects sent draft, updates status
- LifecycleManager.handle_rework: regenerates draft, enforces limit
- WorkerPool._handle_cleanup: dispatches to lifecycle based on action
- WorkerPool._handle_classify: enqueues draft or marks skipped
- WorkerPool._handle_rework: resolves thread_id and delegates to lifecycle
- Sync engine: rework/deletion detection
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from src.gmail.models import Draft, HistoryRecord, Message, Thread
from src.sync.engine import SyncEngine, SyncResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_thread(
    thread_id: str = "thread_1", messages: list[Message] | None = None
) -> Thread:
    if messages is None:
        messages = [_make_message(thread_id=thread_id)]
    return Thread(id=thread_id, messages=messages)


def _make_lifecycle():
    """Create a LifecycleManager with mocked dependencies."""
    from src.lifecycle.manager import LifecycleManager

    db = MagicMock()
    draft_engine = MagicMock()
    context_gatherer = MagicMock()
    mgr = LifecycleManager(db, draft_engine=draft_engine, context_gatherer=context_gatherer)
    mgr.emails = MagicMock()
    mgr.events = MagicMock()
    mgr.labels = MagicMock()
    return mgr


def _make_worker():
    """Create a WorkerPool with all dependencies mocked."""
    from src.tasks.workers import WorkerPool

    pool = MagicMock(spec=WorkerPool)
    pool.emails = MagicMock()
    pool.events = MagicMock()
    pool.labels_repo = MagicMock()
    pool.jobs = MagicMock()
    pool.draft_engine = MagicMock()
    pool.context_gatherer = None
    pool.db = MagicMock()
    pool.lifecycle = MagicMock()
    pool.classification_engine = MagicMock()
    return pool


# ===========================================================================
# LifecycleManager.handle_done
# ===========================================================================


class TestHandleDone:
    """handle_done removes all AI sub-labels + INBOX, keeps Done label."""

    def test_removes_ai_labels_and_inbox(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.labels.get_labels.return_value = {
            "needs_response": "L_NR",
            "outbox": "L_OB",
            "rework": "L_RW",
            "action_required": "L_AR",
            "payment_request": "L_PR",
            "fyi": "L_FYI",
            "waiting": "L_W",
            "done": "L_DONE",
        }

        thread = _make_thread(messages=[
            _make_message(msg_id="m1"),
            _make_message(msg_id="m2"),
        ])
        gmail.get_thread.return_value = thread

        result = mgr.handle_done(1, "thread_1", gmail)

        assert result is True
        gmail.batch_modify_labels.assert_called_once()
        call_args = gmail.batch_modify_labels.call_args
        msg_ids = call_args[0][0]
        remove = call_args[1]["remove"] if "remove" in call_args[1] else call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("remove")

        assert set(msg_ids) == {"m1", "m2"}
        # Should remove all 7 AI sub-labels + INBOX
        assert "INBOX" in remove
        assert "L_NR" in remove
        assert "L_OB" in remove
        assert "L_FYI" in remove
        assert "L_W" in remove
        # Should NOT remove Done label
        assert "L_DONE" not in remove

    def test_updates_db_status_to_archived(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()
        mgr.labels.get_labels.return_value = {"done": "L_DONE"}
        gmail.get_thread.return_value = _make_thread()

        mgr.handle_done(1, "thread_1", gmail)

        mgr.emails.update_status.assert_called_once_with(
            1, "thread_1", "archived", acted_at="CURRENT_TIMESTAMP"
        )

    def test_logs_archived_event(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()
        mgr.labels.get_labels.return_value = {"done": "L_DONE"}
        gmail.get_thread.return_value = _make_thread()

        mgr.handle_done(1, "thread_1", gmail)

        mgr.events.log.assert_called_once()
        args = mgr.events.log.call_args[0]
        assert args[0] == 1
        assert args[1] == "thread_1"
        assert args[2] == "archived"

    def test_thread_not_found_returns_false(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()
        mgr.labels.get_labels.return_value = {"done": "L_DONE"}
        gmail.get_thread.return_value = None

        result = mgr.handle_done(1, "thread_1", gmail)

        assert result is False
        gmail.batch_modify_labels.assert_not_called()
        mgr.emails.update_status.assert_not_called()

    def test_works_when_email_not_in_db(self):
        """handle_done should work even if email isn't in the DB (e.g. manually labeled)."""
        mgr = _make_lifecycle()
        gmail = MagicMock()
        mgr.labels.get_labels.return_value = {"fyi": "L_FYI", "done": "L_DONE"}
        gmail.get_thread.return_value = _make_thread()

        # update_status may silently affect 0 rows — that's fine
        result = mgr.handle_done(1, "thread_1", gmail)

        assert result is True
        gmail.batch_modify_labels.assert_called_once()


# ===========================================================================
# LifecycleManager.handle_sent_detection
# ===========================================================================


class TestHandleSentDetection:
    """handle_sent_detection detects when a draft disappears (was sent)."""

    def test_draft_gone_marks_sent_and_removes_outbox(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = {
            "draft_id": "draft_123",
            "sender_email": "s@e.com",
        }
        gmail.get_draft.return_value = None  # Draft gone — was sent
        mgr.labels.get_labels.return_value = {"outbox": "L_OB"}
        gmail.get_thread.return_value = _make_thread(messages=[
            _make_message(msg_id="m1"),
        ])

        result = mgr.handle_sent_detection(1, "thread_1", gmail)

        assert result is True
        gmail.batch_modify_labels.assert_called_once_with(["m1"], remove=["L_OB"])
        mgr.emails.update_status.assert_called_once_with(
            1, "thread_1", "sent", acted_at="CURRENT_TIMESTAMP"
        )
        mgr.events.log.assert_called_once()
        assert "sent_detected" in mgr.events.log.call_args[0]

    def test_draft_still_exists_returns_false(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = {"draft_id": "draft_123"}
        gmail.get_draft.return_value = MagicMock()  # Draft still there

        result = mgr.handle_sent_detection(1, "thread_1", gmail)

        assert result is False
        mgr.emails.update_status.assert_not_called()

    def test_no_email_record_returns_false(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = None

        result = mgr.handle_sent_detection(1, "thread_1", gmail)

        assert result is False
        gmail.get_draft.assert_not_called()

    def test_no_draft_id_returns_false(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = {"draft_id": None}

        result = mgr.handle_sent_detection(1, "thread_1", gmail)

        assert result is False

    def test_no_outbox_label_still_updates_db(self):
        """Even without outbox label, status should update to sent."""
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = {"draft_id": "draft_123"}
        gmail.get_draft.return_value = None
        mgr.labels.get_labels.return_value = {}  # No outbox label configured

        result = mgr.handle_sent_detection(1, "thread_1", gmail)

        assert result is True
        gmail.batch_modify_labels.assert_not_called()
        mgr.emails.update_status.assert_called_once()


# ===========================================================================
# LifecycleManager.handle_rework
# ===========================================================================


class TestHandleRework:
    """handle_rework regenerates draft with user instructions."""

    def _setup_rework(self, rework_count: int = 0):
        mgr = _make_lifecycle()
        gmail = MagicMock()

        mgr.emails.get_by_thread.return_value = {
            "sender_email": "sender@e.com",
            "sender_name": "Sender",
            "subject": "Test",
            "draft_id": "old_draft",
            "rework_count": rework_count,
            "resolved_style": "business",
            "gmail_message_id": "msg_1",
        }
        mgr.labels.get_labels.return_value = {
            "rework": "L_RW",
            "outbox": "L_OB",
            "action_required": "L_AR",
        }

        draft_msg = _make_message(body="Current draft content")
        gmail.get_draft.return_value = Draft(id="old_draft", message=draft_msg, thread_id="thread_1")
        gmail.get_thread.return_value = _make_thread()
        gmail.create_draft.return_value = "new_draft_id"

        mgr.draft_engine.rework_draft.return_value = ("Reworked body", "make it shorter")
        mgr.context_gatherer = None

        return mgr, gmail

    def test_rework_creates_new_draft(self):
        mgr, gmail = self._setup_rework(rework_count=0)

        result = mgr.handle_rework(1, "thread_1", gmail)

        assert result is True
        mgr.draft_engine.rework_draft.assert_called_once()
        gmail.trash_draft.assert_called_once_with("old_draft")
        gmail.create_draft.assert_called_once()

    def test_rework_moves_label_to_outbox(self):
        mgr, gmail = self._setup_rework(rework_count=0)

        mgr.handle_rework(1, "thread_1", gmail)

        gmail.batch_modify_labels.assert_called_once()
        call_kwargs = gmail.batch_modify_labels.call_args
        assert "L_OB" in call_kwargs[1].get("add", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else [])
        assert "L_RW" in call_kwargs[1].get("remove", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else [])

    def test_rework_updates_db(self):
        mgr, gmail = self._setup_rework(rework_count=1)

        mgr.handle_rework(1, "thread_1", gmail)

        mgr.emails.increment_rework.assert_called_once_with(
            1, "thread_1", "new_draft_id", "make it shorter"
        )

    def test_rework_logs_event(self):
        mgr, gmail = self._setup_rework(rework_count=0)

        mgr.handle_rework(1, "thread_1", gmail)

        # Should log both draft_trashed and draft_reworked events
        event_types = [c[0][2] for c in mgr.events.log.call_args_list]
        assert "draft_trashed" in event_types
        assert "draft_reworked" in event_types

    def test_rework_limit_moves_to_action_required(self):
        mgr, gmail = self._setup_rework(rework_count=3)

        result = mgr.handle_rework(1, "thread_1", gmail)

        assert result is True
        # Should NOT generate a new draft
        mgr.draft_engine.rework_draft.assert_not_called()
        # Should move Rework → Action Required
        gmail.batch_modify_labels.assert_called_once()
        call_kwargs = gmail.batch_modify_labels.call_args
        add_labels = call_kwargs[1].get("add", [])
        remove_labels = call_kwargs[1].get("remove", [])
        assert "L_AR" in add_labels
        assert "L_RW" in remove_labels
        # Should update status to skipped
        mgr.emails.update_status.assert_called_once_with(1, "thread_1", "skipped")

    def test_last_rework_moves_to_action_required(self):
        """On rework #3 (count=2), label should go to action_required, not outbox."""
        mgr, gmail = self._setup_rework(rework_count=2)

        mgr.handle_rework(1, "thread_1", gmail)

        call_kwargs = gmail.batch_modify_labels.call_args
        add_labels = call_kwargs[1].get("add", [])
        assert "L_AR" in add_labels

    def test_no_draft_engine_returns_false(self):
        mgr = _make_lifecycle()
        mgr.draft_engine = None
        gmail = MagicMock()

        result = mgr.handle_rework(1, "thread_1", gmail)

        assert result is False

    def test_no_email_record_returns_false(self):
        mgr = _make_lifecycle()
        gmail = MagicMock()
        mgr.emails.get_by_thread.return_value = None

        result = mgr.handle_rework(1, "thread_1", gmail)

        assert result is False

    def test_thread_not_found_returns_false(self):
        mgr, gmail = self._setup_rework(rework_count=0)
        gmail.get_thread.return_value = None

        result = mgr.handle_rework(1, "thread_1", gmail)

        assert result is False


# ===========================================================================
# WorkerPool._handle_cleanup
# ===========================================================================


class TestHandleCleanup:
    """Worker cleanup handler dispatches to lifecycle based on action."""

    @pytest.mark.asyncio
    async def test_done_action_calls_handle_done(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "done", "thread_id": "thread_1", "message_id": "msg_1"}
        gmail = MagicMock()

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_done.assert_called_once_with(1, "thread_1", gmail)

    @pytest.mark.asyncio
    async def test_check_sent_action_calls_handle_sent_detection(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "check_sent", "thread_id": "thread_1", "message_id": "msg_1"}
        gmail = MagicMock()

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_sent_detection.assert_called_once_with(1, "thread_1", gmail)

    @pytest.mark.asyncio
    async def test_missing_thread_id_skips_done(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "done", "message_id": "msg_1"}  # No thread_id
        gmail = MagicMock()

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_done.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_thread_id_skips_done(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "done", "thread_id": "", "message_id": "msg_1"}
        gmail = MagicMock()

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_done.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_action_does_nothing(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "unknown", "thread_id": "thread_1"}
        gmail = MagicMock()

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_done.assert_not_called()
        pool.lifecycle.handle_sent_detection.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_sent_resolves_thread_id_from_db(self):
        """check_sent payloads lack thread_id — worker should resolve from DB."""
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "check_sent", "message_id": "msg_1"}  # No thread_id
        gmail = MagicMock()

        pool.emails.get_by_message.return_value = {
            "gmail_thread_id": "thread_1",
            "draft_id": "draft_1",
        }

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.emails.get_by_message.assert_called_once_with(1, "msg_1")
        pool.lifecycle.handle_sent_detection.assert_called_once_with(1, "thread_1", gmail)

    @pytest.mark.asyncio
    async def test_check_sent_no_db_record_skips(self):
        """check_sent with no thread_id and no DB record should skip."""
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"action": "check_sent", "message_id": "msg_unknown"}
        gmail = MagicMock()

        pool.emails.get_by_message.return_value = None

        await WorkerPool._handle_cleanup(pool, job, gmail)

        pool.lifecycle.handle_sent_detection.assert_not_called()


# ===========================================================================
# WorkerPool._handle_classify
# ===========================================================================


class TestHandleClassify:
    """Worker classify handler enqueues draft or marks skipped."""

    def _setup_classify(self, category: str = "needs_response"):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail = MagicMock()
        gmail.get_message.return_value = _make_message()

        pool.emails.get_by_thread.return_value = None  # Not yet classified

        classify_result = MagicMock()
        classify_result.category = category
        classify_result.confidence = "high"
        classify_result.reasoning = "Test reasoning"
        classify_result.source = "llm"
        classify_result.detected_language = "en"
        classify_result.resolved_style = "business"
        pool.classification_engine.classify.return_value = classify_result

        pool.labels_repo.get_labels.return_value = {
            "needs_response": "L_NR",
            "fyi": "L_FYI",
        }

        return pool, job, gmail

    @pytest.mark.asyncio
    async def test_needs_response_enqueues_draft(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("needs_response")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.jobs.enqueue.assert_called_once_with(
            "draft", 1, {"thread_id": "thread_1", "message_id": "msg_1"}
        )
        pool.emails.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_fyi_marks_skipped(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("fyi")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.jobs.enqueue.assert_not_called()
        pool.emails.update_status.assert_called_once_with(1, "thread_1", "skipped")

    @pytest.mark.asyncio
    async def test_action_required_marks_skipped(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("action_required")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.jobs.enqueue.assert_not_called()
        pool.emails.update_status.assert_called_once_with(1, "thread_1", "skipped")

    @pytest.mark.asyncio
    async def test_already_classified_skips(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("needs_response")
        pool.emails.get_by_thread.return_value = {"id": 1}  # Already exists

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.classification_engine.classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_message_id_returns_early(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {}
        gmail = MagicMock()

        await WorkerPool._handle_classify(pool, job, gmail)

        gmail.get_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_not_found_returns_early(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}
        gmail = MagicMock()
        gmail.get_message.return_value = None

        await WorkerPool._handle_classify(pool, job, gmail)

        pool.classification_engine.classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_stores_email_record(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("fyi")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.emails.upsert.assert_called_once()
        record = pool.emails.upsert.call_args[0][0]
        assert record.classification == "fyi"
        assert record.gmail_thread_id == "thread_1"

    @pytest.mark.asyncio
    async def test_applies_gmail_label(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("fyi")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        gmail.modify_labels.assert_called_once_with("msg_1", add=["L_FYI"])

    @pytest.mark.asyncio
    async def test_logs_classified_event(self):
        from src.tasks.workers import WorkerPool

        pool, job, gmail = self._setup_classify("fyi")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.blacklist = []
            settings.contacts = {}
            settings.communication_styles = {}
            mock_settings.return_value = settings

            await WorkerPool._handle_classify(pool, job, gmail)

        pool.events.log.assert_called_once()
        args = pool.events.log.call_args[0]
        assert args[2] == "classified"


# ===========================================================================
# WorkerPool._handle_rework
# ===========================================================================


class TestHandleReworkWorker:
    """Worker rework handler resolves thread_id from message and delegates."""

    @pytest.mark.asyncio
    async def test_delegates_to_lifecycle(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_1"}

        gmail = MagicMock()
        gmail.get_message.return_value = _make_message(thread_id="thread_1")

        with patch("src.tasks.workers.UserSettings") as mock_settings:
            settings = MagicMock()
            settings.communication_styles = {"business": {}}
            mock_settings.return_value = settings

            await WorkerPool._handle_rework(pool, job, gmail)

        pool.lifecycle.handle_rework.assert_called_once()
        call_args = pool.lifecycle.handle_rework.call_args[0]
        assert call_args[0] == 1  # user_id
        assert call_args[1] == "thread_1"  # thread_id

    @pytest.mark.asyncio
    async def test_message_not_found_returns_early(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {"message_id": "msg_missing"}

        gmail = MagicMock()
        gmail.get_message.return_value = None

        await WorkerPool._handle_rework(pool, job, gmail)

        pool.lifecycle.handle_rework.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_message_id_returns_early(self):
        from src.tasks.workers import WorkerPool

        pool = _make_worker()
        job = MagicMock()
        job.user_id = 1
        job.payload = {}

        gmail = MagicMock()

        await WorkerPool._handle_rework(pool, job, gmail)

        gmail.get_message.assert_not_called()


# ===========================================================================
# Sync engine: rework and deletion detection
# ===========================================================================


class TestSyncEngineReworkDetection:
    """Sync engine creates rework job when Rework label is added."""

    def test_rework_label_queues_rework_job(self):
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
                {"message_id": "msg_1", "thread_id": "thread_1", "label_ids": ["Label_Rework"]}
            ],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_called_once_with(
            "rework", 1, {"message_id": "msg_1"}
        )
        assert result.label_changes == 1

    def test_deduplicates_rework_for_same_thread(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {"rework": "Label_Rework"}

        record = HistoryRecord(
            id="12345",
            labels_added=[
                {"message_id": "msg_1", "thread_id": "thread_1", "label_ids": ["Label_Rework"]},
                {"message_id": "msg_2", "thread_id": "thread_1", "label_ids": ["Label_Rework"]},
            ],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_called_once()


class TestSyncEngineDeletionDetection:
    """Sync engine creates check_sent cleanup job on message deletion."""

    def test_deletion_queues_check_sent(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {"done": "Label_Done"}

        record = HistoryRecord(
            id="12345",
            messages_deleted=["msg_deleted_1"],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_called_once_with(
            "cleanup", 1, {"message_id": "msg_deleted_1", "action": "check_sent"}
        )
        assert result.deletions == 1

    def test_multiple_deletions_queue_multiple_jobs(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()

        label_ids = {}

        record = HistoryRecord(
            id="12345",
            messages_deleted=["msg_1", "msg_2", "msg_3"],
        )

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        assert engine.jobs.enqueue.call_count == 3
        assert result.deletions == 3


class TestSyncEngineNewMessageDetection:
    """Sync engine creates classify job for new inbox messages."""

    def test_inbox_message_queues_classify(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.router = None

        msg = MagicMock()
        msg.id = "msg_1"
        msg.thread_id = "thread_1"
        msg.label_ids = ["INBOX"]
        msg.sender_email = "s@e.com"
        msg.subject = "Hi"
        msg.headers = {}
        msg.body = "Hello"

        record = HistoryRecord(id="12345", messages_added=[msg])
        label_ids = {}

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_called_once_with(
            "classify", 1, {"message_id": "msg_1", "thread_id": "thread_1"}
        )
        assert result.new_messages == 1

    def test_non_inbox_message_ignored(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.router = None

        msg = MagicMock()
        msg.id = "msg_1"
        msg.thread_id = "thread_1"
        msg.label_ids = ["SENT"]  # Not INBOX

        record = HistoryRecord(id="12345", messages_added=[msg])
        label_ids = {}

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_not_called()

    def test_deduplicates_classify_for_same_thread(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.router = None

        msg1 = MagicMock()
        msg1.id = "msg_1"
        msg1.thread_id = "thread_1"
        msg1.label_ids = ["INBOX"]

        msg2 = MagicMock()
        msg2.id = "msg_2"
        msg2.thread_id = "thread_1"
        msg2.label_ids = ["INBOX"]

        record = HistoryRecord(id="12345", messages_added=[msg1, msg2])
        label_ids = {}

        result = SyncResult()
        engine._process_history_record(1, record, label_ids, result, set())

        engine.jobs.enqueue.assert_called_once()


class TestFullSyncDeduplication:
    """Full sync skips emails already classified or with pending jobs."""

    def test_skips_already_classified_thread(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.labels_repo = MagicMock()
        engine.labels_repo.get_labels.return_value = {}
        engine.labels_repo.get_label_names.return_value = {}

        msg = MagicMock()
        msg.id = "msg_1"
        msg.thread_id = "thread_1"

        gmail = MagicMock()
        gmail.search.return_value = [msg]

        # Thread already in DB
        engine.emails.get_by_thread = MagicMock(return_value={"id": 1})

        result = engine.full_sync(1, gmail)

        engine.jobs.enqueue.assert_not_called()
        assert result.new_messages == 0

    def test_skips_thread_with_pending_job(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.labels_repo = MagicMock()
        engine.labels_repo.get_labels.return_value = {}
        engine.labels_repo.get_label_names.return_value = {}

        msg = MagicMock()
        msg.id = "msg_1"
        msg.thread_id = "thread_1"

        gmail = MagicMock()
        gmail.search.return_value = [msg]

        # No DB record, but pending job exists
        engine.emails.get_by_thread = MagicMock(return_value=None)
        engine.jobs.has_pending_for_thread = MagicMock(return_value=True)

        result = engine.full_sync(1, gmail)

        engine.jobs.enqueue.assert_not_called()
        assert result.new_messages == 0

    def test_enqueues_when_no_record_and_no_pending_job(self):
        db = MagicMock()
        engine = SyncEngine(db)
        engine.jobs = MagicMock()
        engine.labels_repo = MagicMock()
        engine.labels_repo.get_labels.return_value = {}
        engine.labels_repo.get_label_names.return_value = {}

        msg = MagicMock()
        msg.id = "msg_1"
        msg.thread_id = "thread_1"

        gmail = MagicMock()
        gmail.search.return_value = [msg]

        engine.emails.get_by_thread = MagicMock(return_value=None)
        engine.jobs.has_pending_for_thread = MagicMock(return_value=False)

        result = engine.full_sync(1, gmail)

        engine.jobs.enqueue.assert_called_once_with(
            "classify", 1, {"message_id": "msg_1", "thread_id": "thread_1"}
        )
        assert result.new_messages == 1
