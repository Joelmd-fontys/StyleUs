#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    import certifi
except Exception:  # pragma: no cover - optional dependency in local environments
    certifi = None

SEVERITY_ORDER = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


def _build_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


SSL_CONTEXT = _build_ssl_context()


@dataclass(frozen=True, slots=True)
class ResolvedSeverity:
    level: str | None
    source: str


def _normalize_severity(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.strip().upper()
    if upper in SEVERITY_ORDER:
        return upper
    return None


def _severity_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return None


def _load_report(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("dependencies"), list):
        return payload["dependencies"]  # type: ignore[return-value]
    raise SystemExit(f"Unsupported pip-audit JSON format in {path}")


def _http_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "styleus-ci-pip-audit-gate",
        },
    )
    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        return json.load(response)  # type: ignore[return-value]


def _resolve_with_nvd(cve_id: str) -> ResolvedSeverity | None:
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={urllib.parse.quote(cve_id)}"
    try:
        payload = _http_json(url)
    except urllib.error.URLError as exc:
        print(f"warning: unable to query NVD for {cve_id}: {exc}")
        return None
    vulnerabilities = payload.get("vulnerabilities") or []
    if not vulnerabilities:
        return None
    metrics = ((vulnerabilities[0] or {}).get("cve") or {}).get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        metric_entries = metrics.get(key) or []
        if not metric_entries:
            continue
        metric = metric_entries[0]
        cvss_data = metric.get("cvssData") or {}
        severity = _normalize_severity(metric.get("baseSeverity")) or _normalize_severity(
            cvss_data.get("baseSeverity")
        )
        if severity:
            return ResolvedSeverity(severity, f"NVD:{cve_id}")
        score = cvss_data.get("baseScore")
        if isinstance(score, (int, float)):
            return ResolvedSeverity(_severity_from_score(float(score)), f"NVD:{cve_id}")
    return None


def _resolve_with_osv(vuln_id: str) -> ResolvedSeverity | None:
    url = f"https://api.osv.dev/v1/vulns/{urllib.parse.quote(vuln_id)}"
    try:
        payload = _http_json(url)
    except urllib.error.URLError as exc:
        print(f"warning: unable to query OSV for {vuln_id}: {exc}")
        return None

    database_specific = payload.get("database_specific")
    if isinstance(database_specific, dict):
        severity = _normalize_severity(database_specific.get("severity"))
        if severity:
            return ResolvedSeverity(severity, f"OSV:{vuln_id}")

    for affected in payload.get("affected") or []:
        if not isinstance(affected, dict):
            continue
        affected_specific = affected.get("database_specific")
        if not isinstance(affected_specific, dict):
            continue
        severity = _normalize_severity(affected_specific.get("severity"))
        if severity:
            return ResolvedSeverity(severity, f"OSV:{vuln_id}")

    return None


def _resolve_severity(vuln: dict[str, object]) -> ResolvedSeverity | None:
    aliases = [alias for alias in (vuln.get("aliases") or []) if isinstance(alias, str)]
    for alias in aliases:
        if alias.startswith("CVE-"):
            resolved = _resolve_with_nvd(alias)
            if resolved and resolved.level:
                return resolved

    vuln_id = vuln.get("id")
    if isinstance(vuln_id, str):
        resolved = _resolve_with_osv(vuln_id)
        if resolved and resolved.level:
            return resolved

    for alias in aliases:
        resolved = _resolve_with_osv(alias)
        if resolved and resolved.level:
            return resolved
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail on high or critical pip-audit findings.")
    parser.add_argument("report", type=Path, help="Path to the pip-audit JSON report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.report.exists():
        raise SystemExit(f"pip-audit report not found: {args.report}")

    dependencies = _load_report(args.report)
    findings: list[str] = []
    blocking: list[str] = []

    for dependency in dependencies:
        package = dependency.get("name")
        version = dependency.get("version")
        vulns = dependency.get("vulns") or []
        if not vulns:
            continue
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            vuln_id = vuln.get("id", "unknown")
            resolved = _resolve_severity(vuln)
            severity = resolved.level if resolved else None
            source = resolved.source if resolved else "unresolved"
            rendered = f"- {package} {version}: {vuln_id} [{severity or 'UNKNOWN'} via {source}]"
            findings.append(rendered)
            if severity in {"HIGH", "CRITICAL"}:
                blocking.append(rendered)

    if not findings:
        print("pip-audit reported no vulnerabilities.")
        return 0

    print("pip-audit findings:")
    for finding in findings:
        print(finding)

    if blocking:
        print("\nBlocking pip-audit findings (high or critical):")
        for finding in blocking:
            print(finding)
        return 1

    print("\npip-audit reported vulnerabilities, but none resolved to high or critical severity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
