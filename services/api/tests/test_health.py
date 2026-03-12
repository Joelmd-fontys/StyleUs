from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import health as health_router


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
