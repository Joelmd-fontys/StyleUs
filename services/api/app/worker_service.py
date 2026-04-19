"""Minimal web service wrapper around the AI worker loop."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

import anyio
from fastapi import FastAPI, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.runtime.startup import run_startup_tasks
from app.runtime.worker_host import build_worker_lifespan, get_ai_worker_class
from app.services import ai_jobs as ai_jobs_service

if TYPE_CHECKING:
    from app.ai.worker import AIWorker


def _get_ai_worker_class() -> type[AIWorker]:
    return get_ai_worker_class()


def create_worker_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await anyio.to_thread.run_sync(
            partial(run_startup_tasks, settings, include_seed=False, service_name="ai-worker"),
        )
        worker_lifespan = build_worker_lifespan(
            settings,
            worker_class_getter=_get_ai_worker_class,
            start_worker=True,
            thread_name="styleus-ai-worker-service",
            shutdown_reason="worker_service_shutdown",
            shutdown_timeout_extra={"service": "ai-worker"},
        )
        async with worker_lifespan(app):
            yield

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
