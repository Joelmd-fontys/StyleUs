from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault("SUPABASE_URL", "https://styleus-test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
os.environ.setdefault("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
os.environ.setdefault("LOCAL_AUTH_BYPASS", "true")
os.environ.setdefault("APP_VERSION", "0.1.0")
os.environ.setdefault("RUN_MIGRATIONS_ON_START", "false")
os.environ.setdefault("RUN_SEED_ON_START", "false")

from app.api.deps import get_db  # noqa: E402
from app.core.auth import clear_auth_cache  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402

engine = create_engine(os.environ["DATABASE_URL"], future=True, pool_pre_ping=True)

TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session")
def setup_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session(setup_database: None) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient bound to the shared database session."""
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    clear_auth_cache()
    yield
    get_settings.cache_clear()
    clear_auth_cache()
