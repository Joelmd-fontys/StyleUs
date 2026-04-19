"""AI worker CLI entrypoint."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from app.core.config import get_settings
from app.core.logging import logger
from app.runtime.worker_host import get_ai_worker_class

__all__ = ["AIWorker", "main"]

if TYPE_CHECKING:
    from app.ai.worker import AIWorker


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the StyleUs AI worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job, then exit.",
    )
    return parser


def __getattr__(name: str) -> object:
    if name == "AIWorker":
        return get_ai_worker_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> int:
    settings = get_settings()
    if not settings.ai_enable_classifier:
        logger.warning("worker.disabled")
        return 0

    args = _build_parser().parse_args()
    worker_class = get_ai_worker_class()
    worker = worker_class(settings)
    if args.once:
        return 0 if worker.run_once() else 1
    worker.run_forever(install_signal_handlers=True)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
