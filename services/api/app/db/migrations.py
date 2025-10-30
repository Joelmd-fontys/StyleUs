"""Helpers to keep the database schema aligned with Alembic migrations."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.db.session import get_engine

_migration_lock = Lock()
_schema_ready = False


def ensure_schema() -> None:
    """Run pending migrations exactly once per process."""

    global _schema_ready
    if _schema_ready:
        return

    with _migration_lock:
        if _schema_ready:
            return

        engine = get_engine()
        database_url = settings.database_url

        try:
            if database_url.startswith("sqlite"):
                Base.metadata.create_all(bind=engine)
                logger.info("migrations.sqlite_sync")
            else:
                config = _build_alembic_config(database_url)
                with engine.begin() as connection:
                    config.attributes["connection"] = connection
                    logger.info("migrations.upgrade.start")
                    command.upgrade(config, "head")
                    logger.info("migrations.upgrade.complete")
        except Exception:
            logger.exception("migrations.error")
            raise
        else:
            _schema_ready = True


def _build_alembic_config(database_url: str) -> Config:
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config

