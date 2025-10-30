"""Command-line entry point for the deterministic wardrobe seeding pipeline."""

from __future__ import annotations

import argparse
import datetime
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DEFAULT_USER_ID
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
    media_directory,
    read_image_bytes,
    validate_image,
)
from app.services import items as items_service
from app.services import uploads as uploads_service
from app.utils import s3 as s3_utils
from app.utils.images import ProcessedImage, process_image_bytes, save_image_bytes


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

        succeeded = _seed_sources(session, settings, sources, summary)
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
    seed_key = seed_key or settings.seed_key
    summary = SeedSummary()

    config_path = Path(__file__).resolve().parent / "seed_sources.yaml"
    sources = load_seed_sources(config_path)

    with SessionLocal() as session:
        checksums = _collect_source_checksums(sources)
        items = session.scalars(
            select(WardrobeItem).where(
                WardrobeItem.user_id == DEFAULT_USER_ID,
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

            if _item_exists(session, processed.checksum):
                summary.skipped += 1
                continue

            file_name = f"{source.slug}.jpg"
            item, object_key = _create_placeholder_with_upload(
                session,
                settings,
                file_name,
                processed,
            )
            uploads_result = _finalize_upload(
                settings,
                item.id,
                object_key,
                file_name,
                processed,
            )
            items_service.complete_upload(
                session,
                item,
                uploads_result.image_url,
                thumb_url=uploads_result.thumb_url,
                medium_url=uploads_result.medium_url,
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


def _create_placeholder_with_upload(
    session: Session,
    settings: Settings,
    file_name: str,
    processed: ProcessedImage,
) -> tuple[WardrobeItem, str | None]:
    content_type = processed.mime_type
    item, _upload_url, object_key = uploads_service.create_presigned_upload(
        session,
        settings,
        user_id=DEFAULT_USER_ID,
        file_name=file_name,
        content_type=content_type,
    )
    if settings.is_s3_enabled:
        assert object_key is not None  # for type checker
        if not settings.aws_region or not settings.s3_bucket_name:
            raise SeedSourceError("S3 configuration missing for seeding")
        s3_utils.upload_bytes(
            bucket=settings.s3_bucket_name,
            key=object_key,
            region=settings.aws_region,
            data=processed.original_bytes,
            content_type=content_type,
        )
    return item, object_key


def _finalize_upload(
    settings: Settings,
    item_id,
    object_key: str | None,
    file_name: str,
    processed: ProcessedImage,
):
    if settings.is_s3_enabled:
        if not object_key:
            raise SeedSourceError("Missing S3 object key for seeding")
        return uploads_service.finalize_s3_upload(
            settings,
            item_id=item_id,
            object_key=object_key,
        )

    media_dir = settings.media_root_path / str(item_id)
    shutil.rmtree(media_dir, ignore_errors=True)
    save_image_bytes(media_dir / "orig.jpg", processed.original_bytes)
    save_image_bytes(media_dir / "medium.jpg", processed.medium_bytes)
    save_image_bytes(media_dir / "thumb.jpg", processed.thumb_bytes)

    metadata = ImageMetadata(
        width=processed.width,
        height=processed.height,
        bytes=processed.bytes,
        mime_type=processed.mime_type,
        checksum=processed.checksum,
    )

    base_url = f"{settings.media_url_path.rstrip('/')}/{item_id}"
    return uploads_service.UploadFinalizationResult(
        image_url=f"{base_url}/orig.jpg",
        medium_url=f"{base_url}/medium.jpg",
        thumb_url=f"{base_url}/thumb.jpg",
        metadata=metadata,
    )


def _item_exists(session: Session, checksum: str) -> bool:
    return session.scalar(
        select(WardrobeItem.id).where(
            WardrobeItem.user_id == DEFAULT_USER_ID,
            WardrobeItem.image_checksum == checksum,
        )
    ) is not None


def _remove_media(settings: Settings, item: WardrobeItem) -> None:
    if not item.id:
        return
    media_dir = media_directory(settings.media_root_path, str(item.id))
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)


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
