from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import health as health_router
from app.db.migrations import SchemaCompatibilityError


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert payload["database"] == "ok"


def test_health_endpoint_returns_503_when_database_is_unavailable(client, monkeypatch):
    fake_engine = MagicMock()
    fake_engine.connect.side_effect = SQLAlchemyError("database offline")
    monkeypatch.setattr(health_router, "get_engine", lambda: fake_engine)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database unavailable"


def test_health_endpoint_returns_503_when_schema_is_outdated(client, monkeypatch):
    monkeypatch.setattr(
        health_router,
        "get_settings",
        lambda: MagicMock(app_env="production", app_version="0.1.0", is_secure_env=True),
    )
    monkeypatch.setattr(
        health_router,
        "ensure_schema_compatible",
        lambda: (_ for _ in ()).throw(
            SchemaCompatibilityError(
                missing_columns={"wardrobe_items": ["ai_attribute_tags"]},
            )
        ),
    )

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database schema out of date"
