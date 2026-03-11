from __future__ import annotations

import io
import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from jwt import PyJWKClientConnectionError
from sqlalchemy.orm import Session

from app.api import deps as deps_module
from app.api.deps import DEFAULT_USER_ID, get_current_user, get_db
from app.core import auth as auth_module
from app.core.auth import (
    AuthVerificationError,
    CurrentUser,
    SupabaseTokenVerifier,
    clear_auth_cache,
)
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.user import User
from app.models.wardrobe import WardrobeItem


@contextmanager
def _build_staging_client(
    db_session: Session,
    monkeypatch,
    *,
    current_user: CurrentUser,
) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://styleus-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_START", "false")
    monkeypatch.setenv("RUN_SEED_ON_START", "false")
    monkeypatch.delenv("LOCAL_AUTH_BYPASS", raising=False)
    get_settings.cache_clear()
    clear_auth_cache()

    application = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    class DummyVerifier:
        def verify(self, token: str) -> CurrentUser:
            assert token == "test-token"
            return current_user

    application.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(deps_module, "get_token_verifier", lambda settings: DummyVerifier())

    with TestClient(application) as client:
        yield client

    application.dependency_overrides.pop(get_db, None)


def test_local_auth_bypass_returns_explicit_dev_user(db_session: Session) -> None:
    settings = Settings(
        APP_ENV="local",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://styleus-test.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
    )

    current_user = get_current_user(db=db_session, settings=settings, credentials=None)

    assert current_user.id == DEFAULT_USER_ID
    assert current_user.is_local_bypass is True
    assert db_session.get(User, DEFAULT_USER_ID) is not None


def test_missing_bearer_token_rejected_in_staging(db_session: Session, monkeypatch) -> None:
    current_user = CurrentUser(id=uuid.uuid4(), email="secure@example.com")
    with _build_staging_client(db_session, monkeypatch, current_user=current_user) as client:
        response = client.get("/items")

        assert response.status_code == 401
        assert response.json()["detail"]["message"] == "Missing bearer token"
        assert response.headers["www-authenticate"] == "Bearer"


def test_valid_bearer_token_scopes_items_to_authenticated_user(
    db_session: Session,
    monkeypatch,
) -> None:
    signed_in_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    db_session.add_all(
        [
            User(id=signed_in_user_id, email="stale@example.com"),
            User(id=other_user_id, email="other@example.com"),
            WardrobeItem(user_id=other_user_id, category="top", color="black", brand="Other"),
            WardrobeItem(user_id=signed_in_user_id, category="bottom", color="blue", brand="Mine"),
        ]
    )
    db_session.commit()

    with _build_staging_client(
        db_session,
        monkeypatch,
        current_user=CurrentUser(id=signed_in_user_id, email="signed-in@example.com"),
    ) as client:
        response = client.get("/items", headers={"Authorization": "Bearer test-token"})

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["brand"] == "Mine"

    synced_user = db_session.get(User, signed_in_user_id)
    assert synced_user is not None
    assert synced_user.email == "signed-in@example.com"


def test_invalid_bearer_token_is_rejected(db_session: Session, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SUPABASE_URL", "https://styleus-test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "wardrobe-images")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_START", "false")
    monkeypatch.setenv("RUN_SEED_ON_START", "false")
    monkeypatch.delenv("LOCAL_AUTH_BYPASS", raising=False)
    get_settings.cache_clear()
    clear_auth_cache()

    application = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    class RejectingVerifier:
        def verify(self, token: str) -> CurrentUser:
            raise AuthVerificationError("Invalid bearer token")

    application.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(deps_module, "get_token_verifier", lambda settings: RejectingVerifier())

    with TestClient(application) as client:
        response = client.get("/items", headers={"Authorization": "Bearer bad-token"})

    application.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid bearer token"
    assert response.headers["www-authenticate"] == "Bearer"


def test_direct_dependency_accepts_bearer_credentials_when_verifier_succeeds(
    db_session: Session,
    monkeypatch,
) -> None:
    current_user = CurrentUser(id=uuid.uuid4(), email="verified@example.com")
    monkeypatch.setattr(
        deps_module,
        "get_token_verifier",
        lambda settings: type("Verifier", (), {"verify": lambda self, token: current_user})(),
    )
    settings = Settings(
        APP_ENV="staging",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        SUPABASE_URL="https://styleus-test.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="service-role-key",
        SUPABASE_STORAGE_BUCKET="wardrobe-images",
        LOCAL_AUTH_BYPASS="false",
        _env_file=None,
    )

    resolved = get_current_user(
        db=db_session,
        settings=settings,
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
    )

    assert resolved.id == current_user.id
    assert db_session.get(User, current_user.id) is not None


def test_shared_secret_tokens_fallback_to_supabase_userinfo(monkeypatch) -> None:
    user_id = uuid.uuid4()
    token = jwt.encode({"sub": str(user_id)}, "shared-secret", algorithm="HS256")
    captured_request: dict[str, str | float] = {}

    class DummyResponse(io.BytesIO):
        def __enter__(self) -> DummyResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            self.close()
            return False

    def fake_urlopen(request, timeout: float):
        captured_request["url"] = request.full_url
        captured_request["authorization"] = request.headers.get("Authorization", "")
        captured_request["apikey"] = request.headers.get("Apikey", "")
        captured_request["timeout"] = timeout
        payload = {"id": str(user_id), "email": "shared-secret@example.com"}
        return DummyResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(auth_module, "urlopen", fake_urlopen)

    verifier = SupabaseTokenVerifier(
        jwks_url="https://styleus-test.supabase.co/auth/v1/.well-known/jwks.json",
        issuer="https://styleus-test.supabase.co/auth/v1",
        audience="authenticated",
        userinfo_url="https://styleus-test.supabase.co/auth/v1/user",
        public_key="sb_publishable_test_key",
    )

    current_user = verifier.verify(token)

    assert current_user.id == user_id
    assert current_user.email == "shared-secret@example.com"
    assert captured_request == {
        "url": "https://styleus-test.supabase.co/auth/v1/user",
        "authorization": f"Bearer {token}",
        "apikey": "sb_publishable_test_key",
        "timeout": 5.0,
    }


def test_jwks_connection_errors_surface_as_unable_to_verify() -> None:
    token = (
        "eyJhbGciOiJFUzI1NiIsImtpZCI6InRlc3Qta2lkIiwidHlwIjoiSldUIn0."
        "eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCJhdWQiOiJhdXRo"
        "ZW50aWNhdGVkIiwiaXNzIjoiaHR0cHM6Ly9zdHlsZXVzLXRlc3Quc3VwYWJhc2UuY28vYXV0aC92MSIs"
        "ImV4cCI6NDEwMjQ0NDgwMH0.c2ln"
    )
    verifier = SupabaseTokenVerifier(
        jwks_url="https://styleus-test.supabase.co/auth/v1/.well-known/jwks.json",
        issuer="https://styleus-test.supabase.co/auth/v1",
        audience="authenticated",
        userinfo_url="https://styleus-test.supabase.co/auth/v1/user",
        public_key="sb_publishable_test_key",
    )

    class FailingJWKClient:
        def get_signing_key_from_jwt(self, token: str) -> None:
            raise PyJWKClientConnectionError("certificate verify failed")

    verifier._jwks_client = FailingJWKClient()

    with pytest.raises(AuthVerificationError, match="Unable to verify bearer token"):
        verifier.verify(token)


def test_shared_secret_tokens_require_supabase_public_key() -> None:
    token = jwt.encode({"sub": str(uuid.uuid4())}, "shared-secret", algorithm="HS256")
    verifier = SupabaseTokenVerifier(
        jwks_url="https://styleus-test.supabase.co/auth/v1/.well-known/jwks.json",
        issuer="https://styleus-test.supabase.co/auth/v1",
        audience="authenticated",
        userinfo_url="https://styleus-test.supabase.co/auth/v1/user",
        public_key=None,
    )

    with pytest.raises(AuthVerificationError, match="SUPABASE_PUBLISHABLE_KEY"):
        verifier.verify(token)
