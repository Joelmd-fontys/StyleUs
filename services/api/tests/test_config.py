from __future__ import annotations

from app.core.config import get_settings


def _clear_startup_env(monkeypatch) -> None:
    for key in (
        "DATABASE_URL",
        "RUN_MIGRATIONS_ON_START",
        "RUN_SEED_ON_START",
        "SEED_ON_START",
        "API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_local_defaults_enable_startup_helpers(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.run_migrations_on_start is True
    assert settings.run_seed_on_start is True
    assert settings.seed_on_start is True


def test_production_defaults_disable_startup_helpers(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
    monkeypatch.setenv("API_KEY", "secret")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.run_migrations_on_start is False
    assert settings.run_seed_on_start is False


def test_legacy_seed_on_start_alias_is_still_supported(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
    monkeypatch.setenv("SEED_ON_START", "false")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.run_seed_on_start is False
    assert settings.seed_on_start is False


def test_database_url_normalizes_plain_postgresql_scheme(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres.example:secret@db.project.supabase.co:5432/postgres?sslmode=require",
    )

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.database_url == (
        "postgresql+psycopg://postgres.example:secret@db.project.supabase.co:5432/"
        "postgres?sslmode=require"
    )


def test_database_url_normalizes_postgres_scheme(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://postgres.example:secret@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require",
    )

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.database_url == (
        "postgresql+psycopg://postgres.example:secret@aws-0-eu-west-1.pooler.supabase.com:5432/"
        "postgres?sslmode=require"
    )
