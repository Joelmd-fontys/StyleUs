"""Reusable FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings_dependency() -> Settings:
    return get_settings()


def verify_api_key(
    settings: Settings = Depends(get_settings_dependency),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not settings.is_secure_env:
        return
    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "configuration_error", "message": "API key is not configured"},
        )
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid API key"},
        )


def get_current_user_id() -> uuid.UUID:
    return DEFAULT_USER_ID
