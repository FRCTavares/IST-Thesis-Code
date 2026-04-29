#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


CLASS_NAMES = {
    0: "ignored-region",
    1: "pedestrian",
    2: "people",
    3: "bicycle",
    4: "car",
    5: "van",
    6: "truck",
    7: "tricycle",
    8: "awning-tricycle",
    9: "bus",
    10: "motor",
    11: "others",
}

PERSON_CLASS_IDS = {1, 2}


def parse_annotation_file(path: Path) -> list[dict]:
    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            parts = line.split(",")
            if len(parts) < 10:
                raise ValueError(f"{path}:{line_no}: expected >=10 comma fields, got {len(parts)}")

            rows.append(
                {
                    "frame_id": int(float(parts[0])),
                    "target_id": int(float(parts[1])),
                    "x": float(parts[2]),
                    "y": float(parts[3]),
                    "w": float(parts[4]),
                    "h": float(parts[5]),
                    "score": float(parts[6]),
                    "class_id": int(float(parts[7])),
                    "truncation": int(float(parts[8])),
                    "occlusion": int(float(parts[9])),
                }
            )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect VisDrone2019-MOT split structure and annotations.")
    parser.add_argument(
        "--root",
        default="datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val",
        help="Path to extracted VisDrone2019-MOT split root.",
    )
    parser.add_argument(
        "--out-dir",
        default="reports/dataset_checks",
        help="Output directory for inspection reports.",
    )
    parser.add_argument(
        "--processed-dir",
        default="datasets/processed/visdrone2019-mot",
        help="Output directory for generated manifests.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out_dir)
    processed_dir = Path(args.processed_dir)

    sequences_dir = root / "sequences"
    annotations_dir = root / "annotations"

    if not root.exists():
        raise FileNotFoundError(f"Dataset root not found: {root}")
    if not sequences_dir.exists():
        raise FileNotFoundError(f"Missing sequences dir: {sequences_dir}")
    if not annotations_dir.exists():
        raise FileNotFoundError(f"Missing annotations dir: {annotations_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    sequence_dirs = sorted(p for p in sequences_dir.iterdir() if p.is_dir())

    summary_rows = []
    global_class_counts = Counter()
    global_valid_person_ids = set()
    global_all_person_instances = 0
    global_valid_person_instances = 0
    global_images = 0

    for seq_dir in sequence_dirs:
        seq_name = seq_dir.name
        ann_path = annotations_dir / f"{seq_name}.txt"

        if not ann_path.exists():
            raise FileNotFoundError(f"Missing annotation file for {seq_name}: {ann_path}")

        images = sorted(seq_dir.glob("*.jpg"))
        ann_rows = parse_annotation_file(ann_path)

        class_counts = Counter(row["class_id"] for row in ann_rows)

        all_person_rows = [row for row in ann_rows if row["class_id"] in PERSON_CLASS_IDS]
        valid_person_rows = [
            row for row in all_person_rows
            if row["score"] > 0 and row["target_id"] > 0
        ]

        valid_person_ids = {row["target_id"] for row in valid_person_rows}
        person_frames = {row["frame_id"] for row in valid_person_rows}

        occlusion_counts = Counter(row["occlusion"] for row in valid_person_rows)
        truncation_counts = Counter(row["truncation"] for row in valid_person_rows)

        heights = [row["h"] for row in valid_person_rows if row["h"] > 0]
        tiny_lt20 = sum(1 for h in heights if h < 20)
        small_lt40 = sum(1 for h in heights if h < 40)

        n_images = len(images)

        summary_rows.append(
            {
                "sequence": seq_name,
                "images": n_images,
                "annotation_rows": len(ann_rows),
                "all_person_rows_class_1_2": len(all_person_rows),
                "valid_person_rows_class_1_2": len(valid_person_rows),
                "valid_person_track_ids": len(valid_person_ids),
                "valid_person_visible_frames": len(person_frames),
                "tiny_valid_person_h_lt20": tiny_lt20,
                "small_valid_person_h_lt40": small_lt40,
                "occlusion_0": occlusion_counts.get(0, 0),
                "occlusion_1": occlusion_counts.get(1, 0),
                "occlusion_2": occlusion_counts.get(2, 0),
                "truncation_0": truncation_counts.get(0, 0),
                "truncation_1": truncation_counts.get(1, 0),
                "truncation_2": truncation_counts.get(2, 0),
            }
        )

        global_class_counts.update(class_counts)
        global_valid_person_ids.update((seq_name, tid) for tid in valid_person_ids)
        global_all_person_instances += len(all_person_rows)
        global_valid_person_instances += len(valid_person_rows)
        global_images += n_images

    manifest_csv = processed_dir / "val_manifest.csv"
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    summary = {
        "dataset_root": str(root),
        "num_sequences": len(sequence_dirs),
        "total_images": global_images,
        "total_all_person_instances_class_1_2": global_all_person_instances,
        "total_valid_person_instances_class_1_2": global_valid_person_instances,
        "total_valid_person_track_ids_class_1_2": len(global_valid_person_ids),
        "class_counts": {
            str(k): {
                "name": CLASS_NAMES.get(k, f"unknown-{k}"),
                "count": v,
            }
            for k, v in sorted(global_class_counts.items())
        },
        "manifest_csv": str(manifest_csv),
    }

    summary_json = processed_dir / "val_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_md = out_dir / "visdrone_mot_val_inspection.md"

    lines = []
    lines.append("# VisDrone2019-MOT Val Inspection")
    lines.append("")
    lines.append(f"- Dataset root: `{root}`")
    lines.append(f"- Sequences: {summary['num_sequences']}")
    lines.append(f"- Total images: {summary['total_images']}")
    lines.append(f"- All person instances, class 1/2: {summary['total_all_person_instances_class_1_2']}")
    lines.append(f"- Valid person instances, class 1/2: {summary['total_valid_person_instances_class_1_2']}")
    lines.append(f"- Valid person track IDs, class 1/2: {summary['total_valid_person_track_ids_class_1_2']}")
    lines.append("")
    lines.append("## Class counts")
    lines.append("")
    lines.append("| Class ID | Name | Count |")
    lines.append("|---:|---|---:|")

    for k, payload in summary["class_counts"].items():
        lines.append(f"| {k} | {payload['name']} | {payload['count']} |")

    lines.append("")
    lines.append("## Per-sequence summary")
    lines.append("")
    lines.append("| Sequence | Images | Valid person rows | Valid person IDs | Tiny h<20 | Small h<40 | Occ 0 | Occ 1 | Occ 2 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in summary_rows:
        lines.append(
            f"| {row['sequence']} | {row['images']} | {row['valid_person_rows_class_1_2']} | "
            f"{row['valid_person_track_ids']} | {row['tiny_valid_person_h_lt20']} | "
            f"{row['small_valid_person_h_lt40']} | {row['occlusion_0']} | "
            f"{row['occlusion_1']} | {row['occlusion_2']} |"
        )

    lines.append("")
    lines.append("## Generated files")
    lines.append("")
    lines.append(f"- `{manifest_csv}`")
    lines.append(f"- `{summary_json}`")

    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"[ok] wrote {manifest_csv}")
    print(f"[ok] wrote {summary_json}")
    print(f"[ok] wrote {report_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
