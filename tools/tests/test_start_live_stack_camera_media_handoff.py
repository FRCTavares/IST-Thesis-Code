from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
START = ROOT / "tools" / "start_live_stack.sh"


def _source() -> str:
    return START.read_text()


def test_integrated_camera_uses_runtime_media_device():
    text = _source()

    assert 'CAMERA_MEDIA_DEV_RUNTIME="${CAMERA_MEDIA_DEV_OVERRIDE:-/dev/media0}"' in text
    assert '-p media_dev:=$CAMERA_MEDIA_DEV_RUNTIME \\' in text

    launch_start = text.index("start_ros_bg perception_camera")
    launch_end = text.index("\n    sleep 2", launch_start)
    launch_block = text[launch_start:launch_end]

    assert "-p media_dev:=$CAMERA_MEDIA_DEV_RUNTIME" in launch_block


def test_runtime_media_device_is_retained_in_resolved_metadata():
    text = _source()

    metadata_start = text.index("PERCEPTION_CAMERA_RESOLVED_PARAMS=(")
    metadata_end = text.index("\n)", metadata_start)
    metadata_block = text[metadata_start:metadata_end]

    assert '"media_dev=$CAMERA_MEDIA_DEV_RUNTIME"' in metadata_block
