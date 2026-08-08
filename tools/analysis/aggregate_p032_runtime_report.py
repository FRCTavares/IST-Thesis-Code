#!/usr/bin/env python3
"""Aggregate Issue #32 runtime/resource evidence into the Issue #58 join schema.

Reads the replay_algorithmic_cost evidence produced per architecture by
tools/experiments/measure_p032_replay_cost.py (and, where present, the
live_sustained evidence produced by
tools/experiments/run_p032_sustained_ground_run.sh /
tools/analysis/analyze_p032_sustained_run.py) and builds one row per
(architecture_id, sequence_id) using exactly Issue #58's architecture and
sequence identifiers, so the two issues can be joined without rerunning or
manually re-interpreting either one's logs.

Unavailable measurements are recorded as null with an explicit reason, never
as zero. Every metric group carries a `source` field distinguishing
`replay_algorithmic_cost` from `live_sustained` so a reader cannot mistake a
deterministic-replay CPU total for a live wall-clock latency claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = "p032_runtime_characterization_report_v1"

NOT_MEASURED_LIVE = "not_measured_live_this_session"
NOT_APPLICABLE_TIM_DISABLED = "not_applicable_tim_disabled"


def load_manifest(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_replay_row(
    architecture: dict[str, Any],
    sequence_id: str,
    replay_dir: Path,
) -> dict[str, Any]:
    tracker_path = replay_dir / "replay_cost_tracker.json"
    tracker = read_json_optional(tracker_path)

    if tracker is None:
        return {
            "source": "replay_algorithmic_cost",
            "status": "missing",
            "reason": f"expected file not found: {tracker_path}",
        }

    row: dict[str, Any] = {
        "source": "replay_algorithmic_cost",
        "status": "measured",
        "tracker": {
            "wall_s": tracker["wall_s"],
            "user_cpu_s": tracker["user_cpu_s"],
            "sys_cpu_s": tracker["sys_cpu_s"],
            "total_cpu_s": tracker["total_cpu_s"],
            "peak_rss_kib": tracker["peak_rss_kib"],
            "frame_count": tracker["frame_count"],
            "mean_cpu_ms_per_frame": tracker["mean_cpu_ms_per_frame"],
        },
        "provenance": tracker["provenance"],
    }

    if not architecture.get("tim_enabled"):
        row["tim"] = {
            "status": NOT_APPLICABLE_TIM_DISABLED,
        }
        row["combined_total_cpu_s"] = tracker["total_cpu_s"]
        row["combined_peak_rss_kib"] = tracker["peak_rss_kib"]
        return row

    tim_path = replay_dir / "replay_cost_tim.json"
    tim = read_json_optional(tim_path)

    if tim is None:
        row["tim"] = {
            "status": "missing",
            "reason": f"expected file not found: {tim_path}",
        }
        row["combined_total_cpu_s"] = None
        row["combined_peak_rss_kib"] = None
        return row

    appearance_path = Path(tim["appearance_budget_json"])
    appearance = read_json_optional(appearance_path)

    row["tim"] = {
        "status": "measured",
        "wall_s": tim["wall_s"],
        "user_cpu_s": tim["user_cpu_s"],
        "sys_cpu_s": tim["sys_cpu_s"],
        "total_cpu_s": tim["total_cpu_s"],
        "peak_rss_kib": tim["peak_rss_kib"],
        "appearance_budget": appearance,
        "provenance": tim["provenance"],
    }
    row["combined_total_cpu_s"] = (
        tracker["total_cpu_s"] + tim["total_cpu_s"]
    )
    row["combined_peak_rss_kib"] = max(
        tracker["peak_rss_kib"], tim["peak_rss_kib"]
    )
    return row


def build_live_row(live_analysis_path: Path | None) -> dict[str, Any]:
    if live_analysis_path is None:
        return {
            "source": "live_sustained",
            "status": NOT_MEASURED_LIVE,
        }

    analysis = read_json_optional(live_analysis_path)

    if analysis is None:
        return {
            "source": "live_sustained",
            "status": "missing",
            "reason": f"expected file not found: {live_analysis_path}",
        }

    timing = analysis.get("timing", {})
    metrics = timing.get("metrics", {})

    return {
        "source": "live_sustained",
        "status": "measured" if analysis.get("passed") else "measured_with_violations",
        "violations": analysis.get("violations", []),
        "duration_s": analysis.get("observed_duration_s"),
        "warm_up_s": analysis.get("warm_up_s"),
        "latency_ms": {
            "e2e_det": metrics.get("/timing", {}).get("e2e_det_ms"),
            "pub_dt": metrics.get("/timing", {}).get("pub_dt_ms"),
            "track": metrics.get("/timing_tracker", {}).get("track_ms"),
            "e2e_target": metrics.get("/timing_target", {}).get(
                "e2e_target_ms"
            ),
        },
        "cadence_consistency": timing.get("cadence_consistency"),
        "resources": analysis.get("windows", {}).get("resources"),
        "health": analysis.get("windows", {}).get("health"),
        "claim_boundary": analysis.get("claim_boundary"),
        "report_path": str(live_analysis_path),
    }


def comparative_overhead(rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Delta of TIM-enabled vs raw pairing, per tracker type, replay mode only."""
    pairs = [
        ("bytetrack_raw", "bytetrack_tim", "bytetrack"),
        ("sort_raw", "sort_tim", "sort"),
        ("deepsort_raw", "deepsort_tim", "deepsort"),
    ]

    output = []

    for raw_id, tim_id, tracker_type in pairs:
        raw_replay = rows.get(raw_id, {}).get("replay", {})
        tim_replay = rows.get(tim_id, {}).get("replay", {})

        raw_total = raw_replay.get("combined_total_cpu_s")
        tim_total = tim_replay.get("combined_total_cpu_s")
        raw_rss = raw_replay.get("combined_peak_rss_kib")
        tim_rss = tim_replay.get("combined_peak_rss_kib")

        output.append(
            {
                "tracker_type": tracker_type,
                "raw_architecture_id": raw_id,
                "tim_architecture_id": tim_id,
                "source": "replay_algorithmic_cost",
                "delta_total_cpu_s": (
                    (tim_total - raw_total)
                    if raw_total is not None and tim_total is not None
                    else None
                ),
                "delta_peak_rss_kib": (
                    (tim_rss - raw_rss)
                    if raw_rss is not None and tim_rss is not None
                    else None
                ),
            }
        )

    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "architecture_id",
        "sequence_id",
        "tracker_type",
        "tim_enabled",
        "replay_tracker_total_cpu_s",
        "replay_tracker_peak_rss_kib",
        "replay_tim_total_cpu_s",
        "replay_tim_peak_rss_kib",
        "replay_combined_total_cpu_s",
        "replay_combined_peak_rss_kib",
        "live_status",
        "live_e2e_det_p95_ms",
        "live_e2e_target_p95_ms",
    ]

    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            replay = row["replay"]
            live = row["live"]
            tracker = replay.get("tracker", {})
            tim = replay.get("tim", {})
            live_latency = live.get("latency_ms", {})
            e2e_det = live_latency.get("e2e_det") or {}
            e2e_target = live_latency.get("e2e_target") or {}

            writer.writerow(
                {
                    "architecture_id": row["architecture_id"],
                    "sequence_id": row["sequence_id"],
                    "tracker_type": row["tracker_type"],
                    "tim_enabled": row["tim_enabled"],
                    "replay_tracker_total_cpu_s": tracker.get(
                        "total_cpu_s"
                    ),
                    "replay_tracker_peak_rss_kib": tracker.get(
                        "peak_rss_kib"
                    ),
                    "replay_tim_total_cpu_s": tim.get("total_cpu_s"),
                    "replay_tim_peak_rss_kib": tim.get("peak_rss_kib"),
                    "replay_combined_total_cpu_s": replay.get(
                        "combined_total_cpu_s"
                    ),
                    "replay_combined_peak_rss_kib": replay.get(
                        "combined_peak_rss_kib"
                    ),
                    "live_status": live.get("status"),
                    "live_e2e_det_p95_ms": e2e_det.get("p95"),
                    "live_e2e_target_p95_ms": e2e_target.get("p95"),
                }
            )


def render_markdown(rows: list[dict[str, Any]], overhead: list[dict[str, Any]]) -> str:
    lines = [
        "# Issue #32 Runtime/Resource Characterization -- Aggregate",
        "",
        "## Replay algorithmic-cost pass (deterministic, non-real-time; "
        "not a live latency claim)",
        "",
        "| Architecture | Sequence | Tracker CPU (s) | TIM CPU (s) | "
        "Combined CPU (s) | Peak RSS (KiB) | Live status |",
        "|---|---|---:|---:|---:|---:|---|",
    ]

    for row in rows:
        replay = row["replay"]
        tracker = replay.get("tracker", {})
        tim = replay.get("tim", {})
        tracker_cpu = tracker.get("total_cpu_s")
        tim_cpu = tim.get("total_cpu_s")

        lines.append(
            "| {arch} | {seq} | {tcpu} | {timcpu} | {combined} | {rss} | {live} |".format(
                arch=row["architecture_id"],
                seq=row["sequence_id"],
                tcpu=f"{tracker_cpu:.3f}" if tracker_cpu is not None else "n/a",
                timcpu=f"{tim_cpu:.3f}" if tim_cpu is not None else (
                    "n/a" if tim.get("status") == NOT_APPLICABLE_TIM_DISABLED else "missing"
                ),
                combined=(
                    f"{replay['combined_total_cpu_s']:.3f}"
                    if replay.get("combined_total_cpu_s") is not None
                    else "n/a"
                ),
                rss=replay.get("combined_peak_rss_kib") or "n/a",
                live=row["live"]["status"],
            )
        )

    lines += [
        "",
        "## Comparative overhead of adding TIM-MARS (replay CPU cost only)",
        "",
        "| Tracker | Raw CPU (s) -> TIM CPU (s) delta | Peak RSS delta (KiB) |",
        "|---|---:|---:|",
    ]

    for entry in overhead:
        delta_cpu = entry["delta_total_cpu_s"]
        delta_rss = entry["delta_peak_rss_kib"]
        lines.append(
            "| {tracker} | {cpu} | {rss} |".format(
                tracker=entry["tracker_type"],
                cpu=f"{delta_cpu:+.3f}" if delta_cpu is not None else "n/a",
                rss=f"{delta_rss:+d}" if delta_rss is not None else "n/a",
            )
        )

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument(
        "--replay-root",
        required=True,
        type=Path,
        help=(
            "Directory containing one subdirectory per architecture id "
            "with that architecture's replay_cost_*.json files."
        ),
    )
    parser.add_argument(
        "--live-analysis",
        type=Path,
        default=None,
        help=(
            "Optional sustained_analysis.json from a live_sustained run, "
            "applied only to the architecture it was measured for."
        ),
    )
    parser.add_argument(
        "--live-architecture-id",
        default=None,
        help="Architecture id the --live-analysis evidence applies to.",
    )
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--csv-out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)

    rows: list[dict[str, Any]] = []
    rows_by_id: dict[str, dict[str, Any]] = {}

    for architecture in manifest["architectures"]:
        architecture_id = architecture["id"]
        replay_dir = args.replay_root / architecture_id
        replay = build_replay_row(architecture, args.sequence_id, replay_dir)

        live_analysis_path = None
        if (
            args.live_analysis is not None
            and args.live_architecture_id == architecture_id
        ):
            live_analysis_path = args.live_analysis

        live = build_live_row(live_analysis_path)

        row = {
            "architecture_id": architecture_id,
            "sequence_id": args.sequence_id,
            "tracker_type": architecture["tracker_type"],
            "tim_enabled": bool(architecture.get("tim_enabled")),
            "replay": replay,
            "live": live,
        }
        rows.append(row)
        rows_by_id[architecture_id] = row

    overhead = comparative_overhead(rows_by_id)

    output = {
        "schema": SCHEMA,
        "sequence_id": args.sequence_id,
        "issue_58_join": manifest["issue_58_join"],
        "rows": rows,
        "comparative_overhead": overhead,
        "power": manifest["power"],
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.csv_out, rows)

    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.write_text(
        render_markdown(rows, overhead), encoding="utf-8"
    )

    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
