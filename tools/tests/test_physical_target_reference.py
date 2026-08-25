"""Focused tests for the tim_physical_target_bbox_v1 schema, validator, and
Stage A identity attribution rule (docs/issues/p1-10-improve-bbox-evaluation.md).

Corrected after review of the first version: Stage A must attribute
identity (WHO) without any minimum localisation-quality threshold (HOW
WELL is Stage B's separate question). These tests exist specifically to
prove that separation, not just to exercise the schema.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "physical_target_reference.py"
)

SPEC = importlib.util.spec_from_file_location(
    "physical_target_reference",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

PTR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PTR
SPEC.loader.exec_module(PTR)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = (
    REPO_ROOT
    / "tools"
    / "analysis"
    / "templates"
    / "physical_target_reference_template.json"
)


def _provenance(**overrides) -> dict:
    base = {
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
    }
    base.update(overrides)
    return base


def _sample(
    t_s: float,
    identity_state: str,
    identity_context: str | None = None,
    target_bbox_xyxy=None,
    distractor_bboxes_xyxy=None,
    interpolate_from_previous: bool = False,
) -> dict:
    return {
        "t_s": t_s,
        "identity_state": identity_state,
        "identity_context": identity_context,
        "target_bbox_xyxy": target_bbox_xyxy,
        "distractor_bboxes_xyxy": distractor_bboxes_xyxy or [],
        "interpolate_from_previous": interpolate_from_previous,
    }


def _target_only_sample(t_s, bbox, **kwargs) -> dict:
    return _sample(t_s, PTR.STATE_PRESENT_SCORED, PTR.CONTEXT_TARGET_ONLY, bbox, **kwargs)


def _distractors_complete_sample(t_s, bbox, distractors, **kwargs) -> dict:
    return _sample(
        t_s,
        PTR.STATE_PRESENT_SCORED,
        PTR.CONTEXT_DISTRACTORS_COMPLETE,
        bbox,
        distractor_bboxes_xyxy=distractors,
        **kwargs,
    )


def _artifact(samples: list[dict], **provenance_overrides) -> dict:
    return {"provenance": _provenance(**provenance_overrides), "samples": samples}


# 1. valid visible target bbox --------------------------------------------


def test_valid_present_scored_target_only_sample_parses():
    data = _artifact([_target_only_sample(0.0, [100.0, 100.0, 200.0, 300.0])])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    assert artifact.samples[0].identity_state == PTR.STATE_PRESENT_SCORED
    assert artifact.samples[0].identity_context == PTR.CONTEXT_TARGET_ONLY
    assert artifact.samples[0].target_bbox_xyxy == (100.0, 100.0, 200.0, 300.0)


def test_valid_present_scored_distractors_complete_sample_parses():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [100.0, 100.0, 200.0, 300.0],
                [[400.0, 100.0, 500.0, 300.0]],
            )
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].identity_context == PTR.CONTEXT_DISTRACTORS_COMPLETE
    assert len(artifact.samples[0].distractor_bboxes_xyxy) == 1


# 2. target absent with no bbox --------------------------------------------


def test_target_absent_requires_no_bbox():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT)])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].target_bbox_xyxy is None
    assert artifact.samples[0].identity_context is None


def test_target_absent_with_bbox_is_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_ABSENT, target_bbox_xyxy=[1.0, 1.0, 2.0, 2.0])]
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


def test_target_absent_with_identity_context_is_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT, identity_context="target_only")])
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="identity_context"):
        PTR.parse_physical_reference(data)


# 3. visible/present-but-unscored reference case ---------------------------


def test_present_reference_unavailable_requires_no_bbox():
    data = _artifact([_sample(0.0, PTR.STATE_PRESENT_REFERENCE_UNAVAILABLE)])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].target_bbox_xyxy is None


def test_present_scored_without_bbox_is_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, PTR.CONTEXT_TARGET_ONLY)]
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


def test_present_scored_without_identity_context_is_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, None, [1.0, 1.0, 2.0, 2.0])]
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="identity_context"):
        PTR.parse_physical_reference(data)


# 4. malformed bbox ----------------------------------------------------------


def test_malformed_bbox_ordering_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [100.0, 100.0, 100.0, 300.0])]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="non-positive area"):
        PTR.validate_physical_reference(artifact)


def test_bbox_wrong_length_rejected():
    data = _artifact([_target_only_sample(0.0, [1.0, 2.0, 3.0])])
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


# 5. out-of-bounds bbox -------------------------------------------------------


def test_out_of_bounds_bbox_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [100.0, 100.0, 700.0, 300.0])]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(
        PTR.PhysicalReferenceValidationError, match="outside the declared source frame"
    ):
        PTR.validate_physical_reference(artifact)


# 6. missing required provenance ---------------------------------------------


def test_missing_required_provenance_field_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT)])
    del data["provenance"]["source_width"]
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="missing required fields"):
        PTR.parse_physical_reference(data)


# 7. invalid state -------------------------------------------------------------


def test_invalid_identity_state_rejected():
    data = _artifact([_sample(0.0, "somewhere_else_entirely")])
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="identity_state"):
        PTR.parse_physical_reference(data)


def test_invalid_identity_context_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, "somehow_both", [1.0, 1.0, 2.0, 2.0])]
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="identity_context"):
        PTR.parse_physical_reference(data)


# 8. timestamp ordering ---------------------------------------------------------


def test_non_monotonic_timestamps_rejected():
    data = _artifact(
        [
            _sample(5.0, PTR.STATE_ABSENT),
            _sample(5.0, PTR.STATE_ABSENT),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="strictly greater"):
        PTR.validate_physical_reference(artifact)


def test_decreasing_timestamps_rejected():
    data = _artifact(
        [
            _sample(5.0, PTR.STATE_ABSENT),
            _sample(4.0, PTR.STATE_ABSENT),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="strictly greater"):
        PTR.validate_physical_reference(artifact)


# 9. illegal interpolation across absence/unscored/contested boundaries --------


def test_interpolation_across_absence_is_rejected():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _sample(1.0, PTR.STATE_ABSENT),
            _target_only_sample(
                2.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="interpolate_from_previous"):
        PTR.validate_physical_reference(artifact)


def test_interpolation_on_first_sample_is_rejected():
    data = _artifact(
        [
            _target_only_sample(
                0.0, [10.0, 10.0, 20.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="no predecessor"):
        PTR.validate_physical_reference(artifact)


def test_interpolation_between_two_target_only_samples_is_legal():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _target_only_sample(
                1.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)  # must not raise


def test_interpolation_from_distractors_complete_predecessor_is_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [[9.0, 9.0, 19.0, 29.0]],
            ),
            _target_only_sample(
                1.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="interpolate_from_previous"):
        PTR.validate_physical_reference(artifact)


def test_interpolation_into_distractors_complete_successor_is_rejected():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [[9.0, 9.0, 19.0, 29.0]],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="interpolate_from_previous"):
        PTR.validate_physical_reference(artifact)


# 10. no dependency on a tracker ID; annotation completeness --------------------


def test_bare_integer_label_rejected_as_physical_identity():
    data = _artifact(
        [_sample(0.0, PTR.STATE_ABSENT)],
        selected_physical_target_label="7",
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="bare tracker ID"):
        PTR.parse_physical_reference(data)


def test_descriptive_physical_label_is_accepted():
    data = _artifact(
        [_sample(0.0, PTR.STATE_ABSENT)],
        selected_physical_target_label="black_shirt_person",
    )
    artifact = PTR.parse_physical_reference(data)
    assert artifact.provenance.selected_physical_target_label == "black_shirt_person"


def test_empty_sequence_id_is_rejected():
    """A physical-reference artifact must carry a deliberate sequence
    identity -- an empty sequence_id (e.g. a smoke-test artifact saved
    without filling in the form) is never valid, regardless of path."""
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT)], sequence_id="")
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="sequence_id"):
        PTR.parse_physical_reference(data)


def test_whitespace_only_sequence_id_is_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT)], sequence_id="   ")
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="sequence_id"):
        PTR.parse_physical_reference(data)


def test_classify_identity_stage_a_signature_has_no_tracker_id_or_threshold_parameter():
    params = set(inspect.signature(PTR.classify_identity_stage_a).parameters)
    assert not any("track" in name.lower() or name.lower() == "id" for name in params)
    assert not any("threshold" in name.lower() for name in params)


# 7 (review). target_only with non-empty distractors is rejected ---------------


def test_target_only_context_with_distractors_is_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR.STATE_PRESENT_SCORED,
                PTR.CONTEXT_TARGET_ONLY,
                [10.0, 10.0, 20.0, 30.0],
                distractor_bboxes_xyxy=[[40.0, 10.0, 50.0, 30.0]],
            )
        ]
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="target_only"):
        PTR.parse_physical_reference(data)


def test_distractors_complete_context_with_no_distractors_is_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR.STATE_PRESENT_SCORED,
                PTR.CONTEXT_DISTRACTORS_COMPLETE,
                [10.0, 10.0, 20.0, 30.0],
            )
        ]
    )
    with pytest.raises(
        PTR.PhysicalReferenceValidationError, match="distractors_complete"
    ):
        PTR.parse_physical_reference(data)


# 8 (review). empty distractor list under explicit target-only context ---------


def test_empty_distractor_list_under_target_only_is_valid_and_deliberate():
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].distractor_bboxes_xyxy == ()
    assert artifact.samples[0].identity_context == PTR.CONTEXT_TARGET_ONLY


# 11. deterministic parse/serialize/validate ------------------------------------


def test_serialize_round_trip_is_deterministic():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _distractors_complete_sample(
                1.0, [12.0, 10.0, 22.0, 30.0], [[11.0, 10.0, 21.0, 30.0]]
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    first = PTR.serialize_physical_reference(artifact)
    second = PTR.serialize_physical_reference(PTR.parse_physical_reference(first))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_write_then_load_round_trip(tmp_path):
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    out_path = tmp_path / "artifact.json"
    PTR.write_physical_reference(out_path, artifact)

    reloaded = PTR.load_physical_reference(out_path)
    assert reloaded == artifact

    out_path_2 = tmp_path / "artifact_2.json"
    PTR.write_physical_reference(out_path_2, reloaded)
    assert out_path.read_text() == out_path_2.read_text()


# 12. historical coordinate metadata --------------------------------------------


def test_historical_convention_requires_evidence():
    data = _artifact(
        [_sample(0.0, PTR.STATE_ABSENT)],
        coordinate_convention="source_pixels_historical_pre_p53",
    )
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="coordinate_convention_evidence"):
        PTR.parse_physical_reference(data)


def test_historical_convention_with_evidence_is_accepted():
    data = _artifact(
        [_sample(0.0, PTR.STATE_ABSENT)],
        coordinate_convention="source_pixels_historical_pre_p53",
        coordinate_convention_evidence=(
            "Verified via direct bag inspection: /detections header.frame_id="
            "'frame_103' carries no tim_mars_source_pixels_resize_v1 contract "
            "string; bag predates Issue #53's 2026-07-22 closure."
        ),
    )
    artifact = PTR.parse_physical_reference(data)
    assert (
        artifact.provenance.coordinate_convention
        == "source_pixels_historical_pre_p53"
    )


def test_template_artifact_loads_and_validates():
    artifact = PTR.load_physical_reference(TEMPLATE_PATH)
    assert artifact.provenance.contract_version == PTR.CONTRACT_VERSION
    assert len(artifact.samples) >= 1


# --- Stage A identity attribution: WHO, independent of localisation quality ---


def test_classify_identity_target_only_correct_when_output_matches_well():
    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_TARGET_ONLY,
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[],
        output_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
    )
    assert result == PTR.IDENTITY_TARGET


def test_case_1_poor_localisation_remains_identity_target_when_target_only():
    """Corrected-rule test #1: a single-target context with badly localised
    output must still be identity_target -- poor geometry is a Stage B
    question, not a Stage A one."""
    target = (100.0, 100.0, 200.0, 300.0)
    poorly_localised_output = (150.0, 250.0, 210.0, 320.0)  # small overlap only

    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_TARGET_ONLY,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=[],
        output_bbox_xyxy=poorly_localised_output,
    )

    target_iou = PTR.bbox_iou(poorly_localised_output, target)
    assert target_iou < 0.5  # would have failed the old threshold
    assert result == PTR.IDENTITY_TARGET  # but identity attribution is unaffected


def test_case_1b_zero_overlap_still_identity_target_when_target_only():
    """Even zero overlap is identity_target under target_only: there is no
    alternative physical explanation, so the output is attributed to the
    target and Stage B is left to report IoU 0.0 honestly."""
    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_TARGET_ONLY,
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[],
        output_bbox_xyxy=(500.0, 100.0, 600.0, 300.0),  # disjoint from target
    )
    assert result == PTR.IDENTITY_TARGET


def test_case_2_symmetric_zero_overlap_with_distractors_is_unresolved_not_wrong():
    """Corrected-rule test #2: with distractors recorded, an output that
    overlaps neither the target nor any distractor is unresolved -- there is
    no geometric basis to call it a specific wrong person."""
    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[(400.0, 100.0, 500.0, 300.0)],
        output_bbox_xyxy=(250.0, 100.0, 350.0, 300.0),  # overlaps nobody
    )
    assert result == PTR.IDENTITY_UNRESOLVED


def test_case_3_distractor_assignment_is_genuine_wrong_person():
    """Corrected-rule test #3: output clearly, unambiguously matches the
    distractor and not the target."""
    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[(400.0, 100.0, 500.0, 300.0)],
        output_bbox_xyxy=(400.0, 100.0, 500.0, 300.0),  # == distractor exactly
    )
    assert result == PTR.IDENTITY_WRONG_PERSON


def test_case_4_high_target_iou_alone_is_not_sufficient_during_a_crossing():
    """Retained core protection: a bbox that overlaps the target well but
    overlaps a distractor at least as well must NOT be scored correct --
    proven here with no threshold anywhere in the implementation.
    """
    target = (100.0, 100.0, 200.0, 300.0)
    # A distractor bbox nearly identical to (and overlapping) the target,
    # simulating a close crossing.
    distractor = (102.0, 100.0, 202.0, 300.0)
    # The published output sits exactly on the distractor, not the target,
    # but still has high IoU against the target because the two people are
    # side by side.
    output = distractor

    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=[distractor],
        output_bbox_xyxy=output,
    )

    target_iou = PTR.bbox_iou(output, target)
    assert target_iou > 0.9  # a naive single-sided threshold would have passed
    assert result == PTR.IDENTITY_WRONG_PERSON  # the margin rule correctly rejects it


def test_case_5_target_wins_relatively_despite_low_absolute_iou():
    """Corrected-rule test #5: target is the unique relative winner even
    though its absolute IoU is low; the low IoU must remain available to
    Stage B (this test only proves the Stage A verdict; the evaluator that
    reports Stage B numbers is a later milestone)."""
    target = (100.0, 100.0, 200.0, 300.0)
    distractor = (600.0, 100.0, 700.0, 300.0)  # far away, no overlap at all
    output = (105.0, 280.0, 205.0, 320.0)  # weak overlap with target only

    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=[distractor],
        output_bbox_xyxy=output,
    )

    target_iou = PTR.bbox_iou(output, target)
    assert 0.0 < target_iou < 0.5  # below the old (removed) threshold
    assert result == PTR.IDENTITY_TARGET


def test_case_6_exact_tie_is_unresolved_not_target_and_not_wrong():
    """Corrected-rule test #6: target and distractor achieve identical
    nonzero IoU against the output -- genuinely indeterminate."""
    output = (150.0, 100.0, 250.0, 300.0)
    target = (100.0, 100.0, 200.0, 300.0)
    # Constructed so the distractor yields the exact same IoU as the target
    # against this output (mirrored across the output's own span).
    distractor = (200.0, 100.0, 300.0, 300.0)

    target_iou = PTR.bbox_iou(output, target)
    distractor_iou = PTR.bbox_iou(output, distractor)
    assert target_iou == pytest.approx(distractor_iou)
    assert target_iou > 0.0

    result = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=[distractor],
        output_bbox_xyxy=output,
    )
    assert result == PTR.IDENTITY_UNRESOLVED


def test_classify_identity_requires_at_least_one_distractor_for_distractors_complete():
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="at least one"):
        PTR.classify_identity_stage_a(
            identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
            target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
            distractor_bboxes_xyxy=[],
            output_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        )


# --- Regenerated tracker-ID invariance (section O) -------------------------


def test_regenerated_tracker_id_invariance():
    """Two synthetic 'runs' publish the identical physical trajectory under
    disjoint ID numbering; classify_identity_stage_a must be computable
    without touching the physical-reference boxes and must return an
    identical verdict, because it never receives an ID at all.
    """
    target = (100.0, 100.0, 200.0, 300.0)
    distractors = [(400.0, 100.0, 500.0, 300.0)]
    output_bbox = (101.0, 100.0, 201.0, 300.0)

    run_1_output = {"tracker_id": 1, "bbox_xyxy": output_bbox}
    run_2_output = {"tracker_id": 69, "bbox_xyxy": output_bbox}  # regenerated ID

    result_1 = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=distractors,
        output_bbox_xyxy=run_1_output["bbox_xyxy"],
    )
    result_2 = PTR.classify_identity_stage_a(
        identity_context=PTR.CONTEXT_DISTRACTORS_COMPLETE,
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=distractors,
        output_bbox_xyxy=run_2_output["bbox_xyxy"],
    )

    assert result_1 == result_2 == PTR.IDENTITY_TARGET
    assert run_1_output["tracker_id"] != run_2_output["tracker_id"]
