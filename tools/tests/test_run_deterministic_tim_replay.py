"""Unit tests for deterministic TIM-MARS replay helpers."""

from dataclasses import fields
from pathlib import Path
import importlib.util

from thesis_bringup.tim_mars.types import TargetMemoryConfig


RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "run_deterministic_tim_replay.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_deterministic_tim_replay",
    RUNNER_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_memory_config_filters_non_algorithm_parameters():
    canonical = {
        "w_iou": 0.11,
        "appearance_enabled": True,
        "mars_batch_size": 99,
        "appearance_max_image_age_ms": 123.0,
        "unknown_parameter": "ignored",
    }

    config = MODULE.build_memory_config(
        canonical,
        image_width=1280.0,
        image_height=720.0,
        appearance_enabled=False,
    )

    assert config.image_width == 1280.0
    assert config.image_height == 720.0
    assert config.w_iou == 0.11
    assert config.appearance_enabled is False
    assert not hasattr(config, "mars_batch_size")
    assert not hasattr(config, "unknown_parameter")


def test_every_constructor_key_is_a_target_memory_config_field():
    canonical = {
        field.name: getattr(TargetMemoryConfig(), field.name)
        for field in fields(TargetMemoryConfig)
    }

    config = MODULE.build_memory_config(
        canonical,
        image_width=640.0,
        image_height=640.0,
        appearance_enabled=True,
    )

    assert isinstance(config, TargetMemoryConfig)
    assert config.appearance_enabled is True


def test_choose_image_topic_prefers_image_raw():
    available = {
        "/camera/dashboard": object(),
        "/camera/image_raw": object(),
    }

    assert (
        MODULE.choose_image_topic(available, "auto")
        == "/camera/image_raw"
    )


def test_choose_image_topic_falls_back_to_dashboard():
    available = {
        "/camera/dashboard": object(),
    }

    assert (
        MODULE.choose_image_topic(available, "auto")
        == "/camera/dashboard"
    )


def test_track_time_prefers_header_over_source():
    class Stamp:
        sec = 2
        nanosec = 3

    class Header:
        stamp = Stamp()

    class Tracks:
        header = Header()
        src_stamp_ns = 999

    assert MODULE.track_time_ns(Tracks()) == 2_000_000_003


def test_track_time_falls_back_to_source():
    class Stamp:
        sec = 0
        nanosec = 0

    class Header:
        stamp = Stamp()

    class Tracks:
        header = Header()
        src_stamp_ns = 456

    assert MODULE.track_time_ns(Tracks()) == 456


def test_invalid_track_time_returns_zero():
    class Stamp:
        sec = 0
        nanosec = 0

    class Header:
        stamp = Stamp()

    class Tracks:
        header = Header()
        src_stamp_ns = 0

    assert MODULE.track_time_ns(Tracks()) == 0


class _FakeReader:
    def __init__(self, messages):
        self.messages = list(messages)
        self.index = 0

    def has_next(self):
        return self.index < len(self.messages)

    def read_next(self):
        message = self.messages[self.index]
        self.index += 1
        return message


class _FakeWriter:
    def __init__(self):
        self.messages = []

    def write(self, topic, serialized, bag_time_ns):
        self.messages.append(
            (
                int(bag_time_ns),
                topic,
                bytes(serialized),
            )
        )


def test_streamed_output_preserves_source_order_and_merges_generated_messages():
    reader = _FakeReader(
        [
            ("/image", b"image-100", 100),
            ("/tracks", b"tracks-100", 100),
            ("/image", b"image-200", 200),
        ]
    )
    writer = _FakeWriter()

    generated = [
        (200, 5, MODULE.TIM_STATUS_TOPIC, b"status-200"),
        (100, 2, MODULE.TIM_STATUS_TOPIC, b"status-100"),
        (100, 1, MODULE.TIM_TARGET_TOPIC, b"target-100"),
        (200, 4, MODULE.TIM_TARGET_TOPIC, b"target-200"),
    ]

    source_count = MODULE.write_streamed_output(
        writer=writer,
        source_reader=reader,
        generated_messages=generated,
    )

    assert source_count == 3
    assert writer.messages == [
        (100, "/image", b"image-100"),
        (100, "/tracks", b"tracks-100"),
        (100, MODULE.TIM_TARGET_TOPIC, b"target-100"),
        (100, MODULE.TIM_STATUS_TOPIC, b"status-100"),
        (200, "/image", b"image-200"),
        (200, MODULE.TIM_TARGET_TOPIC, b"target-200"),
        (200, MODULE.TIM_STATUS_TOPIC, b"status-200"),
    ]


def test_streamed_output_removes_existing_tim_topics_from_source():
    reader = _FakeReader(
        [
            ("/image", b"image", 100),
            (
                MODULE.TIM_TARGET_TOPIC,
                b"obsolete-target",
                100,
            ),
            (
                MODULE.TIM_STATUS_TOPIC,
                b"obsolete-status",
                100,
            ),
            ("/tracks", b"tracks", 100),
        ]
    )
    writer = _FakeWriter()

    source_count = MODULE.write_streamed_output(
        writer=writer,
        source_reader=reader,
        generated_messages=[
            (
                100,
                1,
                MODULE.TIM_TARGET_TOPIC,
                b"new-target",
            ),
            (
                100,
                2,
                MODULE.TIM_STATUS_TOPIC,
                b"new-status",
            ),
        ],
    )

    assert source_count == 2
    assert writer.messages == [
        (100, "/image", b"image"),
        (100, "/tracks", b"tracks"),
        (
            100,
            MODULE.TIM_TARGET_TOPIC,
            b"new-target",
        ),
        (
            100,
            MODULE.TIM_STATUS_TOPIC,
            b"new-status",
        ),
    ]


def test_streamed_output_writes_generated_messages_between_source_timestamps():
    reader = _FakeReader(
        [
            ("/first", b"first", 100),
            ("/last", b"last", 300),
        ]
    )
    writer = _FakeWriter()

    MODULE.write_streamed_output(
        writer=writer,
        source_reader=reader,
        generated_messages=[
            (
                200,
                1,
                MODULE.TIM_TARGET_TOPIC,
                b"target-200",
            ),
        ],
    )

    assert writer.messages == [
        (100, "/first", b"first"),
        (
            200,
            MODULE.TIM_TARGET_TOPIC,
            b"target-200",
        ),
        (300, "/last", b"last"),
    ]




def test_build_crop_quality_thresholds_uses_canonical_values():
    thresholds = MODULE.build_crop_quality_thresholds(
        {
            "appearance_crop_min_width_px": 16.0,
            "appearance_crop_min_height_px": 32.0,
            "appearance_crop_max_clipping_fraction": 0.20,
            "appearance_crop_min_aspect_ratio": 0.25,
            "appearance_crop_max_aspect_ratio": 0.90,
            "appearance_crop_max_overlap_iou_for_memory": 0.15,
            "appearance_crop_min_centre_distance_norm_for_memory": 0.05,
        }
    )

    assert thresholds.min_width_px == 16.0
    assert thresholds.min_height_px == 32.0
    assert thresholds.max_clipping_fraction == 0.20
    assert thresholds.min_aspect_ratio == 0.25
    assert thresholds.max_aspect_ratio == 0.90
    assert thresholds.max_overlap_iou_for_memory == 0.15
    assert (
        thresholds.min_centre_distance_norm_for_memory
        == 0.05
    )


def test_build_memory_config_preserves_id_switch_appearance_threshold():
    config = MODULE.build_memory_config(
        {
            "id_switch_min_appearance_similarity": 0.78,
            "appearance_enabled": True,
        },
        image_width=640.0,
        image_height=640.0,
        appearance_enabled=True,
    )

    assert (
        config.id_switch_min_appearance_similarity
        == 0.78
    )
