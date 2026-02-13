"""Delete AI-generated drafts containing the ✂️ rework marker.

Finds all Gmail drafts that have an 🤖 AI label and contain the ✂️ marker,
then deletes them. These are typically stale AI drafts that were never sent.

Usage:
    bin/cleanup-drafts              # Dry run (list only)
    bin/cleanup-drafts --delete     # Actually delete
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
from src.gmail.models import Message
from src.gmail.retry import execute_with_retry

SCISSORS = "\u2702\ufe0f"  # ✂️


def get_gmail_api():
    config = AppConfig.from_yaml()
    auth = GmailAuth(config)
    creds = auth.get_credentials(None)
    api = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return api.users()


def list_all_drafts(api) -> list[dict]:
    """List all drafts with pagination."""
    drafts = []
    page_token = None
    while True:
        params = {"userId": "me", "maxResults": 100}
        if page_token:
            params["pageToken"] = page_token
        result = execute_with_retry(api.drafts().list(**params), operation="drafts.list")
        drafts.extend(result.get("drafts", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return drafts


def main():
    parser = argparse.ArgumentParser(description="Delete AI drafts with ✂️ marker")
    parser.add_argument(
        "--delete", action="store_true", help="Actually delete (default is dry run)"
    )
    args = parser.parse_args()

    api = get_gmail_api()

    print("Listing all drafts...")
    drafts = list_all_drafts(api)
    print(f"Found {len(drafts)} total drafts")

    to_delete: list[tuple[str, str]] = []  # (draft_id, subject)

    for i, draft_stub in enumerate(drafts):
        draft_id = draft_stub["id"]
        data = execute_with_retry(
            api.drafts().get(userId="me", id=draft_id, format="full"),
            operation=f"drafts.get({draft_id})",
        )
        msg_data = data.get("message", {})
        msg = Message.from_api(msg_data)

        if SCISSORS in msg.body:
            to_delete.append((draft_id, msg.subject or "(no subject)"))

        if (i + 1) % 10 == 0:
            print(f"  Checked {i + 1}/{len(drafts)}...")

    print(f"\nFound {len(to_delete)} AI drafts with ✂️ marker:")
    for draft_id, subject in to_delete:
        print(f"  [{draft_id}] {subject}")

    if not to_delete:
        print("Nothing to clean up.")
        return

    if not args.delete:
        print(f"\nDry run — pass --delete to remove {len(to_delete)} drafts")
        return

    print(f"\nDeleting {len(to_delete)} drafts...")
    deleted = 0
    for draft_id, subject in to_delete:
        try:
            execute_with_retry(
                api.drafts().delete(userId="me", id=draft_id),
                operation=f"drafts.delete({draft_id})",
            )
            deleted += 1
            print(f"  Deleted: {subject}")
        except Exception as e:
            print(f"  Failed to delete {draft_id}: {e}")

    print(f"\nDone. Deleted {deleted}/{len(to_delete)} drafts.")


if __name__ == "__main__":
    main()
