"""Contract tests for optional raw capture alongside the normal live stack."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "tools/lib/live_cli.sh"
DEFAULTS = REPO_ROOT / "tools/lib/live_defaults.sh"
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
USAGE = REPO_ROOT / "tools/lib/live_usage.sh"
CAMERA_HELPER = REPO_ROOT / "tools/lib/live_camera.sh"


def _case_block(text: str, option: str, next_option: str) -> str:
    start = text.index(f"        {option})")
    end = text.index(f"        {next_option})", start)
    return text[start:end]


def test_record_raw_is_explicit_and_field_record_does_not_reset_it():
    cli = CLI.read_text(encoding="utf-8")

    raw_block = _case_block(cli, "--record-raw", "--no-record-raw")
    field_block = _case_block(cli, "--field-record", "--record-raw")

    assert "FIELD_RAW_IMAGE_RECORD=1" in raw_block
    assert "FIELD_RAW_IMAGE_RECORD" not in field_block


def test_field_record_reuses_canonical_mavros_owner_without_network_transition():
    cli = CLI.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    defaults = DEFAULTS.read_text(encoding="utf-8")

    field_block = _case_block(cli, "--field-record", "--record-raw")

    assert "ENABLE_ROSBAG=1" in field_block
    assert "RECORD_MAVROS=1" in field_block
    assert "FIELD_MAVROS_RECORD" not in field_block
    assert "FIELD_MAVROS_RECORD" not in defaults
    assert "FIELD_MAVROS_RECORD" not in launcher
    assert 'start_ros_bg mavros_pixhawk' not in launcher
    assert '[field] enforcing AERONEXT/Pixhawk network mode' not in launcher


def test_canonical_mavros_evidence_records_real_control_and_battery_topics():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "/mavros/battery" in launcher
    assert "/mavros/extended_state" in launcher
    assert "/mavros/rc/in" in launcher
    assert "/mavros/rc/out" in launcher
    assert "/mavros/setpoint_velocity/cmd_vel" in launcher
    assert "/mavros/setpoint_velocity/cmd_vel_unstamped" not in launcher


def test_current_pixhawk_mavros_target_is_10_1():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert 'MAVROS_TGT_SYSTEM="${MAVROS_TGT_SYSTEM:-10}"' in launcher
    assert 'MAVROS_TGT_COMPONENT="${MAVROS_TGT_COMPONENT:-1}"' in launcher
    assert "tgt_system:=9 tgt_component:=1" not in launcher
    assert "tgt_system:=10 tgt_component:=1" in launcher


def test_live_cleanup_does_not_use_broad_pkill_and_excludes_ancestors():
    helper = CAMERA_HELPER.read_text(encoding="utf-8")

    assert 'pkill -f "$STACK_PROC_PATTERN"' not in helper
    assert 'pgrep -af "$STACK_PROC_PATTERN"' not in helper
    assert 'awk' not in helper[
        helper.index("list_existing_stack_processes()"):
        helper.index("signal_existing_stack_processes()")
    ]
    assert "stack_ancestor_pids()" in helper
    assert "list_existing_stack_processes()" in helper
    assert "signal_existing_stack_processes()" in helper
    assert 'pgrep -f "$STACK_PROC_PATTERN"' in helper
    assert 'excluded_pids["$pid"]=1' in helper
    assert '${excluded_pids[$pid]:-}' in helper
    assert 'ps -p "$pid" -o pid=,args=' in helper


def test_canonical_mavros_imu_probe_uses_one_qos_explicit_subscriber():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "timeout 10s ros2 topic echo" in launcher
    assert "/mavros/imu/data_raw" in launcher
    assert "--qos-profile sensor_data" in launcher
    assert "--qos-reliability best_effort" in launcher
    assert "--qos-durability volatile" in launcher
    assert (
        "timeout 2 ros2 topic echo /mavros/imu/data_raw --once"
        not in launcher
    )


def test_raw_recording_requires_normal_live_recording():
    cli = CLI.read_text(encoding="utf-8")

    assert '[[ "$FIELD_RAW_IMAGE_RECORD" -eq 1 && "$ENABLE_ROSBAG" -ne 1 ]]' in cli
    assert "--record --record-raw" in cli


def test_raw_bag_is_separate_paired_and_uses_camera_topic():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert 'RAW_IMAGE_BAG_OUT_DIR="${VIDEO_BAG_OUT_DIR}__image_raw"' in launcher
    assert "--topics /camera/image_raw" in launcher
    assert 'echo "raw_image_bag_out_dir=$RAW_IMAGE_BAG_OUT_DIR"' in launcher
    assert 'echo "paired_video_bag=$VIDEO_BAG_OUT_DIR"' in launcher
    assert "raw_image_metadata.txt" in launcher


def test_raw_mode_has_field_storage_gate_and_operator_documentation():
    defaults = DEFAULTS.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")

    assert 'RAW_RECORDING_MIN_FREE_GIB="${RAW_RECORDING_MIN_FREE_GIB:-40}"' in defaults
    assert '"$RAW_RECORDING_MIN_FREE_GIB" || exit 1' in launcher
    assert "--field-record --record-raw --tag flight1" in usage
    assert "separate synchronized /camera/image_raw" in usage


def test_source_record_no_mavros_records_issue64_evidence_without_mavros():
    cli = CLI.read_text(encoding="utf-8")

    legacy_block = _case_block(
        cli,
        "--source-record",
        "--source-record-no-mavros",
    )
    block = _case_block(cli, "--source-record-no-mavros", "--tag")

    assert "SOURCE_DETECTIONS_RECORD=0" in legacy_block

    assert "SOURCE_RECORD_MODE=1" in block
    assert "SOURCE_RAW_IMAGE_RECORD=1" in block
    assert "SOURCE_MAVROS_RECORD=0" in block
    assert "SOURCE_DETECTIONS_RECORD=1" in block
    assert "ENABLE_ROSBAG=0" in block
    assert "ENABLE_DATASET_BAG=0" in block
    assert "ENABLE_CONTROL=0" in block
    assert "ENABLE_DASHBOARD_BRIDGE=0" in block
    assert "ENABLE_WEB_VIDEO=0" in block
    assert "ENABLE_TRACKER=0" in block
    assert 'TARGET_MEMORY_MODE="off"' in block


def test_source_raw_recording_has_storage_gate_camera_qos_and_issue64_topics():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert '"${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1' in launcher
    assert (
        '"${SOURCE_RECORD_ROOT:-$THESIS_ROOT/bags/source_video}"'
        in launcher
    )
    assert '"$RAW_RECORDING_MIN_FREE_GIB" || exit 1' in launcher
    assert 'SOURCE_QOS_OVERRIDE_FILE="/etc/thesis/live_record_qos_overrides.yaml"' in launcher
    assert '--qos-profile-overrides-path "$SOURCE_QOS_OVERRIDE_FILE"' in launcher
    assert 'SOURCE_RECORD_TOPICS=(' in launcher
    assert '/camera/image_raw' in launcher
    assert 'SOURCE_RECORD_TOPICS+=(' in launcher
    assert '/detections' in launcher
    assert 'SOURCE_RAW_BAG_SUFFIX="image_raw_detections"' in launcher
    assert '"${SOURCE_RECORD_TOPICS[@]}"' in launcher
    assert '--storage-preset-profile fastwrite' in launcher
    assert '--max-cache-size 536870912' in launcher
    assert '"${SOURCE_ROSBAG_EXTRA_ARGS[@]}"' in launcher


def test_source_record_no_mavros_is_documented():
    usage = USAGE.read_text(encoding="utf-8")

    assert "--source-record-no-mavros" in usage
    assert "/camera/image_raw + /detections" in usage
    assert "Issue #64 tracker/TIM replay" in usage
    assert "no MAVROS or network-mode change" in usage
    assert "SOURCE_RECORD_ROOT" in usage


def test_source_record_root_can_be_overridden_for_ram_capture():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert (
        'SOURCE_ROOT="${SOURCE_RECORD_ROOT:-$THESIS_ROOT/bags/source_video}"'
        in launcher
    )
    assert 'echo "[source] source evidence root: $SOURCE_ROOT"' in launcher
