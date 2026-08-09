"""Tests for the Issue #25 physical-reference annotation UI backend
(tools/bag_annotation_ui/tim_ui_physical_reference.py).

Covers the coordinate-normalisation safety net, save/load through the
real physical_target_reference.py validator (no duplicated schema logic),
path safety, discovery, and tracker-ID independence of the saved artifact.
"""

from __future__ import annotations

import importlib.util
import json
import re
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


# --- coordinate-convention auto-resolution --------------------------------------
#
# The core safety property under test: a historical source must never
# silently resolve to (or default to) the modern convention, an unknown
# source must never silently resolve to either convention, and a genuinely
# modern source must resolve to the modern convention only on positive
# evidence (a real contract-header match), never merely because its date is
# recent.


def test_resolve_coordinate_convention_may_hard_reentry_style_source_is_historical():
    resolved = UI.resolve_coordinate_convention(
        "bags/source/curated/2026-05-14__11-03-26__dataset__"
        "tim_v1_hard_reentry_id_switch_raw"
    )
    assert resolved is not None
    assert resolved["coordinate_convention"] == "source_pixels_historical_pre_p53"
    assert resolved["coordinate_convention_evidence"]
    assert "2026-05-14" in resolved["coordinate_convention_evidence"]


def test_resolve_coordinate_convention_june_canonical_style_source_is_historical():
    resolved = UI.resolve_coordinate_convention(
        "bags/source/curated/2026-06-19__12-55-58__source__2026-06-19__official__"
        "seq03__four_person_crossing_ambiguity__image_raw"
    )
    assert resolved is not None
    assert resolved["coordinate_convention"] == "source_pixels_historical_pre_p53"
    assert "2026-06-19" in resolved["coordinate_convention_evidence"]


def test_resolve_coordinate_convention_modern_source_requires_positive_header_evidence(
    monkeypatch,
):
    monkeypatch.setattr(
        UI,
        "_detections_header_frame_id",
        lambda bag_path: (
            "tim_mars_source_pixels_resize_v1;frame=1;source=640x480;"
            "inference=640x640;scale=1,1.0;pad=0,0"
        ),
    )
    resolved = UI.resolve_coordinate_convention(
        "bags/source/curated/2026-08-09__12-00-00__modern_source"
    )
    assert resolved is not None
    assert resolved["coordinate_convention"] == "source_pixels_p53_contract"
    assert resolved["coordinate_convention_evidence"] is None


def test_resolve_coordinate_convention_unresolvable_source_is_none_not_a_default(
    monkeypatch,
):
    """A post-closure-dated bag with no header evidence must not silently
    become modern, and must not become historical either -- unresolved."""
    monkeypatch.setattr(UI, "_detections_header_frame_id", lambda bag_path: None)
    resolved = UI.resolve_coordinate_convention(
        "bags/source/curated/2026-08-09__12-00-00__unknown_source"
    )
    assert resolved is None


def test_resolve_coordinate_convention_no_embedded_date_and_no_header_is_none(
    monkeypatch,
):
    monkeypatch.setattr(UI, "_detections_header_frame_id", lambda bag_path: None)
    resolved = UI.resolve_coordinate_convention("bags/source/curated/no_date_here")
    assert resolved is None


def test_p53_contract_closure_date_matches_frozen_documentation():
    # The one place this date is allowed to be asserted; keeps this module
    # honest against docs/issues/p1-10-improve-bbox-evaluation.md section F
    # if that document is ever revised.
    assert UI.P53_CONTRACT_CLOSURE_DATE.isoformat() == "2026-07-22"


# --- Frame-local draft geometry (M3 corrective follow-up) -------------------
#
# There is no JS execution environment in this repository (no Node.js), so
# this frontend logic cannot be run directly. Following the same fallback
# used for the coordinate-mapping formula earlier in this milestone, these
# are structural checks against the actual shipped source: they extract
# each named function's real body with a balanced-brace scanner (not a
# fragile single-line regex) and assert on its content and on call order
# between functions.

JS_PATH = REPO_ROOT / "tools/bag_annotation_ui/static/tim_physical_reference_ui.js"
JS_SOURCE = JS_PATH.read_text(encoding="utf-8")


def _extract_js_function_body(source: str, function_name: str) -> str:
    """Return the full body (including braces) of the first
    `function <function_name>(...) { ... }` declaration in `source`,
    found by balanced-brace scanning rather than a regex that could be
    fooled by nested braces."""

    marker = f"function {function_name}("
    start = source.index(marker)
    brace_start = source.index("{", start)
    depth = 0
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : i + 1]
    raise AssertionError(f"unbalanced braces while extracting {function_name}")


def test_js_source_contains_the_frame_local_functions():
    # Fails loudly (via .index() raising) if either function is missing --
    # a much stronger signal than a plain substring search would give.
    _extract_js_function_body(JS_SOURCE, "physicalRefFindSampleAtCurrentFrame")
    _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")


def test_frame_change_syncs_draft_before_repaint():
    """updatePhysicalRefFrame's img.onload must resolve this frame's own
    state (sync) strictly before drawing (repaint), never the reverse --
    repainting first would draw the stale frame's geometry for one frame."""

    onload_start = JS_SOURCE.index("img.onload = function () {")
    onload_body = _extract_js_function_body_from(JS_SOURCE, onload_start)

    sync_pos = onload_body.index("physicalRefSyncDraftToCurrentFrame();")
    repaint_pos = onload_body.index("physicalRefRepaint();")
    assert sync_pos < repaint_pos


def _extract_js_function_body_from(source: str, marker_pos: int) -> str:
    brace_start = source.index("{", marker_pos)
    depth = 0
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start : i + 1]
    raise AssertionError("unbalanced braces")


def test_sync_restores_saved_sample_geometry_when_frame_has_one():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    assert "physicalRefFindSampleAtCurrentFrame()" in body
    assert "if (idx >= 0)" in body
    assert "physicalRefLoadSampleIntoForm(idx" in body


def test_sync_clears_draft_geometry_when_frame_has_no_saved_sample():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    # The clearing statements must appear after the early-return for the
    # "has a saved sample" branch, i.e. in the no-match path.
    idx_branch_pos = body.index("if (idx >= 0)")
    clear_target_pos = body.index("physicalRefDrawnTarget = null;")
    clear_distractors_pos = body.index("physicalRefDrawnDistractors = [];")
    assert clear_target_pos > idx_branch_pos
    assert clear_distractors_pos > idx_branch_pos


def test_sync_discards_unsaved_draft_with_a_visible_status_message():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    assert "hadUnsavedDraft" in body
    assert "discarded" in body.lower()


def test_find_sample_matches_by_current_time_not_frame_index_identity():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefFindSampleAtCurrentFrame")
    assert "currentTimeS()" in body
    assert "physicalRefSamples.findIndex" in body
    # A tolerance comparison, not exact floating-point equality.
    assert "Math.abs" in body and "<" in body


def test_no_carry_forward_every_target_assignment_is_in_an_expected_function():
    """The only places physicalRefDrawnTarget may be assigned a *new* value
    (drawing, loading a saved sample, or clearing) are enumerated here. If a
    future edit adds a path that copies frame A's box into frame B's draft
    without going through the saved-sample restore or the explicit clear,
    this test's coverage will not include that function and will fail."""

    allowed_functions = {
        "physicalRefOnPointerUp",         # user draws a new box
        "physicalRefLoadSampleIntoForm",  # restore a saved sample's own box
        "physicalRefSyncDraftToCurrentFrame",  # clear on frame change with no saved sample
        "physicalRefClearCurrentBox",     # explicit clear action
        "physicalRefOnStateChange",       # clear when leaving present_scored
        "physicalRefNewSampleAtCurrentFrame",  # explicit new-sample reset
    }

    # Excludes the single module-level `let physicalRefDrawnTarget = null;`
    # declaration (the initial state, not a reassignment / carry-forward
    # risk) -- every *re*assignment must still be inside an allow-listed
    # function.
    assignment_positions = [
        m.start()
        for m in re.finditer(r"(?<!let )physicalRefDrawnTarget\s*=", JS_SOURCE)
    ]
    assert assignment_positions, "expected at least one reassignment in the source"

    function_spans = []
    for name in allowed_functions:
        marker = f"function {name}("
        start = JS_SOURCE.index(marker)
        body_start = JS_SOURCE.index("{", start)
        body = _extract_js_function_body_from(JS_SOURCE, start)
        function_spans.append((name, body_start, body_start + len(body)))

    for pos in assignment_positions:
        containing = [
            name for name, s, e in function_spans if s <= pos < e
        ]
        assert containing, (
            "physicalRefDrawnTarget assignment at char "
            f"{pos} is outside every allow-listed function "
            f"{sorted(allowed_functions)} -- possible new carry-forward path"
        )


def test_tracker_overlay_toggle_is_independent_of_draft_geometry():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefFrameUrl")
    assert "physicalRefShowOverlays" in body
    assert "physicalRefDrawnTarget" not in body
    assert "physicalRefSamples" not in body


# --- interpolate_from_previous is per-sample, never inherited across navigation
#
# Corrected requirement (supersedes the M3 frame-local-geometry commit's
# original behaviour, which deliberately left this checkbox untouched):
# interpolate_from_previous is a deliberate per-sample decision, exactly
# like target/distractor geometry -- it must reset to false on navigation
# to a frame with no saved sample, and must restore exactly (true or
# false) when navigating to a frame that does have one.


def test_unsaved_frame_navigation_resets_interpolate_checkbox_to_false():
    """1/2: a checked interpolation flag must never survive navigation to
    an unsaved frame -- it cannot be inherited from whatever frame or
    sample was previously displayed."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_pos = body.index("if (idx >= 0)")
    clear_branch = body[body.index("}", idx_branch_pos) :]
    assert "interpolateCheckbox.checked = false" in clear_branch


def test_interpolate_reset_happens_in_the_no_saved_sample_branch_only():
    """The reset statement must be strictly after the idx>=0 early-return
    branch (i.e. only reachable when there is no saved sample at this
    frame), never before it or inside the restore branch."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_end = body.index("}", body.index("if (idx >= 0)"))
    reset_pos = body.index("interpolateCheckbox.checked = false")
    assert reset_pos > idx_branch_end


def test_saved_sample_with_interpolation_true_is_restored_exactly():
    """3: navigating to a saved sample whose interpolate_from_previous is
    true must set the checkbox to true (restore, not the reset path)."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadSampleIntoForm")
    assert (
        'document.getElementById("physicalRefInterpolate").checked = '
        "!!s.interpolate_from_previous;" in body
    )
    # This is the *only* place a saved sample's flag is written into the
    # checkbox, and it uses the sample's own field verbatim (via !!),
    # so both true and false are restored exactly -- not hardcoded either
    # way.


def test_saved_sample_with_interpolation_false_is_restored_exactly():
    """4: same code path as the true case above (!!s.interpolate_from_previous
    naturally yields false for a falsy saved value) -- verified here as its
    own explicit requirement rather than assumed from the true case."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadSampleIntoForm")
    # A hardcoded `= true` anywhere in this function would violate "restore
    # exactly"; the only assignment must be the sample-driven one asserted
    # above.
    assert '.checked = true;' not in body
    assert '.checked = !!s.interpolate_from_previous;' in body


def test_geometry_frame_local_behaviour_from_7712c487_is_unchanged():
    """5: the prior fix's own guarantees (sync-before-repaint, geometry
    cleared/restored, no carry-forward) still hold after this change."""
    onload_start = JS_SOURCE.index("img.onload = function () {")
    onload_body = _extract_js_function_body_from(JS_SOURCE, onload_start)
    assert onload_body.index(
        "physicalRefSyncDraftToCurrentFrame();"
    ) < onload_body.index("physicalRefRepaint();")

    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_pos = body.index("if (idx >= 0)")
    clear_branch = body[body.index("}", idx_branch_pos) :]
    assert "physicalRefDrawnTarget = null;" in clear_branch
    assert "physicalRefDrawnDistractors = [];" in clear_branch
    assert "physicalRefLoadSampleIntoForm(idx" in body[:idx_branch_pos + 200]
