"""Schemas related to wardrobe items."""

from __future__ import annotations

import datetime
import uuid

from pydantic import Field

from app.schemas.common import CamelModel


class ImageMetadata(CamelModel):
    width: int | None = None
    height: int | None = None
    bytes: int | None = Field(default=None, alias="bytes")
    mime_type: str | None = Field(default=None, alias="mimeType")
    checksum: str | None = None


class PresignRequest(CamelModel):
    content_type: str = Field(alias="contentType")
    file_name: str = Field(alias="fileName")


class PresignResponse(CamelModel):
    upload_url: str = Field(alias="uploadUrl")
    item_id: uuid.UUID = Field(alias="itemId")
    object_key: str | None = Field(default=None, alias="objectKey")


class ItemBase(CamelModel):
    id: uuid.UUID
    category: str
    color: str
    brand: str | None = None
    primary_color: str | None = Field(default=None, alias="primaryColor")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")
    image_url: str | None = Field(default=None, alias="imageUrl")
    thumb_url: str | None = Field(default=None, alias="thumbUrl")
    medium_url: str | None = Field(default=None, alias="mediumUrl")
    created_at: datetime.datetime = Field(alias="createdAt")
    image_metadata: ImageMetadata | None = Field(default=None, alias="imageMetadata")
    ai_confidence: float | None = Field(default=None, alias="aiConfidence")


class ItemDetail(ItemBase):
    tags: list[str]


class ItemUpdate(CamelModel):
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    tags: list[str] | None = None
    primary_color: str | None = Field(default=None, alias="primaryColor")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")


class CompleteUploadRequest(CamelModel):
    image_url: str | None = Field(default=None, alias="imageUrl")
    object_key: str | None = Field(default=None, alias="objectKey")
    file_name: str | None = Field(default=None, alias="fileName")


class ItemAIPreview(CamelModel):
    category: str | None = None
    category_confidence: float | None = Field(default=None, alias="categoryConfidence")
    primary_color: str | None = Field(default=None, alias="primaryColor")
    primary_color_confidence: float | None = Field(default=None, alias="primaryColorConfidence")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")
    secondary_color_confidence: float | None = Field(default=None, alias="secondaryColorConfidence")
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, alias="confidence")
