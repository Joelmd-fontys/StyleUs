"""Upload and presign endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user_id,
    get_db,
    get_settings_dependency,
    verify_api_key,
)
from app.core.config import Settings
from app.core.errors import error_response
from app.schemas.items import CompleteUploadRequest, ItemDetail, PresignRequest, PresignResponse
from app.services import items as items_service
from app.services import uploads as uploads_service

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/presign", response_model=PresignResponse, response_model_by_alias=True)
def create_presigned_upload(
    *,
    payload: PresignRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dependency),
) -> PresignResponse:
    try:
        item, upload_url, _ = uploads_service.create_presigned_upload(
            db,
            settings,
            user_id=user_id,
            file_name=payload.file_name,
            content_type=payload.content_type,
        )
    except RuntimeError as exc:
        response = error_response("configuration_error", str(exc), None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response

    return PresignResponse(upload_url=upload_url, item_id=item.id)


@router.post("/{item_id}/complete-upload", response_model=ItemDetail, response_model_by_alias=True)
def complete_upload(
    *,
    item_id: uuid.UUID,
    payload: CompleteUploadRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ItemDetail:
    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    updated = items_service.complete_upload(db, item, payload.image_url)
    return items_service.to_item_detail(updated)
