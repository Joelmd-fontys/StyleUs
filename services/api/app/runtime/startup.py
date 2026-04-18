"""Shared startup helpers for API-like entrypoints."""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import logger
from app.db.migrations import SchemaCompatibilityError, ensure_schema, ensure_schema_compatible


def _startup_extra(
    settings: Settings,
    *,
    service_name: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    extra: dict[str, object] = {"app_env": settings.app_env}
    if service_name is not None:
        extra["service"] = service_name
    if reason is not None:
        extra["reason"] = reason
    return extra


def run_startup_tasks(
    settings: Settings,
    *,
    include_seed: bool = False,
    service_name: str | None = None,
) -> None:
    if not settings.run_migrations_on_start:
        logger.info(
            "startup.migrations_skipped",
            extra=_startup_extra(settings, service_name=service_name),
        )
    else:
        logger.info(
            "startup.migrations_started",
            extra=_startup_extra(settings, service_name=service_name),
        )
        ensure_schema()

    if not settings.is_secure_env:
        logger.info(
            "startup.schema_validation_skipped",
            extra=_startup_extra(settings, service_name=service_name, reason="non_secure_env"),
        )
    else:
        logger.info(
            "startup.schema_validation_started",
            extra=_startup_extra(settings, service_name=service_name),
        )
        try:
            ensure_schema_compatible()
        except SchemaCompatibilityError as exc:
            logger.exception(
                "startup.schema_incompatible",
                extra={**_startup_extra(settings, service_name=service_name), "error": str(exc)},
            )
            raise
        logger.info(
            "startup.schema_validation_complete",
            extra=_startup_extra(settings, service_name=service_name),
        )

    if not include_seed:
        return

    if not settings.run_seed_on_start:
        logger.info("startup.seed_skipped", extra={"app_env": settings.app_env})
        return

    try:
        from app.seed.runner import run_seed

        logger.info("startup.seed_started", extra={"app_env": settings.app_env})
        run_seed(settings=settings)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("seed.failed")
