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


def safe_float(x, default=0.0) -> float:
    try:
        if x in ("", None):
            return default
        return float(x)
    except Exception:
        return default


def geom(r) -> float:
    return (
        0.34 * safe_float(r.get("iou"))
        + 0.26 * safe_float(r.get("distance"))
        + 0.18 * safe_float(r.get("scale"))
        + 0.14 * safe_float(r.get("confidence"))
    )


def app(r, source: str = "appearance_raw") -> float:
    if source == "appearance_raw":
        return safe_float(r.get("appearance_raw"))
    if source == "frozen_hsv":
        return safe_float(r.get("frozen_hsv_similarity"))
    raise ValueError(f"unknown appearance source: {source}")


def total(r) -> float:
    return safe_float(r.get("total"))


def load_annotations(path: Path):
    anns = []
    with path.open() as f:
        for r in csv.DictReader(f):
            anns.append(
                Ann(
                    start_s=float(r["start_s"]),
                    end_s=float(r["end_s"]),
                    visible=as_bool(r["target_visible"]),
                    correct_id=int(float(r["correct_target_track_id"] or 0)) if r["correct_target_track_id"] else 0,
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


def candidate_dict(rows, appearance_source: str):
    out = {}
    for r in rows:
        tid = int(float(r["score_track_id"]))
        out[tid] = {
            "id": tid,
            "rank": int(float(r["rank"])),
            "total": total(r),
            "geom": geom(r),
            "app": app(r, appearance_source),
        }
    return out


def best_candidate(cands, score_key="total"):
    if not cands:
        return None
    return max(cands.values(), key=lambda x: x[score_key])


def best_reacquire_candidate(cands, lost_min_total, lost_min_geom, lost_min_app):
    plausible = [
        c for c in cands.values()
        if c["total"] >= lost_min_total
        and c["geom"] >= lost_min_geom
        and c["app"] >= lost_min_app
    ]

    if not plausible:
        return None

    # Reacquisition is identity-driven, not rank-0 driven.
    return max(plausible, key=lambda x: (x["app"], x["geom"], x["total"]))


def best_other(cands, selected_id, score_key="total"):
    others = [c for c in cands.values() if c["id"] != selected_id]
    if not others:
        return None
    return max(others, key=lambda x: x[score_key])


def simulate(
    by_frame,
    anns,
    lock_min_total: float,
    lock_min_geom: float,
    lost_min_total: float,
    lost_min_geom: float,
    lost_min_app: float,
    lost_app_margin: float,
    lost_confirm_frames: int,
    missing_ttl_frames: int,
    appearance_source: str,
):
    selected_id = 0
    missing_count = 0

    reacq_id = 0
    reacq_count = 0

    outputs = []

    for frame, rows in sorted(by_frame.items()):
        t = float(rows[0]["t"])
        ann = ann_at(t, anns)

        if ann is None or ann.event_type == "pre_selection" or ann.target_label == "NO_TARGET_SELECTED":
            continue

        cands = candidate_dict(rows, appearance_source)

        # Current selected target maintenance.
        if selected_id > 0:
            cur = cands.get(selected_id)
            if cur is None:
                missing_count += 1
                if missing_count > missing_ttl_frames:
                    selected_id = 0
                    missing_count = 0
            else:
                missing_count = 0
                if cur["total"] < lock_min_total or cur["geom"] < lock_min_geom:
                    selected_id = 0

        # LOST-state rank-aware, appearance-confirmed reacquisition.
        if selected_id == 0:
            best = best_reacquire_candidate(
                cands,
                lost_min_total=lost_min_total,
                lost_min_geom=lost_min_geom,
                lost_min_app=lost_min_app,
            )

            if best is not None:
                other = best_other(cands, best["id"], "app")
                other_app = other["app"] if other is not None else 0.0
                app_advantage = best["app"] - other_app

                ok = app_advantage >= lost_app_margin

                if ok:
                    if reacq_id == best["id"]:
                        reacq_count += 1
                    else:
                        reacq_id = best["id"]
                        reacq_count = 1

                    if reacq_count >= lost_confirm_frames:
                        selected_id = best["id"]
                        reacq_id = 0
                        reacq_count = 0
                else:
                    reacq_id = 0
                    reacq_count = 0

        selected_present = selected_id in cands if selected_id > 0 else False

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

    ap.add_argument("--lock-min-total", type=float, default=0.45)
    ap.add_argument("--lock-min-geom", type=float, default=0.30)
    ap.add_argument("--lost-min-total", type=float, default=0.50)
    ap.add_argument("--lost-min-geom", type=float, default=0.35)
    ap.add_argument("--lost-min-app", type=float, default=0.45)
    ap.add_argument("--lost-app-margin", type=float, default=0.05)
    ap.add_argument("--lost-confirm-frames", type=int, default=2)
    ap.add_argument("--missing-ttl-frames", type=int, default=3)
    ap.add_argument("--appearance-source", choices=["appearance_raw", "frozen_hsv"], default="appearance_raw")

    args = ap.parse_args()

    anns = load_annotations(args.annotations)
    by_frame = load_scores(args.scores)

    outputs = simulate(
        by_frame=by_frame,
        anns=anns,
        lock_min_total=args.lock_min_total,
        lock_min_geom=args.lock_min_geom,
        lost_min_total=args.lost_min_total,
        lost_min_geom=args.lost_min_geom,
        lost_min_app=args.lost_min_app,
        lost_app_margin=args.lost_app_margin,
        lost_confirm_frames=args.lost_confirm_frames,
        missing_ttl_frames=args.missing_ttl_frames,
        appearance_source=args.appearance_source,
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
            "lock_min_total",
            "lock_min_geom",
            "lost_min_total",
            "lost_min_geom",
            "lost_min_app",
            "lost_app_margin",
            "lost_confirm_frames",
            "missing_ttl_frames",
            "appearance_source",
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
                "lock_min_total": args.lock_min_total,
                "lock_min_geom": args.lock_min_geom,
                "lost_min_total": args.lost_min_total,
                "lost_min_geom": args.lost_min_geom,
                "lost_min_app": args.lost_min_app,
                "lost_app_margin": args.lost_app_margin,
                "lost_confirm_frames": args.lost_confirm_frames,
                "missing_ttl_frames": args.missing_ttl_frames,
                "appearance_source": args.appearance_source,
                **metrics,
            }
        )

    md = []
    md.append("# TIM-V2K Rank-Aware Appearance Reacquisition")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---:|")
    for k, v in metrics.items():
        md.append(f"| {k} | {v:.3f} |" if isinstance(v, float) else f"| {k} | {v} |")

    (args.out_dir / "summary.md").write_text("\n".join(md) + "\n")

    print((args.out_dir / "summary.md").read_text())


if __name__ == "__main__":
    main()
