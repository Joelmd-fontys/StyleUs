#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from http.client import HTTPResponse
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_BODY_PREVIEW_CHARS = 400


@dataclass(frozen=True, slots=True)
class CheckResult:
    ok: bool
    message: str


class _DoctypeHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_html_doctype = False

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.has_html_doctype = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll hosted deployment endpoints until they are ready."
    )
    parser.add_argument("--kind", choices=("api", "worker", "frontend"), required=True)
    parser.add_argument("--url", required=True, help="Endpoint or page URL to verify")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Total time to keep polling before failing",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Delay between attempts",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        help="Timeout for each HTTP request",
    )
    parser.add_argument(
        "--body-preview-chars",
        type=int,
        default=DEFAULT_BODY_PREVIEW_CHARS,
        help="How much response body to print per attempt",
    )
    return parser.parse_args()


def _parse_json(body: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def evaluate_api_response(status_code: int, body: str) -> CheckResult:
    payload = _parse_json(body)
    if status_code != 200:
        return CheckResult(False, f"expected HTTP 200, got {status_code}")
    if payload is None:
        return CheckResult(False, "expected JSON object payload from API /health")
    if payload.get("status") != "ok":
        return CheckResult(False, f"expected status=ok, got {payload.get('status')!r}")
    if payload.get("database") != "ok":
        return CheckResult(False, f"expected database=ok, got {payload.get('database')!r}")
    return CheckResult(True, "API health endpoint is ready.")


def evaluate_worker_response(status_code: int, body: str) -> CheckResult:
    payload = _parse_json(body)
    if status_code != 200:
        return CheckResult(False, f"expected HTTP 200, got {status_code}")
    if payload is None:
        return CheckResult(False, "expected JSON object payload from worker /health")
    if payload.get("status") != "ok":
        return CheckResult(False, f"expected status=ok, got {payload.get('status')!r}")
    if payload.get("service") != "ai-worker":
        return CheckResult(False, f"expected service='ai-worker', got {payload.get('service')!r}")
    if payload.get("mode") == "disabled":
        return CheckResult(
            False,
            "worker reported mode=disabled; classifier-backed worker is not ready",
        )
    pending_jobs = payload.get("pending_jobs")
    running_jobs = payload.get("running_jobs")
    if not isinstance(pending_jobs, int):
        return CheckResult(False, "expected integer pending_jobs in worker health payload")
    if not isinstance(running_jobs, int):
        return CheckResult(False, "expected integer running_jobs in worker health payload")
    return CheckResult(True, "Worker health endpoint is ready.")


def evaluate_frontend_response(status_code: int, body: str) -> CheckResult:
    if status_code != 200:
        return CheckResult(False, f"expected HTTP 200, got {status_code}")
    parser = _DoctypeHTMLParser()
    parser.feed(body)
    if not parser.has_html_doctype:
        return CheckResult(False, "expected an HTML document with <!doctype html>")
    return CheckResult(True, "Frontend URL is serving HTML.")


def evaluate_response(kind: str, status_code: int, body: str) -> CheckResult:
    if kind == "api":
        return evaluate_api_response(status_code, body)
    if kind == "worker":
        return evaluate_worker_response(status_code, body)
    return evaluate_frontend_response(status_code, body)


def _preview_body(body: str, limit: int) -> str:
    compact = body.strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def fetch(url: str, *, request_timeout_seconds: int) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=request_timeout_seconds) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except (urllib.error.URLError, TimeoutError) as exc:
        return 0, str(exc)


def _read_response(response: HTTPResponse) -> tuple[int, str]:
    body = response.read().decode("utf-8", errors="replace")
    return response.status, body


def poll_until_ready(
    *,
    kind: str,
    url: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
    request_timeout_seconds: int,
    body_preview_chars: int,
) -> int:
    deadline = time.monotonic() + timeout_seconds
    attempt = 1
    while time.monotonic() < deadline:
        status_code, body = fetch(url, request_timeout_seconds=request_timeout_seconds)
        result = evaluate_response(kind, status_code, body)
        print(f"[{kind}] attempt={attempt} status_code={status_code} url={url}")
        preview = _preview_body(body, body_preview_chars)
        if preview:
            print(preview)
        print(result.message)
        if result.ok:
            return 0
        attempt += 1
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            break
        sleep_seconds = min(poll_interval_seconds, max(0, remaining_seconds))
        print(
            f"Retrying in {sleep_seconds:.0f} seconds. "
            f"Remaining budget: {remaining_seconds:.0f} seconds."
        )
        time.sleep(sleep_seconds)

    print(f"{kind} deployment verification failed before timeout.")
    return 1


def main() -> int:
    args = parse_args()
    return poll_until_ready(
        kind=args.kind,
        url=args.url,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        request_timeout_seconds=args.request_timeout_seconds,
        body_preview_chars=args.body_preview_chars,
    )


if __name__ == "__main__":
    raise SystemExit(main())
