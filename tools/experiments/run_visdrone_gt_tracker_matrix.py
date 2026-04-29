#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_tracker"))

from thesis_tracker.backends import BBox, TrackOutput
from thesis_tracker.backends.sort_backend import SortBackend
from thesis_tracker.backends.ocsort_backend import OCSortBackend
from thesis_tracker.backends.bytetrack_backend import ByteTrackBackend


PERSON_CLASS_IDS = {1, 2}


def parse_gt(path: Path) -> dict[int, list[tuple[BBox, float]]]:
    by_frame: dict[int, list[tuple[BBox, float]]] = {}

    for line in path.read_text().splitlines():
        if not line.strip():
            continue

        p = line.split(",")
        frame = int(float(p[0]))
        target_id = int(float(p[1]))
        x = float(p[2])
        y = float(p[3])
        w = float(p[4])
        h = float(p[5])
        score = float(p[6])
        cls = int(float(p[7]))

        if cls not in PERSON_CLASS_IDS:
            continue
        if target_id <= 0 or score <= 0 or w <= 0 or h <= 0:
            continue

        bbox = (x, y, x + w, y + h)
        by_frame.setdefault(frame, []).append((bbox, 1.0))

    return by_frame


def make_tracker(name: str):
    if name == "sort_live":
        return SortBackend(
            iou_threshold=0.18,
            max_age=4,
            min_hits=3,
            centre_gate=200.0,
            gate_x=None,
            gate_y=None,
        )

    if name == "sort_long":
        return SortBackend(
            iou_threshold=0.30,
            max_age=30,
            min_hits=3,
            centre_gate=9999.0,
            gate_x=None,
            gate_y=None,
        )

    if name == "ocsort_live":
        return OCSortBackend(
            iou_threshold=0.18,
            max_age=4,
            min_hits=3,
            det_thresh=0.35,
            delta_t=3,
            inertia=0.2,
            use_byte=False,
        )

    if name == "ocsort_benchmark":
        return OCSortBackend(
            iou_threshold=0.30,
            max_age=30,
            min_hits=3,
            det_thresh=0.35,
            delta_t=3,
            inertia=0.2,
            use_byte=False,
        )

    if name == "bytetrack_default":
        return ByteTrackBackend(
            track_thresh=0.5,
            match_thresh=0.8,
            track_buffer=30,
            frame_rate=30,
            low_thresh=0.1,
            new_track_thresh=0.6,
            second_match_thresh=0.5,
            unconfirmed_match_thresh=0.7,
            fuse_scores=True,
            mot20=False,
        )

    raise ValueError(f"Unknown tracker preset: {name}")


def track_sequence(seq_name: str, ann_path: Path, n_frames: int, tracker_name: str, pred_path: Path) -> dict:
    tracker = make_tracker(tracker_name)
    tracker.reset()

    gt_by_frame = parse_gt(ann_path)
    pred_path.parent.mkdir(parents=True, exist_ok=True)

    total_outputs = 0
    frame_times_ms: list[float] = []

    with pred_path.open("w", encoding="utf-8") as f:
        for frame in range(1, n_frames + 1):
            dets = gt_by_frame.get(frame, [])
            boxes = [d[0] for d in dets]
            scores = [d[1] for d in dets]

            t0 = time.perf_counter()
            tracks: list[TrackOutput] = tracker.update(
                boxes,
                scores,
                frame_time_ns=frame * 33_333_333,
            )
            frame_times_ms.append((time.perf_counter() - t0) * 1000.0)

            for trk in tracks:
                x1, y1, x2, y2 = trk.bbox_xyxy
                w = max(0.0, x2 - x1)
                h = max(0.0, y2 - y1)
                if w <= 0 or h <= 0:
                    continue

                f.write(
                    f"{frame},{trk.track_id},{x1:.2f},{y1:.2f},{w:.2f},{h:.2f},"
                    f"{trk.score:.6f},-1,-1,-1\n"
                )
                total_outputs += 1

    mean_ms = sum(frame_times_ms) / len(frame_times_ms) if frame_times_ms else 0.0
    sorted_ms = sorted(frame_times_ms)
    p95_ms = sorted_ms[int(0.95 * (len(sorted_ms) - 1))] if sorted_ms else 0.0

    return {
        "tracker": tracker_name,
        "sequence": seq_name,
        "frames": n_frames,
        "outputs": total_outputs,
        "track_ms_mean": mean_ms,
        "track_ms_p95": p95_ms,
        "prediction_file": str(pred_path),
    }


def sequence_length(seq_dir: Path) -> int:
    return len(list(seq_dir.glob("*.jpg")))


def run_eval(pred_root: Path, eval_out: Path, iou_threshold: float) -> None:
    cmd = [
        sys.executable,
        str(REPO / "tools/datasets/evaluate_mot_predictions.py"),
        "--gt-root",
        str(REPO / "datasets/processed/visdrone2019-mot/person_val_mot/gt"),
        "--pred-root",
        str(pred_root),
        "--out-dir",
        str(eval_out),
        "--iou-threshold",
        str(iou_threshold),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default="datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val",
    )
    ap.add_argument(
        "--trackers",
        default="sort_live,sort_long,ocsort_live,ocsort_benchmark,bytetrack_default",
    )
    ap.add_argument("--max-sequences", type=int, default=0)
    ap.add_argument("--iou-threshold", type=float, default=0.5)
    ap.add_argument(
        "--out-root",
        default=f"reports/tracking/visdrone_gt_tracker_matrix_{time.strftime('%Y%m%d_%H%M%S')}",
    )
    args = ap.parse_args()

    root = Path(args.root)
    out_root = Path(args.out_root)
    pred_root = out_root / "predictions"
    eval_root = out_root / "eval"
    out_root.mkdir(parents=True, exist_ok=True)

    seq_root = root / "sequences"
    ann_root = root / "annotations"

    seq_dirs = sorted(p for p in seq_root.iterdir() if p.is_dir())
    if args.max_sequences > 0:
        seq_dirs = seq_dirs[: args.max_sequences]

    trackers = [x.strip() for x in args.trackers.split(",") if x.strip()]

    rows = []

    for tracker_name in trackers:
        print(f"\n=== tracker: {tracker_name} ===")

        tracker_pred_root = pred_root / tracker_name
        tracker_pred_root.mkdir(parents=True, exist_ok=True)

        for seq_dir in seq_dirs:
            seq_name = seq_dir.name
            ann_path = ann_root / f"{seq_name}.txt"
            n_frames = sequence_length(seq_dir)
            pred_path = tracker_pred_root / f"{seq_name}.txt"

            print(f"[run] {tracker_name} {seq_name} frames={n_frames}")

            row = track_sequence(
                seq_name=seq_name,
                ann_path=ann_path,
                n_frames=n_frames,
                tracker_name=tracker_name,
                pred_path=pred_path,
            )
            rows.append(row)

        print(f"[eval] {tracker_name}")
        run_eval(
            pred_root=tracker_pred_root,
            eval_out=eval_root / tracker_name,
            iou_threshold=args.iou_threshold,
        )

    csv_path = out_root / "tracker_runtime_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "tracker",
            "sequence",
            "frames",
            "outputs",
            "track_ms_mean",
            "track_ms_p95",
            "prediction_file",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    md_path = out_root / "README.md"
    md_path.write_text(
        "# VisDrone GT Tracker Matrix\n\n"
        f"- Source: `{root}`\n"
        f"- Trackers: `{','.join(trackers)}`\n"
        f"- Sequences: {len(seq_dirs)}\n"
        f"- IoU threshold: {args.iou_threshold}\n\n"
        "## Outputs\n\n"
        f"- Predictions: `{pred_root}`\n"
        f"- Evaluations: `{eval_root}`\n"
        f"- Runtime CSV: `{csv_path}`\n",
        encoding="utf-8",
    )

    print(f"\n[ok] wrote {csv_path}")
    print(f"[ok] wrote {md_path}")
    print(f"[ok] output root: {out_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
