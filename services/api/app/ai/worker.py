"""Reusable AI worker runtime."""

from __future__ import annotations

import datetime as dt
import signal
import sys
import threading
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, cast

try:  # pragma: no cover - platform specific
    import resource
except ImportError:  # pragma: no cover - windows fallback
    resource = None  # type: ignore[assignment]

from app.core.config import Settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.services import ai_jobs as ai_jobs_service
from app.services.ai_jobs import AIJobLease

_UNSET = object()


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    classifier_enabled: bool
    running: bool
    started_at: dt.datetime | None
    warmup_completed_at: dt.datetime | None
    last_job_claimed_at: dt.datetime | None
    last_job_completed_at: dt.datetime | None
    last_job_failed_at: dt.datetime | None
    last_error: str | None
    memory_rss_mb: float | None


@dataclass(frozen=True, slots=True)
class _AIImports:
    pipeline: Any
    ai_enrichment_error: Any
    build_ai_preview_payload: Any
    run_item_enrichment: Any


def _current_memory_rss_mb() -> float | None:
    if resource is None:  # pragma: no cover - platform specific
        return None
    resource_module = cast(Any, resource)
    usage = cast(int, resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return round(usage / (1024 * 1024), 2)
    return round(usage / 1024, 2)


@lru_cache(maxsize=1)
def _get_ai_imports() -> _AIImports:
    from app.ai import pipeline
    from app.ai.tasks import AIEnrichmentError, build_ai_preview_payload, run_item_enrichment

    return _AIImports(
        pipeline=pipeline,
        ai_enrichment_error=AIEnrichmentError,
        build_ai_preview_payload=build_ai_preview_payload,
        run_item_enrichment=run_item_enrichment,
    )


class AIWorker:
    """Poll the database queue and process AI enrichment jobs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._warmup_attempted = False
        self._warmup_lock = threading.Lock()
        self._snapshot = WorkerSnapshot(
            classifier_enabled=settings.ai_enable_classifier,
            running=False,
            started_at=None,
            warmup_completed_at=None,
            last_job_claimed_at=None,
            last_job_completed_at=None,
            last_job_failed_at=None,
            last_error=None,
            memory_rss_mb=_current_memory_rss_mb(),
        )
        self._snapshot_lock = threading.Lock()

    def snapshot(self) -> WorkerSnapshot:
        with self._snapshot_lock:
            return self._snapshot

    def is_running(self) -> bool:
        return self.snapshot().running

    def thread_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def run_forever(self, *, install_signal_handlers: bool = False) -> None:
        if not self.settings.ai_enable_classifier:
            logger.warning(
                "worker.disabled",
                extra={"event": "worker_disabled", "memory_rss_mb": _current_memory_rss_mb()},
            )
            self._update_snapshot(
                running=False,
                last_error="AI classifier disabled",
                memory_rss_mb=_current_memory_rss_mb(),
            )
            return

        if install_signal_handlers:
            self._install_signal_handlers()

        started_at = dt.datetime.now(dt.UTC)
        self._update_snapshot(
            running=True,
            started_at=started_at,
            last_error=None,
            memory_rss_mb=_current_memory_rss_mb(),
        )
        logger.info(
            "worker.started",
            extra={
                "event": "worker_started",
                "poll_interval_seconds": self.settings.ai_job_poll_interval_seconds,
                "max_attempts": self.settings.ai_job_max_attempts,
                "stale_after_seconds": self.settings.ai_job_stale_after_seconds,
                "memory_rss_mb": _current_memory_rss_mb(),
            },
        )
        self._ensure_pipeline_ready()

        try:
            while not self.stop_event.is_set():
                try:
                    claimed = self.run_once()
                except Exception as exc:  # pragma: no cover - defensive guard
                    self._update_snapshot(
                        last_error=str(exc),
                        memory_rss_mb=_current_memory_rss_mb(),
                    )
                    logger.exception(
                        "worker.loop_error",
                        extra={
                            "event": "worker_loop_error",
                            "error": str(exc),
                            "memory_rss_mb": _current_memory_rss_mb(),
                        },
                    )
                    self.stop_event.wait(self.settings.ai_job_poll_interval_seconds)
                    continue
                if not claimed:
                    self.stop_event.wait(self.settings.ai_job_poll_interval_seconds)
        finally:
            self._update_snapshot(running=False, memory_rss_mb=_current_memory_rss_mb())
            logger.info(
                "worker.stopped",
                extra={"event": "worker_stopped", "memory_rss_mb": _current_memory_rss_mb()},
            )

    def start_in_background(self, *, thread_name: str = "styleus-ai-worker") -> bool:
        if not self.settings.ai_enable_classifier:
            logger.warning(
                "worker.disabled",
                extra={"event": "worker_disabled", "memory_rss_mb": _current_memory_rss_mb()},
            )
            return False

        thread = self._thread
        if thread is not None and thread.is_alive():
            logger.debug(
                "worker.background_thread_already_running",
                extra={"thread_name": thread.name},
            )
            return True

        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_forever_safely,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "worker.background_thread_started",
            extra={
                "event": "worker_started",
                "thread_name": thread_name,
                "memory_rss_mb": _current_memory_rss_mb(),
            },
        )
        return True

    def request_shutdown(self, *, reason: str) -> None:
        logger.info(
            "worker.shutdown_requested",
            extra={
                "event": "worker_shutdown_requested",
                "reason": reason,
                "memory_rss_mb": _current_memory_rss_mb(),
            },
        )
        self.stop_event.set()

    def join(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def run_once(self) -> bool:
        claim_started = time.perf_counter()
        lease = self._claim_next_job()
        if lease is None:
            return False
        self._process_job(
            lease,
            claim_duration_ms=round((time.perf_counter() - claim_started) * 1000, 2),
        )
        return True

    def _claim_next_job(self) -> AIJobLease | None:
        with SessionLocal() as session:
            return ai_jobs_service.claim_next_job(
                session,
                max_attempts=self.settings.ai_job_max_attempts,
                stale_after=dt.timedelta(seconds=self.settings.ai_job_stale_after_seconds),
            )

    def _process_job(self, lease: AIJobLease, *, claim_duration_ms: float) -> None:
        self._ensure_pipeline_ready()
        started = time.perf_counter()
        claimed_at = dt.datetime.now(dt.UTC)
        self._update_snapshot(
            last_job_claimed_at=claimed_at,
            last_error=None,
            memory_rss_mb=_current_memory_rss_mb(),
        )
        logger.info(
            "worker.job_claimed",
            extra={
                "event": "job_claimed",
                "job_id": str(lease.job_id),
                "item_id": str(lease.item_id),
                "attempts": lease.attempts,
                "previous_status": lease.previous_status,
                "claim_duration_ms": claim_duration_ms,
                "queue_latency_ms": lease.queue_latency_ms,
                "memory_rss_mb": _current_memory_rss_mb(),
            },
        )
        ai_imports = _get_ai_imports()
        try:
            with SessionLocal() as session:
                pipeline_result = ai_imports.run_item_enrichment(
                    session,
                    lease.item_id,
                    commit=False,
                )
                preview_payload = ai_imports.build_ai_preview_payload(pipeline_result)
                ai_jobs_service.mark_job_completed(
                    session,
                    lease.job_id,
                    result_payload=preview_payload,
                    commit=False,
                )
                session.commit()
        except ai_imports.ai_enrichment_error as exc:
            failed_at = dt.datetime.now(dt.UTC)
            with SessionLocal() as session:
                job = ai_jobs_service.mark_job_failed(
                    session,
                    lease.job_id,
                    error_message=str(exc),
                    max_attempts=self.settings.ai_job_max_attempts,
                    retryable=exc.retryable,
                )
            self._update_snapshot(
                last_job_failed_at=failed_at,
                last_error=str(exc),
                memory_rss_mb=_current_memory_rss_mb(),
            )
            logger.warning(
                "worker.job_failed",
                extra={
                    "event": "job_failed",
                    "job_id": str(lease.job_id),
                    "item_id": str(lease.item_id),
                    "retryable": exc.retryable,
                    "status": job.status if job else None,
                    "error": str(exc),
                    "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "memory_rss_mb": _current_memory_rss_mb(),
                },
            )
            return
        except Exception as exc:  # pragma: no cover - defensive
            failed_at = dt.datetime.now(dt.UTC)
            with SessionLocal() as session:
                job = ai_jobs_service.mark_job_failed(
                    session,
                    lease.job_id,
                    error_message=str(exc),
                    max_attempts=self.settings.ai_job_max_attempts,
                    retryable=True,
                )
            self._update_snapshot(
                last_job_failed_at=failed_at,
                last_error=str(exc),
                memory_rss_mb=_current_memory_rss_mb(),
            )
            logger.exception(
                "worker.job_failed_unexpected",
                extra={
                    "event": "job_failed",
                    "job_id": str(lease.job_id),
                    "item_id": str(lease.item_id),
                    "status": job.status if job else None,
                    "error": str(exc),
                    "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "memory_rss_mb": _current_memory_rss_mb(),
                },
            )
            return

        completed_at = dt.datetime.now(dt.UTC)
        self._update_snapshot(
            last_job_completed_at=completed_at,
            last_error=None,
            memory_rss_mb=_current_memory_rss_mb(),
        )
        logger.info(
            "worker.job_completed",
            extra={
                "event": "job_completed",
                "job_id": str(lease.job_id),
                "item_id": str(lease.item_id),
                "category": preview_payload.get("category"),
                "subcategory": preview_payload.get("subcategory"),
                "primary_color": preview_payload.get("primary_color"),
                "secondary_color": preview_payload.get("secondary_color"),
                "tags": preview_payload.get("tags"),
                "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "memory_rss_mb": _current_memory_rss_mb(),
            },
        )

    def _ensure_pipeline_ready(self) -> None:
        if self._warmup_attempted:
            return
        with self._warmup_lock:
            if self._warmup_attempted:
                return
            self._warmup_attempted = True
            logger.info(
                "worker.warmup_started",
                extra={"event": "worker_warmup_started", "memory_rss_mb": _current_memory_rss_mb()},
            )
            ai_imports = _get_ai_imports()
            if ai_imports.pipeline.warm_up():
                self._update_snapshot(
                    warmup_completed_at=dt.datetime.now(dt.UTC),
                    memory_rss_mb=_current_memory_rss_mb(),
                )

    def _run_forever_safely(self) -> None:
        try:
            self.run_forever()
        except Exception as exc:  # pragma: no cover - defensive guard
            self._update_snapshot(
                running=False,
                last_error=str(exc),
                memory_rss_mb=_current_memory_rss_mb(),
            )
            logger.exception(
                "worker.crashed",
                extra={
                    "event": "worker_crashed",
                    "error": str(exc),
                    "memory_rss_mb": _current_memory_rss_mb(),
                },
            )
            self.stop_event.set()

    def _install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle_shutdown_signal)
            except ValueError:
                logger.debug("worker.signal_handler_skipped", extra={"signal": sig.name})

    def _handle_shutdown_signal(self, signum: int, frame) -> None:  # type: ignore[no-untyped-def]
        del frame
        self.request_shutdown(reason=signal.Signals(signum).name)

    def _update_snapshot(
        self,
        *,
        classifier_enabled: bool | object = _UNSET,
        running: bool | object = _UNSET,
        started_at: dt.datetime | None | object = _UNSET,
        warmup_completed_at: dt.datetime | None | object = _UNSET,
        last_job_claimed_at: dt.datetime | None | object = _UNSET,
        last_job_completed_at: dt.datetime | None | object = _UNSET,
        last_job_failed_at: dt.datetime | None | object = _UNSET,
        last_error: str | None | object = _UNSET,
        memory_rss_mb: float | None | object = _UNSET,
    ) -> None:
        with self._snapshot_lock:
            current = self._snapshot
            self._snapshot = replace(
                current,
                classifier_enabled=(
                    current.classifier_enabled
                    if classifier_enabled is _UNSET
                    else cast(bool, classifier_enabled)
                ),
                running=current.running if running is _UNSET else cast(bool, running),
                started_at=current.started_at if started_at is _UNSET else cast(
                    dt.datetime | None, started_at
                ),
                warmup_completed_at=(
                    current.warmup_completed_at
                    if warmup_completed_at is _UNSET
                    else cast(dt.datetime | None, warmup_completed_at)
                ),
                last_job_claimed_at=(
                    current.last_job_claimed_at
                    if last_job_claimed_at is _UNSET
                    else cast(dt.datetime | None, last_job_claimed_at)
                ),
                last_job_completed_at=(
                    current.last_job_completed_at
                    if last_job_completed_at is _UNSET
                    else cast(dt.datetime | None, last_job_completed_at)
                ),
                last_job_failed_at=(
                    current.last_job_failed_at
                    if last_job_failed_at is _UNSET
                    else cast(dt.datetime | None, last_job_failed_at)
                ),
                last_error=current.last_error if last_error is _UNSET else cast(
                    str | None, last_error
                ),
                memory_rss_mb=(
                    current.memory_rss_mb
                    if memory_rss_mb is _UNSET
                    else cast(float | None, memory_rss_mb)
                ),
            )
