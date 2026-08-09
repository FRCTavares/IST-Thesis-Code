"""Tests for the Issue #25 physical-reference annotation UI backend
(tools/bag_annotation_ui/tim_ui_physical_reference.py).

Covers the coordinate-normalisation safety net, save/load through the
real physical_target_reference.py validator (no duplicated schema logic),
path safety, discovery, and tracker-ID independence of the saved artifact.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    module_path = REPO_ROOT / relative
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


UI = _load(
    "tim_ui_physical_reference",
    "tools/bag_annotation_ui/tim_ui_physical_reference.py",
)
PTR = sys.modules["physical_target_reference"]


def _artifact_payload(**sample_overrides) -> dict:
    provenance = {
        "schema_version": 1,
        "contract_version": "tim_physical_target_bbox_v1",
        "sequence_id": "dev_test_sequence",
        "source_bag_name": "test_bag",
        "source_bag_path": "bags/source/curated/test_bag",
        "source_image_topic": "/camera/image_raw",
        "source_width": 640,
        "source_height": 480,
        "coordinate_convention": "source_pixels_p53_contract",
        "coordinate_convention_evidence": None,
        "selected_physical_target_label": "black_shirt_person",
        "annotator": "ui_tester",
        "created_date": "2026-08-09",
        "notes": "",
    }
    sample = {
        "t_s": 0.0,
        "identity_state": "present_scored",
        "identity_context": "target_only",
        "target_bbox_xyxy": [100.0, 100.0, 200.0, 300.0],
        "distractor_bboxes_xyxy": [],
        "interpolate_from_previous": False,
        "notes": "",
    }
    sample.update(sample_overrides)
    return {"provenance": provenance, "samples": [sample]}


# --- normalize_rect: reverse-drag, zero-area -------------------------------


def test_normalize_rect_forward_drag_unchanged():
    assert UI.normalize_rect(10.0, 20.0, 110.0, 220.0) == (10.0, 20.0, 110.0, 220.0)


def test_normalize_rect_reverse_x_drag():
    # dragged from bottom-right to top-left on x
    assert UI.normalize_rect(110.0, 20.0, 10.0, 220.0) == (10.0, 20.0, 110.0, 220.0)


def test_normalize_rect_reverse_y_drag():
    assert UI.normalize_rect(10.0, 220.0, 110.0, 20.0) == (10.0, 20.0, 110.0, 220.0)


def test_normalize_rect_fully_reversed_drag():
    assert UI.normalize_rect(110.0, 220.0, 10.0, 20.0) == (10.0, 20.0, 110.0, 220.0)


def test_normalize_rect_zero_area_is_rejected():
    assert UI.normalize_rect(50.0, 50.0, 50.0, 200.0) is None  # zero width
    assert UI.normalize_rect(50.0, 50.0, 200.0, 50.0) is None  # zero height
    assert UI.normalize_rect(50.0, 50.0, 50.0, 50.0) is None  # a single point


# --- path safety -------------------------------------------------------------


def test_safe_relpath_requires_physical_reference_root():
    with pytest.raises(UI.PhysicalReferenceUIError, match="must be under"):
        UI.safe_physical_reference_relpath("docs/data/annotations/foo.json")


def test_safe_relpath_rejects_parent_traversal():
    with pytest.raises(UI.PhysicalReferenceUIError, match="\\.\\."):
        UI.safe_physical_reference_relpath(
            "docs/data/physical_target_references/../../etc/passwd.json"
        )


def test_safe_relpath_requires_json_suffix():
    with pytest.raises(UI.PhysicalReferenceUIError, match="\\.json"):
        UI.safe_physical_reference_relpath(
            "docs/data/physical_target_references/foo.csv"
        )


def test_safe_relpath_rejects_absolute_path():
    with pytest.raises(UI.PhysicalReferenceUIError, match="relative"):
        UI.safe_physical_reference_relpath(
            "/etc/docs/data/physical_target_references/foo.json"
        )


# --- save/load through the real validator, no duplicated schema logic -------


def test_save_then_load_round_trip(tmp_path):
    payload = _artifact_payload()
    rel = "docs/data/physical_target_references/ui_test_fixture.json"

    saved = UI.save_physical_reference_for_ui(rel, payload, tmp_path)
    assert saved["path"] == rel
    assert saved["sample_count"] == 1

    on_disk = tmp_path / rel
    assert on_disk.is_file()

    loaded = UI.load_physical_reference_for_ui(rel, tmp_path)
    assert loaded["provenance"]["selected_physical_target_label"] == "black_shirt_person"
    assert loaded["samples"][0]["target_bbox_xyxy"] == [100.0, 100.0, 200.0, 300.0]


def test_save_rejects_invalid_artifact_via_real_validator(tmp_path):
    # present_scored with no identity_context: rejected by
    # physical_target_reference.py's own validator, not reimplemented here.
    payload = _artifact_payload(identity_context=None)
    rel = "docs/data/physical_target_references/ui_test_invalid.json"

    with pytest.raises(PTR.PhysicalReferenceValidationError, match="identity_context"):
        UI.save_physical_reference_for_ui(rel, payload, tmp_path)

    assert not (tmp_path / rel).exists()


def test_save_rejects_target_only_with_distractors(tmp_path):
    payload = _artifact_payload(
        distractor_bboxes_xyxy=[[400.0, 100.0, 500.0, 300.0]]
    )
    rel = "docs/data/physical_target_references/ui_test_bad_context.json"

    with pytest.raises(PTR.PhysicalReferenceValidationError, match="target_only"):
        UI.save_physical_reference_for_ui(rel, payload, tmp_path)


def test_save_accepts_distractors_complete_with_multiple_distractors(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractor_bboxes_xyxy=[
            [400.0, 100.0, 500.0, 300.0],
            [10.0, 10.0, 50.0, 90.0],
        ],
    )
    rel = "docs/data/physical_target_references/ui_test_distractors.json"

    saved = UI.save_physical_reference_for_ui(rel, payload, tmp_path)
    assert len(saved["samples"][0]["distractor_bboxes_xyxy"]) == 2
    # Deterministic order preserved exactly as submitted:
    assert saved["samples"][0]["distractor_bboxes_xyxy"][0] == [
        400.0, 100.0, 500.0, 300.0,
    ]


def test_saved_artifact_contains_no_tracker_id_field(tmp_path):
    payload = _artifact_payload()
    rel = "docs/data/physical_target_references/ui_test_no_track_id.json"
    UI.save_physical_reference_for_ui(rel, payload, tmp_path)

    raw_text = (tmp_path / rel).read_text(encoding="utf-8")
    raw = json.loads(raw_text)
    assert "track_id" not in raw_text
    assert "correct_target_track_id" not in raw_text
    assert "tracker_id" not in raw_text
    # Structural: no key anywhere in the parsed structure mentions "track".
    def _walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert "track" not in key.lower()
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw)


def test_save_does_not_overwrite_silently_when_reused_path_has_different_content(
    tmp_path,
):
    rel = "docs/data/physical_target_references/ui_test_overwrite.json"
    first = _artifact_payload()
    UI.save_physical_reference_for_ui(rel, first, tmp_path)

    second = _artifact_payload(notes="edited in a second explicit save")
    UI.save_physical_reference_for_ui(rel, second, tmp_path)

    reloaded = UI.load_physical_reference_for_ui(rel, tmp_path)
    assert reloaded["samples"][0]["notes"] == "edited in a second explicit save"


# --- discovery -----------------------------------------------------------------


def test_discover_physical_references_finds_json_files(tmp_path):
    root = tmp_path / "docs" / "data" / "physical_target_references"
    root.mkdir(parents=True)
    (root / "a.json").write_text("{}")
    (root / "b.json").write_text("{}")
    (root / "not_relevant.txt").write_text("x")

    found = UI.discover_physical_references(tmp_path)
    assert found == sorted(found)
    assert all(f.endswith(".json") for f in found)
    assert len(found) == 2


def test_discover_physical_references_empty_when_root_missing(tmp_path):
    assert UI.discover_physical_references(tmp_path) == []
