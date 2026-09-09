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
        "start_ros_bg mavros ros2 launch mavros apm.launch"
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

    # Source-record mode remains intentionally separate.
    assert "start_ros_bg source_mavros_pixhawk " in LAUNCHER


def test_retained_bag_records_actual_stamped_mavros_command():
    assert "/mavros/setpoint_velocity/cmd_vel" in LAUNCHER
    assert "/mavros/setpoint_velocity/cmd_vel_unstamped" not in LAUNCHER

    for topic in (
        "/mavros/state",
        "/mavros/extended_state",
        "/mavros/rc/in",
        "/mavros/rc/out",
        "/mavros/battery",
        "/mavros/global_position/global",
    ):
        assert topic in LAUNCHER


def test_field_path_fails_closed_on_missing_raw_imu():
    assert "/mavros/imu/data_raw missing in retained field mode" in LAUNCHER
    assert 'if [[ "${FIELD_MAVROS_RECORD:-0}" -eq 1 ]]; then' in LAUNCHER


def test_aircraft_authority_boundaries_remain_fail_closed():
    assert "-p enable_yaw_recovery:=false" in LAUNCHER
    assert "/mavros/cmd/arming" not in LAUNCHER
    assert "/mavros/set_mode" not in LAUNCHER
    assert "CommandBool" not in LAUNCHER
    assert "SetMode" not in LAUNCHER
