#!/usr/bin/env python3
"""Evaluation subprocess helpers for the TIM-MARS clean annotation UI."""

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path


def _safe_name(s: str) -> str:
    """Return a filesystem-safe short name for UI-generated report folders."""
    s = s.strip().replace("/", "__")
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", s)[:180]


def run_ui_evaluation(bag: str, ann: str, repo_root: Path) -> tuple[int, dict]:
    """Run RAW-vs-TIM target/bbox evaluation for the selected bag and annotation CSV."""
    bag = str(bag or "").strip()
    ann = str(ann or "").strip()

    if not bag:
        return 200, {"ok": False, "error": "No bag selected."}
    if not ann:
        return 200, {"ok": False, "error": "No annotation selected."}

    bag_path = Path(bag)
    ann_path = Path(ann)

    if not bag_path.is_absolute():
        bag_path = repo_root / bag_path
    if not ann_path.is_absolute():
        ann_path = repo_root / ann_path

    if not bag_path.exists():
        return 200, {"ok": False, "error": f"Bag does not exist: {bag_path}"}
    if not ann_path.exists():
        return 200, {"ok": False, "error": f"Annotation does not exist: {ann_path}"}

    out_dir = (
        repo_root
        / "reports"
        / "ui_evaluations"
        / (_safe_name(bag_path.name) + "__" + _safe_name(ann_path.stem))
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(repo_root / "tools" / "analysis" / "evaluate_tim_target_bbox_correctness.py"),
        str(bag_path),
        "--annotations",
        str(ann_path),
        "--out-dir",
        str(out_dir),
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )

    if proc.returncode != 0:
        return 200, {
            "ok": False,
            "error": "Evaluator failed.",
            "cmd": " ".join(cmd),
            "log": proc.stdout,
            "out_dir": str(out_dir),
        }

    summary_csv = out_dir / "summary.csv"
    summary_md = out_dir / "summary.md"

    rows = []
    if summary_csv.exists():
        with summary_csv.open(newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)

    markdown = summary_md.read_text() if summary_md.exists() else ""

    return 200, {
        "ok": True,
        "cmd": " ".join(cmd),
        "out_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "summary_md": str(summary_md),
        "rows": rows,
        "markdown": markdown,
        "log": proc.stdout,
    }
