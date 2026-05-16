#!/usr/bin/env python3
"""Select the largest usable track ID from a ros2 topic echo /tracks dump."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: select_largest_track_id.py <tracks_echo_txt>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    text = path.read_text(errors="ignore")

    blocks = re.split(r"\n\s*-\s+id:\s+", "\n" + text)
    candidates: list[tuple[float, float, int, float, float]] = []

    for block in blocks[1:]:
        id_match = re.match(r"(\d+)", block)
        w_match = re.search(r"\n\s*w:\s*([0-9.+\-eE]+)", block)
        h_match = re.search(r"\n\s*h:\s*([0-9.+\-eE]+)", block)
        score_match = re.search(r"\n\s*score:\s*([0-9.+\-eE]+)", block)

        if not (id_match and w_match and h_match):
            continue

        track_id = int(id_match.group(1))
        w = float(w_match.group(1))
        h = float(h_match.group(1))
        score = float(score_match.group(1)) if score_match else 0.0

        if w <= 0.0 or h <= 0.0:
            continue

        if h < 40.0:
            continue

        candidates.append((w * h, score, track_id, w, h))

    if not candidates:
        print("no usable tracks found", file=sys.stderr)
        return 1

    candidates.sort(reverse=True)
    print(candidates[0][2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
