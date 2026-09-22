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



def test_background_processes_reset_sigint_sigquit_before_exec():
    start = LAUNCHER.index("start_ros_bg() {")
    end = LAUNCHER.index("\n}\n", start)
    helper = LAUNCHER[start:end]

    # Bash asynchronous jobs inherit SIGINT/SIGQUIT ignored. Reset the actual
    # process dispositions to SIG_DFL before replacing the wrapper with exec.
    assert "signal.signal(signal.SIGINT, signal.SIG_DFL)" in helper
    assert "signal.signal(signal.SIGQUIT, signal.SIG_DFL)" in helper
    assert "os.execvp(sys.argv[1], sys.argv[1:])" in helper
    assert 'local pid=$!' in helper

    # Comments may mention the retired trap implementation; executable lines
    # must not still use it.
    executable = "\n".join(
        line for line in helper.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "trap - INT QUIT" not in executable


def test_start_ros_bg_child_really_honors_sigint(tmp_path):
    start = LAUNCHER.index("start_ros_bg() {")
    end = LAUNCHER.index("\n}\n", start) + len("\n}\n")
    helper = LAUNCHER[start:end]

    script = f"""
set +e
declare -A PROC_PIDS=()
RUN_DIR="$PWD"
PID_FILE="$PWD/pids.txt"
log_start() {{ :; }}

{helper}

start_ros_bg signal_probe python3 -c 'import time; time.sleep(60)'
pid="${{PROC_PIDS[signal_probe]}}"

sleep 0.5

if ! kill -0 "$pid" 2>/dev/null; then
    echo "FAIL: child exited before SIGINT"
    exit 2
fi

kill -INT "$pid"

exited=0
for _ in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then
        exited=1
        break
    fi

    state="$(ps -o stat= -p "$pid" 2>/dev/null | tr -d '[:space:]')"
    case "$state" in
        Z*|X*)
            exited=1
            break
            ;;
    esac

    sleep 0.1
done

if [ "$exited" -ne 1 ]; then
    echo "FAIL: start_ros_bg child ignored SIGINT"
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    exit 3
fi

wait "$pid" 2>/dev/null
rc=$?

echo "PASS: start_ros_bg child exited after SIGINT rc=$rc"
exit 0
"""

    completed = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, (
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    assert "PASS: start_ros_bg child exited after SIGINT" in completed.stdout

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


def test_new_mavros_evidence_topics_are_recorded_in_each_mavros_bag():
    # One occurrence belongs to VIDEO_BAG_TOPICS and one to the separate
    # source-plus-MAVROS recorder. Each bag retains the FCU command echo and
    # status text needed to interpret its own telemetry.
    assert LAUNCHER.count("/mavros/setpoint_raw/target_local") == 2
    assert LAUNCHER.count("/mavros/statustext/recv") == 2

    anchor = LAUNCHER.index("/mavros/setpoint_velocity/cmd_vel")
    window = LAUNCHER[anchor:anchor + 1000]
    assert "/mavros/setpoint_raw/target_local" in window
    assert "/mavros/statustext/recv" in window
    assert "VIDEO_BAG_TOPICS" in LAUNCHER[anchor - 1500:anchor]

    source = LAUNCHER[LAUNCHER.index('if [[ "${SOURCE_RECORD_MODE:-0}" -eq 1 ]]; then'):]
    assert source.count("/mavros/setpoint_raw/target_local") == 1
    assert source.count("/mavros/statustext/recv") == 1


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

def test_canonical_field_sheet_records_nominal_trial_end_before_stop_archival():
    sheet = (REPO_ROOT / "docs/flight/README.md").read_text(encoding="utf-8")
    section = sheet[sheet.index("## 15. Normal stop and package checks"):]
    trial_end = section.index('operator_event.py trial_end --run-id "$RUN_ID"')
    stop_command = section.index("Type `stop` in A", trial_end)
    verify_step = section.index("verify_evidence_package.py --bag-dir", stop_command)
    assert trial_end < stop_command < verify_step
    backup = (REPO_ROOT / "docs/flight/field_day_runbook.md").read_text(encoding="utf-8")
    assert "[README.md](README.md)" in backup


def test_stop_time_required_topics_follow_enabled_subsystems():
    assert "local -a req=(/detections /tracks /timing)" in LAUNCHER
    assert "req+=(/camera/dashboard)" in LAUNCHER
    assert 'if [[ "${FLIGHT_VISUAL_RECORD:-0}" -ne 1 ]]; then' in LAUNCHER
    assert "        /timing /timing_target /control_ref/cmd_vel" not in LAUNCHER
    assert "req+=(/target_memory_mars /target_memory_mars/status /timing_target)" in LAUNCHER
    assert "req+=(/control_ref/cmd_vel /control_ref/diagnostics)" in LAUNCHER



def test_control_log_archival_tracks_controller_enablement():
    from pathlib import Path

    launcher = (
        Path(__file__).resolve().parents[2] / "tools" / "start_live_stack.sh"
    ).read_text(encoding="utf-8")

    start = launcher.index("archive_run_evidence_logs()")
    end = launcher.index("verify_retained_evidence()", start)
    block = launcher[start:end]

    assert 'if [[ "${ENABLE_CONTROL:-0}" -eq 1 ]]; then' in block
    assert "archive_args+=(--log control.log)" in block
    assert "archive_args+=(--optional-file control.log)" in block


def test_retained_recorder_logs_and_transport_report_are_wired():
    archive = LAUNCHER[
        LAUNCHER.index("archive_run_evidence_logs()"):
        LAUNCHER.index("verify_retained_evidence()")
    ]
    verify = LAUNCHER[
        LAUNCHER.index("verify_retained_evidence()"):
        LAUNCHER.index("STOP_DONE=0")
    ]
    assert "--log rosbag.log" in archive
    assert "--log raw_image_bag.log" in archive
    assert "verify_recorder_transport.py" in verify
    assert "--raw-bag-dir" in verify
    assert "--expect-raw-bag" in verify
    assert "--require-topic /camera/image_raw --require-nonzero /camera/image_raw" in verify


def test_integrated_camera_receives_opt_in_sensor_rate_controls():
    start = LAUNCHER.index('start_ros_bg perception_camera env')
    end = LAUNCHER.index('    sleep 2', start)
    block = LAUNCHER[start:end]
    for parameter in (
        'apply_sensor_rate_controls:=$CAMERA_APPLY_RATE_CONTROLS_BOOL',
        'sensor_max_fps:=$CAMERA_SENSOR_MAX_FPS',
        'sensor_ae_exposure_upper:=$CAMERA_SENSOR_AE_UPPER',
        'sensor_ae_exposure_max:=$CAMERA_SENSOR_AE_MAX',
        'sensor_exposure_mode:=$CAMERA_SENSOR_EXPOSURE_MODE',
        'sensor_manual_exposure:=$CAMERA_SENSOR_MANUAL_EXPOSURE',
    ):
        assert parameter in block
