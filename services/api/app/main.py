"""Application entrypoint."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.ai.worker import AIWorker
from app.api import get_api_router
from app.core.config import Settings, get_settings
from app.core.errors import error_response
from app.core.logging import logger, request_id_ctx_var
from app.db.migrations import ensure_schema

_WORKER_SHUTDOWN_TIMEOUT_SECONDS = 30.0


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request ids and consistent error logging to every request."""

    def __init__(self, app, *, settings: Settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx_var.set(request_id)
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception(
                "request.error",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "error": str(exc),
                },
            )
            details = {"error": str(exc)} if self._settings.app_env == "local" else None
            response = error_response("internal_error", "Internal server error", details)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            if response is not None:
                response.headers["X-Request-ID"] = request_id
                logger.info(
                    "request.complete",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "status_code": response.status_code,
                        "latency_ms": latency_ms,
                    },
                )
            request_id_ctx_var.reset(token)
        assert response is not None
        return response


def _maybe_run_migrations(settings: Settings) -> None:
    if not settings.run_migrations_on_start:
        logger.info("startup.migrations_skipped", extra={"app_env": settings.app_env})
        return
    logger.info("startup.migrations_started", extra={"app_env": settings.app_env})
    ensure_schema()


def _maybe_run_seed(settings: Settings) -> None:
    if not settings.run_seed_on_start:
        logger.info("startup.seed_skipped", extra={"app_env": settings.app_env})
        return
    try:
        from app.seed.runner import run_seed

        logger.info("startup.seed_started", extra={"app_env": settings.app_env})
        run_seed(settings=settings)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("seed.failed")


def create_app(*, start_worker: bool = False) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        worker: AIWorker | None = None
        await anyio.to_thread.run_sync(_maybe_run_migrations, settings)
        await anyio.to_thread.run_sync(_maybe_run_seed, settings)
        if start_worker:
            worker = AIWorker(settings)
            worker.start_in_background()
            app.state.ai_worker = worker
        else:
            app.state.ai_worker = None
            logger.info(
                "worker.startup_skipped",
                extra={"reason": "disabled_for_app_instance"},
            )
        try:
            yield
        finally:
            if worker is not None:
                worker.request_shutdown(reason="lifespan_shutdown")
                stopped = await anyio.to_thread.run_sync(
                    worker.join,
                    _WORKER_SHUTDOWN_TIMEOUT_SECONDS,
                )
                if not stopped:
                    logger.warning(
                        "worker.shutdown_timeout",
                        extra={"timeout_seconds": _WORKER_SHUTDOWN_TIMEOUT_SECONDS},
                    )
            app.state.ai_worker = None

    app = FastAPI(title="StyleUs API", version=settings.app_version, lifespan=lifespan)

    app.add_middleware(RequestContextMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(get_api_router())

    return app


app = create_app(start_worker=False)
