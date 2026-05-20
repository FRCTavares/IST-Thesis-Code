#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import defaultdict


def f(x, default=0.0):
    try:
        if x in ("", None):
            return default
        return float(x)
    except Exception:
        return default


def b(x):
    return str(x).strip().lower() in {"true", "1", "yes", "y"}


def load_annotations(path: Path):
    rows = []
    with path.open() as file:
        for r in csv.DictReader(file):
            rows.append({
                "start": f(r["start_s"]),
                "end": f(r["end_s"]),
                "visible": b(r["target_visible"]),
                "correct_id": int(f(r["correct_target_track_id"], 0)) if r["correct_target_track_id"] else 0,
                "event": r["event_type"],
                "label": r["target_label"],
            })
    return rows


def ann_at(t, anns):
    for a in anns:
        if a["start"] <= t < a["end"]:
            return a
    return None


def load_scores(path: Path):
    by_frame = defaultdict(list)
    with path.open() as file:
        for r in csv.DictReader(file):
            by_frame[int(f(r["frame_id"]))].append(r)

    for frame in by_frame:
        by_frame[frame] = sorted(by_frame[frame], key=lambda r: int(f(r["rank"])))

    return dict(sorted(by_frame.items()))


def candidate_geom(r):
    return (
        0.34 * f(r["iou"])
        + 0.26 * f(r["distance"])
        + 0.18 * f(r["scale"])
        + 0.14 * f(r["confidence"])
    )


def simulate(
    by_frame,
    anns,
    challenger_min_total,
    challenger_min_geom,
    challenger_margin_to_current,
    challenger_confirm_frames,
):
    challenger_id = 0
    challenger_count = 0
    outputs = []

    for frame, rows in by_frame.items():
        if not rows:
            continue

        t = f(rows[0]["t"])
        ann = ann_at(t, anns)

        if ann is None or ann["event"] == "pre_selection" or ann["label"] == "NO_TARGET_SELECTED":
            continue

        state = rows[0]["state"]
        current_id = int(f(rows[0]["target_track_id"]))
        selected = current_id
        suppressed = False

        # Only suppress LOCKED output.
        if state == "LOCKED" and current_id > 0:
            current_rows = [r for r in rows if int(f(r["score_track_id"])) == current_id]
            current_total = f(current_rows[0]["total"]) if current_rows else 0.0

            challengers = []
            for r in rows:
                tid = int(f(r["score_track_id"]))
                if tid == current_id:
                    continue

                total = f(r["total"])
                geom = candidate_geom(r)

                if total >= challenger_min_total and geom >= challenger_min_geom:
                    challengers.append((tid, total, geom))

            if challengers:
                best = max(challengers, key=lambda x: (x[1], x[2]))
                tid, total, geom = best

                # Challenger can be weaker than current, but must be persistently plausible.
                close_enough = (current_total - total) <= challenger_margin_to_current

                if close_enough:
                    if challenger_id == tid:
                        challenger_count += 1
                    else:
                        challenger_id = tid
                        challenger_count = 1

                    if challenger_count >= challenger_confirm_frames:
                        selected = 0
                        suppressed = True
                else:
                    challenger_id = 0
                    challenger_count = 0
            else:
                challenger_id = 0
                challenger_count = 0
        else:
            challenger_id = 0
            challenger_count = 0

        correct = ann["correct_id"]

        if not ann["visible"] or correct <= 0:
            label = "lost"
        elif selected <= 0:
            label = "lost"
        elif selected == correct:
            label = "correct"
        else:
            label = "wrong"

        outputs.append({
            "frame": frame,
            "t": t,
            "state": state,
            "raw_selected": current_id,
            "selected": selected,
            "correct": correct,
            "suppressed": suppressed,
            "label": label,
        })

    return outputs


def summarise(outputs):
    n = len(outputs)
    c = sum(1 for x in outputs if x["label"] == "correct")
    w = sum(1 for x in outputs if x["label"] == "wrong")
    l = sum(1 for x in outputs if x["label"] == "lost")
    s = sum(1 for x in outputs if x["suppressed"])
    return {
        "frames": n,
        "correct_frames": c,
        "wrong_frames": w,
        "lost_frames": l,
        "suppressed_frames": s,
        "correct_ratio": c / n if n else 0,
        "wrong_ratio": w / n if n else 0,
        "lost_ratio": l / n if n else 0,
        "suppressed_ratio": s / n if n else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--annotations", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--challenger-min-total", type=float, default=0.50)
    ap.add_argument("--challenger-min-geom", type=float, default=0.50)
    ap.add_argument("--challenger-margin-to-current", type=float, default=0.45)
    ap.add_argument("--challenger-confirm-frames", type=int, default=5)
    args = ap.parse_args()

    anns = load_annotations(args.annotations)
    by_frame = load_scores(args.scores)

    outputs = simulate(
        by_frame,
        anns,
        challenger_min_total=args.challenger_min_total,
        challenger_min_geom=args.challenger_min_geom,
        challenger_margin_to_current=args.challenger_margin_to_current,
        challenger_confirm_frames=args.challenger_confirm_frames,
    )

    metrics = summarise(outputs)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    with (args.out_dir / "timeline.csv").open("w", newline="") as file:
        fieldnames = ["frame", "t", "state", "raw_selected", "selected", "correct", "suppressed", "label"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(outputs)

    with (args.out_dir / "summary.csv").open("w", newline="") as file:
        fieldnames = [
            "challenger_min_total",
            "challenger_min_geom",
            "challenger_margin_to_current",
            "challenger_confirm_frames",
            *metrics.keys(),
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "challenger_min_total": args.challenger_min_total,
            "challenger_min_geom": args.challenger_min_geom,
            "challenger_margin_to_current": args.challenger_margin_to_current,
            "challenger_confirm_frames": args.challenger_confirm_frames,
            **metrics,
        })

    print("# TIM-V2M Locked Suppression")
    print()
    print("| Metric | Value |")
    print("|---|---:|")
    for k, v in metrics.items():
        print(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")


if __name__ == "__main__":
    main()
