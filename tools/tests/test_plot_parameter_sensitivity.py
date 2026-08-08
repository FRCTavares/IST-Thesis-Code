"""Tests for the Issue #31 (P1.13) figure generator.

These do not test pixel/visual aesthetics. They test the data/ordering
contract: parameter values plotted in true numeric order, canonical marked
at its true numeric position rather than forced first, confirmation-time
specifically resolving to 0,1,2,3,4, expected figure files being generated,
clear failure on missing/invalid aggregate input, and that plotting never
mutates the aggregate evidence it reads.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "tools" / "analysis"
PLOTTER_PATH = ANALYSIS_DIR / "plot_parameter_sensitivity.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("plot_parameter_sensitivity", PLOTTER_PATH)


CONFIRMATION_TIME_ROWS = [
    {
        "config_id": "confirmation_time_lower_1",
        "dimension_id": "confirmation_time",
        "overrides": json.dumps({"min_confirm_frames_after_reacquire": 0}),
        "tim_wrong_s": "6.0",
        "tim_lost_s": "50.0",
    },
    {
        "config_id": "baseline",
        "dimension_id": "",
        "overrides": json.dumps({}),
        "tim_wrong_s": "5.0",
        "tim_lost_s": "52.0",
    },
    {
        "config_id": "confirmation_time_higher_1",
        "dimension_id": "confirmation_time",
        "overrides": json.dumps({"min_confirm_frames_after_reacquire": 2}),
        "tim_wrong_s": "4.5",
        "tim_lost_s": "54.0",
    },
    {
        "config_id": "confirmation_time_higher_2",
        "dimension_id": "confirmation_time",
        "overrides": json.dumps({"min_confirm_frames_after_reacquire": 3}),
        "tim_wrong_s": "4.4",
        "tim_lost_s": "55.0",
    },
    {
        "config_id": "confirmation_time_higher_3",
        "dimension_id": "confirmation_time",
        "overrides": json.dumps({"min_confirm_frames_after_reacquire": 4}),
        "tim_wrong_s": "4.3",
        "tim_lost_s": "57.0",
    },
]


def write_full_aggregate_csv(path: Path) -> None:
    """A minimal but complete (all 7 dimensions + baseline) synthetic
    aggregate CSV, using only the columns the plot script reads."""
    rows = [
        {
            "config_id": "baseline",
            "dimension_id": "",
            "overrides": "{}",
            "tim_wrong_s": "5.0",
            "tim_lost_s": "50.0",
        }
    ]
    for dimension_id, canonical_value in MODULE.CANONICAL_VALUE.items():
        for i, offset in enumerate([-2, -1, 1, 2]):
            rows.append(
                {
                    "config_id": f"{dimension_id}_perturb_{i}",
                    "dimension_id": dimension_id,
                    "overrides": json.dumps({"x": canonical_value + offset * 0.01}),
                    "tim_wrong_s": "5.0",
                    "tim_lost_s": "50.0",
                }
            )
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestOrdering:
    def test_confirmation_time_resolves_to_0_1_2_3_4(self):
        dim_rows = MODULE.dimension_rows(CONFIRMATION_TIME_ROWS, "confirmation_time")
        values = [MODULE.row_value(r, "confirmation_time") for r in dim_rows]
        assert values == [0, 1, 2, 3, 4]

    def test_canonical_is_at_true_numeric_position_not_forced_first(self):
        dim_rows = MODULE.dimension_rows(CONFIRMATION_TIME_ROWS, "confirmation_time")
        assert dim_rows[0]["config_id"] != "baseline"
        assert dim_rows[1]["config_id"] == "baseline"
        labels = [MODULE.perturbation_label(r) for r in dim_rows]
        assert labels == ["0", "canonical", "2", "3", "4"]

    def test_input_row_order_does_not_affect_output_order(self):
        shuffled = list(reversed(CONFIRMATION_TIME_ROWS))
        dim_rows = MODULE.dimension_rows(shuffled, "confirmation_time")
        assert [MODULE.row_value(r, "confirmation_time") for r in dim_rows] == [
            0, 1, 2, 3, 4,
        ]

    def test_all_seven_dimensions_place_canonical_by_true_value_not_position(self):
        for dimension_id, canonical_value in MODULE.CANONICAL_VALUE.items():
            rows = [
                {
                    "config_id": "baseline",
                    "dimension_id": "",
                    "overrides": "{}",
                    "tim_wrong_s": "0",
                    "tim_lost_s": "0",
                },
                {
                    "config_id": "perturbed_above",
                    "dimension_id": dimension_id,
                    "overrides": json.dumps({"x": canonical_value + 1}),
                    "tim_wrong_s": "0",
                    "tim_lost_s": "0",
                },
                {
                    "config_id": "perturbed_below",
                    "dimension_id": dimension_id,
                    "overrides": json.dumps({"x": canonical_value - 1}),
                    "tim_wrong_s": "0",
                    "tim_lost_s": "0",
                },
            ]
            ordered = MODULE.dimension_rows(rows, dimension_id)
            assert [r["config_id"] for r in ordered] == [
                "perturbed_below",
                "baseline",
                "perturbed_above",
            ], f"canonical not in true position for {dimension_id}"


class TestFigureGeneration:
    def test_expected_figures_are_generated(self, tmp_path, monkeypatch):
        agg_dir = tmp_path / "aggregate"
        agg_dir.mkdir()
        fig_dir = agg_dir / "figures"
        write_full_aggregate_csv(agg_dir / "matrix_aggregate.csv")
        monkeypatch.setattr(MODULE, "AGG_DIR", agg_dir)
        monkeypatch.setattr(MODULE, "FIG_DIR", fig_dir)

        assert MODULE.main() == 0

        combined = fig_dir / "p031_all_dimensions_wrong_lost.png"
        confirmation = fig_dir / "p031_confirmation_time_tradeoff.png"
        assert combined.is_file()
        assert confirmation.is_file()
        assert combined.stat().st_size > 0
        assert confirmation.stat().st_size > 0

    def test_missing_aggregate_input_fails_clearly(self, tmp_path, monkeypatch):
        agg_dir = tmp_path / "aggregate"
        agg_dir.mkdir()
        monkeypatch.setattr(MODULE, "AGG_DIR", agg_dir)
        monkeypatch.setattr(MODULE, "FIG_DIR", agg_dir / "figures")

        with pytest.raises(FileNotFoundError):
            MODULE.main()

    def test_empty_aggregate_csv_fails_clearly_not_silently(self, tmp_path, monkeypatch):
        agg_dir = tmp_path / "aggregate"
        agg_dir.mkdir()
        (agg_dir / "matrix_aggregate.csv").write_text(
            "config_id,dimension_id,overrides,tim_wrong_s,tim_lost_s\n"
        )
        monkeypatch.setattr(MODULE, "AGG_DIR", agg_dir)
        monkeypatch.setattr(MODULE, "FIG_DIR", agg_dir / "figures")

        with pytest.raises(StopIteration):
            MODULE.main()

    def test_plotting_does_not_mutate_aggregate_evidence(self, tmp_path, monkeypatch):
        agg_dir = tmp_path / "aggregate"
        agg_dir.mkdir()
        csv_path = agg_dir / "matrix_aggregate.csv"
        write_full_aggregate_csv(csv_path)
        before_bytes = csv_path.read_bytes()
        before_mtime = csv_path.stat().st_mtime_ns
        monkeypatch.setattr(MODULE, "AGG_DIR", agg_dir)
        monkeypatch.setattr(MODULE, "FIG_DIR", agg_dir / "figures")

        assert MODULE.main() == 0

        assert csv_path.read_bytes() == before_bytes
        assert csv_path.stat().st_mtime_ns == before_mtime

    def test_figures_are_deterministic_given_the_same_aggregate(
        self, tmp_path, monkeypatch
    ):
        agg_dir = tmp_path / "aggregate"
        agg_dir.mkdir()
        write_full_aggregate_csv(agg_dir / "matrix_aggregate.csv")
        fig_dir = agg_dir / "figures"
        monkeypatch.setattr(MODULE, "AGG_DIR", agg_dir)
        monkeypatch.setattr(MODULE, "FIG_DIR", fig_dir)

        assert MODULE.main() == 0
        first = (fig_dir / "p031_all_dimensions_wrong_lost.png").read_bytes()
        assert MODULE.main() == 0
        second = (fig_dir / "p031_all_dimensions_wrong_lost.png").read_bytes()
        assert first == second
