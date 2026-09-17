"""Contracts for the prospective Issue #27 held-out capture procedure."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "tools/experiments/record_p027_heldout_sequence.sh"
RUNBOOK = REPO_ROOT / "docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md"
EXECUTION_V2 = REPO_ROOT / "docs/flight/P027_HELDOUT_EXECUTION_PLAN_v2.md"
HANDOFF = REPO_ROOT / "docs/data/p027_heldout_handoff.md"
H01 = REPO_ROOT / "docs/flight/P027_H01_EXIT_REENTRY.md"
H02 = REPO_ROOT / "docs/flight/P027_H02_CROSSING.md"
H03 = REPO_ROOT / "docs/flight/P027_H03_OCCLUSION_DISTRACTOR.md"


def test_helper_is_source_only_and_supports_exact_heldout_set():
    text = HELPER.read_text(encoding="utf-8")

    for scenario in ("h01)", "h02)", "h03)"):
        assert scenario in text

    assert "--source-record-no-mavros" in text
    assert "--detector-model yolov8s" in text
    assert "--res vga" in text
    assert "bags/source/held_out/2026-09" in text


def test_helper_validates_freeze_and_refuses_non_pending_entries():
    text = HELPER.read_text(encoding="utf-8")

    assert "validate_tim_evaluation_split.py" in text
    assert "--verify-hashes" in text
    assert '[[ "$entry_status" != "reserved_pending_capture" ]]' in text


def test_helper_does_not_run_final_algorithm_evaluation():
    text = HELPER.read_text(encoding="utf-8")

    for forbidden in (
        "run_deterministic_tracker_replay.py",
        "run_deterministic_tim_replay.py",
        "run_p058_target_reid_replay.py",
        "evaluate_physical_target_bbox_v2.py",
        "--require-final-ready",
    ):
        assert forbidden not in text


def test_common_runbook_is_short_source_only_index():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "Capture is complete." in text
    assert "H01: `16-31-10`" in text
    assert "H02: `16-35-33`" in text
    assert "H03: `16-55-25`" in text
    assert "/camera/image_raw" in text
    assert "/detections" in text
    assert "Tracker, TIM-MARS, controller and MAVROS were OFF." in text
    assert "Do not recapture the sequences." in text
    assert "P027_HELDOUT_EXECUTION_PLAN_v2.md" in text
    assert "final_ready=3/3" in text

    assert len(text.splitlines()) < 110


def test_each_scenario_sheet_has_exact_helper_command_and_integrity_check():
    expected = {
        H01: ("h01", "h01_exit_reentry"),
        H02: ("h02", "h02_crossing"),
        H03: ("h03", "h03_occlusion_distractor"),
    }

    for path, (scenario, directory) in expected.items():
        text = path.read_text(encoding="utf-8")
        compact = " ".join(text.split())

        assert (
            f"tools/experiments/record_p027_heldout_sequence.sh {scenario}"
            in compact
        )
        assert f"bags/source/held_out/2026-09/{directory}" in text
        assert "ros2 bag info" in text
        assert 'SOURCE_ROOT="bags/source/held_out/2026-09/' in text
        assert 'find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d |' in text
        assert "sort |" in text
        assert "tail -n 1" in text
        assert 'test -n "$LATEST_SOURCE_BAG"' in text
        assert "-printf" not in text
        assert "Acceptance must not depend on tracker or TIM performance." in text


def test_h01_h02_h03_physical_scenarios_remain_distinct():
    h01 = " ".join(H01.read_text(encoding="utf-8").split())
    h02 = " ".join(H02.read_text(encoding="utf-8").split())
    h03 = " ".join(H03.read_text(encoding="utf-8").split())

    assert "physically absent for about 5–8 s" in h01
    assert "second close crossing" in h02
    assert "target remains physically present" in h03


def test_common_runbook_keeps_annotation_overlap_and_release_gate():
    runbook = RUNBOOK.read_text(encoding="utf-8")
    execution = EXECUTION_V2.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")

    assert "P027_HELDOUT_EXECUTION_PLAN_v2.md" in runbook
    assert "--verify-hashes --require-final-ready" in runbook
    assert "final_ready=3/3" in runbook

    assert "complete human physical-v2 annotation" in execution
    assert "record anonymous participant/outfit information" in execution
    assert "--require-final-ready" in execution
    assert "final_ready=3/3" in execution

    assert "overlap_record" in handoff
    assert "participant/clothing overlap" in handoff
    assert "physical-v2" in handoff


def test_archived_operator_docs_are_not_current_authority():
    archive = REPO_ROOT / "docs/archive/flight"

    assert (archive / "P023_FLIGHT_READINESS.md").is_file()
    assert (archive / "P023_RUN_PROVENANCE_TEMPLATE.md").is_file()
    assert (archive / "SOURCE_FIRST_FIELD_RECORDING_PLAN.md").is_file()

    active_documents = (
        (REPO_ROOT / "docs/README.md").read_text(encoding="utf-8")
        + (REPO_ROOT / "tools/README.md").read_text(encoding="utf-8")
        + (REPO_ROOT / "docs/design/tim_tooling_index.md").read_text(
            encoding="utf-8"
        )
    )

    assert "flight/SOURCE_FIRST_FIELD_RECORDING_PLAN.md" not in active_documents
    assert "flight/P023_FLIGHT_READINESS.md" not in active_documents
