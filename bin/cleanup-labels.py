"""Remove all 🤖 AI/* labels from inbox messages.

Finds all messages that have any 🤖 AI label and removes all AI labels from them.
Does NOT delete messages — only strips the labels.

Usage:
    bin/cleanup-labels              # Dry run (list only)
    bin/cleanup-labels --delete     # Actually remove labels
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from googleapiclient.discovery import build

from src.config import AppConfig
from src.gmail.auth import GmailAuth

# All 🤖 AI label IDs (parent + children)
AI_LABEL_IDS = [
    "Label_3622223931283024477",  # 🤖 AI (parent)
    "Label_34",  # 🤖 AI/Needs Response
    "Label_35",  # 🤖 AI/Outbox
    "Label_36",  # 🤖 AI/Rework
    "Label_37",  # 🤖 AI/Action Required
    "Label_38",  # 🤖 AI/Payment Request
    "Label_39",  # 🤖 AI/FYI
    "Label_40",  # 🤖 AI/Waiting
    "Label_41",  # 🤖 AI/Done
]


def get_gmail_api():
    config = AppConfig.from_yaml()
    auth = GmailAuth(config)
    creds = auth.get_credentials(None)
    api = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return api.users()


def find_labeled_messages(api) -> list[dict]:
    """Find all messages with any AI label. Returns list of {id, subject, labels}."""
    seen_ids: set[str] = set()
    messages: list[dict] = []

    for label_id in AI_LABEL_IDS:
        page_token = None
        while True:
            params = {"userId": "me", "labelIds": [label_id], "maxResults": 100}
            if page_token:
                params["pageToken"] = page_token
            result = api.messages().list(**params).execute()
            for msg_stub in result.get("messages", []):
                if msg_stub["id"] not in seen_ids:
                    seen_ids.add(msg_stub["id"])
                    messages.append(msg_stub)
            page_token = result.get("nextPageToken")
            if not page_token:
                break

    return messages


def get_subject(api, message_id: str) -> str:
    """Get subject line from a message (metadata only)."""
    msg = api.messages().get(
        userId="me", id=message_id, format="metadata", metadataHeaders=["Subject"]
    ).execute()
    headers = msg.get("payload", {}).get("headers", [])
    for h in headers:
        if h["name"].lower() == "subject":
            return h["value"]
    return "(no subject)"


def main():
    parser = argparse.ArgumentParser(
        description="Remove all 🤖 AI labels from inbox messages"
    )
    parser.add_argument(
        "--delete", action="store_true",
        help="Actually remove labels (default is dry run)",
    )
    args = parser.parse_args()

    api = get_gmail_api()

    print("Searching for messages with 🤖 AI labels...")
    messages = find_labeled_messages(api)
    print(f"Found {len(messages)} messages with AI labels")

    if not messages:
        print("Nothing to clean up.")
        return

    # Show sample in dry-run
    print()
    sample = messages[:10]
    for msg in sample:
        subject = get_subject(api, msg["id"])
        print(f"  {msg['id'][:12]}…  {subject}")
    if len(messages) > 10:
        print(f"  ... and {len(messages) - 10} more")

    if not args.delete:
        print(f"\nDry run — pass --delete to remove AI labels from {len(messages)} messages")
        return

    print(f"\nRemoving AI labels from {len(messages)} messages...")
    # Batch modify for efficiency
    batch_size = 50
    modified = 0
    for i in range(0, len(messages), batch_size):
        batch = messages[i : i + batch_size]
        batch_ids = [m["id"] for m in batch]
        try:
            api.messages().batchModify(
                userId="me",
                body={"ids": batch_ids, "removeLabelIds": AI_LABEL_IDS},
            ).execute()
            modified += len(batch)
            print(f"  Processed {modified}/{len(messages)}")
        except Exception as e:
            print(f"  Batch failed at offset {i}: {e}")

    print(f"\nDone. Removed AI labels from {modified}/{len(messages)} messages.")


if __name__ == "__main__":
    main()
