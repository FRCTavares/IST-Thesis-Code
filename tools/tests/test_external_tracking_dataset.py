"""Synthetic tests for Issue #30 external dataset normalization."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "external_tracking_dataset.py"
)
FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "external_tracking"
)

SPEC = importlib.util.spec_from_file_location(
    "external_tracking_dataset",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def geometry():
    return MODULE.SequenceGeometry(
        image_width=100,
        image_height=80,
        frame_rate=20.0,
        source_index_base=1,
    )


def test_frame_number_and_timestamp_are_normalized():
    assert MODULE.normalize_frame_number(1, 1) == 0
    assert MODULE.normalize_frame_number(4, 1) == 3
    assert MODULE.timestamp_for_frame(3, 20.0) == pytest.approx(
        0.15
    )


def test_invalid_frame_contract_is_rejected():
    with pytest.raises(ValueError):
        MODULE.SequenceGeometry(
            image_width=100,
            image_height=80,
            frame_rate=0.0,
            source_index_base=1,
        )

    with pytest.raises(ValueError):
        MODULE.normalize_frame_number(0, 1)


def test_xywh_conversion_uses_geometric_image_edges():
    assert MODULE.xywh_to_clipped_xyxy(
        -10.0,
        5.0,
        30.0,
        20.0,
        image_width=100,
        image_height=80,
    ) == (0.0, 5.0, 20.0, 25.0)

    assert MODULE.xywh_to_clipped_xyxy(
        90.0,
        70.0,
        20.0,
        20.0,
        image_width=100,
        image_height=80,
    ) == (90.0, 70.0, 100.0, 80.0)


def test_empty_or_invalid_boxes_are_rejected():
    with pytest.raises(ValueError):
        MODULE.xywh_to_clipped_xyxy(
            1.0,
            1.0,
            0.0,
            5.0,
            image_width=100,
            image_height=80,
        )

    with pytest.raises(ValueError):
        MODULE.xywh_to_clipped_xyxy(
            150.0,
            1.0,
            10.0,
            10.0,
            image_width=100,
            image_height=80,
        )


def test_motchallenge_parser_preserves_and_sorts_provenance():
    rows = MODULE.parse_motchallenge_annotations(
        FIXTURE_DIR / "motchallenge_gt.txt",
        dataset="mot17",
        sequence_name="synthetic_mot",
        split="train",
        geometry=geometry(),
        person_class_ids={1, 2},
    )

    assert [row.source_frame_number for row in rows] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert rows[0].normalized_frame_index == 0
    assert rows[0].timestamp_s == pytest.approx(0.0)
    assert rows[0].image_width == 100
    assert rows[0].image_height == 80
    assert rows[0].frame_rate == pytest.approx(20.0)
    assert rows[0].source_index_base == 1
    assert rows[0].bbox_xyxy == (
        90.0,
        70.0,
        100.0,
        80.0,
    )

    clipped = rows[1]
    assert clipped.source_line_number == 1
    assert clipped.source_row.startswith("2,7,-5")
    assert clipped.bbox_xyxy == (0.0, 10.0, 15.0, 40.0)

    assert rows[2].exclusion_reason == "non_positive_identity"
    assert rows[3].exclusion_reason == "non_positive_confidence"
    assert rows[4].exclusion_reason == "non_person_class"


def test_mot_sequence_metadata_preserves_geometry_and_timing():
    metadata = MODULE.parse_mot_sequence_metadata(
        FIXTURE_DIR / "dancetrack_seqinfo.ini"
    )

    assert metadata.name == "dancetrack-synthetic"
    assert metadata.image_directory == "img1"
    assert metadata.frame_rate == pytest.approx(20.0)
    assert metadata.sequence_length == 4
    assert metadata.image_width == 1920
    assert metadata.image_height == 1080
    assert metadata.image_extension == ".jpg"

    geometry = metadata.geometry(source_index_base=1)

    assert geometry.image_width == 1920
    assert geometry.image_height == 1080
    assert geometry.frame_rate == pytest.approx(20.0)
    assert geometry.source_index_base == 1


def test_dancetrack_parser_is_explicit_and_deterministic():
    metadata = MODULE.parse_mot_sequence_metadata(
        FIXTURE_DIR / "dancetrack_seqinfo.ini"
    )

    rows = MODULE.parse_dancetrack_annotations(
        FIXTURE_DIR / "dancetrack_gt.txt",
        sequence_name=metadata.name,
        split="train",
        geometry=metadata.geometry(),
    )

    assert [
        (
            row.normalized_frame_index,
            row.identity,
        )
        for row in rows
    ] == [
        (0, 12),
        (0, 31),
        (1, 12),
        (1, 31),
        (2, -1),
        (3, 77),
    ]

    assert all(row.dataset == "dancetrack" for row in rows)
    assert all(
        row.sequence_name == "dancetrack-synthetic"
        for row in rows
    )
    assert rows[0].timestamp_s == pytest.approx(0.0)
    assert rows[2].timestamp_s == pytest.approx(0.05)

    invalid = next(row for row in rows if row.identity == -1)
    assert invalid.include_as_person_candidate is False
    assert invalid.exclusion_reason == "non_positive_identity"

    clipped = next(row for row in rows if row.identity == 77)
    assert clipped.bbox_xyxy == pytest.approx(
        (1850.0, 980.0, 1920.0, 1080.0)
    )


def test_dancetrack_rejects_non_person_source_class(tmp_path):
    annotations = tmp_path / "gt.txt"
    annotations.write_text(
        "1,4,10,20,30,80,1,2,1\n",
        encoding="utf-8",
    )

    rows = MODULE.parse_dancetrack_annotations(
        annotations,
        sequence_name="synthetic",
        split="train",
        geometry=MODULE.SequenceGeometry(
            image_width=640,
            image_height=480,
            frame_rate=30.0,
            source_index_base=1,
        ),
    )

    assert len(rows) == 1
    assert rows[0].include_as_person_candidate is False
    assert rows[0].exclusion_reason == "non_person_class"


def test_mot_sequence_metadata_rejects_missing_fields(tmp_path):
    seqinfo = tmp_path / "seqinfo.ini"
    seqinfo.write_text(
        "[Sequence]\n"
        "name=incomplete\n"
        "frameRate=30\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="missing sequence fields",
    ):
        MODULE.parse_mot_sequence_metadata(seqinfo)


def test_visdrone_parser_preserves_class_semantics():
    rows = MODULE.parse_visdrone_annotations(
        FIXTURE_DIR / "visdrone_gt.txt",
        sequence_name="synthetic_visdrone",
        split="val",
        geometry=geometry(),
    )

    assert [row.source_frame_number for row in rows] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]

    grouped_people = rows[0]
    assert grouped_people.class_id == 2
    assert grouped_people.class_name == "people"
    assert grouped_people.include_as_person_candidate is False
    assert grouped_people.exclusion_reason == (
        "group_class_not_single_identity"
    )
    assert grouped_people.truncation == 1
    assert grouped_people.occlusion == 2

    pedestrian = rows[1]
    assert pedestrian.class_id == 1
    assert pedestrian.class_name == "pedestrian"
    assert pedestrian.bbox_xyxy == (
        0.0,
        5.0,
        20.0,
        25.0,
    )

    ignored = rows[2]
    assert ignored.ignored_region is True
    assert ignored.exclusion_reason == "ignored_region"

    assert rows[3].exclusion_reason == "non_person_class"
    assert rows[4].exclusion_reason == "non_positive_identity"
    assert rows[5].exclusion_reason == "non_positive_score"


def test_duplicate_frame_identity_is_rejected_even_if_bbox_changes(
    tmp_path,
):
    path = tmp_path / "duplicates.txt"
    path.write_text(
        "1,7,10,10,20,20,1,1,1\n"
        "1,7,11,10,20,20,1,1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="duplicate normalized frame-identity annotation",
    ):
        MODULE.parse_motchallenge_annotations(
            path,
            dataset="mot17",
            sequence_name="duplicate",
            split="train",
            geometry=geometry(),
            person_class_ids={1},
        )


def test_non_integral_or_non_finite_values_are_rejected(tmp_path):
    fractional = tmp_path / "fractional.txt"
    fractional.write_text(
        "1.5,7,10,10,20,20,1,1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frame must be integral"):
        MODULE.parse_motchallenge_annotations(
            fractional,
            dataset="mot17",
            sequence_name="fractional",
            split="train",
            geometry=geometry(),
        )

    non_finite = tmp_path / "non_finite.txt"
    non_finite.write_text(
        "1,7,nan,10,20,20,1,1,1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-finite bbox_left"):
        MODULE.parse_motchallenge_annotations(
            non_finite,
            dataset="mot17",
            sequence_name="non_finite",
            split="train",
            geometry=geometry(),
        )

def test_classless_mot_row_preserves_unspecified_class(tmp_path):
    path = tmp_path / "classless.txt"
    path.write_text(
        "1,7,10,20,30,80\n",
        encoding="utf-8",
    )

    rows = MODULE.parse_motchallenge_annotations(
        path,
        dataset="mot17",
        sequence_name="classless",
        split="train",
        geometry=geometry(),
        person_class_ids={1},
    )

    assert len(rows) == 1
    assert rows[0].class_id is None
    assert rows[0].class_name == "unspecified"
    assert rows[0].include_as_person_candidate is False
    assert rows[0].exclusion_reason == "non_person_class"


def test_annotation_frame_must_fit_sequence_length(tmp_path):
    seqinfo = tmp_path / "seqinfo.ini"
    seqinfo.write_text(
        "[Sequence]\n"
        "name=bounded\n"
        "imDir=img1\n"
        "frameRate=30\n"
        "seqLength=2\n"
        "imWidth=100\n"
        "imHeight=80\n"
        "imExt=.jpg\n",
        encoding="utf-8",
    )

    annotations = tmp_path / "gt.txt"
    annotations.write_text(
        "3,7,10,10,20,20,1,1,1\n",
        encoding="utf-8",
    )

    metadata = MODULE.parse_mot_sequence_metadata(seqinfo)
    rows = MODULE.parse_motchallenge_annotations(
        annotations,
        dataset="mot17",
        sequence_name="bounded",
        split="train",
        geometry=metadata.geometry(),
        person_class_ids={1},
    )

    with pytest.raises(
        ValueError,
        match="annotation frame exceeds sequence length",
    ):
        MODULE.validate_annotations_against_metadata(
            rows,
            metadata,
        )


def test_metadata_validation_accepts_last_valid_frame(tmp_path):
    seqinfo = tmp_path / "seqinfo.ini"
    seqinfo.write_text(
        "[Sequence]\n"
        "name=bounded\n"
        "imDir=img1\n"
        "frameRate=30\n"
        "seqLength=2\n"
        "imWidth=100\n"
        "imHeight=80\n"
        "imExt=.jpg\n",
        encoding="utf-8",
    )

    annotations = tmp_path / "gt.txt"
    annotations.write_text(
        "2,7,10,10,20,20,1,1,1\n",
        encoding="utf-8",
    )

    metadata = MODULE.parse_mot_sequence_metadata(seqinfo)
    rows = MODULE.parse_motchallenge_annotations(
        annotations,
        dataset="mot17",
        sequence_name="bounded",
        split="train",
        geometry=metadata.geometry(),
        person_class_ids={1},
    )

    validated = MODULE.validate_annotations_against_metadata(
        rows,
        metadata,
    )

    assert validated == rows
    assert validated[0].normalized_frame_index == 1
