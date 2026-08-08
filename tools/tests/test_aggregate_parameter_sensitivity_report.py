"""Tests for the Issue #31 (P1.13) parameter-sensitivity aggregator.

These build small synthetic report.json fixtures -- not the real 116-cell
Pi dataset -- using the real frozen 29-configuration/7-dimension matrix
shape (id/dimension_id/order/overrides only, mirroring
docs/data/parameter_sensitivity/tim_mars_parameter_sensitivity_v1.yaml; not
experimental results), and monkeypatch the aggregator's path constants to
point at tmp_path. Tests never touch, depend on, or mutate the real
generated report or its promoted evidence in reports/ or docs/results/.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = REPO_ROOT / "tools" / "analysis"
AGGREGATOR_PATH = ANALYSIS_DIR / "aggregate_parameter_sensitivity_report.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("aggregate_parameter_sensitivity_report", AGGREGATOR_PATH)


# The frozen protocol's 29-configuration matrix shape (id/dimension_id/order/
# overrides only -- not experimental results), mirroring
# docs/data/parameter_sensitivity/tim_mars_parameter_sensitivity_v1.yaml.
REAL_CONFIGS = [
    {"id": "baseline", "dimension_id": None, "order": 0, "overrides": {}},
    {"id": "acceptance_pair_lower_2", "dimension_id": "acceptance_pair", "order": 1,
     "overrides": {"accept_score_locked": 0.42, "accept_score_lost": 0.5}},
    {"id": "acceptance_pair_lower_1", "dimension_id": "acceptance_pair", "order": 2,
     "overrides": {"accept_score_locked": 0.47, "accept_score_lost": 0.55}},
    {"id": "acceptance_pair_higher_1", "dimension_id": "acceptance_pair", "order": 3,
     "overrides": {"accept_score_locked": 0.57, "accept_score_lost": 0.65}},
    {"id": "acceptance_pair_higher_2", "dimension_id": "acceptance_pair", "order": 4,
     "overrides": {"accept_score_locked": 0.62, "accept_score_lost": 0.7}},
    {"id": "ambiguity_margin_lower_2", "dimension_id": "ambiguity_margin", "order": 5,
     "overrides": {"ambiguity_margin": 0.03}},
    {"id": "ambiguity_margin_lower_1", "dimension_id": "ambiguity_margin", "order": 6,
     "overrides": {"ambiguity_margin": 0.05}},
    {"id": "ambiguity_margin_higher_1", "dimension_id": "ambiguity_margin", "order": 7,
     "overrides": {"ambiguity_margin": 0.09}},
    {"id": "ambiguity_margin_higher_2", "dimension_id": "ambiguity_margin", "order": 8,
     "overrides": {"ambiguity_margin": 0.11}},
    {"id": "appearance_conservative_min_similarity_lower_2",
     "dimension_id": "appearance_conservative_min_similarity", "order": 9,
     "overrides": {"appearance_conservative_min_similarity": 0.55}},
    {"id": "appearance_conservative_min_similarity_lower_1",
     "dimension_id": "appearance_conservative_min_similarity", "order": 10,
     "overrides": {"appearance_conservative_min_similarity": 0.6}},
    {"id": "appearance_conservative_min_similarity_higher_1",
     "dimension_id": "appearance_conservative_min_similarity", "order": 11,
     "overrides": {"appearance_conservative_min_similarity": 0.7}},
    {"id": "appearance_conservative_min_similarity_higher_2",
     "dimension_id": "appearance_conservative_min_similarity", "order": 12,
     "overrides": {"appearance_conservative_min_similarity": 0.75}},
    {"id": "appearance_conservative_margin_lower_2",
     "dimension_id": "appearance_conservative_margin", "order": 13,
     "overrides": {"appearance_conservative_margin": 0.01}},
    {"id": "appearance_conservative_margin_lower_1",
     "dimension_id": "appearance_conservative_margin", "order": 14,
     "overrides": {"appearance_conservative_margin": 0.03}},
    {"id": "appearance_conservative_margin_higher_1",
     "dimension_id": "appearance_conservative_margin", "order": 15,
     "overrides": {"appearance_conservative_margin": 0.07}},
    {"id": "appearance_conservative_margin_higher_2",
     "dimension_id": "appearance_conservative_margin", "order": 16,
     "overrides": {"appearance_conservative_margin": 0.09}},
    {"id": "hard_negative_reject_similarity_lower_2",
     "dimension_id": "hard_negative_reject_similarity", "order": 17,
     "overrides": {"hard_negative_reject_similarity": 0.7}},
    {"id": "hard_negative_reject_similarity_lower_1",
     "dimension_id": "hard_negative_reject_similarity", "order": 18,
     "overrides": {"hard_negative_reject_similarity": 0.75}},
    {"id": "hard_negative_reject_similarity_higher_1",
     "dimension_id": "hard_negative_reject_similarity", "order": 19,
     "overrides": {"hard_negative_reject_similarity": 0.85}},
    {"id": "hard_negative_reject_similarity_higher_2",
     "dimension_id": "hard_negative_reject_similarity", "order": 20,
     "overrides": {"hard_negative_reject_similarity": 0.9}},
    {"id": "hard_negative_reject_margin_lower_2",
     "dimension_id": "hard_negative_reject_margin", "order": 21,
     "overrides": {"hard_negative_reject_margin": 0.0}},
    {"id": "hard_negative_reject_margin_lower_1",
     "dimension_id": "hard_negative_reject_margin", "order": 22,
     "overrides": {"hard_negative_reject_margin": 0.015}},
    {"id": "hard_negative_reject_margin_higher_1",
     "dimension_id": "hard_negative_reject_margin", "order": 23,
     "overrides": {"hard_negative_reject_margin": 0.045}},
    {"id": "hard_negative_reject_margin_higher_2",
     "dimension_id": "hard_negative_reject_margin", "order": 24,
     "overrides": {"hard_negative_reject_margin": 0.06}},
    {"id": "confirmation_time_lower_1", "dimension_id": "confirmation_time", "order": 25,
     "overrides": {"min_confirm_frames_after_reacquire": 0}},
    {"id": "confirmation_time_higher_1", "dimension_id": "confirmation_time", "order": 26,
     "overrides": {"min_confirm_frames_after_reacquire": 2}},
    {"id": "confirmation_time_higher_2", "dimension_id": "confirmation_time", "order": 27,
     "overrides": {"min_confirm_frames_after_reacquire": 3}},
    {"id": "confirmation_time_higher_3", "dimension_id": "confirmation_time", "order": 28,
     "overrides": {"min_confirm_frames_after_reacquire": 4}},
]

SEQUENCES = ["seqA", "seqB", "seqC", "seqD"]

assert len(REAL_CONFIGS) == 29
assert {c["dimension_id"] for c in REAL_CONFIGS if c["dimension_id"]} == set(
    MODULE.DIMENSION_ORDER
)


def make_report(
    *,
    raw_correct: float,
    raw_wrong: float,
    raw_lost: float,
    tim_correct: float,
    tim_wrong: float,
    tim_lost: float,
    tim_absent: float = 0.0,
    tim_noselect: float = 0.0,
) -> dict:
    raw_total = raw_correct + raw_wrong + raw_lost
    tim_total = tim_correct + tim_wrong + tim_lost + tim_absent + tim_noselect

    def stream(correct, wrong, lost, absent, noselect, total):
        return {
            "correct_target_duration_s": correct,
            "wrong_target_duration_s": wrong,
            "lost_target_duration_s": lost,
            "target_absent_but_output_valid_duration_s": absent,
            "no_target_selected_duration_s": noselect,
            "correct_target_ratio": correct / total if total else 0.0,
            "wrong_target_ratio": wrong / total if total else 0.0,
            "lost_target_ratio": lost / total if total else 0.0,
        }

    return {
        "duration_metrics": {
            "raw_target": stream(raw_correct, raw_wrong, raw_lost, 0.0, 0.0, raw_total),
            "tim_target_memory": stream(
                tim_correct, tim_wrong, tim_lost, tim_absent, tim_noselect, tim_total
            ),
        },
        "episode_metrics": {
            "tim_target_memory": {
                "wrong_target_burst_count": 1,
                "wrong_handover_count": 0,
                "longest_wrong_target_burst_s": tim_wrong,
            }
        },
        "status_recovery_metrics": {
            "recovery_attempt_count": 1,
            "correct_candidate_suppressed_duration_s": 0.0,
        },
        "memory_event_metrics": {
            "hard_negative_contamination_count": 0,
            "positive_memory_contamination_count": 0,
            "total_memory_contamination_count": 0,
        },
    }


def tim_wrong_for(sequence_index: int, config: dict) -> float:
    """Deterministic, hand-computable synthetic wrong-target value.

    Flat across every non-confirmation_time dimension (matching the real
    observed pattern where most dimensions show zero effect), with a known
    per-cell offset for confirmation_time so deltas can be asserted exactly.
    """
    base = 10.0 * sequence_index
    if config["dimension_id"] == "confirmation_time":
        value = config["overrides"]["min_confirm_frames_after_reacquire"]
        return base + (4 - value) * 0.5
    return base


def tim_lost_for(sequence_index: int, config: dict) -> float:
    base = 100.0 + 10.0 * sequence_index
    if config["dimension_id"] == "confirmation_time":
        value = config["overrides"]["min_confirm_frames_after_reacquire"]
        return base + value * 0.5
    return base


def build_dataset(tmp_path: Path, sequences=SEQUENCES, configs=REAL_CONFIGS):
    seq_dir = tmp_path / "sequences"
    for seq_index, sequence_id in enumerate(sequences):
        raw_correct = 50.0
        raw_wrong = 5.0 * seq_index
        raw_lost = 20.0
        for config in configs:
            tim_wrong = tim_wrong_for(seq_index, config)
            tim_lost = tim_lost_for(seq_index, config)
            tim_correct = 200.0 - tim_wrong - tim_lost
            report = make_report(
                raw_correct=raw_correct,
                raw_wrong=raw_wrong,
                raw_lost=raw_lost,
                tim_correct=tim_correct,
                tim_wrong=tim_wrong,
                tim_lost=tim_lost,
            )
            cell_dir = seq_dir / sequence_id / config["id"]
            cell_dir.mkdir(parents=True)
            (cell_dir / "report.json").write_text(json.dumps(report))

    lock = {
        "development_sequence_ids": list(sequences),
        "materialized_configs": configs,
    }
    lock_path = tmp_path / "parameter_sensitivity_lock.json"
    lock_path.write_text(json.dumps(lock))
    return seq_dir, lock_path


@pytest.fixture()
def dataset(tmp_path, monkeypatch):
    seq_dir, lock_path = build_dataset(tmp_path)
    out_dir = tmp_path / "aggregate"
    monkeypatch.setattr(MODULE, "SEQ_DIR", seq_dir)
    monkeypatch.setattr(MODULE, "LOCK_PATH", lock_path)
    monkeypatch.setattr(MODULE, "OUT_DIR", out_dir)
    return {"seq_dir": seq_dir, "lock_path": lock_path, "out_dir": out_dir}


class TestAccounting:
    def test_complete_116_cell_accounting_is_accepted(self, dataset, capsys):
        assert MODULE.main() == 0
        out = capsys.readouterr().out
        assert "116 cells" in out

        all_rows = json.loads(
            (dataset["out_dir"] / "matrix_all_sequences.json").read_text()
        )
        assert len(all_rows) == 116
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        assert len(agg_rows) == 29

    def test_missing_cell_fails_closed(self, dataset):
        (dataset["seq_dir"] / "seqA" / "baseline" / "report.json").unlink()

        assert MODULE.main() == 1
        assert not (dataset["out_dir"] / "matrix_all_sequences.csv").exists()

    def test_unexpected_cell_is_rejected_not_silently_pooled(self, dataset):
        stray_dir = dataset["seq_dir"] / "seqA" / "not_a_frozen_configuration"
        stray_dir.mkdir(parents=True)
        report = make_report(
            raw_correct=1, raw_wrong=1, raw_lost=1,
            tim_correct=1, tim_wrong=1, tim_lost=1,
        )
        (stray_dir / "report.json").write_text(json.dumps(report))

        assert MODULE.main() == 1
        assert not (dataset["out_dir"] / "matrix_all_sequences.csv").exists()

    def test_all_seven_dimensions_represented(self, dataset):
        assert MODULE.main() == 0
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        dims = {r["dimension_id"] for r in agg_rows if r["dimension_id"]}
        assert dims == set(MODULE.DIMENSION_ORDER)
        assert len(dims) == 7


class TestCanonicalBaseline:
    def test_baseline_identified_exactly_once_with_no_dimension(self, dataset):
        assert MODULE.main() == 0
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        baseline_rows = [r for r in agg_rows if r["config_id"] == "baseline"]
        assert len(baseline_rows) == 1
        assert baseline_rows[0]["dimension_id"] is None

    def test_baseline_appears_once_per_dimension_in_dimension_table(self, dataset):
        assert MODULE.main() == 0
        dim_rows = json.loads(
            (dataset["out_dir"] / "dimension_tradeoff.json").read_text()
        )
        assert len(dim_rows) == 35
        canonical_rows = [r for r in dim_rows if r["is_canonical"]]
        assert len(canonical_rows) == 7
        assert {r["dimension_id"] for r in canonical_rows} == set(
            MODULE.DIMENSION_ORDER
        )
        assert all(r["config_id"] == "baseline" for r in canonical_rows)


class TestBaselineRelativeDeltas:
    def test_within_sequence_deltas_are_exact_for_flat_dimensions(self, dataset):
        assert MODULE.main() == 0
        all_rows = json.loads(
            (dataset["out_dir"] / "matrix_all_sequences.json").read_text()
        )
        flat_rows = [
            r for r in all_rows if r["dimension_id"] not in (None, "confirmation_time")
        ]
        assert flat_rows
        for row in flat_rows:
            assert row["delta_wrong_s_vs_baseline"] == pytest.approx(0.0)
            assert row["delta_lost_s_vs_baseline"] == pytest.approx(0.0)

    def test_aggregate_deltas_match_hand_computed_values(self, dataset):
        assert MODULE.main() == 0
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        by_id = {r["config_id"]: r for r in agg_rows}
        # Per-cell offset (base + (4 - value) * 0.5) minus baseline's flat
        # `base`, summed over the 4 synthetic sequences (offset is
        # sequence-index-independent, so aggregate = 4 * per-cell offset).
        assert by_id["confirmation_time_lower_1"][
            "delta_wrong_s_vs_baseline"
        ] == pytest.approx(4 * 2.0)
        assert by_id["confirmation_time_higher_1"][
            "delta_wrong_s_vs_baseline"
        ] == pytest.approx(4 * 1.0)
        assert by_id["confirmation_time_higher_2"][
            "delta_wrong_s_vs_baseline"
        ] == pytest.approx(4 * 0.5)
        assert by_id["confirmation_time_higher_3"][
            "delta_wrong_s_vs_baseline"
        ] == pytest.approx(0.0)


class TestPerSequenceVsPooled:
    def test_per_sequence_rows_remain_distinguishable(self, dataset):
        assert MODULE.main() == 0
        all_rows = json.loads(
            (dataset["out_dir"] / "matrix_all_sequences.json").read_text()
        )
        baseline_rows = {
            r["sequence_id"]: r["tim_wrong_s"]
            for r in all_rows
            if r["config_id"] == "baseline"
        }
        assert baseline_rows == {"seqA": 0.0, "seqB": 10.0, "seqC": 20.0, "seqD": 30.0}

    def test_aggregate_pools_the_per_sequence_values(self, dataset):
        assert MODULE.main() == 0
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        baseline = next(r for r in agg_rows if r["config_id"] == "baseline")
        assert baseline["tim_wrong_s"] == pytest.approx(0.0 + 10.0 + 20.0 + 30.0)


class TestRawInvariance:
    def test_violation_is_surfaced_not_silently_ignored(self, dataset):
        drifted = make_report(
            raw_correct=999.0, raw_wrong=999.0, raw_lost=999.0,
            tim_correct=1.0, tim_wrong=1.0, tim_lost=1.0,
        )
        path = dataset["seq_dir"] / "seqA" / "ambiguity_margin_lower_2" / "report.json"
        path.write_text(json.dumps(drifted))

        with pytest.raises(ValueError, match="raw/ByteTrack reference stream changed"):
            MODULE.main()


class TestDeterminism:
    def test_output_ordering_is_deterministic_across_runs(self, dataset):
        assert MODULE.main() == 0
        first = (dataset["out_dir"] / "matrix_all_sequences.csv").read_bytes()
        assert MODULE.main() == 0
        second = (dataset["out_dir"] / "matrix_all_sequences.csv").read_bytes()
        assert first == second

    def test_confirmation_time_sorts_numerically_with_canonical_in_true_position(
        self, dataset
    ):
        assert MODULE.main() == 0
        dim_rows = json.loads(
            (dataset["out_dir"] / "dimension_tradeoff.json").read_text()
        )
        ct_rows = [r for r in dim_rows if r["dimension_id"] == "confirmation_time"]
        assert [r["value"] for r in ct_rows] == [0, 1, 2, 3, 4]
        assert [r["is_canonical"] for r in ct_rows] == [
            False, True, False, False, False,
        ]
        assert ct_rows[1]["config_id"] == "baseline"


class TestAccountingConsistency:
    def test_csv_and_json_agree(self, dataset):
        assert MODULE.main() == 0
        import csv

        with (dataset["out_dir"] / "matrix_aggregate.csv").open() as fh:
            csv_ids = [row["config_id"] for row in csv.DictReader(fh)]
        json_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        assert csv_ids == [r["config_id"] for r in json_rows]

    def test_tim_ratios_sum_to_one_when_no_absence_or_no_selection(self, dataset):
        assert MODULE.main() == 0
        agg_rows = json.loads(
            (dataset["out_dir"] / "matrix_aggregate.json").read_text()
        )
        for row in agg_rows:
            total_ratio = (
                row["tim_correct_ratio"] + row["tim_wrong_ratio"] + row["tim_lost_ratio"]
            )
            assert total_ratio == pytest.approx(1.0, abs=1e-3)
