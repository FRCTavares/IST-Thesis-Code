#!/usr/bin/env python3
"""Aggregate and classify the ByteTrack / TIM-MARS configuration sensitivity
experiment.

Reads ``cells.json`` from a run report directory and produces:

* ``comparison_by_sequence.csv`` / ``.json`` -- each candidate vs the freshly
  rerun canonical baseline, per sequence;
* ``repeatability.json`` -- exact-equality check of the canonical baseline
  repeats against the primary baseline cell;
* ``classification.json`` -- improved / neutral / regressed / unsafe_regression
  per (candidate, sequence) and per candidate, using the thesis safety
  ordering correct_target > lost/hover > wrong_target;
* ``report.md`` -- the human-readable scientific summary.

No canonical configuration is modified. This script only reads a completed
run and writes analysis artifacts alongside it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASELINE_ID = "canonical_baseline"

# Evaluator-precision tolerances.
WRONG_TOL_S = 0.05      # asymmetric safety tolerance, matches prior Issue #58 work
MEANINGFUL_CORRECT_S = 0.5
MEANINGFUL_LOST_S = 0.5


def bucket(cell: dict, stream: str, key: str) -> float | None:
    try:
        return float(cell["physical_v2"][stream]["duration_buckets"][key])
    except (KeyError, TypeError):
        return None


def classify(d_correct: float, d_wrong: float, d_lost: float,
             d_absent_output: float, is_regression_gate: bool,
             bootstrap_ok: bool) -> tuple[str, str]:
    if not bootstrap_ok:
        return "bootstrap_failure", "no track reached the physical-target bootstrap IoU threshold"
    reasons = []
    if d_wrong > WRONG_TOL_S or d_absent_output > WRONG_TOL_S:
        reasons.append(
            f"increases wrong-target authority by {d_wrong:+.3f} s"
            + (f" and absent-with-output by {d_absent_output:+.3f} s" if d_absent_output > WRONG_TOL_S else "")
        )
        return "unsafe_regression", "; ".join(reasons)
    if is_regression_gate and (d_correct < -MEANINGFUL_CORRECT_S or d_wrong > WRONG_TOL_S):
        return "regressed", f"degrades the clean regression-gate sequence (dcorrect {d_correct:+.3f} s)"
    if d_correct >= MEANINGFUL_CORRECT_S and d_wrong <= WRONG_TOL_S:
        return "improved", f"gains {d_correct:+.3f} s correct-target output with no wrong-target increase"
    if d_correct <= -MEANINGFUL_CORRECT_S:
        return "regressed", f"loses {d_correct:+.3f} s correct-target output"
    return "neutral", f"within evaluator precision (dcorrect {d_correct:+.3f} s, dwrong {d_wrong:+.3f} s)"


def repeatability(cells: list[dict]) -> dict:
    by_key: dict[tuple[str, str, object], dict] = {}
    for cell in cells:
        by_key[(cell["sequence_id"], cell["config_id"], cell.get("repeat_index"))] = cell

    checks = []
    ok_all = True
    for (seq, config_id, repeat_index), cell in sorted(by_key.items(), key=lambda kv: str(kv[0])):
        if config_id != BASELINE_ID or repeat_index is None:
            continue
        primary = by_key.get((seq, BASELINE_ID, None))
        if primary is None:
            continue
        fields = {
            "tracker_generated_digest": (primary.get("tracker_generated_digest"), cell.get("tracker_generated_digest")),
            "bootstrap_track_id": (
                primary.get("bootstrap", {}).get("resolved_track_id"),
                cell.get("bootstrap", {}).get("resolved_track_id"),
            ),
            "tim_generated_digest": (primary.get("tim_generated_digest"), cell.get("tim_generated_digest")),
            "tim_correct_s": (
                bucket(primary, "tim_target_memory", "correct_target_output_duration_s"),
                bucket(cell, "tim_target_memory", "correct_target_output_duration_s"),
            ),
            "tim_wrong_s": (
                bucket(primary, "tim_target_memory", "wrong_person_output_duration_s"),
                bucket(cell, "tim_target_memory", "wrong_person_output_duration_s"),
            ),
            "tim_lost_s": (
                bucket(primary, "tim_target_memory", "lost_or_suppressed_duration_s"),
                bucket(cell, "tim_target_memory", "lost_or_suppressed_duration_s"),
            ),
            "state_occupancy_fraction": (
                primary.get("tim_state_occupancy", {}).get("state_occupancy_fraction"),
                cell.get("tim_state_occupancy", {}).get("state_occupancy_fraction"),
            ),
        }
        mismatches = {k: v for k, v in fields.items() if v[0] != v[1]}
        passed = not mismatches
        ok_all = ok_all and passed
        checks.append(
            {
                "sequence_id": seq,
                "repeat_index": repeat_index,
                "passed": passed,
                "mismatches": mismatches,
            }
        )
    return {"deterministic": ok_all, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_root", type=Path)
    args = parser.parse_args()

    cells = json.loads((args.report_root / "cells.json").read_text())
    lock = json.loads((args.report_root / "manifest_lock.json").read_text())
    config_order = [c["id"] for c in lock["configurations"]]
    overrides_by_id = {c["id"]: c["overrides"] for c in lock["configurations"]}

    primary = {
        (c["sequence_id"], c["config_id"]): c
        for c in cells
        if c.get("repeat_index") is None
    }
    sequences = [s for s in dict.fromkeys(c["sequence_id"] for c in cells)]
    gate_sequences = {"dev_june_seq01"}

    rows = []
    classification = {}
    for config_id in config_order:
        if config_id == BASELINE_ID:
            continue
        per_seq = {}
        for seq in sequences:
            base = primary.get((seq, BASELINE_ID))
            cand = primary.get((seq, config_id))
            if base is None or cand is None:
                continue
            bc = bucket(base, "tim_target_memory", "correct_target_output_duration_s") or 0.0
            bw = bucket(base, "tim_target_memory", "wrong_person_output_duration_s") or 0.0
            bl = bucket(base, "tim_target_memory", "lost_or_suppressed_duration_s") or 0.0
            ba = bucket(base, "tim_target_memory", "target_absent_with_output_duration_s") or 0.0
            cc = bucket(cand, "tim_target_memory", "correct_target_output_duration_s")
            cw = bucket(cand, "tim_target_memory", "wrong_person_output_duration_s")
            cl = bucket(cand, "tim_target_memory", "lost_or_suppressed_duration_s")
            ca = bucket(cand, "tim_target_memory", "target_absent_with_output_duration_s")
            boot_ok = cand.get("bootstrap", {}).get("ok", False)
            if cc is None:
                verdict, reason = ("bootstrap_failure" if not boot_ok else "evaluation_incomplete",
                                   cand.get("status", "no result"))
                dc = dw = dl = da = None
            else:
                dc, dw, dl, da = cc - bc, cw - bw, cl - bl, ca - ba
                verdict, reason = classify(dc, dw, dl, da, seq in gate_sequences, boot_ok)
            per_seq[seq] = verdict
            rows.append(
                {
                    "config_id": config_id,
                    "overrides": json.dumps(overrides_by_id[config_id]),
                    "sequence_id": seq,
                    "baseline_correct_s": bc, "candidate_correct_s": cc, "delta_correct_s": dc,
                    "baseline_wrong_s": bw, "candidate_wrong_s": cw, "delta_wrong_s": dw,
                    "baseline_lost_s": bl, "candidate_lost_s": cl, "delta_lost_s": dl,
                    "delta_absent_with_output_s": da,
                    "candidate_bootstrap_id": cand.get("bootstrap", {}).get("resolved_track_id"),
                    "candidate_bootstrap_iou": cand.get("bootstrap", {}).get("bootstrap_iou"),
                    "verdict": verdict,
                    "reason": reason,
                }
            )
        verdicts = set(per_seq.values())
        if "unsafe_regression" in verdicts:
            overall = "unsafe_regression"
        elif "regressed" in verdicts:
            overall = "regressed"
        elif "bootstrap_failure" in verdicts:
            overall = "regressed"
        elif verdicts == {"neutral"} or not verdicts:
            overall = "neutral"
        elif "improved" in verdicts and verdicts <= {"improved", "neutral"}:
            overall = "improved"
        else:
            overall = "mixed"
        classification[config_id] = {"overall": overall, "per_sequence": per_seq}

    _write_csv(args.report_root / "comparison_by_sequence.csv", rows)
    (args.report_root / "comparison_by_sequence.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n"
    )
    rep = repeatability(cells)
    (args.report_root / "repeatability.json").write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    (args.report_root / "classification.json").write_text(
        json.dumps(classification, indent=2, sort_keys=True) + "\n"
    )

    _write_markdown(args.report_root, cells, lock, rows, classification, rep, sequences, config_order, overrides_by_id, primary)
    print(f"[ok] aggregation written -> {args.report_root}")
    return 0


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    cols = list(rows[0].keys())
    out = [",".join(cols)]
    for row in rows:
        out.append(",".join("" if row.get(c) is None else str(row.get(c)) for c in cols))
    path.write_text("\n".join(out) + "\n")


def _fmt(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _write_markdown(report_root, cells, lock, rows, classification, rep, sequences,
                    config_order, overrides_by_id, primary) -> None:
    lines: list[str] = []
    A = lines.append
    A("# ByteTrack configuration sensitivity for downstream TIM-MARS")
    A("")
    A("Development-only OFAT screening. No canonical configuration was changed. "
      "This is a recommendation-only experiment.")
    A("")
    A("## Provenance")
    A("")
    A(f"- manifest: `{lock['manifest_path']}` (sha256 `{lock['manifest_sha256']}`)")
    A(f"- canonical ByteTrack config sha256: `{lock['canonical_tracker_config']['sha256']}`")
    A(f"- TIM-MARS config sha256: `{lock['tim_mars_config']['sha256']}`")
    A(f"- repo commit at materialization: `{lock['repo_commit']}`")
    A("")
    A("## Canonical baseline physical-v2 (freshly rerun through this harness)")
    A("")
    A("| Sequence | Correct (s) | Wrong (s) | Lost (s) | Absent-with-output (s) | IoU wmean |")
    A("| --- | ---: | ---: | ---: | ---: | ---: |")
    for seq in sequences:
        base = primary.get((seq, BASELINE_ID))
        if not base:
            continue
        db = base["physical_v2"]["tim_target_memory"]["duration_buckets"]
        loc = base["physical_v2"]["tim_target_memory"].get("localisation", {})
        A(f"| {seq} | {_fmt(db['correct_target_output_duration_s'])} | "
          f"{_fmt(db['wrong_person_output_duration_s'])} | "
          f"{_fmt(db['lost_or_suppressed_duration_s'])} | "
          f"{_fmt(db['target_absent_with_output_duration_s'])} | "
          f"{_fmt(loc.get('iou_duration_weighted_mean'))} |")
    A("")
    A("## Repeatability")
    A("")
    A(f"Deterministic: **{'PASS' if rep['deterministic'] else 'FAIL'}** "
      f"({len(rep['checks'])} baseline repeat checks).")
    if not rep["deterministic"]:
        for check in rep["checks"]:
            if not check["passed"]:
                A(f"- {check['sequence_id']} r{check['repeat_index']}: mismatches {list(check['mismatches'])}")
    A("")
    A("## Candidate vs baseline (TIM-MARS physical-v2)")
    A("")
    A("| Config | Overrides | Sequence | dCorrect (s) | dWrong (s) | dLost (s) | Verdict |")
    A("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in rows:
        A(f"| {row['config_id']} | {row['overrides']} | {row['sequence_id']} | "
          f"{_fmt(row['delta_correct_s'])} | {_fmt(row['delta_wrong_s'])} | "
          f"{_fmt(row['delta_lost_s'])} | {row['verdict']} |")
    A("")
    A("## Overall candidate classification")
    A("")
    A("| Config | Overrides | Overall | Per-sequence |")
    A("| --- | --- | --- | --- |")
    for config_id in config_order:
        if config_id == BASELINE_ID or config_id not in classification:
            continue
        entry = classification[config_id]
        per = ", ".join(f"{k}:{v}" for k, v in entry["per_sequence"].items())
        A(f"| {config_id} | {json.dumps(overrides_by_id[config_id])} | **{entry['overall']}** | {per} |")
    A("")
    A("## Raw ByteTrack diagnostics (identity-independent)")
    A("")
    A("| Sequence | Config | Target ID switches | Fragments | Visible coverage | Tracks matching target (mean) | False continuation in absence (s) |")
    A("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for cell in sorted(cells, key=lambda c: (c["sequence_id"], c["config_id"], str(c.get("repeat_index")))):
        if cell.get("repeat_index") is not None:
            continue
        cont = cell.get("raw_tracker_continuity", {})
        A(f"| {cell['sequence_id']} | {cell['config_id']} | "
          f"{_fmt(cont.get('target_id_switch_count'))} | {_fmt(cont.get('target_track_fragment_count'))} | "
          f"{_fmt(cont.get('target_visible_coverage_fraction'))} | "
          f"{_fmt(cont.get('tracks_matching_target_mean'))} | "
          f"{_fmt(cont.get('false_continuation_during_absence_s'))} |")
    A("")
    (report_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
