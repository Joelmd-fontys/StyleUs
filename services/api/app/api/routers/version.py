"""Version endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import VersionResponse

router = APIRouter()


@router.get("/version", response_model=VersionResponse, response_model_by_alias=True)
def version() -> VersionResponse:
    return VersionResponse(version=settings.app_version)
