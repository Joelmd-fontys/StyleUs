"""Shared worker-host lifecycle helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING

import anyio
from fastapi import FastAPI

from app.core.config import Settings
from app.core.logging import logger

if TYPE_CHECKING:
    from app.ai.worker import AIWorker


def get_ai_worker_class() -> type[AIWorker]:
    from app.ai.worker import AIWorker

    return AIWorker


def build_worker_lifespan(
    settings: Settings,
    *,
    worker_class_getter: Callable[[], type[AIWorker]],
    start_worker: bool,
    thread_name: str,
    startup_skip_reason: str = "disabled_for_app_instance",
    shutdown_reason: str = "lifespan_shutdown",
    shutdown_timeout_seconds: float = 30.0,
    shutdown_timeout_extra: Mapping[str, object] | None = None,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker: AIWorker | None = None
        if start_worker:
            worker = worker_class_getter()(settings)
            app.state.ai_worker = worker
            worker.start_in_background(thread_name=thread_name)
        else:
            app.state.ai_worker = None
            logger.info("worker.startup_skipped", extra={"reason": startup_skip_reason})

        try:
            yield
        finally:
            if worker is not None:
                worker.request_shutdown(reason=shutdown_reason)
                stopped = await anyio.to_thread.run_sync(worker.join, shutdown_timeout_seconds)
                if not stopped:
                    warning_extra: dict[str, object] = {"timeout_seconds": shutdown_timeout_seconds}
                    if shutdown_timeout_extra:
                        warning_extra.update(shutdown_timeout_extra)
                    logger.warning("worker.shutdown_timeout", extra=warning_extra)
            app.state.ai_worker = None

    return lifespan
