#!/usr/bin/env python3
"""
Extract DeepSORT MARS-small128 ReID similarities for TIM appearance experiments.

Input:
- one or more TIM embedding dataset roots containing samples.csv and crops/

Output:
- all_similarity_scores.csv
- summary.md

Memory:
- mean feature of train-split correct crops

Evaluation:
- all correct/distractor/other samples
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from ros2_ws.src.thesis_tracker.thesis_tracker.backends.deepsort_core_backend import MarsSmall128Extractor


@dataclass
class Sample:
    dataset_root: Path
    crop_path: Path
    role: str
    identity_label: str
    event_type: str
    split: str
    target_label: str
    t: float
    frame_id: int
    track_id: int


def as_float(v, default=0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def as_int(v, default=0) -> int:
    try:
        if v in ("", None):
            return default
        return int(float(v))
    except Exception:
        return default


def load_samples(dataset_roots: Iterable[Path]) -> list[Sample]:
    samples: list[Sample] = []

    for root in dataset_roots:
        csv_path = root / "samples.csv"
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)

        with csv_path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                crop_path = root / r["crop_path"]
                if not crop_path.exists():
                    continue

                samples.append(
                    Sample(
                        dataset_root=root,
                        crop_path=crop_path,
                        role=r.get("role", ""),
                        identity_label=r.get("identity_label", ""),
                        event_type=r.get("event_type", ""),
                        split=r.get("split", "unspecified"),
                        target_label=r.get("target_label", ""),
                        t=as_float(r.get("t")),
                        frame_id=as_int(r.get("frame_id")),
                        track_id=as_int(r.get("track_id")),
                    )
                )

    return samples


def encode_crop(extractor: MarsSmall128Extractor, crop_path: Path) -> np.ndarray | None:
    img = cv2.imread(str(crop_path))
    if img is None or img.size == 0:
        return None

    h, w = img.shape[:2]
    feats = extractor.encode(img, [(0, 0, w, h)])
    feat = feats[0]

    if feat is None:
        return None

    feat = np.asarray(feat, dtype=np.float32)
    norm = float(np.linalg.norm(feat))
    if not math.isfinite(norm) or norm <= 1e-12:
        return None

    return feat / max(norm, 1e-12)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-roots", nargs="+", type=Path, required=True)
    p.add_argument("--model", type=Path, default=Path("models/reid/mars-small128.pb"))
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=32)
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    samples = load_samples(args.dataset_roots)
    if not samples:
        raise SystemExit("No samples found.")

    extractor = MarsSmall128Extractor(str(args.model), batch_size=args.batch_size)

    features: dict[Path, np.ndarray] = {}

    print(f"[info] samples={len(samples)}")
    for idx, s in enumerate(samples, start=1):
        feat = encode_crop(extractor, s.crop_path)
        if feat is not None:
            features[s.crop_path] = feat

        if idx % 100 == 0:
            print(f"[info] encoded {idx}/{len(samples)} valid={len(features)}", flush=True)

    memory_samples = [
        s for s in samples
        if s.split == "train" and s.role == "correct" and s.crop_path in features
    ]

    if not memory_samples:
        raise SystemExit("No train-split correct memory samples found.")

    memory = np.mean([features[s.crop_path] for s in memory_samples], axis=0).astype(np.float32)
    memory = memory / max(float(np.linalg.norm(memory)), 1e-12)

    out_csv = args.output_dir / "all_similarity_scores.csv"

    fields = [
        "dataset_root",
        "crop_path",
        "t",
        "frame_id",
        "track_id",
        "role",
        "identity_label",
        "event_type",
        "split",
        "target_label",
        "similarity_to_train_memory",
    ]

    rows = []
    valid_eval = 0

    for s in samples:
        feat = features.get(s.crop_path)
        sim = ""
        if feat is not None:
            sim = f"{float(np.dot(feat, memory)):.6f}"
            valid_eval += 1

        rows.append(
            {
                "dataset_root": str(s.dataset_root),
                "crop_path": str(s.crop_path),
                "t": f"{s.t:.6f}",
                "frame_id": str(s.frame_id),
                "track_id": str(s.track_id),
                "role": s.role,
                "identity_label": s.identity_label,
                "event_type": s.event_type,
                "split": s.split,
                "target_label": s.target_label,
                "similarity_to_train_memory": sim,
            }
        )

    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary = args.output_dir / "summary.md"
    summary.write_text(
        "\n".join(
            [
                "# TIM MARS-small128 ReID Similarity",
                "",
                f"- Dataset roots: `{', '.join(str(x) for x in args.dataset_roots)}`",
                f"- Model: `{args.model}`",
                f"- Samples: {len(samples)}",
                f"- Valid encoded samples: {len(features)}",
                f"- Memory correct samples: {len(memory_samples)}",
                f"- Output: `{out_csv}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"[ok] wrote {out_csv}")
    print(f"[ok] wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
