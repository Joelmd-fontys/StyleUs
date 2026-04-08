"""Build evaluation slices and confusion reports from upload-review feedback."""

# mypy: disable-error-code=import-untyped

from __future__ import annotations

import argparse
import datetime
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai import pipeline
from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.models.ai_feedback import AIReviewFeedbackEvent
from app.models.wardrobe import WardrobeItem
from app.utils import storage as storage_utils

_DEFAULT_OUTPUT_DIR = Path("./media/review_feedback_eval")
_CONFIDENCE_BANDS: tuple[tuple[float, str], ...] = (
    (0.75, ">=0.75"),
    (0.65, "0.65-0.74"),
    (0.55, "0.55-0.64"),
    (0.45, "0.45-0.54"),
)
_THRESHOLD_CANDIDATES: tuple[float, ...] = (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75)


@dataclass(frozen=True, slots=True)
class ReviewFeedbackCase:
    fixture_id: str
    image_path: str
    expected_category: str
    historical_predicted_category: str | None
    historical_prediction_confidence: float | None
    accepted_directly: bool
    item_id: str | None = None
    source: str = "upload_review"
    created_at: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewFeedbackResult:
    fixture_id: str
    image_path: str
    expected_category: str
    historical_predicted_category: str | None
    historical_prediction_confidence: float | None
    historical_correct: bool | None
    historical_confidence_band: str
    accepted_directly: bool
    current_predicted_category: str | None
    current_prediction_confidence: float | None
    current_correct: bool
    current_confidence_band: str


@dataclass(frozen=True, slots=True)
class ConfidenceBandSummary:
    band: str
    total: int
    correct: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class ConfusionCluster:
    predicted_category: str
    expected_category: str
    count: int
    average_confidence: float | None


@dataclass(frozen=True, slots=True)
class ThresholdRecommendation:
    category: str
    threshold: float
    precision: float
    coverage: float
    sample_size: int


@dataclass(frozen=True, slots=True)
class ReviewFeedbackReport:
    total_cases: int
    historical_accuracy: float | None
    current_accuracy: float
    historical_bands: tuple[ConfidenceBandSummary, ...]
    current_bands: tuple[ConfidenceBandSummary, ...]
    historical_confusion: tuple[ConfusionCluster, ...]
    current_confusion: tuple[ConfusionCluster, ...]
    recommended_category_thresholds: tuple[ThresholdRecommendation, ...]
    results: tuple[ReviewFeedbackResult, ...]


def _confidence_band(confidence: float | None) -> str:
    if confidence is None:
        return "unknown"
    for minimum, label in _CONFIDENCE_BANDS:
        if confidence >= minimum:
            return label
    return "<0.45"


def _resolve_manifest_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def load_review_feedback_cases(manifest_path: str | Path) -> list[ReviewFeedbackCase]:
    manifest = _resolve_manifest_path(manifest_path)
    payload = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    base_dir = manifest.parent
    cases: list[ReviewFeedbackCase] = []
    for index, entry in enumerate(payload.get("cases", []), start=1):
        image_path = (base_dir / str(entry["image"])).resolve()
        confidence = entry.get("historical_prediction_confidence")
        cases.append(
            ReviewFeedbackCase(
                fixture_id=str(entry.get("id") or f"feedback-{index}"),
                image_path=str(image_path),
                expected_category=str(entry["expected_category"]),
                historical_predicted_category=entry.get("historical_predicted_category"),
                historical_prediction_confidence=(
                    float(confidence) if confidence is not None else None
                ),
                accepted_directly=bool(entry.get("accepted_directly", False)),
                item_id=entry.get("item_id"),
                source=str(entry.get("source") or "upload_review"),
                created_at=entry.get("created_at"),
                notes=entry.get("notes"),
            )
        )
    if not cases:
        raise ValueError(f"No feedback cases found in {manifest}")
    return cases


def _latest_feedback_events(
    db: Session,
    *,
    limit: int,
    include_accepted: bool,
) -> list[AIReviewFeedbackEvent]:
    stmt = (
        select(AIReviewFeedbackEvent)
        .options(selectinload(AIReviewFeedbackEvent.item))
        .where(AIReviewFeedbackEvent.source == "upload_review")
        .order_by(AIReviewFeedbackEvent.created_at.desc(), AIReviewFeedbackEvent.id.desc())
    )
    events = db.execute(stmt).scalars().all()
    latest_by_item: dict[str, AIReviewFeedbackEvent] = {}
    for event in events:
        item = event.item
        if item is None:
            continue
        key = str(item.id)
        if key in latest_by_item:
            continue
        if not include_accepted and event.accepted_directly:
            continue
        latest_by_item[key] = event
        if len(latest_by_item) >= limit:
            break
    return list(latest_by_item.values())


def _preferred_item_key(item: WardrobeItem) -> str | None:
    if item.image_medium_object_path:
        return item.image_medium_object_path.lstrip("/")
    if item.image_object_path:
        return item.image_object_path.lstrip("/")
    return None


def _suffix_for_path(path: str | None, *, fallback: str = ".jpg") -> str:
    suffix = Path(path or "").suffix.lower()
    return suffix or fallback


def _suffix_for_content_type(content_type: str | None) -> str | None:
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/jpeg":
        return ".jpg"
    return None


def _copy_local_image(image_url: str, destination: Path, *, app_settings: Settings) -> bool:
    parsed = urlparse(image_url)
    candidates = [
        Path(parsed.path or image_url),
        app_settings.media_root_path / (parsed.path or image_url).lstrip("/"),
    ]
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.exists() and resolved.is_file():
            destination.write_bytes(resolved.read_bytes())
            return True
    return False


def _materialize_item_image(
    item: WardrobeItem,
    destination_dir: Path,
    *,
    app_settings: Settings,
) -> Path | None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    storage_key = _preferred_item_key(item)
    if storage_key:
        downloaded = storage_utils.get_storage_adapter(app_settings).download_object(storage_key)
        suffix = _suffix_for_content_type(downloaded.content_type) or _suffix_for_path(storage_key)
        destination = destination_dir / f"{item.id}{suffix}"
        destination.write_bytes(downloaded.data)
        return destination
    if item.image_url:
        destination = destination_dir / f"{item.id}{_suffix_for_path(item.image_url)}"
        if _copy_local_image(item.image_url, destination, app_settings=app_settings):
            return destination
    return None


def export_review_feedback_eval_slice(
    db: Session,
    *,
    output_dir: str | Path = _DEFAULT_OUTPUT_DIR,
    limit: int = 50,
    include_accepted: bool = True,
    app_settings: Settings = settings,
) -> Path:
    output_root = Path(output_dir).expanduser().resolve()
    images_dir = output_root / "images"
    events = _latest_feedback_events(db, limit=limit, include_accepted=include_accepted)

    cases: list[dict[str, Any]] = []
    for event in events:
        item = event.item
        if item is None:
            continue
        exported_image = _materialize_item_image(item, images_dir, app_settings=app_settings)
        if exported_image is None:
            continue
        cases.append(
            {
                "id": f"feedback-{event.id}",
                "image": str(exported_image.relative_to(output_root)),
                "expected_category": event.corrected_category,
                "historical_predicted_category": event.predicted_category,
                "historical_prediction_confidence": event.prediction_confidence,
                "accepted_directly": event.accepted_directly,
                "item_id": str(item.id),
                "source": event.source,
                "created_at": event.created_at.isoformat(),
                "notes": (
                    "accepted directly"
                    if event.accepted_directly
                    else "category changed during upload review"
                ),
            }
        )

    if not cases:
        raise ValueError("No review feedback cases with accessible images were exported")

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "generated_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                "exported_case_count": len(cases),
                "cases": cases,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return manifest_path


def _summarize_bands(
    results: Iterable[ReviewFeedbackResult],
    *,
    use_current: bool,
) -> tuple[ConfidenceBandSummary, ...]:
    band_totals: dict[str, int] = defaultdict(int)
    band_correct: dict[str, int] = defaultdict(int)
    order = ["<0.45", "0.45-0.54", "0.55-0.64", "0.65-0.74", ">=0.75", "unknown"]
    for result in results:
        band = result.current_confidence_band if use_current else result.historical_confidence_band
        is_correct = result.current_correct if use_current else bool(result.historical_correct)
        band_totals[band] += 1
        if is_correct:
            band_correct[band] += 1
    summaries: list[ConfidenceBandSummary] = []
    for band in order:
        total = band_totals.get(band, 0)
        if total == 0:
            continue
        correct = band_correct.get(band, 0)
        summaries.append(
            ConfidenceBandSummary(
                band=band,
                total=total,
                correct=correct,
                accuracy=correct / total,
            )
        )
    return tuple(summaries)


def _summarize_confusion(
    results: Iterable[ReviewFeedbackResult],
    *,
    use_current: bool,
) -> tuple[ConfusionCluster, ...]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for result in results:
        predicted = (
            result.current_predicted_category
            if use_current
            else result.historical_predicted_category
        )
        confidence = (
            result.current_prediction_confidence
            if use_current
            else result.historical_prediction_confidence
        )
        if not predicted or predicted == result.expected_category:
            continue
        grouped[(predicted, result.expected_category)].append(confidence or 0.0)

    clusters = [
        ConfusionCluster(
            predicted_category=predicted,
            expected_category=expected,
            count=len(confidences),
            average_confidence=(
                sum(confidences) / len(confidences) if confidences else None
            ),
        )
        for (predicted, expected), confidences in grouped.items()
    ]
    return tuple(
        sorted(
            clusters,
            key=lambda cluster: (
                -cluster.count,
                -(cluster.average_confidence or 0.0),
                cluster.predicted_category,
                cluster.expected_category,
            ),
        )
    )


def recommend_category_thresholds(
    cases: Sequence[ReviewFeedbackCase],
    *,
    current_threshold: float,
    target_precision: float = 0.85,
    minimum_samples: int = 3,
) -> tuple[ThresholdRecommendation, ...]:
    grouped: dict[str, list[ReviewFeedbackCase]] = defaultdict(list)
    for case in cases:
        if case.historical_predicted_category and case.historical_prediction_confidence is not None:
            grouped[case.historical_predicted_category].append(case)

    recommendations: list[ThresholdRecommendation] = []
    for category, entries in grouped.items():
        if len(entries) < minimum_samples:
            continue
        baseline_entries = [
            case
            for case in entries
            if (case.historical_prediction_confidence or 0.0) >= current_threshold
        ]
        if not baseline_entries:
            continue
        baseline_correct = sum(
            1
            for case in baseline_entries
            if case.historical_predicted_category == case.expected_category
        )
        baseline_precision = baseline_correct / len(baseline_entries)
        if baseline_precision >= target_precision:
            continue

        candidate_thresholds = sorted(
            {
                round(current_threshold, 2),
                *(
                    round(
                        min(1.0, (case.historical_prediction_confidence or 0.0) + 0.01),
                        2,
                    )
                    for case in entries
                ),
            }
        )
        for threshold in candidate_thresholds:
            covered = [
                case
                for case in entries
                if (case.historical_prediction_confidence or 0.0) >= threshold
            ]
            if not covered:
                continue
            correct = sum(
                1
                for case in covered
                if case.historical_predicted_category == case.expected_category
            )
            precision = correct / len(covered)
            if precision < target_precision:
                continue
            recommendations.append(
                ThresholdRecommendation(
                    category=category,
                    threshold=threshold,
                    precision=precision,
                    coverage=len(covered) / len(entries),
                    sample_size=len(entries),
                )
            )
            break

    return tuple(
        sorted(
            recommendations,
            key=lambda item: (-item.sample_size, -item.threshold, item.category),
        )
    )


def build_review_feedback_report(
    cases: Sequence[ReviewFeedbackCase],
    *,
    target_precision: float = 0.85,
) -> ReviewFeedbackReport:
    results: list[ReviewFeedbackResult] = []
    historical_correct_count = 0
    historical_total = 0
    current_correct_count = 0

    for case in cases:
        rerun = pipeline.run(Path(case.image_path))
        current_predicted = str(rerun.clip.get("category") or "") or None
        current_confidence_raw = rerun.clip.get("category_confidence")
        current_confidence = (
            float(current_confidence_raw) if current_confidence_raw is not None else None
        )
        current_correct = current_predicted == case.expected_category
        current_correct_count += int(current_correct)

        historical_correct: bool | None = None
        if case.historical_predicted_category is not None:
            historical_correct = case.historical_predicted_category == case.expected_category
            historical_total += 1
            historical_correct_count += int(historical_correct)

        results.append(
            ReviewFeedbackResult(
                fixture_id=case.fixture_id,
                image_path=case.image_path,
                expected_category=case.expected_category,
                historical_predicted_category=case.historical_predicted_category,
                historical_prediction_confidence=case.historical_prediction_confidence,
                historical_correct=historical_correct,
                historical_confidence_band=_confidence_band(
                    case.historical_prediction_confidence
                ),
                accepted_directly=case.accepted_directly,
                current_predicted_category=current_predicted,
                current_prediction_confidence=current_confidence,
                current_correct=current_correct,
                current_confidence_band=_confidence_band(current_confidence),
            )
        )

    historical_accuracy = (
        historical_correct_count / historical_total if historical_total else None
    )
    current_accuracy = current_correct_count / len(results) if results else 0.0

    return ReviewFeedbackReport(
        total_cases=len(results),
        historical_accuracy=historical_accuracy,
        current_accuracy=current_accuracy,
        historical_bands=_summarize_bands(results, use_current=False),
        current_bands=_summarize_bands(results, use_current=True),
        historical_confusion=_summarize_confusion(results, use_current=False),
        current_confusion=_summarize_confusion(results, use_current=True),
        recommended_category_thresholds=recommend_category_thresholds(
            cases,
            current_threshold=settings.ai_confidence_threshold,
            target_precision=target_precision,
        ),
        results=tuple(results),
    )


def report_to_dict(report: ReviewFeedbackReport) -> dict[str, Any]:
    return {
        "total_cases": report.total_cases,
        "historical_accuracy": report.historical_accuracy,
        "current_accuracy": report.current_accuracy,
        "historical_bands": [asdict(item) for item in report.historical_bands],
        "current_bands": [asdict(item) for item in report.current_bands],
        "historical_confusion": [asdict(item) for item in report.historical_confusion],
        "current_confusion": [asdict(item) for item in report.current_confusion],
        "recommended_category_thresholds": [
            asdict(item) for item in report.recommended_category_thresholds
        ],
        "results": [asdict(item) for item in report.results],
    }


def _format_band_summaries(label: str, summaries: Sequence[ConfidenceBandSummary]) -> list[str]:
    lines = [label]
    if not summaries:
        lines.append("  none")
        return lines
    for summary in summaries:
        lines.append(
            "  "
            f"{summary.band}: {summary.correct}/{summary.total} "
            f"({summary.accuracy:.0%})"
        )
    return lines


def _format_clusters(label: str, clusters: Sequence[ConfusionCluster]) -> list[str]:
    lines = [label]
    if not clusters:
        lines.append("  none")
        return lines
    for cluster in clusters[:5]:
        confidence = (
            f"{cluster.average_confidence:.3f}"
            if cluster.average_confidence is not None
            else "n/a"
        )
        lines.append(
            "  "
            f"{cluster.predicted_category} -> {cluster.expected_category}: "
            f"{cluster.count} (avg confidence {confidence})"
        )
    return lines


def format_review_feedback_report(report: ReviewFeedbackReport) -> str:
    lines = [
        f"cases: {report.total_cases}",
        (
            f"historical accuracy: {report.historical_accuracy:.0%}"
            if report.historical_accuracy is not None
            else "historical accuracy: n/a"
        ),
        f"current accuracy: {report.current_accuracy:.0%}",
    ]
    lines.extend(_format_band_summaries("historical confidence bands:", report.historical_bands))
    lines.extend(_format_band_summaries("current confidence bands:", report.current_bands))
    lines.extend(_format_clusters("historical confusion:", report.historical_confusion))
    lines.extend(_format_clusters("current confusion:", report.current_confusion))
    recommendations = report.recommended_category_thresholds
    if not recommendations:
        lines.append("recommended category threshold: no threshold met the target precision")
    for recommendation in recommendations:
        lines.append(
            "recommended category threshold: "
            f"{recommendation.category} -> "
            f"{recommendation.threshold:.2f} "
            f"(precision {recommendation.precision:.0%}, "
            f"coverage {recommendation.coverage:.0%}, n={recommendation.sample_size})"
        )
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and report on upload-review feedback data")
    parser.add_argument(
        "--manifest",
        help="Existing manifest to analyze instead of exporting a fresh slice from the database",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help="Directory used for exported manifests and copied images",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of latest feedback events to export",
    )
    parser.add_argument(
        "--corrections-only",
        action="store_true",
        help="Exclude directly accepted predictions when exporting from the database",
    )
    parser.add_argument(
        "--target-precision",
        type=float,
        default=0.85,
        help="Precision target used for category-threshold recommendation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.manifest:
        manifest_path = _resolve_manifest_path(args.manifest)
    else:
        with SessionLocal() as session:
            manifest_path = export_review_feedback_eval_slice(
                session,
                output_dir=args.output_dir,
                limit=args.limit,
                include_accepted=not args.corrections_only,
            )

    cases = load_review_feedback_cases(manifest_path)
    report = build_review_feedback_report(
        cases,
        target_precision=args.target_precision,
    )

    if args.json:
        print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(format_review_feedback_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
