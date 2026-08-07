#!/usr/bin/env python3
"""Add the four internal ROS 2 sequences to the Issue #30 first-phase manifest.

Unlike the external MOT-style datasets, the ROS 2 development sequences have
no generic per-sequence discovery tool: there are exactly four of them, they
are already frozen as the ``development`` set in
``docs/data/splits/tim_mars_split_v1.json``, and their provenance (which bag,
which tracker, which annotation) required a one-off forensic check because
two of the four (``seq03_crossing_ambiguity``, ``seq04_occlusion_no_exit``)
had existing Issue #26 evidence generated against an OC-SORT-tracked replay
chain rather than ByteTrack. This module therefore hand-encodes verified
per-sequence facts rather than deriving them from a shared profiler.

No tracker or TIM-MARS *outcome* informed sequence, target or frame-range
selection here; the values below are drawn from already-frozen dataset split
identities (``selected_target_id`` / initial correct-track annotation),
documented capture configuration (``flight_metadata.txt``), and measured bag
duration and message counts -- not from evaluation results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    ROOT / "docs" / "data" / "external_benchmark" / "sequence_manifest.json"
)
DEFAULT_SCHEMA = (
    ROOT / "docs" / "data" / "external_benchmark" / "manifest.schema.json"
)

# Frozen initialization-matching defaults, matching the external sequences
# (tools/analysis/external_target_initialization.py InitializationConfig).
INITIALIZATION_MINIMUM_IOU = 0.50
INITIALIZATION_MINIMUM_MARGIN = 0.10
INITIALIZATION_CONFIRMATION_FRAMES = 2
INITIALIZATION_WINDOW_FRAMES = 10

ADAPTER_SCHEMA_VERSION = 1

# Verified per-sequence facts. image_count/bag_duration_s come from measured
# tim_replay_metadata.json / metadata.yaml values (2026-08-07). dataset_identity
# is the initial correct_target_track_id from each sequence's own ByteTrack
# annotation CSV (matching tim_mars_split_v1.json selected_target_id for May
# and Seq01; Seq03 and Seq04 use their own first-row bytetrack annotation
# since tim_mars_split_v1's recorded selected_target_id of 1 for those two
# refers to the different OC-SORT replay chain, not this ByteTrack one).
ROS2_SEQUENCES = [
    {
        "sequence_name": "may_hard_reentry",
        "primary_challenge": "reentry",
        "event_categories": ["reentry", "tracker_fragmentation"],
        "official_reference": (
            "docs/data/splits/tim_mars_split_v1.json#dev_may_hard_reentry"
        ),
        "bag_local_relative_path": (
            "bags/replay/p018_hard_negative_lifecycle_6ba28c61_2026_07_28/"
            "may_hard_reentry"
        ),
        "input_bag_relative_path": (
            "bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__"
            "tim_mars_v4_margin010__target_1"
        ),
        "annotation_relative_path": (
            "docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv"
        ),
        "dataset_identity": 1,
        "image_count": 360,
        "bag_duration_s": 67.610490128,
        "image_width": 640,
        "image_height": 640,
        "generated_semantic_sha256": (
            "836d73cbf2a47ddbec26adcb4dc9b71765defd0685e93babfc6714287195458c"
        ),
    },
    {
        "sequence_name": "seq01_clean",
        "primary_challenge": "clean_tracking",
        "event_categories": ["clean_tracking"],
        "official_reference": (
            "docs/data/splits/tim_mars_split_v1.json#dev_june_seq01"
        ),
        "bag_local_relative_path": (
            "bags/replay/p018_hard_negative_lifecycle_6ba28c61_2026_07_28/"
            "seq01_clean"
        ),
        "input_bag_relative_path": (
            "bags/source/official_flights/2026-06-19/seq01_clean_four_person/"
            "full_pipeline/2026-06-19__12-45-45__video__2026-06-19__official__"
            "seq01__clean_four_person__yolov8s_bytetrack_tim_mars"
        ),
        "annotation_relative_path": (
            "docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv"
        ),
        "dataset_identity": 1,
        "image_count": 807,
        "bag_duration_s": 107.962569547,
        "image_width": 640,
        "image_height": 640,
        "generated_semantic_sha256": (
            "55ab81da4e4b96876c84fe778effe2c357dafc24d837c9a2af92a046d92b87e9"
        ),
    },
    {
        "sequence_name": "seq03_crossing",
        "primary_challenge": "crowd_crossing",
        "event_categories": [
            "crowd_crossing",
            "identity_confusion",
            "tracker_fragmentation",
        ],
        "official_reference": (
            "docs/data/splits/tim_mars_split_v1.json#dev_june_seq03_ocsort"
            "(re-evaluated on the ByteTrack full_pipeline bag; the split's"
            " own OC-SORT replay chain does not satisfy Issue #30's"
            " ByteTrack-baseline requirement, see Slice 15)"
        ),
        "bag_local_relative_path": (
            "bags/replay/p030_broader_sequences_bytetrack_2026_08_07/"
            "seq03_crossing"
        ),
        "input_bag_relative_path": (
            "bags/source/official_flights/2026-06-19/seq03_crossing_ambiguity/"
            "full_pipeline/2026-06-19__12-57-48__video__2026-06-19__official__"
            "seq03__four_person_crossing_ambiguity__yolov8s_bytetrack_tim_mars"
        ),
        "annotation_relative_path": (
            "docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv"
        ),
        "dataset_identity": 2,
        "image_count": 679,
        "bag_duration_s": 97.476824776,
        "image_width": 640,
        "image_height": 640,
        "generated_semantic_sha256": (
            "d90b8da37ba77f5197e3c473fdaf044504b4524887cf477049030ca454fd617b"
        ),
    },
    {
        "sequence_name": "seq04_occlusion",
        "primary_challenge": "long_occlusion",
        "event_categories": [
            "long_occlusion",
            "physical_absence",
            "reentry",
            "tracker_fragmentation",
        ],
        "official_reference": (
            "docs/data/splits/tim_mars_split_v1.json#dev_june_seq04_ocsort"
            "(re-evaluated on the ByteTrack full_pipeline bag; the split's"
            " own OC-SORT replay chain does not satisfy Issue #30's"
            " ByteTrack-baseline requirement, see Slice 15)"
        ),
        "bag_local_relative_path": (
            "bags/replay/p030_broader_sequences_bytetrack_2026_08_07/"
            "seq04_occlusion"
        ),
        "input_bag_relative_path": (
            "bags/source/official_flights/2026-06-19/seq04_occlusion_no_exit/"
            "full_pipeline/2026-06-19__13-01-36__video__2026-06-19__official__"
            "seq04__four_person_occlusion_no_exit__yolov8s_bytetrack_tim_mars"
        ),
        "annotation_relative_path": (
            "docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv"
        ),
        "dataset_identity": 1,
        "image_count": 467,
        "bag_duration_s": 66.216464757,
        "image_width": 640,
        "image_height": 640,
        "generated_semantic_sha256": (
            "3f61a24494cc242dca998b7741508d64177109c53b22136746a38dac472c4d1e"
        ),
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def build_entry(
    spec: dict[str, Any],
    *,
    repository_root: Path,
    repository_commit: str | None,
) -> dict[str, Any]:
    frame_rate = spec["image_count"] / spec["bag_duration_s"]
    annotation_path = repository_root / spec["annotation_relative_path"]
    annotation_sha256 = sha256_file(annotation_path)

    return {
        "id": f"ros2_internal_development_{spec['sequence_name']}",
        "dataset": "ros2_internal",
        "sequence_name": spec["sequence_name"],
        "split": "development",
        "role": "development_evidence",
        "status": "selected",
        "source": {
            "official_reference": spec["official_reference"],
            "local_relative_path": spec["bag_local_relative_path"],
            "version": (
                f"deterministic_tim_replay:"
                f"{spec['generated_semantic_sha256'][:16]}"
            ),
            "archive_sha256": None,
        },
        "frame_contract": {
            "source_index_base": 0,
            "source_start_frame": 0,
            "source_end_frame_inclusive": spec["image_count"] - 1,
            "normalized_start_index": 0,
            "normalized_end_index_inclusive": spec["image_count"] - 1,
            "frame_rate": frame_rate,
        },
        "image": {
            "width": spec["image_width"],
            "height": spec["image_height"],
            "camera_motion": "moving",
        },
        "target": {
            "dataset_identity": spec["dataset_identity"],
            "initialization_start_frame": 0,
            "initialization_end_frame_inclusive": min(
                INITIALIZATION_WINDOW_FRAMES - 1,
                spec["image_count"] - 1,
            ),
            "initialization_rule": (
                "physical_identity_fixed_to_annotated_initial_correct_"
                "target_track_id_v1"
            ),
            "candidate_match_rule": (
                "frozen_target_unique_iou_confirmation_v1"
            ),
            "minimum_match_iou": INITIALIZATION_MINIMUM_IOU,
            "minimum_match_margin": INITIALIZATION_MINIMUM_MARGIN,
            "confirmation_frames": INITIALIZATION_CONFIRMATION_FRAMES,
            "initial_tracker_identity": spec["dataset_identity"],
            "fixed_after_initialization": True,
            "reselection_enabled": False,
            "minimum_visible_frames": 30,
            "selected_before_outcome_review": True,
        },
        "scene": {
            "approximate_people": 4,
            "primary_challenge": spec["primary_challenge"],
        },
        "event_categories": spec["event_categories"],
        "evaluation_modes": ["detector_bytetrack_tim"],
        "selection_reason": (
            "One of the four sequences already frozen as the `development` "
            "set in docs/data/splits/tim_mars_split_v1.json, reused here as "
            "the fixed internal ROS 2 benchmark case set. The physical "
            "target identity is the initial correct_target_track_id from "
            "the sequence's own official ByteTrack annotation CSV, not a "
            "TIM-MARS outcome. Only ByteTrack-tracked bags are used; where "
            "the split's existing replay chain used OC-SORT instead "
            "(seq03, seq04), a fresh deterministic TIM-MARS replay was "
            "generated against the sequence's official ByteTrack "
            "full_pipeline bag (Slice 15) so the raw baseline is genuinely "
            "ByteTrack, matching Issue #30's explicit requirement."
        ),
        "exclusions": [],
        "provenance": {
            "adapter": "run_deterministic_tim_replay.py",
            "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
            "annotation_sha256": annotation_sha256,
            "repository_commit": repository_commit,
        },
    }


def merge_manifest_entries(
    manifest: dict[str, Any],
    new_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    new_ids = {entry["id"] for entry in new_entries}
    kept = [
        entry
        for entry in manifest["sequences"]
        if entry["id"] not in new_ids
    ]
    manifest = dict(manifest)
    manifest["sequences"] = kept + new_entries
    return manifest


def main() -> int:
    import subprocess

    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    arguments = parser.parse_args()

    repository_root = arguments.repository_root.resolve()

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    repository_commit = result.stdout.strip() or None

    entries = [
        build_entry(
            spec,
            repository_root=repository_root,
            repository_commit=repository_commit,
        )
        for spec in ROS2_SEQUENCES
    ]

    manifest = json.loads(
        arguments.manifest.read_text(encoding="utf-8")
    )
    manifest = merge_manifest_entries(manifest, entries)

    if arguments.freeze:
        import datetime

        manifest["status"] = "frozen"
        manifest["frozen_date"] = datetime.date.today().isoformat()
        manifest["manifest_commit"] = repository_commit
        for entry in manifest["sequences"]:
            if entry["status"] == "selected":
                entry["status"] = "frozen"

    manifest["sequences"] = sorted(
        manifest["sequences"],
        key=lambda entry: entry["id"],
    )

    import jsonschema

    schema = json.loads(arguments.schema.read_text(encoding="utf-8"))
    jsonschema.validate(instance=manifest, schema=schema)

    rendered = json.dumps(manifest, indent=2, sort_keys=False) + "\n"

    if arguments.write:
        arguments.manifest.write_text(rendered, encoding="utf-8")
        print(f"wrote {len(entries)} ROS2 entries to {arguments.manifest}")
        print(f"manifest status: {manifest['status']}")
    else:
        print(rendered)

    for entry in entries:
        print(
            f"added {entry['id']}: identity="
            f"{entry['target']['dataset_identity']} "
            f"frame_rate={entry['frame_contract']['frame_rate']:.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
