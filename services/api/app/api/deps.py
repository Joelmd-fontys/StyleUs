"""Reusable FastAPI dependencies."""

from __future__ import annotations

import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthVerificationError,
    CurrentUser,
    build_local_current_user,
    get_token_verifier,
)
from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.services.users import sync_authenticated_user

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session scoped to the lifetime of the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings_dependency() -> Settings:
    """Expose configured settings for dependency injection."""
    return get_settings()


def get_current_user(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dependency),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Resolve the current user from a Supabase bearer token or explicit local bypass."""
    if credentials is None:
        if settings.local_auth_bypass_enabled:
            current_user = build_local_current_user(settings)
            sync_authenticated_user(
                db,
                user_id=current_user.id,
                email=current_user.email,
            )
            return current_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        current_user = get_token_verifier(settings).verify(credentials.credentials)
    except AuthVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sync_authenticated_user(
        db,
        user_id=current_user.id,
        email=current_user.email,
    )
    return current_user


def get_current_user_id(current_user: CurrentUser = Depends(get_current_user)) -> uuid.UUID:
    """Return the authenticated user identifier for downstream route handlers."""
    return current_user.id
