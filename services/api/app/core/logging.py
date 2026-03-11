"""Logging configuration utilities."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_STANDARD_LOG_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__.keys())


class RequestIdFilter(logging.Filter):
    """Inject the current request id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: MutableMapping[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }

        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id  # type: ignore[attr-defined]
        if getattr(record, "path", None):
            payload["path"] = record.path  # type: ignore[attr-defined]
        if getattr(record, "method", None):
            payload["method"] = record.method  # type: ignore[attr-defined]
        if getattr(record, "status_code", None) is not None:
            payload["status_code"] = record.status_code  # type: ignore[attr-defined]
        if getattr(record, "latency_ms", None) is not None:
            payload["latency_ms"] = record.latency_ms  # type: ignore[attr-defined]
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_KEYS or key in payload or key.startswith("_"):
                continue
            if value is None:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> logging.Logger:
    """Configure root logging once and return the application logger."""

    logger = logging.getLogger("styleus.api")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.INFO)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    app_logger = logging.getLogger("app")
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    # Ensure uvicorn and fastapi loggers align with our formatting.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("uvicorn.access").addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn").propagate = False
    logging.getLogger("uvicorn.error").propagate = False
    logging.getLogger("uvicorn.access").propagate = False

    return logger


logger = configure_logging()
