#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from bisect import bisect_left
from pathlib import Path


def f(x, default=0.0):
    try:
        if x in ("", None):
            return default
        return float(x)
    except Exception:
        return default


def nearest(entries, t, max_dt):
    if not entries:
        return "", ""

    times = [x[0] for x in entries]
    i = bisect_left(times, t)

    candidates = []
    if i < len(entries):
        candidates.append(entries[i])
    if i > 0:
        candidates.append(entries[i - 1])

    if not candidates:
        return "", ""

    best = min(candidates, key=lambda x: abs(x[0] - t))
    dt = abs(best[0] - t)

    if dt > max_dt:
        return "", ""

    return best[1], dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--frozen", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-dt", type=float, default=0.08)
    args = ap.parse_args()

    frozen_by_id = {}

    with args.frozen.open() as file:
        for r in csv.DictReader(file):
            tid = int(f(r["track_id"]))
            t = f(r["t"])
            sim = f(r["frozen_hsv_similarity"])
            frozen_by_id.setdefault(tid, []).append((t, sim))

    for tid in frozen_by_id:
        frozen_by_id[tid].sort(key=lambda x: x[0])

    rows = []
    matched = 0

    with args.scores.open() as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])

        for r in reader:
            t = f(r["t"])
            tid = int(f(r["score_track_id"]))
            sim, dt = nearest(frozen_by_id.get(tid, []), t, args.max_dt)

            r["frozen_hsv_similarity"] = sim
            r["frozen_hsv_dt"] = dt

            if sim != "":
                matched += 1

            rows.append(r)

    out_fields = fieldnames + ["frozen_hsv_similarity", "frozen_hsv_dt"]

    args.out.parent.mkdir(parents=True, exist_ok=True)

    with args.out.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[ok] rows={len(rows)} matched={matched}")
    print(f"[ok] wrote {args.out}")


if __name__ == "__main__":
    main()
