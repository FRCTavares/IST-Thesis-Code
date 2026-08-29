#!/usr/bin/env python3
"""Identity-independent bbox evaluation core for Issue #25.

Builds on the physical-reference schema and the pure Stage A
identity-attribution rule in ``physical_target_reference.py``. This
module owns:

- the timebase join between sparse physical-reference keyframes and a
  controller-facing output stream (bounded interpolation only where the
  frozen v1 rules allow it);
- Stage B numeric localisation metrics (IoU, pixel and reference-height
  centre error), computed unconditionally for every ``identity_target``
  sample -- never gated by a localisation-quality threshold;
- explicit, reconciling duration-bucket accounting;
- duration-weighted aggregation.

It does **not** read ROS bags itself -- see
``evaluate_physical_target_bbox.py`` for the CLI/bag-reading wrapper --
so the entire join/Stage-A/Stage-B/bucket pipeline can be exercised with
synthetic in-memory samples, independent of any real recorded evidence.

Nothing in this module reads or requires the legacy annotation family's
tracker-ID reference field (see ``evaluate_tim_target_bbox_correctness.py``),
or any tracker ID at all, as a physical-identity oracle.
``OutputSample.track_id`` exists purely as passthrough provenance/debug
metadata and is never consulted by any function below.
"""

from __future__ import annotations

import statistics
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from physical_target_reference import (  # noqa: E402
    BBoxXYXY,
    CONTEXT_DISTRACTORS_COMPLETE,
    CONTEXT_TARGET_ONLY,
    IDENTITY_TARGET,
    IDENTITY_UNRESOLVED,
    IDENTITY_WRONG_PERSON,
    STATE_ABSENT,
    STATE_PRESENT_REFERENCE_UNAVAILABLE,
    STATE_PRESENT_SCORED,
    PhysicalReferenceArtifact,
    PhysicalReferenceProvenance,
    PhysicalReferenceSample,
    bbox_iou,
    classify_identity_stage_a,
)

BRINGUP_SOURCE = (
    Path(__file__).resolve().parents[2] / "ros2_ws" / "src" / "thesis_bringup"
)
if str(BRINGUP_SOURCE) not in sys.path:
    sys.path.insert(0, str(BRINGUP_SOURCE))

from thesis_bringup.freshness import (  # noqa: E402
    DEFAULT_MAX_OUTPUT_AGE_S,
    classify_relative_freshness,
)


DEFAULT_STEP_S = 0.05


# --- Output-stream samples ---------------------------------------------------


@dataclass(frozen=True)
class OutputSample:
    """One controller-facing selected-target output reading.

    ``track_id`` is provenance/debug metadata only -- e.g. for a human
    reading a report to see what the tracker happened to call this
    output at the time. No function in this module ever branches on it.
    """

    t_s: float
    track_id: int
    bbox_xyxy: BBoxXYXY | None


def _bbox_is_valid(box: BBoxXYXY | None) -> bool:
    if box is None:
        return False
    x1, y1, x2, y2 = box
    return all(
        v == v and v not in (float("inf"), float("-inf")) for v in box
    ) and x2 > x1 and y2 > y1


def latest_output_at(
    samples: Sequence[OutputSample],
    t_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> OutputSample | None:
    """Latest-preceding-or-equal output at ``t_s``, or None if missing/stale/
    invalid. Reuses the shared freshness/validity semantics already
    established for the rest of the TIM evaluator family."""

    if not samples:
        return None

    times = [s.t_s for s in samples]
    index = bisect_right(times, t_s) - 1
    if index < 0:
        return None

    sample = samples[index]
    freshness = classify_relative_freshness(
        now_s=t_s,
        source_time_s=sample.t_s,
        max_age_s=max_output_age_s,
    )
    if not freshness.fresh:
        return None
    if not _bbox_is_valid(sample.bbox_xyxy):
        return None
    return sample


# --- Physical-reference resolution at an arbitrary time ---------------------


@dataclass(frozen=True)
class ResolvedReference:
    identity_state: str
    identity_context: str | None
    target_bbox_xyxy: BBoxXYXY | None
    distractor_bboxes_xyxy: tuple[BBoxXYXY, ...]


def _lerp_bbox(a: BBoxXYXY, b: BBoxXYXY, fraction: float) -> BBoxXYXY:
    return tuple(a_i + (b_i - a_i) * fraction for a_i, b_i in zip(a, b))  # type: ignore[return-value]


def resolve_reference_at(
    samples: Sequence[PhysicalReferenceSample], t_s: float
) -> ResolvedReference | None:
    """Step-function reference lookup with bounded linear interpolation,
    exactly per docs/issues/p1-10-improve-bbox-evaluation.md section I.

    Returns None outside the artifact's covered span
    ``[samples[0].t_s, samples[-1].t_s)`` -- time outside that span was
    never annotated and must not be silently evaluated.
    """

    if not samples or t_s < samples[0].t_s or t_s >= samples[-1].t_s:
        return None

    times = [s.t_s for s in samples]
    index = bisect_right(times, t_s) - 1
    current = samples[index]
    successor = samples[index + 1]

    target_bbox = current.target_bbox_xyxy
    if (
        successor.interpolate_from_previous
        and current.target_bbox_xyxy is not None
        and successor.target_bbox_xyxy is not None
    ):
        span = successor.t_s - current.t_s
        fraction = (t_s - current.t_s) / span if span > 0.0 else 0.0
        target_bbox = _lerp_bbox(
            current.target_bbox_xyxy, successor.target_bbox_xyxy, fraction
        )

    return ResolvedReference(
        identity_state=current.identity_state,
        identity_context=current.identity_context,
        target_bbox_xyxy=target_bbox,
        distractor_bboxes_xyxy=current.distractor_bboxes_xyxy,
    )


# --- Duration buckets ---------------------------------------------------------


@dataclass
class DurationBuckets:
    """Primary buckets (items 1-6) are mutually exclusive and sum exactly to
    total_evaluated_duration_s. localisation_scored_duration_s and
    target_absent_with_output_duration_s are conditional subset metrics,
    never separately summed into the total -- see reconcile()."""

    correct_target_output_duration_s: float = 0.0
    wrong_person_output_duration_s: float = 0.0
    identity_unresolved_duration_s: float = 0.0
    lost_or_suppressed_duration_s: float = 0.0
    target_absent_duration_s: float = 0.0
    reference_unavailable_duration_s: float = 0.0

    # Conditional/subset metrics (section 11): always <= their parent bucket.
    localisation_scored_duration_s: float = 0.0
    target_absent_with_output_duration_s: float = 0.0

    def primary_total_s(self) -> float:
        return (
            self.correct_target_output_duration_s
            + self.wrong_person_output_duration_s
            + self.identity_unresolved_duration_s
            + self.lost_or_suppressed_duration_s
            + self.target_absent_duration_s
            + self.reference_unavailable_duration_s
        )


@dataclass
class LocalisationAggregate:
    scored_duration_s: float = 0.0
    n_samples: int = 0
    iou_duration_weighted_mean: float | None = None
    iou_min: float | None = None
    iou_max: float | None = None
    iou_median: float | None = None
    iou_p10: float | None = None
    iou_p90: float | None = None
    centre_error_px_duration_weighted_mean: float | None = None
    centre_error_px_median: float | None = None
    centre_error_px_max: float | None = None
    centre_error_ref_h_duration_weighted_mean: float | None = None
    centre_error_ref_h_median: float | None = None
    centre_error_ref_h_max: float | None = None


@dataclass
class EvaluationResult:
    total_evaluated_duration_s: float
    duration_buckets: DurationBuckets
    localisation: LocalisationAggregate
    reconciliation_ok: bool
    reconciliation_residual_s: float


def _centre(box: BBoxXYXY) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def centre_error_px(output_bbox: BBoxXYXY, target_bbox: BBoxXYXY) -> float:
    ox, oy = _centre(output_bbox)
    tx, ty = _centre(target_bbox)
    return ((ox - tx) ** 2 + (oy - ty) ** 2) ** 0.5


def centre_error_ref_h(output_bbox: BBoxXYXY, target_bbox: BBoxXYXY) -> float:
    """Normalised by the *reference* (target) bbox height -- never the
    output bbox height -- per docs/issues/p1-10-improve-bbox-evaluation.md
    section M."""
    _, y1, _, y2 = target_bbox
    ref_h = y2 - y1
    if ref_h <= 0.0:
        return float("inf")
    return centre_error_px(output_bbox, target_bbox) / ref_h


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("cannot take a quantile of an empty sequence")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = q * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def aggregate_localisation(
    samples: Sequence[tuple[float, float, float, float]],
) -> LocalisationAggregate:
    """``samples`` is a sequence of (dt_s, iou, centre_error_px, centre_error_ref_h)
    tuples, one per Stage-B-eligible evaluation tick."""

    if not samples:
        return LocalisationAggregate()

    total_dt = sum(dt for dt, _, _, _ in samples)
    ious = sorted(iou for _, iou, _, _ in samples)
    errs_px = sorted(err for _, _, err, _ in samples)
    errs_ref_h = [err for _, _, _, err in samples if err != float("inf")]
    errs_ref_h_sorted = sorted(errs_ref_h)

    iou_weighted_mean = (
        sum(dt * iou for dt, iou, _, _ in samples) / total_dt if total_dt > 0 else None
    )
    err_px_weighted_mean = (
        sum(dt * err for dt, _, err, _ in samples) / total_dt if total_dt > 0 else None
    )
    err_ref_h_weighted_mean = (
        sum(dt * err for dt, _, _, err in samples if err != float("inf")) / total_dt
        if total_dt > 0 and errs_ref_h
        else None
    )

    return LocalisationAggregate(
        scored_duration_s=total_dt,
        n_samples=len(samples),
        iou_duration_weighted_mean=iou_weighted_mean,
        iou_min=ious[0],
        iou_max=ious[-1],
        iou_median=statistics.median(ious),
        iou_p10=_quantile(ious, 0.10),
        iou_p90=_quantile(ious, 0.90),
        centre_error_px_duration_weighted_mean=err_px_weighted_mean,
        centre_error_px_median=statistics.median(errs_px),
        centre_error_px_max=errs_px[-1],
        centre_error_ref_h_duration_weighted_mean=err_ref_h_weighted_mean,
        centre_error_ref_h_median=(
            statistics.median(errs_ref_h_sorted) if errs_ref_h_sorted else None
        ),
        centre_error_ref_h_max=(
            errs_ref_h_sorted[-1] if errs_ref_h_sorted else None
        ),
    )


def _iter_grid_ticks(start_s: float, end_s: float, step_s: float):
    if step_s <= 0.0:
        raise ValueError("step_s must be positive")
    t = start_s
    while t < end_s:
        dt = min(step_s, end_s - t)
        yield t, dt
        t += step_s


def evaluate_physical_target_bbox(
    *,
    reference: PhysicalReferenceArtifact,
    output_samples: Sequence[OutputSample],
    step_s: float = DEFAULT_STEP_S,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> EvaluationResult:
    samples = reference.samples
    if len(samples) < 2:
        raise ValueError(
            "a physical-reference artifact needs at least two keyframes to "
            "define an evaluable span"
        )

    buckets = DurationBuckets()
    localisation_samples: list[tuple[float, float, float, float]] = []
    total_duration = 0.0

    for t_s, dt in _iter_grid_ticks(samples[0].t_s, samples[-1].t_s, step_s):
        total_duration += dt
        resolved = resolve_reference_at(samples, t_s)
        assert resolved is not None  # guaranteed by the grid bounds above

        if resolved.identity_state == STATE_ABSENT:
            buckets.target_absent_duration_s += dt
            output = latest_output_at(output_samples, t_s, max_output_age_s)
            if output is not None:
                buckets.target_absent_with_output_duration_s += dt
            continue

        if resolved.identity_state == STATE_PRESENT_REFERENCE_UNAVAILABLE:
            buckets.reference_unavailable_duration_s += dt
            continue

        # STATE_PRESENT_SCORED
        output = latest_output_at(output_samples, t_s, max_output_age_s)
        if output is None or output.bbox_xyxy is None:
            buckets.lost_or_suppressed_duration_s += dt
            continue

        assert resolved.target_bbox_xyxy is not None
        assert resolved.identity_context is not None

        outcome = classify_identity_stage_a(
            identity_context=resolved.identity_context,
            target_bbox_xyxy=resolved.target_bbox_xyxy,
            distractor_bboxes_xyxy=resolved.distractor_bboxes_xyxy,
            output_bbox_xyxy=output.bbox_xyxy,
        )

        if outcome == IDENTITY_TARGET:
            buckets.correct_target_output_duration_s += dt
            buckets.localisation_scored_duration_s += dt
            iou = bbox_iou(output.bbox_xyxy, resolved.target_bbox_xyxy)
            err_px = centre_error_px(output.bbox_xyxy, resolved.target_bbox_xyxy)
            err_ref_h = centre_error_ref_h(output.bbox_xyxy, resolved.target_bbox_xyxy)
            localisation_samples.append((dt, iou, err_px, err_ref_h))
        elif outcome == IDENTITY_WRONG_PERSON:
            buckets.wrong_person_output_duration_s += dt
        elif outcome == IDENTITY_UNRESOLVED:
            buckets.identity_unresolved_duration_s += dt
        else:  # pragma: no cover - defensive, classify_identity_stage_a is closed
            raise AssertionError(f"unexpected Stage A outcome: {outcome!r}")

    residual = abs(buckets.primary_total_s() - total_duration)
    return EvaluationResult(
        total_evaluated_duration_s=total_duration,
        duration_buckets=buckets,
        localisation=aggregate_localisation(localisation_samples),
        reconciliation_ok=residual <= 1e-6,
        reconciliation_residual_s=residual,
    )


# --- Report assembly ---------------------------------------------------------


def build_report(
    *,
    result: EvaluationResult,
    stream_name: str,
    provenance: PhysicalReferenceProvenance,
    physical_reference_path: str,
    physical_reference_sha256: str,
    repo_commit: str | None,
    repo_dirty: bool | None,
) -> dict:
    """Deterministic, machine-readable result. Missing provenance is
    recorded as null, never fabricated -- section 19."""

    buckets = result.duration_buckets
    loc = result.localisation

    return {
        "schema_version": provenance.schema_version,
        "contract_version": provenance.contract_version,
        "evaluator": "physical_target_bbox_evaluation",
        "evaluator_mode": "physical_reference_v1",
        "stream": stream_name,
        "source_bag_name": provenance.source_bag_name,
        "source_bag_path": provenance.source_bag_path,
        "source_image_topic": provenance.source_image_topic,
        "source_width": provenance.source_width,
        "source_height": provenance.source_height,
        "coordinate_convention": provenance.coordinate_convention,
        "coordinate_convention_evidence": provenance.coordinate_convention_evidence,
        "selected_physical_target_label": provenance.selected_physical_target_label,
        "physical_reference_path": physical_reference_path,
        "physical_reference_sha256": physical_reference_sha256,
        "repo_commit": repo_commit,
        "repo_dirty": repo_dirty,
        "total_evaluated_duration_s": result.total_evaluated_duration_s,
        "duration_buckets": {
            "correct_target_output_duration_s": buckets.correct_target_output_duration_s,
            "wrong_person_output_duration_s": buckets.wrong_person_output_duration_s,
            "identity_unresolved_duration_s": buckets.identity_unresolved_duration_s,
            "lost_or_suppressed_duration_s": buckets.lost_or_suppressed_duration_s,
            "target_absent_duration_s": buckets.target_absent_duration_s,
            "reference_unavailable_duration_s": buckets.reference_unavailable_duration_s,
            "localisation_scored_duration_s": buckets.localisation_scored_duration_s,
            "target_absent_with_output_duration_s": buckets.target_absent_with_output_duration_s,
        },
        "localisation": {
            "scored_duration_s": loc.scored_duration_s,
            "n_samples": loc.n_samples,
            "iou_duration_weighted_mean": loc.iou_duration_weighted_mean,
            "iou_min": loc.iou_min,
            "iou_max": loc.iou_max,
            "iou_median": loc.iou_median,
            "iou_p10": loc.iou_p10,
            "iou_p90": loc.iou_p90,
            "centre_error_px_duration_weighted_mean": loc.centre_error_px_duration_weighted_mean,
            "centre_error_px_median": loc.centre_error_px_median,
            "centre_error_px_max": loc.centre_error_px_max,
            "centre_error_ref_h_duration_weighted_mean": loc.centre_error_ref_h_duration_weighted_mean,
            "centre_error_ref_h_median": loc.centre_error_ref_h_median,
            "centre_error_ref_h_max": loc.centre_error_ref_h_max,
        },
        "reconciliation": {
            "ok": result.reconciliation_ok,
            "residual_s": result.reconciliation_residual_s,
            "primary_bucket_total_s": buckets.primary_total_s(),
        },
    }
