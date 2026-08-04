from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from sensor_msgs.msg import Image
from thesis_msgs.msg import Track2DArray


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "tools/experiments/p044_soak_input_relay.py"

SPEC = importlib.util.spec_from_file_location(
    "p044_soak_input_relay_under_test",
    PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_allocator_is_strictly_monotonic() -> None:
    allocator = MODULE.StrictStampAllocator()

    assert allocator.allocate(100) == 100
    assert allocator.allocate(100) == 101
    assert allocator.allocate(50) == 102
    assert allocator.allocate(200) == 200


def test_rewind_tracker_counts_repeat_and_backward() -> None:
    tracker = MODULE.SourceRewindTracker()

    for value in (0, 100, 101, 101, 50, 200):
        tracker.observe(value)

    assert tracker.rewinds == 2
    assert tracker.last_positive_ns == 200


def test_image_stamp_is_refreshed_without_mutating_source() -> None:
    message = Image()
    message.header.stamp.sec = 1
    message.header.stamp.nanosec = 2
    message.width = 640

    output = MODULE.rewrite_image(
        message,
        5_000_000_006,
    )

    assert MODULE.stamp_to_ns(output.header.stamp) == 5_000_000_006
    assert MODULE.stamp_to_ns(message.header.stamp) == 1_000_000_002
    assert output.width == 640


def test_tracks_refresh_preserves_track_ids() -> None:
    message = Track2DArray()
    message.header.stamp.sec = 3
    message.src_stamp_ns = 3_000_000_000
    message.frame_id = 9

    output = MODULE.rewrite_tracks(
        message,
        7_000_000_005,
        42,
    )

    assert MODULE.stamp_to_ns(output.header.stamp) == 7_000_000_005
    assert output.src_stamp_ns == 7_000_000_005
    assert output.frame_id == 42
    assert message.src_stamp_ns == 3_000_000_000
    assert message.frame_id == 9


def test_claim_boundary_remains_experiment_only() -> None:
    text = PATH.read_text(encoding="utf-8")

    required = (
        '"experiment_only_timestamp_refresh": True',
        '"cpu_mars_authoritative": True',
        '"repvgg_observational": True',
        '"canonical_policy_changed": False',
        '"production_nodes_modified": False',
    )

    for fragment in required:
        assert fragment in text
