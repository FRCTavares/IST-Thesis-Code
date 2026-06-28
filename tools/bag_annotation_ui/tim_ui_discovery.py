#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


BAG_ROOTS = [
    "bags/reference",
    "bags/replay",
    "bags/review",
    "bags/annotation_inputs",
    "bags/source",
    "artifacts/bags",  # legacy fallback
]

ANNOTATION_ROOTS = [
    "docs/data/annotations",
    "docs/annotations",  # legacy fallback
]


def _role_rank(path: str) -> tuple[int, str]:
    low = path.lower()

    if low.startswith("bags/reference/"):
        role = 0
    elif low.startswith("bags/replay/"):
        role = 1
    elif low.startswith("bags/review/"):
        role = 2
    elif low.startswith("bags/annotation_inputs/"):
        role = 3
    elif low.startswith("bags/source/"):
        role = 4
    elif low.startswith("artifacts/bags/"):
        role = 9
    else:
        role = 99

    return role, path


def discover_bags(repo_root: Path | str = ".") -> list[str]:
    repo_root = Path(repo_root)

    out: list[str] = []
    seen: set[str] = set()

    for root_name in BAG_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue

        for metadata in root.rglob("metadata.yaml"):
            bag = metadata.parent
            try:
                rel = str(bag.relative_to(repo_root))
            except ValueError:
                rel = str(bag)

            if rel in seen:
                continue

            seen.add(rel)
            out.append(rel)

    return sorted(out, key=_role_rank)


def discover_annotations(repo_root: Path | str = ".") -> list[str]:
    repo_root = Path(repo_root)

    out: list[str] = []
    seen: set[str] = set()

    for root_name in ANNOTATION_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue

        for csv_path in root.rglob("*.csv"):
            try:
                rel = str(csv_path.relative_to(repo_root))
            except ValueError:
                rel = str(csv_path)

            if rel in seen:
                continue

            seen.add(rel)
            out.append(rel)

    return sorted(out)
