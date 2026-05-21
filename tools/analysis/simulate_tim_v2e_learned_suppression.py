#!/usr/bin/env python3
"""
Offline TIM-V2E learned-appearance suppression simulator.

Purpose:
- Test whether Tiny16 learned similarity can reduce wrong selected-target output.
- Conservative first policy: suppress selected output when current selected track
  has low learned similarity to selected-target memory.
- No switching/reacquisition in this script.

Inputs:
- target_memory_all_scores.csv
- target correctness annotations
- Tiny16 test_similarity_scores.csv

Output:
- timeline.csv
- summary.md
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ScoreRow:
    frame_id: int
    t: float
    target_track_id: int
    score_track_id: int
    rank: int
    total: float


@dataclass
class SimRow:
    t: float
    frame_id: int
    track_id: int
    role: str
    event_type: str
    sim: float


@dataclass
class Annotation:
    start_s: float
    end_s: float
    target_visible: bool
    correct_id: int
    event_type: str
    target_label: str


@dataclass
class Output:
    frame_id: int
    t: float
    raw_selected: int
    selected_after_policy: int
    selected_similarity: float
    reacquired_track_id: int
    reacquired_similarity: float
    suppressed: bool
    reacquired: bool
    correct_id: int
    event_type: str
    label_raw: str
    label_policy: str


def f(v, default=0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def i(v, default=0) -> int:
    try:
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def b(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def parse_event_set(text: str) -> set[str]:
    return {x.strip() for x in str(text or "").split(",") if x.strip()}


def load_scores(path: Path) -> Dict[int, List[ScoreRow]]:
    by_frame: Dict[int, List[ScoreRow]] = {}

    with path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        required = {"frame_id", "t", "target_track_id", "score_track_id", "rank", "total"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Scores CSV missing columns: {sorted(missing)}")

        for r in reader:
            row = ScoreRow(
                frame_id=i(r["frame_id"]),
                t=f(r["t"]),
                target_track_id=i(r["target_track_id"]),
                score_track_id=i(r["score_track_id"]),
                rank=i(r["rank"]),
                total=f(r["total"]),
            )
            if row.frame_id <= 0:
                continue
            by_frame.setdefault(row.frame_id, []).append(row)

    for frame in by_frame:
        by_frame[frame].sort(key=lambda x: x.rank)

    return dict(sorted(by_frame.items()))


def load_annotations(path: Path) -> List[Annotation]:
    rows: List[Annotation] = []

    with path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        required = {"start_s", "end_s", "target_visible", "correct_target_track_id", "event_type", "target_label"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Annotations CSV missing columns: {sorted(missing)}")

        for r in reader:
            rows.append(
                Annotation(
                    start_s=f(r["start_s"]),
                    end_s=f(r["end_s"]),
                    target_visible=b(r["target_visible"]),
                    correct_id=i(r["correct_target_track_id"]),
                    event_type=str(r["event_type"]).strip(),
                    target_label=str(r["target_label"]).strip(),
                )
            )

    rows.sort(key=lambda x: x.start_s)
    return rows


def load_similarity(path: Path, source_contains: str = "") -> Dict[int, List[SimRow]]:
    by_track: Dict[int, List[SimRow]] = {}

    with path.open("r", newline="") as file:
        reader = csv.DictReader(file)
        required = {"t", "frame_id", "track_id", "role", "event_type", "similarity_to_train_memory"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Similarity CSV missing columns: {sorted(missing)}")

        has_dataset_root = "dataset_root" in set(reader.fieldnames or [])

        for r in reader:
            if source_contains and has_dataset_root:
                if source_contains not in str(r.get("dataset_root", "")):
                    continue

            row = SimRow(
                t=f(r["t"]),
                frame_id=i(r["frame_id"]),
                track_id=i(r["track_id"]),
                role=str(r["role"]).strip(),
                event_type=str(r["event_type"]).strip(),
                sim=f(r["similarity_to_train_memory"], default=float("nan")),
            )
            if row.track_id <= 0 or not math.isfinite(row.sim):
                continue
            by_track.setdefault(row.track_id, []).append(row)

    for tid in by_track:
        by_track[tid].sort(key=lambda x: x.t)

    return by_track


def annotation_at(t: float, annotations: List[Annotation]) -> Optional[Annotation]:
    for ann in annotations:
        if ann.start_s <= t < ann.end_s:
            return ann
    return None


def nearest_similarity(
    by_track: Dict[int, List[SimRow]],
    track_id: int,
    t: float,
    max_dt: float,
) -> float:
    rows = by_track.get(track_id)
    if not rows:
        return float("nan")

    # Current files are small. Linear nearest is fine and transparent.
    best = min(rows, key=lambda r: abs(r.t - t))
    if abs(best.t - t) > max_dt:
        return float("nan")
    return best.sim


def candidate_sims_for_frame(
    rows: List[ScoreRow],
    sim_by_track: Dict[int, List[SimRow]],
    t: float,
    max_dt: float,
) -> List[Tuple[int, float]]:
    out: List[Tuple[int, float]] = []
    seen = set()

    for r in rows:
        tid = int(r.score_track_id)
        if tid <= 0 or tid in seen:
            continue
        seen.add(tid)

        sim = nearest_similarity(sim_by_track, tid, t, max_dt)
        if math.isfinite(sim):
            out.append((tid, sim))

    out.sort(key=lambda x: x[1], reverse=True)
    return out


def eval_label(selected: int, ann: Optional[Annotation]) -> Tuple[str, int, str]:
    if ann is None:
        return "unannotated", 0, ""

    if ann.target_label == "NO_TARGET_SELECTED":
        return "pre_selection", ann.correct_id, ann.event_type

    if not ann.target_visible or ann.correct_id <= 0:
        if selected > 0:
            return "target_absent_but_output_valid", ann.correct_id, ann.event_type
        return "target_not_visible", ann.correct_id, ann.event_type

    if selected <= 0:
        return "lost", ann.correct_id, ann.event_type

    if selected == ann.correct_id:
        return "correct", ann.correct_id, ann.event_type

    return "wrong", ann.correct_id, ann.event_type


def simulate(
    scores_by_frame: Dict[int, List[ScoreRow]],
    annotations: List[Annotation],
    sim_by_track: Dict[int, List[SimRow]],
    sim_threshold: float,
    max_sim_dt: float,
    require_similarity: bool,
    require_similarity_events: set[str],
    enable_reacquire: bool,
    candidate_high_threshold: float,
    reacquire_confirm_frames: int,
) -> List[Output]:
    outputs: List[Output] = []

    pending_reacquire_id = 0
    pending_reacquire_count = 0
    pending_reacquire_sim = float("nan")

    for frame_id, rows in scores_by_frame.items():
        if not rows:
            continue

        t = rows[0].t
        raw_selected = rows[0].target_track_id
        ann = annotation_at(t, annotations)

        raw_label, correct_id, event_type = eval_label(raw_selected, ann)

        selected_sim = nearest_similarity(
            sim_by_track,
            track_id=raw_selected,
            t=t,
            max_dt=max_sim_dt,
        ) if raw_selected > 0 else float("nan")

        suppressed = False
        reacquired = False
        reacquired_track_id = 0
        reacquired_similarity = float("nan")
        selected_after = raw_selected

        require_sim_now = bool(require_similarity)
        if require_similarity_events and event_type not in require_similarity_events:
            require_sim_now = False

        selected_is_low = False
        if raw_selected > 0:
            if math.isfinite(selected_sim):
                selected_is_low = selected_sim < sim_threshold
            else:
                selected_is_low = bool(require_sim_now)

        if raw_selected > 0 and selected_is_low:
            selected_after = 0
            suppressed = True

        if enable_reacquire and selected_after == 0:
            candidates = [
                (tid, sim)
                for tid, sim in candidate_sims_for_frame(rows, sim_by_track, t, max_sim_dt)
                if sim >= candidate_high_threshold
            ]

            if candidates:
                best_tid, best_sim = candidates[0]

                if best_tid == pending_reacquire_id:
                    pending_reacquire_count += 1
                else:
                    pending_reacquire_id = best_tid
                    pending_reacquire_count = 1

                pending_reacquire_sim = best_sim

                if pending_reacquire_count >= max(1, reacquire_confirm_frames):
                    selected_after = best_tid
                    reacquired = True
                    reacquired_track_id = best_tid
                    reacquired_similarity = best_sim
                    suppressed = False
            else:
                pending_reacquire_id = 0
                pending_reacquire_count = 0
                pending_reacquire_sim = float("nan")
        else:
            # Reset confirmation while raw/current selected remains accepted.
            pending_reacquire_id = 0
            pending_reacquire_count = 0
            pending_reacquire_sim = float("nan")

        policy_label, _correct_id2, _event_type2 = eval_label(selected_after, ann)

        outputs.append(
            Output(
                frame_id=frame_id,
                t=t,
                raw_selected=raw_selected,
                selected_after_policy=selected_after,
                selected_similarity=selected_sim,
                reacquired_track_id=reacquired_track_id,
                reacquired_similarity=reacquired_similarity,
                suppressed=suppressed,
                reacquired=reacquired,
                correct_id=correct_id,
                event_type=event_type,
                label_raw=raw_label,
                label_policy=policy_label,
            )
        )

    return outputs

def estimate_dt(outputs: List[Output]) -> float:
    ts = sorted({o.t for o in outputs})
    if len(ts) < 2:
        return 1.0 / 30.0
    diffs = [b - a for a, b in zip(ts[:-1], ts[1:]) if b > a]
    if not diffs:
        return 1.0 / 30.0
    diffs.sort()
    return diffs[len(diffs) // 2]


def summarise(outputs: List[Output]) -> dict:
    dt = estimate_dt(outputs)
    valid = [o for o in outputs if o.label_raw not in {"pre_selection", "unannotated"}]

    def count(label_attr: str, label: str) -> int:
        return sum(1 for o in valid if getattr(o, label_attr) == label)

    raw_correct = count("label_raw", "correct")
    raw_wrong = count("label_raw", "wrong")
    raw_lost = count("label_raw", "lost")

    pol_correct = count("label_policy", "correct")
    pol_wrong = count("label_policy", "wrong")
    pol_lost = count("label_policy", "lost")

    n = len(valid)

    return {
        "frames": n,
        "dt": dt,
        "raw_correct_frames": raw_correct,
        "raw_wrong_frames": raw_wrong,
        "raw_lost_frames": raw_lost,
        "policy_correct_frames": pol_correct,
        "policy_wrong_frames": pol_wrong,
        "policy_lost_frames": pol_lost,
        "raw_correct_s": raw_correct * dt,
        "raw_wrong_s": raw_wrong * dt,
        "raw_lost_s": raw_lost * dt,
        "policy_correct_s": pol_correct * dt,
        "policy_wrong_s": pol_wrong * dt,
        "policy_lost_s": pol_lost * dt,
        "suppressed_frames": sum(1 for o in outputs if o.suppressed),
        "suppressed_s": sum(1 for o in outputs if o.suppressed) * dt,
        "reacquired_frames": sum(1 for o in outputs if o.reacquired),
        "reacquired_s": sum(1 for o in outputs if o.reacquired) * dt,
    }


def event_summary(outputs: List[Output]) -> List[dict]:
    dt = estimate_dt(outputs)
    events = sorted({o.event_type for o in outputs if o.event_type})
    rows = []

    for ev in events:
        ev_rows = [o for o in outputs if o.event_type == ev and o.label_raw not in {"pre_selection", "unannotated"}]
        if not ev_rows:
            continue

        rows.append(
            {
                "event_type": ev,
                "frames": len(ev_rows),
                "raw_correct_s": sum(1 for o in ev_rows if o.label_raw == "correct") * dt,
                "raw_wrong_s": sum(1 for o in ev_rows if o.label_raw == "wrong") * dt,
                "raw_lost_s": sum(1 for o in ev_rows if o.label_raw == "lost") * dt,
                "policy_correct_s": sum(1 for o in ev_rows if o.label_policy == "correct") * dt,
                "policy_wrong_s": sum(1 for o in ev_rows if o.label_policy == "wrong") * dt,
                "policy_lost_s": sum(1 for o in ev_rows if o.label_policy == "lost") * dt,
                "suppressed_s": sum(1 for o in ev_rows if o.suppressed) * dt,
                "reacquired_s": sum(1 for o in ev_rows if o.reacquired) * dt,
            }
        )

    return rows


def write_timeline(path: Path, outputs: List[Output]) -> None:
    with path.open("w", newline="") as file:
        fieldnames = [
            "frame_id",
            "t",
            "raw_selected",
            "selected_after_policy",
            "selected_similarity",
            "reacquired_track_id",
            "reacquired_similarity",
            "suppressed",
            "reacquired",
            "correct_id",
            "event_type",
            "label_raw",
            "label_policy",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for o in outputs:
            writer.writerow(
                {
                    "frame_id": o.frame_id,
                    "t": f"{o.t:.6f}",
                    "raw_selected": o.raw_selected,
                    "selected_after_policy": o.selected_after_policy,
                    "selected_similarity": f"{o.selected_similarity:.6f}" if math.isfinite(o.selected_similarity) else "",
                    "reacquired_track_id": o.reacquired_track_id,
                    "reacquired_similarity": f"{o.reacquired_similarity:.6f}" if math.isfinite(o.reacquired_similarity) else "",
                    "suppressed": str(o.suppressed).lower(),
                    "reacquired": str(o.reacquired).lower(),
                    "correct_id": o.correct_id,
                    "event_type": o.event_type,
                    "label_raw": o.label_raw,
                    "label_policy": o.label_policy,
                }
            )


def write_summary(path: Path, metrics: dict, events: List[dict], args) -> None:
    lines = []
    lines.append("# TIM-V2E learned suppression simulation")
    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append("- Conservative suppression")
    lines.append("- Optional confirmed learned reacquisition")
    lines.append("- If selected track similarity is below threshold, output LOST")
    lines.append("- If enabled, reacquire only after a high-similarity candidate is confirmed")
    lines.append("")
    lines.append("## Parameters")
    lines.append("")
    lines.append(f"- similarity threshold: {args.sim_threshold}")
    lines.append(f"- max similarity time delta: {args.max_sim_dt}")
    lines.append(f"- similarity source contains: `{args.similarity_source_contains}`")
    lines.append(f"- require similarity: {args.require_similarity}")
    lines.append(f"- require similarity events: `{args.require_similarity_events}`")
    lines.append(f"- enable reacquire: {args.enable_reacquire}")
    lines.append(f"- candidate high threshold: {args.candidate_high_threshold}")
    lines.append(f"- reacquire confirm frames: {args.reacquire_confirm_frames}")
    lines.append("")
    lines.append("## Global result")
    lines.append("")
    lines.append("| Metric | Raw | Policy |")
    lines.append("|---|---:|---:|")
    lines.append(f"| correct_s | {metrics['raw_correct_s']:.3f} | {metrics['policy_correct_s']:.3f} |")
    lines.append(f"| wrong_s | {metrics['raw_wrong_s']:.3f} | {metrics['policy_wrong_s']:.3f} |")
    lines.append(f"| lost_s | {metrics['raw_lost_s']:.3f} | {metrics['policy_lost_s']:.3f} |")
    lines.append("")
    lines.append(f"- suppressed_s: {metrics['suppressed_s']:.3f}")
    lines.append(f"- suppressed_frames: {metrics['suppressed_frames']}")
    lines.append(f"- reacquired_s: {metrics['reacquired_s']:.3f}")
    lines.append(f"- reacquired_frames: {metrics['reacquired_frames']}")
    lines.append("")
    lines.append("## Event result")
    lines.append("")
    lines.append("| Event | Raw correct_s | Raw wrong_s | Raw lost_s | Policy correct_s | Policy wrong_s | Policy lost_s | Suppressed_s | Reacquired_s |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for r in events:
        lines.append(
            f"| {r['event_type']} | "
            f"{r['raw_correct_s']:.3f} | {r['raw_wrong_s']:.3f} | {r['raw_lost_s']:.3f} | "
            f"{r['policy_correct_s']:.3f} | {r['policy_wrong_s']:.3f} | {r['policy_lost_s']:.3f} | "
            f"{r['suppressed_s']:.3f} |"
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--scores", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--similarity", type=Path, required=True)
    p.add_argument("--similarity-source-contains", default="")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--sim-threshold", type=float, default=0.0)
    p.add_argument("--max-sim-dt", type=float, default=0.08)
    p.add_argument("--require-similarity", action="store_true")
    p.add_argument(
        "--require-similarity-events",
        default="",
        help="Comma-separated annotation event types where missing similarity should suppress current target. Empty means all events.",
    )
    p.add_argument("--enable-reacquire", action="store_true")
    p.add_argument("--candidate-high-threshold", type=float, default=0.3)
    p.add_argument("--reacquire-confirm-frames", type=int, default=3)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    scores = load_scores(args.scores)
    annotations = load_annotations(args.annotations)
    sim = load_similarity(args.similarity, source_contains=args.similarity_source_contains)

    outputs = simulate(
        scores_by_frame=scores,
        annotations=annotations,
        sim_by_track=sim,
        sim_threshold=args.sim_threshold,
        max_sim_dt=args.max_sim_dt,
        require_similarity=args.require_similarity,
        require_similarity_events=parse_event_set(args.require_similarity_events),
        enable_reacquire=args.enable_reacquire,
        candidate_high_threshold=args.candidate_high_threshold,
        reacquire_confirm_frames=args.reacquire_confirm_frames,
    )

    metrics = summarise(outputs)
    events = event_summary(outputs)

    write_timeline(args.output_dir / "timeline.csv", outputs)
    write_summary(args.output_dir / "summary.md", metrics, events, args)

    print(f"[ok] outputs={len(outputs)}")
    print(f"[ok] wrote {args.output_dir / 'timeline.csv'}")
    print(f"[ok] wrote {args.output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
