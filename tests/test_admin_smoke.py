"""Admin UI smoke tests — run against a live dev server.

These tests hit the real admin UI on localhost to catch internal server errors
that are hard to reproduce with mocked data (e.g. SQLAlchemy relationship issues,
missing columns, bad formatters).

Usage:
    pytest tests/test_admin_smoke.py -v
    GMA_SMOKE_BASE_URL=http://localhost:8000 pytest tests/test_admin_smoke.py -v

Requires: dev server running (`uvicorn src.main:app --reload`)
"""

from __future__ import annotations

import os
import re

import httpx
import pytest

BASE_URL = os.environ.get("GMA_SMOKE_BASE_URL", "http://0.0.0.0:8000")
ADMIN_USER = os.environ.get("GMA_SERVER_ADMIN_USER", "")
ADMIN_PASSWORD = os.environ.get("GMA_SERVER_ADMIN_PASSWORD", "")

# Admin model URL slugs — must match SQLAdmin's generated routes
ADMIN_MODELS = [
    "user-model",
    "user-label-model",
    "user-setting-model",
    "sync-state-model",
    "email-model",
    "email-event-model",
    "llm-call-model",
    "job-model",
]

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="session")
def client():
    """Shared HTTP client for the test session."""
    auth = (ADMIN_USER, ADMIN_PASSWORD) if ADMIN_USER and ADMIN_PASSWORD else None
    with httpx.Client(base_url=BASE_URL, timeout=15, follow_redirects=True, auth=auth) as c:
        # Fail fast if server isn't running
        try:
            resp = c.get("/api/health")
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pytest.skip(
                f"Dev server not running at {BASE_URL} — start with: uvicorn src.main:app --reload"
            )
        yield c


# -- Helpers ------------------------------------------------------------------


def _extract_detail_links(html: str) -> list[str]:
    """Extract detail page hrefs from an admin list page."""
    return re.findall(r'href="(/admin/[^"]+/details/[^"]+)"', html)


# -- Tests --------------------------------------------------------------------


class TestAdminListPages:
    """Every admin list page should return 200."""

    @pytest.mark.parametrize("model_slug", ADMIN_MODELS)
    def test_list_page_returns_200(self, client: httpx.Client, model_slug: str):
        url = f"/admin/{model_slug}/list"
        resp = client.get(url)
        assert resp.status_code == 200, (
            f"GET {url} returned {resp.status_code}\nBody (first 500 chars): {resp.text[:500]}"
        )


class TestAdminDetailPages:
    """For each model, open the first detail link found on the list page."""

    @pytest.mark.parametrize("model_slug", ADMIN_MODELS)
    def test_first_detail_returns_200(self, client: httpx.Client, model_slug: str):
        list_url = f"/admin/{model_slug}/list"
        list_resp = client.get(list_url)
        assert list_resp.status_code == 200, (
            f"List page failed: GET {list_url} → {list_resp.status_code}"
        )

        detail_links = _extract_detail_links(list_resp.text)
        if not detail_links:
            pytest.skip(f"No detail links on {list_url} (table empty)")

        detail_url = detail_links[0]
        resp = client.get(detail_url)
        assert resp.status_code == 200, (
            f"GET {detail_url} returned {resp.status_code}\n"
            f"Body (first 500 chars): {resp.text[:500]}"
        )


class TestAdminDashboard:
    """The admin root dashboard should load."""

    def test_dashboard_returns_200(self, client: httpx.Client):
        resp = client.get("/admin/")
        assert resp.status_code == 200, f"Dashboard returned {resp.status_code}"

    def test_dashboard_contains_all_nav_links(self, client: httpx.Client):
        resp = client.get("/admin/")
        for slug in ADMIN_MODELS:
            assert f"/admin/{slug}/list" in resp.text, f"Nav link for {slug} missing from dashboard"


class TestDebugPages:
    """Debug UI and API endpoints should return 200."""

    def test_debug_email_list_html(self, client: httpx.Client):
        resp = client.get("/debug/emails")
        assert resp.status_code == 200, f"GET /debug/emails returned {resp.status_code}"

    def test_debug_email_list_api(self, client: httpx.Client):
        resp = client.get("/api/debug/emails")
        assert resp.status_code == 200
        data = resp.json()
        assert "emails" in data
        assert "count" in data
        assert "filters" in data

    def test_debug_email_list_api_with_filters(self, client: httpx.Client):
        resp = client.get("/api/debug/emails?status=pending&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["filters"]["status"] == "pending"

    def test_debug_email_detail_html(self, client: httpx.Client):
        # Get an email ID from the list API
        list_resp = client.get("/api/debug/emails?limit=1")
        emails = list_resp.json().get("emails", [])
        if not emails:
            pytest.skip("No emails in database")
        email_id = emails[0]["id"]

        resp = client.get(f"/debug/email/{email_id}")
        assert resp.status_code == 200, f"GET /debug/email/{email_id} returned {resp.status_code}"

    def test_debug_email_detail_api(self, client: httpx.Client):
        list_resp = client.get("/api/debug/emails?limit=1")
        emails = list_resp.json().get("emails", [])
        if not emails:
            pytest.skip("No emails in database")
        email_id = emails[0]["id"]

        resp = client.get(f"/api/emails/{email_id}/debug")
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "events" in data
        assert "llm_calls" in data
        assert "agent_runs" in data
        assert "timeline" in data
        assert "summary" in data
        # Verify summary structure
        summary = data["summary"]
        assert "total_tokens" in summary
        assert "error_count" in summary
        assert "llm_breakdown" in summary

    def test_debug_email_not_found(self, client: httpx.Client):
        resp = client.get("/api/emails/999999/debug")
        assert resp.status_code == 404


class TestNoServerErrors:
    """Scan list pages for any error indicators in the HTML body."""

    @pytest.mark.parametrize("model_slug", ADMIN_MODELS)
    def test_no_error_traces_in_list_page(self, client: httpx.Client, model_slug: str):
        resp = client.get(f"/admin/{model_slug}/list")
        body = resp.text.lower()
        assert "traceback (most recent call last)" not in body, (
            f"Python traceback found on /admin/{model_slug}/list"
        )
        assert "internal server error" not in body, (
            f"Internal Server Error on /admin/{model_slug}/list"
        )
