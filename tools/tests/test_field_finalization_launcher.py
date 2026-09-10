"""Issue #50/#74: launcher wiring for hardened retained-trial finalization."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (REPO_ROOT / "tools/start_live_stack.sh").read_text(encoding="utf-8")
SHUTDOWN = (REPO_ROOT / "tools/lib/live_shutdown.sh").read_text(encoding="utf-8")
DEFAULTS = (REPO_ROOT / "tools/lib/live_defaults.sh").read_text(encoding="utf-8")


def test_shell_scripts_parse():
    for name in ("tools/start_live_stack.sh", "tools/lib/live_shutdown.sh",
                 "tools/lib/live_defaults.sh"):
        subprocess.run(["bash", "-n", str(REPO_ROOT / name)], check=True)


def test_shutdown_library_is_sourced_and_wired():
    assert 'source "$THESIS_ROOT/tools/lib/live_shutdown.sh"' in LAUNCHER
    # stop_stack: publishers first, settle, recorders, then verify
    stop = LAUNCHER[LAUNCHER.index("stop_stack() {"):]
    stop = stop[:stop.index("\n}\n")]
    order = [
        stop.index("stop_app_nodes"),
        stop.index('sleep "${STOP_APP_SETTLE_S'),
        stop.index("finalize_recorders"),
        stop.index("archive_run_evidence_logs"),
        stop.index("verify_retained_evidence"),
    ]
    assert order == sorted(order), "stop_stack steps are out of order"
    # the old blind reverse-PID-array shutdown is gone
    assert 'tac "$PID_FILE"' not in stop


def test_recorder_finalize_grace_default_is_generous():
    assert 'RECORDER_FINALIZE_GRACE_S="${RECORDER_FINALIZE_GRACE_S:-10}"' in DEFAULTS
    # 1-second escalation is no longer the behaviour
    assert "sleep 1\n\n        tac" not in LAUNCHER


def test_finalize_recorders_escalates_then_kills_and_cleans_orphans():
    for token in (
        "did not finalize within",
        "escalating to SIGTERM",
        "sending SIGKILL",
        "tracked recorder process survived finalization",
        "RECORDER_FINALIZE_OUTCOME",
        "_live_collect_tree_identities",
    ):
        assert token in SHUTDOWN

    assert 'pkill -INT -f "ros2 bag record"' not in SHUTDOWN
    assert 'pkill -f "ros2 bag record"' not in SHUTDOWN
    assert 'pkill -f "rosbag2_recorder"' not in SHUTDOWN


def test_new_mavros_evidence_topics_are_recorded_once():
    assert LAUNCHER.count("/mavros/setpoint_raw/target_local") == 1
    assert LAUNCHER.count("/mavros/statustext/recv") == 1
    # they sit in the VIDEO_BAG_TOPICS MAVROS append, right after the
    # existing /mavros/setpoint_velocity/cmd_vel line
    anchor = LAUNCHER.index("/mavros/setpoint_velocity/cmd_vel")
    window = LAUNCHER[anchor:anchor + 1000]
    assert "/mavros/setpoint_raw/target_local" in window
    assert "/mavros/statustext/recv" in window
    assert "VIDEO_BAG_TOPICS" in LAUNCHER[anchor - 1500:anchor]


def test_verify_retained_evidence_is_best_effort_and_prints_incomplete():
    fn = LAUNCHER[LAUNCHER.index("verify_retained_evidence() {"):]
    fn = fn[:fn.index("\n}\n")]
    assert "EVIDENCE PACKAGE INCOMPLETE" in fn
    assert "verify_retained_bag.py" in fn
    assert "verify_evidence_package.py" in fn
    # it must never exit / kill
    assert "exit " not in fn
    assert "kill" not in fn
    assert "return 0" in fn


# J. recording refuses an existing non-empty evidence directory
def test_refuse_existing_bag_dir_guard_present():
    assert "refuse_existing_bag_dir() {" in LAUNCHER
    assert LAUNCHER.count("refuse_existing_bag_dir \"$VIDEO_BAG_OUT_DIR\"") == 1
    assert LAUNCHER.count("refuse_existing_bag_dir \"$DATASET_BAG_OUT_DIR\"") == 1
    assert LAUNCHER.count("refuse_existing_bag_dir \"$RAW_IMAGE_BAG_OUT_DIR\"") == 1
    assert "an existing non-empty evidence directory" in LAUNCHER


def test_refuse_existing_bag_dir_behaviour(tmp_path):
    # extract just the function and exercise it
    fn = LAUNCHER[LAUNCHER.index("refuse_existing_bag_dir() {"):]
    fn = fn[:fn.index("\n}\n") + 2]
    existing = tmp_path / "run__video"
    existing.mkdir()
    (existing / "run__video_0.mcap").write_bytes(b"prior evidence")
    empty = tmp_path / "fresh__video"
    empty.mkdir()
    missing = tmp_path / "absent__video"

    def call(target):
        return subprocess.run(
            ["bash", "-c", fn + f'\nrefuse_existing_bag_dir "{target}"'],
            capture_output=True, text=True,
        )

    r = call(existing)
    assert r.returncode != 0
    assert "refusing to record" in r.stdout
    assert (existing / "run__video_0.mcap").read_bytes() == b"prior evidence"

    assert call(empty).returncode == 0
    assert call(missing).returncode == 0


def test_no_recovery_bounds_leaked_as_cli_knobs_still_holds():
    for knob in ("--recovery-yaw-rate", "--recovery-timeout", "--recovery-budget"):
        assert knob not in LAUNCHER


def test_verifier_helpers_require_an_explicit_bag_dir(tmp_path):
    # M: none of the finalization helpers can auto-pick "the latest" bag/run.
    import sys

    for name, extra in (
        ("verify_retained_bag.py", []),
        ("verify_evidence_package.py", ["--run-id", "x"]),
        ("archive_pixhawk_dataflash.py",
         ["--run-id", "x", "--source-bin", str(tmp_path / "f.bin")]),
    ):
        module = REPO_ROOT / "tools/live" / name
        src = module.read_text(encoding="utf-8")
        assert 'add_argument("--bag-dir", required=True' in src, name
        for banned in ("getmtime", "st_mtime", "st_ctime"):
            assert banned not in src, f"{name} uses {banned}"
        # running without --bag-dir is an argparse error
        result = subprocess.run(
            [sys.executable, str(module), *extra],
            capture_output=True, text=True,
        )
        assert result.returncode == 2, name

def test_field_runbook_records_nominal_trial_end_before_stop_archival():
    runbook = (REPO_ROOT / "docs/flight/field_day_runbook.md").read_text(encoding="utf-8")
    trial_end = runbook.index("operator_event.py trial_end --run-id \"$RUN_ID\"")
    stop_instruction = runbook.index("Then, at the `live-stack>` prompt type `stop`")
    assert trial_end < stop_instruction


def test_stop_time_required_topics_follow_enabled_subsystems():
    assert "        /camera/dashboard /detections /tracks /timing" in LAUNCHER
    assert "        /timing /timing_target /control_ref/cmd_vel" not in LAUNCHER
    assert "req+=(/target_memory_mars /target_memory_mars/status /timing_target)" in LAUNCHER
    assert "req+=(/control_ref/cmd_vel /control_ref/diagnostics)" in LAUNCHER
