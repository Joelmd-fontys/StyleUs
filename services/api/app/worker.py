"""AI worker runtime and CLI entrypoint."""

from __future__ import annotations

import argparse
import datetime as dt
import signal
import threading
import time

from app.ai import pipeline
from app.ai.tasks import AIEnrichmentError, build_ai_preview_payload, run_item_enrichment
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
        self._thread: threading.Thread | None = None

    def run_forever(self, *, install_signal_handlers: bool = False) -> None:
        if install_signal_handlers:
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

    def start_in_background(self, *, thread_name: str = "styleus-ai-worker") -> None:
        if not self.settings.ai_enable_classifier:
            logger.warning("worker.disabled")
            return
        thread = self._thread
        if thread is not None and thread.is_alive():
            logger.debug(
                "worker.background_thread_already_running",
                extra={"thread_name": thread.name},
            )
            return

        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_forever_safely,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()
        logger.info("worker.background_thread_started", extra={"thread_name": thread_name})

    def request_shutdown(self, *, reason: str) -> None:
        logger.info("worker.shutdown_requested", extra={"reason": reason})
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
                pipeline_result = run_item_enrichment(session, lease.item_id, commit=False)
                preview_payload = build_ai_preview_payload(pipeline_result)
                ai_jobs_service.mark_job_completed(
                    session,
                    lease.job_id,
                    result_payload=preview_payload,
                    commit=False,
                )
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
                "category": preview_payload.get("category"),
                "subcategory": preview_payload.get("subcategory"),
                "primary_color": preview_payload.get("primary_color"),
                "secondary_color": preview_payload.get("secondary_color"),
                "tags": preview_payload.get("tags"),
                "total_duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )

    def _run_forever_safely(self) -> None:
        try:
            self.run_forever()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("worker.crashed", extra={"error": str(exc)})
            self.stop_event.set()

    def _install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle_shutdown_signal)
            except ValueError:
                # Signal registration can fail outside the main thread.
                logger.debug("worker.signal_handler_skipped", extra={"signal": sig.name})

    def _handle_shutdown_signal(self, signum: int, frame) -> None:  # type: ignore[no-untyped-def]
        del frame
        self.request_shutdown(reason=signal.Signals(signum).name)


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
    worker.run_forever(install_signal_handlers=True)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
