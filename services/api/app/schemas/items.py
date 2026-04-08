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
    file_size: int = Field(alias="fileSize")


class PresignResponse(CamelModel):
    upload_url: str = Field(alias="uploadUrl")
    item_id: uuid.UUID = Field(alias="itemId")
    object_key: str | None = Field(default=None, alias="objectKey")
    upload_token: str | None = Field(default=None, alias="uploadToken")
    bucket: str | None = None


class ItemBase(CamelModel):
    id: uuid.UUID
    category: str
    subcategory: str | None = None
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


class ItemAIAttributes(CamelModel):
    category: str | None = None
    subcategory: str | None = None
    materials: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list, alias="styleTags")
    attributes: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, alias="confidence")


class AIJobState(CamelModel):
    id: uuid.UUID
    status: str
    attempts: int
    created_at: datetime.datetime = Field(alias="createdAt")
    started_at: datetime.datetime | None = Field(default=None, alias="startedAt")
    completed_at: datetime.datetime | None = Field(default=None, alias="completedAt")
    error_message: str | None = Field(default=None, alias="errorMessage")
    pending: bool = False


class ItemDetail(ItemBase):
    tags: list[str]
    ai: ItemAIAttributes | None = None
    ai_job: AIJobState | None = Field(default=None, alias="aiJob")


class ItemReviewFeedback(CamelModel):
    predicted_category: str | None = Field(default=None, alias="predictedCategory")
    prediction_confidence: float | None = Field(default=None, alias="predictionConfidence")
    accepted_directly: bool = Field(alias="acceptedDirectly")


class ItemUpdate(CamelModel):
    category: str | None = None
    subcategory: str | None = None
    color: str | None = None
    brand: str | None = None
    tags: list[str] | None = None
    primary_color: str | None = Field(default=None, alias="primaryColor")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")
    review_feedback: ItemReviewFeedback | None = Field(default=None, alias="reviewFeedback")


class CompleteUploadRequest(CamelModel):
    image_url: str | None = Field(default=None, alias="imageUrl")
    object_key: str | None = Field(default=None, alias="objectKey")
    file_name: str | None = Field(default=None, alias="fileName")


class ItemAIPreview(CamelModel):
    category: str | None = None
    category_confidence: float | None = Field(default=None, alias="categoryConfidence")
    subcategory: str | None = None
    subcategory_confidence: float | None = Field(
        default=None,
        alias="subcategoryConfidence",
    )
    primary_color: str | None = Field(default=None, alias="primaryColor")
    primary_color_confidence: float | None = Field(default=None, alias="primaryColorConfidence")
    secondary_color: str | None = Field(default=None, alias="secondaryColor")
    secondary_color_confidence: float | None = Field(default=None, alias="secondaryColorConfidence")
    materials: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list, alias="styleTags")
    attributes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tag_confidences: dict[str, float] = Field(default_factory=dict, alias="tagConfidences")
    confidence: float | None = Field(default=None, alias="confidence")
    uncertain: bool = False
    uncertain_fields: list[str] = Field(default_factory=list, alias="uncertainFields")
    pending: bool = False
    job: AIJobState | None = None
