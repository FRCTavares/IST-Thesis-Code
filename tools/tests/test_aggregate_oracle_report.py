"""Tests for the Issue #30 oracle-candidate aggregate report builder."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "aggregate_oracle_report.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("aggregate_oracle_report", MODULE_PATH)


def make_manifest(tmp_path):
    manifest = {
        "status": "frozen",
        "frozen_date": "2026-08-07",
        "sequences": [
            {
                "id": "visdrone_mot_val_seqA",
                "dataset": "visdrone_mot",
                "sequence_name": "seqA",
                "status": "frozen",
                "evaluation_modes": [
                    "oracle_candidate",
                    "detector_bytetrack_tim",
                ],
            },
            {
                "id": "dancetrack_val_seqB",
                "dataset": "dancetrack",
                "sequence_name": "seqB",
                "status": "excluded",
                "evaluation_modes": [
                    "oracle_candidate",
                    "detector_bytetrack_tim",
                ],
            },
            {
                "id": "ros2_internal_development_seqC",
                "dataset": "ros2_internal",
                "sequence_name": "seqC",
                "status": "frozen",
                "evaluation_modes": ["detector_bytetrack_tim"],
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


class TestBuildOracleAggregate:
    def test_only_oracle_eligible_non_excluded_sequences_included(
        self, tmp_path
    ):
        manifest_path = make_manifest(tmp_path)

        report_dir = tmp_path / "oracle_reports"
        report_dir.mkdir()
        (report_dir / "visdrone_mot_val_seqA.json").write_text(
            json.dumps({"status": "evaluated", "raw": {}, "tim_mars": {}}),
            encoding="utf-8",
        )

        aggregate = MODULE.build_oracle_aggregate(
            manifest_path=manifest_path,
            oracle_report_dir=report_dir,
        )

        assert aggregate["evaluation_mode"] == "oracle_candidate"
        assert aggregate["total_sequences"] == 1
        assert aggregate["evaluated_count"] == 1
        assert [s["id"] for s in aggregate["sequences"]] == [
            "visdrone_mot_val_seqA"
        ]

        skipped_by_id = {
            s["id"]: s["reason"] for s in aggregate["skipped_sequences"]
        }
        assert (
            skipped_by_id["dancetrack_val_seqB"]
            == "excluded_from_primary_scope"
        )
        assert (
            skipped_by_id["ros2_internal_development_seqC"]
            == "no_oracle_candidate_contract_declared"
        )

    def test_missing_oracle_report_is_reported_not_crashed(self, tmp_path):
        manifest_path = make_manifest(tmp_path)
        report_dir = tmp_path / "empty_reports"
        report_dir.mkdir()

        aggregate = MODULE.build_oracle_aggregate(
            manifest_path=manifest_path,
            oracle_report_dir=report_dir,
        )

        by_id = {s["id"]: s for s in aggregate["sequences"]}
        assert (
            by_id["visdrone_mot_val_seqA"]["report"]["status"]
            == "missing_report"
        )
