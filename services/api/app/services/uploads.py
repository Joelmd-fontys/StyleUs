"""Upload service helpers."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
import logging

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.wardrobe import WardrobeItem
from app.schemas.items import ImageMetadata
from app.services.items import create_placeholder_item
from app.utils import storage as storage_utils
from app.utils.images import ProcessedImage, allowed_mime_types, process_image_bytes

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_EMPTY_FILE_NAMES = {"", ".", ".."}
_SOURCE_SEGMENT = "source"
LOGGER = logging.getLogger("app.services.uploads")


@dataclass(slots=True)
class UploadSlot:
    item: WardrobeItem
    upload_url: str
    object_key: str
    upload_token: str | None
    bucket: str


@dataclass(slots=True)
class UploadFinalizationResult:
    """Return value transporting object paths and metadata for a completed upload."""

    image_object_path: str
    medium_object_path: str | None
    thumb_object_path: str | None
    metadata: ImageMetadata


def sanitize_file_name(name: str, *, default_extension: str) -> str:
    """Return a storage-safe name preserving a valid extension."""
    stripped = (name or "").strip()
    sanitized = stripped.split("/")[-1].split("\\")[-1]
    base, dot, ext = sanitized.rpartition(".")
    stem = base if dot else sanitized
    normalized_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("._-")
    if normalized_stem in _EMPTY_FILE_NAMES or not normalized_stem:
        normalized_stem = "image"

    normalized_extension = f".{ext.lower()}" if dot else ""
    if normalized_extension not in ALLOWED_CONTENT_TYPES.values():
        normalized_extension = default_extension

    return f"{normalized_stem}{normalized_extension}"


def validate_upload_request(
    settings: Settings,
    *,
    file_name: str,
    content_type: str,
    file_size: int,
) -> str:
    """Validate presign request fields and return a normalized file name."""
    normalized_content_type = content_type.strip().lower()
    extension = ALLOWED_CONTENT_TYPES.get(normalized_content_type)
    if extension is None:
        allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
        raise ValueError(f"Unsupported content type: {normalized_content_type}. Allowed: {allowed}")
    if file_size <= 0:
        raise ValueError("Upload size must be greater than zero")
    if file_size > settings.media_max_upload_size:
        raise ValueError("Upload exceeds maximum allowed size")
    return sanitize_file_name(file_name, default_extension=extension)


def create_presigned_upload(
    db: Session,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    file_name: str,
    content_type: str,
    file_size: int,
) -> UploadSlot:
    """Create a wardrobe item placeholder and return a signed upload target."""
    safe_name = validate_upload_request(
        settings,
        file_name=file_name,
        content_type=content_type,
        file_size=file_size,
    )
    item = create_placeholder_item(db, user_id)
    object_key = build_source_object_key(user_id=user_id, item_id=item.id, file_name=safe_name)
    try:
        signed_target = storage_utils.get_storage_adapter(settings).create_signed_upload_target(
            object_key
        )
    except Exception:
        db.delete(item)
        db.commit()
        raise
    return UploadSlot(
        item=item,
        upload_url=signed_target.upload_url,
        object_key=signed_target.object_path,
        upload_token=signed_target.token,
        bucket=signed_target.bucket,
    )


def build_source_object_key(*, user_id: uuid.UUID, item_id: uuid.UUID, file_name: str) -> str:
    return f"users/{user_id}/{item_id}/{_SOURCE_SEGMENT}/{file_name}"


def build_variant_object_keys(*, user_id: uuid.UUID, item_id: uuid.UUID) -> tuple[str, str, str]:
    prefix = f"users/{user_id}/{item_id}"
    return (
        f"{prefix}/orig.jpg",
        f"{prefix}/medium.jpg",
        f"{prefix}/thumb.jpg",
    )


def finalize_supabase_upload(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    object_key: str,
) -> UploadFinalizationResult:
    """Download the private source upload, create variants, and store them privately."""
    _validate_object_key(user_id=user_id, item_id=item_id, object_key=object_key)

    storage = storage_utils.get_storage_adapter(settings)
    object_info = storage.get_object_info(object_key)
    size = _extract_object_size(object_info)
    if size is not None and size > settings.media_max_upload_size:
        raise ValueError("Upload exceeds maximum allowed size")

    source = storage.download_object(object_key)
    content_type = _resolve_uploaded_content_type(source.content_type, object_info)
    if content_type not in allowed_mime_types():
        raise ValueError("Unsupported image content type")

    processed = process_image_bytes(source.data, content_type)
    orig_key, medium_key, thumb_key = build_variant_object_keys(user_id=user_id, item_id=item_id)

    _upload_variants(
        storage,
        original_key=orig_key,
        medium_key=medium_key,
        thumb_key=thumb_key,
        processed=processed,
    )
    try:
        storage.delete_objects([object_key])
    except storage_utils.SupabaseStorageError as exc:
        LOGGER.warning(
            "uploads.cleanup_source_failed",
            extra={"object_key": object_key, "error": str(exc)},
        )

    metadata = _update_metadata_with_bytes(processed)
    return UploadFinalizationResult(
        image_object_path=orig_key,
        medium_object_path=medium_key,
        thumb_object_path=thumb_key,
        metadata=metadata,
    )


def _validate_object_key(*, user_id: uuid.UUID, item_id: uuid.UUID, object_key: str) -> None:
    expected_prefix = f"users/{user_id}/{item_id}/{_SOURCE_SEGMENT}/"
    normalized = object_key.lstrip("/")
    if not normalized.startswith(expected_prefix):
        raise ValueError("Upload object path is invalid for this item")


def _extract_object_size(object_info: dict[str, object]) -> int | None:
    for key in ("size", "bytes", "contentLength"):
        value = object_info.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    metadata = object_info.get("metadata")
    if isinstance(metadata, dict):
        for key in ("size", "bytes"):
            value = metadata.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return None


def _resolve_uploaded_content_type(
    download_content_type: str | None,
    object_info: dict[str, object],
) -> str:
    candidates = [download_content_type]
    metadata = object_info.get("metadata")
    if isinstance(metadata, dict):
        candidates.extend(
            value
            for value in (
                metadata.get("mimetype"),
                metadata.get("contentType"),
            )
            if isinstance(value, str)
        )
    candidates.extend(
        value
        for value in (
            object_info.get("mimetype"),
            object_info.get("contentType"),
        )
        if isinstance(value, str)
    )
    for candidate in candidates:
        normalized = (candidate or "").split(";")[0].strip().lower()
        if normalized:
            return normalized
    return "image/jpeg"


def _upload_variants(
    storage: storage_utils.SupabaseStorageAdapter,
    *,
    original_key: str,
    medium_key: str,
    thumb_key: str,
    processed: ProcessedImage,
) -> None:
    storage.upload_bytes(
        original_key,
        data=processed.original_bytes,
        content_type="image/jpeg",
    )
    storage.upload_bytes(
        medium_key,
        data=processed.medium_bytes,
        content_type="image/jpeg",
    )
    storage.upload_bytes(
        thumb_key,
        data=processed.thumb_bytes,
        content_type="image/jpeg",
    )


def _update_metadata_with_bytes(processed: ProcessedImage) -> ImageMetadata:
    return ImageMetadata.model_validate(
        {
            "width": processed.width,
            "height": processed.height,
            "bytes": processed.size_bytes,
            "mime_type": processed.mime_type,
            "checksum": processed.checksum,
        }
    )
