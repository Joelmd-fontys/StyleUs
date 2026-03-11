"""Command-line entry point for the deterministic wardrobe seeding pipeline."""

from __future__ import annotations

import argparse
import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.models.seed import SeedRun
from app.models.wardrobe import WardrobeItem
from app.schemas.items import ImageMetadata
from app.seed.utils import (
    SeedSource,
    SeedSourceError,
    load_seed_sources,
    read_image_bytes,
    validate_image,
)
from app.services import items as items_service
from app.services import uploads as uploads_service
from app.services.users import sync_authenticated_user
from app.services.uploads import UploadFinalizationResult
from app.utils import storage as storage_utils
from app.utils.images import ProcessedImage, process_image_bytes


@dataclass(slots=True)
class SeedSummary:
    inserted: int = 0
    skipped: int = 0
    failed: int = 0
    removed: int = 0
    messages: list[str] = field(default_factory=list)

    def log_fields(self) -> dict[str, int | str]:
        payload: dict[str, int | str] = {
            "inserted": self.inserted,
            "skipped": self.skipped,
            "failed": self.failed,
            "removed": self.removed,
        }
        if self.messages:
            payload["messages"] = "; ".join(self.messages)
        return payload


def run_seed(
    *,
    settings: Settings | None = None,
    force: bool = False,
    limit: int | None = None,
    seed_key: str | None = None,
) -> SeedSummary:
    """Populate the wardrobe with curated starter items if the seed has not run yet."""

    settings = settings or get_settings()
    seed_user_id = _require_local_seed_user(settings)
    seed_key = seed_key or settings.seed_key
    limit = limit or settings.seed_limit

    summary = SeedSummary()
    if not settings.seed_on_start and not force:
        summary.messages.append("seeding disabled by configuration")
        return summary

    config_path = Path(__file__).resolve().parent / "seed_sources.yaml"
    sources = load_seed_sources(config_path, limit=limit)

    with SessionLocal() as session:
        if not force and session.get(SeedRun, seed_key) is not None:
            summary.messages.append(f"seed '{seed_key}' already applied")
            summary.skipped += 1
            return summary

        sync_authenticated_user(
            session,
            user_id=seed_user_id,
            email=settings.local_auth_email,
        )
        succeeded = _seed_sources(session, settings, seed_user_id, sources, summary)
        if succeeded and summary.failed == 0:
            session.merge(SeedRun(key=seed_key, applied_at=datetime.datetime.now(datetime.UTC)))
            session.commit()
    logger.info("seed.summary", extra=summary.log_fields())
    return summary


def reset_seed(
    *,
    settings: Settings | None = None,
    seed_key: str | None = None,
) -> SeedSummary:
    """Remove seeded items and clear the seed marker so the dataset can be re-applied."""

    settings = settings or get_settings()
    seed_user_id = _require_local_seed_user(settings)
    seed_key = seed_key or settings.seed_key
    summary = SeedSummary()

    config_path = Path(__file__).resolve().parent / "seed_sources.yaml"
    sources = load_seed_sources(config_path)

    with SessionLocal() as session:
        checksums = _collect_source_checksums(sources)
        items = session.scalars(
            select(WardrobeItem).where(
                WardrobeItem.user_id == seed_user_id,
                WardrobeItem.image_checksum.in_(checksums),
            )
        ).all()

        for item in items:
            summary.removed += 1
            _remove_media(settings, item)
            session.delete(item)

        marker = session.get(SeedRun, seed_key)
        if marker:
            session.delete(marker)
            summary.messages.append(f"seed marker '{seed_key}' removed")

        session.commit()

    logger.info("seed.reset", extra=summary.log_fields())
    return summary


def _seed_sources(
    session: Session,
    settings: Settings,
    seed_user_id: uuid.UUID,
    sources: list[SeedSource],
    summary: SeedSummary,
) -> bool:
    base_dir = Path(__file__).resolve().parent
    all_success = True
    for source in sources:
        try:
            data, original_content_type, _ = read_image_bytes(base_dir, source)
            validate_image(data, original_content_type, source.slug)
            processed = process_image_bytes(data, original_content_type)

            if _item_exists(session, seed_user_id, processed.checksum):
                summary.skipped += 1
                continue

            item = _create_placeholder_item(
                session,
                seed_user_id,
            )
            uploads_result = _finalize_upload(
                settings,
                seed_user_id,
                item.id,
                processed,
            )
            items_service.complete_upload(
                session,
                item,
                uploads_result.image_object_path,
                thumb_object_path=uploads_result.thumb_object_path,
                medium_object_path=uploads_result.medium_object_path,
                metadata=uploads_result.metadata,
            )
            items_service.update_item(
                session,
                item,
                category=source.category,
                color=source.color,
                brand=source.brand,
                tags=list(source.tags) if source.tags else None,
            )
            summary.inserted += 1
        except SeedSourceError as exc:
            all_success = False
            summary.failed += 1
            summary.messages.append(str(exc))
            session.rollback()
        except Exception as exc:  # pragma: no cover - guard against unexpected issues
            all_success = False
            summary.failed += 1
            summary.messages.append(f"{source.slug}: {exc}")
            logger.exception("seed.error", extra={"slug": source.slug})
            session.rollback()
    return all_success


def _collect_source_checksums(sources: list[SeedSource]) -> set[str]:
    base_dir = Path(__file__).resolve().parent
    checksums: set[str] = set()
    for source in sources:
        data, content_type, _ = read_image_bytes(base_dir, source)
        validate_image(data, content_type, source.slug)
        processed = process_image_bytes(data, content_type)
        checksums.add(processed.checksum)
    return checksums


def _create_placeholder_item(
    session: Session,
    seed_user_id: uuid.UUID,
) -> WardrobeItem:
    return items_service.create_placeholder_item(session, seed_user_id)


def _finalize_upload(
    settings: Settings,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    processed: ProcessedImage,
) -> UploadFinalizationResult:
    storage = storage_utils.get_storage_adapter(settings)
    orig_key, medium_key, thumb_key = uploads_service.build_variant_object_keys(
        user_id=user_id,
        item_id=item_id,
    )
    storage.upload_bytes(orig_key, data=processed.original_bytes, content_type="image/jpeg")
    storage.upload_bytes(medium_key, data=processed.medium_bytes, content_type="image/jpeg")
    storage.upload_bytes(thumb_key, data=processed.thumb_bytes, content_type="image/jpeg")

    metadata = ImageMetadata.model_validate(
        {
            "width": processed.width,
            "height": processed.height,
            "bytes": processed.size_bytes,
            "mime_type": processed.mime_type,
            "checksum": processed.checksum,
        }
    )

    return uploads_service.UploadFinalizationResult(
        image_object_path=orig_key,
        medium_object_path=medium_key,
        thumb_object_path=thumb_key,
        metadata=metadata,
    )


def _item_exists(session: Session, seed_user_id: uuid.UUID, checksum: str) -> bool:
    return session.scalar(
        select(WardrobeItem.id).where(
            WardrobeItem.user_id == seed_user_id,
            WardrobeItem.image_checksum == checksum,
        )
    ) is not None


def _require_local_seed_user(settings: Settings) -> uuid.UUID:
    if not settings.is_local_env:
        raise ValueError(
            "Seeding is only supported when APP_ENV=local because it relies on the "
            "local development user identity"
        )
    return settings.local_auth_user_id


def _remove_media(settings: Settings, item: WardrobeItem) -> None:
    if not item.id:
        return
    object_paths = [
        path
        for path in (
            item.image_object_path,
            item.image_medium_object_path,
            item.image_thumb_object_path,
        )
        if path
    ]
    if object_paths:
        storage_utils.get_storage_adapter(settings).delete_objects(object_paths)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the local StyleUs wardrobe dataset.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the seed even if already applied.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override SEED_LIMIT for this run.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove seeded data and clear the seed marker.",
    )
    parser.add_argument(
        "--seed-key",
        type=str,
        default=None,
        help="Override the configured SEED_KEY value.",
    )
    args = parser.parse_args()

    if args.reset:
        reset_seed(seed_key=args.seed_key)
    else:
        run_seed(force=args.force, limit=args.limit, seed_key=args.seed_key)


if __name__ == "__main__":
    main()
