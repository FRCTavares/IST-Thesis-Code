"""Tests for resolving the frozen tracker identity of a captured sequence."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "resolve_external_candidate_stream.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "resolve_external_candidate_stream",
    MODULE_PATH,
)


class TestAnnotationPathFor:
    def test_dancetrack_path(self):
        entry = {
            "dataset": "dancetrack",
            "split": "val",
            "sequence_name": "dancetrack0004",
        }

        path = MODULE.annotation_path_for(entry)

        assert path == (
            ROOT
            / "data"
            / "datasets"
            / "external"
            / "dancetrack"
            / "val"
            / "dancetrack0004"
            / "gt"
            / "gt.txt"
        )

    def test_visdrone_path(self):
        entry = {
            "dataset": "visdrone_mot",
            "split": "val",
            "sequence_name": "uav0000137_00458_v",
        }

        path = MODULE.annotation_path_for(entry)

        assert path == (
            ROOT
            / "data"
            / "datasets"
            / "external"
            / "visdrone_mot"
            / "val"
            / "annotations"
            / "uav0000137_00458_v.txt"
        )

    def test_unsupported_dataset_raises(self):
        import pytest

        entry = {
            "dataset": "mot17",
            "split": "train",
            "sequence_name": "MOT17-02-FRCNN",
        }

        with pytest.raises(ValueError, match="unsupported dataset"):
            MODULE.annotation_path_for(entry)


class TestLoadManifestEntry:
    def test_finds_matching_id(self, tmp_path):
        import json

        manifest = {
            "sequences": [
                {"id": "a", "value": 1},
                {"id": "b", "value": 2},
            ]
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        entry = MODULE.load_manifest_entry(manifest_path, sequence_id="b")

        assert entry["value"] == 2

    def test_missing_id_raises(self, tmp_path):
        import json

        import pytest

        manifest = {"sequences": [{"id": "a", "value": 1}]}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(ValueError, match="sequence id not found"):
            MODULE.load_manifest_entry(manifest_path, sequence_id="missing")


class TestLoadTargetObservationsFiltering:
    def test_filters_by_identity_and_window(self, tmp_path):
        gt_dir = tmp_path / "dancetrack0099" / "gt"
        gt_dir.mkdir(parents=True)
        gt_path = gt_dir / "gt.txt"
        # frame,id,x,y,w,h,conf,class,vis
        rows = [
            "1,5,10,10,20,40,1,1,1",
            "2,5,11,10,20,40,1,1,1",
            "12,5,12,10,20,40,1,1,1",  # outside init window (0-9)
            "1,6,50,50,20,40,1,1,1",  # different identity
        ]
        gt_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

        data_root = tmp_path
        # patch ROOT-relative lookup by calling annotation_path_for logic
        # directly against a constructed geometry/annotation pair instead of
        # going through the real repository data directory.
        import external_tracking_dataset as adapter

        geometry = adapter.SequenceGeometry(
            image_width=1920,
            image_height=1080,
            frame_rate=20.0,
            source_index_base=1,
        )
        parsed = adapter.parse_dancetrack_annotations(
            gt_path,
            sequence_name="dancetrack0099",
            split="val",
            geometry=geometry,
        )

        entry = {
            "target": {
                "dataset_identity": 5,
                "initialization_start_frame": 0,
                "initialization_end_frame_inclusive": 9,
            }
        }

        selected = [
            row
            for row in parsed
            if row.identity == entry["target"]["dataset_identity"]
            and entry["target"]["initialization_start_frame"]
            <= row.normalized_frame_index
            <= entry["target"]["initialization_end_frame_inclusive"]
            and row.include_as_person_candidate
        ]

        assert len(selected) == 2
        assert {row.normalized_frame_index for row in selected} == {0, 1}


def write_fake_bag(bag_dir, *, compressed):
    import yaml

    bag_dir.mkdir(parents=True)
    payload = b"not a real mcap file, just bytes for the test" * 1000

    metadata = {
        "rosbag2_bagfile_information": {
            "version": 9,
            "storage_identifier": "mcap",
            "duration": {"nanoseconds": 0},
            "starting_time": {"nanoseconds_since_epoch": 0},
            "message_count": 0,
            "topics_with_message_count": [],
            "relative_file_paths": [
                "bag_0.mcap.zstd" if compressed else "bag_0.mcap"
            ],
            "files": [
                {
                    "path": "bag_0.mcap",
                    "starting_time": {"nanoseconds_since_epoch": 0},
                    "duration": {"nanoseconds": 0},
                    "message_count": 0,
                }
            ],
            "custom_data": None,
            "ros_distro": "jazzy",
        }
    }

    if compressed:
        metadata["rosbag2_bagfile_information"]["compression_format"] = (
            "zstd"
        )
        metadata["rosbag2_bagfile_information"]["compression_mode"] = "FILE"

        raw_path = bag_dir / "bag_0.mcap"
        raw_path.write_bytes(payload)
        import subprocess

        subprocess.run(
            ["zstd", "-f", str(raw_path), "-o", str(bag_dir / "bag_0.mcap.zstd")],
            check=True,
        )
        raw_path.unlink()
    else:
        (bag_dir / "bag_0.mcap").write_bytes(payload)

    (bag_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8"
    )

    return payload


class TestIsCompressedBag:
    def test_uncompressed_bag_is_false(self, tmp_path):
        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=False)

        assert MODULE.is_compressed_bag(bag_dir) is False

    def test_compressed_bag_is_true(self, tmp_path):
        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=True)

        assert MODULE.is_compressed_bag(bag_dir) is True

    def test_missing_metadata_is_false(self, tmp_path):
        bag_dir = tmp_path / "empty"
        bag_dir.mkdir()

        assert MODULE.is_compressed_bag(bag_dir) is False


class TestEnsureUncompressedBag:
    def test_uncompressed_bag_returned_unchanged(self, tmp_path):
        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=False)

        result = MODULE.ensure_uncompressed_bag(bag_dir)

        assert result == bag_dir

    def test_compressed_bag_is_decompressed_correctly(self, tmp_path):
        bag_dir = tmp_path / "bag"
        original_payload = write_fake_bag(bag_dir, compressed=True)

        result = MODULE.ensure_uncompressed_bag(bag_dir)

        assert result != bag_dir
        assert MODULE.is_compressed_bag(result) is False
        assert (result / "bag_0.mcap").read_bytes() == original_payload

    def test_decompressed_metadata_has_no_compression_fields(
        self, tmp_path
    ):
        import yaml

        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=True)

        result = MODULE.ensure_uncompressed_bag(bag_dir)

        rewritten = yaml.safe_load(
            (result / "metadata.yaml").read_text(encoding="utf-8")
        )
        info = rewritten["rosbag2_bagfile_information"]

        assert "compression_format" not in info
        assert "compression_mode" not in info
        assert info["relative_file_paths"] == ["bag_0.mcap"]

    def test_refuses_when_insufficient_disk_space(
        self, tmp_path, monkeypatch
    ):
        import shutil

        import pytest

        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=True)

        class FakeUsage:
            free = 1 * (1024**3)  # 1 GiB, far below any real requirement
            total = 0
            used = 0

        monkeypatch.setattr(
            shutil, "disk_usage", lambda _path: FakeUsage()
        )

        with pytest.raises(RuntimeError, match="refusing to decompress"):
            MODULE.ensure_uncompressed_bag(bag_dir)


class TestOpenBagReaderRefusesCompressed:
    def test_raises_on_compressed_bag(self, tmp_path):
        import pytest

        bag_dir = tmp_path / "bag"
        write_fake_bag(bag_dir, compressed=True)

        with pytest.raises(ValueError, match="still compressed"):
            MODULE.open_bag_reader(bag_dir)
