"""Upload and presign endpoints."""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user_id,
    get_db,
    get_settings_dependency,
)
from app.core.config import Settings
from app.core.errors import error_response
from app.core.logging import logger
from app.schemas.items import CompleteUploadRequest, ItemDetail, PresignRequest, PresignResponse
from app.services import ai_jobs as ai_jobs_service
from app.services import items as items_service
from app.services import uploads as uploads_service
from app.utils import storage as storage_utils

router = APIRouter()


def _run_inline_ai_enrichment(db: Session, *, item_id: uuid.UUID) -> None:
    from app.ai.tasks import AIEnrichmentError, run_item_enrichment

    try:
        run_item_enrichment(db, item_id, commit=True)
    except AIEnrichmentError as exc:
        db.rollback()
        logger.warning(
            "upload.inline_ai_failed",
            extra={"item_id": str(item_id), "error": str(exc), "mode": "heuristic_inline"},
        )
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        logger.exception(
            "upload.inline_ai_failed_unexpected",
            extra={"item_id": str(item_id), "error": str(exc), "mode": "heuristic_inline"},
        )


@router.post("/presign", response_model=PresignResponse, response_model_by_alias=True)
def create_presigned_upload(
    *,
    payload: PresignRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
    settings: Settings = Depends(get_settings_dependency),
) -> PresignResponse | JSONResponse:
    """Create an upload session for the client and return a signed Supabase upload target."""
    try:
        slot = uploads_service.create_presigned_upload(
            db,
            settings,
            user_id=user_id,
            file_name=payload.file_name,
            content_type=payload.content_type,
            file_size=payload.file_size,
        )
    except ValueError as exc:
        response = error_response("invalid_upload", str(exc), None)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response
    except storage_utils.SupabaseStorageError as exc:
        response = error_response("upload_error", str(exc), None)
        response.status_code = status.HTTP_502_BAD_GATEWAY
        return response
    except RuntimeError as exc:
        response = error_response("configuration_error", str(exc), None)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response

    return PresignResponse.model_validate(
        {
            "upload_url": slot.upload_url,
            "item_id": slot.item.id,
            "object_key": slot.object_key,
            "upload_token": slot.upload_token,
            "bucket": slot.bucket,
        }
    )


@router.put("/uploads/{item_id}")
async def upload_blob(*, item_id: uuid.UUID) -> JSONResponse:
    """Legacy route kept only to point clients at the direct-storage upload flow."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "deprecated_upload_sink",
            "message": (
                "Binary uploads are no longer accepted by the API. "
                "Request a signed upload target from POST /items/presign instead."
            ),
            "itemId": str(item_id),
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
) -> ItemDetail | JSONResponse:
    """Finalize an upload by persisting private storage paths for the wardrobe item."""
    item = items_service.get_item(db, user_id, item_id)
    if not item:
        response = error_response("not_found", "Wardrobe item not found", {"itemId": str(item_id)})
        response.status_code = status.HTTP_404_NOT_FOUND
        return response

    started = time.perf_counter()
    try:
        if not payload.object_key:
            response = error_response(
                "invalid_request",
                "objectKey is required when completing uploads",
                None,
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response
        result = uploads_service.finalize_supabase_upload(
            settings,
            user_id=user_id,
            item_id=item_id,
            object_key=payload.object_key,
        )
    except ValueError as exc:
        logger.warning(
            "upload.complete_validation_failed",
            extra={
                "item_id": str(item_id),
                "reason": str(exc),
                "mode": "supabase",
            },
        )
        response = error_response("invalid_upload", str(exc), None)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response
    except storage_utils.SupabaseStorageNotFoundError as exc:
        logger.warning(
            "upload.complete_missing_source",
            extra={
                "item_id": str(item_id),
                "reason": str(exc),
                "mode": "supabase",
            },
        )
        response = error_response("invalid_upload", str(exc), None)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response
    except storage_utils.SupabaseStorageError as exc:
        logger.warning(
            "upload.complete_storage_failed",
            extra={
                "item_id": str(item_id),
                "reason": str(exc),
                "mode": "supabase",
            },
        )
        response = error_response("upload_error", str(exc), None)
        response.status_code = status.HTTP_502_BAD_GATEWAY
        return response
    except Exception as exc:  # pragma: no cover - unexpected failure
        logger.exception(
            "upload.complete_failed",
            extra={
                "item_id": str(item_id),
                "mode": "supabase",
                "error": str(exc),
            },
        )
        details = {"error": str(exc)} if settings.app_env == "local" else None
        response = error_response("upload_error", "Unable to finalize upload", details)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response

    try:
        updated = items_service.complete_upload(
            db,
            item,
            result.image_object_path,
            thumb_object_path=result.thumb_object_path,
            medium_object_path=result.medium_object_path,
            metadata=result.metadata,
            commit=False,
        )
        db.commit()
        if settings.ai_enable_classifier:
            try:
                ai_jobs_service.enqueue_item_job(db, updated, commit=True)
            except Exception as exc:  # pragma: no cover - defensive
                db.rollback()
                logger.exception(
                    "upload.enqueue_ai_job_failed",
                    extra={"item_id": str(item_id), "error": str(exc)},
                )
        else:
            _run_inline_ai_enrichment(db, item_id=item_id)
        refreshed = items_service.get_item(db, user_id, item_id)
        if refreshed is not None:
            updated = refreshed
    except Exception as exc:  # pragma: no cover - defensive
        db.rollback()
        logger.exception(
            "upload.complete_persist_failed",
            extra={"item_id": str(item_id), "error": str(exc)},
        )
        details = {"error": str(exc)} if settings.app_env == "local" else None
        response = error_response("upload_error", "Unable to persist upload metadata", details)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return response
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "upload.completed",
        extra={
            "item_id": str(item_id),
            "object_path": result.image_object_path,
            "thumb_object_path": result.thumb_object_path,
            "medium_object_path": result.medium_object_path,
            "mode": "supabase",
            "duration_ms": duration_ms,
        },
    )
    signed_urls = items_service.build_signed_media_urls(settings, [updated])
    return items_service.to_item_detail(updated, signed_urls=signed_urls)
