"""Tests for WatchManager — Gmail push notification setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.gmail.models import WatchResponse
from src.sync.watch import WatchManager


class TestRenewWatch:
    def _make_manager(self, topic: str = "projects/test/topics/gmail-push") -> WatchManager:
        db = MagicMock()
        gmail_service = MagicMock()
        return WatchManager(db, gmail_service, topic)

    def test_watch_includes_inbox_and_action_labels(self):
        """Watch must include INBOX + user-action labels for label-change notifications."""
        manager = self._make_manager()

        client = MagicMock()
        manager.gmail_service.for_user.return_value = client
        client.watch.return_value = WatchResponse(history_id="123", expiration="9999999999")

        with patch("src.sync.watch.LabelRepository") as mock_labels_cls:
            mock_labels_cls.return_value.get_labels.return_value = {
                "needs_response": "Label_NR",
                "rework": "Label_RW",
                "done": "Label_DN",
                "outbox": "Label_OB",
            }
            manager.renew_watch(1, "user@example.com")

        client.watch.assert_called_once()
        call_args = client.watch.call_args
        assert call_args[0][0] == "projects/test/topics/gmail-push"

        label_ids = call_args[1]["label_ids"]
        assert "INBOX" in label_ids
        assert "Label_NR" in label_ids
        assert "Label_RW" in label_ids
        assert "Label_DN" in label_ids
        # outbox is not a user-action label, should not be included
        assert "Label_OB" not in label_ids

    def test_watch_works_with_missing_labels(self):
        """Watch should still work if some labels aren't configured yet."""
        manager = self._make_manager()

        client = MagicMock()
        manager.gmail_service.for_user.return_value = client
        client.watch.return_value = WatchResponse(history_id="123", expiration="9999999999")

        with patch("src.sync.watch.LabelRepository") as mock_labels_cls:
            mock_labels_cls.return_value.get_labels.return_value = {
                "needs_response": "Label_NR",
                # rework and done not configured
            }
            result = manager.renew_watch(1, "user@example.com")

        assert result is True
        label_ids = client.watch.call_args[1]["label_ids"]
        assert label_ids == ["INBOX", "Label_NR"]

    def test_watch_skipped_without_topic(self):
        """No Pub/Sub topic → skip watch entirely."""
        manager = self._make_manager(topic="")
        result = manager.renew_watch(1, "user@example.com")
        assert result is False

    def test_watch_updates_sync_state(self):
        """Successful watch should persist history_id and expiration."""
        manager = self._make_manager()
        manager.sync_state = MagicMock()

        client = MagicMock()
        manager.gmail_service.for_user.return_value = client
        client.watch.return_value = WatchResponse(history_id="456", expiration="1234567890")

        with patch("src.sync.watch.LabelRepository") as mock_labels_cls:
            mock_labels_cls.return_value.get_labels.return_value = {}
            manager.renew_watch(1, "user@example.com")

        manager.sync_state.set_watch.assert_called_once_with(1, "456", "1234567890")

    def test_watch_returns_false_on_failure(self):
        """Gmail API error → return False, don't crash."""
        manager = self._make_manager()

        client = MagicMock()
        manager.gmail_service.for_user.return_value = client
        client.watch.side_effect = Exception("API error")

        with patch("src.sync.watch.LabelRepository") as mock_labels_cls:
            mock_labels_cls.return_value.get_labels.return_value = {}
            result = manager.renew_watch(1, "user@example.com")

        assert result is False
