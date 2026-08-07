#!/usr/bin/env python3
"""Aggregate oracle-candidate-mode results into one Issue #30 report.

Oracle-candidate mode (``tools/analysis/build_oracle_candidate_bag.py``)
replaces the detector and tracker with an idealized, ground-truth-derived
candidate stream, isolating TIM-MARS identity-memory and recovery behaviour
from detector/tracker candidate availability. It answers a different,
diagnostic question than the full detector-ByteTrack-TIM pipeline
(``aggregate_first_phase_report.py``): "when an appropriate target candidate
is available, how does TIM-MARS behave independently of detector/tracker
candidate availability?"

This script is intentionally kept separate from, and never merges its
counts into, the full-pipeline aggregate: the two evaluation modes measure
different things and must not be combined into one headline metric. Only
sequences whose frozen manifest entry both declares ``"oracle_candidate"``
in ``evaluation_modes`` and is not ``status: "excluded"`` are included --
this script does not invent an oracle protocol for sequences the manifest
does not already declare it for (currently: ``ros2_internal`` sequences have
no oracle contract at all, and DanceTrack/``uav0000268_05773_v`` are
excluded from the primary benchmark scope).

This script does not run anything itself beyond reading already-generated
report.json files (one per sequence, produced by
``run_external_sequence_report.py``'s ``build_report`` against an oracle
bag instead of a live capture bag). It is a read-only aggregation step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    ROOT / "docs" / "data" / "external_benchmark" / "sequence_manifest.json"
)
DEFAULT_ORACLE_REPORT_DIR = (
    ROOT
    / "artifacts"
    / "reports"
    / "p030_broader_sequences"
    / "oracle_frame_reports"
)


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def summarize_oracle_report(report_path: Path) -> dict[str, Any]:
    if not report_path.exists():
        return {"status": "missing_report", "path": str(report_path)}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["vocabulary"] = "frame_level_outcome_taxonomy"
    return report


def oracle_eligible(entry: dict[str, Any]) -> bool:
    return (
        "oracle_candidate" in entry.get("evaluation_modes", [])
        and entry.get("status") != "excluded"
    )


def build_oracle_aggregate(
    *,
    manifest_path: Path,
    oracle_report_dir: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)

    sequences: list[dict[str, Any]] = []
    skipped_sequences: list[dict[str, Any]] = []

    for entry in manifest["sequences"]:
        sequence_id = entry["id"]

        if not oracle_eligible(entry):
            skipped_sequences.append(
                {
                    "id": sequence_id,
                    "dataset": entry["dataset"],
                    "reason": (
                        "excluded_from_primary_scope"
                        if entry.get("status") == "excluded"
                        else "no_oracle_candidate_contract_declared"
                    ),
                }
            )
            continue

        report_path = oracle_report_dir / f"{sequence_id}.json"
        summary = summarize_oracle_report(report_path)

        sequences.append(
            {
                "id": sequence_id,
                "dataset": entry["dataset"],
                "sequence_name": entry["sequence_name"],
                "report": summary,
            }
        )

    evaluated = [
        s for s in sequences if s["report"].get("status") == "evaluated"
    ]
    init_failures = [
        s
        for s in sequences
        if s["report"].get("status") == "initialization_failure"
    ]
    missing = [
        s
        for s in sequences
        if s["report"].get("status")
        not in ("evaluated", "initialization_failure")
    ]

    return {
        "evaluation_mode": "oracle_candidate",
        "manifest_status": manifest["status"],
        "manifest_frozen_date": manifest.get("frozen_date"),
        "total_sequences": len(sequences),
        "evaluated_count": len(evaluated),
        "initialization_failure_count": len(init_failures),
        "missing_report_count": len(missing),
        "sequences": sequences,
        "skipped_sequences": skipped_sequences,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--oracle-report-dir",
        type=Path,
        default=DEFAULT_ORACLE_REPORT_DIR,
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    aggregate = build_oracle_aggregate(
        manifest_path=arguments.manifest,
        oracle_report_dir=arguments.oracle_report_dir,
    )

    rendered = json.dumps(aggregate, indent=2, default=str)

    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
