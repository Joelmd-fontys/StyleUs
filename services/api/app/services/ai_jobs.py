"""Database-backed AI job queue helpers."""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob, AIJobStatus
from app.models.wardrobe import WardrobeItem

LOGGER = logging.getLogger("app.services.ai_jobs")
_MAX_ERROR_MESSAGE_LENGTH = 2000
_DELETED_ITEM_ERROR = "Wardrobe item deleted before AI enrichment"
AIJobResultPayload = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class AIJobLease:
    job_id: uuid.UUID
    item_id: uuid.UUID
    attempts: int
    created_at: dt.datetime
    claimed_at: dt.datetime
    previous_status: str

    @property
    def queue_latency_ms(self) -> float:
        return round((self.claimed_at - self.created_at).total_seconds() * 1000, 2)


def enqueue_item_job(db: Session, item: WardrobeItem, *, commit: bool = True) -> AIJob:
    """Create or reuse the durable AI job for an uploaded item."""

    job = db.execute(select(AIJob).where(AIJob.item_id == item.id)).scalars().first()
    if job is None:
        job = AIJob(item_id=item.id, status=AIJobStatus.PENDING.value, attempts=0)
        db.add(job)
    elif job.status in {AIJobStatus.COMPLETED.value, AIJobStatus.FAILED.value}:
        job.status = AIJobStatus.PENDING.value
        job.started_at = None
        job.completed_at = None
        job.attempts = 0
        job.error_message = None
        job.result_payload = None
        db.add(job)

    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    LOGGER.info(
        "ai.jobs.enqueued",
        extra={
            "job_id": str(job.id),
            "item_id": str(item.id),
            "status": job.status,
            "attempts": job.attempts,
        },
    )
    return job


def claim_next_job(
    db: Session,
    *,
    max_attempts: int,
    stale_after: dt.timedelta,
) -> AIJobLease | None:
    """Claim the next pending or stale-running AI job."""

    now = dt.datetime.now(dt.UTC)
    _fail_deleted_item_jobs(db, now=now)
    stale_before = now - stale_after
    stmt = (
        select(AIJob)
        .where(
            or_(
                AIJob.status == AIJobStatus.PENDING.value,
                and_(
                    AIJob.status == AIJobStatus.RUNNING.value,
                    AIJob.started_at.is_not(None),
                    AIJob.started_at <= stale_before,
                    AIJob.attempts < max_attempts,
                ),
            )
        )
        .order_by(
            case((AIJob.status == AIJobStatus.PENDING.value, 0), else_=1),
            AIJob.created_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = db.execute(stmt).scalars().first()
    if job is None:
        db.rollback()
        return None

    previous_status = job.status
    job.status = AIJobStatus.RUNNING.value
    job.started_at = now
    job.completed_at = None
    job.error_message = None
    job.result_payload = None
    job.attempts += 1
    db.add(job)
    db.commit()
    return AIJobLease(
        job_id=job.id,
        item_id=job.item_id,
        attempts=job.attempts,
        created_at=job.created_at,
        claimed_at=now,
        previous_status=previous_status,
    )


def mark_job_completed(
    db: Session,
    job_id: uuid.UUID,
    *,
    result_payload: AIJobResultPayload | None = None,
    commit: bool = True,
) -> AIJob | None:
    """Mark an AI job as completed."""

    job = db.get(AIJob, job_id)
    if job is None:
        return None

    job.status = AIJobStatus.COMPLETED.value
    job.completed_at = dt.datetime.now(dt.UTC)
    job.error_message = None
    job.result_payload = dict(result_payload) if result_payload is not None else None
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def mark_job_failed(
    db: Session,
    job_id: uuid.UUID,
    *,
    error_message: str,
    max_attempts: int,
    retryable: bool = True,
    commit: bool = True,
) -> AIJob | None:
    """Requeue or fail an AI job after an unsuccessful attempt."""

    job = db.get(AIJob, job_id)
    if job is None:
        return None

    normalized_error = _normalize_error_message(error_message)
    terminal = (not retryable) or job.attempts >= max_attempts
    job.error_message = normalized_error
    if terminal:
        job.status = AIJobStatus.FAILED.value
        job.completed_at = dt.datetime.now(dt.UTC)
        job.result_payload = None
    else:
        job.status = AIJobStatus.PENDING.value
        job.started_at = None
        job.completed_at = None
        job.result_payload = None
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def get_item_job(db: Session, item_id: uuid.UUID) -> AIJob | None:
    """Return the durable AI job for an item if one exists."""

    return db.execute(select(AIJob).where(AIJob.item_id == item_id)).scalars().first()


def _normalize_error_message(error_message: str) -> str:
    normalized = (error_message or "").strip() or "Unknown AI worker failure"
    return normalized[:_MAX_ERROR_MESSAGE_LENGTH]


def _fail_deleted_item_jobs(db: Session, *, now: dt.datetime) -> None:
    deleted_item_ids = select(WardrobeItem.id).where(WardrobeItem.deleted_at.is_not(None))
    db.execute(
        update(AIJob)
        .where(
            AIJob.item_id.in_(deleted_item_ids),
            AIJob.status.in_(
                [
                    AIJobStatus.PENDING.value,
                    AIJobStatus.RUNNING.value,
                ]
            ),
        )
        .values(
            status=AIJobStatus.FAILED.value,
            completed_at=now,
            error_message=_DELETED_ITEM_ERROR,
            result_payload=None,
        )
    )
    db.flush()
