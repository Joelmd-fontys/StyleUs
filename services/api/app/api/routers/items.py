"""Wardrobe item API routes."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db, verify_api_key
from app.core.errors import error_response
from app.models.wardrobe import WardrobeItem
from app.schemas.items import ItemAIPreview, ItemDetail, ItemUpdate
from app.services import items as items_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[ItemDetail], response_model_by_alias=True)
def list_wardrobe_items(
    *,
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    created_since: datetime.datetime | None = Query(default=None, alias="createdSince"),
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ItemDetail]:
    """Return wardrobe items for the current user applying optional filters."""

    items: Sequence[WardrobeItem] = items_service.list_items(
        db,
        user_id,
        category=category,
        query=q,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
        created_since=created_since,
    )
    return [items_service.to_item_detail(item) for item in items]


@router.get("/{item_id}", response_model=ItemDetail, response_model_by_alias=True)
def get_wardrobe_item(
    *,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ItemDetail | JSONResponse:
    """Fetch a single wardrobe item or respond with 404 if it is missing."""

    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response
    return items_service.to_item_detail(item)


@router.get("/{item_id}/ai-preview", response_model=ItemAIPreview, response_model_by_alias=True)
def get_item_ai_preview(
    *,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ItemAIPreview | JSONResponse:
    """Return the latest AI predictions for an item."""

    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response
    return items_service.to_ai_preview(item)


@router.patch("/{item_id}", response_model=ItemDetail, response_model_by_alias=True)
def update_wardrobe_item(
    *,
    item_id: uuid.UUID,
    payload: ItemUpdate,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ItemDetail | JSONResponse:
    """Update a wardrobe item and return the refreshed representation."""

    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    updated = items_service.update_item(
        db,
        item,
        category=payload.category,
        color=payload.color,
        brand=payload.brand,
        tags=payload.tags,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color,
    )
    return items_service.to_item_detail(updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wardrobe_item(
    *,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> Response:
    """Soft delete a wardrobe item for the current user."""

    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    items_service.delete_item(db, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
