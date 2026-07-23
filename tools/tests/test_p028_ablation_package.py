"""Contracts for the promoted P0.28 ablation package."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "docs"
    / "results"
    / "selected_target_tracking"
    / "p028_component_ablation_development"
)

AGGREGATE = PACKAGE / "matrix_aggregate_annotated_id.csv"
ALL_SEQUENCES = PACKAGE / "matrix_all_sequences_annotated_id.csv"
AGGREGATE_JSON = PACKAGE / "matrix_aggregate_annotated_id.json"
PROVENANCE = PACKAGE / "run_provenance.json"
LOCK = PACKAGE / "ablation_lock.json"
README = PACKAGE / "README.md"
HASHES = PACKAGE / "SHA256SUMS"

EXPECTED_ROWS = (
    "raw_tracker",
    "geometry_only",
    "geometry_positive_appearance",
    "geometry_appearance_margin",
    "geometry_hard_negatives",
    "geometry_persistence",
    "final_simplified_tim_mars",
)

EXPECTED_SEQUENCES = (
    "dev_may_hard_reentry",
    "dev_june_seq01",
    "dev_june_seq03_ocsort",
    "dev_june_seq04_ocsort",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def test_package_contains_promoted_artifacts():
    required = (
        README,
        AGGREGATE,
        ALL_SEQUENCES,
        AGGREGATE_JSON,
        PROVENANCE,
        LOCK,
        HASHES,
    )

    for path in required:
        assert path.is_file()


def test_complete_seven_row_matrix_is_tracked():
    aggregate = read_csv(AGGREGATE)
    all_rows = read_csv(ALL_SEQUENCES)

    assert len(aggregate) == 7
    assert len(all_rows) == 28

    assert tuple(
        row["row_id"]
        for row in aggregate
    ) == EXPECTED_ROWS

    counts = Counter(
        row["sequence_id"]
        for row in all_rows
    )

    assert set(counts) == set(EXPECTED_SEQUENCES)

    for sequence in EXPECTED_SEQUENCES:
        assert counts[sequence] == 7

        row_ids = tuple(
            row["row_id"]
            for row in all_rows
            if row["sequence_id"] == sequence
        )

        assert row_ids == EXPECTED_ROWS


def test_json_and_provenance_are_valid():
    aggregate = json.loads(
        AGGREGATE_JSON.read_text(encoding="utf-8")
    )

    assert len(aggregate) == 7

    assert json.loads(
        PROVENANCE.read_text(encoding="utf-8")
    )

    assert json.loads(
        LOCK.read_text(encoding="utf-8")
    )


def test_copied_artifact_hashes_match():
    expected = {}

    for line in HASHES.read_text(
        encoding="utf-8"
    ).splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[filename.strip()] = digest

    actual_files = (
        AGGREGATE,
        ALL_SEQUENCES,
        AGGREGATE_JSON,
        PROVENANCE,
        LOCK,
    )

    assert set(expected) == {
        path.name
        for path in actual_files
    }

    for path in actual_files:
        assert sha256(path) == expected[path.name]


def test_readme_preserves_correction_boundary():
    text = README.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    normalized_lower = normalized.lower()

    required_text = (
        "not held out",
        "annotated-id evaluator",
        "complete seven-row spatial matrix was not retained",
        "later corrected dual-oracle audit",
        "different evidence versions",
        "must not be substituted",
        "zero wrong-target output",
        "h01-h03 remain required",
    )

    for value in required_text:
        assert value in normalized_lower

    for value in ("2.750", "1.300"):
        assert value in normalized

def test_all_rows_and_sequences_are_human_readable():
    text = README.read_text(encoding="utf-8")

    for row_id in EXPECTED_ROWS:
        assert f"`{row_id}`" in text

    required_titles = (
        "May hard re-entry",
        "June Seq01 clean four-person sequence",
        "June Seq03 OC-SORT crossing sequence",
        "June Seq04 OC-SORT occlusion sequence",
    )

    for title in required_titles:
        assert title in text


def test_package_is_linked_from_canonical_indexes():
    paths = (
        ROOT / "docs" / "README.md",
        ROOT / "docs" / "results" / "README.md",
        ROOT / "docs" / "data" / "ablations" / "README.md",
        ROOT / "docs" / "design" / "tim_tooling_index.md",
        ROOT
        / "docs"
        / "algorithm"
        / "tim_mars_evidence_versions.md",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "p028_component_ablation_development" in text


def test_closed_issue_is_removed_from_queue():
    text = (
        ROOT / "docs" / "TODO_LIST.md"
    ).read_text(encoding="utf-8")

    assert "[#57 —" not in text
    assert "Open executable issues: **28**." in text
