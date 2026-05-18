#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Ann:
    start_s: float
    end_s: float
    visible: bool
    correct_id: int
    event_type: str
    target_label: str


def as_bool(x) -> bool:
    return str(x).strip().lower() in {"true", "1", "yes", "y"}


def geom(r) -> float:
    return (
        0.34 * float(r["iou"])
        + 0.26 * float(r["distance"])
        + 0.18 * float(r["scale"])
        + 0.14 * float(r["confidence"])
    )


def load_annotations(path: Path):
    anns = []
    with path.open() as f:
        for r in csv.DictReader(f):
            anns.append(
                Ann(
                    start_s=float(r["start_s"]),
                    end_s=float(r["end_s"]),
                    visible=as_bool(r["target_visible"]),
                    correct_id=int(float(r["correct_target_track_id"] or 0)),
                    event_type=r["event_type"],
                    target_label=r["target_label"],
                )
            )
    return anns


def ann_at(t: float, anns):
    for a in anns:
        if a.start_s <= t < a.end_s:
            return a
    return None


def load_scores(path: Path):
    by_frame = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            frame = int(float(r["frame_id"]))
            by_frame.setdefault(frame, []).append(r)

    for frame in by_frame:
        by_frame[frame] = sorted(by_frame[frame], key=lambda r: int(float(r["rank"])))

    return by_frame


def simulate(
    by_frame,
    anns,
    runner_min_geom: float,
    runner_max_gap: float,
    runner_confirm_frames: int,
    reacquire_confirm_frames: int,
):
    selected_id = 0
    runner_id = 0
    runner_count = 0
    reacq_id = 0
    reacq_count = 0

    outputs = []

    for frame, rows in sorted(by_frame.items()):
        t = float(rows[0]["t"])
        ann = ann_at(t, anns)

        if ann is None or ann.event_type == "pre_selection" or ann.target_label == "NO_TARGET_SELECTED":
            continue

        candidates = {}
        for r in rows:
            tid = int(float(r["score_track_id"]))
            candidates[tid] = {
                "id": tid,
                "rank": int(float(r["rank"])),
                "geom": geom(r),
                "total": float(r["total"]),
            }

        best = max(candidates.values(), key=lambda x: x["geom"]) if candidates else None

        # Initialise or reacquire selected ID.
        if selected_id == 0:
            if best is not None and best["geom"] >= runner_min_geom:
                if reacq_id == best["id"]:
                    reacq_count += 1
                else:
                    reacq_id = best["id"]
                    reacq_count = 1

                if reacq_count >= reacquire_confirm_frames:
                    selected_id = best["id"]
                    reacq_id = 0
                    reacq_count = 0
            else:
                reacq_id = 0
                reacq_count = 0

        selected_present = selected_id in candidates if selected_id > 0 else False

        if selected_id > 0 and not selected_present:
            selected_id = 0
            runner_id = 0
            runner_count = 0

        selected_present = selected_id in candidates if selected_id > 0 else False

        # Persistent runner-up switch rule.
        if selected_present and len(candidates) >= 2:
            selected_geom = candidates[selected_id]["geom"]

            others = [c for c in candidates.values() if c["id"] != selected_id]
            best_other = max(others, key=lambda x: x["geom"]) if others else None

            if best_other is not None:
                gap = selected_geom - best_other["geom"]

                if best_other["geom"] >= runner_min_geom and gap <= runner_max_gap:
                    if runner_id == best_other["id"]:
                        runner_count += 1
                    else:
                        runner_id = best_other["id"]
                        runner_count = 1

                    if runner_count >= runner_confirm_frames:
                        selected_id = best_other["id"]
                        runner_id = 0
                        runner_count = 0
                else:
                    runner_id = 0
                    runner_count = 0
            else:
                runner_id = 0
                runner_count = 0

        selected_present = selected_id in candidates if selected_id > 0 else False

        if not ann.visible or ann.correct_id <= 0:
            label = "lost"
        elif not selected_present:
            label = "lost"
        elif selected_id == ann.correct_id:
            label = "correct"
        else:
            label = "wrong"

        outputs.append(
            {
                "frame": frame,
                "t": t,
                "selected_id": selected_id if selected_present else 0,
                "correct_id": ann.correct_id,
                "label": label,
            }
        )

    return outputs


def summarise(outputs):
    n = len(outputs)
    correct = sum(1 for o in outputs if o["label"] == "correct")
    wrong = sum(1 for o in outputs if o["label"] == "wrong")
    lost = sum(1 for o in outputs if o["label"] == "lost")

    return {
        "frames": n,
        "correct_frames": correct,
        "wrong_frames": wrong,
        "lost_frames": lost,
        "correct_ratio": correct / n if n else 0.0,
        "wrong_ratio": wrong / n if n else 0.0,
        "lost_ratio": lost / n if n else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--annotations", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--runner-min-geom", type=float, default=0.45)
    ap.add_argument("--runner-max-gap", type=float, default=0.45)
    ap.add_argument("--runner-confirm-frames", type=int, default=10)
    ap.add_argument("--reacquire-confirm-frames", type=int, default=2)
    args = ap.parse_args()

    anns = load_annotations(args.annotations)
    by_frame = load_scores(args.scores)

    outputs = simulate(
        by_frame=by_frame,
        anns=anns,
        runner_min_geom=args.runner_min_geom,
        runner_max_gap=args.runner_max_gap,
        runner_confirm_frames=args.runner_confirm_frames,
        reacquire_confirm_frames=args.reacquire_confirm_frames,
    )

    metrics = summarise(outputs)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    with (args.out_dir / "timeline.csv").open("w", newline="") as f:
        fieldnames = ["frame", "t", "selected_id", "correct_id", "label"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(outputs)

    with (args.out_dir / "summary.csv").open("w", newline="") as f:
        fieldnames = [
            "runner_min_geom",
            "runner_max_gap",
            "runner_confirm_frames",
            "reacquire_confirm_frames",
            "correct_ratio",
            "wrong_ratio",
            "lost_ratio",
            "frames",
            "correct_frames",
            "wrong_frames",
            "lost_frames",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerow(
            {
                "runner_min_geom": args.runner_min_geom,
                "runner_max_gap": args.runner_max_gap,
                "runner_confirm_frames": args.runner_confirm_frames,
                "reacquire_confirm_frames": args.reacquire_confirm_frames,
                **metrics,
            }
        )

    md = []
    md.append("# TIM-V2F Persistent Runner-Up Policy")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---:|")
    for k, v in metrics.items():
        md.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")

    (args.out_dir / "summary.md").write_text("\n".join(md) + "\n")

    print((args.out_dir / "summary.md").read_text())


if __name__ == "__main__":
    main()
