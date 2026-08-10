"""Focused tests for the Issue #25 M2-v2 interval-aware evaluation core
(tools/analysis/physical_target_bbox_evaluation_v2.py), proving the frozen
v2 contract (docs/issues/p1-10-physical-reference-v2-contract.md, sections
H-K) end-to-end with synthetic data before any real sequence is annotated.

The one thing every test group here ultimately proves, from a different
angle: v1's silent step-hold of stale present_scored geometry across an
uncovered interval does not exist in v2 under any circumstance. Coverage
comes only from an exact keyframe instant (zero duration by itself) or a
legally interpolated span (per physical person, by person_ref, never by
list position).
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest


def _load(name: str, relative: str):
    module_path = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PTR1 = _load("physical_target_reference", "analysis/physical_target_reference.py")
PTR2 = _load("physical_target_reference_v2", "analysis/physical_target_reference_v2.py")
EV1 = _load(
    "physical_target_bbox_evaluation", "analysis/physical_target_bbox_evaluation.py"
)
EV2 = _load(
    "physical_target_bbox_evaluation_v2",
    "analysis/physical_target_bbox_evaluation_v2.py",
)


TARGET_ONLY = PTR2.CONTEXT_TARGET_ONLY
DIST_COMPLETE = PTR2.CONTEXT_DISTRACTORS_COMPLETE
SCORED = PTR2.STATE_PRESENT_SCORED
UNAVAILABLE = PTR2.STATE_PRESENT_REFERENCE_UNAVAILABLE
ABSENT = PTR2.STATE_ABSENT


def _distractor(person_ref: str, bbox) -> PTR2.DistractorEntry:
    return PTR2.DistractorEntry(person_ref=person_ref, bbox_xyxy=bbox)


def _ref_sample(
    t_s,
    state,
    context=None,
    bbox=None,
    distractors=None,
    interpolate=False,
) -> PTR2.PhysicalReferenceSample:
    return PTR2.PhysicalReferenceSample(
        t_s=t_s,
        identity_state=state,
        identity_context=context,
        target_bbox_xyxy=bbox,
        distractors=tuple(distractors or []),
        interpolate_from_previous=interpolate,
    )


def _provenance(**overrides) -> PTR2.PhysicalReferenceProvenance:
    base = dict(
        schema_version=2,
        contract_version="tim_physical_target_bbox_v2",
        sequence_id="dev_test_sequence",
        source_bag_name="test_bag",
        source_bag_path="bags/source/curated/test_bag",
        source_image_topic="/camera/image_raw",
        source_width=640,
        source_height=480,
        coordinate_convention="source_pixels_p53_contract",
        selected_physical_target_label="black_shirt_person",
        annotator="tester",
        created_date="2026-08-10",
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=10.0),
    )
    base.update(overrides)
    return PTR2.PhysicalReferenceProvenance(**base)


def _artifact(samples, **provenance_overrides) -> PTR2.PhysicalReferenceArtifact:
    return PTR2.PhysicalReferenceArtifact(
        provenance=_provenance(**provenance_overrides), samples=tuple(samples)
    )


def _out(t_s, bbox, track_id=1) -> EV2.OutputSample:
    return EV2.OutputSample(t_s=t_s, track_id=track_id, bbox_xyxy=bbox)


def _validated_artifact_dict(samples: list[dict], **provenance_overrides) -> dict:
    """Build via the real JSON-shaped parser/validator path (not just the
    dataclasses directly) for tests that specifically want validator
    involvement (e.g. rejection tests)."""
    base = {
        "schema_version": 2,
        "contract_version": "tim_physical_target_bbox_v2",
        "sequence_id": "dev_test_sequence",
        "source_bag_name": "test_bag",
        "source_bag_path": "bags/source/curated/test_bag",
        "source_image_topic": "/camera/image_raw",
        "source_width": 640,
        "source_height": 480,
        "coordinate_convention": "source_pixels_p53_contract",
        "selected_physical_target_label": "black_shirt_person",
        "annotator": "tester",
        "created_date": "2026-08-10",
        "evaluation_window": {"start_s": 0.0, "end_s": 10.0},
    }
    base.update(provenance_overrides)
    return {"provenance": base, "samples": samples}


def _sample_dict(
    t_s,
    identity_state,
    identity_context=None,
    target_bbox_xyxy=None,
    distractors=None,
    interpolate_from_previous=False,
) -> dict:
    return {
        "t_s": t_s,
        "identity_state": identity_state,
        "identity_context": identity_context,
        "target_bbox_xyxy": target_bbox_xyxy,
        "distractors": distractors or [],
        "interpolate_from_previous": interpolate_from_previous,
    }


# 1. before first sample -> gap ------------------------------------------------


def test_before_first_sample_is_reference_gap():
    # A single present_scored sample at t=5 means BOTH [0,5) (before first)
    # and [5,10) (after last, present_scored, no forward extrapolation) are
    # gap -- this test isolates the "before first sample" half directly via
    # resolve_reference_interval, since the full evaluate_...() total would
    # also include the "after last sample" gap contribution (proven
    # separately in test_after_last_present_scored_sample_is_reference_gap).
    reference = _artifact(
        [_ref_sample(5.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0))],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=10.0),
    )
    resolved_before = EV2.resolve_reference_interval(reference.samples, 2.0)
    assert resolved_before.condition == EV2.REF_GAP
    assert resolved_before.target_bbox_xyxy is None

    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    # Whole window is gap: [0,5) before-first + [5,10) after-last (no hold).
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(10.0)
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)


# 2. after last present_scored -> gap -------------------------------------------


def test_after_last_present_scored_sample_is_reference_gap():
    reference = _artifact(
        [_ref_sample(2.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0))],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=10.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    # [0, 2) before-first-sample gap + [2, 10) after-last-sample gap = 10.0 total
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(10.0)


# 3. last absent propagates to horizon end --------------------------------------


def test_last_absent_sample_propagates_to_evaluation_window_end():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(3.0, ABSENT),
        ]
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    # [0,3) gap (no interpolation claimed), [3,10) absent-propagated
    assert result.duration_buckets.target_absent_duration_s == pytest.approx(7.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(3.0)


# 4. last reference-unavailable propagates to horizon end -----------------------


def test_last_reference_unavailable_sample_propagates_to_evaluation_window_end():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(4.0, UNAVAILABLE),
        ]
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    assert result.duration_buckets.reference_unavailable_duration_s == pytest.approx(6.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(4.0)


# 5/6. isolated present_scored keyframe = zero covered duration, no step_s support


def test_isolated_present_scored_keyframe_grants_zero_covered_duration():
    reference = _artifact(
        [_ref_sample(0.5, SCORED, TARGET_ONLY, (10.0, 10.0, 20.0, 30.0))],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.05
    )
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(1.0)
    # Explicitly NOT the v1-style "0.05 scored, 0.95 gap" split.
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.localisation_scored_duration_s == 0.0


@pytest.mark.parametrize("step_s", [0.05, 0.1, 0.25, 1.0])
def test_isolated_keyframe_zero_duration_holds_regardless_of_grid_step(step_s):
    reference = _artifact(
        [_ref_sample(0.5, SCORED, TARGET_ONLY, (10.0, 10.0, 20.0, 30.0))],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=step_s
    )
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(1.0)


# 7. non-interpolated scored pair -> gap ----------------------------------------


def test_non_interpolated_present_scored_pair_is_reference_gap():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (50.0, 0.0, 60.0, 10.0)),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(5.0)
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)


# 8. target_only interpolation ---------------------------------------------------


def test_target_only_interpolation_covers_the_full_span():
    a = (0.0, 0.0, 10.0, 10.0)
    b = (100.0, 0.0, 110.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(10.0, SCORED, TARGET_ONLY, b, interpolate=True),
        ]
    )
    resolved_mid = EV2.resolve_reference_interval(reference.samples, 5.0)
    assert resolved_mid.condition == EV2.REF_COVERED
    assert resolved_mid.target_bbox_xyxy == pytest.approx((50.0, 0.0, 60.0, 10.0))

    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=1.0
    )
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(10.0)
    assert result.duration_buckets.interpolated_reference_duration_s == pytest.approx(10.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(0.0)


# 9/10. distractors_complete interpolation, per-person by person_ref ------------


def test_distractors_complete_interpolation_per_person_ref():
    reference = _artifact(
        [
            _ref_sample(
                0.0,
                SCORED,
                DIST_COMPLETE,
                (0.0, 0.0, 10.0, 10.0),
                [
                    _distractor("phys_d001", (20.0, 0.0, 30.0, 10.0)),
                    _distractor("phys_d002", (40.0, 0.0, 50.0, 10.0)),
                ],
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                (10.0, 10.0, 20.0, 20.0),
                [
                    _distractor("phys_d001", (30.0, 10.0, 40.0, 20.0)),
                    _distractor("phys_d002", (50.0, 10.0, 60.0, 20.0)),
                ],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    resolved = EV2.resolve_reference_interval(reference.samples, 1.0)
    assert resolved.condition == EV2.REF_COVERED
    assert resolved.target_bbox_xyxy == pytest.approx((5.0, 5.0, 15.0, 15.0))
    by_ref = {d.person_ref: d.bbox_xyxy for d in resolved.distractors}
    assert by_ref["phys_d001"] == pytest.approx((25.0, 5.0, 35.0, 15.0))
    assert by_ref["phys_d002"] == pytest.approx((45.0, 5.0, 55.0, 15.0))


# 11. list-order invariance -------------------------------------------------------


def test_distractor_list_order_does_not_affect_correspondence_or_result():
    def make(order_swapped: bool):
        first_distractors = [
            _distractor("phys_d001", (20.0, 0.0, 30.0, 10.0)),
            _distractor("phys_d002", (40.0, 0.0, 50.0, 10.0)),
        ]
        second_distractors = [
            _distractor("phys_d002", (50.0, 10.0, 60.0, 20.0)),
            _distractor("phys_d001", (30.0, 10.0, 40.0, 20.0)),
        ]
        if order_swapped:
            first_distractors = list(reversed(first_distractors))
            second_distractors = list(reversed(second_distractors))
        return _artifact(
            [
                _ref_sample(
                    0.0, SCORED, DIST_COMPLETE, (0.0, 0.0, 10.0, 10.0), first_distractors
                ),
                _ref_sample(
                    2.0,
                    SCORED,
                    DIST_COMPLETE,
                    (10.0, 10.0, 20.0, 20.0),
                    second_distractors,
                    interpolate=True,
                ),
            ],
            evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
        )

    reference_normal = make(order_swapped=False)
    reference_swapped = make(order_swapped=True)

    result_normal = EV2.evaluate_physical_target_bbox_v2(
        reference=reference_normal,
        output_samples=[_out(1.0, (25.0, 5.0, 35.0, 15.0))],
        step_s=0.5,
    )
    result_swapped = EV2.evaluate_physical_target_bbox_v2(
        reference=reference_swapped,
        output_samples=[_out(1.0, (25.0, 5.0, 35.0, 15.0))],
        step_s=0.5,
    )
    assert result_normal.duration_buckets == result_swapped.duration_buckets
    assert result_normal.localisation == result_swapped.localisation


# 12. non-round timestamp interpolation ------------------------------------------


def test_interpolation_with_non_round_bag_relative_timestamps():
    a_t, b_t = 24.77, 29.37
    a = (100.0, 100.0, 120.0, 140.0)
    b = (140.0, 100.0, 160.0, 140.0)
    reference = _artifact(
        [
            _ref_sample(a_t, SCORED, TARGET_ONLY, a),
            _ref_sample(b_t, SCORED, TARGET_ONLY, b, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=30.0),
    )
    t_mid = 27.0
    expected_fraction = (t_mid - a_t) / (b_t - a_t)
    resolved = EV2.resolve_reference_interval(reference.samples, t_mid)
    assert resolved.condition == EV2.REF_COVERED
    expected_x1 = a[0] + (b[0] - a[0]) * expected_fraction
    assert resolved.target_bbox_xyxy[0] == pytest.approx(expected_x1)


# 13/14. changed person_ref set rejected; no intersection fallback --------------


def test_added_person_ref_is_gap_not_partial_interpolation():
    """Even though this specific artifact would fail validate_physical_reference
    (the schema layer already proves rejection separately in
    test_physical_target_reference_v2.py), resolve_reference_interval itself
    must never silently fall back to a partial/intersection interpolation if
    it is ever handed a successor whose interpolate_from_previous is legally
    False for a set-mismatched pair -- proven here directly at the resolution
    layer, independent of schema validation."""
    reference = _artifact(
        [
            _ref_sample(
                0.0,
                SCORED,
                DIST_COMPLETE,
                (0.0, 0.0, 10.0, 10.0),
                [_distractor("phys_d001", (20.0, 0.0, 30.0, 10.0))],
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                (10.0, 10.0, 20.0, 20.0),
                [
                    _distractor("phys_d001", (30.0, 10.0, 40.0, 20.0)),
                    _distractor("phys_d002", (50.0, 10.0, 60.0, 20.0)),
                ],
                interpolate=False,  # correctly left false: sets differ
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    resolved = EV2.resolve_reference_interval(reference.samples, 1.0)
    assert resolved.condition == EV2.REF_GAP
    assert resolved.distractors == ()


def test_validator_rejects_added_person_ref_interpolation_claim():
    data = _validated_artifact_dict(
        [
            _sample_dict(
                0.0,
                SCORED,
                DIST_COMPLETE,
                [0.0, 0.0, 10.0, 10.0],
                [{"person_ref": "phys_d001", "bbox_xyxy": [20.0, 0.0, 30.0, 10.0]}],
            ),
            _sample_dict(
                2.0,
                SCORED,
                DIST_COMPLETE,
                [10.0, 10.0, 20.0, 20.0],
                [
                    {"person_ref": "phys_d001", "bbox_xyxy": [30.0, 10.0, 40.0, 20.0]},
                    {"person_ref": "phys_d002", "bbox_xyxy": [50.0, 10.0, 60.0, 20.0]},
                ],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        PTR2.validate_physical_reference(artifact)


# 15. no step-hold fallback --------------------------------------------------------


def test_no_step_hold_fallback_anywhere_in_resolution_source():
    """A gap must never carry the predecessor's own bbox as if it were
    still valid -- the direct behavioural proof that no step-hold fallback
    exists (contrast with v1's resolve_reference_at, which returns exactly
    the predecessor's bbox in this situation; see the explicit v1/v2
    comparison in test_original_defect_regression_gap_without_interpolation_covered_with_it)."""
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (1.0, 1.0, 2.0, 2.0)),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (9.0, 9.0, 10.0, 10.0)),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    resolved = EV2.resolve_reference_interval(reference.samples, 3.0)
    assert resolved.condition == EV2.REF_GAP
    assert resolved.target_bbox_xyxy is None


# 16/17/18. Stage A on interpolated reference ------------------------------------


def test_stage_a_target_on_interpolated_target_only_reference():
    a = (0.0, 0.0, 10.0, 10.0)
    b = (10.0, 0.0, 20.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(2.0, SCORED, TARGET_ONLY, b, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    # At t=1.0 the interpolated target is (5,0,15,10).
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(1.0, (5.0, 0.0, 15.0, 10.0))],
        step_s=0.5,
    )
    assert result.duration_buckets.correct_target_output_duration_s > 0.0
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0


def test_stage_a_wrong_person_using_interpolated_distractor_geometry():
    """The original defect this whole v2 effort exists to fix: a moving
    distractor's interpolated position must be used, not a stale one --
    proven by constructing an output that only overlaps the *interpolated*
    (not the start-keyframe) distractor position."""
    target = (0.0, 0.0, 10.0, 10.0)
    distractor_start = (100.0, 0.0, 110.0, 10.0)
    distractor_end = (200.0, 0.0, 210.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(
                0.0,
                SCORED,
                DIST_COMPLETE,
                target,
                [_distractor("phys_d001", distractor_start)],
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                target,
                [_distractor("phys_d001", distractor_end)],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    # At t=2.0's approach (t=1.9), interpolated distractor is near (195,0,205,10).
    output_near_end_position = (195.0, 0.0, 205.0, 10.0)
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(1.9, output_near_end_position)],
        step_s=0.05,
    )
    assert result.duration_buckets.wrong_person_output_duration_s > 0.0

    # Under a naive v1-style stale hold, the SAME output at t=1.9 would have
    # been compared only to the start-keyframe distractor position (far
    # away), which would not explain this output at all -- demonstrating
    # the practical consequence of the fix, not just its mechanism.
    far_from_start_distractor = EV1.bbox_iou(output_near_end_position, distractor_start)
    assert far_from_start_distractor == 0.0


def test_stage_a_identity_unresolved_using_interpolated_geometry():
    target_start = (0.0, 0.0, 10.0, 10.0)
    target_end = (100.0, 0.0, 110.0, 10.0)
    distractor_start = (200.0, 0.0, 210.0, 10.0)
    distractor_end = (100.0, 0.0, 110.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(
                0.0,
                SCORED,
                DIST_COMPLETE,
                target_start,
                [_distractor("phys_d001", distractor_start)],
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                target_end,
                [_distractor("phys_d001", distractor_end)],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    # At t=2.0 (exclusive upper bound of this interval, use 1.999) target and
    # distractor interpolate to (nearly) the same box -> tie -> unresolved,
    # when the output also sits exactly on that same box.
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(1.999, (99.9, 0.0, 109.9, 10.0))],
        step_s=0.001,
    )
    assert result.duration_buckets.identity_unresolved_duration_s > 0.0


# 19/20. poor localisation reaches Stage B; wrong-person never does -------------


def test_poor_target_localisation_including_iou_zero_reaches_stage_b():
    target = (100.0, 100.0, 200.0, 300.0)
    disjoint_output = (500.0, 100.0, 600.0, 300.0)
    # Window kept within DEFAULT_MAX_OUTPUT_AGE_S (0.9s) so the single
    # t=0 output reading stays fresh for the whole span -- this test is
    # about Stage B not filtering poor/zero IoU, not about output
    # freshness, which is exercised separately (sections 21-23).
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(0.8, SCORED, TARGET_ONLY, target, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=0.8),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[_out(0.0, disjoint_output)], step_s=0.2
    )
    assert result.duration_buckets.correct_target_output_duration_s == pytest.approx(0.8)
    assert result.duration_buckets.localisation_scored_duration_s == pytest.approx(0.8)
    assert result.localisation.iou_min == pytest.approx(0.0)


def test_wrong_person_never_contributes_to_localisation_aggregate():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [_distractor("phys_d001", distractor)]),
            _ref_sample(
                0.8,
                SCORED,
                DIST_COMPLETE,
                target,
                [_distractor("phys_d001", distractor)],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=0.8),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[_out(0.0, distractor)], step_s=0.2
    )
    assert result.duration_buckets.wrong_person_output_duration_s == pytest.approx(0.8)
    assert result.localisation.n_samples == 0
    assert result.localisation.iou_duration_weighted_mean is None


# 21. valid reference + no output -> lost/suppressed -----------------------------


def test_valid_reference_no_fresh_output_is_lost_or_suppressed():
    a = (0.0, 0.0, 10.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(2.0, SCORED, TARGET_ONLY, a, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    assert result.duration_buckets.lost_or_suppressed_duration_s == pytest.approx(2.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(0.0)


# 22. gap + output -> still gap ---------------------------------------------------


def test_gap_with_a_present_output_remains_gap_not_lost_or_scored():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (50.0, 0.0, 60.0, 10.0)),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    # Repeated output readings (spacing < DEFAULT_MAX_OUTPUT_AGE_S) so the
    # output stays fresh across the whole span -- this test is about gap
    # classification not being displaced by output presence, not about
    # output staleness (exercised separately).
    outputs = [_out(t, (0.0, 0.0, 10.0, 10.0)) for t in (0.0, 0.8, 1.6, 2.4, 3.2, 4.0, 4.8)]
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=outputs, step_s=1.0
    )
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(5.0)
    assert result.duration_buckets.lost_or_suppressed_duration_s == 0.0
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    # Diagnostic subset still records that an output happened to exist.
    assert result.duration_buckets.reference_gap_with_output_duration_s == pytest.approx(5.0)


# 23. unavailable + output -> unavailable -----------------------------------------


def test_reference_unavailable_with_output_remains_unavailable():
    reference = _artifact(
        [
            _ref_sample(0.0, UNAVAILABLE),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=10.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(0.0, (0.0, 0.0, 10.0, 10.0))],
        step_s=1.0,
    )
    assert result.duration_buckets.reference_unavailable_duration_s == pytest.approx(5.0)


# 24. absent + output -> absence + output subset ----------------------------------


def test_absent_with_output_records_safety_subset():
    reference = _artifact(
        [
            _ref_sample(0.0, ABSENT),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=10.0),
    )
    outputs = [_out(t, (0.0, 0.0, 10.0, 10.0)) for t in (0.0, 0.8, 1.6, 2.4, 3.2, 4.0, 4.8)]
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=outputs, step_s=1.0
    )
    assert result.duration_buckets.target_absent_duration_s == pytest.approx(5.0)
    assert result.duration_buckets.target_absent_with_output_duration_s == pytest.approx(5.0)


# 25/26. exact seven-bucket reconciliation, non-grid-aligned end -----------------


def test_seven_bucket_reconciliation_across_mixed_segments():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    # Per-interval breakdown (window [0,7)):
    #   [0,1) absent (state-propagated)                          -> target_absent
    #   [1,2) present_reference_unavailable (state-propagated)   -> reference_unavailable
    #   [2,3) target_only, legally interpolated into by sample@3 -> covered
    #   [3,4) target_only -> distractors_complete: context change,
    #         successor@4 does not claim interpolation            -> gap
    #   [4,5) isolated distractors_complete keyframe (successor@5
    #         does not claim interpolation)                       -> gap
    #   [5,6) target_only, legally interpolated into by sample@6  -> covered
    #   [6,7) after the last sample (present_scored, no forward
    #         extrapolation)                                      -> gap
    reference = _artifact(
        [
            _ref_sample(0.0, ABSENT),
            _ref_sample(1.0, UNAVAILABLE),
            _ref_sample(2.0, SCORED, TARGET_ONLY, target),
            _ref_sample(3.0, SCORED, TARGET_ONLY, target, interpolate=True),
            _ref_sample(4.0, SCORED, DIST_COMPLETE, target, [_distractor("phys_d001", distractor)]),
            _ref_sample(5.0, SCORED, TARGET_ONLY, target),
            _ref_sample(6.0, SCORED, TARGET_ONLY, target, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=7.0),
    )
    outputs = [
        # Fresh throughout [2,3) (age < 0.9 across the whole span) -> correct.
        _out(2.0, target),
        # Present during the [4,5) gap (diagnostic subset only), but stale
        # by the time [5,6) is reached (age >= 0.9) -> lost_or_suppressed
        # there, never wrong_person (a gap output never reaches Stage A).
        _out(4.0, distractor),
    ]

    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=outputs, step_s=0.25
    )

    assert result.reconciliation_ok is True
    assert result.reconciliation_residual_s < 1e-9
    buckets = result.duration_buckets
    assert buckets.primary_total_s() == pytest.approx(result.total_evaluated_duration_s)
    assert buckets.target_absent_duration_s == pytest.approx(1.0)
    assert buckets.reference_unavailable_duration_s == pytest.approx(1.0)
    assert buckets.reference_gap_duration_s == pytest.approx(3.0)  # [3,4)+[4,5)+[6,7)
    assert buckets.correct_target_output_duration_s == pytest.approx(1.0)  # [2,3)
    assert buckets.wrong_person_output_duration_s == pytest.approx(0.0)
    assert buckets.lost_or_suppressed_duration_s == pytest.approx(1.0)  # [5,6), output gone stale
    assert buckets.interpolated_reference_duration_s == pytest.approx(2.0)  # [2,3) + [5,6)
    assert buckets.reference_gap_with_output_duration_s == pytest.approx(1.0)  # [4,5) only


def test_reconciliation_holds_for_non_grid_aligned_evaluation_end():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(1.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0), interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.13),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.3
    )
    assert result.reconciliation_ok is True
    assert result.total_evaluated_duration_s == pytest.approx(1.13)
    assert result.duration_buckets.primary_total_s() == pytest.approx(1.13)


# --- Right-boundary anchor at t_s == evaluation_window.end_s -------------------
#
# Corrected 2026-08-10, before any M3-v2 UI work: the sample anchor domain is
# the closed [start_s, end_s], distinct from the half-open evaluated duration
# domain [start_s, end_s). No evaluator code changed for this correction --
# these tests exist to prove that is genuinely true, not just claimed.


def test_isolated_sample_exactly_at_evaluation_window_end_is_zero_duration():
    reference = _artifact(
        [_ref_sample(5.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0))],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    assert result.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(5.0)
    assert result.reconciliation_ok is True


def test_legal_interpolation_to_right_boundary_anchor_covers_exactly_to_horizon():
    a = (0.0, 0.0, 10.0, 10.0)
    b = (50.0, 0.0, 60.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(5.0, SCORED, TARGET_ONLY, b, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    buckets = result.duration_buckets
    assert buckets.interpolated_reference_duration_s == pytest.approx(5.0)
    assert buckets.reference_covered_duration_s() == pytest.approx(5.0)
    assert buckets.reference_gap_duration_s == pytest.approx(0.0)
    assert result.reconciliation_ok is True
    assert result.total_evaluated_duration_s == pytest.approx(5.0)
    assert buckets.primary_total_s() == pytest.approx(5.0)

    # And the interpolated geometry right up to (but not including) end_s is
    # correct, not merely "some" coverage.
    resolved_near_end = EV2.resolve_reference_interval(reference.samples, 4.5)
    assert resolved_near_end.condition == EV2.REF_COVERED
    expected_fraction = 4.5 / 5.0
    expected_x1 = a[0] + (b[0] - a[0]) * expected_fraction
    assert resolved_near_end.target_bbox_xyxy[0] == pytest.approx(expected_x1)


def test_non_interpolated_right_boundary_anchor_creates_no_coverage_after_itself():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(5.0, SCORED, TARGET_ONLY, (50.0, 0.0, 60.0, 10.0)),  # not interpolated
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=5.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    buckets = result.duration_buckets
    assert buckets.reference_gap_duration_s == pytest.approx(5.0)
    assert buckets.reference_covered_duration_s() == pytest.approx(0.0)
    assert result.reconciliation_ok is True


def test_distractors_complete_interpolation_to_right_boundary_anchor():
    """The same right-boundary-anchor coverage guarantee holds for
    distractors_complete, matched by person_ref, not just target_only."""
    reference = _artifact(
        [
            _ref_sample(
                0.0,
                SCORED,
                DIST_COMPLETE,
                (0.0, 0.0, 10.0, 10.0),
                [_distractor("phys_d001", (100.0, 0.0, 110.0, 10.0))],
            ),
            _ref_sample(
                4.0,
                SCORED,
                DIST_COMPLETE,
                (40.0, 0.0, 50.0, 10.0),
                [_distractor("phys_d001", (140.0, 0.0, 150.0, 10.0))],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=4.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.4
    )
    assert result.duration_buckets.interpolated_reference_duration_s == pytest.approx(4.0)
    assert result.duration_buckets.reference_gap_duration_s == pytest.approx(0.0)
    assert result.reconciliation_ok is True


# 27/28/29/30. coverage metrics ---------------------------------------------------


def test_reference_covered_duration_and_coverage_fraction():
    a = (0.0, 0.0, 10.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(4.0, SCORED, TARGET_ONLY, a, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=8.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    buckets = result.duration_buckets
    assert buckets.reference_covered_duration_s() == pytest.approx(4.0)
    assert buckets.reference_gap_duration_s == pytest.approx(4.0)
    fraction = buckets.reference_coverage_fraction(result.total_evaluated_duration_s)
    assert fraction == pytest.approx(0.5)


def test_interpolated_reference_duration_is_a_subset_not_a_primary_bucket():
    a = (0.0, 0.0, 10.0, 10.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, a),
            _ref_sample(3.0, SCORED, TARGET_ONLY, a, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=3.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    buckets = result.duration_buckets
    assert buckets.interpolated_reference_duration_s == pytest.approx(3.0)
    # Not part of primary_total_s()'s seven terms directly summed twice:
    # removing it from a hand computation of the seven primary buckets must
    # still reconcile.
    assert buckets.primary_total_s() == pytest.approx(3.0)  # lost_or_suppressed only


# 31. localisation subset correct --------------------------------------------------


def test_localisation_scored_duration_is_subset_of_correct_target_bucket():
    target = (100.0, 100.0, 200.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(2.0, SCORED, TARGET_ONLY, target, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[_out(0.0, target)], step_s=0.5
    )
    buckets = result.duration_buckets
    assert buckets.localisation_scored_duration_s <= buckets.correct_target_output_duration_s + 1e-9
    assert buckets.localisation_scored_duration_s == pytest.approx(
        buckets.correct_target_output_duration_s
    )


# 32. regenerated tracker-ID invariance --------------------------------------------


def test_regenerated_tracker_id_invariance_end_to_end():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    output_bbox = (101.0, 100.0, 201.0, 300.0)

    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [_distractor("phys_d001", distractor)]),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                target,
                [_distractor("phys_d001", distractor)],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )

    result_run_1 = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(0.0, output_bbox, track_id=1)],
        step_s=0.5,
    )
    result_run_2 = EV2.evaluate_physical_target_bbox_v2(
        reference=reference,
        output_samples=[_out(0.0, output_bbox, track_id=69)],
        step_s=0.5,
    )

    assert result_run_1.duration_buckets == result_run_2.duration_buckets
    assert result_run_1.localisation == result_run_2.localisation
    assert result_run_1.reconciliation_ok == result_run_2.reconciliation_ok


def test_output_sample_track_id_is_never_read_by_v2_evaluation_functions():
    source = inspect.getsource(EV2.evaluate_physical_target_bbox_v2)
    source += inspect.getsource(EV2.resolve_reference_interval)
    assert ".track_id" not in source


def test_no_tracker_id_concept_in_v2_evaluator_module_source():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "analysis"
        / "physical_target_bbox_evaluation_v2.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "correct_target_track_id" not in source


# 33/34/35. report/provenance ------------------------------------------------------


def test_build_report_v2_records_schema_version_provenance_and_evaluation_window():
    target = (100.0, 100.0, 200.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target, interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[_out(0.0, target)], step_s=0.5
    )
    report = EV2.build_report(
        result=result,
        stream_name="tim_target_memory",
        provenance=reference.provenance,
        physical_reference_path="docs/data/physical_target_references/dev_test.json",
        physical_reference_sha256="b" * 64,
        repo_commit="0" * 40,
        repo_dirty=False,
    )

    assert report["schema_version"] == 2
    assert report["contract_version"] == "tim_physical_target_bbox_v2"
    assert report["evaluator"] == "physical_target_bbox_evaluation_v2"
    assert report["evaluator_mode"] == "physical_reference_v2"
    assert report["evaluation_window"] == {"start_s": 0.0, "end_s": 1.0}
    assert report["physical_reference_sha256"] == "b" * 64
    assert report["repo_commit"] == "0" * 40
    assert report["repo_dirty"] is False
    for key in (
        "correct_target_output_duration_s",
        "wrong_person_output_duration_s",
        "identity_unresolved_duration_s",
        "lost_or_suppressed_duration_s",
        "target_absent_duration_s",
        "reference_unavailable_duration_s",
        "reference_gap_duration_s",
    ):
        assert key in report["duration_buckets"]
    for key in (
        "reference_covered_duration_s",
        "reference_gap_duration_s",
        "reference_coverage_fraction",
        "interpolated_reference_duration_s",
    ):
        assert key in report["coverage"]


def test_build_report_v2_never_fabricates_missing_provenance():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(1.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0), interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.0),
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    report = EV2.build_report(
        result=result,
        stream_name="raw_target",
        provenance=reference.provenance,
        physical_reference_path="unused.json",
        physical_reference_sha256="c" * 64,
        repo_commit=None,
        repo_dirty=None,
    )
    assert report["repo_commit"] is None
    assert report["repo_dirty"] is None


def test_build_report_v2_retains_coordinate_metadata():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(1.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0), interpolate=True),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=1.0),
        coordinate_convention="source_pixels_historical_pre_p53",
        coordinate_convention_evidence="direct bag header inspection",
    )
    result = EV2.evaluate_physical_target_bbox_v2(
        reference=reference, output_samples=[], step_s=0.5
    )
    report = EV2.build_report(
        result=result,
        stream_name="raw_target",
        provenance=reference.provenance,
        physical_reference_path="unused.json",
        physical_reference_sha256="d" * 64,
        repo_commit=None,
        repo_dirty=None,
    )
    assert report["coordinate_convention"] == "source_pixels_historical_pre_p53"
    assert report["coordinate_convention_evidence"] == "direct bag header inspection"


# 36. invalid v2 fails before evaluation -------------------------------------------


def test_invalid_v2_artifact_fails_validation_before_evaluation():
    # A bare-integer person_ref is rejected at parse time (structural field
    # validation), before validate_physical_reference (semantic checks) or
    # the evaluator ever run -- proving the evaluator is unreachable for a
    # malformed artifact in the real load_physical_reference() workflow,
    # which calls parse then validate before returning anything usable.
    data = _validated_artifact_dict(
        [
            _sample_dict(
                0.0,
                SCORED,
                DIST_COMPLETE,
                [0.0, 0.0, 10.0, 10.0],
                [{"person_ref": "1", "bbox_xyxy": [20.0, 0.0, 30.0, 10.0]}],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="person_ref"):
        PTR2.parse_physical_reference(data)


def test_v1_artifact_cannot_be_evaluated_by_v2_loader():
    v1_data = {
        "provenance": {
            "schema_version": 1,
            "contract_version": "tim_physical_target_bbox_v1",
            "sequence_id": "dev_test_sequence",
            "source_bag_name": "test_bag",
            "source_bag_path": "bags/source/curated/test_bag",
            "source_image_topic": "/camera/image_raw",
            "source_width": 640,
            "source_height": 480,
            "coordinate_convention": "source_pixels_p53_contract",
            "selected_physical_target_label": "black_shirt_person",
            "annotator": "tester",
            "created_date": "2026-08-09",
        },
        "samples": [
            {
                "t_s": 0.0,
                "identity_state": "present_scored",
                "identity_context": "target_only",
                "target_bbox_xyxy": [10.0, 10.0, 20.0, 30.0],
                "distractor_bboxes_xyxy": [],
                "interpolate_from_previous": False,
            }
        ],
    }
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        PTR2.parse_physical_reference(v1_data)


def test_v2_artifact_cannot_be_evaluated_by_v1_evaluator_input_path():
    """A v2-shaped artifact must be rejected by the v1 schema parser too --
    the two evaluators' inputs are not interchangeable in either direction."""
    data = _validated_artifact_dict(
        [_sample_dict(0.0, SCORED, TARGET_ONLY, [10.0, 10.0, 20.0, 30.0])]
    )
    with pytest.raises(PTR1.PhysicalReferenceValidationError, match="schema_version"):
        PTR1.parse_physical_reference(data)


# --- Explicit original-defect regression: gap vs. correctly interpolated -------


def test_original_defect_regression_gap_without_interpolation_covered_with_it():
    """The exact scenario the whole v2 effort exists to fix: two
    distractors_complete anchors describing a moving person. Without
    interpolation, v2 must report an honest gap (never a stale hold, unlike
    v1). With legal interpolation and the same person_ref set, v2 must
    report correctly interpolated target/distractor geometry -- proven by
    checking a mid-interval output against the true interpolated position,
    not the stale start-keyframe one."""
    target_a = (0.0, 0.0, 10.0, 10.0)
    target_b = (40.0, 0.0, 50.0, 10.0)
    distractor_a = (100.0, 0.0, 110.0, 10.0)
    distractor_b = (140.0, 0.0, 150.0, 10.0)

    # --- without interpolation: honest gap ---
    reference_no_interp = _artifact(
        [
            _ref_sample(
                0.0, SCORED, DIST_COMPLETE, target_a, [_distractor("phys_d001", distractor_a)]
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                target_b,
                [_distractor("phys_d001", distractor_b)],
                interpolate=False,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    resolved_gap = EV2.resolve_reference_interval(reference_no_interp.samples, 1.0)
    assert resolved_gap.condition == EV2.REF_GAP
    assert resolved_gap.target_bbox_xyxy is None

    result_gap = EV2.evaluate_physical_target_bbox_v2(
        reference=reference_no_interp,
        output_samples=[_out(1.0, (20.0, 0.0, 30.0, 10.0))],
        step_s=0.5,
    )
    assert result_gap.duration_buckets.reference_gap_duration_s == pytest.approx(2.0)
    assert result_gap.duration_buckets.reference_covered_duration_s() == pytest.approx(0.0)

    # v1 comparison: the same non-interpolated pair silently step-holds.
    v1_samples = (
        PTR1.PhysicalReferenceSample(
            t_s=0.0,
            identity_state=PTR1.STATE_PRESENT_SCORED,
            identity_context=PTR1.CONTEXT_DISTRACTORS_COMPLETE,
            target_bbox_xyxy=target_a,
            distractor_bboxes_xyxy=(distractor_a,),
            interpolate_from_previous=False,
        ),
        PTR1.PhysicalReferenceSample(
            t_s=2.0,
            identity_state=PTR1.STATE_PRESENT_SCORED,
            identity_context=PTR1.CONTEXT_DISTRACTORS_COMPLETE,
            target_bbox_xyxy=target_b,
            distractor_bboxes_xyxy=(distractor_b,),
            interpolate_from_previous=False,
        ),
    )
    v1_resolved = EV1.resolve_reference_at(v1_samples, 1.0)
    assert v1_resolved is not None
    assert v1_resolved.target_bbox_xyxy == target_a  # the defect, deliberately unfixed in v1

    # --- with legal interpolation: correctly interpolated geometry ---
    reference_interp = _artifact(
        [
            _ref_sample(
                0.0, SCORED, DIST_COMPLETE, target_a, [_distractor("phys_d001", distractor_a)]
            ),
            _ref_sample(
                2.0,
                SCORED,
                DIST_COMPLETE,
                target_b,
                [_distractor("phys_d001", distractor_b)],
                interpolate=True,
            ),
        ],
        evaluation_window=PTR2.EvaluationWindow(start_s=0.0, end_s=2.0),
    )
    resolved_covered = EV2.resolve_reference_interval(reference_interp.samples, 1.0)
    assert resolved_covered.condition == EV2.REF_COVERED
    assert resolved_covered.target_bbox_xyxy == pytest.approx((20.0, 0.0, 30.0, 10.0))
    by_ref = {d.person_ref: d.bbox_xyxy for d in resolved_covered.distractors}
    assert by_ref["phys_d001"] == pytest.approx((120.0, 0.0, 130.0, 10.0))

    # Output that only matches the correctly-interpolated target position
    # (not the stale t=0 anchor) must be scored identity_target.
    # The full span is legally covered by interpolation regardless of Stage
    # A's per-instant verdict, so reference_gap must be exactly 0 -- the
    # crux of the fix. The output (fixed, matching the target's correctly
    # interpolated t=1.0 position) is genuinely identity_target at t=1.0,
    # and the target keeps moving after that -- so only >0 (not the full
    # span) is asserted for correct_target, proven precisely at t=1.0 by
    # the resolve_reference_interval check above already.
    result_covered = EV2.evaluate_physical_target_bbox_v2(
        reference=reference_interp,
        output_samples=[_out(1.0, (20.0, 0.0, 30.0, 10.0))],
        step_s=0.5,
    )
    assert result_covered.duration_buckets.correct_target_output_duration_s > 0.0
    assert result_covered.duration_buckets.reference_gap_duration_s == pytest.approx(0.0)
