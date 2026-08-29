"""Tests for the Issue #25 v2 physical-reference annotation UI
(tools/bag_annotation_ui/tim_ui_physical_reference_v2.py and
tools/bag_annotation_ui/static/tim_physical_reference_v2_ui.js).

Sibling of test_tim_ui_physical_reference.py (v1), which is untouched and
remains fully meaningful. Covers the two new pieces of pure UI logic v2
adds (deterministic person_ref generation, known-person-ref discovery),
save/load through the real physical_target_reference_v2.py validator (no
duplicated schema logic), the evaluation-window/right-boundary-anchor
UI behaviour frozen in commit 4ab33ec1, v1/v2 explicitness, and -- since
no Node/browser automation exists in this repository -- structural tests
against the actual shipped frontend JS source using the same
balanced-brace function-body extractor already established for the v1
frontend file.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
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


UI2 = _load(
    "tim_ui_physical_reference_v2",
    "tools/bag_annotation_ui/tim_ui_physical_reference_v2.py",
)
PTR2 = sys.modules["physical_target_reference_v2"]


def _distractor(person_ref: str, bbox) -> dict:
    return {"person_ref": person_ref, "bbox_xyxy": bbox}


def _artifact_payload(**sample_overrides) -> dict:
    provenance = {
        "schema_version": 2,
        "contract_version": "tim_physical_target_bbox_v2",
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
        "created_date": "2026-08-10",
        "evaluation_window": {"start_s": 0.0, "end_s": 10.0},
        "notes": "",
    }
    sample = {
        "t_s": 0.0,
        "identity_state": "present_scored",
        "identity_context": "target_only",
        "target_bbox_xyxy": [100.0, 100.0, 200.0, 300.0],
        "distractors": [],
        "interpolate_from_previous": False,
        "notes": "",
    }
    sample.update(sample_overrides)
    return {"provenance": provenance, "samples": [sample]}


# 1/2. v2 save/load round trip, explicit schema/version -----------------------


def test_save_then_load_round_trip_is_explicitly_v2(tmp_path):
    payload = _artifact_payload()
    rel = "docs/data/physical_target_references/ui_test_v2_fixture.json"

    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert saved["path"] == rel
    assert saved["sample_count"] == 1
    assert saved["provenance"]["schema_version"] == 2
    assert saved["provenance"]["contract_version"] == "tim_physical_target_bbox_v2"

    on_disk = tmp_path / rel
    assert on_disk.is_file()

    loaded = UI2.load_physical_reference_v2_for_ui(rel, tmp_path)
    assert loaded["provenance"]["schema_version"] == 2
    assert loaded["provenance"]["contract_version"] == "tim_physical_target_bbox_v2"
    assert loaded["samples"][0]["target_bbox_xyxy"] == [100.0, 100.0, 200.0, 300.0]


# 3/4. evaluation_window preserved, right-boundary anchor accepted ------------


def test_evaluation_window_preserved_through_round_trip(tmp_path):
    payload = _artifact_payload()
    payload["provenance"]["evaluation_window"] = {"start_s": 0.0, "end_s": 67.865}
    rel = "docs/data/physical_target_references/ui_test_v2_window.json"

    UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    loaded = UI2.load_physical_reference_v2_for_ui(rel, tmp_path)
    assert loaded["provenance"]["evaluation_window"] == {"start_s": 0.0, "end_s": 67.865}


def test_sample_exactly_at_evaluation_window_end_is_accepted(tmp_path):
    """Corrected 2026-08-10 (commit 4ab33ec1): the final source frame's own
    timestamp is a legal right-boundary interpolation anchor."""
    payload = _artifact_payload(t_s=10.0)
    payload["provenance"]["evaluation_window"] = {"start_s": 0.0, "end_s": 10.0}
    rel = "docs/data/physical_target_references/ui_test_v2_right_boundary.json"

    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert saved["samples"][0]["t_s"] == 10.0


# 5. phys_d001 accepted --------------------------------------------------------


def test_valid_person_ref_accepted_through_ui_save(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[_distractor("phys_d001", [400.0, 100.0, 500.0, 300.0])],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_person_ref.json"
    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert saved["samples"][0]["distractors"][0]["person_ref"] == "phys_d001"


# 6. deterministic new-person generator ----------------------------------------


def test_next_person_ref_is_lowest_unused_ordinal():
    assert UI2.next_person_ref([]) == "phys_d001"
    assert UI2.next_person_ref(["phys_d001"]) == "phys_d002"
    assert UI2.next_person_ref(["phys_d001", "phys_d002", "phys_d004"]) == "phys_d003"


def test_next_person_ref_ignores_malformed_or_unrelated_refs():
    assert UI2.next_person_ref(["not_a_person_ref", "phys_d001", "7"]) == "phys_d002"


def test_next_person_ref_never_derived_from_tracker_like_values():
    # Tracker-like strings never match the namespace pattern, so they are
    # simply ignored -- the generator still starts from phys_d001.
    assert UI2.next_person_ref(["T2", "track_7", "1"]) == "phys_d001"


# 7. known-person discovery across saved samples -------------------------------


def test_known_person_refs_discovered_across_all_samples():
    samples = [
        {"distractors": [{"person_ref": "phys_d001", "bbox_xyxy": [0, 0, 1, 1]}]},
        {"distractors": [{"person_ref": "phys_d002", "bbox_xyxy": [0, 0, 1, 1]}]},
        {"distractors": []},
    ]
    assert UI2.known_person_refs(samples) == ["phys_d001", "phys_d002"]


def test_known_person_refs_sorted_and_deduplicated():
    samples = [
        {"distractors": [{"person_ref": "phys_d002", "bbox_xyxy": [0, 0, 1, 1]}]},
        {"distractors": [{"person_ref": "phys_d001", "bbox_xyxy": [0, 0, 1, 1]}]},
        {"distractors": [{"person_ref": "phys_d001", "bbox_xyxy": [0, 0, 1, 1]}]},
    ]
    assert UI2.known_person_refs(samples) == ["phys_d001", "phys_d002"]


def test_known_person_refs_empty_for_no_samples():
    assert UI2.known_person_refs([]) == []
    assert UI2.known_person_refs(None) == []


# 8/9/10. malformed person_ref rejected by the real backend validator --------


def test_duplicate_person_ref_in_current_sample_rejected(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[
            _distractor("phys_d001", [400.0, 100.0, 500.0, 300.0]),
            _distractor("phys_d001", [10.0, 10.0, 50.0, 90.0]),
        ],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_dup.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="duplicate"):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert not (tmp_path / rel).exists()


def test_missing_person_ref_rejected(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[{"bbox_xyxy": [400.0, 100.0, 500.0, 300.0]}],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_missing_ref.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="person_ref"):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert not (tmp_path / rel).exists()


@pytest.mark.parametrize("bad_ref", ["1", "T2", "track_7", "d1"])
def test_tracker_like_person_ref_rejected(tmp_path, bad_ref):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[_distractor(bad_ref, [400.0, 100.0, 500.0, 300.0])],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_bad_ref.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="person_ref"):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert not (tmp_path / rel).exists()


# 11/12. same-set interpolation accepted, changed-set rejected ----------------


def test_same_set_distractors_complete_interpolation_accepted(tmp_path):
    payload = {
        "provenance": _artifact_payload()["provenance"],
        "samples": [
            {
                "t_s": 0.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [0.0, 0.0, 10.0, 10.0],
                "distractors": [
                    _distractor("phys_d001", [20.0, 0.0, 30.0, 10.0]),
                    _distractor("phys_d002", [40.0, 0.0, 50.0, 10.0]),
                ],
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 5.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [5.0, 0.0, 15.0, 10.0],
                "distractors": [
                    _distractor("phys_d001", [25.0, 0.0, 35.0, 10.0]),
                    _distractor("phys_d002", [45.0, 0.0, 55.0, 10.0]),
                ],
                "interpolate_from_previous": True,
                "notes": "",
            },
        ],
    }
    rel = "docs/data/physical_target_references/ui_test_v2_interp_ok.json"
    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert saved["samples"][1]["interpolate_from_previous"] is True


def test_changed_set_distractors_complete_interpolation_rejected(tmp_path):
    payload = {
        "provenance": _artifact_payload()["provenance"],
        "samples": [
            {
                "t_s": 0.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [0.0, 0.0, 10.0, 10.0],
                "distractors": [_distractor("phys_d001", [20.0, 0.0, 30.0, 10.0])],
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 5.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [5.0, 0.0, 15.0, 10.0],
                "distractors": [
                    _distractor("phys_d001", [25.0, 0.0, 35.0, 10.0]),
                    _distractor("phys_d002", [45.0, 0.0, 55.0, 10.0]),
                ],
                "interpolate_from_previous": True,
                "notes": "",
            },
        ],
    }
    rel = "docs/data/physical_target_references/ui_test_v2_interp_bad.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert not (tmp_path / rel).exists()


# 13/14. drawing/list order independent, deterministic saved order -----------


def test_distractor_drawing_order_does_not_affect_saved_order(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[
            _distractor("phys_d002", [40.0, 0.0, 50.0, 10.0]),
            _distractor("phys_d001", [20.0, 0.0, 30.0, 10.0]),
        ],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_order.json"
    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    refs = [d["person_ref"] for d in saved["samples"][0]["distractors"]]
    assert refs == ["phys_d001", "phys_d002"]

    reloaded = UI2.load_physical_reference_v2_for_ui(rel, tmp_path)
    reloaded_refs = [d["person_ref"] for d in reloaded["samples"][0]["distractors"]]
    assert reloaded_refs == ["phys_d001", "phys_d002"]


# 15/16. source coordinate and historical provenance preservation ------------


def test_source_dimensions_preserved(tmp_path):
    payload = _artifact_payload()
    payload["provenance"]["source_width"] = 640
    payload["provenance"]["source_height"] = 640  # May's verified square capture
    rel = "docs/data/physical_target_references/ui_test_v2_dims.json"
    UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    loaded = UI2.load_physical_reference_v2_for_ui(rel, tmp_path)
    assert loaded["provenance"]["source_width"] == 640
    assert loaded["provenance"]["source_height"] == 640


def test_historical_coordinate_provenance_preserved(tmp_path):
    payload = _artifact_payload()
    payload["provenance"]["coordinate_convention"] = "source_pixels_historical_pre_p53"
    payload["provenance"]["coordinate_convention_evidence"] = (
        "Bag directory name embeds capture date 2026-05-14, before Issue "
        "#53's contract closed on 2026-07-22."
    )
    rel = "docs/data/physical_target_references/ui_test_v2_historical.json"
    UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    loaded = UI2.load_physical_reference_v2_for_ui(rel, tmp_path)
    assert loaded["provenance"]["coordinate_convention"] == "source_pixels_historical_pre_p53"
    assert "2026-05-14" in loaded["provenance"]["coordinate_convention_evidence"]


# 17. invalid payload never writes a misleading artifact ----------------------


def test_invalid_payload_writes_no_file(tmp_path):
    payload = _artifact_payload(identity_context=None)  # present_scored needs a context
    rel = "docs/data/physical_target_references/ui_test_v2_invalid.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert not (tmp_path / rel).exists()
    assert not (tmp_path / "docs/data/physical_target_references").exists() or not any(
        (tmp_path / "docs/data/physical_target_references").iterdir()
    )


# 18. v1 is never silently migrated --------------------------------------------


def test_v1_artifact_rejected_with_clear_message_not_migrated(tmp_path):
    v1_payload = {
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
    rel = "docs/data/physical_target_references/ui_test_v1_legacy.json"
    on_disk = tmp_path / rel
    on_disk.parent.mkdir(parents=True, exist_ok=True)
    on_disk.write_text(json.dumps(v1_payload), encoding="utf-8")
    original_text = on_disk.read_text(encoding="utf-8")

    with pytest.raises(UI2.PhysicalReferenceUIError, match="v1"):
        UI2.load_physical_reference_v2_for_ui(rel, tmp_path)

    # The file on disk is completely untouched -- read-rejected, never
    # rewritten as v2.
    assert on_disk.read_text(encoding="utf-8") == original_text


def test_unsupported_schema_version_produces_explicit_error(tmp_path):
    payload = _artifact_payload()
    payload["provenance"]["schema_version"] = 3
    rel = "docs/data/physical_target_references/ui_test_v2_future.json"
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="schema_version"):
        UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)


# 19. scratch-path safety (reused v1 safety net, confirmed for v2 too) -------


def test_path_outside_physical_reference_root_rejected(tmp_path):
    payload = _artifact_payload()
    with pytest.raises(UI2.PhysicalReferenceUIError, match="under"):
        UI2.save_physical_reference_v2_for_ui("docs/data/other/sneaky.json", payload, tmp_path)


def test_scratch_path_is_a_normal_writable_destination(tmp_path):
    payload = _artifact_payload()
    rel = "docs/data/physical_target_references/_scratch/example.json"
    saved = UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    assert saved["path"] == rel
    assert (tmp_path / rel).is_file()


# --- no tracker-ID concept anywhere in a saved v2 artifact -------------------


def test_saved_v2_artifact_contains_no_tracker_id_field(tmp_path):
    payload = _artifact_payload(
        identity_context="distractors_complete",
        distractors=[_distractor("phys_d001", [400.0, 100.0, 500.0, 300.0])],
    )
    rel = "docs/data/physical_target_references/ui_test_v2_no_track.json"
    UI2.save_physical_reference_v2_for_ui(rel, payload, tmp_path)
    raw_text = (tmp_path / rel).read_text(encoding="utf-8")
    assert "track" not in raw_text.lower()


# =============================================================================
# Frontend structural tests
#
# No Node/browser automation exists in this repository, so these are
# structural tests against the actual shipped .js/.html source, using the
# same balanced-brace function-body extractor already established for the
# v1 frontend file (tools/tests/test_tim_ui_physical_reference.py). They
# read real extracted function bodies and assert on their content and call
# order, not a fragile single-line regex.
# =============================================================================

JS_PATH = REPO_ROOT / "tools/bag_annotation_ui/static/tim_physical_reference_v2_ui.js"
JS_SOURCE = JS_PATH.read_text(encoding="utf-8")

HTML_PATH = REPO_ROOT / "tools/bag_annotation_ui/static/tim_clean_ui.html"
HTML_SOURCE = HTML_PATH.read_text(encoding="utf-8")


def _extract_js_function_body(source: str, function_name: str) -> str:
    """Return the full body (including braces) of the first
    `function <function_name>(...) { ... }` declaration in `source`, found
    by balanced-brace scanning rather than a regex that could be fooled by
    nested braces."""

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


def _strip_js_line_comments(source: str) -> str:
    """Strip `// ...` line comments (not full JS parsing -- good enough for
    the small, quote-free code snippets these tests scan). Used where a
    test needs to prove an identifier/token is absent from actual *code*,
    not merely absent from the explanatory prose of a comment describing
    why it is intentionally absent."""

    return "\n".join(line.split("//", 1)[0] for line in source.split("\n"))


# --- 1. v2 mode/version visible ----------------------------------------------


def test_v2_contract_version_visible_in_html_and_js():
    assert "tim_physical_target_bbox_v2" in HTML_SOURCE
    assert "Physical reference v2" in HTML_SOURCE
    assert "tim_physical_target_bbox_v2" in JS_SOURCE


def test_html_loads_the_v2_script_not_the_v1_one_as_the_active_workspace():
    assert "tim_physical_reference_v2_ui.js" in HTML_SOURCE
    # v1's file must still exist and be untouched (Section 25/26), but the
    # normal workspace must not load it as the active script.
    v1_js_path = REPO_ROOT / "tools/bag_annotation_ui/static/tim_physical_reference_ui.js"
    assert v1_js_path.exists()
    assert '<script src="/static/tim_physical_reference_ui.js' not in HTML_SOURCE


# --- 2/3. person_ref palette and "+ New physical person" action -------------


def test_person_ref_palette_container_and_render_function_exist():
    assert 'id="physicalRefPersonRefPalette"' in HTML_SOURCE
    _extract_js_function_body(JS_SOURCE, "physicalRefV2RenderPersonRefPalette")


def test_new_physical_person_action_exists_and_is_wired():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2NewPersonRef")
    assert "physicalRefV2NextPersonRef" in body
    assert "physicalRefV2SelectPersonRef" in body
    assert "window.physicalRefV2NewPersonRef" in JS_SOURCE
    assert "+ New physical person" in JS_SOURCE


# --- 4. generated IDs match the phys_dNNN namespace, lowest-unused policy ---


def test_next_person_ref_js_uses_the_frozen_namespace_and_lowest_unused_policy():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2NextPersonRef")
    assert "phys_d" in body
    # Lowest-unused-ordinal policy, not monotonic-next: a used-set lookup
    # followed by an incrementing scan, never simply "count existing + 1".
    assert "used.has(n)" in body
    assert "n++" in body
    assert "padStart" in body  # zero-padded to the 3-digit minimum width


def test_next_person_ref_js_never_reads_tracker_or_drawing_order_state():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2NextPersonRef")
    assert "track" not in body.lower()
    assert "physicalRefDrawnTarget" not in body
    assert "bbox" not in body.lower()


# --- 5. an existing person_ref can be reused -----------------------------------


def test_existing_person_ref_can_be_selected_for_reuse():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2SelectPersonRef")
    assert "physicalRefV2ActivePersonRef = ref" in body
    assert "window.physicalRefV2SelectPersonRef" in JS_SOURCE


# --- 6. canvas draws person_ref labels, not "distractor N" -------------------


def test_canvas_labels_use_person_ref_not_positional_labels():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRepaint")
    assert "d.person_ref" in body
    assert '"Target"' in body
    assert "distractor \"" not in body  # the old v1-style positional label


# --- 7/9. remove is current-sample-only, no list-position identity logic ---


def test_remove_distractor_only_touches_current_draft():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRemoveDistractor")
    assert "physicalRefDrawnDistractors.splice" in body
    # Checked against the code only (comments stripped) -- the function's
    # own comment explains *why* physicalRefSamples is untouched, which
    # would otherwise trip a naive substring check on the prose itself.
    code_only = _strip_js_line_comments(body)
    assert "physicalRefSamples" not in code_only


def test_no_list_position_identity_logic_in_sample_construction():
    """Distractors are always paired by person_ref (via explicit
    object keys), never assumed to correspond by array index between two
    samples -- proven directly on the interpolation-eligibility comparison,
    which sorts both sides by person_ref before comparing rather than
    zipping the raw arrays."""
    body = _extract_js_function_body(
        JS_SOURCE, "physicalRefV2UpdateInterpolationEligibilityNote"
    )
    assert "d.person_ref" in body
    assert ".sort()" in body


def test_known_person_refs_keyed_by_person_ref_field_not_index():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2KnownPersonRefsFromSamples")
    assert "d.person_ref" in body
    assert "forEach((d)" in body or "forEach((d, " in body


# --- 8. distractors_complete interpolation checkbox is selectable ------------


def test_interpolate_checkbox_not_disabled_for_distractors_complete():
    assert 'id="physicalRefInterpolate"' in HTML_SOURCE
    # No JS path disables the checkbox based on identity_context -- backend
    # validation is authoritative, the frontend only ever offers a
    # convenience status note (physicalRefInterpolateNote), never a second
    # independent schema check that blocks the control itself.
    assert "physicalRefInterpolate\").disabled" not in JS_SOURCE


# --- 10. frame change clears unsaved person_ref associations -----------------


def test_sync_to_frame_resets_active_person_ref_in_the_clear_branch():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_pos = body.index("if (idx >= 0)")
    clear_branch = body[body.index("}", idx_branch_pos) :]
    assert "physicalRefV2ActivePersonRef = null" in clear_branch


def test_load_sample_into_form_also_resets_active_person_ref():
    """Editing an existing saved sample must not leave a stale 'currently
    selected new person' association active."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadSampleIntoForm")
    assert "physicalRefV2ActivePersonRef = null" in body


# --- 11/12. ArrowLeft/ArrowRight follow the existing navigation path --------


def test_arrow_left_steps_to_previous_frame():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2OnKeyDown")
    left_pos = body.index('"ArrowLeft"')
    step_call_pos = body.index("physicalRefV2StepFrame(-1)")
    assert left_pos < step_call_pos < body.index('"ArrowRight"')


def test_arrow_right_steps_to_next_frame():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2OnKeyDown")
    right_pos = body.index('"ArrowRight"')
    step_call_pos = body.index("physicalRefV2StepFrame(1)")
    assert step_call_pos > right_pos


def test_step_frame_uses_the_existing_slider_seek_path():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2StepFrame")
    assert 'document.getElementById("progress")' in body
    assert "seek()" in body
    # No duplicated frame-change logic -- it delegates to the exact same
    # path the slider's own oninput already uses.
    assert "img.onload" not in body
    assert "fetch(" not in body


# --- 13-16. shortcuts suppressed inside form controls -------------------------


def test_editable_target_check_covers_input_textarea_select_contenteditable():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2IsEditableTarget")
    assert '"input"' in body
    assert '"textarea"' in body
    assert '"select"' in body
    assert "isContentEditable" in body


def test_keydown_handler_checks_editable_target_before_acting():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2OnKeyDown")
    editable_check_pos = body.index("physicalRefV2IsEditableTarget(evt.target)")
    arrow_left_pos = body.index('"ArrowLeft"')
    assert editable_check_pos < arrow_left_pos


# --- 17. shortcut never saves --------------------------------------------------


def test_keyboard_stepping_never_calls_save():
    keydown_body = _extract_js_function_body(JS_SOURCE, "physicalRefV2OnKeyDown")
    step_body = _extract_js_function_body(JS_SOURCE, "physicalRefV2StepFrame")
    assert "physicalRefSave(" not in keydown_body
    assert "physicalRefSave(" not in step_body


def test_keyboard_hint_is_visible_in_html():
    assert "step frame" in HTML_SOURCE


# --- 18. tracker overlays remain independent of physical annotations -------


def test_tracker_overlay_toggle_independent_of_person_ref_state():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefFrameUrl")
    assert "draw_tracks" in body
    assert "physicalRefV2ActivePersonRef" not in body
    assert "physicalRefDrawnDistractors" not in body


def test_canvas_labels_function_does_not_depend_on_overlay_visibility():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRepaint")
    assert "physicalRefShowOverlays" not in body


# --- 19. legacy annotation mode remains wired ---------------------------------


def test_legacy_annotation_workspace_still_present_in_html():
    assert 'id="annotationWorkspace"' in HTML_SOURCE
    assert 'value="annotation"' in HTML_SOURCE


def test_v1_frontend_and_backend_files_not_deleted():
    v1_js = REPO_ROOT / "tools/bag_annotation_ui/static/tim_physical_reference_ui.js"
    v1_backend = REPO_ROOT / "tools/bag_annotation_ui/tim_ui_physical_reference.py"
    v1_tests = REPO_ROOT / "tools/tests/test_tim_ui_physical_reference.py"
    assert v1_js.exists()
    assert v1_backend.exists()
    assert v1_tests.exists()


# --- evaluation_window / right-boundary anchor, derived not invented -------


def test_evaluation_window_derived_from_frame_times_s_first_and_last():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2EvaluationWindow")
    assert "frameTimesS[0]" in body
    assert "frameTimesS[frameTimesS.length - 1]" in body
    # Checked against the code only (comments stripped) -- the function's
    # own comment explicitly lists what it deliberately does NOT do, which
    # would otherwise trip a naive substring check on the prose itself.
    code_only = _strip_js_line_comments(body)
    for forbidden in ("DEFAULT_STEP_S", "0.05", "nextafter", "epsilon"):
        assert forbidden not in code_only


def test_right_boundary_anchor_hint_present_in_frame_update():
    body = _extract_js_function_body(JS_SOURCE, "updatePhysicalRefFrame")
    assert "isRightBoundaryAnchor" in body
    assert "evalWindow.end_s" in body


# --- no tracker-ID concept anywhere in the v2 frontend source --------------


def test_v2_js_source_never_references_tracker_id_fields():
    assert "correct_target_track_id" not in JS_SOURCE
    assert "trackerId" not in JS_SOURCE
    assert "tracker_id" not in JS_SOURCE


def test_v2_js_exposes_the_same_feature_detection_globals_tim_clean_ui_expects():
    assert "window.shouldOpenPhysicalRefWorkspace = shouldOpenPhysicalRefWorkspace" in JS_SOURCE
    assert "window.updatePhysicalRefFrame = updatePhysicalRefFrame" in JS_SOURCE


# =============================================================================
# Human-smoke corrective fix: tracker overlay toggle must be a pure
# presentation operation and must never mutate/discard an unsaved
# physical-reference draft (target bbox, distractor bboxes, person_ref
# associations/selection, identity_state/context, draw mode, or the
# interpolation flag). Only an actual frame change may reset the draft --
# see physicalRefSyncDraftToCurrentFrame, still invoked only from
# updatePhysicalRefFrame (real navigation), never from
# physicalRefRefreshOverlayImage (overlay-visibility-only redraw).
# =============================================================================


# --- 1/2/3/4/10. overlay refresh never resyncs/clears the frame-local draft -


def test_overlay_refresh_never_resyncs_frame_local_draft():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefSyncDraftToCurrentFrame" not in body
    # Not just "doesn't call the sync function" -- also never re-implements
    # its clearing assignments inline.
    assert "physicalRefDrawnTarget = null" not in body
    assert "physicalRefDrawnDistractors = []" not in body


# --- 5. pending newly-created phys_dNNN selection survives the toggle -------


def test_overlay_refresh_preserves_active_person_ref_selection():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefV2ActivePersonRef" not in body


# --- 6/8. identity_state/context and draw mode survive the toggle ----------


def test_overlay_refresh_never_touches_state_context_or_draw_mode_controls():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefState" not in body
    assert "physicalRefContext" not in body
    assert "physicalRefDrawMode" not in body


# --- 7. interpolation checkbox state survives the toggle --------------------


def test_overlay_refresh_never_touches_interpolate_checkbox():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefInterpolate" not in body


# --- 9. overlay toggle never autosaves ---------------------------------------


def test_overlay_refresh_never_calls_save():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefSave(" not in body


# --- 11/12/13. overlays actually change, physical annotations stay visible -


def test_overlay_refresh_reloads_image_and_repaints():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    # Re-fetches the frame (tracker-overlay pixels are baked server-side into
    # the JPEG by physicalRefFrameUrl's draw_tracks param, so a real image
    # reload -- not a pure canvas re-render -- is genuinely required), then
    # repaints from the *current, untouched* draft/saved state, which is
    # exactly what makes physical Target/phys_dNNN boxes and labels remain
    # visible regardless of overlay visibility (physicalRefRepaint already
    # draws them unconditionally -- see test_canvas_labels_use_person_ref_not_positional_labels
    # and test_canvas_labels_function_does_not_depend_on_overlay_visibility).
    assert "physicalRefLoadFrameImage(idx" in body
    assert "physicalRefRepaint()" in body


# --- root cause / fix: the checkbox is wired to the pure-repaint path ------


def test_overlay_checkbox_wired_to_pure_refresh_not_frame_update():
    checkbox_marker = 'id="physicalRefShowOverlays"'
    assert checkbox_marker in HTML_SOURCE
    start = HTML_SOURCE.index(checkbox_marker)
    tag_end = HTML_SOURCE.index(">", start)
    tag = HTML_SOURCE[start:tag_end]
    assert 'onchange="physicalRefRefreshOverlayImage()"' in tag
    # This is the exact root cause of the human-verified bug: the checkbox
    # used to call the frame-navigation function directly, which discarded
    # any unsaved draft via physicalRefSyncDraftToCurrentFrame.
    assert "onchange=\"updatePhysicalRefFrame()\"" not in tag


# --- 14/15. real frame navigation is NOT weakened ----------------------------


def test_update_physical_ref_frame_still_resyncs_draft_on_real_navigation():
    body = _extract_js_function_body(JS_SOURCE, "updatePhysicalRefFrame")
    assert "physicalRefSyncDraftToCurrentFrame()" in body


def test_sync_draft_clear_branch_still_resets_interpolation_checkbox():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_pos = body.index("if (idx >= 0)")
    clear_branch = body[body.index("}", idx_branch_pos) :]
    assert "interpolateCheckbox.checked = false" in clear_branch


# --- structural separation: image loading is pure fetch/buffer mechanics ---


def test_load_frame_image_helper_has_no_draft_state_coupling():
    """physicalRefLoadFrameImage is the one place both the real-navigation
    path and the overlay-only-redraw path fetch the frame JPEG. It must stay
    pure image-fetch/canvas-buffer-sizing mechanics -- draft-state decisions
    (resync vs. leave alone) belong entirely to each caller's onReady
    callback, never to the shared loader itself."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadFrameImage")
    assert "physicalRefSyncDraftToCurrentFrame" not in body
    assert "physicalRefDrawnTarget" not in body
    assert "physicalRefDrawnDistractors" not in body
    assert "physicalRefV2ActivePersonRef" not in body
    assert "physicalRefInterpolate" not in body


def test_both_frame_update_and_overlay_refresh_share_the_image_loading_helper():
    """No duplicated fetch/canvas-sizing logic between the two call sites --
    both funnel through the same physicalRefLoadFrameImage helper, so the
    coordinate contract (canvas buffer = natural image size) can never drift
    between the navigation path and the overlay-toggle path."""
    nav_body = _extract_js_function_body(JS_SOURCE, "updatePhysicalRefFrame")
    overlay_body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefLoadFrameImage(idx" in nav_body
    assert "physicalRefLoadFrameImage(idx" in overlay_body
    assert "new Image()" not in nav_body
    assert "new Image()" not in overlay_body


def test_overlay_refresh_exposed_as_feature_detection_global():
    assert "window.physicalRefRefreshOverlayImage = physicalRefRefreshOverlayImage" in JS_SOURCE


# =============================================================================
# Human-smoke corrective fix #2: the active-person status chip must reflect
# CURRENT UI STATE (whether the active person_ref already has a bbox in the
# current draft/sample), not merely how it was originally created. Two
# independent concepts must never be conflated:
#   - historically known (person_ref appears in a SAVED sample somewhere in
#     the artifact) vs. brand new (not saved anywhere yet);
#   - drawn on the current frame right now (has a bbox in
#     physicalRefDrawnDistractors) vs. not drawn on the current frame.
# See physicalRefV2ActivePersonRefStatusSuffix.
# =============================================================================


def _status_suffix_body():
    return _extract_js_function_body(JS_SOURCE, "physicalRefV2ActivePersonRefStatusSuffix")


# --- 1/6. not-drawn wording, new vs. historically known ----------------------


def test_status_suffix_new_person_not_drawn_says_new_not_yet_drawn():
    body = _status_suffix_body()
    assert '" (new, not yet drawn)"' in body


def test_status_suffix_historically_known_not_drawn_says_not_drawn_on_this_frame():
    body = _status_suffix_body()
    assert '" (not drawn on this frame)"' in body
    # The two wordings are the two arms of one ternary keyed on
    # isHistoricallyKnown -- never two independently-computed strings that
    # could drift apart.
    assert "isHistoricallyKnown ?" in body


# --- 2/7. once drawn, "not yet drawn" can never be shown, regardless of ----
# --- whether the person is new or historically known -----------------------


def test_status_suffix_drawn_now_never_says_not_drawn_regardless_of_history():
    body = _status_suffix_body()
    guard_pos = body.index("if (drawnNow)")
    ternary_pos = body.index("isHistoricallyKnown ?")
    # The drawn-now guard is checked, and returns, strictly before the
    # historically-known ternary is ever reached -- so a drawn box can never
    # fall through into either "not drawn" wording, whether the identity is
    # brand new or historically known.
    assert guard_pos < ternary_pos
    return_pos = body.index("return \"\";", guard_pos)
    assert guard_pos < return_pos < ternary_pos


def test_status_suffix_checks_the_current_draft_not_saved_samples():
    body = _status_suffix_body()
    assert "physicalRefDrawnDistractors.some" in body
    # Drawn-status must never be derived from physicalRefSamples (saved
    # data) -- it is purely a current-draft/current-frame question,
    # independent of whether a save has happened.
    assert "physicalRefSamples" not in body


# --- 3. status updates immediately after drawing, no save required --------


def test_drawing_a_distractor_rerenders_palette_immediately_without_saving():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefOnPointerUp")
    push_pos = body.index("physicalRefDrawnDistractors.push(")
    render_pos = body.index("physicalRefV2RenderPersonRefPalette();", push_pos)
    assert push_pos < render_pos
    between = body[push_pos:render_pos]
    assert "physicalRefSave(" not in between
    assert "fetch(" not in between


# --- 4. removing the current-frame bbox returns status to not-drawn -------


def test_removing_a_distractor_rerenders_palette_immediately_without_saving():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRemoveDistractor")
    splice_pos = body.index("physicalRefDrawnDistractors.splice(")
    render_pos = body.index("physicalRefV2RenderPersonRefPalette();", splice_pos)
    assert splice_pos < render_pos
    between = body[splice_pos:render_pos]
    assert "physicalRefSave(" not in between


# --- 5. historically known chips are never wired through the "new" branch --


def test_known_chip_loop_passes_historically_known_true_to_status_suffix():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2RenderPersonRefPalette")
    known_loop = body[: body.index("if (physicalRefV2ActivePersonRef && known.indexOf")]
    assert "physicalRefV2ActivePersonRefStatusSuffix(ref, true)" in known_loop


def test_pending_new_chip_passes_historically_known_false_to_status_suffix():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2RenderPersonRefPalette")
    pending_branch = body[body.index("if (physicalRefV2ActivePersonRef && known.indexOf") :]
    assert "physicalRefV2ActivePersonRefStatusSuffix(physicalRefV2ActivePersonRef, false)" in pending_branch


def test_only_the_active_selection_receives_a_drawn_status_suffix():
    """Non-active known chips stay plain -- per-frame drawn status is only
    meaningful, and only shown, for whichever person_ref the annotator has
    actually selected right now."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2RenderPersonRefPalette")
    known_loop = body[: body.index("if (physicalRefV2ActivePersonRef && known.indexOf")]
    assert "isActive ? physicalRefV2ActivePersonRefStatusSuffix(ref, true) : \"\"" in known_loop


# --- 8. overlay refresh must not alter or recompute person_ref status ------


def test_overlay_refresh_still_never_touches_the_person_ref_palette():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefV2RenderPersonRefPalette" not in body
    assert "physicalRefV2ActivePersonRefStatusSuffix" not in body


# --- 9. real frame navigation recalculates status from the new frame ------


def test_sync_draft_to_frame_rerenders_palette_in_both_branches():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefSyncDraftToCurrentFrame")
    idx_branch_pos = body.index("if (idx >= 0)")
    saved_sample_branch = body[idx_branch_pos : body.index("}", idx_branch_pos)]
    clear_branch = body[body.index("}", idx_branch_pos) :]
    # Saved-sample branch delegates to physicalRefLoadSampleIntoForm, which
    # itself re-renders the palette (checked below) -- the no-saved-sample
    # (clear) branch re-renders it directly.
    assert "physicalRefLoadSampleIntoForm(idx" in saved_sample_branch
    assert "physicalRefV2RenderPersonRefPalette();" in clear_branch


def test_load_sample_into_form_rerenders_palette_for_the_new_frame():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadSampleIntoForm")
    assert "physicalRefV2RenderPersonRefPalette();" in body


# --- 10. deterministic person_ref generation policy is unchanged -----------


def test_next_person_ref_policy_untouched_by_the_status_suffix_fix():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefV2NextPersonRef")
    assert "used.has(n)" in body
    assert "phys_d" in body
    assert "physicalRefV2ActivePersonRefStatusSuffix" not in body
    assert "physicalRefDrawnDistractors" not in body


# =============================================================================
# Human-smoke corrective fix #3: an explicit "Load selected JSON" must fully
# replace the physical-reference editing state, not just the in-memory
# sample table. Before this fix, physicalRefLoadSelected() replaced
# physicalRefSamples but never resynced the current-frame draft, so a stale
# (possibly backend-rejected, never-persisted) unsaved Target bbox,
# distractor bboxes, and interpolation checkbox kept displaying on the
# canvas as though they belonged to the freshly loaded artifact. Fixed by
# having physicalRefLoadSelected() call physicalRefSyncDraftToCurrentFrame()
# -- the same function real frame navigation already uses -- after
# replacing physicalRefSamples, so the current frame's draft is
# reconstructed strictly from the newly loaded artifact: its own saved
# sample if one exists at this timestamp, otherwise a fully cleared draft.
# =============================================================================


def _load_selected_body():
    return _extract_js_function_body(JS_SOURCE, "physicalRefLoadSelected")


# --- 1/9. successful load replaces (never merges/appends to) the samples ---


def test_load_selected_replaces_the_sample_collection_wholesale():
    body = _load_selected_body()
    assert "physicalRefSamples = data.samples || []" in body
    # Assignment, never appended/merged -- a stale in-memory (e.g.
    # backend-rejected) sample can never survive a load alongside the
    # freshly loaded ones.
    assert "physicalRefSamples.push(" not in body
    assert "physicalRefSamples.concat(" not in body


def test_load_selected_never_preserves_any_pre_load_sample_state():
    body = _load_selected_body()
    assert "...physicalRefSamples" not in body
    assert "physicalRefSamples.filter(" not in body


# --- 2-6. current-frame draft is resynced strictly from the loaded artifact


def test_load_selected_resyncs_the_current_frame_draft_after_replacing_samples():
    body = _load_selected_body()
    samples_pos = body.index("physicalRefSamples = data.samples || []")
    sync_pos = body.index("physicalRefSyncDraftToCurrentFrame()")
    assert samples_pos < sync_pos


def test_load_selected_does_not_duplicate_the_draft_clearing_logic():
    """The clearing/restoring logic itself lives in exactly one place
    (physicalRefSyncDraftToCurrentFrame) -- physicalRefLoadSelected must
    delegate to it rather than re-implementing a second, potentially
    diverging, reset (which is exactly the class of bug this fix
    corrects: a second, forgotten code path that didn't get updated)."""
    body = _load_selected_body()
    assert "physicalRefDrawnTarget = null" not in body
    assert "physicalRefDrawnDistractors = []" not in body
    assert "interpolateCheckbox.checked = false" not in body


def test_load_selected_known_person_palette_reflects_only_loaded_samples():
    """physicalRefV2RenderPersonRefPalette derives its 'known' list from the
    global physicalRefSamples, which physicalRefLoadSelected reassigns to
    data.samples before the palette is re-rendered (via
    physicalRefSyncDraftToCurrentFrame(), called after the reassignment) --
    so a stale pre-load palette entry can never survive a load."""
    palette_body = _extract_js_function_body(JS_SOURCE, "physicalRefV2RenderPersonRefPalette")
    assert "physicalRefV2KnownPersonRefsFromSamples(physicalRefSamples)" in palette_body
    load_body = _load_selected_body()
    assign_pos = load_body.index("physicalRefSamples = data.samples || []")
    sync_pos = load_body.index("physicalRefSyncDraftToCurrentFrame()")
    assert assign_pos < sync_pos


# --- 7/8. a loaded saved sample at the current frame restores exactly -----


def test_sync_draft_restores_saved_sample_geometry_and_interpolation_exactly():
    """The restore logic real navigation already relies on, and which the
    load path now reuses verbatim (see
    test_load_selected_resyncs_the_current_frame_draft_after_replacing_samples)
    -- proven directly here for traceability against this fix's own
    requirement list."""
    body = _extract_js_function_body(JS_SOURCE, "physicalRefLoadSampleIntoForm")
    assert "physicalRefDrawnTarget = s.target_bbox_xyxy" in body
    assert "physicalRefDrawnDistractors = (s.distractors || [])" in body
    assert 'physicalRefInterpolate").checked = !!s.interpolate_from_previous' in body


# --- 10. overlay refresh (already human-verified) is not regressed --------


def test_overlay_refresh_still_never_calls_load_selected_or_sync():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshOverlayImage")
    assert "physicalRefLoadSelected" not in body
    assert "physicalRefSyncDraftToCurrentFrame" not in body


# --- 11. real frame navigation (already human-verified) is not regressed --


def test_update_physical_ref_frame_still_resyncs_draft_via_the_same_shared_function():
    body = _extract_js_function_body(JS_SOURCE, "updatePhysicalRefFrame")
    assert "physicalRefSyncDraftToCurrentFrame()" in body


# --- 12. explicit load never autosaves --------------------------------------


def test_load_selected_never_calls_save():
    body = _load_selected_body()
    assert "physicalRefSave(" not in body


# =============================================================================
# Assisted M4B review: evaluator-backed effective preview
# =============================================================================


def _two_anchor_preview_payload(*, interpolate=True, changed_set=False):
    provenance = _artifact_payload()["provenance"]
    provenance["evaluation_window"] = {"start_s": 0.0, "end_s": 10.0}
    first_distractors = [
        _distractor("phys_d001", [20.0, 0.0, 30.0, 10.0]),
        _distractor("phys_d002", [40.0, 0.0, 50.0, 10.0]),
    ]
    last_distractors = [
        _distractor("phys_d001", [30.0, 10.0, 40.0, 20.0]),
        _distractor("phys_d002", [50.0, 10.0, 60.0, 20.0]),
    ]
    if changed_set:
        last_distractors = last_distractors[:1]
    return {
        "provenance": provenance,
        "samples": [
            {
                "t_s": 0.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [0.0, 0.0, 10.0, 10.0],
                "distractors": first_distractors,
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 10.0,
                "identity_state": "present_scored",
                "identity_context": "distractors_complete",
                "target_bbox_xyxy": [10.0, 10.0, 20.0, 20.0],
                "distractors": last_distractors,
                "interpolate_from_previous": interpolate,
                "notes": "",
            },
        ],
    }


def test_preview_reuses_the_evaluator_canonical_resolver():
    evaluator = sys.modules["physical_target_bbox_evaluation_v2"]
    assert UI2.resolve_reference_interval is evaluator.resolve_reference_interval
    source = inspect.getsource(UI2.resolve_effective_reference_preview)
    assert "resolve_reference_interval(artifact.samples, t)" in source


def test_preview_classifies_exact_keyframes_and_final_right_boundary():
    payload = _two_anchor_preview_payload()
    previews = UI2.build_effective_reference_previews(payload, [0.0, 10.0])
    assert [item["classification"] for item in previews] == [
        "explicit_keyframe",
        "explicit_keyframe",
    ]
    assert previews[1]["t_s"] == 10.0
    assert previews[1]["target_bbox_xyxy"] == [10.0, 10.0, 20.0, 20.0]


def test_preview_interpolates_target_with_evaluator_geometry():
    payload = _two_anchor_preview_payload()
    preview = UI2.build_effective_reference_previews(payload, [5.0])[0]
    assert preview["classification"] == "interpolated"
    assert preview["target_bbox_xyxy"] == pytest.approx([5.0, 5.0, 15.0, 15.0])


def test_preview_interpolates_distractors_by_stable_person_ref():
    payload = _two_anchor_preview_payload()
    preview = UI2.build_effective_reference_previews(payload, [5.0])[0]
    by_ref = {
        entry["person_ref"]: entry["bbox_xyxy"]
        for entry in preview["distractors"]
    }
    assert sorted(by_ref) == ["phys_d001", "phys_d002"]
    assert by_ref["phys_d001"] == pytest.approx([25.0, 5.0, 35.0, 15.0])
    assert by_ref["phys_d002"] == pytest.approx([45.0, 5.0, 55.0, 15.0])


def test_changed_person_set_without_interpolation_is_previewed_as_gap():
    payload = _two_anchor_preview_payload(interpolate=False, changed_set=True)
    preview = UI2.build_effective_reference_previews(payload, [5.0])[0]
    assert preview["classification"] == "reference_gap"
    assert preview["target_bbox_xyxy"] is None
    assert preview["distractors"] == []


def test_changed_person_set_cannot_claim_preview_interpolation():
    payload = _two_anchor_preview_payload(interpolate=True, changed_set=True)
    with pytest.raises(PTR2.PhysicalReferenceValidationError, match="correspondence"):
        UI2.build_effective_reference_previews(payload, [5.0])


def test_preview_classifies_absent_unavailable_and_gap_without_geometry():
    provenance = _artifact_payload()["provenance"]
    provenance["evaluation_window"] = {"start_s": 0.0, "end_s": 6.0}
    payload = {
        "provenance": provenance,
        "samples": [
            {
                "t_s": 0.0,
                "identity_state": "absent",
                "identity_context": None,
                "target_bbox_xyxy": None,
                "distractors": [],
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 2.0,
                "identity_state": "present_reference_unavailable",
                "identity_context": None,
                "target_bbox_xyxy": None,
                "distractors": [],
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 4.0,
                "identity_state": "present_scored",
                "identity_context": "target_only",
                "target_bbox_xyxy": [0.0, 0.0, 10.0, 10.0],
                "distractors": [],
                "interpolate_from_previous": False,
                "notes": "",
            },
            {
                "t_s": 6.0,
                "identity_state": "present_scored",
                "identity_context": "target_only",
                "target_bbox_xyxy": [2.0, 0.0, 12.0, 10.0],
                "distractors": [],
                "interpolate_from_previous": False,
                "notes": "",
            },
        ],
    }
    previews = UI2.build_effective_reference_previews(payload, [1.0, 3.0, 5.0])
    assert [item["classification"] for item in previews] == [
        "absent",
        "present_reference_unavailable",
        "reference_gap",
    ]
    assert all(item["target_bbox_xyxy"] is None for item in previews)


def test_preview_batch_does_not_mutate_artifact_payload():
    payload = _two_anchor_preview_payload()
    original = copy.deepcopy(payload)
    UI2.build_effective_reference_previews(payload, [0.0, 1.0, 5.0, 10.0])
    assert payload == original


# =============================================================================
# Assisted M4B review: ephemeral optical-flow geometry proposals
# =============================================================================


def test_optical_flow_proposal_preserves_human_refs_and_translates_geometry():
    rng = UI2.np.random.default_rng(25)
    base = rng.integers(0, 256, size=(90, 120), dtype=UI2.np.uint8)
    first = UI2.cv2.cvtColor(base, UI2.cv2.COLOR_GRAY2BGR)
    transform = UI2.np.float32([[1.0, 0.0, 4.0], [0.0, 1.0, 3.0]])
    second = UI2.cv2.warpAffine(first, transform, (120, 90))

    target = [10.0, 10.0, 40.0, 50.0]
    distractors = [
        _distractor("phys_d002", [70.0, 20.0, 105.0, 60.0]),
        _distractor("phys_d001", [45.0, 30.0, 65.0, 70.0]),
    ]
    original_target = copy.deepcopy(target)
    original_distractors = copy.deepcopy(distractors)

    proposal = UI2.propose_geometry_with_optical_flow(
        [first, second], 0, 1, target, distractors
    )

    assert proposal["method"] == "sparse_lk_median_translation"
    assert proposal["accepted"] is False
    assert proposal["identity_source"] == "human_anchor_person_refs_only"
    assert proposal["target_bbox_xyxy"] == pytest.approx(
        [14.0, 13.0, 44.0, 53.0], abs=0.8
    )
    assert [d["person_ref"] for d in proposal["distractors"]] == [
        "phys_d001",
        "phys_d002",
    ]
    assert target == original_target
    assert distractors == original_distractors


def test_optical_flow_proposal_refuses_long_unreviewed_jump():
    image = UI2.np.zeros((20, 20, 3), dtype=UI2.np.uint8)
    images = [image] * (UI2.MAX_OPTICAL_FLOW_FRAME_DISTANCE + 2)
    with pytest.raises(UI2.PhysicalReferenceUIError, match="maximum"):
        UI2.propose_geometry_with_optical_flow(
            images,
            0,
            UI2.MAX_OPTICAL_FLOW_FRAME_DISTANCE + 1,
            [1.0, 1.0, 10.0, 15.0],
            [],
        )


def test_proposal_request_cannot_modify_or_save_reference():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRequestProposal")
    assert "physicalRefSamples" not in body
    assert "physicalRefUpdateActiveSample" not in body
    assert "physicalRefSave" not in body
    assert 'fetch("/api/physical_reference_v2/propose"' in body


def test_preview_request_cannot_modify_samples_or_save_reference():
    body = _extract_js_function_body(JS_SOURCE, "physicalRefRefreshEffectivePreview")
    assert "physicalRefSamples[" not in body
    assert "physicalRefSamples =" not in body
    assert "physicalRefSave" not in body
    assert 'fetch("/api/physical_reference_v2/preview"' in body


def test_proposal_acceptance_is_explicit_in_memory_and_never_saves_json():
    assert 'onclick="physicalRefAcceptProposalAsAnchor()"' in HTML_SOURCE
    body = _extract_js_function_body(JS_SOURCE, "physicalRefAcceptProposalAsAnchor")
    assert "physicalRefCopyProposalToDraft()" in body
    assert "physicalRefUpdateActiveSample()" in body
    assert "physicalRefSave" not in body
    assert "JSON is still unchanged" in body


def test_effective_preview_toggle_defaults_on_and_styles_are_distinct():
    marker = 'id="physicalRefShowEffective"'
    assert marker in HTML_SOURCE
    tag_start = HTML_SOURCE.rfind("<input", 0, HTML_SOURCE.index(marker))
    tag_end = HTML_SOURCE.index(">", HTML_SOURCE.index(marker))
    tag = HTML_SOURCE[tag_start:tag_end]
    assert "checked" in tag
    assert 'onchange="physicalRefOnEffectiveToggle()"' in tag

    repaint = _extract_js_function_body(JS_SOURCE, "physicalRefRepaint")
    assert '"#22d3ee"' in repaint
    assert '"#ffe066"' in repaint
    assert "ctx.setLineDash([10, 7])" in repaint
    assert "ctx.setLineDash([3, 6])" in repaint


def test_proposal_backend_has_no_tracker_or_detector_identity_inputs():
    signature = inspect.signature(UI2.propose_geometry_with_optical_flow)
    assert set(signature.parameters) == {
        "images",
        "anchor_frame_index",
        "target_frame_index",
        "target_bbox_xyxy",
        "distractors",
    }


# =============================================================================
# M4B sequential image-only proposal propagation
# =============================================================================


def _sequence_fixture(frame_count=31, dx_per_frame=1, with_distractor=True):
    rng = UI2.np.random.default_rng(2508)
    target_patch = rng.integers(0, 256, size=(24, 20, 3), dtype=UI2.np.uint8)
    distractor_patch = rng.integers(0, 256, size=(22, 18, 3), dtype=UI2.np.uint8)
    images = []
    for frame_index in range(frame_count):
        image = UI2.np.zeros((100, 140, 3), dtype=UI2.np.uint8)
        x = 10 + dx_per_frame * frame_index
        image[20:44, x : x + 20] = target_patch
        if with_distractor:
            image[58:80, 95 - frame_index : 113 - frame_index] = distractor_patch
        images.append(image)
    end_s = float(frame_count - 1) / 10.0
    first_distractors = (
        [_distractor("phys_d001", [95.0, 58.0, 113.0, 80.0])]
        if with_distractor
        else []
    )
    last_distractors = (
        [
            _distractor(
                "phys_d001",
                [95.0 - (frame_count - 1), 58.0, 113.0 - (frame_count - 1), 80.0],
            )
        ]
        if with_distractor
        else []
    )
    context = "distractors_complete" if with_distractor else "target_only"
    artifact = _artifact_payload()
    artifact["provenance"]["source_width"] = 140
    artifact["provenance"]["source_height"] = 100
    artifact["provenance"]["evaluation_window"] = {"start_s": 0.0, "end_s": end_s}
    artifact["samples"] = [
        {
            "t_s": 0.0,
            "identity_state": "present_scored",
            "identity_context": context,
            "target_bbox_xyxy": [10.0, 20.0, 30.0, 44.0],
            "distractors": first_distractors,
            "interpolate_from_previous": False,
            "notes": "",
        },
        {
            "t_s": end_s,
            "identity_state": "present_scored",
            "identity_context": context,
            "target_bbox_xyxy": [
                10.0 + dx_per_frame * (frame_count - 1),
                20.0,
                30.0 + dx_per_frame * (frame_count - 1),
                44.0,
            ],
            "distractors": last_distractors,
            "interpolate_from_previous": True,
            "notes": "",
        },
    ]
    return images, [index / 10.0 for index in range(frame_count)], artifact


def test_sequential_optical_flow_propagates_every_frame_and_preserves_labels():
    images, times_s, artifact = _sequence_fixture()
    result = UI2.generate_sequence_proposals(images, times_s, artifact)

    assert result["method"] == UI2.SEQUENCE_PROPAGATION_METHOD
    assert result["identity_source"] == "explicit_human_anchor_person_refs_only"
    assert result["detector_refinement_used"] is False
    assert len(result["proposals"]) == len(images)
    middle = result["proposals"][15]
    assert middle["classification"] == "automatic_proposal"
    assert middle["target_bbox_xyxy"] == pytest.approx([25, 20, 45, 44], abs=1.5)
    assert [item["person_ref"] for item in middle["distractors"]] == ["phys_d001"]
    assert middle["distractors"][0]["bbox_xyxy"] == pytest.approx(
        [80, 58, 98, 80], abs=1.5
    )
    assert result["proposals"][0]["classification"] == "explicit_anchor"
    assert result["proposals"][-1]["classification"] == "explicit_anchor"


def test_sequential_generation_normalizes_and_clips_boxes_to_source_bounds():
    image = UI2.np.zeros((40, 40, 3), dtype=UI2.np.uint8)
    clipped = UI2._clip_box_to_image((38.0, 35.0, 20.0, 50.0), 40, 40)
    assert clipped == (20.0, 35.0, 38.0, 40.0)
    assert UI2._clip_box_to_image((50.0, 50.0, 60.0, 60.0), 40, 40) is None
    assert image.shape == (40, 40, 3)


def test_anonymous_detector_geometry_can_refine_size_but_not_identity():
    result = UI2.refine_box_with_anonymous_detections(
        [10.0, 10.0, 30.0, 50.0], [[9.0, 8.0, 33.0, 54.0]]
    )
    assert result["status"] == "refined"
    assert result["bbox_xyxy"] == [9.0, 8.0, 33.0, 54.0]
    assert result["used_detector_geometry"] is True
    signature = inspect.signature(UI2.refine_box_with_anonymous_detections)
    assert set(signature.parameters) == {
        "propagated_box",
        "anonymous_detection_boxes",
    }
    with pytest.raises(UI2.PhysicalReferenceUIError, match="coordinate lists only"):
        UI2.refine_box_with_anonymous_detections(
            [10.0, 10.0, 30.0, 50.0],
            [{"tracker_id": 7, "bbox_xyxy": [9.0, 8.0, 33.0, 54.0]}],
        )


def test_multiple_plausible_anonymous_detections_are_ambiguous_not_guessed():
    result = UI2.refine_box_with_anonymous_detections(
        [10.0, 10.0, 30.0, 50.0],
        [[11.0, 10.0, 31.0, 50.0], [9.0, 10.0, 29.0, 50.0]],
    )
    assert result["status"] == "ambiguous"
    assert result["used_detector_geometry"] is False
    assert result["bbox_xyxy"] == [10.0, 10.0, 30.0, 50.0]


def test_sequence_cache_key_is_deterministic_and_artifact_sensitive():
    _, times_s, artifact = _sequence_fixture(frame_count=5, with_distractor=False)
    first = UI2.sequence_proposal_cache_key(artifact, times_s, 5)
    assert UI2.sequence_proposal_cache_key(copy.deepcopy(artifact), times_s, 5) == first
    changed = copy.deepcopy(artifact)
    changed["samples"][0]["target_bbox_xyxy"][0] += 1.0
    assert UI2.sequence_proposal_cache_key(changed, times_s, 5) != first


def test_full_sequence_generation_does_not_mutate_reference_artifact():
    images, times_s, artifact = _sequence_fixture(frame_count=15)
    before = copy.deepcopy(artifact)
    result = UI2.generate_sequence_proposals(images, times_s, artifact)
    assert artifact == before
    assert result["accepted"] is False
    assert result["saved"] is False


def _proposal_frame(index, box, confidence="high", classification="automatic_proposal"):
    return {
        "frame_index": index,
        "t_s": index / 10.0,
        "classification": classification,
        "target_bbox_xyxy": list(box) if box is not None else None,
        "target_confidence": confidence,
        "distractors": [],
        "overall_confidence": confidence,
    }


def _effective_frame(box):
    return {
        "classification": "interpolated",
        "target_bbox_xyxy": list(box) if box is not None else None,
        "distractors": [],
    }


def test_review_frames_are_grouped_into_regions_with_peak_navigation_frame():
    proposals = [_proposal_frame(i, [i, 0, i + 10, 20]) for i in range(10)]
    effective = [_effective_frame([i, 0, i + 10, 20]) for i in range(10)]
    for index in (2, 3, 4, 8):
        effective[index] = _effective_frame([index + 20, 0, index + 30, 20])
    regions = UI2.compute_review_regions(proposals, effective, max_clean_gap_frames=0)
    assert [(r["start_frame_index"], r["end_frame_index"]) for r in regions] == [
        (2, 4),
        (8, 8),
    ]
    assert all("target" in region["labels"] for region in regions)
    assert regions[0]["peak_frame_index"] in {2, 3, 4}


def test_adaptive_anchor_selection_recursively_splits_nonlinear_span():
    proposals = []
    for index in range(41):
        shift = 18.0 * UI2.math.sin(UI2.math.pi * index / 40.0)
        classification = "explicit_anchor" if index in {0, 40} else "automatic_proposal"
        proposals.append(
            _proposal_frame(index, [shift, 0.0, shift + 10.0, 20.0], classification=classification)
        )
    suggestions = UI2.suggest_adaptive_anchor_frames(
        proposals, [0, 40], min_span_frames=3, max_suggestions=8
    )
    assert suggestions
    assert any(abs(item["frame_index"] - 20) <= 2 for item in suggestions)
    assert all(item["accepted"] is False for item in suggestions)


def test_changed_person_sets_and_absence_stop_sequence_identity_propagation():
    images = [UI2.np.zeros((50, 50, 3), dtype=UI2.np.uint8) for _ in range(21)]
    artifact = _artifact_payload()
    artifact["provenance"]["source_width"] = 50
    artifact["provenance"]["source_height"] = 50
    artifact["provenance"]["evaluation_window"] = {"start_s": 0.0, "end_s": 2.0}
    artifact["samples"] = [
        {
            "t_s": 0.0,
            "identity_state": "present_scored",
            "identity_context": "target_only",
            "target_bbox_xyxy": [5.0, 5.0, 20.0, 30.0],
            "distractors": [],
            "interpolate_from_previous": False,
            "notes": "",
        },
        {
            "t_s": 1.0,
            "identity_state": "absent",
            "identity_context": None,
            "target_bbox_xyxy": None,
            "distractors": [],
            "interpolate_from_previous": False,
            "notes": "",
        },
        {
            "t_s": 2.0,
            "identity_state": "present_scored",
            "identity_context": "distractors_complete",
            "target_bbox_xyxy": [10.0, 5.0, 25.0, 30.0],
            "distractors": [_distractor("phys_d001", [30.0, 5.0, 45.0, 30.0])],
            "interpolate_from_previous": False,
            "notes": "",
        },
    ]
    result = UI2.generate_sequence_proposals(
        images, [index / 10.0 for index in range(21)], artifact
    )
    assert result["proposals"][10]["classification"] == "explicit_state"
    assert result["proposals"][5]["classification"] == "unsupported_reference_span"
    assert result["proposals"][15]["classification"] == "unsupported_reference_span"
    assert result["proposals"][5]["target_bbox_xyxy"] is None


def test_sequence_ui_requires_explicit_acceptance_and_keeps_save_separate():
    assert 'onclick="physicalRefStartSequenceProposals()"' in HTML_SOURCE
    assert 'onclick="physicalRefNextReviewRegion()"' in HTML_SOURCE
    assert 'onclick="physicalRefPreviousReviewRegion()"' in HTML_SOURCE
    start_body = _extract_js_function_body(JS_SOURCE, "physicalRefStartSequenceProposals")
    assert "physicalRefUpdateActiveSample" not in start_body
    assert "physicalRefSave" not in start_body
    assert "/api/physical_reference_v2/sequence_proposals/start" in start_body
    accept_body = _extract_js_function_body(JS_SOURCE, "physicalRefAcceptProposalAsAnchor")
    assert "physicalRefUpdateActiveSample()" in accept_body
    assert "physicalRefSave" not in accept_body


def test_sequence_backend_has_no_tracker_identity_or_tim_target_inputs():
    signature = inspect.signature(UI2.generate_sequence_proposals)
    assert set(signature.parameters) == {
        "images",
        "times_s",
        "artifact_payload",
        "anonymous_detections_by_frame",
        "progress_callback",
    }
    source = inspect.getsource(UI2.generate_sequence_proposals)
    assert "tracker_id" not in source
    assert "selected_target" not in source
    assert "TIM-MARS" not in source
