"""Shared error handling helpers."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def error_response(code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    """Produce a standardized error response payload."""

    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        payload["details"] = details
    return JSONResponse(content=payload)
