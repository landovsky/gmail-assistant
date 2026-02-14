"""Admin setup — create engine and mount SQLAdmin."""

from __future__ import annotations

from fastapi import FastAPI
from sqladmin import Admin
from sqlalchemy import create_engine

from src.admin.views import (
    EmailAdmin,
    EmailEventAdmin,
    JobAdmin,
    LLMCallAdmin,
    SyncStateAdmin,
    UserAdmin,
    UserLabelAdmin,
    UserSettingAdmin,
)


def setup_admin(app: FastAPI, sqlite_path: str, *, debug: bool = False) -> Admin:
    """Set up and mount the admin interface.

    Creates a read-only SQLAlchemy engine (WAL mode supports concurrent
    readers) and registers all ModelView classes.

    Args:
        app: FastAPI application instance
        sqlite_path: Path to SQLite database file
        debug: Show full tracebacks on errors (development only)

    Returns:
        Admin instance (for testing purposes)
    """
    # Create read-only engine (WAL mode allows concurrent readers)
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={
            "check_same_thread": False,  # Allow multi-threaded access
        },
    )

    # Create admin instance
    admin = Admin(
        app,
        engine,
        title="Gmail Assistant Admin",
        base_url="/admin",
        debug=debug,
    )

    # Register all views
    admin.add_view(UserAdmin)
    admin.add_view(UserLabelAdmin)
    admin.add_view(UserSettingAdmin)
    admin.add_view(SyncStateAdmin)
    admin.add_view(EmailAdmin)
    admin.add_view(EmailEventAdmin)
    admin.add_view(LLMCallAdmin)
    admin.add_view(JobAdmin)

    return admin
