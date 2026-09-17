"""Focused tests for the Issue #64 exact-PTS video source adapter."""

from __future__ import annotations

import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "experiments" / "prepare_p064_video_source.py"

spec = importlib.util.spec_from_file_location(
    "prepare_p064_video_source",
    MODULE_PATH,
)
assert spec is not None and spec.loader is not None

MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def test_exact_millisecond_pts_mapping_preserves_intervals():
    source, mapped = MODULE.map_source_timestamps(
        [0, 21, 47, 108],
        time_base=Fraction(1, 1000),
        timestamp_offset_ns=1_000_000_000,
    )

    assert source == [
        0,
        21_000_000,
        47_000_000,
        108_000_000,
    ]
    assert mapped == [
        1_000_000_000,
        1_021_000_000,
        1_047_000_000,
        1_108_000_000,
    ]
    assert [
        b - a for a, b in zip(source, source[1:])
    ] == [
        b - a for a, b in zip(mapped, mapped[1:])
    ]


@pytest.mark.parametrize(
    "ticks",
    [
        [0, 0, 1],
        [0, 2, 1],
    ],
)
def test_nonmonotonic_video_pts_fail_closed(ticks):
    with pytest.raises(ValueError, match="strictly increasing"):
        MODULE.map_source_timestamps(
            ticks,
            time_base=Fraction(1, 1000),
            timestamp_offset_ns=1_000_000_000,
        )


def test_offset_must_make_first_timestamp_positive():
    with pytest.raises(ValueError, match="positive"):
        MODULE.map_source_timestamps(
            [0, 1],
            time_base=Fraction(1, 1000),
            timestamp_offset_ns=0,
        )


def test_non_integer_nanosecond_pts_fail_closed():
    with pytest.raises(ValueError, match="exactly"):
        MODULE.exact_pts_ns(
            1,
            Fraction(1, 90_000),
        )


def test_time_base_validation():
    assert MODULE.parse_time_base("1/1000") == Fraction(1, 1000)

    with pytest.raises(ValueError):
        MODULE.parse_time_base("0/1")


def test_decode_command_is_passthrough_raw_bgr(tmp_path):
    path = tmp_path / "input.mkv"
    command = MODULE.ffmpeg_decode_command(path)

    assert command[0] == "ffmpeg"
    assert "-fps_mode" in command
    assert command[command.index("-fps_mode") + 1] == "passthrough"
    assert command[command.index("-pix_fmt") + 1] == "bgr24"
    assert command[-1] == "pipe:1"


def test_mcap_storage_uses_native_zstd_fast(tmp_path):
    options = MODULE.make_storage_options(tmp_path / "bag")

    assert options.storage_id == "mcap"
    assert options.storage_preset_profile == "zstd_fast"


def test_timestamp_digest_is_order_sensitive():
    assert MODULE.timestamp_digest([1, 2, 3]) != MODULE.timestamp_digest(
        [1, 3, 2]
    )

def test_artifact_manifest_hashes_existing_payload_files(tmp_path):
    first = tmp_path / "metadata.yaml"
    second = tmp_path / "payload.mcap"

    first.write_bytes(b"metadata")
    second.write_bytes(b"payload")

    manifest = MODULE.artifact_manifest(tmp_path)

    assert [entry["file"] for entry in manifest] == [
        "metadata.yaml",
        "payload.mcap",
    ]
    assert all(len(entry["sha256"]) == 64 for entry in manifest)
    assert [entry["bytes"] for entry in manifest] == [
        len(b"metadata"),
        len(b"payload"),
    ]
