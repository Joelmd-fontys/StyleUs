"""Application entrypoint."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING

import anyio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api import get_api_router
from app.core.config import Settings, get_settings
from app.core.errors import error_response
from app.core.logging import logger, request_id_ctx_var
from app.runtime.startup import run_startup_tasks
from app.runtime.worker_host import build_worker_lifespan, get_ai_worker_class

if TYPE_CHECKING:
    from app.ai.worker import AIWorker


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add essential security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


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


def _get_ai_worker_class() -> type[AIWorker]:
    return get_ai_worker_class()


def create_app(*, start_worker: bool = False) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await anyio.to_thread.run_sync(
            partial(run_startup_tasks, settings, include_seed=True),
        )
        worker_lifespan = build_worker_lifespan(
            settings,
            worker_class_getter=_get_ai_worker_class,
            start_worker=start_worker,
            thread_name="styleus-ai-worker",
        )
        async with worker_lifespan(app):
            yield

    app = FastAPI(title="StyleUs API", version=settings.app_version, lifespan=lifespan)

    app.add_middleware(SecurityHeadersMiddleware)
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
