"""Utility helpers used by the seeding pipeline."""

from __future__ import annotations

import io
import re
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from PIL import Image

MAX_REMOTE_BYTES = 10 * 1024 * 1024  # 10MB ceiling for remote assets
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass(slots=True)
class SeedSource:
    """Represents a curated wardrobe item definition."""

    title: str
    brand: str | None
    category: str
    color: str | None
    tags: Sequence[str]
    image_path: str

    @property
    def slug(self) -> str:
        brand_prefix = self.brand or "styleus"
        base = re.sub(
            r"[^a-z0-9]+",
            "-",
            f"{brand_prefix}-{self.title}".lower(),
        ).strip("-")
        return base or "seed-item"


class SeedSourceError(RuntimeError):
    """Raised when a source entry is invalid."""


def _category_set() -> set[str]:
    return {"top", "bottom", "outerwear", "shoes", "accessory"}


def load_seed_sources(config_path: Path, *, limit: int | None = None) -> list[SeedSource]:
    """Parse the curated YAML configuration into SeedSource objects."""
    if not config_path.exists():
        raise SeedSourceError(f"Seed configuration missing: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    items: Iterable[dict] = raw.get("items") or []

    sources: list[SeedSource] = []
    for item in items:
        title = _require_str(item, "title")
        brand = item.get("brand")
        category = _require_str(item, "category").lower()
        if category not in _category_set():
            raise SeedSourceError(f"Unsupported category '{category}' in seed '{title}'")
        color = item.get("color")
        tags = _parse_tags(item.get("tags"))
        image_path = _require_str(item, "image")
        sources.append(
            SeedSource(
                title=title,
                brand=brand,
                category=category,
                color=color,
                tags=tags,
                image_path=image_path,
            )
        )
        if limit is not None and len(sources) >= limit:
            break
    return sources


def _require_str(item: dict, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SeedSourceError(f"Seed item missing required '{key}' value")
    return value.strip()


def _parse_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        cleaned: list[str] = []
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                cleaned.append(entry.strip())
        return cleaned
    raise SeedSourceError("Tags must be a sequence of strings")


def read_image_bytes(base_path: Path, source: SeedSource) -> tuple[bytes, str, str]:
    """Load image bytes either from a bundled file or a remote URL."""
    image_ref = source.image_path
    if image_ref.startswith("http://") or image_ref.startswith("https://"):
        return _load_remote_image(image_ref, source.slug)
    return _load_local_image(base_path / image_ref, source.slug)


def _load_local_image(path: Path, slug: str) -> tuple[bytes, str, str]:
    if not path.exists():
        raise SeedSourceError(f"Local image not found for seed '{slug}': {path}")
    data = path.read_bytes()
    content_type = _infer_content_type(path.suffix)
    return data, content_type, path.name


def _load_remote_image(url: str, slug: str) -> tuple[bytes, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "StyleUsSeeder/1.0"})
    with urllib.request.urlopen(request, timeout=10) as response:
        content_length = response.getheader("Content-Length")
        if content_length and int(content_length) > MAX_REMOTE_BYTES:
            raise SeedSourceError(f"Remote image too large for seed '{slug}'")
        data = response.read(MAX_REMOTE_BYTES + 1)
        if len(data) > MAX_REMOTE_BYTES:
            raise SeedSourceError(
                f"Remote image exceeded {MAX_REMOTE_BYTES} bytes for seed '{slug}'",
            )
        content_type = response.getheader("Content-Type", "").split(";")[0].strip()
    if content_type not in ALLOWED_CONTENT_TYPES.values():
        raise SeedSourceError(f"Unsupported remote content type '{content_type}' for seed '{slug}'")
    file_extension = _extension_from_content_type(content_type)
    file_name = f"{slug}{file_extension}"
    return data, content_type, file_name


def _infer_content_type(extension: str) -> str:
    extension = extension.lower()
    if extension not in ALLOWED_CONTENT_TYPES:
        raise SeedSourceError(f"Unsupported image extension '{extension}'")
    return ALLOWED_CONTENT_TYPES[extension]


def _extension_from_content_type(content_type: str) -> str:
    for ext, ctype in ALLOWED_CONTENT_TYPES.items():
        if ctype == content_type:
            return ext
    raise SeedSourceError(f"Unsupported content type '{content_type}'")


def validate_image(data: bytes, content_type: str, slug: str) -> None:
    """Ensure the image bytes can be parsed before writing to disk."""
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise SeedSourceError(f"Image validation failed for seed '{slug}': {exc}") from exc


def media_directory(base_media_path: Path, item_id: str) -> Path:
    return base_media_path / item_id
