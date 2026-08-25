"""Focused tests for the Issue #25 identity-independent evaluation core
(tools/analysis/physical_target_bbox_evaluation.py), proving the frozen
Stage A / Stage B separation end-to-end with synthetic data before any
real sequence is annotated.
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


PTR = _load("physical_target_reference", "analysis/physical_target_reference.py")
EV = _load(
    "physical_target_bbox_evaluation", "analysis/physical_target_bbox_evaluation.py"
)


def _ref_sample(
    t_s,
    state,
    context=None,
    bbox=None,
    distractors=None,
    interpolate=False,
):
    return PTR.PhysicalReferenceSample(
        t_s=t_s,
        identity_state=state,
        identity_context=context,
        target_bbox_xyxy=bbox,
        distractor_bboxes_xyxy=tuple(distractors or []),
        interpolate_from_previous=interpolate,
    )


def _provenance(**overrides):
    base = dict(
        schema_version=1,
        contract_version="tim_physical_target_bbox_v1",
        sequence_id="dev_test_sequence",
        source_bag_name="test_bag",
        source_bag_path="bags/source/curated/test_bag",
        source_image_topic="/camera/image_raw",
        source_width=640,
        source_height=480,
        coordinate_convention="source_pixels_p53_contract",
        selected_physical_target_label="black_shirt_person",
        annotator="tester",
        created_date="2026-08-09",
    )
    base.update(overrides)
    return PTR.PhysicalReferenceProvenance(**base)


def _artifact(samples, **provenance_overrides):
    return PTR.PhysicalReferenceArtifact(
        provenance=_provenance(**provenance_overrides), samples=tuple(samples)
    )


def _out(t_s, bbox, track_id=1):
    return EV.OutputSample(t_s=t_s, track_id=track_id, bbox_xyxy=bbox)


TARGET_ONLY = PTR.CONTEXT_TARGET_ONLY
DIST_COMPLETE = PTR.CONTEXT_DISTRACTORS_COMPLETE
SCORED = PTR.STATE_PRESENT_SCORED
UNAVAILABLE = PTR.STATE_PRESENT_REFERENCE_UNAVAILABLE
ABSENT = PTR.STATE_ABSENT


# --- 1/20: perfect target localisation -----------------------------------


def test_perfect_localisation_is_identity_target_iou_1_centre_error_0():
    box = (100.0, 100.0, 200.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, box),
            _ref_sample(1.0, SCORED, TARGET_ONLY, box),
        ]
    )
    outputs = [_out(0.0, box)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.correct_target_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.localisation_scored_duration_s == pytest.approx(1.0)
    assert result.localisation.iou_min == pytest.approx(1.0)
    assert result.localisation.iou_duration_weighted_mean == pytest.approx(1.0)
    assert result.localisation.centre_error_px_median == pytest.approx(0.0)
    assert result.localisation.centre_error_ref_h_median == pytest.approx(0.0)


# --- 2/20: poor localisation, still identity_target -----------------------


def test_poor_localisation_remains_identity_target_low_iou_retained():
    target = (100.0, 100.0, 200.0, 300.0)
    poor_output = (150.0, 250.0, 210.0, 320.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target),
        ]
    )
    outputs = [_out(0.0, poor_output)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.correct_target_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0
    assert result.localisation.iou_duration_weighted_mean < 0.5
    assert result.localisation.iou_duration_weighted_mean > 0.0
    assert result.localisation.centre_error_px_median > 0.0


# --- 3/20: zero overlap under explicit target_only -------------------------


def test_zero_overlap_under_target_only_is_still_target_and_scored():
    target = (100.0, 100.0, 200.0, 300.0)
    disjoint_output = (500.0, 100.0, 600.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target),
        ]
    )
    outputs = [_out(0.0, disjoint_output)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.correct_target_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.localisation_scored_duration_s == pytest.approx(1.0)
    assert result.localisation.iou_min == pytest.approx(0.0)
    assert result.localisation.iou_duration_weighted_mean == pytest.approx(0.0)


# --- 4/20: distractor wins --------------------------------------------------


def test_distractor_win_is_wrong_person_with_no_stage_b_contribution():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(1.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )
    outputs = [_out(0.0, distractor)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.wrong_person_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.localisation_scored_duration_s == 0.0
    assert result.localisation.n_samples == 0


# --- 5/20: high target IoU but distractor even better -----------------------


def test_high_target_iou_beaten_by_distractor_is_wrong_person():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (102.0, 100.0, 202.0, 300.0)
    output = distractor  # sits exactly on the distractor
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(1.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )
    outputs = [_out(0.0, output)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    target_iou = EV.bbox_iou(output, target)
    assert target_iou > 0.9  # would pass a naive single-sided threshold
    assert result.duration_buckets.wrong_person_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.correct_target_output_duration_s == 0.0


# --- 6/20 & 7/20: tie / all-zero multi-person is unresolved -----------------


def test_exact_tie_is_identity_unresolved():
    output = (150.0, 100.0, 250.0, 300.0)
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (200.0, 100.0, 300.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(1.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )
    outputs = [_out(0.0, output)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.identity_unresolved_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.localisation_scored_duration_s == 0.0


def test_all_zero_overlap_multi_person_is_identity_unresolved():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    output = (250.0, 100.0, 350.0, 300.0)  # overlaps nobody
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(1.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )
    outputs = [_out(0.0, output)]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.identity_unresolved_duration_s == pytest.approx(1.0)


# --- 8/20: no output while target present -----------------------------------


def test_no_output_while_target_present_is_lost_or_suppressed():
    target = (100.0, 100.0, 200.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target),
        ]
    )
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=[], step_s=0.5
    )

    assert result.duration_buckets.lost_or_suppressed_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0


# --- 9/20 & 10/20: target absence --------------------------------------------


def test_target_absent_no_output():
    reference = _artifact([_ref_sample(0.0, ABSENT), _ref_sample(1.0, ABSENT)])
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=[], step_s=0.5
    )

    assert result.duration_buckets.target_absent_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.target_absent_with_output_duration_s == 0.0


def test_target_absent_with_output_is_a_distinct_safety_condition():
    reference = _artifact([_ref_sample(0.0, ABSENT), _ref_sample(1.0, ABSENT)])
    outputs = [_out(0.0, (10.0, 10.0, 20.0, 30.0))]
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.target_absent_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.target_absent_with_output_duration_s == pytest.approx(1.0)
    # Never collapsed into ordinary localisation error:
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0
    assert result.localisation.n_samples == 0


# --- 11/20: reference unavailable -------------------------------------------


def test_reference_unavailable_ignores_any_output():
    reference = _artifact(
        [_ref_sample(0.0, UNAVAILABLE), _ref_sample(1.0, UNAVAILABLE)]
    )
    outputs = [_out(0.0, (10.0, 10.0, 20.0, 30.0))]
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.5
    )

    assert result.duration_buckets.reference_unavailable_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.correct_target_output_duration_s == 0.0
    assert result.duration_buckets.wrong_person_output_duration_s == 0.0
    assert result.duration_buckets.target_absent_duration_s == 0.0
    assert result.localisation.n_samples == 0


# --- 12/20 & 13/20: interpolation join behaviour -----------------------------


def test_interpolation_between_target_only_keyframes_is_linear():
    reference = PTR.PhysicalReferenceArtifact(
        provenance=_provenance(),
        samples=(
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(
                10.0,
                SCORED,
                TARGET_ONLY,
                (100.0, 0.0, 110.0, 10.0),
                interpolate=True,
            ),
        ),
    )

    resolved = EV.resolve_reference_at(reference.samples, 5.0)
    assert resolved is not None
    assert resolved.target_bbox_xyxy == pytest.approx((50.0, 0.0, 60.0, 10.0))


def test_no_interpolation_flag_holds_previous_bbox_step_function():
    reference = PTR.PhysicalReferenceArtifact(
        provenance=_provenance(),
        samples=(
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(
                10.0, SCORED, TARGET_ONLY, (100.0, 0.0, 110.0, 10.0)
            ),  # interpolate=False (default)
        ),
    )

    resolved_mid = EV.resolve_reference_at(reference.samples, 5.0)
    assert resolved_mid is not None
    assert resolved_mid.target_bbox_xyxy == (0.0, 0.0, 10.0, 10.0)  # held, not lerped

    resolved_at_boundary = EV.resolve_reference_at(reference.samples, 10.0)
    assert resolved_at_boundary is None  # outside the covered span: [0, 10)


def test_reference_resolution_outside_covered_span_is_none():
    reference_samples = (
        _ref_sample(5.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
        _ref_sample(10.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
    )
    assert EV.resolve_reference_at(reference_samples, 4.999) is None
    assert EV.resolve_reference_at(reference_samples, 10.0) is None
    assert EV.resolve_reference_at(reference_samples, 7.0) is not None


# --- 14/20: provenance/hash recorded in the report --------------------------


def test_build_report_records_provenance_and_reconciliation():
    target = (100.0, 100.0, 200.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target),
        ]
    )
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=[_out(0.0, target)], step_s=0.5
    )

    report = EV.build_report(
        result=result,
        stream_name="tim_target_memory",
        provenance=reference.provenance,
        physical_reference_path="docs/data/physical_target_references/dev_test_sequence.json",
        physical_reference_sha256="a" * 64,
        repo_commit="0" * 40,
        repo_dirty=False,
    )

    assert report["schema_version"] == 1
    assert report["contract_version"] == "tim_physical_target_bbox_v1"
    assert report["physical_reference_sha256"] == "a" * 64
    assert report["repo_commit"] == "0" * 40
    assert report["repo_dirty"] is False
    assert report["source_bag_name"] == "test_bag"
    assert report["reconciliation"]["ok"] is True


# --- 15/20: fails closed on a degenerate reference --------------------------


def test_fails_closed_on_single_sample_reference():
    reference = _artifact([_ref_sample(0.0, ABSENT)])
    with pytest.raises(ValueError, match="at least two keyframes"):
        EV.evaluate_physical_target_bbox(reference=reference, output_samples=[])


# --- 16/20: timestamp boundary / join behaviour ------------------------------


def test_latest_output_at_uses_latest_preceding_sample_not_future_one():
    outputs = [_out(0.0, (0.0, 0.0, 10.0, 10.0)), _out(2.0, (5.0, 5.0, 15.0, 15.0))]
    at_1s = EV.latest_output_at(outputs, 1.0, max_output_age_s=5.0)
    assert at_1s is not None
    assert at_1s.bbox_xyxy == (0.0, 0.0, 10.0, 10.0)


def test_latest_output_at_returns_none_when_stale():
    outputs = [_out(0.0, (0.0, 0.0, 10.0, 10.0))]
    stale = EV.latest_output_at(outputs, 5.0, max_output_age_s=0.9)
    assert stale is None


def test_grid_never_evaluates_at_or_beyond_the_final_keyframe():
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
            _ref_sample(1.0, SCORED, TARGET_ONLY, (0.0, 0.0, 10.0, 10.0)),
        ]
    )
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=[_out(0.0, (0.0, 0.0, 10.0, 10.0))], step_s=0.3
    )
    # 0.3+0.3+0.3+0.1 = 1.0 exactly, last tick clipped to reach the boundary
    assert result.total_evaluated_duration_s == pytest.approx(1.0)


# --- 17/20: regenerated tracker-ID invariance --------------------------------


def test_regenerated_tracker_id_invariance_end_to_end():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    output_bbox = (101.0, 100.0, 201.0, 300.0)

    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(2.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )

    result_run_1 = EV.evaluate_physical_target_bbox(
        reference=reference,
        output_samples=[_out(0.0, output_bbox, track_id=1)],
        step_s=0.5,
    )
    result_run_2 = EV.evaluate_physical_target_bbox(
        reference=reference,
        output_samples=[_out(0.0, output_bbox, track_id=69)],
        step_s=0.5,
    )

    assert result_run_1.duration_buckets == result_run_2.duration_buckets
    assert result_run_1.localisation == result_run_2.localisation
    assert result_run_1.reconciliation_ok == result_run_2.reconciliation_ok


def test_module_source_never_references_correct_target_track_id():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "analysis"
        / "physical_target_bbox_evaluation.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "correct_target_track_id" not in source


def test_output_sample_track_id_is_never_read_by_evaluation_functions():
    source = inspect.getsource(EV.evaluate_physical_target_bbox)
    source += inspect.getsource(EV.latest_output_at)
    source += inspect.getsource(EV.resolve_reference_at)
    assert ".track_id" not in source


# --- 18/20: duration accounting reconciliation -------------------------------


def test_duration_reconciliation_across_mixed_segments():
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (400.0, 100.0, 500.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, ABSENT),
            _ref_sample(1.0, UNAVAILABLE),
            _ref_sample(2.0, SCORED, TARGET_ONLY, target),
            _ref_sample(3.0, SCORED, DIST_COMPLETE, target, [distractor]),
            _ref_sample(4.0, SCORED, DIST_COMPLETE, target, [distractor]),
        ]
    )
    outputs = [
        _out(2.0, target),  # correct, target_only segment
        _out(3.0, distractor),  # wrong_person, distractors_complete segment
    ]

    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=outputs, step_s=0.25
    )

    assert result.reconciliation_ok is True
    assert result.reconciliation_residual_s < 1e-9
    assert result.duration_buckets.primary_total_s() == pytest.approx(
        result.total_evaluated_duration_s
    )
    assert result.duration_buckets.target_absent_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.reference_unavailable_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.correct_target_output_duration_s == pytest.approx(1.0)
    assert result.duration_buckets.wrong_person_output_duration_s == pytest.approx(1.0)


# --- 19/20: numeric centre-error formula -------------------------------------


def test_centre_error_px_formula():
    output = (0.0, 0.0, 10.0, 10.0)  # centre (5, 5)
    target = (6.0, 8.0, 16.0, 18.0)  # centre (11, 13)
    # dx=6, dy=8 -> distance 10
    assert EV.centre_error_px(output, target) == pytest.approx(10.0)


def test_centre_error_ref_h_uses_reference_height_not_output_height():
    output = (0.0, 0.0, 10.0, 100.0)  # tall output, height 100
    target = (5.0, 5.0, 15.0, 25.0)  # reference height 20, centre (10, 15)
    # output centre (5, 50); dx=5, dy=35 -> px = sqrt(25+1225)=sqrt(1250)
    expected_px = (5.0 ** 2 + 35.0 ** 2) ** 0.5
    assert EV.centre_error_px(output, target) == pytest.approx(expected_px)
    assert EV.centre_error_ref_h(output, target) == pytest.approx(expected_px / 20.0)
    # Explicitly not divided by the output's own (100px) height:
    assert EV.centre_error_ref_h(output, target) != pytest.approx(expected_px / 100.0)


# --- 20/20: numeric IoU formula (Stage B propagation) ------------------------


def test_stage_b_iou_matches_bbox_iou_primitive():
    target = (100.0, 100.0, 200.0, 300.0)
    output = (150.0, 100.0, 250.0, 300.0)
    reference = _artifact(
        [
            _ref_sample(0.0, SCORED, TARGET_ONLY, target),
            _ref_sample(1.0, SCORED, TARGET_ONLY, target),
        ]
    )
    result = EV.evaluate_physical_target_bbox(
        reference=reference, output_samples=[_out(0.0, output)], step_s=1.0
    )

    expected_iou = EV.bbox_iou(output, target)
    assert result.localisation.iou_duration_weighted_mean == pytest.approx(expected_iou)
