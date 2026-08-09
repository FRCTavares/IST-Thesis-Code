"""Focused tests for the tim_physical_target_bbox_v1 schema, validator, and
Stage A identity classifier (docs/issues/p1-10-improve-bbox-evaluation.md).
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
    target_bbox_xyxy=None,
    distractor_bboxes_xyxy=None,
    interpolate_from_previous: bool = False,
) -> dict:
    return {
        "t_s": t_s,
        "identity_state": identity_state,
        "target_bbox_xyxy": target_bbox_xyxy,
        "distractor_bboxes_xyxy": distractor_bboxes_xyxy or [],
        "interpolate_from_previous": interpolate_from_previous,
    }


def _artifact(samples: list[dict], **provenance_overrides) -> dict:
    return {"provenance": _provenance(**provenance_overrides), "samples": samples}


# 1. valid visible target bbox --------------------------------------------


def test_valid_present_scored_sample_parses():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, [100.0, 100.0, 200.0, 300.0])]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    assert artifact.samples[0].identity_state == PTR.STATE_PRESENT_SCORED
    assert artifact.samples[0].target_bbox_xyxy == (100.0, 100.0, 200.0, 300.0)


# 2. target absent with no bbox --------------------------------------------


def test_target_absent_requires_no_bbox():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT)])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].target_bbox_xyxy is None


def test_target_absent_with_bbox_is_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_ABSENT, [1.0, 1.0, 2.0, 2.0])])
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


# 3. visible/present-but-unscored reference case ---------------------------


def test_present_reference_unavailable_requires_no_bbox():
    data = _artifact([_sample(0.0, PTR.STATE_PRESENT_REFERENCE_UNAVAILABLE)])
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)
    assert artifact.samples[0].target_bbox_xyxy is None


def test_present_scored_without_bbox_is_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_PRESENT_SCORED)])
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


# 4. malformed bbox ----------------------------------------------------------


def test_malformed_bbox_ordering_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, [100.0, 100.0, 100.0, 300.0])]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="non-positive area"):
        PTR.validate_physical_reference(artifact)


def test_bbox_wrong_length_rejected():
    data = _artifact([_sample(0.0, PTR.STATE_PRESENT_SCORED, [1.0, 2.0, 3.0])])
    with pytest.raises(PTR.PhysicalReferenceValidationError):
        PTR.parse_physical_reference(data)


# 5. out-of-bounds bbox -------------------------------------------------------


def test_out_of_bounds_bbox_rejected():
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, [100.0, 100.0, 700.0, 300.0])]
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


# 9. illegal interpolation across absence/unscored boundary --------------------


def test_interpolation_across_absence_is_rejected():
    data = _artifact(
        [
            _sample(0.0, PTR.STATE_PRESENT_SCORED, [10.0, 10.0, 20.0, 30.0]),
            _sample(1.0, PTR.STATE_ABSENT),
            _sample(
                2.0,
                PTR.STATE_PRESENT_SCORED,
                [12.0, 10.0, 22.0, 30.0],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="interpolate_from_previous"):
        PTR.validate_physical_reference(artifact)


def test_interpolation_on_first_sample_is_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR.STATE_PRESENT_SCORED,
                [10.0, 10.0, 20.0, 30.0],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="no predecessor"):
        PTR.validate_physical_reference(artifact)


def test_interpolation_between_two_present_scored_samples_is_legal():
    data = _artifact(
        [
            _sample(0.0, PTR.STATE_PRESENT_SCORED, [10.0, 10.0, 20.0, 30.0]),
            _sample(
                1.0,
                PTR.STATE_PRESENT_SCORED,
                [12.0, 10.0, 22.0, 30.0],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)  # must not raise


def test_interpolation_from_ambiguous_predecessor_is_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR.STATE_PRESENT_AMBIGUOUS,
                [10.0, 10.0, 20.0, 30.0],
                distractor_bboxes_xyxy=[[9.0, 9.0, 19.0, 29.0]],
            ),
            _sample(
                1.0,
                PTR.STATE_PRESENT_SCORED,
                [12.0, 10.0, 22.0, 30.0],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    with pytest.raises(PTR.PhysicalReferenceValidationError, match="interpolate_from_previous"):
        PTR.validate_physical_reference(artifact)


# 10. no dependency on a tracker ID ---------------------------------------------


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


def test_classify_identity_stage_a_signature_has_no_tracker_id_parameter():
    params = set(inspect.signature(PTR.classify_identity_stage_a).parameters)
    assert not any("track" in name.lower() or name.lower() == "id" for name in params)


# 11. deterministic parse/serialize/validate ------------------------------------


def test_serialize_round_trip_is_deterministic():
    data = _artifact(
        [
            _sample(0.0, PTR.STATE_PRESENT_SCORED, [10.0, 10.0, 20.0, 30.0]),
            _sample(
                1.0,
                PTR.STATE_PRESENT_AMBIGUOUS,
                [12.0, 10.0, 22.0, 30.0],
                distractor_bboxes_xyxy=[[11.0, 10.0, 21.0, 30.0]],
            ),
        ]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    first = PTR.serialize_physical_reference(artifact)
    second = PTR.serialize_physical_reference(PTR.parse_physical_reference(first))

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_write_then_load_round_trip(tmp_path):
    data = _artifact(
        [_sample(0.0, PTR.STATE_PRESENT_SCORED, [10.0, 10.0, 20.0, 30.0])]
    )
    artifact = PTR.parse_physical_reference(data)
    PTR.validate_physical_reference(artifact)

    out_path = tmp_path / "artifact.json"
    PTR.write_physical_reference(out_path, artifact)

    reloaded = PTR.load_physical_reference(out_path)
    assert reloaded == artifact

    # A second write from the reloaded artifact must byte-match the first.
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
    assert not artifact.provenance.contract_version == ""  # sanity: still parsed


def test_template_artifact_loads_and_validates():
    artifact = PTR.load_physical_reference(TEMPLATE_PATH)
    assert artifact.provenance.contract_version == PTR.CONTRACT_VERSION
    assert len(artifact.samples) >= 1


# --- Stage A identity classifier ------------------------------------------


def test_classify_identity_no_distractors_correct_when_above_threshold():
    result = PTR.classify_identity_stage_a(
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[],
        output_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
    )
    assert result == PTR.IDENTITY_CORRECT


def test_classify_identity_no_distractors_wrong_when_below_threshold():
    result = PTR.classify_identity_stage_a(
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[],
        output_bbox_xyxy=(500.0, 100.0, 600.0, 300.0),
    )
    assert result == PTR.IDENTITY_WRONG


def test_classify_identity_with_distractor_correct_when_target_clearly_wins():
    result = PTR.classify_identity_stage_a(
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[(400.0, 100.0, 500.0, 300.0)],
        output_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
    )
    assert result == PTR.IDENTITY_CORRECT


def test_classify_identity_high_iou_alone_is_not_sufficient_during_a_crossing():
    """The exact non-negotiable rule: a bbox that overlaps the target well
    but overlaps a distractor at least as well must NOT be scored correct.
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
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=[distractor],
        output_bbox_xyxy=output,
    )

    target_iou = PTR.bbox_iou(output, target)
    assert target_iou >= PTR.DEFAULT_IDENTITY_IOU_THRESHOLD  # would pass a naive threshold
    assert result == PTR.IDENTITY_WRONG  # but the margin rule correctly rejects it


def test_classify_identity_unmatched_when_neither_target_nor_distractor_match():
    result = PTR.classify_identity_stage_a(
        target_bbox_xyxy=(100.0, 100.0, 200.0, 300.0),
        distractor_bboxes_xyxy=[(400.0, 100.0, 500.0, 300.0)],
        output_bbox_xyxy=(250.0, 100.0, 350.0, 300.0),
    )
    assert result == PTR.IDENTITY_UNMATCHED


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
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=distractors,
        output_bbox_xyxy=run_1_output["bbox_xyxy"],
    )
    result_2 = PTR.classify_identity_stage_a(
        target_bbox_xyxy=target,
        distractor_bboxes_xyxy=distractors,
        output_bbox_xyxy=run_2_output["bbox_xyxy"],
    )

    assert result_1 == result_2 == PTR.IDENTITY_CORRECT
    assert run_1_output["tracker_id"] != run_2_output["tracker_id"]
