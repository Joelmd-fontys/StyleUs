"""Application entrypoint."""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import get_api_router
from app.core.config import get_settings
from app.core.errors import error_response
from app.core.logging import logger, request_id_ctx_var
from app.db.migrations import ensure_schema


def _maybe_run_seed(settings):
    if settings.app_env != "local":
        return
    if not settings.seed_on_start:
        return
    try:
        from app.seed.runner import run_seed

        run_seed(settings=settings)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("seed.failed")


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await anyio.to_thread.run_sync(ensure_schema)
        await anyio.to_thread.run_sync(_maybe_run_seed, settings)
        yield

    app = FastAPI(title="StyleUs API", version=settings.app_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    media_root = settings.media_root_path
    media_root.mkdir(parents=True, exist_ok=True)
    app.mount(settings.media_url_path, StaticFiles(directory=media_root), name="media")

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx_var.set(request_id)
        start = time.perf_counter()
        response = None
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
            details = {"error": str(exc)} if settings.app_env == "local" else None
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
        return response

    app.include_router(get_api_router())

    return app


app = create_app()
