"""API package exporting routers."""

from fastapi import APIRouter

from app.api.routers import health, items, uploads, version


def get_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router, tags=["health"])
    router.include_router(version.router, tags=["health"])
    router.include_router(items.router, prefix="/items", tags=["items"])
    router.include_router(uploads.router, prefix="/items", tags=["uploads"])
    return router


__all__ = ["get_api_router"]
