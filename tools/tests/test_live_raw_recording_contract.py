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
    assert "--field-record --record-raw --tag flight1" in usage
    assert "separate synchronized /camera/image_raw" in usage


def test_source_record_no_mavros_is_raw_only_and_never_requests_mavros():
    cli = CLI.read_text(encoding="utf-8")

    block = _case_block(cli, "--source-record-no-mavros", "--tag")

    assert "SOURCE_RECORD_MODE=1" in block
    assert "SOURCE_RAW_IMAGE_RECORD=1" in block
    assert "SOURCE_MAVROS_RECORD=0" in block
    assert "ENABLE_ROSBAG=0" in block
    assert "ENABLE_DATASET_BAG=0" in block
    assert "ENABLE_CONTROL=0" in block
    assert "ENABLE_DASHBOARD_BRIDGE=0" in block
    assert "ENABLE_WEB_VIDEO=0" in block
    assert "ENABLE_TRACKER=0" in block
    assert 'TARGET_MEMORY_MODE="off"' in block


def test_source_raw_recording_has_storage_gate_and_camera_qos_override():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert '"${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1' in launcher
    assert '"$THESIS_ROOT/bags/source_video"' in launcher
    assert '"$RAW_RECORDING_MIN_FREE_GIB" || exit 1' in launcher
    assert 'SOURCE_QOS_OVERRIDE_FILE="/etc/thesis/live_record_qos_overrides.yaml"' in launcher
    assert '--qos-profile-overrides-path "$SOURCE_QOS_OVERRIDE_FILE"' in launcher


def test_source_record_no_mavros_is_documented():
    usage = USAGE.read_text(encoding="utf-8")

    assert "--source-record-no-mavros" in usage
    assert "no MAVROS or network-mode change" in usage
