#!/usr/bin/env python3
"""Freeze deterministic tracker and fixed-ID raw-target output into a ROS bag.

The runner processes recorded messages in original rosbag source order. It
replaces existing tracker, raw-target, tracker-timing, and TIM output topics
with one generated /tracks and /target message per /detections message.

For DeepSORT, image callbacks are forwarded to the backend as they occur in
the original source sequence. This mirrors the live TrackerNode latest-image
contract without ROS playback or executor scheduling.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rclpy.serialization import deserialize_message, serialize_message

import rosbag2_py

from rosidl_runtime_py.utilities import get_message

from thesis_msgs.msg import TargetState, Track2D, Track2DArray

from thesis_tracker.backends.bytetrack_backend import ByteTrackBackend
from thesis_tracker.backends.deepsort_core_backend import DeepSortBackend
from thesis_tracker.backends.ocsort_backend import OCSortBackend
from thesis_tracker.backends.sort_backend import SortBackend

from vision_msgs.msg import Detection2DArray

import yaml


DEFAULT_DETECTIONS_TOPIC = '/detections'
DEFAULT_TRACKS_TOPIC = '/tracks'
DEFAULT_TARGET_TOPIC = '/target'
REPLACED_EXTRA_TOPICS = {
    '/timing_tracker',
    '/target_memory_mars',
    '/target_memory_mars/status',
}


def parse_args() -> argparse.Namespace:
    """Parse deterministic tracker-freezing arguments."""
    parser = argparse.ArgumentParser(
        description=(
            'Generate deterministic tracker and fixed-ID raw-target evidence '
            'from a recorded image and detection timeline.'
        )
    )
    parser.add_argument('input_bag', type=Path)
    parser.add_argument('output_bag', type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument(
        '--model',
        type=Path,
        help='MARS model path required by DeepSORT.',
    )
    parser.add_argument(
        '--image-topic',
        default='auto',
        help='Image topic or auto.',
    )
    parser.add_argument(
        '--detections-topic',
        default=DEFAULT_DETECTIONS_TOPIC,
    )
    parser.add_argument(
        '--tracks-topic',
        default=DEFAULT_TRACKS_TOPIC,
    )
    parser.add_argument(
        '--target-topic',
        default=DEFAULT_TARGET_TOPIC,
    )
    parser.add_argument(
        '--selection-mode',
        choices=('largest_first_eligible', 'fixed_id'),
        default='largest_first_eligible',
    )
    parser.add_argument('--selected-track-id', type=int)
    parser.add_argument(
        '--min-selection-height-px',
        type=float,
        default=40.0,
    )
    parser.add_argument(
        '--selection-confirmation-messages',
        type=int,
        default=1,
        help=(
            'Require an eligible tracker ID in this many consecutive '
            'track messages before autonomous selection.'
        ),
    )
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument(
        '--skip-source-hash',
        action='store_true',
        help='Skip hashing source bag files during diagnostic runs.',
    )
    return parser.parse_args()


def detect_storage_id(bag_path: Path) -> str:
    """Detect rosbag storage from files in a bag directory."""
    if list(bag_path.glob('*.mcap')):
        return 'mcap'

    if list(bag_path.glob('*.db3')):
        return 'sqlite3'

    raise RuntimeError(
        f'Could not determine bag storage type: {bag_path}'
    )


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    """Open a rosbag reader using CDR serialization."""
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag_path),
            storage_id=detect_storage_id(bag_path),
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr',
        ),
    )
    return reader


def topic_metadata_map(
    reader: rosbag2_py.SequentialReader,
) -> dict[str, Any]:
    """Return rosbag topic metadata indexed by topic name."""
    return {
        metadata.name: metadata
        for metadata in reader.get_all_topics_and_types()
    }


def copy_topic_metadata(metadata: Any) -> rosbag2_py.TopicMetadata:
    """Copy source topic metadata for a new writer."""
    return rosbag2_py.TopicMetadata(
        id=0,
        name=str(metadata.name),
        type=str(metadata.type),
        serialization_format=(
            str(metadata.serialization_format)
            if metadata.serialization_format
            else 'cdr'
        ),
        offered_qos_profiles=list(
            getattr(metadata, 'offered_qos_profiles', [])
        ),
        type_description_hash=str(
            getattr(metadata, 'type_description_hash', '')
        ),
    )


def generated_topic_metadata(
    name: str,
    message_type: str,
) -> rosbag2_py.TopicMetadata:
    """Create metadata for a generated CDR topic."""
    return rosbag2_py.TopicMetadata(
        id=0,
        name=name,
        type=message_type,
        serialization_format='cdr',
        offered_qos_profiles=[],
        type_description_hash='',
    )


def choose_image_topic(
    available: dict[str, Any],
    requested: str,
    required: bool,
) -> str | None:
    """Resolve the deterministic appearance-image topic."""
    if requested != 'auto':
        if requested not in available:
            raise RuntimeError(
                f'Requested image topic is not present: {requested}'
            )
        return requested

    for candidate in (
        '/camera/image_raw',
        '/camera/dashboard',
    ):
        if candidate in available:
            return candidate

    if required:
        raise RuntimeError(
            'DeepSORT requires /camera/image_raw or /camera/dashboard'
        )

    return None


def load_tracker_parameters(path: Path) -> dict[str, Any]:
    """Load tracker ROS parameters from one active YAML profile."""
    with path.open(encoding='utf-8') as stream:
        document = yaml.safe_load(stream)

    try:
        parameters = document['tracker_node']['ros__parameters']
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f'Invalid tracker YAML structure: {path}'
        ) from exc

    if not isinstance(parameters, dict):
        raise RuntimeError(
            f'Tracker parameter mapping is not a dictionary: {path}'
        )

    return dict(parameters)


def build_backend(
    parameters: dict[str, Any],
    model_path: Path | None,
):
    """Construct the backend represented by one tracker YAML profile."""
    tracker_type = str(parameters.get('tracker_type', '')).strip()
    min_score = float(parameters.get('min_score', 0.35))

    if tracker_type == 'sort':
        backend = SortBackend(
            iou_threshold=float(
                parameters.get('iou_threshold', 0.18)
            ),
            max_age=int(parameters.get('max_age', 4)),
            min_hits=int(parameters.get('min_hits', 3)),
            centre_gate=float(
                parameters.get('centre_gate', 200.0)
            ),
            gate_x=(
                None
                if parameters.get('gate_x') is None
                else float(parameters['gate_x'])
            ),
            gate_y=(
                None
                if parameters.get('gate_y') is None
                else float(parameters['gate_y'])
            ),
        )
    elif tracker_type == 'ocsort':
        backend = OCSortBackend(
            iou_threshold=float(
                parameters.get('iou_threshold', 0.3)
            ),
            max_age=int(parameters.get('max_age', 30)),
            min_hits=int(parameters.get('min_hits', 3)),
            det_thresh=float(
                parameters.get('det_thresh', 0.35)
            ),
            delta_t=int(parameters.get('delta_t', 3)),
            inertia=float(parameters.get('inertia', 0.2)),
            use_byte=bool(parameters.get('use_byte', False)),
        )
    elif tracker_type == 'bytetrack':
        backend = ByteTrackBackend(
            track_thresh=float(
                parameters.get('track_thresh', 0.5)
            ),
            match_thresh=float(
                parameters.get('match_thresh', 0.8)
            ),
            track_buffer=int(
                parameters.get('track_buffer', 30)
            ),
            frame_rate=int(parameters.get('frame_rate', 30)),
            low_thresh=float(
                parameters.get('low_thresh', 0.1)
            ),
            new_track_thresh=float(
                parameters.get('new_track_thresh', 0.6)
            ),
            second_match_thresh=float(
                parameters.get('second_match_thresh', 0.5)
            ),
            unconfirmed_match_thresh=float(
                parameters.get(
                    'unconfirmed_match_thresh',
                    0.7,
                )
            ),
            fuse_scores=bool(
                parameters.get('fuse_scores', True)
            ),
            mot20=bool(parameters.get('mot20', False)),
        )
    elif tracker_type == 'deepsort':
        if model_path is None or not model_path.is_file():
            raise RuntimeError(
                'DeepSORT requires an existing --model path'
            )

        backend = DeepSortBackend(
            max_age=int(parameters.get('max_age', 30)),
            n_init=int(parameters.get('n_init', 3)),
            max_cosine_distance=float(
                parameters.get('max_cosine_distance', 0.2)
            ),
            nn_budget=int(parameters.get('nn_budget', 100)),
            max_iou_distance=float(
                parameters.get('max_iou_distance', 0.7)
            ),
            only_position_gating=bool(
                parameters.get(
                    'only_position_gating',
                    False,
                )
            ),
            reid_model_path=str(model_path),
            reid_batch_size=int(
                parameters.get('reid_batch_size', 32)
            ),
        )
    else:
        raise RuntimeError(
            f'Unsupported tracker type in configuration: {tracker_type!r}'
        )

    return tracker_type, min_score, backend


def header_time_ns(message: Any) -> int:
    """Return a ROS header timestamp in nanoseconds."""
    header = getattr(message, 'header', None)
    stamp = getattr(header, 'stamp', None)

    if stamp is None:
        return 0

    return (
        int(getattr(stamp, 'sec', 0)) * 1_000_000_000
        + int(getattr(stamp, 'nanosec', 0))
    )


def parse_frame_id(value: str) -> int:
    """Parse a numeric frame ID from frame_<number>."""
    text = str(value)

    if not text.startswith('frame_'):
        return 0

    try:
        return int(text.split('_', 1)[1])
    except ValueError:
        return 0


def detection_inputs(
    message: Detection2DArray,
    min_score: float,
) -> tuple[list[tuple[float, float, float, float]], list[float]]:
    """Convert vision detections into backend boxes and scores."""
    boxes = []
    scores = []

    for detection in message.detections:
        if not detection.results:
            continue

        score = max(
            float(result.hypothesis.score)
            for result in detection.results
        )

        if score < min_score:
            continue

        cx = float(detection.bbox.center.position.x)
        cy = float(detection.bbox.center.position.y)
        width = float(detection.bbox.size_x)
        height = float(detection.bbox.size_y)

        boxes.append(
            (
                cx - 0.5 * width,
                cy - 0.5 * height,
                cx + 0.5 * width,
                cy + 0.5 * height,
            )
        )
        scores.append(score)

    return boxes, scores


def make_tracks_message(
    detection_message: Detection2DArray,
    backend_tracks: list[Any],
) -> Track2DArray:
    """Convert unified backend output to thesis Track2DArray."""
    message = Track2DArray()
    message.header = detection_message.header
    message.frame_id = parse_frame_id(
        detection_message.header.frame_id
    )
    message.src_stamp_ns = header_time_ns(detection_message)
    message.t_cam_msg_seen_ns = 0
    message.t_track_cb_start_ns = 0
    message.t_track_cb_end_ns = 0

    tracks = []

    for backend_track in backend_tracks:
        x1, y1, x2, y2 = backend_track.bbox_xyxy
        width = float(x2 - x1)
        height = float(y2 - y1)

        track = Track2D()
        track.id = int(backend_track.track_id)
        track.cx = float(x1 + 0.5 * width)
        track.cy = float(y1 + 0.5 * height)
        track.w = width
        track.h = height

        score = float(backend_track.score)
        track.score = score if score > 0.0 else 1.0
        track.label = 'person'
        tracks.append(track)

    message.tracks = tracks
    return message


def update_track_presence_streaks(
    tracks_message: Track2DArray,
    previous_streaks: dict[int, int],
    min_height_px: float,
) -> dict[int, int]:
    """Update consecutive per-ID eligible-observation streaks."""
    eligible_ids = {
        int(track.id)
        for track in tracks_message.tracks
        if int(track.id) > 0
        and float(track.w) > 0.0
        and float(track.h) >= min_height_px
    }

    return {
        track_id: int(previous_streaks.get(track_id, 0)) + 1
        for track_id in eligible_ids
    }


def select_largest_track_id(
    tracks_message: Track2DArray,
    min_height_px: float,
    presence_streaks: dict[int, int] | None = None,
    confirmation_messages: int = 1,
) -> int | None:
    """Select the largest eligible, sufficiently persistent track."""
    if confirmation_messages <= 0:
        raise ValueError(
            'selection confirmation messages must be positive'
        )

    def is_confirmed(track_id: int) -> bool:
        if confirmation_messages == 1:
            return True

        return (
            presence_streaks is not None
            and int(presence_streaks.get(track_id, 0))
            >= confirmation_messages
        )

    eligible = [
        track
        for track in tracks_message.tracks
        if int(track.id) > 0
        and float(track.w) > 0.0
        and float(track.h) >= min_height_px
        and is_confirmed(int(track.id))
    ]

    if not eligible:
        return None

    selected = max(
        eligible,
        key=lambda track: (
            float(track.w) * float(track.h),
            float(track.score),
            -int(track.id),
        ),
    )
    return int(selected.id)


def make_target_message(
    tracks_message: Track2DArray,
    selected_track_id: int | None,
) -> TargetState:
    """Publish one fixed selected tracker ID or an invalid target."""
    message = TargetState()
    message.header = tracks_message.header
    message.frame_id = int(tracks_message.frame_id)
    message.src_stamp_ns = int(tracks_message.src_stamp_ns)
    message.t_cam_msg_seen_ns = 0
    message.t_target_cb_start_ns = 0
    message.t_target_cb_end_ns = 0

    selected = None

    if selected_track_id is not None:
        selected = next(
            (
                track
                for track in tracks_message.tracks
                if int(track.id) == selected_track_id
            ),
            None,
        )

    if selected is None:
        message.id = 0
        message.cx = 0.0
        message.cy = 0.0
        message.w = 0.0
        message.h = 0.0
        message.score = 0.0
        message.quality = 0.0
        return message

    message.id = int(selected.id)
    message.cx = float(selected.cx)
    message.cy = float(selected.cy)
    message.w = float(selected.w)
    message.h = float(selected.h)
    message.score = float(selected.score)
    message.quality = float(selected.score)
    return message


def percentile(values: list[float], fraction: float) -> float | None:
    """Return a linearly interpolated percentile."""
    if not values:
        return None

    ordered = sorted(values)
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower

    return (
        ordered[lower] * (1.0 - weight)
        + ordered[upper] * weight
    )


def image_age_summary(values: list[float]) -> dict[str, Any]:
    """Summarize image-header age at detection processing."""
    if not values:
        return {
            'samples': 0,
        }

    return {
        'samples': len(values),
        'negative_age_count': sum(value < 0.0 for value in values),
        'over_120_ms_count': sum(value > 120.0 for value in values),
        'over_200_ms_count': sum(value > 200.0 for value in values),
        'min_ms': min(values),
        'p50_ms': percentile(values, 0.50),
        'p90_ms': percentile(values, 0.90),
        'p95_ms': percentile(values, 0.95),
        'p99_ms': percentile(values, 0.99),
        'max_ms': max(values),
    }


SEMANTIC_DIGEST_SCHEMA = (
    'tim_tracker_freeze_generated_fields_v1'
)


def new_generated_semantic_digest():
    """Create a domain-separated generated-message semantic digest."""
    digest = hashlib.sha256()
    digest.update(SEMANTIC_DIGEST_SCHEMA.encode('utf-8'))
    digest.update(b'\0')
    return digest


def _digest_bytes(digest: Any, value: bytes) -> None:
    """Append length-prefixed bytes to a semantic digest."""
    digest.update(len(value).to_bytes(8, 'big'))
    digest.update(value)


def _digest_text(digest: Any, value: str) -> None:
    """Append one UTF-8 string to a semantic digest."""
    _digest_bytes(digest, str(value).encode('utf-8'))


def _digest_uint(digest: Any, value: int) -> None:
    """Append one non-negative integer to a semantic digest."""
    digest.update(int(value).to_bytes(8, 'big', signed=False))


def _digest_int(digest: Any, value: int) -> None:
    """Append one signed integer to a semantic digest."""
    digest.update(int(value).to_bytes(8, 'big', signed=True))


def _digest_float32(digest: Any, value: float) -> None:
    """Append one canonical IEEE-754 float32 value."""
    digest.update(struct.pack('>f', float(value)))


def update_generated_semantic_digest(
    digest: Any,
    topic: str,
    bag_time_ns: int,
    message: Any,
    *,
    tracks_topic: str = DEFAULT_TRACKS_TOPIC,
    target_topic: str = DEFAULT_TARGET_TOPIC,
) -> None:
    """Append one generated message using only declared ROS fields."""
    _digest_text(digest, topic)
    _digest_int(digest, bag_time_ns)

    header = message.header
    _digest_int(digest, int(header.stamp.sec))
    _digest_uint(digest, int(header.stamp.nanosec))
    _digest_text(digest, str(header.frame_id))

    _digest_uint(digest, int(message.frame_id))
    _digest_int(digest, int(message.src_stamp_ns))
    _digest_int(
        digest,
        int(message.t_cam_msg_seen_ns),
    )

    if topic == tracks_topic:
        _digest_int(
            digest,
            int(message.t_track_cb_start_ns),
        )
        _digest_int(
            digest,
            int(message.t_track_cb_end_ns),
        )
        _digest_uint(digest, len(message.tracks))

        for track in message.tracks:
            _digest_uint(digest, int(track.id))
            _digest_float32(digest, float(track.cx))
            _digest_float32(digest, float(track.cy))
            _digest_float32(digest, float(track.w))
            _digest_float32(digest, float(track.h))
            _digest_float32(digest, float(track.score))
            _digest_text(digest, str(track.label))

        return

    if topic == target_topic:
        _digest_int(
            digest,
            int(message.t_target_cb_start_ns),
        )
        _digest_int(
            digest,
            int(message.t_target_cb_end_ns),
        )
        _digest_uint(digest, int(message.id))
        _digest_float32(digest, float(message.cx))
        _digest_float32(digest, float(message.cy))
        _digest_float32(digest, float(message.w))
        _digest_float32(digest, float(message.h))
        _digest_float32(digest, float(message.score))
        _digest_float32(digest, float(message.quality))
        return

    raise ValueError(
        'Unsupported generated semantic-digest topic '
        f'{topic!r}; expected {tracks_topic!r} or '
        f'{target_topic!r}'
    )


def write_streamed_output(
    writer: Any,
    source_reader: Any,
    generated_messages: list[tuple[int, int, str, bytes]],
    skipped_topics: set[str],
) -> int:
    """Stream source messages and merge generated messages by bag time."""
    generated_messages.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    generated_index = 0
    source_messages_written = 0
    current_time_ns = None
    current_source_group = []

    def flush_group() -> None:
        nonlocal generated_index
        nonlocal source_messages_written
        nonlocal current_source_group
        nonlocal current_time_ns

        if current_time_ns is None:
            return

        while (
            generated_index < len(generated_messages)
            and generated_messages[generated_index][0]
            < current_time_ns
        ):
            bag_time_ns, _sequence, topic, serialized = (
                generated_messages[generated_index]
            )
            writer.write(topic, serialized, bag_time_ns)
            generated_index += 1

        for topic, serialized, bag_time_ns in current_source_group:
            writer.write(topic, serialized, bag_time_ns)
            source_messages_written += 1

        while (
            generated_index < len(generated_messages)
            and generated_messages[generated_index][0]
            == current_time_ns
        ):
            bag_time_ns, _sequence, topic, serialized = (
                generated_messages[generated_index]
            )
            writer.write(topic, serialized, bag_time_ns)
            generated_index += 1

        current_source_group = []

    while source_reader.has_next():
        topic, serialized, bag_time_ns = source_reader.read_next()

        if topic in skipped_topics:
            continue

        if current_time_ns is None:
            current_time_ns = int(bag_time_ns)

        if int(bag_time_ns) != current_time_ns:
            flush_group()
            current_time_ns = int(bag_time_ns)

        current_source_group.append(
            (
                topic,
                serialized,
                int(bag_time_ns),
            )
        )

    flush_group()

    while generated_index < len(generated_messages):
        bag_time_ns, _sequence, topic, serialized = (
            generated_messages[generated_index]
        )
        writer.write(topic, serialized, bag_time_ns)
        generated_index += 1

    return source_messages_written


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 for one file."""
    digest = hashlib.sha256()

    with path.open('rb') as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b'',
        ):
            digest.update(chunk)

    return digest.hexdigest()


def source_manifest(
    bag_path: Path,
    hash_files: bool,
) -> list[dict[str, Any]]:
    """Describe the files that define the source rosbag."""
    rows = []

    for path in sorted(
        item
        for item in bag_path.iterdir()
        if item.is_file()
    ):
        row = {
            'name': path.name,
            'size_bytes': path.stat().st_size,
        }

        if hash_files:
            row['sha256'] = sha256_file(path)

        rows.append(row)

    return rows


def git_value(repo_root: Path, *arguments: str) -> str:
    """Return one Git value without making metadata generation fatal."""
    result = subprocess.run(
        ['git', '-C', str(repo_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return ''

    return result.stdout.strip()


def count_output_topics(bag_path: Path) -> dict[str, int]:
    """Count all topics in a completed output rosbag."""
    counts: dict[str, int] = {}
    reader = open_reader(bag_path)

    while reader.has_next():
        topic, _serialized, _bag_time_ns = reader.read_next()
        counts[topic] = counts.get(topic, 0) + 1

    return counts


def main() -> int:
    """Run deterministic tracker freezing."""
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    input_bag = args.input_bag.expanduser().resolve()
    output_bag = args.output_bag.expanduser().resolve()
    config_path = args.config.expanduser().resolve()

    if not input_bag.is_dir():
        raise RuntimeError(
            f'Input bag does not exist: {input_bag}'
        )

    if not config_path.is_file():
        raise RuntimeError(
            f'Tracker configuration does not exist: {config_path}'
        )

    if output_bag.exists():
        if not args.overwrite:
            raise RuntimeError(
                f'Output already exists: {output_bag}'
            )
        shutil.rmtree(output_bag)

    parameters = load_tracker_parameters(config_path)
    tracker_type = str(parameters.get('tracker_type', ''))

    model_path = None

    if tracker_type == 'deepsort':
        model_path = (
            args.model.expanduser().resolve()
            if args.model is not None
            else (
                repo_root
                / 'models/reid/mars-small128.pb'
            ).resolve()
        )

    tracker_type, min_score, backend = build_backend(
        parameters,
        model_path,
    )

    if (
        args.selection_mode == 'fixed_id'
        and (
            args.selected_track_id is None
            or args.selected_track_id <= 0
        )
    ):
        raise RuntimeError(
            'fixed_id selection requires --selected-track-id > 0'
        )

    if args.selection_confirmation_messages <= 0:
        raise RuntimeError(
            '--selection-confirmation-messages must be positive'
        )

    reader = open_reader(input_bag)
    metadata_by_topic = topic_metadata_map(reader)

    if args.detections_topic not in metadata_by_topic:
        raise RuntimeError(
            f'Missing detection topic: {args.detections_topic}'
        )

    image_topic = choose_image_topic(
        metadata_by_topic,
        args.image_topic,
        required=(tracker_type == 'deepsort'),
    )

    message_types = {
        topic: get_message(metadata.type)
        for topic, metadata in metadata_by_topic.items()
    }

    selected_track_id = (
        int(args.selected_track_id)
        if args.selection_mode == 'fixed_id'
        else None
    )
    selection_record = None
    selection_presence_streaks: dict[int, int] = {}
    latest_image = None
    latest_image_sequence = 0
    latest_image_time_ns = 0
    source_sequence = 0
    generated_sequence = 0
    detection_messages = 0
    total_filtered_detections = 0
    tracks_written = 0
    targets_written = 0
    valid_targets_written = 0
    image_messages_seen = 0
    missing_prior_images = 0
    image_ages_ms = []
    generated_messages = []
    generated_semantic_digest = new_generated_semantic_digest()

    while reader.has_next():
        topic, serialized, bag_time_ns = reader.read_next()
        source_sequence += 1

        if topic == image_topic:
            latest_image = deserialize_message(
                serialized,
                message_types[topic],
            )
            latest_image_sequence = source_sequence
            latest_image_time_ns = header_time_ns(latest_image)
            image_messages_seen += 1

            if tracker_type == 'deepsort':
                backend.update_latest_image(latest_image)

            continue

        if topic != args.detections_topic:
            continue

        detection_message = deserialize_message(
            serialized,
            Detection2DArray,
        )
        detection_messages += 1
        detection_time_ns = header_time_ns(detection_message)

        if tracker_type == 'deepsort':
            if latest_image is None:
                missing_prior_images += 1
            else:
                image_ages_ms.append(
                    (
                        detection_time_ns - latest_image_time_ns
                    ) / 1_000_000.0
                )

        boxes, scores = detection_inputs(
            detection_message,
            min_score,
        )
        total_filtered_detections += len(boxes)

        backend_tracks = backend.update(
            boxes,
            scores,
            detection_time_ns,
        )

        tracks_message = make_tracks_message(
            detection_message,
            backend_tracks,
        )

        if (
            args.selection_mode == 'largest_first_eligible'
            and selected_track_id is None
        ):
            selection_presence_streaks = (
                update_track_presence_streaks(
                    tracks_message,
                    selection_presence_streaks,
                    args.min_selection_height_px,
                )
            )
            selected_track_id = select_largest_track_id(
                tracks_message,
                args.min_selection_height_px,
                presence_streaks=selection_presence_streaks,
                confirmation_messages=(
                    args.selection_confirmation_messages
                ),
            )

            if selected_track_id is not None:
                selection_record = {
                    'effective_track_id': selected_track_id,
                    'frame_id': int(tracks_message.frame_id),
                    'header_time_ns': detection_time_ns,
                    'bag_time_ns': int(bag_time_ns),
                    'detection_source_sequence': source_sequence,
                    'latest_image_source_sequence': (
                        latest_image_sequence
                        if latest_image is not None
                        else None
                    ),
                    'confirmation_messages_observed': int(
                        selection_presence_streaks[
                            selected_track_id
                        ]
                    ),
                }

        target_message = make_target_message(
            tracks_message,
            selected_track_id,
        )

        update_generated_semantic_digest(
            generated_semantic_digest,
            args.tracks_topic,
            int(bag_time_ns),
            tracks_message,
            tracks_topic=args.tracks_topic,
            target_topic=args.target_topic,
        )
        update_generated_semantic_digest(
            generated_semantic_digest,
            args.target_topic,
            int(bag_time_ns),
            target_message,
            tracks_topic=args.tracks_topic,
            target_topic=args.target_topic,
        )

        generated_messages.append(
            (
                int(bag_time_ns),
                generated_sequence,
                args.tracks_topic,
                bytes(serialize_message(tracks_message)),
            )
        )
        generated_sequence += 1
        generated_messages.append(
            (
                int(bag_time_ns),
                generated_sequence,
                args.target_topic,
                bytes(serialize_message(target_message)),
            )
        )
        generated_sequence += 1

        tracks_written += 1
        targets_written += 1

        if int(target_message.id) > 0:
            valid_targets_written += 1

    if detection_messages == 0:
        raise RuntimeError('No detection messages were processed')

    if (
        args.selection_mode == 'largest_first_eligible'
        and selected_track_id is None
    ):
        raise RuntimeError(
            'Autonomous initialization found no eligible track'
        )

    output_bag.parent.mkdir(parents=True, exist_ok=True)

    skipped_topics = {
        args.tracks_topic,
        args.target_topic,
        *REPLACED_EXTRA_TOPICS,
    }

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(
            uri=str(output_bag),
            storage_id='mcap',
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr',
        ),
    )

    for metadata in metadata_by_topic.values():
        if metadata.name in skipped_topics:
            continue
        writer.create_topic(copy_topic_metadata(metadata))

    writer.create_topic(
        generated_topic_metadata(
            args.tracks_topic,
            'thesis_msgs/msg/Track2DArray',
        )
    )
    writer.create_topic(
        generated_topic_metadata(
            args.target_topic,
            'thesis_msgs/msg/TargetState',
        )
    )

    source_reader = open_reader(input_bag)
    source_messages_streamed = write_streamed_output(
        writer,
        source_reader,
        generated_messages,
        skipped_topics,
    )
    writer.close()

    output_counts = count_output_topics(output_bag)

    if output_counts.get(args.tracks_topic, 0) != detection_messages:
        raise RuntimeError(
            'Output track count does not match detection count'
        )

    if output_counts.get(args.target_topic, 0) != detection_messages:
        raise RuntimeError(
            'Output target count does not match detection count'
        )

    tracker_config_copy = output_bag / 'tracker_config.yaml'
    shutil.copy2(config_path, tracker_config_copy)

    config_sha256 = sha256_file(tracker_config_copy)
    model_metadata = None

    if model_path is not None:
        model_metadata = {
            'source': str(model_path),
            'sha256': sha256_file(model_path),
            'size_bytes': model_path.stat().st_size,
        }

    summary = {
        'schema_version': 1,
        'created_at_utc': datetime.now(
            timezone.utc
        ).isoformat(),
        'repository': {
            'root': str(repo_root),
            'branch': git_value(
                repo_root,
                'branch',
                '--show-current',
            ),
            'commit': git_value(
                repo_root,
                'rev-parse',
                'HEAD',
            ),
            'status_short': git_value(
                repo_root,
                'status',
                '--short',
            ).splitlines(),
        },
        'command': ' '.join(sys.argv),
        'input_bag': str(input_bag),
        'output_bag': str(output_bag),
        'source_manifest': source_manifest(
            input_bag,
            hash_files=not args.skip_source_hash,
        ),
        'tracker': {
            'type': tracker_type,
            'config_source': str(config_path),
            'config_copy': tracker_config_copy.name,
            'config_sha256': config_sha256,
            'parameters': parameters,
            'min_score': min_score,
            'model': model_metadata,
        },
        'topics': {
            'image': image_topic,
            'detections': args.detections_topic,
            'tracks': args.tracks_topic,
            'target': args.target_topic,
            'replaced_or_removed': sorted(skipped_topics),
        },
        'selection': {
            'requested_mode': args.selection_mode,
            'requested_track_id': args.selected_track_id,
            'effective_track_id': selected_track_id,
            'minimum_height_px': args.min_selection_height_px,
            'required_confirmation_messages': (
                args.selection_confirmation_messages
            ),
            'initialization': selection_record,
            'fixed_after_initialization': True,
            'reselection_enabled': False,
        },
        'determinism': {
            'semantic_digest_schema': (
                SEMANTIC_DIGEST_SCHEMA
            ),
            'generated_semantic_sha256': (
                generated_semantic_digest.hexdigest()
            ),
            'raw_cdr_payload_bytes_are_contract': False,
            'raw_mcap_file_bytes_are_contract': False,
            'reason': (
                'ROS CDR payloads may contain non-semantic '
                'alignment-padding bytes; determinism is defined '
                'over declared message fields and write order.'
            ),
        },
        'processing_contract': {
            'tracker_processing_order': (
                'original_rosbag_source_sequence'
            ),
            'deepsort_image_policy': (
                'latest_image_callback_in_original_source_sequence'
                if tracker_type == 'deepsort'
                else 'not_used'
            ),
            'generated_write_order_at_detection_timestamp': [
                args.tracks_topic,
                args.target_topic,
            ],
            'source_messages_written_before_generated_at_shared_time': True,
        },
        'counts': {
            'source_messages_streamed': source_messages_streamed,
            'image_messages_seen': image_messages_seen,
            'detection_messages_processed': detection_messages,
            'filtered_detections_processed': total_filtered_detections,
            'track_messages_written': tracks_written,
            'target_messages_written': targets_written,
            'valid_target_messages_written': valid_targets_written,
            'missing_prior_image_count': missing_prior_images,
            'output_topic_counts': output_counts,
        },
        'deepsort_image_age': image_age_summary(
            image_ages_ms
        ),
    }

    metadata_path = output_bag / 'tracker_freeze_metadata.json'
    metadata_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )

    metadata_sha256 = sha256_file(metadata_path)
    (
        output_bag / 'tracker_freeze_metadata.sha256'
    ).write_text(
        f'{metadata_sha256}  {metadata_path.name}\n',
        encoding='utf-8',
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
