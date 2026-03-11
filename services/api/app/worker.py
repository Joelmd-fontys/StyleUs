"""Standalone AI worker entrypoint."""

from __future__ import annotations

import argparse
import datetime as dt
import signal
import threading
import time

from app.ai import pipeline
from app.ai.tasks import AIEnrichmentError, run_item_enrichment
from app.core.config import Settings, get_settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.services import ai_jobs as ai_jobs_service
from app.services.ai_jobs import AIJobLease


class AIWorker:
    """Poll the database queue and process AI enrichment jobs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.stop_event = threading.Event()

    def run_forever(self) -> None:
        self._install_signal_handlers()
        logger.info(
            "worker.started",
            extra={
                "poll_interval_seconds": self.settings.ai_job_poll_interval_seconds,
                "max_attempts": self.settings.ai_job_max_attempts,
                "stale_after_seconds": self.settings.ai_job_stale_after_seconds,
            },
        )
        logger.info("worker.warmup_started")
        pipeline.warm_up()
        while not self.stop_event.is_set():
            claimed = self.run_once()
            if not claimed:
                self.stop_event.wait(self.settings.ai_job_poll_interval_seconds)
        logger.info("worker.stopped")

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
        started = time.perf_counter()
        logger.info(
            "worker.job_claimed",
            extra={
                "job_id": str(lease.job_id),
                "item_id": str(lease.item_id),
                "attempts": lease.attempts,
                "previous_status": lease.previous_status,
                "claim_duration_ms": claim_duration_ms,
                "queue_latency_ms": lease.queue_latency_ms,
            },
        )
        try:
            with SessionLocal() as session:
                run_item_enrichment(session, lease.item_id, commit=False)
                ai_jobs_service.mark_job_completed(session, lease.job_id, commit=False)
                session.commit()
        except AIEnrichmentError as exc:
            with SessionLocal() as session:
                job = ai_jobs_service.mark_job_failed(
                    session,
                    lease.job_id,
                    error_message=str(exc),
                    max_attempts=self.settings.ai_job_max_attempts,
                    retryable=exc.retryable,
                )
            logger.warning(
                "worker.job_failed",
                extra={
                    "job_id": str(lease.job_id),
                    "item_id": str(lease.item_id),
                    "retryable": exc.retryable,
                    "status": job.status if job else None,
                    "error": str(exc),
                    "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return
        except Exception as exc:  # pragma: no cover - defensive
            with SessionLocal() as session:
                job = ai_jobs_service.mark_job_failed(
                    session,
                    lease.job_id,
                    error_message=str(exc),
                    max_attempts=self.settings.ai_job_max_attempts,
                    retryable=True,
                )
            logger.exception(
                "worker.job_failed_unexpected",
                extra={
                    "job_id": str(lease.job_id),
                    "item_id": str(lease.item_id),
                    "status": job.status if job else None,
                    "error": str(exc),
                    "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return

        logger.info(
            "worker.job_completed",
            extra={
                "job_id": str(lease.job_id),
                "item_id": str(lease.item_id),
                "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )

    def _install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle_shutdown_signal)
            except ValueError:
                # Signal registration can fail outside the main thread.
                logger.debug("worker.signal_handler_skipped", extra={"signal": sig.name})

    def _handle_shutdown_signal(self, signum: int, frame) -> None:  # type: ignore[no-untyped-def]
        del frame
        logger.info("worker.shutdown_requested", extra={"signal": signal.Signals(signum).name})
        self.stop_event.set()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the StyleUs AI worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job, then exit.",
    )
    return parser


def main() -> int:
    settings = get_settings()
    if not settings.ai_enable_classifier:
        logger.warning("worker.disabled")
        return 0

    args = _build_parser().parse_args()
    worker = AIWorker(settings)
    if args.once:
        return 0 if worker.run_once() else 1
    worker.run_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
