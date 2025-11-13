"""Database engine and session configuration."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _create_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )


engine: Engine = _create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_engine() -> Engine:
    return engine


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
