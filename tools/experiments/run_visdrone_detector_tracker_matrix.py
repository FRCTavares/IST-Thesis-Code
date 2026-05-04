#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_bringup"))
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_inference_client"))
sys.path.insert(0, str(REPO / "ros2_ws/src/thesis_tracker"))

from thesis_bringup.nodes.perception_pipeline_node import HailoDirectInferenceEngine
from thesis_tracker.backends import BBox, TrackOutput
from thesis_tracker.backends.ocsort_backend import OCSortBackend
from thesis_tracker.backends.bytetrack_backend import ByteTrackBackend
from thesis_tracker.backends.sort_backend import SortBackend


def letterbox_bgr_to_rgb_square(bgr: np.ndarray, size: int):
    h0, w0 = bgr.shape[:2]
    scale = min(size / w0, size / h0)
    new_w = int(round(w0 * scale))
    new_h = int(round(h0 * scale))

    resized = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((size, size, 3), dtype=np.uint8)

    pad_x = (size - new_w) // 2
    pad_y = (size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(rgb), scale, pad_x, pad_y


def det_to_original_xyxy(det: dict, orig_w: int, orig_h: int, size: int, scale: float, pad_x: int, pad_y: int):
    x = float(det["x"]) * size
    y = float(det["y"]) * size
    w = float(det["w"]) * size
    h = float(det["h"]) * size

    x1 = (x - pad_x) / scale
    y1 = (y - pad_y) / scale
    x2 = (x + w - pad_x) / scale
    y2 = (y + h - pad_y) / scale

    x1 = max(0.0, min(orig_w - 1.0, x1))
    y1 = max(0.0, min(orig_h - 1.0, y1))
    x2 = max(0.0, min(orig_w - 1.0, x2))
    y2 = max(0.0, min(orig_h - 1.0, y2))

    if x2 <= x1 or y2 <= y1:
        return None

    return x1, y1, x2, y2


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


def run_detector_sequence(
    engine: HailoDirectInferenceEngine,
    seq_dir: Path,
    det_path: Path,
    input_size: int,
    score_threshold: float,
    max_frames: int,
) -> dict:
    images = sorted(seq_dir.glob("*.jpg"))
    if max_frames > 0:
        images = images[:max_frames]

    det_path.parent.mkdir(parents=True, exist_ok=True)

    infer_ms_values = []
    post_ms_values = []
    total_dets = 0
    kept_dets = 0

    with det_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["frame", "x1", "y1", "x2", "y2", "score"],
        )
        writer.writeheader()

        for idx, img_path in enumerate(images, start=1):
            bgr = cv2.imread(str(img_path))
            if bgr is None:
                print(f"[warn] could not read {img_path}")
                continue

            orig_h, orig_w = bgr.shape[:2]
            rgb, scale, pad_x, pad_y = letterbox_bgr_to_rgb_square(bgr, input_size)

            result = engine.infer(rgb, idx, idx, 0, 1000)
            if result is None:
                continue

            timing = result.get("timing", {})
            infer_start = int(timing.get("t_infer_start_ns", 0))
            infer_end = int(timing.get("t_infer_end_ns", 0))
            post_start = int(timing.get("t_post_start_ns", 0))
            post_end = int(timing.get("t_post_end_ns", 0))

            if infer_end > infer_start:
                infer_ms_values.append((infer_end - infer_start) / 1e6)
            if post_end > post_start:
                post_ms_values.append((post_end - post_start) / 1e6)

            dets = result.get("detections", [])
            total_dets += len(dets)

            for d in dets:
                score = float(d.get("score", 0.0))
                if score < score_threshold:
                    continue

                xyxy = det_to_original_xyxy(
                    d,
                    orig_w=orig_w,
                    orig_h=orig_h,
                    size=input_size,
                    scale=scale,
                    pad_x=pad_x,
                    pad_y=pad_y,
                )
                if xyxy is None:
                    continue

                x1, y1, x2, y2 = xyxy
                writer.writerow(
                    {
                        "frame": idx,
                        "x1": f"{x1:.2f}",
                        "y1": f"{y1:.2f}",
                        "x2": f"{x2:.2f}",
                        "y2": f"{y2:.2f}",
                        "score": f"{score:.6f}",
                    }
                )
                kept_dets += 1

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    def p95(xs):
        if not xs:
            return 0.0
        s = sorted(xs)
        return s[int(0.95 * (len(s) - 1))]

    return {
        "sequence": seq_dir.name,
        "frames": len(images),
        "raw_detections": total_dets,
        "kept_detections": kept_dets,
        "infer_ms_mean": mean(infer_ms_values),
        "infer_ms_p95": p95(infer_ms_values),
        "post_ms_mean": mean(post_ms_values),
        "post_ms_p95": p95(post_ms_values),
        "detection_file": str(det_path),
    }


def read_detection_cache(path: Path) -> dict[int, list[tuple[BBox, float]]]:
    out = defaultdict(list)

    with path.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            frame = int(r["frame"])
            x1 = float(r["x1"])
            y1 = float(r["y1"])
            x2 = float(r["x2"])
            y2 = float(r["y2"])
            score = float(r["score"])

            if x2 <= x1 or y2 <= y1:
                continue

            out[frame].append(((x1, y1, x2, y2), score))

    return dict(out)


def track_sequence(det_path: Path, n_frames: int, tracker_name: str, pred_path: Path) -> dict:
    tracker = make_tracker(tracker_name)
    tracker.reset()

    dets_by_frame = read_detection_cache(det_path)
    pred_path.parent.mkdir(parents=True, exist_ok=True)

    track_ms_values = []
    outputs = 0

    with pred_path.open("w", encoding="utf-8") as f:
        for frame in range(1, n_frames + 1):
            dets = dets_by_frame.get(frame, [])
            boxes = [d[0] for d in dets]
            scores = [d[1] for d in dets]

            t0 = time.perf_counter()
            tracks: list[TrackOutput] = tracker.update(
                boxes,
                scores,
                frame_time_ns=frame * 33_333_333,
            )
            track_ms_values.append((time.perf_counter() - t0) * 1000.0)

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
                outputs += 1

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    def p95(xs):
        if not xs:
            return 0.0
        s = sorted(xs)
        return s[int(0.95 * (len(s) - 1))]

    return {
        "tracker": tracker_name,
        "sequence": det_path.stem,
        "frames": n_frames,
        "outputs": outputs,
        "track_ms_mean": mean(track_ms_values),
        "track_ms_p95": p95(track_ms_values),
        "prediction_file": str(pred_path),
    }


def run_eval(pred_root: Path, eval_out: Path, iou_threshold: float, max_frame: int = 0) -> None:
    cmd = [
        sys.executable,
        str(REPO / "tools/data/datasets/evaluate_mot_predictions.py"),
        "--gt-root",
        str(REPO / "data/datasets/processed/visdrone2019-mot/person_val_mot/gt"),
        "--pred-root",
        str(pred_root),
        "--out-dir",
        str(eval_out),
        "--iou-threshold",
        str(iou_threshold),
    ]

    if max_frame > 0:
        cmd.extend(["--max-frame", str(max_frame)])

    subprocess.run(cmd, check=True)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root",
        default="data/datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val",
    )
    ap.add_argument("--hef", default="models/hef/yolov6n.hef")
    ap.add_argument("--model-name", default="yolov6n")
    ap.add_argument("--input-size", type=int, default=640)
    ap.add_argument("--score-threshold", type=float, default=0.25)
    ap.add_argument("--trackers", default="ocsort_live,bytetrack_default")
    ap.add_argument("--max-sequences", type=int, default=0)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--iou-threshold", type=float, default=0.5)
    ap.add_argument(
        "--out-root",
        default=f"artifacts/reports/tracking/visdrone_detector_tracker_matrix_{time.strftime('%Y%m%d_%H%M%S')}",
    )
    args = ap.parse_args()

    root = Path(args.root)
    hef = Path(args.hef)
    out_root = Path(args.out_root)

    seq_root = root / "sequences"
    seq_dirs = sorted(p for p in seq_root.iterdir() if p.is_dir())
    if args.max_sequences > 0:
        seq_dirs = seq_dirs[: args.max_sequences]

    trackers = [x.strip() for x in args.trackers.split(",") if x.strip()]

    det_root = out_root / "detections" / args.model_name
    pred_root = out_root / "predictions"
    eval_root = out_root / "eval"

    print(f"[info] model={args.model_name} hef={hef}")
    print(f"[info] sequences={len(seq_dirs)} score_threshold={args.score_threshold}")
    print(f"[info] trackers={trackers}")

    detector_rows = []
    tracker_rows = []

    engine = HailoDirectInferenceEngine(
        hef_path=str(hef),
        infer_timeout_ms=1000,
        label_filter="person",
    )

    try:
        for seq_dir in seq_dirs:
            det_path = det_root / f"{seq_dir.name}.csv"
            print(f"[detect] {seq_dir.name}")
            row = run_detector_sequence(
                engine=engine,
                seq_dir=seq_dir,
                det_path=det_path,
                input_size=args.input_size,
                score_threshold=args.score_threshold,
                max_frames=args.max_frames,
            )
            detector_rows.append(row)
    finally:
        engine.close()

    write_csv(out_root / "detector_runtime_summary.csv", detector_rows)

    for tracker_name in trackers:
        tracker_pred_root = pred_root / f"{args.model_name}__{tracker_name}"
        tracker_pred_root.mkdir(parents=True, exist_ok=True)

        print(f"\n=== tracker: {tracker_name} ===")

        for det_row in detector_rows:
            seq_name = det_row["sequence"]
            n_frames = int(det_row["frames"])
            det_path = Path(det_row["detection_file"])
            pred_path = tracker_pred_root / f"{seq_name}.txt"

            print(f"[track] {args.model_name} {tracker_name} {seq_name}")

            row = track_sequence(
                det_path=det_path,
                n_frames=n_frames,
                tracker_name=tracker_name,
                pred_path=pred_path,
            )
            row["model"] = args.model_name
            tracker_rows.append(row)

        print(f"[eval] {args.model_name} {tracker_name}")
        run_eval(
            pred_root=tracker_pred_root,
            eval_out=eval_root / f"{args.model_name}__{tracker_name}",
            iou_threshold=args.iou_threshold,
            max_frame=args.max_frames,
        )

    write_csv(out_root / "tracker_runtime_summary.csv", tracker_rows)

    (out_root / "README.md").write_text(
        "# VisDrone Detector-Tracker Matrix\n\n"
        f"- Dataset root: `{root}`\n"
        f"- Model: `{args.model_name}`\n"
        f"- HEF: `{hef}`\n"
        f"- Input size: {args.input_size}\n"
        f"- Score threshold: {args.score_threshold}\n"
        f"- Trackers: `{','.join(trackers)}`\n"
        f"- Sequences: {len(seq_dirs)}\n"
        f"- Max frames: {args.max_frames}\n"
        f"- IoU threshold: {args.iou_threshold}\n\n"
        "## Outputs\n\n"
        f"- Detections: `{det_root}`\n"
        f"- Predictions: `{pred_root}`\n"
        f"- Evaluations: `{eval_root}`\n",
        encoding="utf-8",
    )

    print(f"\n[ok] output root: {out_root}")
    print(f"[ok] detector runtime: {out_root / 'detector_runtime_summary.csv'}")
    print(f"[ok] tracker runtime: {out_root / 'tracker_runtime_summary.csv'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
