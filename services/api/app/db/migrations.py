"""Helpers to keep the database schema aligned with Alembic migrations."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from threading import Lock

from sqlalchemy import inspect

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
from app.db.session import get_engine

_migration_lock = Lock()
_schema_ready = False


class SchemaCompatibilityError(RuntimeError):
    """Raised when the live database schema does not match mapped models."""

    def __init__(
        self,
        *,
        missing_tables: Iterable[str] = (),
        missing_columns: dict[str, Iterable[str]] | None = None,
    ) -> None:
        self.missing_tables = tuple(sorted({table for table in missing_tables if table}))
        self.missing_columns = {
            table: tuple(sorted({column for column in columns if column}))
            for table, columns in sorted((missing_columns or {}).items())
            if columns
        }

        details: list[str] = []
        if self.missing_tables:
            details.append(f"missing tables: {', '.join(self.missing_tables)}")
        if self.missing_columns:
            column_details = ", ".join(
                f"{table}({', '.join(columns)})"
                for table, columns in self.missing_columns.items()
            )
            details.append(f"missing columns: {column_details}")

        message = "Database schema is out of date"
        if details:
            message = f"{message} ({'; '.join(details)})"
        super().__init__(message)


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


def ensure_schema_compatible() -> None:
    """Verify the live schema contains every mapped table and column."""

    engine = get_engine()
    with engine.connect() as connection:
        inspector = inspect(connection)
        missing_tables: list[str] = []
        missing_columns: dict[str, list[str]] = {}

        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                missing_tables.append(table.name)
                continue

            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            expected_columns = {column.name for column in table.columns}
            missing = sorted(expected_columns - existing_columns)
            if missing:
                missing_columns[table.name] = missing

    if missing_tables or missing_columns:
        raise SchemaCompatibilityError(
            missing_tables=missing_tables,
            missing_columns=missing_columns,
        )


def _build_alembic_config(database_url: str) -> Config:
    service_root = Path(__file__).resolve().parents[2]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    return config
