"""Upload and presign endpoints."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user_id,
    get_db,
    get_settings_dependency,
    verify_api_key,
)
from app.core.config import Settings
from app.core.errors import error_response
from app.core.logging import logger
from app.schemas.items import CompleteUploadRequest, ItemDetail, PresignRequest, PresignResponse
from app.services import items as items_service
from app.services import uploads as uploads_service

ALLOWED_PUT_CONTENT_TYPES = set(uploads_service.ALLOWED_CONTENT_TYPES.keys())

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/presign", response_model=PresignResponse, response_model_by_alias=True)
def create_presigned_upload(
    *,
    payload: PresignRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dependency),
) -> PresignResponse:
    """Create an upload session for the client, returning either an S3 URL or local API sink."""
    try:
        item, upload_url, object_key = uploads_service.create_presigned_upload(
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

    return PresignResponse(upload_url=upload_url, item_id=item.id, object_key=object_key)


@router.put("/uploads/{item_id}")
async def upload_blob(
    *,
    item_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dependency),
) -> JSONResponse:
    """Accept the binary payload for a local-mode upload."""
    if settings.is_s3_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    content_type = request.headers.get("content-type")
    normalized_content_type = content_type.lower() if content_type else None
    if not normalized_content_type or normalized_content_type not in ALLOWED_PUT_CONTENT_TYPES:
        detail = {
            "code": "unsupported_media_type",
            "message": "Only JPEG, PNG, and WEBP images are allowed",
        }
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)

    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            content_length = int(content_length_header)
        except ValueError:
            content_length = None
        else:
            if content_length > settings.media_max_upload_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "code": "file_too_large",
                        "message": "Upload exceeds maximum allowed size",
                    },
                )

    body = await request.body()
    if len(body) > settings.media_max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "file_too_large",
                "message": "Upload exceeds maximum allowed size",
            },
        )

    requested_file_name = request.headers.get("X-File-Name", "image")
    saved_path = uploads_service.save_local_upload(
        settings=settings,
        item_id=item_id,
        file_name=requested_file_name,
        content_type=normalized_content_type,
        data=body,
    )

    logger.info(
        "upload.saved",
        extra={
            "item_id": str(item_id),
            "content_type": normalized_content_type,
            "path": str(saved_path),
        },
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "fileName": saved_path.name,
            "path": str(saved_path.relative_to(settings.media_root_path)),
        },
    )


@router.post("/{item_id}/complete-upload", response_model=ItemDetail, response_model_by_alias=True)
def complete_upload(
    *,
    item_id: uuid.UUID,
    payload: CompleteUploadRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dependency),
) -> ItemDetail:
    """Finalize an upload by persisting the public image URL for the wardrobe item."""
    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    started = time.perf_counter()
    try:
        if settings.is_s3_enabled:
            if not payload.object_key:
                response = error_response(
                    "invalid_request",
                    "objectKey is required when completing uploads in S3 mode",
                    None,
                )
                response.status_code = status.HTTP_400_BAD_REQUEST
                return response
            result = uploads_service.finalize_s3_upload(
                settings,
                item_id=item_id,
                object_key=payload.object_key,
            )
        else:
            result = uploads_service.finalize_local_upload(
                settings,
                item_id=item_id,
                file_name=payload.file_name,
            )
    except ValueError as exc:
        response = error_response("invalid_upload", str(exc), None)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response

    updated = items_service.complete_upload(
        db,
        item,
        result.image_url,
        thumb_url=result.thumb_url,
        medium_url=result.medium_url,
        metadata=result.metadata,
    )
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "upload.completed",
        extra={
            "item_id": str(item_id),
            "url": result.image_url,
            "thumb_url": result.thumb_url,
            "medium_url": result.medium_url,
            "mode": "s3" if settings.is_s3_enabled else "local",
            "duration_ms": duration_ms,
        },
    )
    return items_service.to_item_detail(updated)
