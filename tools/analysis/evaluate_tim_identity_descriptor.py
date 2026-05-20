#!/usr/bin/env python3
"""
Offline descriptor audit for TIM-V2E.

Purpose:
- Evaluate whether a lightweight appearance descriptor can separate the selected
  target from distractors during annotated hard crossing/re-entry intervals.
- This script is intentionally offline-only. It must not change live TIM behaviour.

Expected next implementation steps:
1. Load exact bag frames or exported frame images.
2. Load exact tracks/all-scores for the same eval run.
3. Load target correctness annotations and optional target_id_aliases.csv.
4. Extract deterministic person crops.
5. Compute 16D hand descriptor first.
6. Export pair/candidate similarity tables.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bag", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--aliases", type=Path, default=None)
    p.add_argument("--all-scores-csv", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--descriptor", choices=["hsv16", "hsv_grad16", "learned16"], default="hsv16")
    p.add_argument("--model", type=Path, default=None)
    p.add_argument("--crop-w", type=int, default=64)
    p.add_argument("--crop-h", type=int, default=128)
    p.add_argument("--min-bbox-h", type=float, default=24.0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = args.output_dir / "summary.md"
    summary.write_text(
        "# TIM-V2E descriptor audit\n\n"
        "Status: skeleton created.\n\n"
        "Next implementation:\n"
        "- load frames from bag or exported frame directory\n"
        "- align tracks/all-scores with annotations\n"
        "- extract deterministic crops\n"
        "- compute descriptor similarities\n"
        "- report whether the true target outranks distractors in critical windows\n",
        encoding="utf-8",
    )

    print(f"Wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
