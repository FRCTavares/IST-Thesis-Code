"""Contract tests for optional raw capture alongside the normal live stack."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "tools/lib/live_cli.sh"
DEFAULTS = REPO_ROOT / "tools/lib/live_defaults.sh"
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
USAGE = REPO_ROOT / "tools/lib/live_usage.sh"


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
    assert "--record --record-raw --tag NON_HELD_OUT_DIAGNOSTIC" in usage
    assert "--record-raw             Diagnostic paired raw" in usage
    assert "separate synchronized /camera/image_raw" in usage



def test_field_raw_recorder_starts_before_expensive_provenance():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    main_metadata = launcher.index(
        'write_video_bag_metadata "$VIDEO_BAG_OUT_DIR/flight_metadata.txt"'
    )
    raw_start = launcher.index(
        "start_ros_bg raw_image_bag ros2 bag record"
    )
    deferred_main_provenance = launcher.index(
        'write_live_run_provenance video "$VIDEO_BAG_OUT_DIR/run_metadata.json"',
        raw_start,
    )
    raw_provenance = launcher.index(
        'write_live_run_provenance raw_image "$RAW_IMAGE_BAG_OUT_DIR/run_metadata.json"',
        raw_start,
    )

    # In paired raw mode, the early provenance call is guarded out.
    window = launcher[main_metadata:raw_start]
    assert '[[ "${FIELD_RAW_IMAGE_RECORD:-0}" -ne 1 ]]' in window

    # Both expensive provenance writes occur only after raw recording starts.
    assert raw_start < deferred_main_provenance < raw_provenance


def test_field_raw_recorder_has_high_throughput_storage_contract():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    start = launcher.index(
        'if [[ "${FIELD_RAW_IMAGE_RECORD:-0}" -eq 1 ]]; then'
    )
    end = launcher.index(
        'if [[ "${SOURCE_RECORD_MODE:-0}" -eq 1 ]]; then',
        start,
    )
    block = launcher[start:end]

    assert "RAW_IMAGE_ROSBAG_EXTRA_ARGS=(" in block
    assert "--storage-preset-profile fastwrite" in block
    assert "--max-cache-size 536870912" in block
    assert '"${RAW_IMAGE_ROSBAG_EXTRA_ARGS[@]}"' in block
    assert "sleep 3" not in block


def test_main_retained_recorder_has_expanded_cache():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "VIDEO_ROSBAG_EXTRA_ARGS=(" in launcher
    assert "--max-cache-size 268435456" in launcher
    assert '"${VIDEO_ROSBAG_EXTRA_ARGS[@]}"' in launcher


def test_launcher_does_not_claim_unsupported_fastrtps_shm_override():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    # The installed Jazzy rmw_fastrtps implementation does not expose the
    # historical RMW_FASTRTPS_USE_SHM switch. Do not use it as an evidence
    # transport control or claim that it enables/disables FastDDS SHM.
    assert "LIVE_RECORD_FASTDDS_SHM" not in launcher
    assert "RMW_FASTRTPS_USE_SHM" not in launcher


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
