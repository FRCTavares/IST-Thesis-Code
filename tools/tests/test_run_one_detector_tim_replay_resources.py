from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_one_detector_tim_replay.sh"
)


def text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_resource_sampling_is_disabled_by_default():
    content = text()

    assert (
        'RESOURCE_SAMPLING_ENABLED='
        '"${RESOURCE_SAMPLING_ENABLED:-false}"'
        in content
    )


def test_existing_resource_collectors_are_reused():
    content = text()

    assert (
        "tools/experiments/sample_process_groups.py"
        in content
    )
    assert (
        "tools/experiments/sample_p044_hardware_health.py"
        in content
    )


def test_owned_child_pgid_is_resolved_from_supervisor():
    content = text()

    assert "resolve_owned_pgid() {" in content
    assert (
        '/proc/$supervisor_pid/task/'
        '$supervisor_pid/children'
        in content
    )
    assert 'if [[ "$pgid" == "$child_pid" ]]' in content


def test_architecture_resource_groups_are_explicit():
    content = text()

    assert '--group "detector=$DETECTOR_PGID"' in content
    assert '--group "tracker=$TRACKER_PGID"' in content
    assert (
        'RESOURCE_GROUP_ARGS+='
        '(--group "tim=$TIM_PGID")'
        in content
    )


def test_non_architecture_helpers_are_not_resource_groups():
    content = text()

    start = content.index(
        'echo "[info] starting process-group resource sampler"'
    )
    end = content.index(
        'echo "[info] nodes before playback"',
        start,
    )
    section = content[start:end]

    assert '--group "dashboard=' not in section
    assert '--group "recorder=' not in section
    assert '--group "playback=' not in section


def test_samplers_are_cleaned_up():
    content = text()

    start = content.index("cleanup() {")
    end = content.index("trap cleanup EXIT", start)
    cleanup = content[start:end]

    assert (
        'stop_owned_process "resource sampler"'
        in cleanup
    )
    assert (
        'stop_owned_process "hardware health sampler"'
        in cleanup
    )


def test_resource_sampling_stops_before_recorder_shutdown():
    content = text()

    playback_wait = content.index('wait "$PLAY_PID"')
    health_stop = content.index(
        'stop_owned_process "hardware health sampler"',
        playback_wait,
    )
    resource_stop = content.index(
        'stop_owned_process "resource sampler"',
        playback_wait,
    )
    recorder_stop = content.index(
        'echo "[info] stopping recorder"',
        playback_wait,
    )

    assert playback_wait < health_stop < recorder_stop
    assert playback_wait < resource_stop < recorder_stop


def test_tim_off_skips_selected_target_authority_bootstrap():
    content = text()

    wait_marker = 'echo "[info] waiting for playback to finish"'
    wait_index = content.index(wait_marker)

    skip_marker = (
        'echo "[info] TIM-MARS disabled; skipping '
        'selected-target authority bootstrap"'
    )
    skip_index = content.index(skip_marker)

    selection_index = content.index(
        'if ! select_target "$TARGET_ID"; then'
    )

    gate_index = content.rfind(
        'if [[ "$RUN_TIM_MARS" == "true" ]]; then',
        0,
        selection_index,
    )

    assert gate_index >= 0
    assert gate_index < selection_index < skip_index < wait_index
