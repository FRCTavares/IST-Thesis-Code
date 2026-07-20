#!/usr/bin/env python3
"""Build the curated TIM-MARS canonical evidence catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CATALOGUE_PATH = ROOT / "docs/data/catalogue/tim_eval_catalogue.yaml"

P002_ROOT = ROOT / "reports/p002_historical_deepsort_93e047b5_2026_07_19"
P014_ROOT = ROOT / "reports/p014_protected_appearance_2026_07_17"
P004_OCSORT_ROOT = ROOT / "reports/p004_ocsort_tim_1b7dc400_2026_07_20"
P004_MATRIX_ROOT = ROOT / "reports/p004_tim_matrix_1b7dc400_2026_07_20"

CANONICAL_CONFIG_SHA256 = (
    "16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655"
)
MARS_MODEL_SHA256 = (
    "e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1"
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object."""
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def relative_repository_path(value: str) -> str:
    """Normalise an absolute or relative repository path."""
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()

    marker = "/Thesis-Code/"
    text = path.as_posix()
    if marker not in text:
        raise ValueError(f"Path is outside the thesis repository: {value}")
    return text.split(marker, 1)[1]


def annotation_contract(
    path_value: str,
    expected_sha256: str,
) -> dict[str, Any]:
    """Return a validated annotation reference."""
    path = ROOT / path_value
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Annotation digest mismatch for {path_value}: "
            f"{actual_sha256} != {expected_sha256}"
        )
    return {
        "path": path_value,
        "sha256": actual_sha256,
    }


def metadata_lineage(
    metadata_path: Path,
    *,
    selected_track_id: int,
    require_resolved_runtime: bool = False,
) -> dict[str, Any]:
    """Extract exact replay lineage from a tracked metadata sidecar."""
    metadata = load_json(metadata_path)

    runtime_id = metadata.get("runtime", {}).get("selected_track_id")
    if runtime_id != selected_track_id:
        raise ValueError(
            f"Selected-ID mismatch in {metadata_path}: "
            f"{runtime_id} != {selected_track_id}"
        )

    config_sha256 = metadata.get("canonical_config", {}).get("sha256")
    if config_sha256 != CANONICAL_CONFIG_SHA256:
        raise ValueError(
            f"Canonical-config mismatch in {metadata_path}: {config_sha256}"
        )

    model_sha256 = metadata.get("model", {}).get("sha256")
    if model_sha256 != MARS_MODEL_SHA256:
        raise ValueError(
            f"MARS-model mismatch in {metadata_path}: {model_sha256}"
        )

    source_manifest = metadata.get("source_manifest")
    if not isinstance(source_manifest, list) or not source_manifest:
        raise ValueError(f"Missing source manifest in {metadata_path}")

    for item in source_manifest:
        if not item.get("name") or not item.get("sha256"):
            raise ValueError(
                f"Incomplete source-manifest item in {metadata_path}: {item}"
            )

    lineage = {
        "source_bag": relative_repository_path(metadata["input_bag"]),
        "output_bag": relative_repository_path(metadata["output_bag"]),
        "selected_track_id": selected_track_id,
        "replay_repository_commit": metadata["repository"]["commit"],
        "canonical_config_sha256": config_sha256,
        "mars_model_sha256": model_sha256,
        "replay_metadata": {
            "path": metadata_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(metadata_path),
        },
        "source_manifest": source_manifest,
    }

    if require_resolved_runtime:
        if metadata.get("schema_version") != 3:
            raise ValueError(
                f"Expected replay metadata schema 3 in {metadata_path}"
            )

        if metadata.get("repository", {}).get("status_short") != []:
            raise ValueError(
                f"Replay repository state is not clean in {metadata_path}"
            )

        resolved = metadata.get("resolved_runtime")
        if not isinstance(resolved, dict):
            raise ValueError(
                f"Missing resolved-runtime reference in {metadata_path}"
            )

        runtime_path = metadata_path.parent / resolved["file"]
        fingerprint_path = (
            metadata_path.parent / resolved["fingerprint_file"]
        )

        runtime_sha256 = sha256_file(runtime_path)
        if runtime_sha256 != resolved["sha256"]:
            raise ValueError(
                f"Resolved-runtime digest mismatch in {metadata_path}"
            )

        expected_fingerprint = (
            f"{runtime_sha256}  {runtime_path.name}\n"
        )
        if fingerprint_path.read_text(encoding="utf-8") != expected_fingerprint:
            raise ValueError(
                f"Resolved-runtime fingerprint mismatch in {metadata_path}"
            )

        runtime = load_json(runtime_path)
        if runtime.get("schema_version") != 2:
            raise ValueError(
                f"Expected resolved-runtime schema 2 in {runtime_path}"
            )

        lineage["resolved_runtime"] = {
            "path": runtime_path.relative_to(ROOT).as_posix(),
            "sha256": runtime_sha256,
            "fingerprint_path": (
                fingerprint_path.relative_to(ROOT).as_posix()
            ),
            "fingerprint_sha256": sha256_file(fingerprint_path),
        }

    return lineage


def evaluation_reference(path: Path) -> dict[str, str]:
    """Return a tracked evaluator-output reference."""
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
    }


def build_p002_row() -> dict[str, Any]:
    """Build the clean historical DeepSORT reproduction row."""
    comparison_path = P002_ROOT / "comparison.json"
    metadata_path = P002_ROOT / "current/tim_replay_metadata.json"
    evaluation_path = P002_ROOT / "current/evaluation/summary.csv"

    comparison = load_json(comparison_path)
    current = comparison["current_canonical"]
    annotation = comparison["annotation"]

    row = {
        "id": "p002_deepsort_current_canonical",
        "status": "final evidence",
        "claim_status": "historical failure reproduction",
        "sequence": "may_hard_reentry",
        "tracker": "deepsort",
        "method": "tim_mars",
        "selection_provenance": "annotation-driven diagnostic",
        "replay_scope": "memory-only replay",
        "annotation": annotation_contract(
            annotation["path"],
            annotation["sha256"],
        ),
        "lineage": metadata_lineage(
            metadata_path,
            selected_track_id=1,
        ),
        "report": {
            "path": comparison_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(comparison_path),
            "row_reference": "current_canonical",
        },
        "evaluation": evaluation_reference(evaluation_path),
        "result": {
            "raw": current["raw"],
            "tim": current["tim"],
        },
        "claim_boundary": (
            "Tracker-specific DeepSORT reproduction. It does not support "
            "tracker-independent correctness claims."
        ),
    }

    if comparison["commit"] != row["lineage"]["replay_repository_commit"]:
        raise ValueError("P0.2 comparison and replay commits disagree")

    return row


def build_p004_matrix_rows() -> list[dict[str, Any]]:
    """Build the autonomous four-tracker hard-reentry rows."""
    summary_path = P004_MATRIX_ROOT / "canonical_matrix_summary.json"
    summary = load_json(summary_path)

    if summary["canonical_config_sha256"] != CANONICAL_CONFIG_SHA256:
        raise ValueError("P0.4 matrix canonical-config digest mismatch")

    rows: list[dict[str, Any]] = []

    for source_row in summary["rows"]:
        tracker = source_row["tracker"]
        selected_track_id = int(source_row["selected_track_id"])
        metadata_path = (
            P004_MATRIX_ROOT / tracker / "tim_replay_metadata.json"
        )
        evaluation_path = (
            P004_MATRIX_ROOT / tracker / "evaluation/summary.csv"
        )

        lineage = metadata_lineage(
            metadata_path,
            selected_track_id=selected_track_id,
            require_resolved_runtime=True,
        )

        if lineage["replay_repository_commit"] != summary["repository_commit"]:
            raise ValueError(
                f"P0.4 matrix commit mismatch for {tracker}"
            )

        rows.append(
            {
                "id": f"p004_matrix_{tracker}",
                "status": "final evidence",
                "claim_status": "canonical safety rejection",
                "sequence": "may_hard_reentry",
                "tracker": tracker,
                "method": "tim_mars",
                "selection_provenance": "autonomous",
                "replay_scope": "memory-only replay",
                "annotation": annotation_contract(
                    source_row["annotation"],
                    source_row["annotation_sha256"],
                ),
                "lineage": {
                    **lineage,
                    "source_tracker_semantic_sha256": (
                        source_row["source_tracker_semantic_sha256"]
                    ),
                    "tim_semantic_sha256": (
                        source_row["tim_semantic_sha256"]
                    ),
                },
                "report": {
                    "path": summary_path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(summary_path),
                    "row_reference": f"rows[tracker={tracker}]",
                },
                "evaluation": evaluation_reference(evaluation_path),
                "result": {
                    "raw": {
                        "correct_ratio": source_row["raw_correct_ratio"],
                        "wrong_ratio": source_row["raw_wrong_ratio"],
                        "lost_ratio": source_row["raw_lost_ratio"],
                        "correct_duration_s": (
                            source_row["raw_correct_duration_s"]
                        ),
                        "wrong_duration_s": (
                            source_row["raw_wrong_duration_s"]
                        ),
                        "lost_duration_s": (
                            source_row["raw_lost_duration_s"]
                        ),
                        "absent_output_duration_s": (
                            source_row["raw_absent_output_duration_s"]
                        ),
                    },
                    "tim": {
                        "correct_ratio": source_row["tim_correct_ratio"],
                        "wrong_ratio": source_row["tim_wrong_ratio"],
                        "lost_ratio": source_row["tim_lost_ratio"],
                        "correct_duration_s": (
                            source_row["tim_correct_duration_s"]
                        ),
                        "wrong_duration_s": (
                            source_row["tim_wrong_duration_s"]
                        ),
                        "lost_duration_s": (
                            source_row["tim_lost_duration_s"]
                        ),
                        "absent_output_duration_s": (
                            source_row["tim_absent_output_duration_s"]
                        ),
                    },
                    "delta": {
                        "correct_duration_s": (
                            source_row["correct_duration_delta_s"]
                        ),
                        "wrong_duration_s": (
                            source_row["wrong_duration_delta_s"]
                        ),
                        "lost_duration_s": (
                            source_row["lost_duration_delta_s"]
                        ),
                        "absent_output_duration_s": (
                            source_row["absent_output_delta_s"]
                        ),
                    },
                    "safety": {
                        "tolerance_s": source_row["safety_tolerance_s"],
                        "unsafe": source_row["unsafe_degradation"],
                        "reason": source_row["unsafe_reason"],
                    },
                },
                "claim_boundary": (
                    "Within-tracker raw-versus-TIM comparison only. "
                    "Autonomous target selection differs across trackers, "
                    "so absolute cross-tracker ranking is not claimed."
                ),
            }
        )

    return rows


def build_p004_ocsort_rows() -> list[dict[str, Any]]:
    """Build the repeated OC-SORT sequence rows."""
    summary_path = (
        P004_OCSORT_ROOT / "canonical_ocsort_sequence_summary.json"
    )
    summary = load_json(summary_path)

    if summary["canonical_config_sha256"] != CANONICAL_CONFIG_SHA256:
        raise ValueError("P0.4 OC-SORT canonical-config digest mismatch")

    rows: list[dict[str, Any]] = []

    for sequence, sequence_data in summary["sequences"].items():
        selected_track_id = int(summary["selected_track_id"])
        metadata_path = (
            P004_OCSORT_ROOT / f"{sequence}_r1/tim_replay_metadata.json"
        )
        evaluation_path = (
            P004_OCSORT_ROOT / f"{sequence}_r1/evaluation/summary.csv"
        )

        lineage = metadata_lineage(
            metadata_path,
            selected_track_id=selected_track_id,
            require_resolved_runtime=True,
        )

        expected_commit = summary["tim_replay_repository_commit"]
        if lineage["replay_repository_commit"] != expected_commit:
            raise ValueError(
                f"P0.4 OC-SORT commit mismatch for {sequence}"
            )

        rows.append(
            {
                "id": f"p004_ocsort_{sequence}",
                "status": "final evidence",
                "claim_status": "canonical safety rejection",
                "sequence": sequence,
                "tracker": "ocsort",
                "method": "tim_mars",
                "selection_provenance": "annotation-driven diagnostic",
                "replay_scope": "memory-only replay",
                "annotation": annotation_contract(
                    sequence_data["annotation"],
                    sequence_data["annotation_sha256"],
                ),
                "lineage": {
                    **lineage,
                    "tracker_freeze_repository_commit": (
                        summary["tracker_freeze_repository_commit"]
                    ),
                    "event_evaluator_repository_commit": (
                        summary["event_evaluator_repository_commit"]
                    ),
                    "generated_semantic_sha256": (
                        sequence_data["generated_semantic_sha256"]
                    ),
                },
                "report": {
                    "path": summary_path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(summary_path),
                    "row_reference": f"sequences.{sequence}",
                },
                "evaluation": evaluation_reference(evaluation_path),
                "result": {
                    "raw": sequence_data["raw"],
                    "tim": sequence_data["tim"],
                    "delta": sequence_data["delta"],
                    "safety": sequence_data["safety"],
                    "repeatability": sequence_data["repeatability"],
                },
                "claim_boundary": (
                    "OC-SORT tracker-specific diagnostic with a fixed "
                    "selected ID and tracker-specific manual annotation."
                ),
            }
        )

    return rows


def build_catalogue() -> dict[str, Any]:
    """Build the complete curated evidence catalogue."""
    final_rows = [
        build_p002_row(),
        *build_p004_matrix_rows(),
        *build_p004_ocsort_rows(),
    ]

    selection_counts: dict[str, int] = {}
    replay_counts: dict[str, int] = {}

    for row in final_rows:
        selection = row["selection_provenance"]
        replay = row["replay_scope"]
        selection_counts[selection] = selection_counts.get(selection, 0) + 1
        replay_counts[replay] = replay_counts.get(replay, 0) + 1

    return {
        "schema_version": 2,
        "generated_by": "tools/catalogue/build_tim_eval_catalogue.py",
        "source_of_truth": (
            "Tracked report summaries and their per-run provenance sidecars."
        ),
        "classification_contract": {
            "selection_provenance": [
                "autonomous",
                "annotation-driven diagnostic",
            ],
            "replay_scope": [
                "memory-only replay",
                "full-pipeline replay",
            ],
            "note": (
                "Selection provenance and replay scope are orthogonal. "
                "Each final row must contain one value from each axis."
            ),
        },
        "canonical_fingerprints": {
            "tim_mars_config_sha256": CANONICAL_CONFIG_SHA256,
            "mars_model_sha256": MARS_MODEL_SHA256,
        },
        "summary": {
            "final_row_count": len(final_rows),
            "selection_provenance_counts": selection_counts,
            "replay_scope_counts": replay_counts,
            "full_pipeline_final_row_count": sum(
                row["replay_scope"] == "full-pipeline replay"
                for row in final_rows
            ),
        },
        "final_rows": final_rows,
        "diagnostic_reports": [
            {
                "id": "p014_protected_appearance",
                "status": "diagnostic only",
                "path": (
                    "reports/p014_protected_appearance_2026_07_17/"
                    "canonical_comparison.tsv"
                ),
                "sha256": sha256_file(
                    P014_ROOT / "canonical_comparison.tsv"
                ),
                "reason": (
                    "The aggregate table records A/B results and "
                    "configuration fingerprints but does not preserve "
                    "source bag, annotation, selected ID, replay commit, "
                    "and replay-metadata digest for each row. It "
                    "therefore supports the implementation decision but "
                    "is not a canonical final-row package."
                ),
            }
        ],
        "excluded_candidates": [
            {
                "id": "legacy_seq02_catalogue_rows",
                "sequence": "seq02",
                "status": "non-final",
                "reason": (
                    "The former catalogue promoted missing target-0 replay "
                    "paths. The current ByteTrack annotation expects IDs "
                    "1, 15, 23, 28, 40, and 46, so target 0 is not a proven "
                    "correct-target lineage."
                ),
                "annotation": annotation_contract(
                    "docs/data/annotations/june_hard_sequences/"
                    "seq02_bytetrack.csv",
                    (
                        "ae331a582793221be0bf2aca4bec622be0130bb64559456767"
                        "baf0797d179fe0"
                    ),
                ),
                "expected_target_ids": [1, 15, 23, 28, 40, 46],
            },
            {
                "id": "official_full_pipeline_field_bags",
                "status": "non-final",
                "replay_scope": "full-pipeline replay",
                "reason": (
                    "Fresh or relocated full-pipeline runs are not promoted "
                    "because tracker IDs are not guaranteed to match the "
                    "existing manual annotations. No full-pipeline final row "
                    "is currently supported."
                ),
            },
            {
                "id": "legacy_eval_catalogue",
                "status": "replaced",
                "reason": (
                    "The previous catalogue declared a generator that never "
                    "existed in Git, contained 30 promoted rows whose paths "
                    "were all absent, and included annotation metadata that "
                    "disagreed with the current CSV files."
                ),
            },
        ],
    }


def render_catalogue(data: dict[str, Any]) -> str:
    """Serialise the catalogue deterministically."""
    header = (
        "# Canonical TIM-MARS evidence catalogue.\n"
        "# Regenerate with: "
        "python3 tools/catalogue/build_tim_eval_catalogue.py\n"
        "# Validate with: "
        "python3 tools/catalogue/build_tim_eval_catalogue.py --check\n"
    )
    body = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    return header + body


def main() -> int:
    """Build or validate the committed catalogue."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed catalogue differs from generated output.",
    )
    args = parser.parse_args()

    rendered = render_catalogue(build_catalogue())

    if args.check:
        if not CATALOGUE_PATH.exists():
            print(f"Missing catalogue: {CATALOGUE_PATH}")
            return 1

        committed = CATALOGUE_PATH.read_text(encoding="utf-8")
        if committed != rendered:
            print(
                "Committed TIM evidence catalogue is stale. "
                "Regenerate it with this script."
            )
            return 1

        print("TIM evidence catalogue is current.")
        return 0

    CATALOGUE_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {CATALOGUE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
