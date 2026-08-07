"""Tests for the image-sequence-to-ROS2-bag source converter."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "experiments"
MODULE_PATH = ANALYSIS_DIR / "images_to_camera_bag.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("images_to_camera_bag", MODULE_PATH)


class TestDiscoverImages:
    def test_sorts_lexicographically(self, tmp_path):
        for name in ("00000010.jpg", "00000002.jpg", "00000001.png"):
            (tmp_path / name).write_bytes(b"x")

        images = MODULE.discover_images(tmp_path)

        assert [path.name for path in images] == [
            "00000001.png",
            "00000002.jpg",
            "00000010.jpg",
        ]

    def test_ignores_non_image_files(self, tmp_path):
        (tmp_path / "00000001.jpg").write_bytes(b"x")
        (tmp_path / "readme.txt").write_bytes(b"x")
        (tmp_path / "seqinfo.ini").write_bytes(b"x")

        images = MODULE.discover_images(tmp_path)

        assert [path.name for path in images] == ["00000001.jpg"]

    def test_raises_when_no_images(self, tmp_path):
        (tmp_path / "readme.txt").write_bytes(b"x")

        with pytest.raises(ValueError, match="no images found"):
            MODULE.discover_images(tmp_path)


class TestFrameTimestampsNs:
    def test_evenly_spaced_at_frame_rate(self):
        timestamps = MODULE.frame_timestamps_ns(
            5, frame_rate_hz=20.0, start_time_ns=0
        )

        assert timestamps == [0, 50_000_000, 100_000_000, 150_000_000, 200_000_000]

    def test_respects_start_time_offset(self):
        timestamps = MODULE.frame_timestamps_ns(
            3, frame_rate_hz=10.0, start_time_ns=1_000_000_000
        )

        assert timestamps == [
            1_000_000_000,
            1_100_000_000,
            1_200_000_000,
        ]

    def test_rejects_non_positive_count(self):
        with pytest.raises(ValueError, match="count must be positive"):
            MODULE.frame_timestamps_ns(0, frame_rate_hz=20.0, start_time_ns=0)

    def test_rejects_non_positive_frame_rate(self):
        with pytest.raises(ValueError, match="frame_rate_hz must be positive"):
            MODULE.frame_timestamps_ns(5, frame_rate_hz=0.0, start_time_ns=0)

    def test_monotonically_increasing(self):
        timestamps = MODULE.frame_timestamps_ns(
            50, frame_rate_hz=7.475, start_time_ns=0
        )

        assert all(
            later > earlier
            for earlier, later in zip(timestamps, timestamps[1:])
        )
