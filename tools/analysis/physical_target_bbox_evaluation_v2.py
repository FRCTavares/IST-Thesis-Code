#!/usr/bin/env python3
"""Interval-aware bbox evaluation core for ``tim_physical_target_bbox_v2``
(Issue #25, M2-v2).

Full semantics are frozen in
``docs/issues/p1-10-physical-reference-v2-contract.md`` (sections H-K).
This module is a sibling of, not a replacement for,
``physical_target_bbox_evaluation.py`` (the v1 evaluation core, which is
untouched and remains valid on its own terms for
``tim_physical_target_bbox_v1`` artifacts).

The one thing this module exists to fix, precisely: v1's
``resolve_reference_at`` step-holds the previous keyframe's target and
distractor geometry across any gap where interpolation was not both
claimed and legal, and the v1 evaluator then feeds that stale geometry to
Stage A/B as if it were contemporaneous ground truth. This module never
does that. Reference resolution here is **interval-based**, not a
step-hold lookup at an arbitrary instant:

1. The declared ``evaluation_window`` is partitioned into atomic
   intervals at every physical-reference sample timestamp, the window's
   own start/end, and a regular grid (``step_s``) used only to give
   controller-output freshness changes reasonable resolution within long
   intervals -- never used to manufacture reference validity.
2. Each atomic interval is classified as *exactly one* of: before the
   first sample or after a present_scored last sample (uncovered --
   ``reference_gap``), a propagated ``absent``/``present_reference_unavailable``
   state, or a legally interpolated ``present_scored`` span. An isolated
   keyframe with no legal interpolation into or out of it therefore
   contributes **zero** duration of valid reference on its own -- it is a
   point measurement, not an interval.
3. Interpolation, when legal, is per physical person: the target
   linearly, and (for ``distractors_complete``) each distractor matched
   by its ``person_ref`` -- never by list position, drawing order, or
   proximity. Legality itself (exact ``person_ref`` set match between the
   two endpoints) is enforced by
   ``physical_target_reference_v2.validate_physical_reference`` before an
   artifact ever reaches this module; this module trusts, but does not
   re-derive, that guarantee -- exactly mirroring v1's own trust model
   (v1's evaluator does not re-validate its input either).

Stage A (``classify_identity_stage_a``) and Stage B (``bbox_iou``,
``centre_error_px``, ``centre_error_ref_h``) are imported unchanged from
v1 -- neither requires any v2-specific change, since neither has ever
needed to know how a resolved bbox came to be resolved, only what it is
at the instant being scored. Output-stream primitives
(``OutputSample``, ``latest_output_at``, localisation aggregation) are
likewise imported from v1's evaluator core rather than duplicated -- they
are schema-version-independent.

Nothing in this module reads or requires any tracker ID as a physical-
identity oracle. ``OutputSample.track_id`` (imported from v1) exists
purely as passthrough provenance/debug metadata and is never consulted
here, exactly as in v1.
"""

from __future__ import annotations

import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from physical_target_reference_v2 import (  # noqa: E402
    BBoxXYXY,
    CONTEXT_DISTRACTORS_COMPLETE,
    STATE_ABSENT,
    STATE_PRESENT_REFERENCE_UNAVAILABLE,
    STATE_PRESENT_SCORED,
    DistractorEntry,
    PhysicalReferenceArtifact,
    PhysicalReferenceProvenance,
    PhysicalReferenceSample,
    bbox_iou,
    classify_identity_stage_a,
)
from physical_target_reference import (  # noqa: E402
    IDENTITY_TARGET,
    IDENTITY_UNRESOLVED,
    IDENTITY_WRONG_PERSON,
)
from physical_target_bbox_evaluation import (  # noqa: E402
    DEFAULT_STEP_S,
    LocalisationAggregate,
    OutputSample,
    _lerp_bbox,
    aggregate_localisation,
    centre_error_px,
    centre_error_ref_h,
    latest_output_at,
)

BRINGUP_SOURCE = (
    Path(__file__).resolve().parents[2] / "ros2_ws" / "src" / "thesis_bringup"
)
if str(BRINGUP_SOURCE) not in sys.path:
    sys.path.insert(0, str(BRINGUP_SOURCE))

from thesis_bringup.freshness import DEFAULT_MAX_OUTPUT_AGE_S  # noqa: E402


# --- Interval-condition classification ---------------------------------------
#
# Exactly one of these four applies to any atomic interval. There is no
# fifth "step-held geometry" condition -- that is the behaviour this
# module exists to eliminate.

REF_GAP = "reference_gap"
REF_TARGET_ABSENT = "target_absent"
REF_UNAVAILABLE = "reference_unavailable"
REF_COVERED = "reference_covered"


@dataclass(frozen=True)
class ResolvedReferenceV2:
    """The reference condition for one atomic interval. ``interpolated``
    is always True when ``condition == REF_COVERED`` -- there is no other
    way for this module to produce covered geometry (contract section H:
    an isolated keyframe is a point, never itself a positive-duration
    interval)."""

    condition: str
    identity_context: str | None = None
    target_bbox_xyxy: BBoxXYXY | None = None
    distractors: tuple[DistractorEntry, ...] = field(default_factory=tuple)
    interpolated: bool = False


def resolve_reference_interval(
    samples: Sequence[PhysicalReferenceSample], t0: float
) -> ResolvedReferenceV2:
    """Classify the atomic half-open interval starting at ``t0`` (i.e.
    ``[t0, next_breakpoint)``) against the frozen v2 contract.

    Never step-holds present_scored geometry. Caller guarantees ``samples``
    is non-empty, already validated (``validate_physical_reference``), and
    that ``t0`` lies inside the declared ``evaluation_window``.
    """

    if t0 < samples[0].t_s:
        # Before the first sample: no backward inference (contract, M2-v2
        # brief item 5).
        return ResolvedReferenceV2(condition=REF_GAP)

    if t0 >= samples[-1].t_s:
        # At or after the last sample: no forward extrapolation (item 7).
        last = samples[-1]
        if last.identity_state == STATE_ABSENT:
            return ResolvedReferenceV2(condition=REF_TARGET_ABSENT)
        if last.identity_state == STATE_PRESENT_REFERENCE_UNAVAILABLE:
            return ResolvedReferenceV2(condition=REF_UNAVAILABLE)
        return ResolvedReferenceV2(condition=REF_GAP)  # present_scored, no hold

    times = [s.t_s for s in samples]
    index = bisect_right(times, t0) - 1
    current = samples[index]
    successor = samples[index + 1]

    if current.identity_state == STATE_ABSENT:
        # Legitimate state-label propagation (contract section G) -- not a
        # geometry hold, since no bbox is attached to this state at all.
        return ResolvedReferenceV2(condition=REF_TARGET_ABSENT)

    if current.identity_state == STATE_PRESENT_REFERENCE_UNAVAILABLE:
        return ResolvedReferenceV2(condition=REF_UNAVAILABLE)

    # STATE_PRESENT_SCORED: valid geometry exists for this interval only if
    # the successor claims (and the pre-validated artifact therefore
    # guarantees is legal) interpolation from this exact predecessor.
    # Never a step-hold of `current`'s own bbox.
    if not successor.interpolate_from_previous:
        return ResolvedReferenceV2(condition=REF_GAP)

    span = successor.t_s - current.t_s
    fraction = (t0 - current.t_s) / span if span > 0.0 else 0.0

    assert current.target_bbox_xyxy is not None
    assert successor.target_bbox_xyxy is not None
    target_bbox = _lerp_bbox(
        current.target_bbox_xyxy, successor.target_bbox_xyxy, fraction
    )

    if current.identity_context == CONTEXT_DISTRACTORS_COMPLETE:
        # Interpolate strictly by person_ref, never by list position --
        # validate_physical_reference already guarantees an exact set
        # match between current and successor for this to be legal, so
        # every key in current_by_ref also exists in successor_by_ref.
        current_by_ref = {d.person_ref: d.bbox_xyxy for d in current.distractors}
        successor_by_ref = {d.person_ref: d.bbox_xyxy for d in successor.distractors}
        distractors = tuple(
            DistractorEntry(
                person_ref=ref,
                bbox_xyxy=_lerp_bbox(
                    current_by_ref[ref], successor_by_ref[ref], fraction
                ),
            )
            for ref in sorted(current_by_ref)
        )
    else:
        distractors = ()

    return ResolvedReferenceV2(
        condition=REF_COVERED,
        identity_context=current.identity_context,
        target_bbox_xyxy=target_bbox,
        distractors=distractors,
        interpolated=True,
    )


# --- Interval partitioning ----------------------------------------------------


def _build_breakpoints(
    window_start_s: float,
    window_end_s: float,
    sample_times: Sequence[float],
    step_s: float,
) -> list[float]:
    """Every atomic interval boundary: the window's own start/end, every
    physical-reference sample timestamp (so a reference-semantic
    transition can never be split across, or hidden inside, one interval),
    and a regular grid at ``step_s`` spacing (so controller-output
    freshness changes are given reasonable resolution within otherwise
    long intervals -- this is the only role the grid plays; it never
    grants reference validity by itself)."""

    if step_s <= 0.0:
        raise ValueError("step_s must be positive")

    points: set[float] = {window_start_s, window_end_s}
    points.update(t for t in sample_times if window_start_s <= t < window_end_s)

    t = window_start_s
    while t < window_end_s:
        points.add(t)
        t += step_s

    return sorted(points)


# --- Duration buckets ---------------------------------------------------------


@dataclass
class DurationBucketsV2:
    """Seven primary buckets (contract section J) are mutually exclusive
    and sum exactly to the declared evaluation_window's duration. Every
    other field here is a conditional/subset metric, never separately
    summed into the total -- see reconcile()."""

    correct_target_output_duration_s: float = 0.0
    wrong_person_output_duration_s: float = 0.0
    identity_unresolved_duration_s: float = 0.0
    lost_or_suppressed_duration_s: float = 0.0
    target_absent_duration_s: float = 0.0
    reference_unavailable_duration_s: float = 0.0
    reference_gap_duration_s: float = 0.0

    # Conditional/subset metrics: always <= their parent bucket(s).
    localisation_scored_duration_s: float = 0.0
    target_absent_with_output_duration_s: float = 0.0
    reference_gap_with_output_duration_s: float = 0.0
    interpolated_reference_duration_s: float = 0.0

    def primary_total_s(self) -> float:
        return (
            self.correct_target_output_duration_s
            + self.wrong_person_output_duration_s
            + self.identity_unresolved_duration_s
            + self.lost_or_suppressed_duration_s
            + self.target_absent_duration_s
            + self.reference_unavailable_duration_s
            + self.reference_gap_duration_s
        )

    def reference_covered_duration_s(self) -> float:
        """Contract section J: duration where physical geometry was valid
        for Stage A/B evaluation, whether or not a fresh output existed at
        that instant."""
        return (
            self.correct_target_output_duration_s
            + self.wrong_person_output_duration_s
            + self.identity_unresolved_duration_s
            + self.lost_or_suppressed_duration_s
        )

    def reference_coverage_fraction(self, total_duration_s: float) -> float | None:
        if total_duration_s <= 0.0:
            return None
        return self.reference_covered_duration_s() / total_duration_s


@dataclass
class EvaluationResultV2:
    evaluation_window_start_s: float
    evaluation_window_end_s: float
    total_evaluated_duration_s: float
    duration_buckets: DurationBucketsV2
    localisation: LocalisationAggregate
    reconciliation_ok: bool
    reconciliation_residual_s: float


def evaluate_physical_target_bbox_v2(
    *,
    reference: PhysicalReferenceArtifact,
    output_samples: Sequence[OutputSample],
    step_s: float = DEFAULT_STEP_S,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> EvaluationResultV2:
    samples = reference.samples
    if not samples:
        raise ValueError(
            "a tim_physical_target_bbox_v2 artifact needs at least one sample"
        )

    window = reference.provenance.evaluation_window
    breakpoints = _build_breakpoints(
        window.start_s, window.end_s, [s.t_s for s in samples], step_s
    )

    buckets = DurationBucketsV2()
    localisation_samples: list[tuple[float, float, float, float]] = []
    total_duration = 0.0

    for t0, t1 in zip(breakpoints, breakpoints[1:]):
        dt = t1 - t0
        if dt <= 0.0:
            continue
        total_duration += dt

        resolved = resolve_reference_interval(samples, t0)

        if resolved.condition == REF_GAP:
            buckets.reference_gap_duration_s += dt
            output = latest_output_at(output_samples, t0, max_output_age_s)
            if output is not None:
                buckets.reference_gap_with_output_duration_s += dt
            continue

        if resolved.condition == REF_TARGET_ABSENT:
            buckets.target_absent_duration_s += dt
            output = latest_output_at(output_samples, t0, max_output_age_s)
            if output is not None:
                buckets.target_absent_with_output_duration_s += dt
            continue

        if resolved.condition == REF_UNAVAILABLE:
            buckets.reference_unavailable_duration_s += dt
            continue

        # REF_COVERED -- always via legal interpolation (never a hold).
        assert resolved.interpolated
        buckets.interpolated_reference_duration_s += dt

        output = latest_output_at(output_samples, t0, max_output_age_s)
        if output is None or output.bbox_xyxy is None:
            buckets.lost_or_suppressed_duration_s += dt
            continue

        assert resolved.target_bbox_xyxy is not None
        assert resolved.identity_context is not None

        outcome = classify_identity_stage_a(
            identity_context=resolved.identity_context,
            target_bbox_xyxy=resolved.target_bbox_xyxy,
            distractor_bboxes_xyxy=[d.bbox_xyxy for d in resolved.distractors],
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
    return EvaluationResultV2(
        evaluation_window_start_s=window.start_s,
        evaluation_window_end_s=window.end_s,
        total_evaluated_duration_s=total_duration,
        duration_buckets=buckets,
        localisation=aggregate_localisation(localisation_samples),
        reconciliation_ok=residual <= 1e-6,
        reconciliation_residual_s=residual,
    )


# --- Report assembly ---------------------------------------------------------


def build_report(
    *,
    result: EvaluationResultV2,
    stream_name: str,
    provenance: PhysicalReferenceProvenance,
    physical_reference_path: str,
    physical_reference_sha256: str,
    repo_commit: str | None,
    repo_dirty: bool | None,
) -> dict:
    """Deterministic, machine-readable result. Missing provenance is
    recorded as null, never fabricated -- matching v1's own build_report."""

    buckets = result.duration_buckets
    loc = result.localisation
    total = result.total_evaluated_duration_s

    return {
        "schema_version": provenance.schema_version,
        "contract_version": provenance.contract_version,
        "evaluator": "physical_target_bbox_evaluation_v2",
        "evaluator_mode": "physical_reference_v2",
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
        "evaluation_window": {
            "start_s": result.evaluation_window_start_s,
            "end_s": result.evaluation_window_end_s,
        },
        "total_evaluated_duration_s": total,
        "duration_buckets": {
            "correct_target_output_duration_s": buckets.correct_target_output_duration_s,
            "wrong_person_output_duration_s": buckets.wrong_person_output_duration_s,
            "identity_unresolved_duration_s": buckets.identity_unresolved_duration_s,
            "lost_or_suppressed_duration_s": buckets.lost_or_suppressed_duration_s,
            "target_absent_duration_s": buckets.target_absent_duration_s,
            "reference_unavailable_duration_s": buckets.reference_unavailable_duration_s,
            "reference_gap_duration_s": buckets.reference_gap_duration_s,
            "localisation_scored_duration_s": buckets.localisation_scored_duration_s,
            "target_absent_with_output_duration_s": buckets.target_absent_with_output_duration_s,
            "reference_gap_with_output_duration_s": buckets.reference_gap_with_output_duration_s,
        },
        "coverage": {
            "reference_covered_duration_s": buckets.reference_covered_duration_s(),
            "reference_gap_duration_s": buckets.reference_gap_duration_s,
            "reference_coverage_fraction": buckets.reference_coverage_fraction(total),
            "interpolated_reference_duration_s": buckets.interpolated_reference_duration_s,
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
