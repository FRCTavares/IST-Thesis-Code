#!/usr/bin/env python3
"""Resolve pre-migration Git commit IDs to their equivalent rewritten IDs.

Historical experiment and prospective-freeze records retain the commit IDs
that were recorded at the time.  A later metadata-only Git-history migration
changed commit object IDs without changing tracked source trees.

Git operations against those preserved historical authorities must therefore
translate the recorded ID to the equivalent commit in the rewritten history.
The complete deterministic mapping is retained in
docs/provenance/git_history_migration_20260917.tsv.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPING_PATH = (
    _REPO_ROOT
    / "docs/provenance/git_history_migration_20260917.tsv"
)
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@lru_cache(maxsize=1)
def _history_mapping() -> dict[str, str]:
    """Load and validate the metadata-only Git-history translation."""
    if not _MAPPING_PATH.is_file():
        raise RuntimeError(
            f"Git history migration map is missing: {_MAPPING_PATH}"
        )

    mapping: dict[str, str] = {}

    for lineno, raw in enumerate(
        _MAPPING_PATH.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not raw.strip():
            continue

        fields = raw.split("\t")

        if len(fields) != 2:
            raise RuntimeError(
                f"invalid Git history mapping line {lineno}"
            )

        old, new = fields

        if (
            not _FULL_SHA_RE.fullmatch(old)
            or not _FULL_SHA_RE.fullmatch(new)
        ):
            raise RuntimeError(
                f"invalid Git commit ID on mapping line {lineno}"
            )

        if old in mapping and mapping[old] != new:
            raise RuntimeError(
                f"conflicting mapping for Git commit {old}"
            )

        mapping[old] = new

    return mapping


def resolve_git_commit(commit: str) -> str:
    """Return the rewritten equivalent of a preserved historical commit ID."""
    return _history_mapping().get(commit, commit)
