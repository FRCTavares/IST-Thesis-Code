#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import cv2


PERSON_CLASS_IDS = {1, 2}


def parse_annotations(path: Path) -> dict[int, list[dict]]:
    by_frame: dict[int, list[dict]] = defaultdict(list)

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            p = line.split(",")
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

            by_frame[frame_id].append(
                {
                    "target_id": target_id,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "class_id": class_id,
                    "truncation": truncation,
                    "occlusion": occlusion,
                }
            )

    return by_frame


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VisDrone MOT GT preview frames.")
    parser.add_argument(
        "--root",
        default="datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val",
    )
    parser.add_argument("--sequence", default="uav0000086_00000_v")
    parser.add_argument("--frames", default="1,50,100,200,300")
    parser.add_argument("--out-dir", default="reports/dataset_checks/visdrone_gt_preview")
    args = parser.parse_args()

    root = Path(args.root)
    seq_dir = root / "sequences" / args.sequence
    ann_path = root / "annotations" / f"{args.sequence}.txt"
    out_dir = Path(args.out_dir) / args.sequence
    out_dir.mkdir(parents=True, exist_ok=True)

    if not seq_dir.exists():
        raise FileNotFoundError(seq_dir)
    if not ann_path.exists():
        raise FileNotFoundError(ann_path)

    ann = parse_annotations(ann_path)
    frame_ids = [int(x.strip()) for x in args.frames.split(",") if x.strip()]

    for frame_id in frame_ids:
        img_path = seq_dir / f"{frame_id:07d}.jpg"
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"[warn] missing image: {img_path}")
            continue

        for row in ann.get(frame_id, []):
            x1 = int(round(row["x"]))
            y1 = int(round(row["y"]))
            x2 = int(round(row["x"] + row["w"]))
            y2 = int(round(row["y"] + row["h"]))

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"id={row['target_id']} c={row['class_id']} occ={row['occlusion']}"
            cv2.putText(
                img,
                label,
                (x1, max(15, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        out_path = out_dir / f"{frame_id:07d}_gt.jpg"
        cv2.imwrite(str(out_path), img)
        print(f"[ok] wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
