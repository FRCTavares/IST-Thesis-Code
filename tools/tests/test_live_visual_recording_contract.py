"""Contracts for separate visual recording in non-held-out live runs."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "tools/live"
LAUNCHER = (ROOT / "tools/start_live_stack.sh").read_text(encoding="utf-8")
CLI = (ROOT / "tools/lib/live_cli.sh").read_text(encoding="utf-8")
SHUTDOWN = (ROOT / "tools/lib/live_shutdown.sh").read_text(encoding="utf-8")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, LIVE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


visual_verifier = _load("verify_visual_evidence")
visual_metadata = _load("attach_visual_run_metadata")


@pytest.fixture
def fake_root(tmp_path):
    (tmp_path / "models/hef").mkdir(parents=True)
    (tmp_path / "models/reid").mkdir(parents=True)
    cfg = tmp_path / "ros2_ws/install/thesis_bringup/share/thesis_bringup/config"
    cfg.mkdir(parents=True)
    (tmp_path / "models/hef/yolov8s.hef").write_bytes(b"stub")
    (tmp_path / "models/reid/mars-small128.pb").write_bytes(b"stub")
    (cfg / "tim_mars_canonical.yaml").write_text("stub: true\n")
    return tmp_path


def _parse(fake_root, *args):
    library = ROOT / "tools/lib"
    shell = (
        "set +u; "
        f"source '{library}/live_usage.sh'; "
        f"source '{library}/live_defaults.sh'; "
        f"source '{library}/live_storage.sh'; "
        f"source '{library}/live_cli.sh'; "
        'parse_and_validate_live_stack_args "$@"; '
        'rc=$?; echo "RESOLVE visual=$FLIGHT_VISUAL_RECORD '
        'bag=$ENABLE_ROSBAG control=$ENABLE_CONTROL mavros=$RECORD_MAVROS '
        'raw=$FIELD_RAW_IMAGE_RECORD dash=$CAMERA_DASHBOARD_FPS '
        'rate_controls=$CAMERA_APPLY_RATE_CONTROLS_BOOL"; exit $rc'
    )
    result = subprocess.run(
        ["bash", "-c", shell, "bash", *args],
        cwd=ROOT, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(fake_root),
             "THESIS_ROOT": str(fake_root)},
    )
    return result


def test_manual_and_controller_profiles_resolve_without_mavros(fake_root):
    for options, controller in (
        (("--record-structured-visual", "--no-control"), "0"),
        (("--record-structured-visual",), "1"),
    ):
        result = _parse(fake_root, *options)
        assert result.returncode == 0, result.stdout + result.stderr
        resolved = result.stdout.split("RESOLVE ")[1]
        for token in ("visual=1", "bag=1", f"control={controller}",
                      "mavros=0", "raw=0", "dash=15.0", "rate_controls=true"):
            assert token in resolved


def test_field_profile_is_visual_but_does_not_enable_control_mirroring(fake_root):
    result = _parse(fake_root, "--field-record", "--no-control")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "visual=1" in result.stdout
    assert "control=0" in result.stdout
    assert "mavros=1" in result.stdout
    assert 'CONTROL_MAVROS_BOOL="false"' in (ROOT / "tools/lib/live_defaults.sh").read_text()


@pytest.mark.parametrize("options", [
    ("--record-structured-visual", "--record-raw"),
    ("--record-structured-visual", "--no-web-video"),
    ("--record-structured-visual", "--no-dashboard"),
    ("--record-structured-visual", "--camera-rate-controls-off"),
    ("--record-structured-visual", "--dash", "10"),
])
def test_profile_rejects_unmeasured_or_high_bandwidth_overrides(fake_root, options):
    result = _parse(fake_root, *options)
    assert result.returncode != 0
    assert "structured visual recording" in result.stdout


def test_structured_topics_exclude_images_and_visual_uses_same_run_id():
    topic_block = LAUNCHER.split("VIDEO_BAG_TOPICS=(", 1)[1].split("if [[ \"${RUN_TARGET_MEMORY_MARS", 1)[0]
    assert 'if [[ "${FLIGHT_VISUAL_RECORD:-0}" -ne 1 ]]; then' in topic_block
    assert "VIDEO_BAG_TOPICS=(/camera/dashboard" in topic_block
    assert "/camera/image_raw" not in topic_block
    assert 'VISUAL_FILE="$VIDEO_BAG_OUT_DIR/visual_${RUN_ID}.mkv"' in LAUNCHER
    assert "start_ros_bg visual_record ffmpeg" in LAUNCHER
    assert "-use_wallclock_as_timestamps 1" in LAUNCHER
    assert "-an -c:v copy" in LAUNCHER
    assert "quality=45" in LAUNCHER
    assert "--expect-visual" in LAUNCHER
    assert "stop_visual_recorder" in LAUNCHER
    assert "kill_tree \"$pid\" INT" in SHUTDOWN


def test_source_only_mode_does_not_inherit_visual_recording(fake_root):
    result = _parse(fake_root, "--source-record-no-mavros")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "visual=0" in result.stdout
    assert "bag=0" in result.stdout
    source = CLI[CLI.index("        --source-record-no-mavros)"):CLI.index("        --tag)", CLI.index("        --source-record-no-mavros)"))]
    for marker in ("SOURCE_RAW_IMAGE_RECORD=1", "SOURCE_DETECTIONS_RECORD=1",
                   "ENABLE_TRACKER=0", "ENABLE_CONTROL=0",
                   "ENABLE_DASHBOARD_BRIDGE=0", "SOURCE_MAVROS_RECORD=0"):
        assert marker in source


def test_visual_verifier_accepts_decodable_timestamped_mjpeg(tmp_path):
    bag = tmp_path / "bag"
    bag.mkdir()
    visual = bag / "visual_test_run.mkv"
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=size=640x480:rate=10",
         "-frames:v", "10", "-c:v", "mjpeg", "-y", str(visual)],
        capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stderr
    report = visual_verifier.verify_visual(
        bag, "test_run", recorder_alive_at_stop=True, finalization="graceful"
    )
    assert report["passed"] is True
    assert report["codec"] == "mjpeg"
    assert report["decoded_frames"] == 10
    assert report["timestamps"]["nondecreasing"] is True
    assert report["decode_to_null"]["returncode"] == 0


def test_visual_verifier_rejects_missing_and_corrupt_file(tmp_path):
    bag = tmp_path / "bag"
    bag.mkdir()
    missing = visual_verifier.verify_visual(
        bag, "test_run", recorder_alive_at_stop=False, finalization="failed"
    )
    assert missing["passed"] is False
    assert any("missing or empty" in error for error in missing["errors"])
    assert any("not alive" in error for error in missing["errors"])
    (bag / "visual_test_run.mkv").write_bytes(b"not a video")
    corrupt = visual_verifier.verify_visual(
        bag, "test_run", recorder_alive_at_stop=True, finalization="graceful"
    )
    assert corrupt["passed"] is False


def test_visual_start_attaches_only_to_matching_precomputed_run(tmp_path):
    bag = tmp_path / "bag"
    bag.mkdir()
    visual = bag / "visual_run123.mkv"
    visual.write_bytes(b"x")
    precomputed = tmp_path / "precomputed.json"
    precomputed.write_text(json.dumps({
        "run_id": "run123",
        "bag": {"out_dir": str(bag)},
        "visual": {"file": str(visual), "started_at_utc": ""},
    }))
    result = visual_metadata.attach(
        precomputed, bag / "run_metadata.json", "run123", visual,
        "2026-09-14T20:00:00.000000000Z",
    )
    assert result["visual"]["started_at_utc"].startswith("2026-09-14")
    with pytest.raises(ValueError, match="run ID mismatch"):
        visual_metadata.attach(
            precomputed, bag / "run_metadata.json", "another", visual,
            "2026-09-14T20:00:00Z",
        )
