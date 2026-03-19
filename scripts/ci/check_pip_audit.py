#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

IGNORED_TOOL_PACKAGES = {
    "pip",
    "pip-audit",
    "pip-api",
    "setuptools",
    "wheel",
}


def _load_report(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("dependencies"), list):
        return payload["dependencies"]  # type: ignore[return-value]
    raise SystemExit(f"Unsupported pip-audit JSON format in {path}")


def _normalize_package_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace("_", "-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail on pip-audit findings for project dependencies.",
    )
    parser.add_argument("report", type=Path, help="Path to the pip-audit JSON report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.report.exists():
        raise SystemExit(f"pip-audit report not found: {args.report}")

    dependencies = _load_report(args.report)
    ignored: list[str] = []
    findings: list[str] = []

    for dependency in dependencies:
        package_name = _normalize_package_name(dependency.get("name"))
        vulnerabilities = dependency.get("vulns") or []
        if not isinstance(vulnerabilities, list) or not vulnerabilities:
            continue

        rendered_vulns = []
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                continue
            vuln_id = vulnerability.get("id", "unknown")
            aliases = vulnerability.get("aliases") or []
            fix_versions = vulnerability.get("fix_versions") or []
            parts = [str(vuln_id)]
            if aliases:
                parts.append(f"aliases={','.join(str(alias) for alias in aliases)}")
            if fix_versions:
                parts.append(f"fix={','.join(str(version) for version in fix_versions)}")
            rendered_vulns.append(" ".join(parts))

        if not rendered_vulns:
            continue

        version = dependency.get("version", "unknown")
        rendered = f"- {package_name or 'unknown'} {version}: {'; '.join(rendered_vulns)}"
        if package_name in IGNORED_TOOL_PACKAGES:
            ignored.append(rendered)
            continue
        findings.append(rendered)

    if ignored:
        print("Ignoring pip-audit findings for audit/build tooling packages:")
        for finding in ignored:
            print(finding)

    if not findings:
        print("pip-audit reported no blocking vulnerabilities in project dependencies.")
        return 0

    print("Blocking pip-audit findings:")
    for finding in findings:
        print(finding)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
