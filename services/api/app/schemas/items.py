"""Schemas related to wardrobe items."""

from __future__ import annotations

import datetime
import uuid

from pydantic import Field

from app.schemas.common import CamelModel


class PresignRequest(CamelModel):
    content_type: str = Field(alias="contentType")
    file_name: str = Field(alias="fileName")


class PresignResponse(CamelModel):
    upload_url: str = Field(alias="uploadUrl")
    item_id: uuid.UUID = Field(alias="itemId")


class ItemBase(CamelModel):
    id: uuid.UUID
    category: str
    color: str
    brand: str | None = None
    image_url: str | None = Field(default=None, alias="imageUrl")
    created_at: datetime.datetime = Field(alias="createdAt")


class ItemDetail(ItemBase):
    tags: list[str]


class ItemUpdate(CamelModel):
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    tags: list[str] | None = None


class CompleteUploadRequest(CamelModel):
    image_url: str = Field(alias="imageUrl")
