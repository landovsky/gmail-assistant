"""Tests for Gmail data models."""

import pytest

from src.gmail.models import Message, Thread, Draft


class TestMessageParsing:
    def test_from_api_basic(self):
        data = {
            "id": "msg_1",
            "threadId": "thread_1",
            "snippet": "Hello there",
            "internalDate": "1700000000000",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Sender Name <sender@example.com>"},
                    {"name": "To", "value": "me@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                ],
                "mimeType": "text/plain",
                "body": {"data": "SGVsbG8gV29ybGQ="},  # "Hello World"
            },
        }
        msg = Message.from_api(data)
        assert msg.id == "msg_1"
        assert msg.thread_id == "thread_1"
        assert msg.sender_email == "sender@example.com"
        assert msg.sender_name == "Sender Name"
        assert msg.subject == "Test Subject"
        assert msg.body == "Hello World"
        assert "INBOX" in msg.label_ids

    def test_from_api_no_name(self):
        data = {
            "id": "msg_2",
            "threadId": "thread_2",
            "payload": {
                "headers": [
                    {"name": "From", "value": "plain@example.com"},
                    {"name": "Subject", "value": "No Name"},
                ],
            },
        }
        msg = Message.from_api(data)
        assert msg.sender_email == "plain@example.com"
        assert msg.sender_name == ""


class TestThread:
    def test_from_api(self):
        data = {
            "id": "thread_1",
            "snippet": "Latest message",
            "historyId": "12345",
            "messages": [
                {
                    "id": "msg_1",
                    "threadId": "thread_1",
                    "payload": {"headers": [{"name": "Subject", "value": "Test"}]},
                },
                {
                    "id": "msg_2",
                    "threadId": "thread_1",
                    "payload": {"headers": [{"name": "Subject", "value": "Re: Test"}]},
                },
            ],
        }
        thread = Thread.from_api(data)
        assert thread.id == "thread_1"
        assert thread.message_count == 2
        assert thread.latest_message.id == "msg_2"

    def test_empty_thread(self):
        thread = Thread(id="empty")
        assert thread.message_count == 0
        assert thread.latest_message is None


class TestDraft:
    def test_from_api(self):
        data = {
            "id": "draft_1",
            "message": {
                "id": "msg_draft",
                "threadId": "thread_1",
                "payload": {"headers": [{"name": "Subject", "value": "Re: Test"}]},
            },
        }
        draft = Draft.from_api(data)
        assert draft.id == "draft_1"
        assert draft.message is not None
        assert draft.thread_id == "thread_1"
