"""Unit tests for deterministic TIM-MARS replay helpers."""

import argparse
from dataclasses import fields
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
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


def test_compact_output_keeps_only_evaluation_source_topics():
    skipped = MODULE.skipped_source_topics_for_output(
        {
            "/camera/image_raw",
            "/diagnostics",
            "/tracks",
            "/target",
            MODULE.TIM_TARGET_TOPIC,
            MODULE.TIM_STATUS_TOPIC,
        },
        tracks_topic="/tracks",
        raw_target_topic="/target",
        replace_raw_target=False,
        compact_output=True,
    )

    assert skipped == {
        "/camera/image_raw",
        "/diagnostics",
        MODULE.TIM_TARGET_TOPIC,
        MODULE.TIM_STATUS_TOPIC,
    }


def test_compact_output_omits_replaced_source_raw_target():
    skipped = MODULE.skipped_source_topics_for_output(
        {
            "/camera/dashboard",
            "/tracks",
            "/target",
        },
        tracks_topic="/tracks",
        raw_target_topic="/target",
        replace_raw_target=True,
        compact_output=True,
    )

    assert skipped == {
        "/camera/dashboard",
        "/target",
        MODULE.TIM_TARGET_TOPIC,
        MODULE.TIM_STATUS_TOPIC,
    }


def test_full_output_only_omits_generated_and_replaced_topics():
    skipped = MODULE.skipped_source_topics_for_output(
        {
            "/camera/dashboard",
            "/tracks",
            "/target",
        },
        tracks_topic="/tracks",
        raw_target_topic="/target",
        replace_raw_target=False,
        compact_output=False,
    )

    assert skipped == {
        MODULE.TIM_TARGET_TOPIC,
        MODULE.TIM_STATUS_TOPIC,
    }


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


def test_write_resolved_runtime_writes_fingerprint(
    tmp_path,
):
    """Persist resolved runtime provenance and a matching fingerprint."""
    output = tmp_path / "bag"
    output.mkdir()

    payload = {
        "schema_version": 2,
        "runtime_overrides": {
            "selected_track_id": 1,
            "appearance_enabled": True,
        },
        "experiment_fields": {
            "raw_target_mode": "source",
        },
        "value_sources": {
            "selected_track_id": (
                "command_line_required"
            ),
            "appearance_enabled": (
                "canonical_config"
            ),
        },
    }

    (
        runtime_path,
        fingerprint_path,
        runtime_sha256,
    ) = MODULE.write_resolved_runtime(
        output,
        payload,
    )

    assert runtime_path.is_file()
    assert fingerprint_path.is_file()
    assert runtime_sha256 == (
        MODULE.sha256_file(runtime_path)
    )
    assert MODULE.json.loads(
        runtime_path.read_text(
            encoding="utf-8"
        )
    ) == payload

    expected = (
        f"{runtime_sha256}  "
        f"{runtime_path.name}\n"
    )

    assert fingerprint_path.read_text(
        encoding="utf-8"
    ) == expected


def test_build_resolved_runtime_payload_records_sources(
    monkeypatch,
    tmp_path,
):
    """Record precise origins for effective deterministic values."""
    monkeypatch.setattr(
        MODULE.sys,
        "argv",
        [
            "runner",
            "input",
            "output",
            "--config",
            "config.yaml",
            "--model",
            "model.pb",
            "--selected-track-id",
            "7",
            "--image-width",
            "800",
            "--no-zero-id-when-not-visible",
            "--raw-target-mode",
            "selected_id",
            "--tracks-topic",
            "/custom/tracks",
            "--compact-output",
        ],
    )

    args = MODULE.argparse.Namespace(
        selected_track_id=7,
        image_width=800.0,
        image_height=640.0,
        tracks_are_normalized=False,
        zero_id_when_not_visible=False,
        appearance_enabled=None,
        appearance_request_policy=None,
        appearance_compute_min_interval_ms=None,
        raw_target_mode="selected_id",
        image_topic="auto",
        tracks_topic="/custom/tracks",
        raw_target_topic="/target",
        compact_output=True,
    )

    payload = (
        MODULE.build_resolved_runtime_payload(
            summary={
                "canonical_config": {
                    "copy": (
                        "tim_mars_canonical_config.yaml"
                    ),
                    "sha256": "a" * 64,
                    "source": "config.yaml",
                },
            },
            args=args,
            appearance_enabled=True,
            appearance_request_policy="all_candidates",
            appearance_compute_min_interval_ms=250.0,
            image_topic="/camera/image_raw",
            input_bag=tmp_path / "input",
            output_bag=tmp_path / "output",
        )
    )

    assert payload["schema_version"] == 3
    assert payload["runtime_overrides"] == {
        "selected_track_id": 7,
        "image_width": 800.0,
        "image_height": 640.0,
        "tracks_are_normalized": False,
        "zero_id_when_not_visible": False,
        "appearance_enabled": True,
        "appearance_request_policy": "all_candidates",
        "appearance_compute_min_interval_ms": 250.0,
        "compact_output": True,
    }

    sources = payload["value_sources"]

    assert sources["input_bag"] == (
        "command_line_required"
    )
    assert sources["output_bag"] == (
        "command_line_required"
    )
    assert sources["selected_track_id"] == (
        "command_line_required"
    )
    assert sources["image_width"] == (
        "command_line"
    )
    assert sources["image_height"] == (
        "runner_default"
    )
    assert sources["tracks_are_normalized"] == (
        "runner_default"
    )
    assert sources["zero_id_when_not_visible"] == (
        "command_line"
    )
    assert sources["appearance_enabled"] == (
        "canonical_config"
    )
    assert sources["appearance_request_policy"] == (
        "canonical_config"
    )
    assert sources[
        "appearance_compute_min_interval_ms"
    ] == "canonical_config"
    assert sources["raw_target_mode"] == (
        "command_line"
    )
    assert sources["image_topic"] == (
        "bag_auto_detect"
    )
    assert sources["tracks_topic"] == (
        "command_line"
    )
    assert sources["raw_target_topic"] == (
        "runner_default"
    )
    assert sources["compact_output"] == (
        "command_line"
    )


def test_argument_source_supports_equals_and_boolean_flags(
    monkeypatch,
):
    """Recognise explicit option values in both accepted CLI forms."""
    monkeypatch.setattr(
        MODULE.sys,
        "argv",
        [
            "runner",
            "--image-height=720",
            "--appearance-enabled",
        ],
    )

    assert MODULE.argument_source(
        "--image-height"
    ) == "command_line"
    assert MODULE.argument_source(
        "--appearance-enabled",
        "--no-appearance-enabled",
    ) == "command_line"
    assert MODULE.argument_source(
        "--tracks-topic"
    ) == "runner_default"


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


def test_make_status_message_zeroes_backend_wall_time_for_determinism(
    monkeypatch,
):
    captured = {}

    def fake_status_json_from_output(_output, **kwargs):
        captured.update(kwargs)
        return json.dumps({"ok": True}, sort_keys=True)

    monkeypatch.setattr(
        MODULE,
        "status_json_from_output",
        fake_status_json_from_output,
    )

    diagnostics = SimpleNamespace(
        appearance_candidates=3,
        appearance_request_policy="geometry_winner",
        appearance_request_reason="geometry_winner",
        appearance_request_candidates=1,
        appearance_request_track_ids=(2,),
        appearance_request_encoding_eligible=1,
        appearance_features_valid=2,
        image_track_offset_ms=12.0,
        appearance_skip_reason="ok",
        track_timestamp_ns=1_000_000_000,
        selected_image_timestamp_ns=988_000_000,
        appearance_warning=None,
        candidate_track_ids=(1, 2, 3),
        appearance_cache_size=2,
        appearance_embedding_age_ms_by_track_id={1: 0.0},
        appearance_crop_quality_by_track_id={},
        appearance_encoding_rejected=0,
        appearance_memory_update_ineligible=1,
        appearance_encoding_eligible=3,
        appearance_backend_calls=1,
        appearance_backend_requested=3,
        appearance_backend_returned=3,
        appearance_backend_valid=2,
        appearance_backend_wall_ms=7.5,
        appearance_update_cooldown_remaining=0,
    )

    runtime = SimpleNamespace(
        config=SimpleNamespace(
            appearance=SimpleNamespace(
                enabled=True,
                compute_min_interval_ms=0.0,
                cache_ttl_ms=750.0,
            )
        )
    )
    tracks_message = SimpleNamespace(
        frame_id=12,
        tracks=[object(), object(), object()],
    )
    result = SimpleNamespace(
        output=object(),
        diagnostics=diagnostics,
    )

    message = MODULE.make_status_message(
        runtime=runtime,
        tracks_message=tracks_message,
        result=result,
    )

    assert json.loads(message.data) == {"ok": True}
    assert captured["appearance_request_policy"] == (
        "geometry_winner"
    )
    assert captured["appearance_request_reason"] == (
        "geometry_winner"
    )
    assert captured["appearance_request_candidates"] == 1
    assert captured["appearance_request_track_ids"] == (2,)
    assert (
        captured["appearance_request_encoding_eligible"]
        == 1
    )
    assert (
        captured["appearance_compute_min_interval_ms"]
        == 0.0
    )
    assert captured["appearance_encoding_eligible"] == 3
    assert captured["appearance_backend_calls"] == 1
    assert captured["appearance_backend_requested"] == 3
    assert captured["appearance_backend_returned"] == 3
    assert captured["appearance_backend_valid"] == 2
    assert captured["appearance_backend_wall_ms"] == 0.0
    assert (
        MODULE.SEMANTIC_DIGEST_SCHEMA
        == "tim_mars_replay_generated_fields_v4"
    )


def test_resolve_appearance_request_policy_uses_canonical_default():
    args = argparse.Namespace(
        appearance_request_policy=None,
    )

    assert (
        MODULE.resolve_appearance_request_policy(
            {
                "appearance_request_policy": (
                    "geometry_winner"
                )
            },
            args,
        )
        == "geometry_winner"
    )



def test_resolve_appearance_request_policy_accepts_ambiguity_guarded_override():
    """Accept the guarded selector through an explicit replay override."""
    args = argparse.Namespace(
        appearance_request_policy="ambiguity_guarded",
    )

    assert (
        MODULE.resolve_appearance_request_policy(
            {
                "appearance_request_policy": (
                    "all_candidates"
                ),
            },
            args,
        )
        == "ambiguity_guarded"
    )

def test_resolve_appearance_request_policy_rejects_invalid_value():
    args = argparse.Namespace(
        appearance_request_policy=None,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported appearance_request_policy",
    ):
        MODULE.resolve_appearance_request_policy(
            {
                "appearance_request_policy": "unsupported",
            },
            args,
        )


def test_resolve_appearance_compute_interval_supports_zero_override():
    args = argparse.Namespace(
        appearance_compute_min_interval_ms=0.0,
    )

    assert (
        MODULE.resolve_appearance_compute_min_interval_ms(
            {
                "appearance_compute_min_interval_ms": 250.0,
            },
            args,
        )
        == 0.0
    )


def test_resolve_appearance_compute_interval_rejects_negative_value():
    args = argparse.Namespace(
        appearance_compute_min_interval_ms=-1.0,
    )

    with pytest.raises(
        ValueError,
        match="must be non-negative",
    ):
        MODULE.resolve_appearance_compute_min_interval_ms(
            {},
            args,
        )
