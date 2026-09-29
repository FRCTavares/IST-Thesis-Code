#!/usr/bin/env python3
"""GT-only VisDrone selected-person corpus audit for Issue #125.

This tool is deliberately outcome-blind. It may read only:
- VisDrone source images;
- VisDrone ground-truth annotations;
- explicit eligibility parameters supplied on the command line.

It must not read detector, tracker, Target-ReID, TIM-MARS, or previous result
artifacts. Its purpose is to reconcile the source/annotation frame domain and
prepare a deterministic candidate episode manifest before any architecture
outcome is inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from external_tracking_dataset import (  # noqa: E402
    ExternalObjectAnnotation,
    SequenceGeometry,
    parse_visdrone_annotations,
)

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


@dataclass(frozen=True)
class EligibilityConfig:
    minimum_selection_height_px: float = 20.0
    minimum_target_present_frames: int = 30
    maximum_selection_truncation: int = 1
    maximum_selection_occlusion: int = 1
    initialization_window_frames: int = 10

    def __post_init__(self) -> None:
        if self.minimum_selection_height_px <= 0.0:
            raise ValueError("minimum_selection_height_px must be positive")
        if self.minimum_target_present_frames <= 0:
            raise ValueError("minimum_target_present_frames must be positive")
        if self.maximum_selection_truncation < 0:
            raise ValueError("maximum_selection_truncation must be non-negative")
        if self.maximum_selection_occlusion < 0:
            raise ValueError("maximum_selection_occlusion must be non-negative")
        if self.initialization_window_frames <= 0:
            raise ValueError("initialization_window_frames must be positive")


@dataclass(frozen=True)
class EpisodeCandidate:
    split: str
    sequence_name: str
    dataset_identity: int
    selection_frame_index: int
    initialization_end_frame_inclusive: int
    target_present_frames_from_selection: int
    selection_bbox_height_px: float
    selection_truncation: int | None
    selection_occlusion: int | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_image_frame_number(path: Path) -> int:
    try:
        source_number = int(path.stem)
    except ValueError as exc:
        raise ValueError(
            f"non-numeric image filename is not supported: {path.name}"
        ) from exc
    if source_number <= 0:
        raise ValueError(f"image frame number must be positive: {path.name}")
    return source_number


def discover_image_frames(image_dir: Path) -> dict[int, Path]:
    if not image_dir.is_dir():
        raise FileNotFoundError(f"image directory not found: {image_dir}")

    frames: dict[int, Path] = {}
    for path in sorted(image_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        source_number = parse_image_frame_number(path)
        if source_number in frames:
            raise ValueError(
                "duplicate source frame number "
                f"{source_number}: {frames[source_number]} and {path}"
            )
        frames[source_number] = path

    if not frames:
        raise ValueError(f"no source images found in {image_dir}")
    return frames


def annotation_source_frames(
    rows: Sequence[ExternalObjectAnnotation],
) -> set[int]:
    return {int(row.source_frame_number) for row in rows}


def reconcile_frame_domain(
    image_source_frames: Iterable[int],
    annotation_source_frame_values: Iterable[int],
) -> dict[str, object]:
    image_frames = set(int(value) for value in image_source_frames)
    annotation_frames = set(int(value) for value in annotation_source_frame_values)

    return {
        "image_frame_count": len(image_frames),
        "annotation_frame_count": len(annotation_frames),
        "intersection_frame_count": len(image_frames & annotation_frames),
        "image_only_frames": sorted(image_frames - annotation_frames),
        "annotation_only_frames": sorted(annotation_frames - image_frames),
        "minimum_image_frame": min(image_frames) if image_frames else None,
        "maximum_image_frame": max(image_frames) if image_frames else None,
        "minimum_annotation_frame": (
            min(annotation_frames) if annotation_frames else None
        ),
        "maximum_annotation_frame": (
            max(annotation_frames) if annotation_frames else None
        ),
    }


def bbox_height(row: ExternalObjectAnnotation) -> float:
    return float(row.bbox_xyxy[3] - row.bbox_xyxy[1])


def contiguous_segments(frames: Sequence[int]) -> list[tuple[int, int]]:
    unique = sorted(set(int(frame) for frame in frames))
    if not unique:
        return []

    segments: list[tuple[int, int]] = []
    start = previous = unique[0]
    for frame in unique[1:]:
        if frame != previous + 1:
            segments.append((start, previous))
            start = frame
        previous = frame
    segments.append((start, previous))
    return segments


def _selection_annotation_is_eligible(
    row: ExternalObjectAnnotation,
    config: EligibilityConfig,
) -> bool:
    if not row.include_as_person_candidate:
        return False
    if bbox_height(row) < config.minimum_selection_height_px:
        return False
    if (
        row.truncation is not None
        and int(row.truncation) > config.maximum_selection_truncation
    ):
        return False
    if (
        row.occlusion is not None
        and int(row.occlusion) > config.maximum_selection_occlusion
    ):
        return False
    return True


def build_episode_candidates(
    rows: Sequence[ExternalObjectAnnotation],
    *,
    split: str,
    sequence_name: str,
    config: EligibilityConfig,
) -> tuple[list[EpisodeCandidate], dict[str, int]]:
    by_identity: dict[int, list[ExternalObjectAnnotation]] = defaultdict(list)
    for row in rows:
        if row.include_as_person_candidate:
            by_identity[int(row.identity)].append(row)

    episodes: list[EpisodeCandidate] = []
    exclusions = Counter()

    for identity in sorted(by_identity):
        identity_rows = sorted(
            by_identity[identity],
            key=lambda row: row.normalized_frame_index,
        )

        eligible_selection_rows = [
            row
            for row in identity_rows
            if _selection_annotation_is_eligible(row, config)
        ]
        if not eligible_selection_rows:
            exclusions["no_eligible_selection_frame"] += 1
            continue

        selected_row = eligible_selection_rows[0]
        remaining = [
            row
            for row in identity_rows
            if row.normalized_frame_index
            >= selected_row.normalized_frame_index
        ]
        if len(remaining) < config.minimum_target_present_frames:
            exclusions["insufficient_target_present_frames"] += 1
            continue

        sequence_last_frame = max(
            int(row.normalized_frame_index) for row in rows
        )
        end_frame = min(
            selected_row.normalized_frame_index
            + config.initialization_window_frames
            - 1,
            sequence_last_frame,
        )
        episodes.append(
            EpisodeCandidate(
                split=split,
                sequence_name=sequence_name,
                dataset_identity=identity,
                selection_frame_index=selected_row.normalized_frame_index,
                initialization_end_frame_inclusive=end_frame,
                target_present_frames_from_selection=len(remaining),
                selection_bbox_height_px=bbox_height(selected_row),
                selection_truncation=selected_row.truncation,
                selection_occlusion=selected_row.occlusion,
            )
        )

    return episodes, dict(sorted(exclusions.items()))


def summarize_sequence(
    rows: Sequence[ExternalObjectAnnotation],
    *,
    split: str,
    sequence_name: str,
    image_frames: dict[int, Path],
    config: EligibilityConfig,
) -> tuple[dict[str, object], list[EpisodeCandidate]]:
    person_rows = [row for row in rows if row.include_as_person_candidate]
    by_identity: dict[int, list[ExternalObjectAnnotation]] = defaultdict(list)
    for row in person_rows:
        by_identity[int(row.identity)].append(row)

    truncation = Counter(
        "none" if row.truncation is None else str(int(row.truncation))
        for row in person_rows
    )
    occlusion = Counter(
        "none" if row.occlusion is None else str(int(row.occlusion))
        for row in person_rows
    )
    heights = [bbox_height(row) for row in person_rows]

    episodes, exclusions = build_episode_candidates(
        rows,
        split=split,
        sequence_name=sequence_name,
        config=config,
    )

    identity_summaries = []
    for identity in sorted(by_identity):
        identity_rows = sorted(
            by_identity[identity],
            key=lambda row: row.normalized_frame_index,
        )
        normalized_frames = [
            int(row.normalized_frame_index) for row in identity_rows
        ]
        identity_heights = [bbox_height(row) for row in identity_rows]
        identity_summaries.append(
            {
                "dataset_identity": identity,
                "target_present_frames": len(identity_rows),
                "first_normalized_frame": min(normalized_frames),
                "last_normalized_frame": max(normalized_frames),
                "contiguous_segments": [
                    {"start": start, "end_inclusive": end}
                    for start, end in contiguous_segments(normalized_frames)
                ],
                "minimum_bbox_height_px": min(identity_heights),
                "maximum_bbox_height_px": max(identity_heights),
            }
        )

    frame_domain = reconcile_frame_domain(
        image_frames,
        annotation_source_frames(rows),
    )

    report = {
        "split": split,
        "sequence_name": sequence_name,
        "frame_domain": frame_domain,
        "annotation_row_count": len(rows),
        "person_annotation_row_count": len(person_rows),
        "pedestrian_identity_count": len(by_identity),
        "truncation_distribution": dict(sorted(truncation.items())),
        "occlusion_distribution": dict(sorted(occlusion.items())),
        "bbox_height_px": {
            "minimum": min(heights) if heights else None,
            "maximum": max(heights) if heights else None,
        },
        "eligibility": {
            "config": asdict(config),
            "eligible_episode_count": len(episodes),
            "exclusions": exclusions,
        },
        "identities": identity_summaries,
    }
    return report, episodes


def load_sequence_rows(
    *,
    split: str,
    sequence_name: str,
    annotation_path: Path,
    image_width: int,
    image_height: int,
) -> list[ExternalObjectAnnotation]:
    # Frame rate is irrelevant to this GT-only frame-domain audit, but the
    # existing normalized annotation adapter requires a positive value. Use
    # 1.0 as a dimensionless logical cadence and do not expose timestamp_s as
    # physical time in Issue #125 outputs.
    geometry = SequenceGeometry(
        image_width=image_width,
        image_height=image_height,
        frame_rate=1.0,
        source_index_base=1,
    )
    return parse_visdrone_annotations(
        annotation_path,
        sequence_name=sequence_name,
        split=split,
        geometry=geometry,
    )


def image_dimensions(path: Path) -> tuple[int, int]:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"could not read source image: {path}")
    height, width = image.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid source image dimensions: {path}")
    return int(width), int(height)


def audit_split(
    dataset_root: Path,
    *,
    split: str,
    config: EligibilityConfig,
) -> dict[str, object]:
    split_root = dataset_root / split
    annotations_dir = split_root / "annotations"
    sequences_dir = split_root / "sequences"

    if not annotations_dir.is_dir():
        raise FileNotFoundError(
            f"VisDrone annotations directory not found: {annotations_dir}"
        )
    if not sequences_dir.is_dir():
        raise FileNotFoundError(
            f"VisDrone sequences directory not found: {sequences_dir}"
        )

    annotation_paths = sorted(annotations_dir.glob("*.txt"))
    if not annotation_paths:
        raise ValueError(f"no annotation files found in {annotations_dir}")

    sequence_reports: list[dict[str, object]] = []
    all_episodes: list[EpisodeCandidate] = []

    for annotation_path in annotation_paths:
        sequence_name = annotation_path.stem
        image_dir = sequences_dir / sequence_name
        image_frames = discover_image_frames(image_dir)
        first_image = image_frames[min(image_frames)]
        width, height = image_dimensions(first_image)
        rows = load_sequence_rows(
            split=split,
            sequence_name=sequence_name,
            annotation_path=annotation_path,
            image_width=width,
            image_height=height,
        )
        report, episodes = summarize_sequence(
            rows,
            split=split,
            sequence_name=sequence_name,
            image_frames=image_frames,
            config=config,
        )
        report["source"] = {
            "annotation_relative_path": annotation_path.relative_to(
                dataset_root
            ).as_posix(),
            "annotation_sha256": sha256_file(annotation_path),
            "image_relative_directory": image_dir.relative_to(
                dataset_root
            ).as_posix(),
            "image_width": width,
            "image_height": height,
        }
        sequence_reports.append(report)
        all_episodes.extend(episodes)

    return {
        "schema": "p125_visdrone_gt_only_corpus_audit_v1",
        "outcome_blind_contract": (
            "This report reads VisDrone source images and ground-truth "
            "annotations only. Detector/tracker/Target-ReID/TIM-MARS "
            "outputs are forbidden inputs."
        ),
        "dataset": "visdrone_mot",
        "split": split,
        "eligibility_config": asdict(config),
        "sequence_count": len(sequence_reports),
        "sequence_reports": sequence_reports,
        "episode_candidates": [asdict(episode) for episode in all_episodes],
        "totals": {
            "pedestrian_identities": sum(
                int(report["pedestrian_identity_count"])
                for report in sequence_reports
            ),
            "eligible_episode_candidates": len(all_episodes),
            "image_frames": sum(
                int(report["frame_domain"]["image_frame_count"])
                for report in sequence_reports
            ),
            "annotation_frames": sum(
                int(report["frame_domain"]["annotation_frame_count"])
                for report in sequence_reports
            ),
            "image_only_frames": sum(
                len(report["frame_domain"]["image_only_frames"])
                for report in sequence_reports
            ),
            "annotation_only_frames": sum(
                len(report["frame_domain"]["annotation_only_frames"])
                for report in sequence_reports
            ),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "data" / "datasets" / "external" / "visdrone_mot",
    )
    parser.add_argument(
        "--split",
        choices=("train", "val"),
        required=True,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--minimum-selection-height-px",
        type=float,
        default=20.0,
    )
    parser.add_argument(
        "--minimum-target-present-frames",
        type=int,
        default=30,
    )
    parser.add_argument(
        "--maximum-selection-truncation",
        type=int,
        default=1,
        help=(
            "VisDrone selection gate. Official GT defines 0 as no "
            "truncation and 1 as partial truncation (1-50%%)."
        ),
    )
    parser.add_argument(
        "--maximum-selection-occlusion",
        type=int,
        default=1,
        help=(
            "VisDrone selection gate. Official GT defines 0 as none, "
            "1 as partial (1-50%%), and 2 as heavy (50-100%%)."
        ),
    )
    parser.add_argument(
        "--initialization-window-frames",
        type=int,
        default=10,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = EligibilityConfig(
        minimum_selection_height_px=args.minimum_selection_height_px,
        minimum_target_present_frames=args.minimum_target_present_frames,
        maximum_selection_truncation=args.maximum_selection_truncation,
        maximum_selection_occlusion=args.maximum_selection_occlusion,
        initialization_window_frames=args.initialization_window_frames,
    )
    report = audit_split(
        args.dataset_root.expanduser().resolve(),
        split=args.split,
        config=config,
    )
    output = args.out.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["totals"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
