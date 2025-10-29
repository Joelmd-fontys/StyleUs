"""Image processing helpers for metadata extraction and variant generation."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}

THUMB_TARGET = 200
MEDIUM_TARGET = 800


@dataclass(slots=True)
class ProcessedImage:
    """Result container for processed image variants and metadata."""

    width: int
    height: int
    bytes: int
    mime_type: str
    checksum: str
    original_bytes: bytes
    medium_bytes: bytes
    thumb_bytes: bytes


def allowed_mime_types() -> Iterable[str]:
    """Expose the accepted MIME types."""
    return ALLOWED_MIME_TYPES.keys()


def _save_as_jpeg(image: Image.Image, *, max_size: int | None = None) -> bytes:
    """Return JPEG bytes for the provided image optionally constrained by size."""
    working = image.copy()
    if max_size is not None:
        working.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    working.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue()


def process_image_bytes(data: bytes, mime_type: str) -> ProcessedImage:
    """Produce normalized JPEG variants and metadata for the given image payload."""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    width, height = image.size
    original_bytes = _save_as_jpeg(image, max_size=None)
    medium_bytes = _save_as_jpeg(image, max_size=MEDIUM_TARGET)
    thumb_bytes = _save_as_jpeg(image, max_size=THUMB_TARGET)
    checksum = hashlib.sha256(original_bytes).hexdigest()

    return ProcessedImage(
        width=width,
        height=height,
        bytes=len(original_bytes),
        mime_type="image/jpeg",
        checksum=checksum,
        original_bytes=original_bytes,
        medium_bytes=medium_bytes,
        thumb_bytes=thumb_bytes,
    )


def save_image_bytes(destination: Path, data: bytes) -> None:
    """Persist image bytes to disk using a temporary file for atomic writes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(destination)
