from __future__ import annotations

import tomllib
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parent.parent


def test_runtime_dependencies_include_heuristic_ai_stack() -> None:
    pyproject = tomllib.loads((API_ROOT / "pyproject.toml").read_text())

    dependencies = pyproject["project"]["dependencies"]
    ai_extra = pyproject["project"]["optional-dependencies"]["ai"]
    dev_extra = pyproject["project"]["optional-dependencies"]["dev"]

    assert "numpy==1.26.4" in dependencies
    assert "scikit-learn==1.5.0" in dependencies
    assert "open-clip-torch==2.26.1" in ai_extra
    assert "timm==1.0.12" in ai_extra
    assert "transformers==5.0.0" in ai_extra
    assert all(not dependency.startswith("transformers==") for dependency in dev_extra)
    assert "pytest==9.0.3" in dev_extra


def test_dockerfiles_install_expected_dependency_sets() -> None:
    api_dockerfile = (API_ROOT / "Dockerfile").read_text()
    worker_dockerfile = (API_ROOT / "Dockerfile.worker").read_text()

    assert 'pip install --no-cache-dir .' in api_dockerfile
    assert "COPY alembic.ini ./alembic.ini" in api_dockerfile
    assert "COPY alembic ./alembic" in api_dockerfile
    assert 'pip install --no-cache-dir ".[ai]"' in worker_dockerfile
    assert "COPY alembic.ini ./alembic.ini" in worker_dockerfile
    assert "COPY alembic ./alembic" in worker_dockerfile


def test_render_blueprint_runs_migrations_before_serving() -> None:
    render_blueprint = (REPO_ROOT / "render.yaml").read_text()

    assert "preDeployCommand: python -m alembic upgrade head" in render_blueprint
    assert render_blueprint.count('key: RUN_MIGRATIONS_ON_START') >= 2
    assert render_blueprint.count('value: "true"') >= 2


def test_ai_embedding_migration_exists_for_wardrobe_items() -> None:
    migration = (
        API_ROOT / "alembic" / "versions" / "202603181030_add_ai_embeddings_and_attributes.py"
    ).read_text()

    assert 'down_revision: str | None = "202603111200"' in migration
    assert 'sa.Column("ai_attribute_tags", sa.JSON(), nullable=True)' in migration
    assert 'sa.Column("ai_embedding", sa.JSON(), nullable=True)' in migration
    assert 'sa.Column("ai_embedding_model", sa.String(length=255), nullable=True)' in migration
