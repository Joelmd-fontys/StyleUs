from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _clear_startup_env(monkeypatch) -> None:
    for key in (
        "APP_ENV",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_STORAGE_BUCKET",
        "SUPABASE_JWT_AUDIENCE",
        "LOCAL_AUTH_BYPASS",
        "RUN_MIGRATIONS_ON_START",
        "RUN_SEED_ON_START",
        "SEED_ON_START",
    ):
        monkeypatch.delenv(key, raising=False)


def test_missing_app_env_fails_closed(monkeypatch):
    _clear_startup_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_local_defaults_enable_startup_helpers_and_bypass(monkeypatch):
    _clear_startup_env(monkeypatch)
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        _env_file=None,
    )

    assert settings.run_migrations_on_start is True
    assert settings.run_seed_on_start is True
    assert settings.seed_on_start is True
    assert settings.local_auth_bypass_enabled is True


def test_production_defaults_disable_startup_helpers_and_require_supabase(monkeypatch):
    _clear_startup_env(monkeypatch)
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
            _env_file=None,
        )

    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        _env_file=None,
    )

    assert settings.run_migrations_on_start is False
    assert settings.run_seed_on_start is False
    assert settings.local_auth_bypass_enabled is False


def test_local_auth_bypass_is_rejected_outside_local(monkeypatch):
    _clear_startup_env(monkeypatch)

    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="staging",
            DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
            SUPABASE_URL="https://project.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY="service-role-key",
            SUPABASE_STORAGE_BUCKET="wardrobe-images",
            LOCAL_AUTH_BYPASS="true",
            _env_file=None,
        )


def test_supabase_public_key_accepts_legacy_alias(monkeypatch):
    _clear_startup_env(monkeypatch)
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        SUPABASE_ANON_KEY="legacy-anon-key",
        _env_file=None,
    )

    assert settings.supabase_public_key == "legacy-anon-key"


def test_legacy_seed_on_start_alias_is_still_supported(monkeypatch):
    _clear_startup_env(monkeypatch)
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        SEED_ON_START="false",
        _env_file=None,
    )

    assert settings.run_seed_on_start is False
    assert settings.seed_on_start is False


def test_database_url_normalizes_plain_postgresql_scheme(monkeypatch):
    _clear_startup_env(monkeypatch)
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgresql://postgres.example:secret@db.project.supabase.co:5432/postgres?sslmode=require",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        _env_file=None,
    )

    assert settings.database_url == (
        "postgresql+psycopg://postgres.example:secret@db.project.supabase.co:5432/"
        "postgres?sslmode=require"
    )


def test_database_url_normalizes_postgres_scheme(monkeypatch):
    _clear_startup_env(monkeypatch)
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgres://postgres.example:secret@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        _env_file=None,
    )

    assert settings.database_url == (
        "postgresql+psycopg://postgres.example:secret@aws-0-eu-west-1.pooler.supabase.com:5432/"
        "postgres?sslmode=require"
    )
