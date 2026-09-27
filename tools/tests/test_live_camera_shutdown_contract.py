"""Contracts for clean integrated-camera shutdown."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAMERA = (
    ROOT
    / "ros2_ws/src/thesis_bringup/thesis_bringup/perception/perception_camera_node.py"
).read_text(encoding="utf-8")


def test_publish_context_error_is_ignored_only_during_shutdown():
    start = CAMERA.index("except RCLError as exc:")
    end = CAMERA.index("if self._fps > 0.0:", start)
    block = CAMERA[start:end]

    assert "self._camera_stop.is_set() or not rclpy.ok()" in block
    assert "\"publisher's context is invalid\" in str(exc)" in block
    assert "return" in block
    assert "raise" in block


def test_camera_thread_must_exit_before_node_destruction():
    start = CAMERA.index("def destroy_node(self)")
    block = CAMERA[start:]

    assert "self._camera_stop.set()" in block
    assert "self._camera_thread.join(timeout=5.0)" in block
    assert "if self._camera_thread.is_alive():" in block
    assert (
        'raise RuntimeError('
        '"camera capture thread did not stop before node destruction")'
    ) in block
