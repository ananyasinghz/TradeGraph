"""Optional background source-fetch loop (Phase B)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.core.config import Settings

logger = logging.getLogger(__name__)


async def _source_fetch_loop(app: FastAPI, settings: Settings) -> None:
    interval = max(60, int(settings.source_fetch_interval_minutes) * 60)
    while True:
        try:
            factory = app.state.session_factory
            with factory() as session:
                from backend.app.services import jobs_service

                # Live adapters auto-ingest; curated connections stay fetch-only.
                jobs_service.run_source_fetch_job(session, run_ingest=None)
                session.commit()
            logger.info("source_fetch_scheduler completed")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("source_fetch_scheduler failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    task: asyncio.Task[None] | None = None
    if settings.source_fetch_scheduler_enabled:
        task = asyncio.create_task(_source_fetch_loop(app, settings))
        logger.info(
            "source_fetch_scheduler enabled (every %sm)",
            settings.source_fetch_interval_minutes,
        )
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
