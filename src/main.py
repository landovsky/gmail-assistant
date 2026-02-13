"""Gmail Assistant v2 — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from src.api.admin import router as admin_router
from src.api.briefing import router as briefing_router
from src.api.webhook import router as webhook_router
from src.classify.engine import ClassificationEngine
from src.config import AppConfig
from src.db.connection import init_db
from src.draft.engine import DraftEngine
from src.gmail.client import GmailService
from src.llm.config import LLMConfig
from src.llm.gateway import LLMGateway
from src.tasks.scheduler import Scheduler
from src.tasks.workers import WorkerPool

logger = logging.getLogger(__name__)

# Global references for background tasks
_worker_pool: WorkerPool | None = None
_scheduler: Scheduler | None = None
_bg_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    global _worker_pool, _scheduler, _bg_tasks

    config = app.state.config
    db = app.state.db

    gmail_service = GmailService(config)
    llm_config = LLMConfig.from_app_config(config)
    llm_gateway = LLMGateway(llm_config)
    classification_engine = ClassificationEngine(llm_gateway)
    draft_engine = DraftEngine(llm_gateway)

    # Start worker pool
    _worker_pool = WorkerPool(db, gmail_service, classification_engine, draft_engine, config)
    _bg_tasks.append(asyncio.create_task(_worker_pool.start()))

    # Start scheduler (watch renewal + fallback sync)
    _scheduler = Scheduler(db, gmail_service, config)
    _bg_tasks.append(asyncio.create_task(_scheduler.start()))

    logger.info("Worker pool and scheduler started")

    yield

    # Shutdown
    if _worker_pool:
        _worker_pool.stop()
    if _scheduler:
        _scheduler.stop()
    for task in _bg_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _bg_tasks.clear()
    logger.info("Application shutdown complete")


def _init_sentry(dsn: str) -> None:
    """Initialize Sentry SDK if a DSN is configured."""
    if not dsn:
        return
    sentry_sdk.init(
        dsn,
        send_default_pii=True,
        max_request_body_size="always",
        traces_sample_rate=0,
        send_client_reports=False,
        auto_session_tracking=False,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = AppConfig.from_yaml()

    _init_sentry(config.sentry_dsn)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.server.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title="Gmail Assistant v2",
        version="2.0.0",
        description="AI-powered Gmail inbox management",
        lifespan=lifespan,
    )

    # Initialize database
    db = init_db(config)
    app.state.config = config
    app.state.db = db

    # Register routes
    app.include_router(webhook_router)
    app.include_router(admin_router)
    app.include_router(briefing_router)

    return app


def cli_entry() -> None:
    """CLI entry point for running the server."""
    import uvicorn

    config = AppConfig.from_yaml()
    app = create_app(config)

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.server.log_level,
    )


# Default app instance for uvicorn
app = create_app()
