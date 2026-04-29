#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


def read_mot(path: Path) -> dict[int, list[tuple[int, np.ndarray]]]:
    by_frame = defaultdict(list)

    for line in path.read_text().splitlines():
        if not line.strip():
            continue

        p = line.split(",")
        frame = int(float(p[0]))
        obj_id = int(float(p[1]))
        x, y, w, h = map(float, p[2:6])

        if obj_id <= 0 or w <= 0 or h <= 0:
            continue

        by_frame[frame].append((obj_id, np.array([x, y, w, h], dtype=float)))

    return dict(by_frame)


def iou_xywh(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b

    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)

    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter

    return inter / union if union > 0 else 0.0


def match_frame(gt_rows, pred_rows, iou_thr: float):
    if not gt_rows or not pred_rows:
        return []

    cost = np.ones((len(gt_rows), len(pred_rows)), dtype=float) * 1e6

    for i, (_, gbox) in enumerate(gt_rows):
        for j, (_, pbox) in enumerate(pred_rows):
            iou = iou_xywh(gbox, pbox)
            if iou >= iou_thr:
                cost[i, j] = 1.0 - iou

    gi, pj = linear_sum_assignment(cost)

    matches = []
    for i, j in zip(gi, pj):
        if cost[i, j] < 1e6:
            gt_id = gt_rows[i][0]
            pred_id = pred_rows[j][0]
            iou = 1.0 - cost[i, j]
            matches.append((gt_id, pred_id, iou))

    return matches


def evaluate_pair(gt_file: Path, pred_file: Path, iou_thr: float) -> dict:
    gt = read_mot(gt_file)
    pred = read_mot(pred_file)

    total_gt = total_pred = tp = fp = fn = 0
    iou_sum = 0.0
    id_switches = 0
    fragments = 0

    last_match_for_gt = {}
    was_matched_prev = defaultdict(bool)
    pair_counts = defaultdict(int)

    for frame in sorted(set(gt) | set(pred)):
        gt_rows = gt.get(frame, [])
        pred_rows = pred.get(frame, [])

        total_gt += len(gt_rows)
        total_pred += len(pred_rows)

        matches = match_frame(gt_rows, pred_rows, iou_thr)
        matched_gt = {m[0] for m in matches}

        tp += len(matches)
        fn += len(gt_rows) - len(matches)
        fp += len(pred_rows) - len(matches)

        for gt_id, pred_id, iou in matches:
            iou_sum += iou
            pair_counts[(gt_id, pred_id)] += 1

            if gt_id in last_match_for_gt and last_match_for_gt[gt_id] != pred_id:
                id_switches += 1

            if gt_id in was_matched_prev and not was_matched_prev[gt_id]:
                fragments += 1

            last_match_for_gt[gt_id] = pred_id

        for gt_id, _ in gt_rows:
            was_matched_prev[gt_id] = gt_id in matched_gt

    mota = 1.0 - ((fn + fp + id_switches) / total_gt) if total_gt else 0.0
    motp_iou = iou_sum / tp if tp else 0.0

    gt_ids = sorted({g for g, _ in pair_counts})
    pr_ids = sorted({p for _, p in pair_counts})
    idtp = 0

    if gt_ids and pr_ids:
        mat = np.zeros((len(gt_ids), len(pr_ids)), dtype=float)
        gi = {gid: i for i, gid in enumerate(gt_ids)}
        pi = {pid: j for j, pid in enumerate(pr_ids)}

        for (gid, pid), count in pair_counts.items():
            mat[gi[gid], pi[pid]] = count

        rows, cols = linear_sum_assignment(-mat)
        idtp = int(mat[rows, cols].sum())

    idfp = total_pred - idtp
    idfn = total_gt - idtp
    idf1 = (2 * idtp) / (2 * idtp + idfp + idfn) if (2 * idtp + idfp + idfn) else 0.0

    return {
        "frames": len(set(gt) | set(pred)),
        "gt": total_gt,
        "pred": total_pred,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "iou_sum": iou_sum,
        "mota": mota,
        "motp_iou": motp_iou,
        "idf1": idf1,
        "idtp": idtp,
        "idfp": idfp,
        "idfn": idfn,
        "id_switches": id_switches,
        "fragments": fragments,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt-root", default="datasets/processed/visdrone2019-mot/person_val_mot/gt")
    ap.add_argument("--pred-root", default="datasets/processed/visdrone2019-mot/person_val_mot/predictions/perfect")
    ap.add_argument("--out-dir", default="reports/tracking/visdrone_person_mot_eval_perfect")
    ap.add_argument("--iou-threshold", type=float, default=0.5)
    args = ap.parse_args()

    gt_root = Path(args.gt_root)
    pred_root = Path(args.pred_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    totals = defaultdict(float)

    skipped = []

    for seq_dir in sorted(p for p in gt_root.iterdir() if p.is_dir()):
        name = seq_dir.name
        gt_file = seq_dir / "gt" / "gt.txt"
        pred_file = pred_root / f"{name}.txt"

        if not pred_file.exists():
            skipped.append(name)
            continue

        r = evaluate_pair(gt_file, pred_file, args.iou_threshold)
        r["sequence"] = name
        rows.append(r)

        for k, v in r.items():
            if k != "sequence":
                totals[k] += v

    if not rows:
        raise FileNotFoundError(f"No prediction files found under {pred_root}")

    overall = dict(totals)
    overall["sequence"] = "OVERALL"
    overall["mota"] = 1.0 - ((overall["fn"] + overall["fp"] + overall["id_switches"]) / overall["gt"])
    overall["motp_iou"] = overall["iou_sum"] / overall["tp"] if overall["tp"] else 0.0
    overall["idf1"] = (2 * overall["idtp"]) / (2 * overall["idtp"] + overall["idfp"] + overall["idfn"])
    rows.append(overall)

    fieldnames = [
        "sequence", "frames", "gt", "pred", "tp", "fp", "fn",
        "mota", "motp_iou", "idf1", "id_switches", "fragments",
        "idtp", "idfp", "idfn",
    ]

    csv_path = out_dir / "summary.csv"
    md_path = out_dir / "summary.md"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in fieldnames})

    lines = [
        "# Lightweight MOT Evaluation Summary",
        "",
        f"- GT root: `{gt_root}`",
        f"- Prediction root: `{pred_root}`",
        f"- IoU threshold: {args.iou_threshold}",
        "",
        "| Sequence | GT | Pred | FP | FN | IDSW | Frag | MOTA | IDF1 | MOTP IoU |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in rows:
        lines.append(
            f"| {r['sequence']} | {int(r['gt'])} | {int(r['pred'])} | "
            f"{int(r['fp'])} | {int(r['fn'])} | {int(r['id_switches'])} | "
            f"{int(r['fragments'])} | {100*r['mota']:.2f}% | "
            f"{100*r['idf1']:.2f}% | {100*r['motp_iou']:.2f}% |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(md_path.read_text())
    print(f"[ok] wrote {csv_path}")
    print(f"[ok] wrote {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
