#!/usr/bin/env python3
"""Attach the visual start time to precomputed live-run provenance."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def attach(precomputed: Path, output: Path, run_id: str, visual_file: Path, started_at: str) -> dict:
    metadata = json.loads(precomputed.read_text(encoding="utf-8"))
    visual = metadata.get("visual")
    if metadata.get("run_id") != run_id:
        raise ValueError("precomputed run ID mismatch")
    if not isinstance(visual, dict) or visual.get("file") != str(visual_file):
        raise ValueError("precomputed visual file mismatch")
    if visual.get("started_at_utc"):
        raise ValueError("precomputed visual start time was already set")
    if Path(metadata.get("bag", {}).get("out_dir", "")) != output.parent:
        raise ValueError("precomputed bag destination mismatch")
    if visual_file.parent != output.parent or visual_file.name != f"visual_{run_id}.mkv":
        raise ValueError("visual path does not match the run")
    if not visual_file.is_file():
        raise ValueError("visual recorder output missing")
    parsed = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("visual start time must have a timezone")
    visual["started_at_utc"] = started_at
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--precomputed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--visual-file", required=True, type=Path)
    parser.add_argument("--visual-started-at-utc", required=True)
    args = parser.parse_args()
    try:
        metadata = attach(
            args.precomputed, args.output, args.run_id,
            args.visual_file, args.visual_started_at_utc,
        )
        fd, tmp = tempfile.mkstemp(dir=str(args.output.parent), prefix=".run_metadata.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(metadata, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, args.output)
        except BaseException:
            os.unlink(tmp)
            raise
        args.precomputed.unlink()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[warn] visual run metadata incomplete: {exc}")
        return 1
    print(f"[ok] attached visual start time to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
