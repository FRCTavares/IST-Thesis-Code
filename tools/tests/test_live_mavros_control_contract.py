from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = (ROOT / "tools/lib/live_cli.sh").read_text(encoding="utf-8")
USAGE = (ROOT / "tools/lib/live_usage.sh").read_text(encoding="utf-8")
LAUNCHER = (ROOT / "tools/start_live_stack.sh").read_text(encoding="utf-8")


def _case_block(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    finish = text.index(end, begin)
    return text[begin:finish]


def test_field_record_implies_managed_mavros_but_not_control_authority():
    block = _case_block(CLI, "--field-record)", "--record-raw)")
    assert "FIELD_MAVROS_RECORD=1" in block
    assert "RECORD_MAVROS=1" in block
    assert "CONTROL_MAVROS_BOOL" not in block


def test_control_mavros_requires_retained_field_mode():
    assert "--control-mavros is permitted only in retained field mode" in CLI
    assert "use --field-record --control-mavros for aircraft control" in CLI
    assert "--field-record requires MAVROS telemetry recording" in CLI
    assert "aircraft authority; requires --field-record" in USAGE


def test_retained_field_mode_rejects_preexisting_mavros():
    assert "pre-existing MAVROS process detected in retained field mode" in LAUNCHER
    assert "stop the existing MAVROS process and rerun" in LAUNCHER
    assert "pgrep -f" in LAUNCHER


def test_body_frame_is_verified_before_controller_mirroring_starts():
    field_network = LAUNCHER.index(
        'set_pi_network_mode.sh" pixhawk'
    )
    mavros_launch = LAUNCHER.index(
        "start_mavros_target_probe mavros"
    )
    frame_set = LAUNCHER.index(
        "ros2 param set /mavros/setpoint_velocity mav_frame"
    )
    frame_verify = LAUNCHER.index(
        "setpoint_velocity mav_frame verified: BODY_NED"
    )
    controller = LAUNCHER.index(
        "start_ros_bg control ros2 run thesis_bringup control_ref_node"
    )

    assert field_network < mavros_launch < frame_set < frame_verify < controller
    assert 'MAVROS_SETPOINT_VELOCITY_FRAME="BODY_NED"' in LAUNCHER


def test_legacy_normal_live_field_mavros_instance_is_removed():
    assert "start_ros_bg mavros_pixhawk " not in LAUNCHER
    assert (
        'echo "[field] starting MAVROS Pixhawk 6X Ethernet link"'
        not in LAUNCHER
    )

    # Source-record mode remains intentionally separate but shares the
    # same fail-closed FCU target resolver.
    assert "start_mavros_target_probe source_mavros_pixhawk" in LAUNCHER


def test_retained_bag_records_actual_stamped_mavros_command():
    assert "/mavros/setpoint_velocity/cmd_vel" in LAUNCHER
    assert "/mavros/setpoint_velocity/cmd_vel_unstamped" not in LAUNCHER

    for topic in (
        "/mavros/state",
        "/mavros/imu/data_raw",
        "/mavros/rc/in",
        "/mavros/battery",
        "/mavros/local_position/pose",
        "/mavros/local_position/velocity_local",
        "/mavros/setpoint_raw/target_local",
        "/mavros/statustext/recv",
    ):
        assert topic in LAUNCHER

    for redundant_topic in (
        "/mavros/extended_state",
        "/mavros/imu/data\n",
        "/mavros/imu/mag",
        "/mavros/imu/static_pressure",
        "/mavros/imu/temperature_imu",
        "/mavros/rc/out",
        "/mavros/global_position/global",
        "/mavros/global_position/rel_alt",
        "/mavros/global_position/local",
    ):
        assert redundant_topic not in LAUNCHER


def test_stream_rate_request_is_direct_bounded_and_fail_closed():
    start = LAUNCHER.index(
        'mavros_log ok "setpoint_velocity mav_frame verified: BODY_NED"'
    )
    end = LAUNCHER.index(
        'mavros_log info "checking /mavros/imu/data_raw, timeout 10s"'
    )
    stream_gate = LAUNCHER[start:end]

    assert "if ros2 service list" not in stream_gate
    assert "MAVROS_STREAM_SERVICE_READY" not in stream_gate
    assert "still waiting for stream-rate service" not in stream_gate
    assert (
        "timeout 15 ros2 service call \\\n"
        "        /mavros/set_stream_rate \\\n"
        "        mavros_msgs/srv/StreamRate"
        in stream_gate
    )
    assert (
        'mavros_log error "failed to request MAVROS stream rate within 15s"'
        in stream_gate
    )

    source_start = LAUNCHER.index(
        'echo "[source] requesting MAVLink streams"'
    )
    source_end = LAUNCHER.index(
        'echo "[source] starting MAVROS recorder: $SOURCE_MAVROS_BAG_OUT_DIR"'
    )
    source_gate = LAUNCHER[source_start:source_end]

    assert (
        "timeout 15 ros2 service call /mavros/set_stream_rate "
        "mavros_msgs/srv/StreamRate"
        in source_gate
    )


def test_field_path_fails_closed_on_missing_raw_imu():
    assert "/mavros/imu/data_raw missing in retained field mode" in LAUNCHER
    assert 'if [[ "${FIELD_MAVROS_RECORD:-0}" -eq 1 ]]; then' in LAUNCHER

    imu_gate = LAUNCHER[
        LAUNCHER.index(
            'mavros_log info "checking /mavros/imu/data_raw, timeout 10s"'
        ):
        LAUNCHER.index('mavros_log ok "MAVROS telemetry setup finished"')
    ]

    # Keep one DDS subscriber alive for the full readiness interval. Repeated
    # 2-second subscribers produced a real-hardware false negative despite
    # MAVROS already receiving RAW_IMU from the FCU.
    assert (
        "timeout 10 ros2 topic echo /mavros/imu/data_raw --once"
        in imu_gate
    )
    assert "timeout 2 ros2 topic echo /mavros/imu/data_raw --once" not in imu_gate
    assert "still waiting for raw IMU sample" not in imu_gate


def test_aircraft_authority_boundaries_remain_fail_closed():
    # Yaw recovery defaults OFF: the controller is launched with the
    # resolved CONTROL_YAW_RECOVERY_BOOL, whose default is "false".
    assert (
        "-p enable_yaw_recovery:=$CONTROL_ENABLE_YAW_RECOVERY" in LAUNCHER
    )
    assert (
        'CONTROL_ENABLE_YAW_RECOVERY="${CONTROL_YAW_RECOVERY_BOOL:-false}"'
        in LAUNCHER
    )
    assert 'CONTROL_YAW_RECOVERY_BOOL="false"' in (
        (ROOT / "tools/lib/live_defaults.sh").read_text(encoding="utf-8")
    )
    assert "/mavros/cmd/arming" not in LAUNCHER
    assert "/mavros/set_mode" not in LAUNCHER
    assert "CommandBool" not in LAUNCHER
    assert "SetMode" not in LAUNCHER


def test_yaw_recovery_candidate_is_deliberately_gated():
    # Candidate activation requires the acknowledgement AND the retained
    # field control-trial path; the recovery bounds are never CLI knobs.
    assert "--control-yaw-recovery)" in CLI
    assert "--acknowledge-yaw-recovery-candidate)" in CLI
    assert "add --acknowledge-yaw-recovery-candidate to proceed" in CLI
    assert "--control-yaw-recovery requires retained field recording" in CLI
    assert "--control-yaw-recovery is a closed-loop control-trial candidate" in CLI
    for knob in ("--recovery-yaw-rate", "--recovery-timeout", "--recovery-budget",
                 "--recovery-max-duration", "--recovery-max-integrated"):
        assert knob not in CLI
        assert knob not in USAGE
        assert knob not in LAUNCHER




def test_preexisting_mavros_check_observes_state_transition_not_first_sample():
    helper = LAUNCHER[
        LAUNCHER.index("mavros_state_reports_connected() {"):
        LAUNCHER.index("remove_tracked_pid_entry() {")
    ]

    assert 'timeout "$timeout_s" ros2 topic echo /mavros/state' in helper
    assert "ros2 topic echo /mavros/state --once" not in helper
    assert "grep -q '^connected: true$'" in helper
    assert 'rm -f "$tmp"' in helper

    mavros_runtime = LAUNCHER[
        LAUNCHER.index('if [[ "$RECORD_MAVROS" -eq 1 ]]; then'):
        LAUNCHER.index(
            'if [[ "${SOURCE_RECORD_MODE:-0}" -eq 1 ]]; then'
        )
    ]

    assert "if mavros_state_reports_connected 5; then" in mavros_runtime
    assert (
        "timeout 3 ros2 topic echo /mavros/state --once"
        not in mavros_runtime
    )

def test_mavros_target_system_is_resolved_fail_closed():
    assert 'MAVROS_TGT_SYSTEM_CANDIDATES="${MAVROS_TGT_SYSTEM_CANDIDATES:-10 9}"' in LAUNCHER
    assert 'if [[ -n "${MAVROS_TGT_SYSTEM:-}" ]]; then' in LAUNCHER
    assert 'MAVROS_TARGET_SELECTION_MODE="explicit"' in LAUNCHER
    assert 'MAVROS_TARGET_SELECTION_MODE="auto"' in LAUNCHER
    assert "start_mavros_target_probe mavros" in LAUNCHER
    assert "start_mavros_target_probe source_mavros_pixhawk" in LAUNCHER
    assert "no approved MAVROS FCU target connected" in LAUNCHER
    assert "stop_mavros_probe_attempt" in LAUNCHER
    assert "tgt_system:=9" not in LAUNCHER


def test_resolved_mavros_target_is_recorded_in_metadata():
    assert "mavros_target_selection_mode=" in LAUNCHER
    assert "mavros_target_system_requested=" in LAUNCHER
    assert "mavros_target_system_candidates=" in LAUNCHER
    assert "mavros_target_system_resolved=" in LAUNCHER
    assert "mavros_target_component_resolved=" in LAUNCHER


def test_target_probe_does_not_gain_aircraft_authority():
    probe = LAUNCHER[
        LAUNCHER.index("start_mavros_target_probe() {"):
        LAUNCHER.index("# Refuse to record a retained trial", LAUNCHER.index("start_mavros_target_probe() {"))
    ]
    assert "/mavros/cmd/arming" not in probe
    assert "/mavros/set_mode" not in probe
    assert "/mavros/setpoint_velocity/cmd_vel" not in probe
    assert "CommandBool" not in probe
    assert "SetMode" not in probe






def test_mavros_probe_readiness_uses_persistent_heartbeat_not_short_dds_echoes():
    probe = LAUNCHER[
        LAUNCHER.index("start_mavros_target_probe() {"):
        LAUNCHER.index(
            "# Refuse to record a retained trial",
            LAUNCHER.index("start_mavros_target_probe() {"),
        )
    ]

    assert 'MAVROS_TARGET_PROBE_TIMEOUT_S="${MAVROS_TARGET_PROBE_TIMEOUT_S:-15}"' in probe
    assert "CON: Got HEARTBEAT, connected. FCU:" in probe
    assert 'grep -Fq' in probe
    assert "ros2 topic echo /mavros/state" not in probe
    assert "MAVROS_TARGET_PROBE_ATTEMPTS" not in probe


def test_mavros_probe_cleanup_snapshots_and_verifies_owned_descendants():
    cleanup = LAUNCHER[
        LAUNCHER.index("stop_mavros_probe_attempt() {"):
        LAUNCHER.index("start_mavros_target_probe() {")
    ]

    assert '_live_collect_tree_identities "$pid"' in cleanup
    assert 'tree_identities=("${_LIVE_TREE_IDENTITIES[@]}")' in cleanup
    assert '_live_identity_alive "$identity"' in cleanup
    assert 'owned MAVROS probe process' in cleanup
    assert 'kill -s TERM "$owned_pid"' in cleanup
    assert 'kill -s KILL "$owned_pid"' in cleanup
    assert cleanup.index('_live_collect_tree_identities "$pid"') < cleanup.index(
        'kill_tree "$pid" INT'
    )

def test_failed_mavros_probe_cleanup_must_succeed_before_next_candidate():
    probe = LAUNCHER[
        LAUNCHER.index("start_mavros_target_probe() {"):
        LAUNCHER.index(
            "# Refuse to record a retained trial",
            LAUNCHER.index("start_mavros_target_probe() {"),
        )
    ]

    guard = 'if ! stop_mavros_probe_attempt "$process_name"; then'
    error = (
        "refusing to probe another MAVROS target after cleanup failure"
    )

    assert guard in probe
    assert error in probe

    guarded = probe[probe.index(guard):]
    assert guarded.index(error) < guarded.index("return 1")
    assert guarded.index("return 1") < guarded.index("sleep 1")


def test_probe_pid_tracking_replace_failure_is_fail_closed_and_cleans_tmp():
    cleanup = LAUNCHER[
        LAUNCHER.index("remove_tracked_pid_entry() {"):
        LAUNCHER.index("stop_mavros_probe_attempt() {")
    ]

    assert 'if ! mv "$tmp" "$PID_FILE"; then' in cleanup
    assert 'rm -f "$tmp"' in cleanup
    assert "failed to replace PID tracking file" in cleanup
    assert "return 1" in cleanup

def test_failed_mavros_probe_is_removed_from_shutdown_pid_tracking():
    cleanup = LAUNCHER[
        LAUNCHER.index("remove_tracked_pid_entry() {"):
        LAUNCHER.index("start_mavros_target_probe() {")
    ]

    assert 'awk -v pid="$pid" -v name="$process_name"' in cleanup
    assert 'mv "$tmp" "$PID_FILE"' in cleanup

    # Initial shutdown is tree-wide while parent/child relationships are
    # intact; escalation is then restricted to the exact snapshotted
    # PID/start-time identities owned by this probe.
    assert 'kill_tree "$pid" INT' in cleanup
    assert '_live_collect_tree_identities "$pid"' in cleanup
    assert '_live_identity_alive "$identity"' in cleanup
    assert 'kill -s TERM "$owned_pid"' in cleanup
    assert 'kill -s KILL "$owned_pid"' in cleanup

    assert 'remove_tracked_pid_entry "$pid" "$process_name"' in cleanup
    assert "failed to stop owned MAVROS probe process" in cleanup
    assert "unset 'PROC_PIDS[$process_name]'" in cleanup

def test_retained_command_topics_follow_enabled_control_authority():
    start = LAUNCHER.index("VIDEO_BAG_TOPICS=(")
    end = LAUNCHER.index('if ! refuse_existing_bag_dir', start)
    topics = LAUNCHER[start:end]

    controller_guard = (
        'if [[ "${ENABLE_CONTROL:-0}" -eq 1 ]]; then\n'
        '        VIDEO_BAG_TOPICS+=(\n'
        '            /control_ref/cmd_vel\n'
        '            /control_ref/diagnostics'
    )
    assert controller_guard in topics

    mavros_control_guard = (
        'if [[ "${ENABLE_CONTROL:-0}" -eq 1 && '
        '"${CONTROL_MAVROS_BOOL:-false}" == "true" ]]; then\n'
        '            VIDEO_BAG_TOPICS+=(\n'
        '                /mavros/setpoint_velocity/cmd_vel'
    )
    assert mavros_control_guard in topics
