"""Gmail data models — Message, Thread, Draft, History."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    id: str
    thread_id: str
    sender_email: str = ""
    sender_name: str = ""
    to: str = ""
    subject: str = ""
    snippet: str = ""
    body: str = ""
    date: str = ""
    internal_date: str = ""
    label_ids: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Message:
        """Parse a Gmail API message resource."""
        payload = data.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

        sender = headers.get("From", "")
        sender_email = sender
        sender_name = ""
        if "<" in sender and ">" in sender:
            sender_name = sender.split("<")[0].strip().strip('"')
            sender_email = sender.split("<")[1].rstrip(">")

        body = cls._extract_body(payload)

        return cls(
            id=data["id"],
            thread_id=data.get("threadId", ""),
            sender_email=sender_email,
            sender_name=sender_name,
            to=headers.get("To", ""),
            subject=headers.get("Subject", ""),
            snippet=data.get("snippet", ""),
            body=body,
            date=headers.get("Date", ""),
            internal_date=data.get("internalDate", ""),
            label_ids=data.get("labelIds", []),
            headers=headers,
        )

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Extract plain text body from message payload."""
        import base64

        # Simple single-part message
        if payload.get("mimeType") == "text/plain" and "body" in payload:
            data = payload["body"].get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        # Multipart — look for text/plain
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Nested multipart
            for sub in part.get("parts", []):
                if sub.get("mimeType") == "text/plain":
                    data = sub.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        return ""


@dataclass
class Thread:
    id: str
    messages: list[Message] = field(default_factory=list)
    snippet: str = ""
    history_id: str = ""

    @classmethod
    def from_api(cls, data: dict) -> Thread:
        messages = [Message.from_api(m) for m in data.get("messages", [])]
        return cls(
            id=data["id"],
            messages=messages,
            snippet=data.get("snippet", ""),
            history_id=data.get("historyId", ""),
        )

    @property
    def latest_message(self) -> Message | None:
        return self.messages[-1] if self.messages else None

    @property
    def message_count(self) -> int:
        return len(self.messages)


@dataclass
class Draft:
    id: str
    message: Message | None = None
    thread_id: str = ""

    @classmethod
    def from_api(cls, data: dict) -> Draft:
        msg = None
        if "message" in data:
            msg = Message.from_api(data["message"])
        return cls(
            id=data["id"],
            message=msg,
            thread_id=data.get("message", {}).get("threadId", ""),
        )


@dataclass
class WatchResponse:
    history_id: str
    expiration: str

    @classmethod
    def from_api(cls, data: dict) -> WatchResponse:
        return cls(
            history_id=data.get("historyId", ""),
            expiration=data.get("expiration", ""),
        )


@dataclass
class HistoryRecord:
    id: str
    messages_added: list[Message] = field(default_factory=list)
    messages_deleted: list[str] = field(default_factory=list)
    labels_added: list[dict] = field(default_factory=list)
    labels_removed: list[dict] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> HistoryRecord:
        messages_added = []
        for item in data.get("messagesAdded", []):
            messages_added.append(Message.from_api(item["message"]))

        messages_deleted = [
            item["message"]["id"] for item in data.get("messagesDeleted", [])
        ]

        labels_added = [
            {"message_id": item["message"]["id"], "label_ids": item.get("labelIds", [])}
            for item in data.get("labelsAdded", [])
        ]

        labels_removed = [
            {"message_id": item["message"]["id"], "label_ids": item.get("labelIds", [])}
            for item in data.get("labelsRemoved", [])
        ]

        return cls(
            id=data["id"],
            messages_added=messages_added,
            messages_deleted=messages_deleted,
            labels_added=labels_added,
            labels_removed=labels_removed,
        )
