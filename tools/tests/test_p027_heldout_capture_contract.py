"""Contract tests for the Issue #27 prospective held-out capture helper."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "tools/experiments/record_p027_heldout_sequence.sh"
RUNBOOK = REPO_ROOT / "docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md"


def test_helper_is_source_only_and_has_all_three_scenarios():
    text = HELPER.read_text(encoding="utf-8")

    assert "h01)" in text
    assert "h02)" in text
    assert "h03)" in text

    assert "--source-record-no-mavros" in text
    assert "--detector-model yolov8s" in text
    assert "--res vga" in text

    assert "bags/source/held_out/2026-09" in text


def test_helper_validates_prospective_freeze_before_capture():
    text = HELPER.read_text(encoding="utf-8")

    assert "validate_tim_evaluation_split.py" in text
    assert "--verify-hashes" in text
    assert '[[ "$entry_status" != "reserved_pending_capture" ]]' in text


def test_helper_does_not_launch_tracker_tim_control_or_final_evaluation():
    text = HELPER.read_text(encoding="utf-8")

    forbidden = (
        "run_deterministic_tracker_replay.py",
        "run_deterministic_tim_replay.py",
        "run_p058_target_reid_replay.py",
        "evaluate_physical_target_bbox_v2.py",
        "--require-final-ready",
    )

    for value in forbidden:
        assert value not in text


def test_helper_preserves_raw_and_common_detector_evidence():
    text = HELPER.read_text(encoding="utf-8")

    assert "/camera/image_raw + /detections" in text
    assert "image_raw_detections" in text
    assert "Do not rename or delete this retained source." in text


def test_runbook_separates_physical_scenario_from_algorithm_outcome():
    text = RUNBOOK.read_text(encoding="utf-8")
    compact = " ".join(text.split())

    assert "Do not inspect tracker output" in compact
    assert "physical scenario and recording integrity only" in compact
    assert (
        "must not be repeated because an algorithm later performed badly"
        in compact
    )


def test_runbook_freezes_vga_source_and_common_detector_fanout():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "`640x480`" in text
    assert "detector inference geometry: `640x640`" in text
    assert "`/camera/image_raw` and `/detections`" in text
    assert "same frozen detector stream" in text


def test_runbook_requires_identity_outfit_overlap_and_physical_v2():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "participant and outfit codes" in text
    assert "development/legacy people/clothing overlap" in text
    assert "heldout_h01_exit_reentry.json" in text
    assert "heldout_h02_crossing.json" in text
    assert "heldout_h03_occlusion_distractor.json" in text
    assert "phys_dNNN" in text


def test_runbook_keeps_final_gate_fail_closed_until_all_three_ready():
    text = RUNBOOK.read_text(encoding="utf-8")
    compact = " ".join(text.split())

    assert "--require-final-ready" in text
    assert "Only after the gate passes" in compact
    assert "new prospective split is required" in compact
