"""Unit tests for deterministic tracker-freezing helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from thesis_msgs.msg import Track2D, Track2DArray


RUNNER_PATH = (
    Path(__file__).resolve().parents[1]
    / 'experiments'
    / 'run_deterministic_tracker_replay.py'
)

SPEC = importlib.util.spec_from_file_location(
    'run_deterministic_tracker_replay',
    RUNNER_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_track(
    track_id: int,
    width: float,
    height: float,
    score: float,
) -> Track2D:
    """Construct one test track."""
    track = Track2D()
    track.id = track_id
    track.w = width
    track.h = height
    track.score = score
    track.cx = 100.0
    track.cy = 100.0
    track.label = 'person'
    return track


def test_select_largest_track_uses_area_score_then_lowest_id():
    """Choose area, score, and lowest-ID deterministic tie breakers."""
    message = Track2DArray()
    message.tracks = [
        make_track(4, 20.0, 50.0, 0.8),
        make_track(2, 25.0, 40.0, 0.9),
        make_track(1, 25.0, 40.0, 0.9),
    ]

    assert MODULE.select_largest_track_id(message, 40.0) == 1


def test_select_largest_track_rejects_short_tracks():
    """Reject tracks below the autonomous-selection height gate."""
    message = Track2DArray()
    message.tracks = [
        make_track(1, 100.0, 39.9, 1.0),
    ]

    assert MODULE.select_largest_track_id(message, 40.0) is None


def test_fixed_target_is_invalid_when_selected_id_is_absent():
    """Keep raw selection fixed rather than selecting a replacement."""
    message = Track2DArray()
    message.frame_id = 7
    message.src_stamp_ns = 99
    message.tracks = [
        make_track(2, 30.0, 60.0, 0.8),
    ]

    target = MODULE.make_target_message(message, 1)

    assert target.id == 0
    assert target.frame_id == 7
    assert target.src_stamp_ns == 99
    assert target.w == 0.0
    assert target.h == 0.0


def test_fixed_target_copies_selected_track():
    """Copy the selected tracker ID and geometry into raw target."""
    message = Track2DArray()
    message.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]

    target = MODULE.make_target_message(message, 1)

    assert target.id == 1
    assert target.w == 30.0
    assert target.h == 60.0
    assert target.score == 0.8
    assert target.quality == 0.8


def semantic_digest(
    records,
) -> str:
    """Return one generated-message semantic digest for tests."""
    digest = MODULE.new_generated_semantic_digest()

    for topic, bag_time_ns, message in records:
        MODULE.update_generated_semantic_digest(
            digest,
            topic,
            bag_time_ns,
            message,
        )

    return digest.hexdigest()


def test_semantic_digest_matches_for_equal_track_messages():
    """Ignore object identity while preserving declared ROS fields."""
    first = Track2DArray()
    first.header.frame_id = 'frame_7'
    first.frame_id = 7
    first.src_stamp_ns = 123
    first.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]

    second = Track2DArray()
    second.header.frame_id = 'frame_7'
    second.frame_id = 7
    second.src_stamp_ns = 123
    second.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]

    assert semantic_digest(
        [('/tracks', 500, first)]
    ) == semantic_digest(
        [('/tracks', 500, second)]
    )


def test_semantic_digest_changes_when_track_geometry_changes():
    """Detect any change to generated tracker geometry."""
    first = Track2DArray()
    first.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]

    second = Track2DArray()
    second.tracks = [
        make_track(1, 31.0, 60.0, 0.8),
    ]

    assert semantic_digest(
        [('/tracks', 500, first)]
    ) != semantic_digest(
        [('/tracks', 500, second)]
    )


def test_semantic_digest_supports_custom_generated_topics():
    """Support CLI overrides for generated tracks and target topics."""
    tracks = Track2DArray()
    tracks.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]
    target = MODULE.make_target_message(tracks, 1)

    digest = MODULE.new_generated_semantic_digest()

    MODULE.update_generated_semantic_digest(
        digest,
        '/frozen/tracks',
        500,
        tracks,
        tracks_topic='/frozen/tracks',
        target_topic='/frozen/target',
    )
    MODULE.update_generated_semantic_digest(
        digest,
        '/frozen/target',
        500,
        target,
        tracks_topic='/frozen/tracks',
        target_topic='/frozen/target',
    )

    assert len(digest.hexdigest()) == 64


def test_semantic_digest_includes_generated_write_order():
    """Treat tracks-then-target ordering as part of determinism."""
    tracks = Track2DArray()
    tracks.tracks = [
        make_track(1, 30.0, 60.0, 0.8),
    ]
    target = MODULE.make_target_message(tracks, 1)

    first = semantic_digest(
        [
            ('/tracks', 500, tracks),
            ('/target', 500, target),
        ]
    )
    second = semantic_digest(
        [
            ('/target', 500, target),
            ('/tracks', 500, tracks),
        ]
    )

    assert first != second


def test_image_age_summary_records_negative_and_stale_samples():
    """Preserve image-timing limitations in replay metadata."""
    summary = MODULE.image_age_summary(
        [-10.0, 0.0, 50.0, 150.0, 250.0]
    )

    assert summary['samples'] == 5
    assert summary['negative_age_count'] == 1
    assert summary['over_120_ms_count'] == 2
    assert summary['over_200_ms_count'] == 1
    assert summary['min_ms'] == -10.0
    assert summary['max_ms'] == 250.0


class FakeReader:
    """Minimal rosbag reader used by merge tests."""

    def __init__(self, messages):
        """Initialize the fake reader with source messages."""
        self.messages = list(messages)
        self.index = 0

    def has_next(self):
        """Return whether another message exists."""
        return self.index < len(self.messages)

    def read_next(self):
        """Return the next source message."""
        message = self.messages[self.index]
        self.index += 1
        return message


class FakeWriter:
    """Minimal rosbag writer used by merge tests."""

    def __init__(self):
        """Initialize an empty generated-message list."""
        self.messages = []

    def write(self, topic, serialized, bag_time_ns):
        """Record one generated write."""
        self.messages.append(
            (
                int(bag_time_ns),
                topic,
                bytes(serialized),
            )
        )


def test_streamed_output_replaces_old_tracker_topics():
    """Remove old tracks and target while preserving source ordering."""
    reader = FakeReader(
        [
            ('/detections', b'detection', 100),
            ('/tracks', b'old-tracks', 100),
            ('/target', b'old-target', 100),
            ('/camera/image_raw', b'image', 200),
        ]
    )
    writer = FakeWriter()

    source_count = MODULE.write_streamed_output(
        writer,
        reader,
        [
            (100, 1, '/tracks', b'new-tracks'),
            (100, 2, '/target', b'new-target'),
        ],
        {'/tracks', '/target'},
    )

    assert source_count == 2
    assert writer.messages == [
        (100, '/detections', b'detection'),
        (100, '/tracks', b'new-tracks'),
        (100, '/target', b'new-target'),
        (200, '/camera/image_raw', b'image'),
    ]
