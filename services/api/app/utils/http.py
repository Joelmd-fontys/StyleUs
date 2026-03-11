"""HTTP helpers with an explicit CA bundle for outbound TLS."""

from __future__ import annotations

import ssl
import urllib.request
from functools import lru_cache
from typing import Any

import certifi


@lru_cache(maxsize=1)
def get_ssl_context() -> ssl.SSLContext:
    """Return a reusable SSL context backed by certifi's CA bundle."""
    return ssl.create_default_context(cafile=certifi.where())


def urlopen(target: str | urllib.request.Request, *, timeout: float | None = None) -> Any:
    """Open an HTTPS request with the shared certifi-backed SSL context."""
    kwargs: dict[str, Any] = {"context": get_ssl_context()}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return urllib.request.urlopen(target, **kwargs)
