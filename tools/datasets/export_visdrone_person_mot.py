#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import Counter


PERSON_CLASS_IDS = {1, 2}


def parse_visdrone_annotation(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            p = line.split(",")
            if len(p) < 10:
                raise ValueError(f"{path}:{line_no}: expected 10 fields, got {len(p)}")

            frame_id = int(float(p[0]))
            target_id = int(float(p[1]))
            x = float(p[2])
            y = float(p[3])
            w = float(p[4])
            h = float(p[5])
            score = float(p[6])
            class_id = int(float(p[7]))
            truncation = int(float(p[8]))
            occlusion = int(float(p[9]))

            if class_id not in PERSON_CLASS_IDS:
                continue
            if score <= 0 or target_id <= 0:
                continue
            if w <= 0 or h <= 0:
                continue

            rows.append(
                {
                    "frame_id": frame_id,
                    "target_id": target_id,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "score": score,
                    "class_id": class_id,
                    "truncation": truncation,
                    "occlusion": occlusion,
                }
            )

    return rows


def image_size(first_image: Path) -> tuple[int, int]:
    import cv2

    img = cv2.imread(str(first_image))
    if img is None:
        raise RuntimeError(f"Could not read image: {first_image}")
    height, width = img.shape[:2]
    return width, height


def main() -> int:
    parser = argparse.ArgumentParser(description="Export VisDrone2019-MOT person GT to MOTChallenge-style format.")
    parser.add_argument(
        "--root",
        default="data/datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val",
        help="Extracted VisDrone2019-MOT split root.",
    )
    parser.add_argument(
        "--out-root",
        default="data/datasets/processed/visdrone2019-mot/person_val_mot",
        help="Output root for converted MOT files.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    out_root = Path(args.out_root)

    sequences_dir = root / "sequences"
    annotations_dir = root / "annotations"

    gt_root = out_root / "gt"
    perfect_pred_root = out_root / "predictions" / "perfect"
    report_dir = Path("artifacts/reports/dataset_checks")
    report_dir.mkdir(parents=True, exist_ok=True)

    gt_root.mkdir(parents=True, exist_ok=True)
    perfect_pred_root.mkdir(parents=True, exist_ok=True)

    sequence_dirs = sorted(p for p in sequences_dir.iterdir() if p.is_dir())
    summary_rows = []

    for seq_dir in sequence_dirs:
        seq_name = seq_dir.name
        ann_path = annotations_dir / f"{seq_name}.txt"
        images = sorted(seq_dir.glob("*.jpg"))

        if not images:
            raise FileNotFoundError(f"No images found in {seq_dir}")
        if not ann_path.exists():
            raise FileNotFoundError(f"Missing annotation file: {ann_path}")

        width, height = image_size(images[0])
        rows = parse_visdrone_annotation(ann_path)

        seq_gt_dir = gt_root / seq_name / "gt"
        seq_gt_dir.mkdir(parents=True, exist_ok=True)

        gt_path = seq_gt_dir / "gt.txt"
        pred_path = perfect_pred_root / f"{seq_name}.txt"
        seqinfo_path = gt_root / seq_name / "seqinfo.ini"

        with gt_path.open("w", encoding="utf-8") as gt_f, pred_path.open("w", encoding="utf-8") as pred_f:
            for row in rows:
                # MOTChallenge format:
                # frame, id, bb_left, bb_top, bb_width, bb_height, conf, x, y, z
                line = (
                    f"{row['frame_id']},{row['target_id']},"
                    f"{row['x']:.2f},{row['y']:.2f},{row['w']:.2f},{row['h']:.2f},"
                    f"1,-1,-1,-1\n"
                )
                gt_f.write(line)
                pred_f.write(line)

        seqinfo_path.write_text(
            "\n".join(
                [
                    "[Sequence]",
                    f"name={seq_name}",
                    "imDir=img1",
                    "frameRate=30",
                    f"seqLength={len(images)}",
                    f"imWidth={width}",
                    f"imHeight={height}",
                    "imExt=.jpg",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        ids = {r["target_id"] for r in rows}
        occ = Counter(r["occlusion"] for r in rows)
        tiny = sum(1 for r in rows if r["h"] < 20)
        small = sum(1 for r in rows if r["h"] < 40)

        summary_rows.append(
            {
                "sequence": seq_name,
                "images": len(images),
                "width": width,
                "height": height,
                "person_rows": len(rows),
                "person_ids": len(ids),
                "tiny_h_lt20": tiny,
                "small_h_lt40": small,
                "occlusion_0": occ.get(0, 0),
                "occlusion_1": occ.get(1, 0),
                "occlusion_2": occ.get(2, 0),
                "gt_path": str(gt_path),
                "perfect_pred_path": str(pred_path),
            }
        )

    summary_csv = out_root / "export_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    report_md = report_dir / "visdrone_person_mot_export.md"
    lines = [
        "# VisDrone Person MOT Export",
        "",
        f"- Source root: `{root}`",
        f"- Output root: `{out_root}`",
        f"- Sequences: {len(summary_rows)}",
        f"- Total images: {sum(r['images'] for r in summary_rows)}",
        f"- Total person rows: {sum(r['person_rows'] for r in summary_rows)}",
        f"- Total person IDs: {sum(r['person_ids'] for r in summary_rows)}",
        "",
        "## Per-sequence export",
        "",
        "| Sequence | Images | Size | Person rows | Person IDs | Tiny h<20 | Small h<40 | Occ 0 | Occ 1 | Occ 2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for r in summary_rows:
        lines.append(
            f"| {r['sequence']} | {r['images']} | {r['width']}x{r['height']} | "
            f"{r['person_rows']} | {r['person_ids']} | {r['tiny_h_lt20']} | "
            f"{r['small_h_lt40']} | {r['occlusion_0']} | {r['occlusion_1']} | {r['occlusion_2']} |"
        )

    lines += [
        "",
        "## Generated roots",
        "",
        f"- Ground truth: `{gt_root}`",
        f"- Perfect predictions: `{perfect_pred_root}`",
        f"- Summary CSV: `{summary_csv}`",
    ]

    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[ok] wrote {summary_csv}")
    print(f"[ok] wrote {report_md}")
    print(f"[ok] GT root: {gt_root}")
    print(f"[ok] perfect prediction root: {perfect_pred_root}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
