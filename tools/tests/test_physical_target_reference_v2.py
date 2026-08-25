"""Focused tests for the tim_physical_target_bbox_v2 schema and validator
(docs/issues/p1-10-physical-reference-v2-contract.md).

M1-v2 is schema + validator only. There is no interpolation math, no
duration accounting, and no evaluator here -- those are M2-v2. These tests
exist to prove the frozen contract's structural guarantees: annotation-local
person_ref correspondence (never a tracker ID, never list position),
exact-set-match interpolation legality, an explicit validated evaluation
window, deterministic serialization independent of drawing/input order, and
complete isolation from the unmodified tim_physical_target_bbox_v1 module.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ANALYSIS_DIR = Path(__file__).resolve().parents[1] / "analysis"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ANALYSIS_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PTR1 = _load_module("physical_target_reference", "physical_target_reference.py")
PTR2 = _load_module("physical_target_reference_v2", "physical_target_reference_v2.py")


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH_V2 = (
    REPO_ROOT
    / "tools"
    / "analysis"
    / "templates"
    / "physical_target_reference_v2_template.json"
)
CONTRACT_DOC_PATH = (
    REPO_ROOT / "docs" / "issues" / "p1-10-physical-reference-v2-contract.md"
)


def _provenance(**overrides) -> dict:
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
        "evaluation_window": {"start_s": 0.0, "end_s": 20.0},
    }
    base.update(overrides)
    return base


def _distractor(person_ref: str, bbox) -> dict:
    return {"person_ref": person_ref, "bbox_xyxy": bbox}


def _sample(
    t_s: float,
    identity_state: str,
    identity_context: str | None = None,
    target_bbox_xyxy=None,
    distractors=None,
    interpolate_from_previous: bool = False,
) -> dict:
    return {
        "t_s": t_s,
        "identity_state": identity_state,
        "identity_context": identity_context,
        "target_bbox_xyxy": target_bbox_xyxy,
        "distractors": distractors or [],
        "interpolate_from_previous": interpolate_from_previous,
    }


def _target_only_sample(t_s, bbox, **kwargs) -> dict:
    return _sample(t_s, PTR2.STATE_PRESENT_SCORED, PTR2.CONTEXT_TARGET_ONLY, bbox, **kwargs)


def _distractors_complete_sample(t_s, bbox, distractors, **kwargs) -> dict:
    return _sample(
        t_s,
        PTR2.STATE_PRESENT_SCORED,
        PTR2.CONTEXT_DISTRACTORS_COMPLETE,
        bbox,
        distractors=distractors,
        **kwargs,
    )


def _artifact(samples: list[dict], **provenance_overrides) -> dict:
    return {"provenance": _provenance(**provenance_overrides), "samples": samples}


# 1. v2 contract/version correct -----------------------------------------------


def test_v2_contract_version_correct():
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    artifact = PTR2.parse_physical_reference(data)
    assert artifact.provenance.schema_version == 2
    assert artifact.provenance.contract_version == "tim_physical_target_bbox_v2"


def test_unsupported_schema_version_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])], schema_version=3
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="schema_version"):
        PTR2.parse_physical_reference(data)


# 2/3. evaluation window required and validated ---------------------------------


def test_evaluation_window_required():
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    del data["provenance"]["evaluation_window"]
    with pytest.raises(
        PTR2.PhysicalReferenceValidationError, match="missing required fields"
    ):
        PTR2.parse_physical_reference(data)


def test_evaluation_window_end_before_start_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 10.0, "end_s": 5.0},
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="end_s"):
        PTR2.parse_physical_reference(data)


def test_evaluation_window_equal_start_end_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 5.0, "end_s": 5.0},
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="end_s"):
        PTR2.parse_physical_reference(data)


def test_evaluation_window_negative_start_rejected():
    data = _artifact(
        [_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": -1.0, "end_s": 5.0},
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="non-negative"):
        PTR2.parse_physical_reference(data)


# 4/5. sample outside the declared window rejected (half-open convention) -------


def test_sample_before_evaluation_window_rejected():
    data = _artifact(
        [_target_only_sample(0.5, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 1.0, "end_s": 5.0},
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="evaluation_window"):
        PTR2.validate_physical_reference(artifact)


def test_sample_strictly_after_evaluation_window_end_rejected():
    data = _artifact(
        [_target_only_sample(5.5, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 0.0, "end_s": 5.0},
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="evaluation_window"):
        PTR2.validate_physical_reference(artifact)


def test_sample_exactly_at_evaluation_window_end_is_legal_anchor():
    """Corrected 2026-08-10: t_s == end_s is a legal right-boundary
    interpolation anchor (contract section I) -- the sample anchor domain
    is the closed [start_s, end_s], distinct from the half-open evaluated
    duration domain [start_s, end_s)."""
    data = _artifact(
        [_target_only_sample(5.0, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 0.0, "end_s": 5.0},
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise
    assert artifact.samples[0].t_s == artifact.provenance.evaluation_window.end_s


def test_interpolation_into_a_sample_exactly_at_evaluation_window_end_is_legal():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _target_only_sample(
                5.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ],
        evaluation_window={"start_s": 0.0, "end_s": 5.0},
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise


def test_sample_exactly_at_window_start_is_valid():
    data = _artifact(
        [_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])],
        evaluation_window={"start_s": 0.0, "end_s": 5.0},
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise


# 6-9. person_ref namespace ------------------------------------------------------


def test_valid_person_ref_accepted():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            )
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)
    assert artifact.samples[0].distractors[0].person_ref == "phys_d001"


@pytest.mark.parametrize(
    "bad_ref",
    ["7", "T2", "track_7", "1", "d1", "phys_1", "phys_d1", "phys_d12", "PHYS_D001", ""],
)
def test_tracker_like_or_malformed_person_ref_rejected(bad_ref):
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor(bad_ref, [40.0, 10.0, 50.0, 30.0])],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="person_ref"):
        PTR2.parse_physical_reference(data)


# 10. duplicate person_ref within a sample rejected ------------------------------


def test_duplicate_person_ref_within_sample_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                    _distractor("phys_d001", [60.0, 10.0, 70.0, 30.0]),
                ],
            )
        ]
    )
    with pytest.raises(
        PTR2.PhysicalReferenceValidationError, match="duplicate person_ref"
    ):
        PTR2.parse_physical_reference(data)


def test_same_person_ref_reused_across_non_adjacent_samples_is_accepted():
    """Section D.5: reuse across a gap (the annotator's genuine-certainty
    case) is legitimate and must not be mistaken for the within-sample
    duplicate rule above."""
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            ),
            _target_only_sample(1.0, [12.0, 10.0, 22.0, 30.0]),
            _distractors_complete_sample(
                2.0,
                [14.0, 10.0, 24.0, 30.0],
                [_distractor("phys_d001", [44.0, 10.0, 54.0, 30.0])],
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise


# 11. malformed distractor entries -----------------------------------------------


def test_distractor_entry_missing_bbox_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0, [10.0, 10.0, 20.0, 30.0], [{"person_ref": "phys_d001"}]
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="bbox_xyxy"):
        PTR2.parse_physical_reference(data)


def test_distractor_entry_missing_person_ref_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [{"bbox_xyxy": [40.0, 10.0, 50.0, 30.0]}],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="person_ref"):
        PTR2.parse_physical_reference(data)


def test_distractor_entry_not_an_object_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0, [10.0, 10.0, 20.0, 30.0], [[40.0, 10.0, 50.0, 30.0]]
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="object"):
        PTR2.parse_physical_reference(data)


# 12. distractor bbox source bounds enforced -------------------------------------


def test_distractor_bbox_out_of_bounds_rejected():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [600.0, 10.0, 700.0, 30.0])],
            )
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(
        PTR2.PhysicalReferenceValidationError, match="outside the declared source frame"
    ):
        PTR2.validate_physical_reference(artifact)


# 13/14. target_only / distractors_complete completeness ------------------------


def test_target_only_with_distractors_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR2.STATE_PRESENT_SCORED,
                PTR2.CONTEXT_TARGET_ONLY,
                [10.0, 10.0, 20.0, 30.0],
                distractors=[_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="target_only"):
        PTR2.parse_physical_reference(data)


def test_distractors_complete_with_no_distractors_rejected():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR2.STATE_PRESENT_SCORED,
                PTR2.CONTEXT_DISTRACTORS_COMPLETE,
                [10.0, 10.0, 20.0, 30.0],
            )
        ]
    )
    with pytest.raises(
        PTR2.PhysicalReferenceValidationError, match="distractors_complete"
    ):
        PTR2.parse_physical_reference(data)


# 15/16. absent / reference_unavailable forbid geometry --------------------------


def test_absent_forbids_target_bbox():
    data = _artifact(
        [_sample(0.0, PTR2.STATE_ABSENT, target_bbox_xyxy=[1.0, 1.0, 2.0, 2.0])]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        PTR2.parse_physical_reference(data)


def test_absent_forbids_distractors():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR2.STATE_ABSENT,
                distractors=[_distractor("phys_d001", [1.0, 1.0, 2.0, 2.0])],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        PTR2.parse_physical_reference(data)


def test_reference_unavailable_forbids_target_bbox():
    data = _artifact(
        [
            _sample(
                0.0,
                PTR2.STATE_PRESENT_REFERENCE_UNAVAILABLE,
                target_bbox_xyxy=[1.0, 1.0, 2.0, 2.0],
            )
        ]
    )
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        PTR2.parse_physical_reference(data)


def test_reference_unavailable_requires_no_bbox_and_validates():
    data = _artifact([_sample(0.0, PTR2.STATE_PRESENT_REFERENCE_UNAVAILABLE)])
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)
    assert artifact.samples[0].target_bbox_xyxy is None


# 17/18. equal person_ref sets permit interpolation, order-independent ----------


def test_equal_person_ref_sets_permit_interpolation():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                ],
            ),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [
                    _distractor("phys_d001", [42.0, 10.0, 52.0, 30.0]),
                    _distractor("phys_d002", [62.0, 10.0, 72.0, 30.0]),
                ],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise


def test_distractor_list_order_change_does_not_break_interpolation():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                ],
            ),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [
                    _distractor("phys_d002", [62.0, 10.0, 72.0, 30.0]),
                    _distractor("phys_d001", [42.0, 10.0, 52.0, 30.0]),
                ],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise
    # Storage itself is canonically sorted regardless of input order.
    assert [d.person_ref for d in artifact.samples[0].distractors] == [
        "phys_d001",
        "phys_d002",
    ]
    assert [d.person_ref for d in artifact.samples[1].distractors] == [
        "phys_d001",
        "phys_d002",
    ]


# 19/20. added/removed person_ref rejects interpolation -------------------------


def test_added_person_ref_rejects_interpolation():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            ),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [
                    _distractor("phys_d001", [42.0, 10.0, 52.0, 30.0]),
                    _distractor("phys_d002", [62.0, 10.0, 72.0, 30.0]),
                ],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        PTR2.validate_physical_reference(artifact)


def test_removed_person_ref_rejects_interpolation():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                ],
            ),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [_distractor("phys_d001", [42.0, 10.0, 52.0, 30.0])],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        PTR2.validate_physical_reference(artifact)


def test_replaced_person_ref_same_count_rejects_interpolation():
    """Same cardinality, different identity -- must still be rejected; a
    count-only check would wrongly accept this."""
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            ),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [_distractor("phys_d002", [62.0, 10.0, 72.0, 30.0])],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        PTR2.validate_physical_reference(artifact)


# 21. target_only interpolation remains legal ------------------------------------


def test_target_only_interpolation_remains_legal():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _target_only_sample(
                1.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise


def test_interpolation_on_first_sample_is_rejected():
    data = _artifact(
        [
            _target_only_sample(
                0.0, [10.0, 10.0, 20.0, 30.0], interpolate_from_previous=True
            )
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="no predecessor"):
        PTR2.validate_physical_reference(artifact)


# 22/23. context/state mismatch rejects interpolation ----------------------------


def test_context_mismatch_rejects_interpolation():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _distractors_complete_sample(
                1.0,
                [12.0, 10.0, 22.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
                interpolate_from_previous=True,
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="identity_context"):
        PTR2.validate_physical_reference(artifact)


def test_state_mismatch_rejects_interpolation():
    data = _artifact(
        [
            _sample(0.0, PTR2.STATE_ABSENT),
            _target_only_sample(
                1.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="present_scored"):
        PTR2.validate_physical_reference(artifact)


def test_interpolation_across_absence_is_rejected():
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _sample(1.0, PTR2.STATE_ABSENT),
            _target_only_sample(
                2.0, [12.0, 10.0, 22.0, 30.0], interpolate_from_previous=True
            ),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="present_scored"):
        PTR2.validate_physical_reference(artifact)


# 24/25. deterministic serialization and round-trips ------------------------------


def test_serialization_sorts_distractors_by_person_ref():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                ],
            )
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)
    serialized = PTR2.serialize_physical_reference(artifact)
    refs = [d["person_ref"] for d in serialized["samples"][0]["distractors"]]
    assert refs == ["phys_d001", "phys_d002"]


def test_serialize_is_deterministic_regardless_of_input_distractor_order():
    data_a = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                ],
            )
        ]
    )
    data_b = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [
                    _distractor("phys_d002", [60.0, 10.0, 70.0, 30.0]),
                    _distractor("phys_d001", [40.0, 10.0, 50.0, 30.0]),
                ],
            )
        ]
    )
    artifact_a = PTR2.parse_physical_reference(data_a)
    artifact_b = PTR2.parse_physical_reference(data_b)
    PTR2.validate_physical_reference(artifact_a)
    PTR2.validate_physical_reference(artifact_b)
    serialized_a = PTR2.serialize_physical_reference(artifact_a)
    serialized_b = PTR2.serialize_physical_reference(artifact_b)
    assert json.dumps(serialized_a, sort_keys=True) == json.dumps(
        serialized_b, sort_keys=True
    )


def test_write_then_load_round_trip(tmp_path):
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)

    out_path = tmp_path / "artifact_v2.json"
    PTR2.write_physical_reference(out_path, artifact)

    reloaded = PTR2.load_physical_reference(out_path)
    assert reloaded == artifact

    out_path_2 = tmp_path / "artifact_v2_2.json"
    PTR2.write_physical_reference(out_path_2, reloaded)
    assert out_path.read_text() == out_path_2.read_text()


# 26. v1 parser remains unchanged/isolated (both directions) ---------------------


def test_v1_style_artifact_rejected_by_v2_parser():
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
    # A real v1 artifact is structurally incompatible with v2 in more than
    # one way at once (no evaluation_window, distractor_bboxes_xyxy instead
    # of distractors) -- whichever is detected first, it must be rejected,
    # never silently accepted. The schema_version check itself is isolated
    # and proven separately by test_unsupported_schema_version_rejected.
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        PTR2.parse_physical_reference(v1_data)


def test_v2_style_artifact_rejected_by_v1_parser():
    data = _artifact([_target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0])])
    with pytest.raises(PTR1.PhysicalReferenceValidationError, match="schema_version"):
        PTR1.parse_physical_reference(data)


def test_v1_module_untouched_constants():
    """Defensive: v2's own SCHEMA_VERSION/CONTRACT_VERSION must never leak
    into, or be confused with, v1's."""
    assert PTR1.SCHEMA_VERSION == 1
    assert PTR1.CONTRACT_VERSION == "tim_physical_target_bbox_v1"
    assert PTR2.SCHEMA_VERSION == 2
    assert PTR2.CONTRACT_VERSION == "tim_physical_target_bbox_v2"


# 27. no tracker-ID concept anywhere in the v2 structure -------------------------


def test_v2_serialized_artifact_has_no_tracker_id_concept_anywhere():
    data = _artifact(
        [
            _distractors_complete_sample(
                0.0,
                [10.0, 10.0, 20.0, 30.0],
                [_distractor("phys_d001", [40.0, 10.0, 50.0, 30.0])],
            )
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    serialized = PTR2.serialize_physical_reference(artifact)
    assert "track" not in json.dumps(serialized).lower()


def test_classify_identity_stage_a_is_reused_unchanged_from_v1():
    """Stage A requires zero v2-specific changes (contract section K) --
    proven here by identity, not merely behavioural equivalence."""
    assert PTR2.classify_identity_stage_a is PTR1.classify_identity_stage_a


# 28. non-interpolated present_scored gap is schema-legal, carries no claim -----


def test_non_interpolated_present_scored_gap_is_schema_legal():
    """The schema permits two present_scored keyframes with
    interpolate_from_previous=False (a deliberate, unbridged gap) -- not a
    validator error. What that gap means at evaluation time is frozen in
    docs/issues/p1-10-physical-reference-v2-contract.md (section H,
    reference_gap_duration_s), not implemented until M2-v2."""
    data = _artifact(
        [
            _target_only_sample(0.0, [10.0, 10.0, 20.0, 30.0]),
            _target_only_sample(5.0, [50.0, 10.0, 60.0, 30.0]),
        ]
    )
    artifact = PTR2.parse_physical_reference(data)
    PTR2.validate_physical_reference(artifact)  # must not raise
    assert artifact.samples[1].interpolate_from_previous is False


# 29. no invented freshness/support-window tolerance in the schema module -------


def test_v2_schema_module_defines_no_freshness_or_support_window_constant():
    """M1-v2 is schema/validator only; no freshness tolerance or support
    window constant may leak into the schema layer -- that would be
    exactly the invented-tolerance the v2 contract explicitly forbids
    (docs/issues/p1-10-physical-reference-v2-contract.md section H).
    Checks actual module attribute names (constants/functions/classes),
    not the module's own explanatory prose about why no such thing
    exists -- a docstring describing the absence of a tolerance is not
    itself a tolerance."""
    forbidden_tokens = ("freshness", "support_window", "tolerance", "step_s", "max_age")
    for name in vars(PTR2):
        lowered = name.lower()
        for token in forbidden_tokens:
            assert (
                token not in lowered
            ), f"unexpected {token!r} in v2 module attribute {name!r}"


# 30. the frozen contract document exists and carries the key terms -------------


def test_v2_contract_doc_exists_and_freezes_reconciliation_language():
    assert CONTRACT_DOC_PATH.exists()
    text = CONTRACT_DOC_PATH.read_text(encoding="utf-8")
    assert "evaluation_window" in text
    assert "reference_gap_duration_s" in text
    assert "reference_covered_duration_s" in text
    assert "reference_coverage_fraction" in text


# --- template ---------------------------------------------------------------


def test_v2_template_loads_and_validates():
    artifact = PTR2.load_physical_reference(TEMPLATE_PATH_V2)
    assert artifact.provenance.contract_version == PTR2.CONTRACT_VERSION
    assert artifact.provenance.schema_version == 2
    assert len(artifact.samples) >= 1


def test_v2_template_contains_a_distractors_complete_sample_with_person_ref():
    artifact = PTR2.load_physical_reference(TEMPLATE_PATH_V2)
    dc_samples = [
        s
        for s in artifact.samples
        if s.identity_context == PTR2.CONTEXT_DISTRACTORS_COMPLETE
    ]
    assert dc_samples
    assert any(s.distractors for s in dc_samples)
    assert all(
        PTR2.PERSON_REF_PATTERN.match(d.person_ref)
        for s in dc_samples
        for d in s.distractors
    )


def test_v2_template_contains_a_legal_interpolation_example():
    artifact = PTR2.load_physical_reference(TEMPLATE_PATH_V2)
    assert any(s.interpolate_from_previous for s in artifact.samples)
