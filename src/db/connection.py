"""Database connection management — SQLite (default) with PostgreSQL upgrade path."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from src.config import AppConfig, DatabaseBackend

logger = logging.getLogger(__name__)


class Database:
    """Database abstraction supporting SQLite (and future PostgreSQL)."""

    def __init__(self, config: AppConfig):
        self.config = config.database
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Ensure database file/schema exists."""
        if self.config.backend == DatabaseBackend.SQLITE:
            db_path = Path(self.config.sqlite_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection (context manager)."""
        if self.config.backend == DatabaseBackend.SQLITE:
            conn = sqlite3.connect(
                str(self.config.sqlite_path),
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            raise NotImplementedError("PostgreSQL backend not yet implemented")

    def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            if cursor.description:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            return []

    def execute_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Execute a query and return the first row as a dict, or None."""
        results = self.execute(sql, params)
        return results[0] if results else None

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE and return lastrowid or rowcount."""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.lastrowid or cursor.rowcount

    def execute_many(self, sql: str, params_list: list[tuple]) -> int:
        """Execute a batch of writes."""
        with self.connection() as conn:
            cursor = conn.executemany(sql, params_list)
            return cursor.rowcount

    def run_migration(self, sql: str) -> None:
        """Run a migration SQL script."""
        with self.connection() as conn:
            conn.executescript(sql)
        logger.info("Migration applied successfully")

    def initialize_schema(self) -> None:
        """Create the v2 schema if tables don't exist."""
        migrations_dir = Path(__file__).parent / "migrations"
        migrations = [
            "001_v2_schema.sql",
            "002_llm_calls.sql",
        ]

        for migration_file in migrations:
            migration_path = migrations_dir / migration_file
            if migration_path.exists():
                sql = migration_path.read_text()
                self.run_migration(sql)
                logger.info("Applied migration: %s", migration_file)
            else:
                logger.warning("Migration file not found: %s", migration_path)


# Module-level singleton
_db: Database | None = None


def get_db() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


def init_db(config: AppConfig) -> Database:
    """Initialize the global database instance."""
    global _db
    _db = Database(config)
    _db.initialize_schema()
    return _db
