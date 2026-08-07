"""Tests for the Issue #30 first-phase aggregate report builder."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "aggregate_first_phase_report.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("aggregate_first_phase_report", MODULE_PATH)


def make_manifest(tmp_path):
    manifest = {
        "status": "frozen",
        "frozen_date": "2026-08-07",
        "sequences": [
            {
                "id": "dancetrack_val_seqA",
                "dataset": "dancetrack",
                "sequence_name": "seqA",
            },
            {
                "id": "visdrone_mot_val_seqB",
                "dataset": "visdrone_mot",
                "sequence_name": "seqB",
            },
            {
                "id": "ros2_internal_development_may_hard_reentry",
                "dataset": "ros2_internal",
                "sequence_name": "may_hard_reentry",
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class TestBuildAggregate:
    def test_counts_evaluated_and_missing(self, tmp_path, monkeypatch):
        manifest_path = make_manifest(tmp_path)

        report_dir = tmp_path / "reports"
        report_dir.mkdir()
        (report_dir / "dancetrack_val_seqA.json").write_text(
            json.dumps({"status": "evaluated", "raw": {}, "tim_mars": {}}),
            encoding="utf-8",
        )
        (report_dir / "visdrone_mot_val_seqB.json").write_text(
            json.dumps(
                {
                    "status": "initialization_failure",
                    "resolution": {"reason": "no_confirmed_initial_tracker_match"},
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setitem(
            MODULE.ROS2_EVENT_RECOVERY_REPORTS,
            "ros2_internal_development_may_hard_reentry",
            tmp_path / "does_not_exist.json",
        )

        aggregate = MODULE.build_aggregate(
            manifest_path=manifest_path,
            external_report_dir=report_dir,
        )

        assert aggregate["total_sequences"] == 3
        assert aggregate["evaluated_count"] == 1
        assert aggregate["initialization_failure_count"] == 1
        assert aggregate["missing_report_count"] == 1

    def test_missing_external_report_is_reported_not_crashed(
        self, tmp_path
    ):
        manifest_path = make_manifest(tmp_path)
        report_dir = tmp_path / "empty_reports"
        report_dir.mkdir()

        aggregate = MODULE.build_aggregate(
            manifest_path=manifest_path,
            external_report_dir=report_dir,
        )

        by_id = {s["id"]: s for s in aggregate["sequences"]}
        assert (
            by_id["dancetrack_val_seqA"]["report"]["status"]
            == "missing_report"
        )
