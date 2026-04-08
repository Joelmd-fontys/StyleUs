from __future__ import annotations

import os

import pytest

from app.ai import benchmark


def test_load_category_cases_uses_explicit_fixture_manifest() -> None:
    cases = benchmark.load_category_cases()

    assert len(cases) == 10
    assert {case.expected_category for case in cases} == {
        "accessory",
        "bottom",
        "outerwear",
        "shoes",
        "top",
    }
    assert all(case.image_path.exists() for case in cases)


@pytest.mark.skipif(
    os.getenv("STYLEUS_RUN_CATEGORY_BENCH") != "1",
    reason="Enable STYLEUS_RUN_CATEGORY_BENCH=1 to run the live category regression benchmark.",
)
def test_category_benchmark_pipeline_regression_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_ENABLE_CLASSIFIER", "true")

    summary = benchmark.run_category_benchmark(strategy="pipeline")

    assert summary.total >= 10
    assert summary.correct >= 8
    assert summary.accuracy >= 0.8


@pytest.mark.skipif(
    os.getenv("STYLEUS_RUN_CATEGORY_BENCH") != "1",
    reason="Enable STYLEUS_RUN_CATEGORY_BENCH=1 to run the live category strategy comparison.",
)
def test_category_benchmark_focus_strategy_does_not_outperform_pipeline_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_ENABLE_CLASSIFIER", "true")

    pipeline_summary = benchmark.run_category_benchmark(strategy="pipeline")
    focus_summary = benchmark.run_category_benchmark(strategy="focus")

    assert pipeline_summary.accuracy >= focus_summary.accuracy
