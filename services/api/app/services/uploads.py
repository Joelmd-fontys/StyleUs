"""Upload service helpers."""

from __future__ import annotations

import contextlib
import json
import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.wardrobe import WardrobeItem
from app.schemas.items import ImageMetadata
from app.services.items import create_placeholder_item
from app.utils import s3 as s3_utils
from app.utils.images import (
    ProcessedImage,
    allowed_mime_types,
    process_image_bytes,
    save_image_bytes,
)
from app.utils.s3 import generate_presigned_put_url

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

UPLOAD_INFO_FILENAME = "_upload.json"


@dataclass(slots=True)
class UploadFinalizationResult:
    """Return value transporting URLs and metadata for a completed upload."""

    image_url: str
    medium_url: str | None
    thumb_url: str | None
    metadata: ImageMetadata


def _allowed_content_types() -> Iterable[str]:
    return ALLOWED_CONTENT_TYPES.keys()


def sanitize_file_name(name: str, *, default_extension: str) -> str:
    """Return a filesystem-safe name preserving a valid extension."""
    base, ext = os.path.splitext(name or "")
    sanitized_base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("._-")
    if not sanitized_base:
        sanitized_base = "image"

    ext = ext.lower()
    if ext not in ALLOWED_CONTENT_TYPES.values():
        ext = default_extension

    return f"{sanitized_base}{ext}"


def create_presigned_upload(
    db: Session,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    file_name: str,
    content_type: str,
) -> tuple[WardrobeItem, str, str | None]:
    """Create a wardrobe item placeholder and determine the appropriate upload target."""
    item = create_placeholder_item(db, user_id)

    if settings.is_s3_enabled:
        object_key = f"user/{user_id}/{item.id}/{file_name}"
        upload_url = generate_presigned_put_url(
            bucket=settings.s3_bucket_name,  # type: ignore[arg-type]
            key=object_key,
            content_type=content_type,
            region=settings.aws_region,  # type: ignore[arg-type]
        )
        return item, upload_url, object_key

    upload_url = f"/items/uploads/{item.id}"
    return item, upload_url, None


def save_local_upload(
    *,
    settings: Settings,
    item_id: uuid.UUID,
    file_name: str,
    content_type: str,
    data: bytes,
) -> Path:
    """Persist an uploaded image to the local media directory."""
    extension = ALLOWED_CONTENT_TYPES.get(content_type)
    if extension is None:
        allowed = ", ".join(sorted(_allowed_content_types()))
        raise ValueError(f"Unsupported content type: {content_type}. Allowed: {allowed}")
    safe_name = sanitize_file_name(file_name, default_extension=extension)

    media_dir = settings.media_root_path / str(item_id)
    media_dir.mkdir(parents=True, exist_ok=True)

    destination = media_dir / safe_name
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(destination)

    info_path = media_dir / UPLOAD_INFO_FILENAME
    info_path.write_text(
        json.dumps({"file_name": safe_name, "content_type": content_type}),
        encoding="utf-8",
    )
    return destination


def _load_local_upload_info(media_dir: Path) -> dict[str, Any] | None:
    info_path = media_dir / UPLOAD_INFO_FILENAME
    if not info_path.exists():
        return None
    try:
        loaded = json.loads(info_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - defensive
        return None
    if isinstance(loaded, dict):
        return cast(dict[str, Any], loaded)
    return None


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


def finalize_local_upload(
    settings: Settings,
    *,
    item_id: uuid.UUID,
    file_name: str | None,
) -> UploadFinalizationResult:
    """Generate variants and metadata for a locally stored upload."""
    media_dir = settings.media_root_path / str(item_id)
    info = _load_local_upload_info(media_dir) or {}
    content_type = info.get("content_type", "image/jpeg")

    if content_type not in allowed_mime_types():
        raise ValueError("Unsupported image content type")

    default_extension = ALLOWED_CONTENT_TYPES.get(content_type, ".jpg")
    safe_name = info.get("file_name")
    if file_name:
        safe_name = sanitize_file_name(file_name, default_extension=default_extension)

    if not safe_name:
        raise ValueError("Upload information missing; retry the upload")

    source_path = media_dir / safe_name
    data = source_path.read_bytes()
    processed = process_image_bytes(data, content_type)

    orig_path = media_dir / "orig.jpg"
    medium_path = media_dir / "medium.jpg"
    thumb_path = media_dir / "thumb.jpg"

    save_image_bytes(orig_path, processed.original_bytes)
    save_image_bytes(medium_path, processed.medium_bytes)
    save_image_bytes(thumb_path, processed.thumb_bytes)

    metadata = _update_metadata_with_bytes(processed)

    # Clean up temporary artifacts
    info_path = media_dir / UPLOAD_INFO_FILENAME
    with contextlib.suppress(FileNotFoundError):
        source_path.unlink()
    with contextlib.suppress(FileNotFoundError):
        info_path.unlink()

    base_url = f"{settings.media_url_path.rstrip('/')}/{item_id}"
    return UploadFinalizationResult(
        image_url=f"{base_url}/{orig_path.name}",
        medium_url=f"{base_url}/{medium_path.name}",
        thumb_url=f"{base_url}/{thumb_path.name}",
        metadata=metadata,
    )


def finalize_s3_upload(
    settings: Settings,
    *,
    item_id: uuid.UUID,
    object_key: str,
) -> UploadFinalizationResult:
    """Download from S3, generate variants, and upload them back."""
    if not settings.aws_region or not settings.s3_bucket_name:
        raise ValueError("AWS configuration missing")

    bucket = settings.s3_bucket_name
    region = settings.aws_region

    head = s3_utils.head_object(bucket=bucket, key=object_key, region=region)
    if head is None:
        raise ValueError("Uploaded object could not be found")

    content_type = head.get("ContentType") or "image/jpeg"
    if content_type not in allowed_mime_types():
        raise ValueError("Unsupported image content type")

    original_data = s3_utils.download_object(bucket=bucket, key=object_key, region=region)
    processed = process_image_bytes(original_data, content_type)

    base_prefix, _sep, _ = object_key.rpartition("/")
    prefix = f"{base_prefix}/" if base_prefix else ""

    orig_key = f"{prefix}orig.jpg"
    medium_key = f"{prefix}medium.jpg"
    thumb_key = f"{prefix}thumb.jpg"

    s3_utils.upload_bytes(
        bucket=bucket,
        key=orig_key,
        region=region,
        data=processed.original_bytes,
        content_type="image/jpeg",
    )
    s3_utils.upload_bytes(
        bucket=bucket,
        key=medium_key,
        region=region,
        data=processed.medium_bytes,
        content_type="image/jpeg",
    )
    s3_utils.upload_bytes(
        bucket=bucket,
        key=thumb_key,
        region=region,
        data=processed.thumb_bytes,
        content_type="image/jpeg",
    )

    metadata = _update_metadata_with_bytes(processed)

    return UploadFinalizationResult(
        image_url=build_public_s3_url(settings, object_key=orig_key),
        medium_url=build_public_s3_url(settings, object_key=medium_key),
        thumb_url=build_public_s3_url(settings, object_key=thumb_key),
        metadata=metadata,
    )
def build_public_s3_url(settings: Settings, *, object_key: str) -> str:
    """Construct an S3 object URL suitable for public consumption."""
    region = settings.aws_region or ""
    bucket = settings.s3_bucket_name or ""
    return f"https://{bucket}.s3.{region}.amazonaws.com/{object_key}"
