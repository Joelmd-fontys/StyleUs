#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEPLOY_HEALTHCHECK_URL = "https://styleus-api.onrender.com/health"


@dataclass(frozen=True, slots=True)
class ManagedSection:
    path: Path
    start_marker: str
    end_marker: str
    content: str
    line_limit: int


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _read_render_health_path() -> str:
    render_text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    for line in render_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("healthCheckPath:"):
            return stripped.split(":", 1)[1].strip()
    raise SystemExit("render.yaml is missing healthCheckPath")


def _check_required_paths(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not (ROOT / path).exists()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required repository paths: {joined}")


def _build_structure_block() -> str:
    return """```text
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
```"""


def _build_sections() -> list[ManagedSection]:
    package_json = _load_json(ROOT / "apps/web/package.json")
    pyproject = _load_toml(ROOT / "services/api/pyproject.toml")

    frontend_scripts = set(((package_json.get("scripts") or {})).keys())
    required_frontend_scripts = {"build", "lint", "test", "typecheck"}
    missing_frontend_scripts = sorted(required_frontend_scripts - frontend_scripts)
    if missing_frontend_scripts:
        joined = ", ".join(missing_frontend_scripts)
        raise SystemExit(f"apps/web/package.json is missing required scripts: {joined}")

    dev_dependencies = set(
        pyproject["project"]["optional-dependencies"]["dev"]  # type: ignore[index]
    )
    backend_tools = {
        "ruff": any(dep.startswith("ruff") for dep in dev_dependencies),
        "mypy": any(dep.startswith("mypy") for dep in dev_dependencies),
        "pytest": any(dep.startswith("pytest") for dep in dev_dependencies),
    }
    missing_backend_tools = sorted(tool for tool, installed in backend_tools.items() if not installed)
    if missing_backend_tools:
        joined = ", ".join(missing_backend_tools)
        raise SystemExit(f"services/api/pyproject.toml is missing CI tools: {joined}")

    health_path = _read_render_health_path()
    deploy_target = f"`DEPLOY_HEALTHCHECK_URL` (defaults to `{DEFAULT_DEPLOY_HEALTHCHECK_URL}`)"

    return [
        ManagedSection(
            path=Path("README.md"),
            start_marker="<!-- project-structure:start -->",
            end_marker="<!-- project-structure:end -->",
            content=_build_structure_block(),
            line_limit=220,
        ),
        ManagedSection(
            path=Path("README.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=f"""## CI/CD Pipeline

- `.github/workflows/ci.yml` runs on every pull request and branch push.
- Backend validation runs `python -m ruff check .`, `python -m mypy app`, `python -m pytest -q`, and `python scripts/ci/verify_backend.py` against PostgreSQL.
- Frontend validation runs `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`.
- Security checks run `actions/dependency-review-action`, `npm audit --audit-level=high`, `pip-audit`, and `gitleaks`.
- `python scripts/ci/sync_docs.py --check` fails when the generated documentation sections drift from the current repo shape.
- After merge to `main`, `.github/workflows/deploy.yml` waits for the platform Git deploy window and polls {deploy_target} until `{health_path}` reports `status=ok` and `database=ok`.""",
            line_limit=220,
        ),
        ManagedSection(
            path=Path("docs/architecture/deployment.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=f"""## CI/CD Pipeline

- Pull requests and branch pushes run `.github/workflows/ci.yml`.
- GitHub Actions validates backend linting, type checking, tests, startup verification, frontend checks, documentation sync, dependency review, `npm audit`, `pip-audit`, and `gitleaks`.
- Merges to `main` let Vercel and Render deploy through Git integration; `.github/workflows/deploy.yml` only verifies the result by polling {deploy_target}.
- The production readiness gate is `GET {health_path}`, which must confirm both API liveness and database connectivity.""",
            line_limit=200,
        ),
        ManagedSection(
            path=Path("docs/config/environments.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=f"""## CI/CD Pipeline

- CI uses a GitHub Actions PostgreSQL service plus local-safe values for `APP_ENV`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `LOCAL_AUTH_BYPASS`, `RUN_MIGRATIONS_ON_START`, and `RUN_SEED_ON_START`.
- Pull request validation does not require hosted platform secrets for normal backend or frontend checks.
- Deploy verification reads {deploy_target}; set the repository variable when the production API URL changes.
- Optional repository secret `SECRET_SCAN_REVIEW_GITHUB_TOKEN` enables GitHub secret-scanning alert review in CI when GitHub Advanced Security is available.""",
            line_limit=200,
        ),
        ManagedSection(
            path=Path("docs/process/workflow.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content="""## Checks

- `.github/workflows/ci.yml` runs on every pull request and push.
- Pull requests stay mergeable only when backend, frontend, security, build, and documentation checks pass.
- `python scripts/ci/sync_docs.py` keeps the managed docs sections aligned with the repository shape and deployment workflow.
- `.github/workflows/deploy.yml` runs after merges to `main` and verifies the deployed API health endpoint.""",
            line_limit=200,
        ),
        ManagedSection(
            path=Path("recap.md"),
            start_marker="<!-- current-shape:start -->",
            end_marker="<!-- current-shape:end -->",
            content="""- `apps/web` contains the only frontend application and is deployed by Vercel.
- `services/api` contains the API, worker service, migrations, and seed pipeline, and is deployed by Render.
- `.github/workflows/ci.yml` validates docs, code quality, tests, builds, and security on every pull request and push.
- `.github/workflows/deploy.yml` verifies the production backend health after merges to `main`.
- `docs` contains only cross-cutting notes that are still relevant to operation, deployment, or delivery workflow.""",
            line_limit=200,
        ),
        ManagedSection(
            path=Path("recap.md"),
            start_marker="<!-- ci-cd:start -->",
            end_marker="<!-- ci-cd:end -->",
            content=f"""## CI/CD Pipeline

- PRs fail on backend or frontend validation errors, documentation drift, dependency review issues, high or critical audit findings, or detected secrets.
- The docs sync script owns the managed CI/CD sections in `README.md`, `docs/architecture/deployment.md`, `docs/config/environments.md`, `docs/process/workflow.md`, and `recap.md`.
- Production deploys stay platform-native: Vercel handles the web app, Render rebuilds the API and worker services, and GitHub Actions verifies {deploy_target} after merge.""",
            line_limit=200,
        ),
    ]


def _replace_section(text: str, section: ManagedSection) -> str:
    if section.start_marker not in text or section.end_marker not in text:
        raise SystemExit(
            f"{section.path} is missing managed markers {section.start_marker} / {section.end_marker}"
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
    parser = argparse.ArgumentParser(description="Synchronize managed CI/CD documentation sections.")
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
        print(f"\nDocumentation is out of date. Run `python scripts/ci/sync_docs.py` to update: {joined}")
        return 1

    if changed_paths:
        joined = ", ".join(changed_paths)
        print(f"Synchronized documentation: {joined}")
    else:
        print("Documentation is already synchronized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
