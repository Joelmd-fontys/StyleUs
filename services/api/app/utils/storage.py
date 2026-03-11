"""Supabase Storage helpers."""

from __future__ import annotations

import json
import socket
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.core.config import Settings
from app.utils.http import urlopen


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase Storage returns an unexpected error."""


class SupabaseStorageNotFoundError(SupabaseStorageError):
    """Raised when a storage object could not be found."""


@dataclass(slots=True)
class SignedUploadTarget:
    bucket: str
    object_path: str
    upload_url: str
    token: str | None = None


@dataclass(slots=True)
class DownloadedObject:
    object_path: str
    data: bytes
    content_type: str | None = None
    size: int | None = None


class SupabaseStorageAdapter:
    """Small REST adapter around private Supabase Storage endpoints."""

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        bucket: str,
        signed_url_ttl_seconds: int = 3600,
        request_timeout_seconds: float = 15.0,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket
        self.signed_url_ttl_seconds = signed_url_ttl_seconds
        self.request_timeout_seconds = request_timeout_seconds
        self.storage_api_url = f"{self.supabase_url}/storage/v1"

    def create_signed_upload_target(
        self,
        object_path: str,
        *,
        upsert: bool = False,
    ) -> SignedUploadTarget:
        payload = self._request_json(
            "POST",
            self._object_path(f"/object/upload/sign/{self.bucket}", object_path),
            json_body={"upsert": upsert},
        )
        token = self._extract_token(payload)
        raw_url = self._extract_signed_url(payload)
        upload_url = raw_url or self._absolute_storage_url(
            f"/object/upload/sign/{self.bucket}/{self._quote_object_path(object_path)}"
        )
        if token and "token=" not in upload_url:
            separator = "&" if "?" in upload_url else "?"
            upload_url = f"{upload_url}{separator}token={parse.quote(token)}"
        return SignedUploadTarget(
            bucket=self.bucket,
            object_path=str(payload.get("path") or object_path),
            upload_url=upload_url,
            token=token,
        )

    def create_signed_url(self, object_path: str, *, expires_in: int | None = None) -> str:
        payload = self._request_json(
            "POST",
            self._object_path(f"/object/sign/{self.bucket}", object_path),
            json_body={"expiresIn": expires_in or self.signed_url_ttl_seconds},
        )
        signed_url = self._extract_signed_url(payload)
        if not signed_url:
            raise SupabaseStorageError("Supabase Storage did not return a signed read URL")
        return signed_url

    def create_signed_urls(
        self,
        object_paths: Sequence[str],
        *,
        expires_in: int | None = None,
    ) -> dict[str, str]:
        unique_paths = list(dict.fromkeys(path for path in object_paths if path))
        if not unique_paths:
            return {}

        payload = self._request_json(
            "POST",
            f"/object/sign/{self.bucket}",
            json_body={
                "paths": unique_paths,
                "expiresIn": expires_in or self.signed_url_ttl_seconds,
            },
        )

        entries = payload if isinstance(payload, list) else payload.get("signedURLs") or payload.get("data")
        if not isinstance(entries, list):
            raise SupabaseStorageError("Supabase Storage returned an unexpected signed URL payload")

        signed: dict[str, str] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            path = entry.get("path")
            signed_url = self._extract_signed_url(entry)
            if isinstance(path, str) and signed_url:
                signed[path] = signed_url
        return signed

    def get_object_info(self, object_path: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            self._object_path(f"/object/info/{self.bucket}", object_path),
        )

    def download_object(self, object_path: str) -> DownloadedObject:
        body, headers = self._request_bytes(
            "GET",
            self._object_path(f"/object/authenticated/{self.bucket}", object_path),
        )
        content_length = headers.get("Content-Length")
        size = int(content_length) if content_length and content_length.isdigit() else len(body)
        return DownloadedObject(
            object_path=object_path,
            data=body,
            content_type=headers.get_content_type() if headers.get_content_type() else None,
            size=size,
        )

    def upload_bytes(
        self,
        object_path: str,
        *,
        data: bytes,
        content_type: str,
        upsert: bool = True,
    ) -> None:
        self._request_bytes(
            "POST",
            self._object_path(f"/object/{self.bucket}", object_path),
            data=data,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "private, max-age=0, no-transform",
                "x-upsert": "true" if upsert else "false",
            },
            expected_statuses=(200, 201),
        )

    def delete_objects(self, object_paths: Iterable[str]) -> None:
        prefixes = [path for path in dict.fromkeys(object_paths) if path]
        if not prefixes:
            return
        self._request_json(
            "DELETE",
            f"/object/{self.bucket}",
            json_body={"prefixes": prefixes},
            expected_statuses=(200, 204),
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: Sequence[int] = (200,),
    ) -> dict[str, Any] | list[dict[str, Any]]:
        body, _headers = self._request_bytes(
            method,
            path,
            data=json.dumps(json_body).encode("utf-8") if json_body is not None else None,
            headers={
                "Content-Type": "application/json",
                **(dict(headers) if headers else {}),
            },
            expected_statuses=expected_statuses,
        )
        if not body:
            return {}
        try:
            decoded = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise SupabaseStorageError("Supabase Storage returned invalid JSON") from exc
        if isinstance(decoded, dict):
            return decoded
        if isinstance(decoded, list):
            return [entry for entry in decoded if isinstance(entry, dict)]
        raise SupabaseStorageError("Supabase Storage returned an unsupported payload")

    def _request_bytes(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        expected_statuses: Sequence[int] = (200,),
    ) -> tuple[bytes, Any]:
        request_headers = self._service_headers()
        if headers:
            request_headers.update(headers)
        url = path if path.startswith("http") else f"{self.storage_api_url}{path}"
        req = request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(req, timeout=self.request_timeout_seconds) as response:
                status_code = getattr(response, "status", response.getcode())
                body = response.read()
                if status_code not in expected_statuses:
                    raise SupabaseStorageError(
                        f"Supabase Storage returned unexpected status {status_code}"
                    )
                return body, response.headers
        except error.HTTPError as exc:
            if exc.code == 404:
                raise SupabaseStorageNotFoundError(
                    f"Storage object not found for path '{path}'"
                ) from exc
            message = self._decode_error_body(exc.read())
            raise SupabaseStorageError(message) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise SupabaseStorageError(
                    f"Supabase Storage request timed out after {self.request_timeout_seconds:g}s"
                ) from exc
            raise SupabaseStorageError(f"Unable to reach Supabase Storage: {exc.reason}") from exc
        except TimeoutError as exc:
            raise SupabaseStorageError(
                f"Supabase Storage request timed out after {self.request_timeout_seconds:g}s"
            ) from exc

    def _service_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }

    def _object_path(self, prefix: str, object_path: str) -> str:
        return f"{prefix}/{self._quote_object_path(object_path)}"

    @staticmethod
    def _quote_object_path(object_path: str) -> str:
        return parse.quote(object_path.lstrip("/"), safe="/")

    def _extract_signed_url(self, payload: Mapping[str, Any]) -> str | None:
        raw = payload.get("signedURL") or payload.get("signedUrl") or payload.get("url")
        if not isinstance(raw, str) or not raw:
            return None
        return self._absolute_storage_url(raw)

    @staticmethod
    def _extract_token(payload: Mapping[str, Any]) -> str | None:
        token = payload.get("token")
        if isinstance(token, str) and token:
            return token
        for candidate in (
            payload.get("signedURL"),
            payload.get("signedUrl"),
            payload.get("url"),
        ):
            if not isinstance(candidate, str) or "token=" not in candidate:
                continue
            query = parse.urlparse(candidate).query
            token_values = parse.parse_qs(query).get("token", [])
            if token_values:
                return token_values[0]
        return None

    def _absolute_storage_url(self, value: str) -> str:
        if value.startswith("http://") or value.startswith("https://"):
            return value
        if value.startswith("/storage/v1/"):
            return f"{self.supabase_url}{value}"
        if value.startswith("/object/"):
            return f"{self.storage_api_url}{value}"
        if value.startswith("object/"):
            return f"{self.storage_api_url}/{value}"
        return f"{self.storage_api_url}/{value.lstrip('/')}"

    @staticmethod
    def _decode_error_body(raw: bytes) -> str:
        if not raw:
            return "Supabase Storage request failed"
        text = raw.decode("utf-8", errors="ignore")
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return text or "Supabase Storage request failed"
        if isinstance(decoded, dict):
            message = decoded.get("message") or decoded.get("error")
            if isinstance(message, str) and message:
                return message
        return text or "Supabase Storage request failed"


def get_storage_adapter(settings: Settings) -> SupabaseStorageAdapter:
    """Build a Supabase Storage adapter for the current settings."""

    if not (
        settings.supabase_url
        and settings.supabase_service_role_key
        and settings.supabase_storage_bucket
    ):
        raise SupabaseStorageError("Supabase Storage is not configured")

    return SupabaseStorageAdapter(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        bucket=settings.supabase_storage_bucket,
        signed_url_ttl_seconds=settings.supabase_signed_url_ttl_seconds,
        request_timeout_seconds=settings.supabase_http_timeout_seconds,
    )
