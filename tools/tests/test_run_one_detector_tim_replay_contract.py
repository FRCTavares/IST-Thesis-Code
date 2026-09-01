"""Regression contract for the full detector/tracker/TIM replay runner."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT / "tools" / "experiments" / "run_one_detector_tim_replay.sh"
).read_text()

SUPERVISOR = (
    ROOT / "tools" / "lib" / "run_in_owned_process_group.py"
).read_text()

TRACK_SELECTION_HELPER = (
    ROOT / "tools" / "experiments" / "wait_for_track_selection.py"
).read_text()


def test_runner_does_not_use_strict_exit_shell_options():
    assert "set -e" not in RUNNER
    assert "set -eo" not in RUNNER
    assert "set -o pipefail" not in RUNNER


def test_runner_explicitly_propagates_setup_and_provenance_failures():
    assert 'if [[ ! -e "$BAG_PATH" ]]' in RUNNER
    assert 'if ! BAG_PATH="$(realpath "$BAG_PATH")"; then' in RUNNER
    assert 'if ! mkdir -p "$LOG_DIR" "$OUT_ROOT" "$REPORT_ROOT"; then' in RUNNER

    assert 'if ! source /opt/ros/jazzy/setup.bash; then' in RUNNER
    assert 'if ! source "$THESIS_ROOT/ros2_ws/install/setup.bash"; then' in RUNNER

    assert 'if [[ ! -x "${PROCESS_GROUP_SUPERVISOR[0]}" ]]' in RUNNER

    assert (
        'if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_METADATA_HELPER" ]]'
        in RUNNER
    )
    assert (
        'if [[ "$RUN_TIM_MARS" == "true" && ! -f "$TIM_MARS_MODEL_PATH" ]]'
        in RUNNER
    )
    assert 'if ! python3 "$TIM_METADATA_HELPER"' in RUNNER
    assert "failed to write TIM-MARS run provenance metadata" in RUNNER


def test_runner_cleanup_is_scoped_to_runner_owned_process_groups():
    assert "pkill -f" not in RUNNER

    assert 'DETECTOR_PID=$!' in RUNNER
    assert 'TRACKER_PID=$!' in RUNNER
    assert 'DASHBOARD_PID=$!' in RUNNER
    assert 'TIM_PID=$!' in RUNNER
    assert 'REC_PID=$!' in RUNNER
    assert 'PLAY_PID=$!' in RUNNER

    assert "PROCESS_GROUP_SUPERVISOR=(" in RUNNER
    assert "run_in_owned_process_group.py" in RUNNER

    assert (
        '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run '
        "thesis_bringup perception_pipeline_node"
    ) in RUNNER
    assert (
        '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run '
        "thesis_tracker tracker_node"
    ) in RUNNER
    assert (
        '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run '
        "thesis_bringup dashboard_bridge_node"
    ) in RUNNER
    assert (
        '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 run '
        "thesis_bringup target_memory_mars_node"
    ) in RUNNER
    assert '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 bag record' in RUNNER
    assert '"${PROCESS_GROUP_SUPERVISOR[@]}" ros2 bag play' in RUNNER

    assert "owned_process_alive" in RUNNER
    assert "stop_owned_process" in RUNNER
    assert 'kill -TERM "$pid"' in RUNNER
    assert 'kill -USR1 "$pid"' in RUNNER
    assert 'kill -INT "$REC_PID"' in RUNNER

    assert "os.fork()" in SUPERVISOR
    assert "os.setsid()" in SUPERVISOR
    assert "os.execvp(" in SUPERVISOR
    assert "os.killpg(" in SUPERVISOR
    assert "signal.SIGUSR1" in SUPERVISOR
    assert "signal.SIGKILL" in SUPERVISOR


def test_runner_uses_typed_persistent_tracks_resolution():
    assert "wait_for_track_selection.py" in RUNNER
    assert '--topic /tracks' in RUNNER
    assert '--largest' in RUNNER
    assert '--target-id "$target_id"' in RUNNER
    assert '--min-height 40.0' in RUNNER

    assert "ros2 topic echo /tracks --once" not in RUNNER
    assert "tracks_once.txt" not in RUNNER
    assert "select_largest_track_id.py" not in RUNNER

    assert "Track2DArray" in TRACK_SELECTION_HELPER
    assert "ReliabilityPolicy.BEST_EFFORT" in TRACK_SELECTION_HELPER
    assert "HistoryPolicy.KEEP_LAST" in TRACK_SELECTION_HELPER
    assert "depth=1" in TRACK_SELECTION_HELPER


def test_runner_uses_one_authoritative_target_command_path():
    assert "selecting target through dashboard authority API" in RUNNER
    assert "curl -sS --fail-with-body" in RUNNER
    assert "target authority API confirmed selection" in RUNNER
    assert "ros2 topic pub --once" not in RUNNER
    assert "--qos-reliability best_effort" not in RUNNER


def test_runner_forces_schema_v4_timing_topics():
    assert "-p publish_timing:=true" in RUNNER
    assert "-p publish_timing_topic:=true" in RUNNER
    assert "-p timing_target_topic:=/timing_target" in RUNNER
    assert "/timing_tracker" in RUNNER
    assert "/timing_target" in RUNNER


def test_runner_example_uses_canonical_yolov8s():
    assert "yolov8s largest bytetrack mars" in RUNNER

def test_runner_records_content_hashes_for_runtime_models():
    assert 'sha256sum "$HEF_PATH"' in RUNNER
    assert 'sha256sum "$TIM_MARS_MODEL_PATH"' in RUNNER
    assert (
        '--field "detector_hef_sha256=$DETECTOR_HEF_SHA256"'
        in RUNNER
    )
    assert (
        '--field "mars_model_sha256=$TIM_MARS_MODEL_SHA256"'
        in RUNNER
    )
