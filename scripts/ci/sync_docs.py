#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import cast

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ManagedSection:
    path: Path
    start_marker: str
    end_marker: str
    content: str
    line_limit: int


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a top-level JSON object")
    return cast(dict[str, object], payload)


def _load_toml(path: Path) -> dict[str, object]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a top-level TOML table")
    return cast(dict[str, object], payload)


def _read_render_health_path() -> str:
    render_text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    in_services = False
    current_service_name: str | None = None
    for line in render_text.splitlines():
        stripped = line.strip()
        if stripped == "services:":
            in_services = True
            continue
        if not in_services:
            continue
        if stripped.startswith("- type:"):
            current_service_name = None
            continue
        if stripped.startswith("name:"):
            current_service_name = stripped.split(":", 1)[1].strip()
            continue
        if current_service_name == "styleus-api" and stripped.startswith("healthCheckPath:"):
            return stripped.split(":", 1)[1].strip()
    raise SystemExit("render.yaml is missing styleus-api healthCheckPath")


def _check_required_paths(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not (ROOT / path).exists()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required repository paths: {joined}")


def _build_structure_block() -> str:
    return dedent(
        """\
        ```text
        apps/
          web/         React frontend for wardrobe, upload, and review flows

        services/
  api/         FastAPI API, AI worker service, database models, and migrations

docs/
  architecture/ deployment and worker design notes
  config/       environment and platform configuration docs
  process/      delivery workflow notes

.github/
  workflows/    GitHub Actions CI and deployment verification

scripts/
  ci/           docs sync, security gating, and startup verification helpers

        dev.sh         One-command local launcher for web, API, worker, DB, and migrations
        render.yaml    Render service definitions for the API and AI worker
        Makefile       Repo-level convenience commands
        ```
        """
    ).strip()


def _managed_block(text: str) -> str:
    return dedent(text).strip()


def _build_sections() -> list[ManagedSection]:
    package_json = _load_json(ROOT / "apps/web/package.json")
    pyproject = _load_toml(ROOT / "services/api/pyproject.toml")

    scripts = package_json.get("scripts")
    if not isinstance(scripts, dict):
        raise SystemExit("apps/web/package.json must contain a scripts object")

    frontend_scripts = set(scripts.keys())
    required_frontend_scripts = {"build", "lint", "test", "typecheck"}
    missing_frontend_scripts = sorted(required_frontend_scripts - frontend_scripts)
    if missing_frontend_scripts:
        joined = ", ".join(missing_frontend_scripts)
        raise SystemExit(f"apps/web/package.json is missing required scripts: {joined}")

    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise SystemExit("services/api/pyproject.toml must contain a [project] table")

    optional_dependencies = project.get("optional-dependencies")
    if not isinstance(optional_dependencies, dict):
        raise SystemExit(
            "services/api/pyproject.toml must contain project.optional-dependencies"
        )

    dev_dependencies_raw = optional_dependencies.get("dev")
    if not isinstance(dev_dependencies_raw, list) or not all(
        isinstance(dep, str) for dep in dev_dependencies_raw
    ):
        raise SystemExit(
            "services/api/pyproject.toml must contain a string list at "
            "project.optional-dependencies.dev"
        )

    dev_dependencies = set(dev_dependencies_raw)
    backend_tools = {
        "ruff": any(dep.startswith("ruff") for dep in dev_dependencies),
        "mypy": any(dep.startswith("mypy") for dep in dev_dependencies),
        "pytest": any(dep.startswith("pytest") for dep in dev_dependencies),
    }
    missing_backend_tools = sorted(
        tool for tool, installed in backend_tools.items() if not installed
    )
    if missing_backend_tools:
        joined = ", ".join(missing_backend_tools)
        raise SystemExit(f"services/api/pyproject.toml is missing CI tools: {joined}")

    health_path = _read_render_health_path()
    return [
        ManagedSection(
            path=Path("README.md"),
            start_marker="<!-- project-structure:start -->",
            end_marker="<!-- project-structure:end -->",
            content=_build_structure_block(),
            line_limit=230,
        ),
        ManagedSection(
            path=Path("README.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=_managed_block(
                """
                ## CI/CD Pipeline

                - Pull requests run `.github/workflows/ci.yml`, which keeps the
                  merge gate local-safe with workflow validation, docs sync,
                  backend checks, frontend checks, and security scanning.
                - Backend validation uses sqlite plus
                  `python scripts/ci/verify_backend.py`, so normal CI does not
                  depend on Render, Vercel, or Supabase availability.
                - Merges to `main` run `.github/workflows/deploy.yml`, which
                  waits for the platform-native Vercel and Render deploys, then
                  verifies the API, worker, and optional frontend endpoints.
                - Detailed CI stages, required repository variables, and local
                  mirror commands live in
                  [docs/process/workflow.md](docs/process/workflow.md).
                """
            ),
            line_limit=230,
        ),
        ManagedSection(
            path=Path("docs/architecture/deployment.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=_managed_block(
                f"""
                ## CI/CD Pipeline

                - Pull requests run local-safe validation only; deployment
                  happens through Vercel and Render after merge.
                - `.github/workflows/deploy.yml` verifies the hosted API at
                  `{health_path}`, the worker `/health` endpoint, and the
                  optional frontend URL after the platform deploy window.
                - The canonical delivery workflow and CI/CD operating notes
                  live in `docs/process/workflow.md`.
                """
            ),
            line_limit=200,
        ),
        ManagedSection(
            path=Path("docs/config/environments.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=_managed_block(
                """
                ## CI/CD Pipeline

                - CI uses local-safe values for `APP_ENV`, `DATABASE_URL`,
                  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
                  `SUPABASE_STORAGE_BUCKET`, `LOCAL_AUTH_BYPASS`,
                  `RUN_MIGRATIONS_ON_START`, and `RUN_SEED_ON_START`.
                - Pull request validation does not require hosted platform
                  secrets for normal backend or frontend checks.
                - Repository variables `DEPLOY_HEALTHCHECK_URL` and
                  `DEPLOY_WORKER_HEALTHCHECK_URL` should be set when the hosted
                  API or worker URL differs from the workflow defaults.
                - Optional repository variables `DEPLOY_FRONTEND_URL`,
                  `DEPLOY_INITIAL_WAIT_SECONDS`, `DEPLOY_TIMEOUT_SECONDS`, and
                  `DEPLOY_POLL_INTERVAL_SECONDS` tune post-merge deploy
                  verification.
                - Optional repository secret
                  `SECRET_SCAN_REVIEW_GITHUB_TOKEN` enables GitHub
                  secret-scanning alert review in CI when GitHub Advanced
                  Security is available.
                """
            ),
            line_limit=200,
        ),
        ManagedSection(
            path=Path("docs/process/workflow.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=_managed_block(
                """
                ## Checks

                - `.github/workflows/ci.yml` is the pull request merge gate.
                - Pull requests stay mergeable only when workflow validation,
                  docs sync, backend, frontend, and security checks pass.
                - `.github/workflows/deploy.yml` runs after merges to `main`
                  and verifies the deployed API, worker, and optional frontend
                  endpoints.
                - `python scripts/ci/sync_docs.py` keeps the short generated
                  CI/CD summaries aligned with the current repo shape.
                """
            ),
            line_limit=200,
        ),
        ManagedSection(
            path=Path("recap.md"),
            start_marker="<!-- current-shape:start -->",
            end_marker="<!-- current-shape:end -->",
            content=_managed_block(
                """
                - `apps/web` contains the only frontend application and is deployed by Vercel.
                - `services/api` contains the API, worker service, migrations,
                  and seed pipeline, and is deployed by Render.
                - `.github/workflows/ci.yml` validates workflow syntax, docs,
                  code quality, tests, builds, and security for pull requests.
                - `.github/workflows/deploy.yml` verifies the production
                  backend health after merges to `main`, and can optionally
                  verify the frontend URL too.
                - `docs` contains only cross-cutting notes that are still
                  relevant to operation, deployment, or delivery workflow.
                """
            ),
            line_limit=200,
        ),
        ManagedSection(
            path=Path("recap.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=_managed_block(
                """
                ## CI/CD Pipeline

                - PRs fail on backend or frontend validation errors,
                  documentation drift, dependency review issues, high or
                  critical audit findings, or detected secrets.
                - The docs sync script owns the short generated CI/CD summaries
                  in `README.md`, `docs/architecture/deployment.md`,
                  `docs/config/environments.md`, `docs/process/workflow.md`,
                  and `recap.md`.
                - Production deploys stay platform-native: Vercel handles the
                  web app, Render rebuilds the API and worker services, and
                  GitHub Actions verifies the hosted health endpoints after
                  merge.
                """
            ),
            line_limit=200,
        ),
    ]


def _replace_section(text: str, section: ManagedSection) -> str:
    if section.start_marker not in text or section.end_marker not in text:
        raise SystemExit(
            f"{section.path} is missing managed markers "
            f"{section.start_marker} / {section.end_marker}"
        )
    before, remainder = text.split(section.start_marker, 1)
    _, after = remainder.split(section.end_marker, 1)
    managed = f"{section.start_marker}\n{section.content.rstrip()}\n{section.end_marker}"
    return before + managed + after


def _write_or_check(section: ManagedSection, *, check: bool) -> bool:
    path = ROOT / section.path
    original = path.read_text(encoding="utf-8")
    updated = _replace_section(original, section)
    line_count = len(updated.splitlines())
    if line_count > section.line_limit:
        raise SystemExit(
            f"{section.path} exceeds the {section.line_limit}-line limit after sync ({line_count})"
        )
    if original == updated:
        return False
    if check:
        diff = difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=str(section.path),
            tofile=str(section.path),
            lineterm="",
        )
        print("\n".join(diff))
        return True
    path.write_text(updated, encoding="utf-8")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize managed CI/CD documentation sections."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when a managed section is out of date.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    _check_required_paths(
        [
            Path("apps/web"),
            Path("services/api"),
            Path("docs/architecture/deployment.md"),
            Path("docs/config/environments.md"),
            Path("docs/process/workflow.md"),
            Path(".github/workflows/ci.yml"),
            Path(".github/workflows/deploy.yml"),
            Path("render.yaml"),
        ]
    )

    changed_paths: list[str] = []
    seen_paths: set[Path] = set()
    for section in _build_sections():
        changed = _write_or_check(section, check=args.check)
        if changed and section.path not in seen_paths:
            changed_paths.append(str(section.path))
            seen_paths.add(section.path)

    if args.check and changed_paths:
        joined = ", ".join(changed_paths)
        print(
            "\nDocumentation is out of date. Run "
            f"`python scripts/ci/sync_docs.py` to update: {joined}"
        )
        return 1

    if changed_paths:
        joined = ", ".join(changed_paths)
        print(f"Synchronized documentation: {joined}")
    else:
        print("Documentation is already synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
