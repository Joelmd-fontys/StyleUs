"""Offline category benchmark helpers for upload-style fixture images."""

# mypy: disable-error-code=import-untyped

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

import yaml  # type: ignore[import-untyped]

from app.ai import pipeline
from app.ai.clip_heads import ClipPrediction

CategoryStrategy = Literal["heuristic", "pipeline", "full", "focus", "masked"]

_DEFAULT_FIXTURE_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "upload_category_cases.yaml"
)


@dataclass(frozen=True, slots=True)
class CategoryBenchmarkCase:
    fixture_id: str
    image_path: Path
    expected_category: str
    expected_subcategory: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class CategoryBenchmarkResult:
    fixture_id: str
    image_path: str
    expected_category: str
    predicted_category: str | None
    category_confidence: float | None
    correct: bool
    strategy: CategoryStrategy
    expected_subcategory: str | None = None
    predicted_subcategory: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class CategoryBenchmarkSummary:
    strategy: CategoryStrategy
    correct: int
    total: int
    accuracy: float
    results: tuple[CategoryBenchmarkResult, ...]


def _resolve_manifest_path(manifest_path: str | Path | None = None) -> Path:
    if manifest_path is None:
        return _DEFAULT_FIXTURE_MANIFEST
    return Path(manifest_path).expanduser().resolve()


def load_category_cases(manifest_path: str | Path | None = None) -> list[CategoryBenchmarkCase]:
    manifest = _resolve_manifest_path(manifest_path)
    payload = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    base_dir = manifest.parent
    cases: list[CategoryBenchmarkCase] = []
    for index, entry in enumerate(payload.get("cases", []), start=1):
        image_path = (base_dir / entry["image"]).resolve()
        cases.append(
            CategoryBenchmarkCase(
                fixture_id=str(entry.get("id") or f"fixture-{index}"),
                image_path=image_path,
                expected_category=str(entry["expected_category"]),
                expected_subcategory=entry.get("expected_subcategory"),
                notes=entry.get("notes"),
            )
        )
    if not cases:
        raise ValueError(f"No benchmark cases found in {manifest}")
    return cases


def predict_category_for_image(
    strategy: CategoryStrategy,
    image_path: Path,
) -> ClipPrediction:
    if strategy == "pipeline":
        result = pipeline.run(image_path)
        return result.clip

    source_image = pipeline._load_source_image(image_path)
    focus = pipeline._prepare_focus_image(source_image)
    color_result = pipeline._get_color_result(focus)

    if strategy == "heuristic":
        return pipeline._heuristic_prediction(image_path, color_result)

    predictor = pipeline._get_predictor()
    if strategy == "full":
        embedding = predictor.embed_pil_image(source_image)
    elif strategy == "focus":
        embedding = predictor.embed_pil_image(focus.image)
    elif strategy == "masked":
        embedding = predictor.embed_pil_image(focus.masked_image)
    else:  # pragma: no cover - argparse and callers restrict the values
        raise ValueError(f"Unsupported category strategy: {strategy}")

    clip_result = cast(ClipPrediction, predictor.predict(embedding))
    pipeline._apply_subcategory_selection(
        clip_result,
        image_path=image_path,
        colors=color_result,
    )
    return clip_result


def run_category_benchmark(
    *,
    strategy: CategoryStrategy,
    manifest_path: str | Path | None = None,
) -> CategoryBenchmarkSummary:
    cases = load_category_cases(manifest_path)
    results: list[CategoryBenchmarkResult] = []
    correct = 0
    for case in cases:
        clip = predict_category_for_image(strategy, case.image_path)
        predicted_category = clip.get("category")
        predicted_subcategory = clip.get("subcategory")
        category_confidence = clip.get("category_confidence")
        is_correct = predicted_category == case.expected_category
        if is_correct:
            correct += 1
        results.append(
            CategoryBenchmarkResult(
                fixture_id=case.fixture_id,
                image_path=str(case.image_path),
                expected_category=case.expected_category,
                predicted_category=str(predicted_category) if predicted_category else None,
                category_confidence=(
                    float(cast(float, category_confidence))
                    if category_confidence is not None
                    else None
                ),
                correct=is_correct,
                strategy=strategy,
                expected_subcategory=case.expected_subcategory,
                predicted_subcategory=str(predicted_subcategory) if predicted_subcategory else None,
                notes=case.notes,
            )
        )

    total = len(results)
    accuracy = (correct / total) if total else 0.0
    return CategoryBenchmarkSummary(
        strategy=strategy,
        correct=correct,
        total=total,
        accuracy=accuracy,
        results=tuple(results),
    )


def run_multiple_category_benchmarks(
    *,
    strategies: Iterable[CategoryStrategy],
    manifest_path: str | Path | None = None,
) -> list[CategoryBenchmarkSummary]:
    return [
        run_category_benchmark(strategy=strategy, manifest_path=manifest_path)
        for strategy in strategies
    ]


def summary_to_dict(summary: CategoryBenchmarkSummary) -> dict[str, object]:
    return {
        "strategy": summary.strategy,
        "correct": summary.correct,
        "total": summary.total,
        "accuracy": round(summary.accuracy, 4),
        "results": [asdict(result) for result in summary.results],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline upload category benchmark")
    parser.add_argument(
        "--manifest",
        default=str(_DEFAULT_FIXTURE_MANIFEST),
        help="Path to the upload category fixture manifest",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=["heuristic", "pipeline", "full", "focus", "masked"],
        default=["heuristic", "pipeline", "full", "focus"],
        help="Category strategies to evaluate",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the benchmark report as JSON",
    )
    return parser.parse_args()


def _format_human_summary(summary: CategoryBenchmarkSummary) -> str:
    lines = [
        f"{summary.strategy}: {summary.correct}/{summary.total} ({summary.accuracy:.0%})",
    ]
    for result in summary.results:
        status = "ok" if result.correct else "miss"
        confidence = (
            f"{result.category_confidence:.3f}"
            if result.category_confidence is not None
            else "n/a"
        )
        lines.append(
            "  "
            f"{status} {Path(result.image_path).name}: "
            f"expected={result.expected_category} predicted={result.predicted_category} "
            f"confidence={confidence}"
        )
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    summaries = run_multiple_category_benchmarks(
        strategies=cast(Sequence[CategoryStrategy], args.strategies),
        manifest_path=args.manifest,
    )

    if args.json:
        print(
            json.dumps(
                [summary_to_dict(summary) for summary in summaries],
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    for index, summary in enumerate(summaries):
        if index:
            print()
        print(_format_human_summary(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
