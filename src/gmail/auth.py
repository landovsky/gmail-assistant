"""Gmail authentication — personal OAuth (lite) and service account (multi-user)."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import AppConfig, AuthMode

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailAuth:
    """Unified auth supporting personal OAuth and service account impersonation."""

    def __init__(self, config: AppConfig):
        self.config = config.auth
        self.mode = self.config.mode

    def get_credentials(self, user_email: str | None = None) -> Credentials:
        if self.mode == AuthMode.SERVICE_ACCOUNT:
            return self._service_account_creds(user_email)
        else:
            return self._personal_oauth_creds()

    def _personal_oauth_creds(self) -> Credentials:
        """Load or refresh personal OAuth token."""
        from google.oauth2.credentials import Credentials as OAuthCredentials

        token_path = Path(self.config.token_file)
        creds = None

        if token_path.exists():
            creds = OAuthCredentials.from_authorized_user_file(
                str(token_path), GMAIL_SCOPES
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing OAuth token")
                creds.refresh(Request())
            else:
                logger.info("Running OAuth consent flow")
                credentials_path = Path(self.config.credentials_file)
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth credentials not found at {credentials_path}. "
                        "Download from Google Cloud Console → APIs & Services → Credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save token for next run
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())
            logger.info("OAuth token saved to %s", token_path)

        return creds

    def _service_account_creds(self, user_email: str | None) -> Credentials:
        """Get service account credentials with optional user impersonation."""
        sa_path = Path(self.config.service_account_file)
        if not sa_path.exists():
            raise FileNotFoundError(
                f"Service account key not found at {sa_path}. "
                "Create one in Google Cloud Console → IAM & Admin → Service Accounts."
            )

        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=GMAIL_SCOPES
        )

        if user_email:
            creds = creds.with_subject(user_email)

        return creds
