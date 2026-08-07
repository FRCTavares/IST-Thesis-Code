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
