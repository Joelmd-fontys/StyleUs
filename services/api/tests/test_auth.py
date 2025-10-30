from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from app.api.deps import verify_api_key
from app.core.config import get_settings


def test_verify_api_key_enforces_when_secure_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    settings = get_settings()

    with pytest.raises(HTTPException) as exc:
        verify_api_key(settings=settings, x_api_key="wrong")

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

    # Valid key should pass without raising.
    verify_api_key(settings=settings, x_api_key="secret")
