"""Database layer — SQLite (default) with PostgreSQL upgrade path."""

from src.db.connection import get_db, Database

__all__ = ["get_db", "Database"]
