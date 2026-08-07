"""Tests for the Issue #30 external-sequence end-to-end report orchestrator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "run_external_sequence_report.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("run_external_sequence_report", MODULE_PATH)

import external_tracking_dataset as adapter  # noqa: E402


def make_dancetrack_rows(tmp_path):
    gt_dir = tmp_path / "dancetrack0099" / "gt"
    gt_dir.mkdir(parents=True)
    gt_path = gt_dir / "gt.txt"
    rows = [
        "1,5,10,10,20,40,1,1,1",  # target identity 5
        "1,6,50,50,20,40,1,1,1",  # other identity 6, same frame
        "2,5,11,10,20,40,1,1,1",
    ]
    gt_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    geometry = adapter.SequenceGeometry(
        image_width=1920,
        image_height=1080,
        frame_rate=20.0,
        source_index_base=1,
    )
    return adapter.parse_dancetrack_annotations(
        gt_path,
        sequence_name="dancetrack0099",
        split="val",
        geometry=geometry,
    )


class TestTargetAndOtherPeopleGrouping:
    def test_separates_target_from_other_people_by_frame(self, tmp_path):
        rows = make_dancetrack_rows(tmp_path)
        dataset_identity = 5

        target_by_frame = {
            row.normalized_frame_index: row
            for row in rows
            if row.identity == dataset_identity
            and row.include_as_person_candidate
        }

        other_people_by_frame: dict[int, list] = {}
        for row in rows:
            if row.identity == dataset_identity:
                continue
            if not row.include_as_person_candidate:
                continue
            other_people_by_frame.setdefault(
                row.normalized_frame_index, []
            ).append(
                MODULE.OtherPerson(
                    normalized_frame_index=row.normalized_frame_index,
                    dataset_identity=row.identity,
                    bbox_xyxy=row.bbox_xyxy,
                )
            )

        assert set(target_by_frame.keys()) == {0, 1}
        assert list(other_people_by_frame.keys()) == [0]
        assert other_people_by_frame[0][0].dataset_identity == 6


class TestBuildReportInitializationFailure:
    def test_reports_initialization_failure_without_running_replay(
        self, monkeypatch
    ):
        called = {"replay_ran": False}

        def fake_resolve(**kwargs):
            return {
                "sequence_id": kwargs["sequence_id"],
                "success": False,
                "reason": "no_confirmed_initial_tracker_match",
                "initial_tracker_identity": None,
            }

        def fake_load_manifest_entry(*args, **kwargs):
            return {"id": "x", "dataset": "dancetrack"}

        def fake_run_replay(**kwargs):
            called["replay_ran"] = True

        monkeypatch.setattr(MODULE, "resolve", fake_resolve)
        monkeypatch.setattr(
            MODULE, "load_manifest_entry", fake_load_manifest_entry
        )
        monkeypatch.setattr(
            MODULE, "run_deterministic_replay", fake_run_replay
        )

        report = MODULE.build_report(
            sequence_id="dancetrack_val_dancetrack0099",
            capture_bag=Path("/nonexistent/bag"),
        )

        assert report["status"] == "initialization_failure"
        assert called["replay_ran"] is False


class TestRunDeterministicReplayPassesSourceDimensions:
    def test_subprocess_command_includes_frozen_image_dimensions(
        self, monkeypatch, tmp_path
    ):
        # Regression test for the uav0000339_00001_v false wrong-person
        # signal (2026-08-07): run_deterministic_tim_replay.py defaults to
        # 640x640 (the ROS 2 field sequences' resolution) when these flags
        # are omitted. External sequences have a different source
        # resolution (e.g. VisDrone at 1904x1071); omitting the flags made
        # TIM-MARS clip candidate boxes, normalize geometry against the
        # wrong diagonal, and rescale appearance crops incorrectly, while
        # the unaffected raw baseline just copies boxes through -- producing
        # a spurious TIM-only "wrong person" signal that was actually a
        # pipeline coordinate-space bug, not a tracking failure.
        captured_argv = {}

        def fake_run(argv, cwd, check):
            captured_argv["argv"] = argv

        monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

        MODULE.run_deterministic_replay(
            capture_bag=tmp_path / "capture",
            output_bag=tmp_path / "output",
            selected_track_id=1,
            image_width=1904,
            image_height=1071,
            repo_root=tmp_path,
        )

        argv = captured_argv["argv"]
        assert "--image-width" in argv
        assert argv[argv.index("--image-width") + 1] == "1904"
        assert "--image-height" in argv
        assert argv[argv.index("--image-height") + 1] == "1071"

    def test_build_report_passes_manifest_image_dimensions_through(
        self, monkeypatch, tmp_path
    ):
        captured = {}

        def fake_resolve(**kwargs):
            return {
                "sequence_id": kwargs["sequence_id"],
                "success": True,
                "initial_tracker_identity": 1,
            }

        def fake_load_manifest_entry(*args, **kwargs):
            return {
                "id": "visdrone_mot_val_uav0000339_00001_v",
                "dataset": "visdrone_mot",
                "sequence_name": "uav0000339_00001_v",
                "split": "val",
                "image": {"width": 1904, "height": 1071},
                "frame_contract": {
                    "frame_rate": 24.0,
                    "normalized_start_index": 0,
                    "normalized_end_index_inclusive": 1,
                },
                "target": {
                    "dataset_identity": 17,
                    "minimum_match_iou": 0.5,
                    "minimum_match_margin": 0.1,
                    "confirmation_frames": 2,
                    "initialization_start_frame": 0,
                    "initialization_end_frame_inclusive": 9,
                },
            }

        def fake_run_replay(**kwargs):
            captured["image_width"] = kwargs["image_width"]
            captured["image_height"] = kwargs["image_height"]

        def fake_read_target_stream(*args, **kwargs):
            return {}

        def fake_load_all_annotations(entry):
            return []

        monkeypatch.setattr(MODULE, "resolve", fake_resolve)
        monkeypatch.setattr(
            MODULE, "load_manifest_entry", fake_load_manifest_entry
        )
        monkeypatch.setattr(
            MODULE, "run_deterministic_replay", fake_run_replay
        )
        monkeypatch.setattr(
            MODULE, "read_target_stream", fake_read_target_stream
        )
        monkeypatch.setattr(
            MODULE, "load_all_annotations", fake_load_all_annotations
        )

        MODULE.build_report(
            sequence_id="visdrone_mot_val_uav0000339_00001_v",
            capture_bag=tmp_path / "capture",
            replay_output_root=tmp_path / "replay",
        )

        assert captured["image_width"] == 1904
        assert captured["image_height"] == 1071
