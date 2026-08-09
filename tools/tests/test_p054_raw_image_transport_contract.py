"""Contract tests for Issue #54: raw-image publication must be configurable,
default off (no perception/tracking/TIM/dashboard consumer needs it), and
auto-enabled exactly when a recording path that genuinely needs it is
active. Also covers the --record-dataset truthfulness fix and the
/camera/fps ownership fix.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "tools/lib/live_cli.sh"
DEFAULTS = REPO_ROOT / "tools/lib/live_defaults.sh"
LAUNCHER = REPO_ROOT / "tools/start_live_stack.sh"
USAGE = REPO_ROOT / "tools/lib/live_usage.sh"
PERCEPTION_CAMERA_NODE = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/thesis_bringup/perception/perception_camera_node.py"
)


def _case_block(text: str, option: str, next_option: str) -> str:
    start = text.index(f"        {option})")
    end = text.index(f"        {next_option})", start)
    return text[start:end]


def test_image_raw_publish_flag_is_off_by_default():
    defaults = DEFAULTS.read_text(encoding="utf-8")
    assert 'CAMERA_PUBLISH_IMAGE_RAW_BOOL="false"' in defaults
    assert "CAMERA_PUBLISH_IMAGE_RAW_EXPLICIT=0" in defaults


def test_image_raw_cli_flags_set_explicit_and_value():
    cli = CLI.read_text(encoding="utf-8")

    on_block = _case_block(cli, "--camera-publish-image-raw", "--camera-no-publish-image-raw")
    off_block = _case_block(cli, "--camera-no-publish-image-raw", "--source-record")

    assert "CAMERA_PUBLISH_IMAGE_RAW_EXPLICIT=1" in on_block
    assert 'CAMERA_PUBLISH_IMAGE_RAW_BOOL="true"' in on_block
    assert "CAMERA_PUBLISH_IMAGE_RAW_EXPLICIT=1" in off_block
    assert 'CAMERA_PUBLISH_IMAGE_RAW_BOOL="false"' in off_block


def test_image_raw_auto_enabled_by_raw_recording_paths_and_conflict_is_an_error():
    cli = CLI.read_text(encoding="utf-8")

    assert "REQUIRES_IMAGE_RAW=0" in cli
    assert '"$FIELD_RAW_IMAGE_RECORD" -eq 1 || "$ENABLE_DATASET_BAG" -eq 1' in cli
    assert '"${SOURCE_RAW_IMAGE_RECORD:-0}" -eq 1' in cli
    assert 'CAMERA_PUBLISH_IMAGE_RAW_BOOL="true"' in cli
    assert "--camera-no-publish-image-raw conflicts with an active raw-image recording flag" in cli


def test_perception_camera_launch_passes_resolved_image_raw_and_fps_flags():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "-p publish_image_raw:=$CAMERA_PUBLISH_IMAGE_RAW_BOOL" in launcher
    assert "-p publish_fps_topic:=true" in launcher
    assert "-p fps_topic:=/camera/fps" in launcher


def test_startup_log_reflects_resolved_state_not_a_hardcoded_claim():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert 'log_info "full-rate raw image publishing is disabled in live operation"' not in launcher
    assert 'if [[ "$CAMERA_PUBLISH_IMAGE_RAW_BOOL" == "true" ]]; then' in launcher
    assert "full-rate /camera/image_raw publishing is ENABLED" in launcher
    assert "full-rate /camera/image_raw publishing is disabled" in launcher


def test_record_dataset_topic_list_includes_image_raw_and_drops_unowned_camera_info():
    launcher = LAUNCHER.read_text(encoding="utf-8")

    start = launcher.index("DATASET_BAG_TOPICS=(")
    end = launcher.index(")", start)
    block = launcher[start:end]

    assert "/camera/image_raw" in block
    assert "/camera/fps" in block
    assert "/camera/camera_info" not in block


def test_record_dataset_help_text_matches_actual_behavior():
    usage = USAGE.read_text(encoding="utf-8")
    assert "Record raw camera imagery + perception/TIM telemetry for offline replay" in usage


def test_advanced_help_documents_new_image_raw_flags_with_consequences():
    usage = USAGE.read_text(encoding="utf-8")
    assert "--camera-publish-image-raw" in usage
    assert "--camera-no-publish-image-raw" in usage
    assert "26.4 MiB/s" in usage


def test_perception_camera_node_gates_image_raw_publisher_on_parameter():
    source = PERCEPTION_CAMERA_NODE.read_text(encoding="utf-8")

    assert 'self.declare_parameter("publish_image_raw", False)' in source
    assert "self._publish_image_raw = bool(self.get_parameter" in source
    assert (
        "self.create_publisher(Image, \"/camera/image_raw\", dashboard_qos)\n"
        "            if self._publish_image_raw\n"
        "            else None"
    ) in source
    assert "if self._image_raw_pub is not None:" in source


def test_perception_camera_node_owns_camera_fps_publisher():
    source = PERCEPTION_CAMERA_NODE.read_text(encoding="utf-8")

    assert 'self.declare_parameter("publish_fps_topic", True)' in source
    assert 'self.declare_parameter("fps_topic", "/camera/fps")' in source
    assert "def _maybe_publish_fps(self) -> None:" in source
    assert "self._maybe_publish_fps()" in source
    # Same rolling-window convention already proven in video_file_publisher_node.py.
    assert "window_ns = 3_000_000_000" in source
    assert "200_000_000" in source
