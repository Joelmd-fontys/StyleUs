"""Supabase JWT verification helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import (
    InvalidTokenError,
    PyJWKClient,
    PyJWKClientConnectionError,
    PyJWKClientError,
)

from app.core.config import Settings
from app.utils.http import get_ssl_context, urlopen

SUPPORTED_ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "ES256", "EdDSA"})
SUPABASE_USERINFO_TIMEOUT_SECONDS = 5.0


class AuthVerificationError(ValueError):
    """Raised when a bearer token cannot be trusted."""


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Authenticated user information derived from the current request."""

    id: uuid.UUID
    email: str
    is_local_bypass: bool = False


class SupabaseTokenVerifier:
    """Verify Supabase access tokens against the project's JWKS endpoint."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        userinfo_url: str,
        public_key: str | None,
    ) -> None:
        self._jwks_client = PyJWKClient(
            jwks_url,
            ssl_context=get_ssl_context(),
        )
        self._issuer = issuer
        self._audience = audience
        self._userinfo_url = userinfo_url
        self._public_key = public_key

    def verify(self, token: str) -> CurrentUser:
        algorithm = _resolve_token_algorithm(token)
        if algorithm.upper().startswith("HS"):
            return self._verify_via_userinfo(token)
        if algorithm not in SUPPORTED_ASYMMETRIC_ALGORITHMS:
            raise AuthVerificationError("Unsupported bearer token algorithm")

        return self._verify_via_jwks(token)

    def _verify_via_jwks(self, token: str) -> CurrentUser:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(SUPPORTED_ASYMMETRIC_ALGORITHMS),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "exp", "iss"]},
            )
        except PyJWKClientConnectionError as exc:
            raise AuthVerificationError("Unable to verify bearer token") from exc
        except (InvalidTokenError, PyJWKClientError) as exc:
            raise AuthVerificationError("Invalid bearer token") from exc

        return _current_user_from_payload(payload)

    def _verify_via_userinfo(self, token: str) -> CurrentUser:
        if not self._public_key:
            raise AuthVerificationError(
                "Legacy Supabase JWT verification requires "
                "SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY"
            )

        request = urllib.request.Request(
            self._userinfo_url,
            headers={
                "apikey": self._public_key,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(
                request, timeout=SUPABASE_USERINFO_TIMEOUT_SECONDS
            ) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise AuthVerificationError("Invalid bearer token") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise AuthVerificationError("Unable to verify bearer token") from exc

        if not isinstance(payload, dict):
            raise AuthVerificationError("Invalid bearer token")

        return _current_user_from_userinfo(payload)


def build_local_current_user(settings: Settings) -> CurrentUser:
    """Build the explicit local-development user for auth bypass mode."""
    return CurrentUser(
        id=settings.local_auth_user_id,
        email=settings.local_auth_email.strip().lower(),
        is_local_bypass=True,
    )


def get_token_verifier(settings: Settings) -> SupabaseTokenVerifier:
    """Return a cached verifier for the configured Supabase project."""
    issuer = settings.supabase_issuer
    jwks_url = settings.supabase_jwks_url
    userinfo_url = settings.supabase_userinfo_url
    if not issuer or not jwks_url or not userinfo_url:
        raise AuthVerificationError("Supabase auth is not configured")

    return _get_token_verifier(
        jwks_url,
        issuer,
        settings.supabase_jwt_audience,
        userinfo_url,
        settings.supabase_public_key,
    )


def clear_auth_cache() -> None:
    """Clear cached verifier state for tests."""
    _get_token_verifier.cache_clear()


@lru_cache(maxsize=4)
def _get_token_verifier(
    jwks_url: str,
    issuer: str,
    audience: str,
    userinfo_url: str,
    public_key: str | None,
) -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(
        jwks_url=jwks_url,
        issuer=issuer,
        audience=audience,
        userinfo_url=userinfo_url,
        public_key=public_key,
    )


def _resolve_token_algorithm(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise AuthVerificationError("Invalid bearer token") from exc

    algorithm = header.get("alg")
    if not isinstance(algorithm, str) or not algorithm.strip():
        raise AuthVerificationError("Bearer token algorithm is missing")
    return algorithm.strip()


def _current_user_from_payload(payload: dict[str, Any]) -> CurrentUser:
    return _current_user_from_claims(payload, subject_claim="sub")


def _current_user_from_userinfo(payload: dict[str, Any]) -> CurrentUser:
    return _current_user_from_claims(payload, subject_claim="id")


def _current_user_from_claims(payload: dict[str, Any], *, subject_claim: str) -> CurrentUser:
    raw_sub = payload.get(subject_claim)
    if not isinstance(raw_sub, str):
        raise AuthVerificationError("Bearer token subject is missing")

    try:
        user_id = uuid.UUID(raw_sub)
    except ValueError as exc:
        raise AuthVerificationError("Bearer token subject is invalid") from exc

    email = _resolve_email(payload, user_id)
    return CurrentUser(id=user_id, email=email)


def _resolve_email(payload: dict[str, Any], user_id: uuid.UUID) -> str:
    email_claim = payload.get("email")
    if isinstance(email_claim, str) and email_claim.strip():
        return email_claim.strip().lower()

    fallback = f"user-{user_id}@auth.styleus.invalid"
    return fallback
