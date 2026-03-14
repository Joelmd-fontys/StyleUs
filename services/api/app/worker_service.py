"""Minimal web service wrapper around the AI worker loop."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import anyio
from fastapi import FastAPI, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.services import ai_jobs as ai_jobs_service

if TYPE_CHECKING:
    from app.ai.worker import AIWorker

_WORKER_SHUTDOWN_TIMEOUT_SECONDS = 30.0


def _get_ai_worker_class() -> type[AIWorker]:
    from app.ai.worker import AIWorker

    return AIWorker


def create_worker_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker = _get_ai_worker_class()(settings)
        app.state.ai_worker = worker
        worker.start_in_background(thread_name="styleus-ai-worker-service")
        try:
            yield
        finally:
            worker.request_shutdown(reason="worker_service_shutdown")
            stopped = await anyio.to_thread.run_sync(
                worker.join,
                _WORKER_SHUTDOWN_TIMEOUT_SECONDS,
            )
            if not stopped:
                logger.warning(
                    "worker.shutdown_timeout",
                    extra={
                        "service": "ai-worker",
                        "timeout_seconds": _WORKER_SHUTDOWN_TIMEOUT_SECONDS,
                    },
                )
            app.state.ai_worker = None

    app = FastAPI(
        title="StyleUs AI Worker",
        version=settings.app_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.get("/health")
    def health_check() -> dict[str, object]:
        worker = getattr(app.state, "ai_worker", None)
        if worker is None:
            detail = "Worker unavailable"
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )

        try:
            with SessionLocal() as session:
                queue_counts = ai_jobs_service.get_queue_counts(session)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc

        snapshot = worker.snapshot()
        if not settings.ai_enable_classifier:
            disabled_response: dict[str, object] = {
                "status": "ok",
                "service": "ai-worker",
                "mode": "disabled",
                "pending_jobs": queue_counts["pending"],
                "running_jobs": queue_counts["running"],
            }
            if snapshot.memory_rss_mb is not None:
                disabled_response["memory_rss_mb"] = snapshot.memory_rss_mb
            return disabled_response

        if not (worker.is_running() or worker.thread_alive()):
            detail = "Worker unavailable"
            if snapshot.last_error:
                detail = snapshot.last_error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )

        response: dict[str, object] = {
            "status": "ok",
            "service": "ai-worker",
            "pending_jobs": queue_counts["pending"],
            "running_jobs": queue_counts["running"],
        }
        if snapshot.memory_rss_mb is not None:
            response["memory_rss_mb"] = snapshot.memory_rss_mb
        return response

    return app


app = create_worker_app()
