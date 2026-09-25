"""Three-flight opportunity markers retain operator timing without claiming outcomes."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "live/operator_event.py"
spec = importlib.util.spec_from_file_location("operator_event", MODULE_PATH)
assert spec and spec.loader
operator_event = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator_event)


@pytest.mark.parametrize(
    ("opportunity_id", "scenario"),
    [("O1", "right_loss"), ("O2", "left_loss"), ("O3", "distractor_loss")],
)
def test_opportunity_events_append_with_timebases_and_frozen_horizon(
    tmp_path, opportunity_id, scenario
):
    common = ["--run-id", "run_1", "--trial-id", "bcb_baseline_a",
              "--log-dir", str(tmp_path)]
    assert operator_event.main(
        ["opportunity_start", *common, "--opportunity-id", opportunity_id,
         "--scenario", scenario]
    ) == 0
    assert operator_event.main(
        ["opportunity_end", *common, "--opportunity-id", opportunity_id,
         "--outcome", "right_censored", "--note", "no return by horizon"]
    ) == 0
    path = tmp_path / "run_1/operator_events.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["event"] for r in records] == ["opportunity_start", "opportunity_end"]
    assert records[0]["detail"] == {
        "opportunity_id": opportunity_id, "scenario": scenario,
        "observation_horizon_s": 10.0,
    }
    assert records[1]["detail"]["outcome"] == "right_censored"
    assert "reacquisition_time_s" not in records[1]["detail"]
    for record in records:
        assert record["schema_version"] == 1
        assert record["trial_id"] == "bcb_baseline_a"
        assert record["ts_monotonic_ns"] > 0
        assert datetime.fromisoformat(record["ts_utc"].replace("Z", "+00:00"))
        assert operator_event.validate_event(record) == []


@pytest.mark.parametrize("outcome", operator_event.OPPORTUNITY_OUTCOMES)
def test_all_operator_outcomes_are_valid(tmp_path, outcome):
    assert operator_event.main(
        ["opportunity_end", "--run-id", "run_2", "--log-dir", str(tmp_path),
         "--opportunity-id", "O2", "--outcome", outcome]
    ) == 0


def test_mismatched_scenario_and_changed_horizon_are_rejected(tmp_path):
    common = ["opportunity_start", "--run-id", "run_3",
              "--log-dir", str(tmp_path), "--opportunity-id", "O1"]
    assert operator_event.main([*common, "--scenario", "left_loss"]) == 2
    assert operator_event.main(
        [*common, "--scenario", "right_loss", "--observation-horizon-s", "5"]
    ) == 2
    assert not (tmp_path / "run_3").exists()


def test_existing_schema_one_log_records_remain_valid():
    old = {
        "schema_version": 1, "event": "trial_start",
        "ts_utc": "2026-09-25T11:20:44Z", "run_id": "old",
        "detail": {"condition": "baseline", "scenario": "following"},
    }
    assert operator_event.validate_event(old) == []
