"""Tests for the Issue #58 comparison aggregator's scientific contracts.

These build small synthetic fixtures rather than depending on the real
generated reports, following the P030/P031 testing convention.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "aggregate_lightweight_vs_integrated_report.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("aggregate_lightweight_vs_integrated_report", MODULE_PATH)


def make_calibration_row(config_id, dimension_id, tim_wrong, tim_lost, tim_absent=0.0):
    return {
        "config_id": config_id,
        "dimension_id": dimension_id,
        "raw_wrong_s": 5.0,
        "raw_absent_valid_s": 0.0,
        "tim_wrong_s": tim_wrong,
        "tim_lost_s": tim_lost,
        "tim_absent_valid_s": tim_absent,
    }


class TestAsymmetricSafetyGate:
    def test_promotable_configuration_with_lowest_wrong_is_selected(self, tmp_path):
        rows = [
            make_calibration_row("baseline", None, tim_wrong=6.0, tim_lost=50.0),
            make_calibration_row("dim_a_lower", "dim_a", tim_wrong=4.0, tim_lost=52.0),
            make_calibration_row("dim_a_higher", "dim_a", tim_wrong=5.9, tim_lost=48.0),
        ]
        path = tmp_path / "calibration_aggregate.json"
        path.write_text(json.dumps(rows))

        gate = {"wrong_target_tolerance_s": 0.05, "absence_output_tolerance_s": 0.05}
        winner_id, winner = MODULE.select_calibrated_sort_config(path, gate)

        assert winner_id == "dim_a_lower"

    def test_no_promotable_configuration_fails_closed(self, tmp_path):
        rows = [
            make_calibration_row("baseline", None, tim_wrong=6.0, tim_lost=50.0),
            make_calibration_row("dim_a_lower", "dim_a", tim_wrong=7.0, tim_lost=10.0),
        ]
        path = tmp_path / "calibration_aggregate.json"
        path.write_text(json.dumps(rows))

        gate = {"wrong_target_tolerance_s": 0.05, "absence_output_tolerance_s": 0.05}
        with pytest.raises(
            MODULE.NoPromotableConfiguration, match="no SORT\\+TIM calibration configuration"
        ):
            MODULE.select_calibrated_sort_config(path, gate)

    def test_gate_failure_carries_closest_candidate_not_a_fabricated_winner(self, tmp_path):
        rows = [
            make_calibration_row("baseline", None, tim_wrong=16.0, tim_lost=5.0),
            make_calibration_row("dim_a_lower", "dim_a", tim_wrong=15.3, tim_lost=7.0),
        ]
        path = tmp_path / "calibration_aggregate.json"
        path.write_text(json.dumps(rows))

        gate = {"wrong_target_tolerance_s": 0.05, "absence_output_tolerance_s": 0.05}
        with pytest.raises(MODULE.NoPromotableConfiguration) as excinfo:
            MODULE.select_calibrated_sort_config(path, gate)

        assert excinfo.value.closest["config_id"] == "dim_a_lower"

    def test_build_records_no_safe_configuration_found_not_available(self):
        manifest = {
            "development_sequences": [{"id": "dev_may_hard_reentry"}],
            "architectures": [
                {
                    "id": "sort_tim",
                    "tracker_type": "sort",
                    "tim_enabled": True,
                    "data_source": "run_fresh",
                }
            ],
            "annotation_availability": {
                "dev_may_hard_reentry": {"sort": "available"},
            },
        }
        closest = {"config_id": "confirmation_time_higher_3", "tim_wrong_s": 15.331, "tim_lost_s": 6.919}
        rows = MODULE.build(manifest, calibrated_sort_config_id=None, sort_tim_gate_failure=closest)

        assert len(rows) == 1
        assert rows[0]["status"] == "no_safe_configuration_found"
        assert rows[0]["wrong_s"] == 15.331
        assert "confirmation_time_higher_3" in rows[0]["note"]

    def test_absence_output_regression_alone_blocks_promotion(self, tmp_path):
        rows = [
            make_calibration_row("baseline", None, tim_wrong=6.0, tim_lost=50.0, tim_absent=0.0),
            make_calibration_row(
                "dim_a_lower", "dim_a", tim_wrong=4.0, tim_lost=48.0, tim_absent=1.0
            ),
        ]
        for row in rows:
            row["raw_wrong_s"] = 6.0  # baseline itself must be within tolerance of raw
        path = tmp_path / "calibration_aggregate.json"
        path.write_text(json.dumps(rows))

        gate = {"wrong_target_tolerance_s": 0.05, "absence_output_tolerance_s": 0.05}
        winner_id, _ = MODULE.select_calibrated_sort_config(path, gate)

        # dim_a_lower has the lowest wrong but a disqualifying absence-output
        # regression; only baseline remains promotable.
        assert winner_id == "baseline"

    def test_selection_never_uses_a_single_blended_scalar(self):
        # Structural check: the selection sort key is a tuple of the two
        # named safety/availability metrics, never a combined score.
        import inspect

        source = inspect.getsource(MODULE.select_calibrated_sort_config)
        assert "tim_wrong_s" in source
        assert "tim_lost_s" in source
        assert "score" not in source.lower()
        assert "weight" not in source.lower()


class TestPendingAnnotationAccounting:
    def test_pending_row_has_no_fabricated_metrics(self):
        row = MODULE.pending_row("sort_tim", "dev_june_seq01")
        assert row["status"] == "pending_annotation"
        assert row["wrong_s"] is None
        assert row["correct_s"] is None
        assert row["lost_s"] is None

    def test_pending_cells_are_never_silently_dropped(self, tmp_path, monkeypatch):
        manifest = {
            "development_sequences": [{"id": "dev_june_seq01"}],
            "architectures": [
                {
                    "id": "sort_tim",
                    "tracker_type": "sort",
                    "tim_enabled": True,
                    "data_source": "run_fresh",
                }
            ],
            "annotation_availability": {
                "dev_june_seq01": {"sort": "pending_annotation"},
            },
        }
        rows = MODULE.build(manifest, calibrated_sort_config_id=None)
        assert len(rows) == 1
        assert rows[0]["status"] == "pending_annotation"
        assert rows[0]["architecture_id"] == "sort_tim"
        assert rows[0]["sequence_id"] == "dev_june_seq01"


class TestDurationFieldExtraction:
    def test_cell_row_reads_correct_stream_for_raw_vs_tim(self):
        report = {
            "duration_metrics": {
                "raw_target": {
                    "correct_target_duration_s": "1.0",
                    "wrong_target_duration_s": "2.0",
                    "lost_target_duration_s": "3.0",
                    "target_absent_but_output_valid_duration_s": "0.0",
                    "no_target_selected_duration_s": "0.0",
                },
                "tim_target_memory": {
                    "correct_target_duration_s": "10.0",
                    "wrong_target_duration_s": "20.0",
                    "lost_target_duration_s": "30.0",
                    "target_absent_but_output_valid_duration_s": "0.0",
                    "no_target_selected_duration_s": "0.0",
                },
            },
            "episode_metrics": {
                "raw_target": {
                    "wrong_target_burst_count": 1,
                    "wrong_handover_count": 0,
                    "longest_wrong_target_burst_s": 2.0,
                },
                "tim_target_memory": {
                    "wrong_target_burst_count": 2,
                    "wrong_handover_count": 1,
                    "longest_wrong_target_burst_s": 20.0,
                },
            },
            "status_recovery_metrics": {
                "recovery_attempt_count": 5,
                "correct_candidate_suppressed_duration_s": 1.5,
            },
        }
        raw_row = MODULE.cell_row("bytetrack_raw", "dev_may_hard_reentry", report, "raw_target")
        tim_row = MODULE.cell_row("bytetrack_tim", "dev_may_hard_reentry", report, "tim_target_memory")

        assert raw_row["wrong_s"] == 2.0
        assert tim_row["wrong_s"] == 20.0
        assert raw_row["status"] == "available"
        # Raw stream never carries TIM's status-derived recovery metrics.
        assert raw_row["recovery_attempt_count"] is None
        assert tim_row["recovery_attempt_count"] == 5
