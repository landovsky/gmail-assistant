"""Gmail API client — direct API wrapper with per-user impersonation."""

from __future__ import annotations

import base64
import logging
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build

from src.config import AppConfig
from src.gmail.auth import GmailAuth
from src.gmail.models import Draft, HistoryRecord, Message, Thread, WatchResponse
from src.gmail.retry import execute_with_retry

logger = logging.getLogger(__name__)


class GmailService:
    """Top-level Gmail service — creates per-user clients."""

    def __init__(self, config: AppConfig):
        self.auth = GmailAuth(config)
        self.config = config

    def for_user(self, user_email: str | None = None) -> UserGmailClient:
        """Create a Gmail client for a specific user (or the default user in lite mode)."""
        creds = self.auth.get_credentials(user_email)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return UserGmailClient(service, user_email or "me")


class UserGmailClient:
    """Gmail operations for a single user — all direct API, no LLM round-trips."""

    def __init__(self, service: Any, user_email: str):
        self.service = service
        self.user_email = user_email
        self._gmail = service.users()

    def _exec(self, request: Any, operation: str = "API call") -> Any:
        """Execute a Google API request with retry on transient network errors."""
        return execute_with_retry(request, operation=operation)

    def search(self, query: str, max_results: int = 50) -> list[Message]:
        """Search for messages matching a Gmail query."""
        results = self._exec(
            self._gmail.messages().list(userId="me", q=query, maxResults=max_results),
            operation="messages.list",
        )
        messages = []
        for item in results.get("messages", []):
            msg = self.get_message(item["id"])
            if msg:
                messages.append(msg)
        return messages

    def search_metadata(self, query: str, max_results: int = 10) -> list[Message]:
        """Search messages, fetching only metadata (no body). Much cheaper than search()."""
        try:
            results = self._exec(
                self._gmail.messages().list(userId="me", q=query, maxResults=max_results),
                operation="messages.list (metadata)",
            )
            messages = []
            for item in results.get("messages", []):
                msg = self.get_message(item["id"], format="metadata")
                if msg:
                    messages.append(msg)
            return messages
        except Exception as e:
            logger.error("Metadata search failed for query %r: %s", query, e)
            return []

    def get_message(self, message_id: str, format: str = "full") -> Message | None:
        """Get a single message by ID."""
        try:
            data = self._exec(
                self._gmail.messages().get(userId="me", id=message_id, format=format),
                operation=f"messages.get({message_id})",
            )
            return Message.from_api(data)
        except Exception as e:
            logger.error("Failed to get message %s: %s", message_id, e)
            return None

    def get_thread(self, thread_id: str) -> Thread | None:
        """Get a full thread with all messages."""
        try:
            data = self._exec(
                self._gmail.threads().get(userId="me", id=thread_id, format="full"),
                operation=f"threads.get({thread_id})",
            )
            return Thread.from_api(data)
        except Exception as e:
            logger.error("Failed to get thread %s: %s", thread_id, e)
            return None

    def modify_labels(
        self,
        message_id: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> bool:
        """Add/remove labels on a single message."""
        try:
            body: dict[str, Any] = {}
            if add:
                body["addLabelIds"] = add
            if remove:
                body["removeLabelIds"] = remove
            self._exec(
                self._gmail.messages().modify(userId="me", id=message_id, body=body),
                operation=f"messages.modify({message_id})",
            )
            return True
        except Exception as e:
            logger.error("Failed to modify labels on %s: %s", message_id, e)
            return False

    def batch_modify_labels(
        self,
        message_ids: list[str],
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> bool:
        """Batch modify labels on multiple messages."""
        if not message_ids:
            return True
        try:
            body: dict[str, Any] = {"ids": message_ids}
            if add:
                body["addLabelIds"] = add
            if remove:
                body["removeLabelIds"] = remove
            self._exec(
                self._gmail.messages().batchModify(userId="me", body=body),
                operation="messages.batchModify",
            )
            return True
        except Exception as e:
            logger.error("Failed to batch modify labels: %s", e)
            return False

    def create_draft(
        self,
        thread_id: str,
        to: str,
        subject: str,
        body: str,
        in_reply_to: str | None = None,
    ) -> str | None:
        """Create a draft reply in a thread. Returns draft ID."""
        try:
            message = MIMEText(body)
            message["from"] = self.user_email
            message["to"] = to
            message["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
            if in_reply_to:
                message["In-Reply-To"] = in_reply_to
                message["References"] = in_reply_to

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            draft_body = {
                "message": {
                    "raw": raw,
                    "threadId": thread_id,
                }
            }
            result = self._exec(
                self._gmail.drafts().create(userId="me", body=draft_body),
                operation="drafts.create",
            )
            return result.get("id")
        except Exception as e:
            logger.error("Failed to create draft: %s", e)
            return None

    def get_draft(self, draft_id: str) -> Draft | None:
        """Get a draft by ID."""
        try:
            data = self._exec(
                self._gmail.drafts().get(userId="me", id=draft_id),
                operation=f"drafts.get({draft_id})",
            )
            return Draft.from_api(data)
        except Exception:
            return None

    def trash_draft(self, draft_id: str) -> bool:
        """Move a draft to trash."""
        try:
            self._exec(
                self._gmail.drafts().delete(userId="me", id=draft_id),
                operation=f"drafts.delete({draft_id})",
            )
            return True
        except Exception as e:
            logger.error("Failed to trash draft %s: %s", draft_id, e)
            return False

    def list_drafts(self) -> list[Draft]:
        """List all drafts."""
        try:
            result = self._exec(
                self._gmail.drafts().list(userId="me"),
                operation="drafts.list",
            )
            return [Draft.from_api(d) for d in result.get("drafts", [])]
        except Exception as e:
            logger.error("Failed to list drafts: %s", e)
            return []

    def get_thread_draft(self, thread_id: str) -> Draft | None:
        """Find a user-written draft belonging to a specific thread.

        Lists all drafts and returns the first one matching the thread ID,
        fetched with full body content. Returns None if no draft exists.
        """
        drafts = self.list_drafts()
        for draft in drafts:
            if draft.thread_id == thread_id:
                return self.get_draft(draft.id)
        return None

    def trash_thread_drafts(self, thread_id: str) -> int:
        """Trash all drafts belonging to a thread. Returns count trashed."""
        drafts = self.list_drafts()
        count = 0
        for draft in drafts:
            if draft.thread_id == thread_id:
                if self.trash_draft(draft.id):
                    count += 1
        return count

    def list_history(
        self,
        start_history_id: str,
        label_id: str | None = None,
        max_results: int = 100,
    ) -> list[HistoryRecord]:
        """List history records since a given historyId."""
        try:
            params: dict[str, Any] = {
                "userId": "me",
                "startHistoryId": start_history_id,
                "maxResults": max_results,
            }
            if label_id:
                params["labelId"] = label_id

            records = []
            response = self._exec(
                self._gmail.history().list(**params),
                operation="history.list",
            )
            for item in response.get("history", []):
                records.append(HistoryRecord.from_api(item))

            # Handle pagination
            while "nextPageToken" in response:
                params["pageToken"] = response["nextPageToken"]
                response = self._exec(
                    self._gmail.history().list(**params),
                    operation="history.list (page)",
                )
                for item in response.get("history", []):
                    records.append(HistoryRecord.from_api(item))

            return records
        except Exception as e:
            # historyId too old → need full sync
            if "historyId" in str(e).lower():
                logger.warning("History ID too old, full sync needed: %s", e)
                return []
            logger.error("Failed to list history: %s", e)
            return []

    def watch(self, topic_name: str, label_ids: list[str] | None = None) -> WatchResponse | None:
        """Set up Gmail push notifications via Pub/Sub."""
        try:
            body: dict[str, Any] = {"topicName": topic_name}
            if label_ids:
                body["labelIds"] = label_ids
                body["labelFilterBehavior"] = "INCLUDE"
            result = self._exec(
                self._gmail.watch(userId="me", body=body),
                operation="watch",
            )
            return WatchResponse.from_api(result)
        except Exception as e:
            logger.error("Failed to set up watch: %s", e)
            return None

    def stop_watch(self) -> bool:
        """Stop Gmail push notifications."""
        try:
            self._exec(
                self._gmail.stop(userId="me"),
                operation="stop",
            )
            return True
        except Exception as e:
            logger.error("Failed to stop watch: %s", e)
            return False

    def get_or_create_label(self, name: str, **kwargs: Any) -> str | None:
        """Get existing label by name or create it. Returns label ID."""
        try:
            # List existing labels
            results = self._exec(
                self._gmail.labels().list(userId="me"),
                operation="labels.list",
            )
            for label in results.get("labels", []):
                if label["name"] == name:
                    return label["id"]

            # Create new label
            body: dict[str, Any] = {
                "name": name,
                "labelListVisibility": kwargs.get("visibility", "labelShow"),
                "messageListVisibility": kwargs.get("message_visibility", "show"),
            }
            result = self._exec(
                self._gmail.labels().create(userId="me", body=body),
                operation=f"labels.create({name})",
            )
            logger.info("Created label: %s → %s", name, result["id"])
            return result["id"]
        except Exception as e:
            logger.error("Failed to get/create label %s: %s", name, e)
            return None

    def get_profile(self) -> dict[str, Any]:
        """Get the user's Gmail profile (email address, historyId)."""
        try:
            return self._exec(
                self._gmail.getProfile(userId="me"),
                operation="getProfile",
            )
        except Exception as e:
            logger.error("Failed to get profile: %s", e)
            return {}
