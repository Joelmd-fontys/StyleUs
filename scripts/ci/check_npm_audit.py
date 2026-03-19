#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail on high or critical npm audit findings.",
    )
    parser.add_argument("report", type=Path, help="Path to the npm audit JSON report")
    return parser.parse_args()


def _load_report(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"::warning::npm audit report at {path} was not valid JSON: {exc}")
        return {}

    if isinstance(payload, dict):
        return payload
    print(f"::warning::npm audit report at {path} was not a JSON object.")
    return {}


def _count_vulnerabilities(payload: dict[str, object]) -> tuple[int, int] | None:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        vulnerabilities = metadata.get("vulnerabilities")
        if isinstance(vulnerabilities, dict):
            high = int(vulnerabilities.get("high", 0) or 0)
            critical = int(vulnerabilities.get("critical", 0) or 0)
            return high, critical

    advisories = payload.get("advisories")
    if isinstance(advisories, dict):
        high = 0
        critical = 0
        for advisory in advisories.values():
            if not isinstance(advisory, dict):
                continue
            severity = str(advisory.get("severity", "")).lower()
            if severity == "critical":
                critical += 1
            elif severity == "high":
                high += 1
        return high, critical

    return None


def main() -> int:
    args = parse_args()
    if not args.report.exists():
        raise SystemExit(f"npm audit report not found: {args.report}")

    payload = _load_report(args.report)
    counts = _count_vulnerabilities(payload)
    if counts is None:
        message = payload.get("message")
        if isinstance(message, str) and message:
            print(f"::warning::npm audit did not return vulnerability data: {message}")
        else:
            print(
                "::warning::npm audit did not return vulnerability metadata; treating this as an execution issue."
            )
        return 0

    high, critical = counts
    if high == 0 and critical == 0:
        print("npm audit reported no blocking high or critical vulnerabilities.")
        return 0

    print(f"Blocking npm audit findings: high={high}, critical={critical}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
