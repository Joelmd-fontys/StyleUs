from __future__ import annotations

from pathlib import Path
import tomllib


API_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_dependencies_include_heuristic_ai_stack() -> None:
    pyproject = tomllib.loads((API_ROOT / "pyproject.toml").read_text())

    dependencies = pyproject["project"]["dependencies"]
    ai_extra = pyproject["project"]["optional-dependencies"]["ai"]

    assert "numpy==1.26.4" in dependencies
    assert "scikit-learn==1.5.0" in dependencies
    assert "open-clip-torch==2.26.1" in ai_extra
    assert "timm==1.0.12" in ai_extra


def test_dockerfiles_install_expected_dependency_sets() -> None:
    api_dockerfile = (API_ROOT / "Dockerfile").read_text()
    worker_dockerfile = (API_ROOT / "Dockerfile.worker").read_text()

    assert 'pip install --no-cache-dir .' in api_dockerfile
    assert 'pip install --no-cache-dir ".[ai]"' in worker_dockerfile
