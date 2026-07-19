"""Unit tests for deterministic TIM-MARS replay helpers."""

from dataclasses import fields
from pathlib import Path
import importlib.util
import json

from std_msgs.msg import String
from thesis_msgs.msg import (
    TargetState,
    Track2D,
    Track2DArray,
)

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


def _track(
    track_id,
    width=30.0,
    height=60.0,
    score=0.8,
):
    track = Track2D()
    track.id = track_id
    track.cx = 100.0
    track.cy = 200.0
    track.w = width
    track.h = height
    track.score = score
    return track


def test_fixed_id_raw_target_copies_selected_track():
    message = Track2DArray()
    message.frame_id = 7
    message.src_stamp_ns = 123456
    message.t_cam_msg_seen_ns = 123400
    message.tracks = [
        _track(1),
        _track(2, width=40.0),
    ]

    target = (
        MODULE.make_fixed_id_raw_target_message(
            tracks_message=message,
            selected_track_id=1,
        )
    )

    assert target.id == 1
    assert target.frame_id == 7
    assert target.src_stamp_ns == 123456
    assert target.t_cam_msg_seen_ns == 123400
    assert target.t_target_cb_start_ns == 0
    assert target.t_target_cb_end_ns == 0
    assert target.w == 30.0
    assert target.h == 60.0
    assert target.score == 0.8
    assert target.quality == 0.8


def test_fixed_id_raw_target_is_invalid_when_id_absent():
    message = Track2DArray()
    message.frame_id = 8
    message.tracks = [_track(2)]

    target = (
        MODULE.make_fixed_id_raw_target_message(
            tracks_message=message,
            selected_track_id=1,
        )
    )

    assert target.id == 0
    assert target.frame_id == 8
    assert target.w == 0.0
    assert target.h == 0.0


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


def test_streamed_output_preserves_raw_target_by_default():
    reader = _FakeReader(
        [
            ("/tracks", b"tracks", 100),
            ("/target", b"source-target", 100),
        ]
    )
    writer = _FakeWriter()

    source_count = MODULE.write_streamed_output(
        writer=writer,
        source_reader=reader,
        generated_messages=[],
    )

    assert source_count == 2
    assert writer.messages == [
        (100, "/tracks", b"tracks"),
        (100, "/target", b"source-target"),
    ]


def test_streamed_output_replaces_requested_raw_target():
    reader = _FakeReader(
        [
            ("/tracks", b"tracks", 100),
            ("/target", b"old-target", 100),
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
                "/target",
                b"new-target",
            ),
        ],
        skipped_source_topics={"/target"},
    )

    assert source_count == 1
    assert writer.messages == [
        (100, "/tracks", b"tracks"),
        (100, "/target", b"new-target"),
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

def _semantic_digest(records):
    """Return one digest for generated TIM records."""
    digest = (
        MODULE.new_generated_semantic_digest()
    )

    for topic, bag_time_ns, message in records:
        MODULE.update_generated_semantic_digest(
            digest,
            topic,
            bag_time_ns,
            message,
        )

    return digest.hexdigest()


def _target_message(
    track_id=7,
    centre_x=0.25,
):
    """Build one deterministic generated target."""
    message = TargetState()
    message.header.stamp.sec = 3
    message.header.stamp.nanosec = 4
    message.header.frame_id = 'camera'
    message.frame_id = 12
    message.src_stamp_ns = 100
    message.t_cam_msg_seen_ns = 101
    message.t_target_cb_start_ns = 0
    message.t_target_cb_end_ns = 0
    message.id = track_id
    message.cx = centre_x
    message.cy = 0.50
    message.w = 0.10
    message.h = 0.20
    message.score = 0.80
    message.quality = 0.70
    return message


def _status_message(state='LOCKED'):
    """Build one deterministic generated status."""
    message = String()
    message.data = json.dumps(
        {
            'state': state,
            'valid': state == 'LOCKED',
        },
        sort_keys=True,
    )
    return message


def test_tim_semantic_digest_matches_equal_messages():
    """Ignore Python object identity."""
    first = [
        (
            MODULE.TIM_TARGET_TOPIC,
            500,
            _target_message(),
        ),
        (
            MODULE.TIM_STATUS_TOPIC,
            500,
            _status_message(),
        ),
    ]
    second = [
        (
            MODULE.TIM_TARGET_TOPIC,
            500,
            _target_message(),
        ),
        (
            MODULE.TIM_STATUS_TOPIC,
            500,
            _status_message(),
        ),
    ]

    assert _semantic_digest(first) == (
        _semantic_digest(second)
    )


def test_tim_semantic_digest_detects_field_change():
    """Detect changes to declared generated fields."""
    first = [
        (
            MODULE.TIM_TARGET_TOPIC,
            500,
            _target_message(),
        ),
    ]
    second = [
        (
            MODULE.TIM_TARGET_TOPIC,
            500,
            _target_message(
                centre_x=0.30,
            ),
        ),
    ]

    assert _semantic_digest(first) != (
        _semantic_digest(second)
    )


def test_tim_semantic_digest_includes_write_order():
    """Treat target-then-status ordering as a contract."""
    target = _target_message()
    status = _status_message()

    normal = [
        (
            MODULE.TIM_TARGET_TOPIC,
            500,
            target,
        ),
        (
            MODULE.TIM_STATUS_TOPIC,
            500,
            status,
        ),
    ]
    reversed_order = list(reversed(normal))

    assert _semantic_digest(normal) != (
        _semantic_digest(reversed_order)
    )


def test_semantic_digest_supports_generated_raw_target():
    digest = (
        MODULE.new_generated_semantic_digest()
    )

    MODULE.update_generated_semantic_digest(
        digest,
        "/target",
        500,
        _target_message(),
        raw_target_topic="/target",
    )

    assert len(digest.hexdigest()) == 64


def test_source_manifest_hashes_exact_files(
    tmp_path,
):
    """Record source file size and SHA-256."""
    source = tmp_path / 'source'
    source.mkdir()
    payload = source / 'metadata.yaml'
    payload.write_bytes(b'canonical-source\n')

    manifest = MODULE.source_manifest(
        source,
        hash_files=True,
    )

    assert manifest == [
        {
            'name': 'metadata.yaml',
            'size_bytes': 17,
            'sha256': MODULE.sha256_file(
                payload
            ),
        },
    ]


def test_write_replay_metadata_writes_fingerprint(
    tmp_path,
):
    """Persist metadata and a matching fingerprint."""
    output = tmp_path / 'bag'
    output.mkdir()

    metadata_path, fingerprint_path = (
        MODULE.write_replay_metadata(
            output,
            {
                'schema_version': 1,
                'passed': True,
            },
        )
    )

    assert metadata_path.is_file()
    assert fingerprint_path.is_file()

    expected = (
        f'{MODULE.sha256_file(metadata_path)}  '
        f'{metadata_path.name}\n'
    )

    assert (
        fingerprint_path.read_text(
            encoding='utf-8'
        )
        == expected
    )


def test_git_value_preserves_leading_short_status_column(
    monkeypatch,
    tmp_path,
):
    """Keep both columns of Git short-status output."""

    class Result:
        stdout = (
            ' M tracked.py\n'
            '?? untracked.txt\n'
        )

    def fake_run(*_args, **_kwargs):
        return Result()

    monkeypatch.setattr(
        MODULE.subprocess,
        'run',
        fake_run,
    )

    value = MODULE.git_value(
        tmp_path,
        'status',
        '--short',
    )

    assert value.splitlines() == [
        ' M tracked.py',
        '?? untracked.txt',
    ]
