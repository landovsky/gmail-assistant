"""Gmail API integration — direct client with personal OAuth and service account support."""

from src.gmail.auth import GmailAuth, AuthMode
from src.gmail.client import GmailService, UserGmailClient
from src.gmail.models import Message, Thread, Draft, WatchResponse, HistoryRecord

__all__ = [
    "GmailAuth",
    "AuthMode",
    "GmailService",
    "UserGmailClient",
    "Message",
    "Thread",
    "Draft",
    "WatchResponse",
    "HistoryRecord",
]
