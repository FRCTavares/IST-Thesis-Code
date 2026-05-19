#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import Counter


def f(x, default=0.0):
    try:
        if x in ("", None):
            return default
        return float(x)
    except Exception:
        return default


def load_aliases(path: Path):
    aliases = []
    if not path or not path.exists():
        return aliases

    with path.open() as file:
        for r in csv.DictReader(file):
            alias_ids = set()
            raw = (r.get("alias_correct_ids") or "").strip()
            if raw:
                for part in raw.replace(";", ",").split(","):
                    part = part.strip()
                    if part:
                        alias_ids.add(int(f(part)))

            aliases.append({
                "start": f(r["start_s"]),
                "end": f(r["end_s"]),
                "primary": int(f(r["primary_correct_id"])),
                "aliases": alias_ids,
                "reason": r.get("reason", ""),
            })

    return aliases


def correct_set_for(t: float, correct_id: int, aliases):
    ids = set()
    if correct_id > 0:
        ids.add(correct_id)

    for a in aliases:
        if a["start"] <= t < a["end"] and correct_id == a["primary"]:
            ids |= a["aliases"]

    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", required=True, type=Path)
    ap.add_argument("--aliases", type=Path)
    args = ap.parse_args()

    aliases = load_aliases(args.aliases) if args.aliases else []

    rows = []
    with args.timeline.open() as file:
        rows = list(csv.DictReader(file))

    labels = []
    duplicate_correct = 0

    for r in rows:
        t = f(r["t"])
        selected = int(f(r["selected_id"]))
        correct = int(f(r["correct_id"]))

        correct_ids = correct_set_for(t, correct, aliases)

        if correct <= 0:
            label = "lost"
        elif selected <= 0:
            label = "lost"
        elif selected == correct:
            label = "correct"
        elif selected in correct_ids:
            label = "same_person_duplicate"
            duplicate_correct += 1
        else:
            label = "wrong"

        labels.append(label)

    n = len(labels)
    counts = Counter(labels)

    correct_total = counts["correct"] + counts["same_person_duplicate"]

    print("| Metric | Value |")
    print("|---|---:|")
    print(f"| frames | {n} |")
    print(f"| strict_correct_ratio | {counts['correct']/n if n else 0:.3f} |")
    print(f"| alias_correct_ratio | {correct_total/n if n else 0:.3f} |")
    print(f"| same_person_duplicate_ratio | {counts['same_person_duplicate']/n if n else 0:.3f} |")
    print(f"| wrong_ratio | {counts['wrong']/n if n else 0:.3f} |")
    print(f"| lost_ratio | {counts['lost']/n if n else 0:.3f} |")
    print()
    print("counts:", dict(counts))


if __name__ == "__main__":
    main()
