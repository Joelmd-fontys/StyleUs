"""Health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, response_model_by_alias=True)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)
