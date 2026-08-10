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
