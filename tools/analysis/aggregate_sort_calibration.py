"""Aggregate the Issue #58 SORT+TIM calibration sweep (29 cells, May only)
into one table the safety-gate selector can read.

Mirrors tools/analysis/aggregate_parameter_sensitivity_report.py's per-cell
extraction, simplified for a single sequence (no cross-sequence pooling).
Refuses to run if any of the 29 expected cells is missing.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "p058_sort_tim_calibration_6231fdc1_2026_08_08"
LOCK_PATH = REPORT_DIR / "sort_calibration_lock.json"
SEQ_DIR = REPORT_DIR / "sequences" / "dev_may_hard_reentry"
OUT_DIR = REPORT_DIR / "aggregate"

DURATION_FIELDS = [
    "correct_target_duration_s",
    "wrong_target_duration_s",
    "lost_target_duration_s",
    "target_absent_but_output_valid_duration_s",
    "no_target_selected_duration_s",
]


def duration_row(stream_metrics: dict[str, Any]) -> dict[str, float]:
    return {field: float(stream_metrics[field]) for field in DURATION_FIELDS}


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text())
    configs = lock["materialized_configs"]

    missing = [c["id"] for c in configs if not (SEQ_DIR / c["id"] / "report.json").is_file()]
    if missing:
        print(f"[error] {len(missing)} missing calibration cells, refusing to aggregate: {missing}")
        return 1

    rows: list[dict[str, Any]] = []
    reference_raw = None
    for config in configs:
        report = json.loads((SEQ_DIR / config["id"] / "report.json").read_text())
        raw_full = report["duration_metrics"]["raw_target"]
        raw = duration_row(raw_full)
        tim = duration_row(report["duration_metrics"]["tim_target_memory"])

        if reference_raw is None:
            reference_raw = raw_full
        elif raw_full != reference_raw:
            raise ValueError(
                f"raw/SORT reference stream changed at configuration "
                f"{config['id']}; this indicates a tooling or "
                "non-determinism bug, not new evidence"
            )

        rows.append(
            {
                "config_id": config["id"],
                "dimension_id": config["dimension_id"],
                "order": config["order"],
                "overrides": json.dumps(config["overrides"], sort_keys=True),
                "raw_correct_s": raw["correct_target_duration_s"],
                "raw_wrong_s": raw["wrong_target_duration_s"],
                "raw_lost_s": raw["lost_target_duration_s"],
                "raw_absent_valid_s": raw["target_absent_but_output_valid_duration_s"],
                "tim_correct_s": tim["correct_target_duration_s"],
                "tim_wrong_s": tim["wrong_target_duration_s"],
                "tim_lost_s": tim["lost_target_duration_s"],
                "tim_absent_valid_s": tim["target_absent_but_output_valid_duration_s"],
            }
        )

    baseline = next(r for r in rows if r["config_id"] == "baseline")
    for row in rows:
        row["delta_wrong_s_vs_baseline"] = round(row["tim_wrong_s"] - baseline["tim_wrong_s"], 3)
        row["delta_lost_s_vs_baseline"] = round(row["tim_lost_s"] - baseline["tim_lost_s"], 3)

    assert len(rows) == 29, f"expected 29 rows, got {len(rows)}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "calibration_aggregate.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (OUT_DIR / "calibration_aggregate.json").write_text(json.dumps(rows, indent=2) + "\n")

    print(f"[ok] aggregated 29 SORT+TIM calibration cells (dev_may_hard_reentry): {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
