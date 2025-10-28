"""Upload service helpers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.wardrobe import WardrobeItem
from app.services.items import create_placeholder_item
from app.utils.s3 import generate_presigned_put_url


def create_presigned_upload(
    db: Session,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    file_name: str,
    content_type: str,
) -> tuple[WardrobeItem, str, str]:
    if not settings.aws_region or not settings.s3_bucket_name:
        raise RuntimeError("AWS configuration is incomplete")

    item = create_placeholder_item(db, user_id)
    object_key = f"user/{user_id}/{item.id}/{file_name}"
    upload_url = generate_presigned_put_url(
        bucket=settings.s3_bucket_name,
        key=object_key,
        content_type=content_type,
        region=settings.aws_region,
    )
    return item, upload_url, object_key
