"""Periodic scheduler — watch renewal and fallback sync.

Simple asyncio sleep-loop scheduler. No external dependencies.
Runs alongside the WorkerPool as background tasks in the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging

from src.config import AppConfig
from src.db.connection import Database
from src.db.models import JobRepository, UserRepository
from src.gmail.client import GmailService
from src.sync.watch import WatchManager

logger = logging.getLogger(__name__)

# Watch expires after 7 days; renew daily with some jitter margin
WATCH_RENEWAL_INTERVAL_HOURS = 24


class Scheduler:
    """Schedules periodic background jobs — watch renewal and fallback sync."""

    def __init__(self, db: Database, gmail_service: GmailService, config: AppConfig):
        self.db = db
        self.gmail_service = gmail_service
        self.config = config
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Launch all scheduled loops."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._watch_renewal_loop()),
            asyncio.create_task(self._fallback_sync_loop()),
            asyncio.create_task(self._full_sync_loop()),
        ]
        logger.info("Scheduler started (watch renewal + fallback sync + full sync)")
        await asyncio.gather(*self._tasks)

    def stop(self) -> None:
        """Signal all loops to stop."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        logger.info("Scheduler stopping")

    async def _watch_renewal_loop(self) -> None:
        """Renew Gmail watch() for all users on startup, then every 24h."""
        while self._running:
            try:
                await self._renew_watches()
            except Exception:
                logger.exception("Watch renewal failed")
            await asyncio.sleep(WATCH_RENEWAL_INTERVAL_HOURS * 3600)

    async def _fallback_sync_loop(self) -> None:
        """Enqueue a sync job for all users every N minutes as a safety net."""
        interval = self.config.sync.fallback_interval_minutes * 60
        while self._running:
            await asyncio.sleep(interval)
            try:
                await self._enqueue_fallback_syncs()
            except Exception:
                logger.exception("Fallback sync scheduling failed")

    async def _renew_watches(self) -> None:
        """Renew watches for all active users."""
        topic = self.config.sync.pubsub_topic
        if not topic:
            logger.debug("No Pub/Sub topic configured, skipping watch renewal")
            return

        watch_mgr = WatchManager(self.db, self.gmail_service, topic)
        results = await asyncio.to_thread(watch_mgr.renew_all_watches)
        for email, success in results.items():
            if success:
                logger.info("Watch renewed for %s", email)
            else:
                logger.warning("Watch renewal failed for %s", email)

    async def _full_sync_loop(self) -> None:
        """Run a full inbox scan periodically to catch emails missed during watch outages."""
        interval = self.config.sync.full_sync_interval_hours * 3600
        while self._running:
            await asyncio.sleep(interval)
            try:
                await self._enqueue_full_syncs()
            except Exception:
                logger.exception("Full sync scheduling failed")

    async def _enqueue_fallback_syncs(self) -> None:
        """Enqueue a sync job for each active user."""
        users = await asyncio.to_thread(UserRepository(self.db).get_active_users)
        jobs = JobRepository(self.db)
        for user in users:
            await asyncio.to_thread(jobs.enqueue, "sync", user.id, {"history_id": ""})
        if users:
            logger.info("Fallback sync queued for %d user(s)", len(users))

    async def _enqueue_full_syncs(self) -> None:
        """Enqueue a full sync job for each active user."""
        users = await asyncio.to_thread(UserRepository(self.db).get_active_users)
        jobs = JobRepository(self.db)
        for user in users:
            await asyncio.to_thread(
                jobs.enqueue, "sync", user.id, {"history_id": "", "force_full": True}
            )
        if users:
            logger.info("Full sync queued for %d user(s)", len(users))
