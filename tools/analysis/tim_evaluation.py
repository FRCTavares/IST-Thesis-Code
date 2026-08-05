"""Shared selected-target evaluation semantics.

This module is the single authority for annotation parsing, target-message
validity, bag/header time origins, latest-preceding output freshness, interval
integration, and track-ID correctness classification.
"""

from __future__ import annotations

import bisect

import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
BRINGUP_SOURCE = REPO_ROOT / "ros2_ws" / "src" / "thesis_bringup"
if str(BRINGUP_SOURCE) not in sys.path:
    sys.path.insert(0, str(BRINGUP_SOURCE))

from thesis_bringup.freshness import (  # noqa: E402
    DEFAULT_MAX_OUTPUT_AGE_S,
    FreshnessResult,
    classify_relative_freshness,
)


TARGET_TOPIC_RAW = "/target"
TARGET_TOPIC_TIM = "/target_memory_mars"
IMAGE_TOPICS_FOR_T0 = ("/camera/image_raw", "/camera/dashboard")


@dataclass
class AnnotationInterval:
    bag_name: str
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int
    distractor_track_ids: str
    event_type: str
    notes: str

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass
class TargetSample:
    t_s: float
    track_id: int
    bbox_valid: Optional[bool] = None


@dataclass(frozen=True)
class EvaluationBagSamples:
    """Selected-target and TIM status samples on one shared origin."""

    target_samples: Dict[str, List[TargetSample]]
    status_samples: Dict[str, List["StatusSample"]]
    time_origin_ns: int


@dataclass(frozen=True)
class IntervalSlice:
    t_s: float
    duration_s: float


@dataclass
class DurationStats:
    correct_target_duration_s: float = 0.0
    wrong_target_duration_s: float = 0.0
    lost_target_duration_s: float = 0.0
    target_not_visible_duration_s: float = 0.0
    target_absent_but_output_valid_duration_s: float = 0.0
    no_target_selected_duration_s: float = 0.0
    visible_target_duration_s: float = 0.0
    stale_output_duration_s: float = 0.0

    @property
    def correct_target_ratio(self) -> float:
        return safe_div(
            self.correct_target_duration_s,
            self.visible_target_duration_s,
        )

    @property
    def wrong_target_ratio(self) -> float:
        return safe_div(
            self.wrong_target_duration_s,
            self.visible_target_duration_s,
        )

    @property
    def lost_target_ratio(self) -> float:
        return safe_div(
            self.lost_target_duration_s,
            self.visible_target_duration_s,
        )


def safe_div(a: float, b: float) -> float:
    if b <= 0.0:
        return float("nan")
    return a / b


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_int_or_zero(value: str) -> int:
    value = str(value).strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def validate_annotations(
    rows: List[AnnotationInterval],
) -> None:
    """Reject ambiguous timelines while allowing gaps and empty rows."""
    previous_end_by_bag: Dict[str, float] = {}

    for row in sorted(
        rows,
        key=lambda item: (
            item.bag_name,
            item.start_s,
            item.end_s,
        ),
    ):
        if not (
            math.isfinite(row.start_s)
            and math.isfinite(row.end_s)
        ):
            raise ValueError(
                "Annotation interval times must be finite: "
                f"{row.bag_name} [{row.start_s}, {row.end_s})"
            )
        if row.end_s < row.start_s:
            raise ValueError(
                "Annotation interval has negative duration: "
                f"{row.bag_name} [{row.start_s}, {row.end_s})"
            )
        if row.end_s == row.start_s:
            continue

        previous_end = previous_end_by_bag.get(row.bag_name)
        if (
            previous_end is not None
            and row.start_s < previous_end
        ):
            raise ValueError(
                "Overlapping annotation intervals are ambiguous: "
                f"{row.bag_name} starts at {row.start_s} "
                f"before previous end {previous_end}"
            )
        previous_end_by_bag[row.bag_name] = row.end_s


def load_annotations(path: Path) -> List[AnnotationInterval]:
    rows: List[AnnotationInterval] = []

    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "bag_name",
            "start_s",
            "end_s",
            "target_label",
            "target_visible",
            "correct_target_track_id",
            "distractor_track_ids",
            "event_type",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Annotation CSV is missing columns: "
                f"{sorted(missing)}"
            )

        for row in reader:
            rows.append(
                AnnotationInterval(
                    bag_name=row["bag_name"],
                    start_s=float(row["start_s"]),
                    end_s=float(row["end_s"]),
                    target_label=row["target_label"].strip(),
                    target_visible=parse_bool(
                        row["target_visible"]
                    ),
                    correct_target_track_id=parse_int_or_zero(
                        row["correct_target_track_id"]
                    ),
                    distractor_track_ids=(
                        row["distractor_track_ids"].strip()
                    ),
                    event_type=row["event_type"].strip(),
                    notes=row["notes"].strip(),
                )
            )

    rows.sort(key=lambda item: item.start_s)
    validate_annotations(rows)
    return rows


def import_rosbag_tools():
    try:
        from rosbag2_py import (
            ConverterOptions,
            SequentialReader,
            StorageOptions,
        )
        from rclpy.serialization import deserialize_message
        from rosidl_runtime_py.utilities import get_message
    except Exception as exc:
        raise RuntimeError(
            "Could not import ROS 2 bag tools. Source ROS first:\n"
            "  source /opt/ros/jazzy/setup.bash\n"
            "  source \"$THESIS_ROOT/ros2_ws/install/setup.bash\""
        ) from exc

    return (
        SequentialReader,
        StorageOptions,
        ConverterOptions,
        deserialize_message,
        get_message,
    )


def find_track_id_field(msg: object) -> int:
    candidate_names = [
        "target_track_id",
        "track_id",
        "id",
        "target_id",
    ]

    for name in candidate_names:
        if hasattr(msg, name):
            try:
                return int(getattr(msg, name))
            except Exception:
                pass

    for nested_name in ["target", "track"]:
        if not hasattr(msg, nested_name):
            continue
        nested = getattr(msg, nested_name)
        for name in candidate_names:
            if hasattr(nested, name):
                try:
                    return int(getattr(nested, name))
                except Exception:
                    pass

    return 0


def detect_storage_id(bag_path: Path) -> str:
    metadata_path = bag_path / "metadata.yaml"

    if metadata_path.exists():
        text = metadata_path.read_text(errors="ignore")
        if (
            "storage_identifier: mcap" in text
            or "storage_id: mcap" in text
        ):
            return "mcap"
        if (
            "storage_identifier: sqlite3" in text
            or "storage_id: sqlite3" in text
        ):
            return "sqlite3"

    if list(bag_path.glob("*.mcap")):
        return "mcap"
    if list(bag_path.glob("*.db3")):
        return "sqlite3"
    return "sqlite3"


def header_time_ns(msg: object) -> Optional[int]:
    if not hasattr(msg, "header"):
        return None
    header = getattr(msg, "header")
    if not hasattr(header, "stamp"):
        return None
    stamp = getattr(header, "stamp")

    try:
        return (
            int(stamp.sec) * 1_000_000_000
            + int(stamp.nanosec)
        )
    except Exception:
        return None


def target_bbox_validity(msg: object) -> Optional[bool]:
    """Return bbox validity when the target message exposes bbox fields."""
    names = ("cx", "cy", "w", "h")
    if not all(hasattr(msg, name) for name in names):
        return None

    try:
        cx, cy, width, height = (
            float(getattr(msg, name))
            for name in names
        )
    except (TypeError, ValueError):
        return False

    return bool(
        all(
            math.isfinite(value)
            for value in (cx, cy, width, height)
        )
        and width > 0.0
        and height > 0.0
    )


def sample_output_id(sample: TargetSample) -> int:
    if sample.track_id == 0:
        return 0
    if sample.bbox_valid is False:
        return 0
    return sample.track_id


def nearest_header_anchor_time_ns(
    *,
    bag_time_ns: int,
    anchors: List[tuple[int, int]],
) -> Optional[int]:
    """Project one bag timestamp using the nearest header-bearing sample."""
    if not anchors:
        return None

    bag_times = [anchor[0] for anchor in anchors]
    index = bisect.bisect_left(bag_times, bag_time_ns)

    candidates: List[tuple[int, int]] = []

    if index > 0:
        candidates.append(anchors[index - 1])
    if index < len(anchors):
        candidates.append(anchors[index])

    anchor_bag_ns, anchor_header_ns = min(
        candidates,
        key=lambda anchor: (
            abs(anchor[0] - bag_time_ns),
            anchor[0],
        ),
    )

    return (
        anchor_header_ns
        + bag_time_ns
        - anchor_bag_ns
    )


def evaluation_message_time_ns(
    *,
    bag_time_ns: int,
    message_header_time_ns: Optional[int],
    timebase: str,
    header_from_bag_offset_ns: Optional[int],
    header_anchors: Optional[List[tuple[int, int]]] = None,
) -> Optional[int]:
    """Resolve headerless messages onto the evaluation timeline."""
    if timebase == "bag":
        return bag_time_ns

    if timebase != "header":
        raise ValueError(f"Unsupported timebase: {timebase}")

    if message_header_time_ns is not None:
        return message_header_time_ns

    if header_anchors:
        return nearest_header_anchor_time_ns(
            bag_time_ns=bag_time_ns,
            anchors=header_anchors,
        )

    if header_from_bag_offset_ns is None:
        return None

    return bag_time_ns + header_from_bag_offset_ns


def read_evaluation_samples_from_bag(
    bag_path: Path,
    target_topics: Iterable[str],
    status_topics: Iterable[str],
    timebase: str,
) -> EvaluationBagSamples:
    """Read target and JSON status topics using one common time origin."""
    (
        SequentialReader,
        StorageOptions,
        ConverterOptions,
        deserialize_message,
        get_message,
    ) = import_rosbag_tools()

    if timebase not in {"bag", "header"}:
        raise ValueError(f"Unsupported timebase: {timebase}")

    requested_targets = set(target_topics)
    requested_statuses = set(status_topics)
    requested = requested_targets | requested_statuses

    reader = SequentialReader()
    storage_options = StorageOptions(
        uri=str(bag_path),
        storage_id=detect_storage_id(bag_path),
    )
    converter_options = ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    reader.open(storage_options, converter_options)

    topic_types = {
        metadata.name: metadata.type
        for metadata in reader.get_all_topics_and_types()
    }
    available_requested = requested & set(topic_types)

    if not available_requested:
        raise RuntimeError(
            "None of the requested topics were found in bag. "
            f"Requested={sorted(requested)}. "
            f"Available={sorted(topic_types)}"
        )

    available_targets = requested_targets & set(topic_types)
    available_statuses = requested_statuses & set(topic_types)

    image_topics = [
        topic
        for topic in IMAGE_TOPICS_FOR_T0
        if topic in topic_types
    ]
    topics_needed_for_t0 = set(available_requested)

    if timebase == "header":
        topics_needed_for_t0 |= set(image_topics)

    t0_types = {
        topic: get_message(topic_types[topic])
        for topic in topics_needed_for_t0
    }
    first_image_time_ns: Optional[int] = None
    first_image_bag_time_ns: Optional[int] = None
    first_requested_time_ns: Optional[int] = None
    first_requested_bag_time_ns: Optional[int] = None
    header_anchors: List[tuple[int, int]] = []

    while reader.has_next():
        topic, data, bag_time_ns = reader.read_next()

        if topic not in topics_needed_for_t0:
            continue

        msg = deserialize_message(data, t0_types[topic])
        message_header_time_ns = header_time_ns(msg)
        message_time_ns = (
            message_header_time_ns
            if timebase == "header"
            else bag_time_ns
        )

        if (
            topic in available_requested
            and first_requested_bag_time_ns is None
        ):
            first_requested_bag_time_ns = bag_time_ns

        if (
            topic in available_requested
            and first_requested_time_ns is None
            and message_time_ns is not None
        ):
            first_requested_time_ns = message_time_ns

        if (
            topic in image_topics
            and first_image_bag_time_ns is None
        ):
            first_image_bag_time_ns = bag_time_ns

        if (
            topic in image_topics
            and first_image_time_ns is None
            and message_header_time_ns is not None
        ):
            first_image_time_ns = message_header_time_ns

        if (
            timebase == "header"
            and topic in available_targets
            and message_header_time_ns is not None
        ):
            header_anchors.append(
                (
                    bag_time_ns,
                    message_header_time_ns,
                )
            )

        if timebase == "bag":
            if first_requested_bag_time_ns is not None:
                break
        elif first_image_time_ns is not None:
            break

    if timebase == "header" and not header_anchors:
        reader = SequentialReader()
        reader.open(storage_options, converter_options)

        anchor_types = {
            topic: get_message(topic_types[topic])
            for topic in available_targets
        }

        while reader.has_next():
            topic, data, bag_time_ns = reader.read_next()

            if topic not in available_targets:
                continue

            msg = deserialize_message(
                data,
                anchor_types[topic],
            )
            message_header_time_ns = header_time_ns(msg)

            if message_header_time_ns is None:
                continue

            header_anchors.append(
                (
                    bag_time_ns,
                    message_header_time_ns,
                )
            )

            if first_requested_time_ns is None:
                first_requested_time_ns = (
                    message_header_time_ns
                )

            if first_requested_bag_time_ns is None:
                first_requested_bag_time_ns = bag_time_ns

    header_anchors.sort(
        key=lambda anchor: (
            anchor[0],
            anchor[1],
        )
    )

    deduplicated_header_anchors: List[
        tuple[int, int]
    ] = []

    for anchor in header_anchors:
        if (
            deduplicated_header_anchors
            and anchor[0]
            == deduplicated_header_anchors[-1][0]
        ):
            deduplicated_header_anchors[-1] = anchor
        else:
            deduplicated_header_anchors.append(anchor)

    header_anchors = deduplicated_header_anchors

    header_from_bag_offset_ns: Optional[int] = None

    if (
        timebase == "header"
        and first_image_time_ns is not None
        and first_image_bag_time_ns is not None
    ):
        t0_ns = first_image_time_ns
        header_from_bag_offset_ns = (
            first_image_time_ns
            - first_image_bag_time_ns
        )
    elif timebase == "bag":
        t0_ns = first_requested_bag_time_ns
    elif header_anchors:
        t0_ns = header_anchors[0][1]
    else:
        t0_ns = first_requested_time_ns

    if t0_ns is None:
        raise RuntimeError(
            "Could not determine time origin for evaluation"
        )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    message_types = {
        topic: get_message(topic_types[topic])
        for topic in available_requested
    }

    target_samples: Dict[str, List[TargetSample]] = {
        topic: []
        for topic in requested_targets
    }
    status_samples: Dict[str, List[StatusSample]] = {
        topic: []
        for topic in requested_statuses
    }

    while reader.has_next():
        topic, data, bag_time_ns = reader.read_next()

        if topic not in available_requested:
            continue

        msg = deserialize_message(
            data,
            message_types[topic],
        )
        message_header_time_ns = header_time_ns(msg)

        message_time_ns = evaluation_message_time_ns(
            bag_time_ns=bag_time_ns,
            message_header_time_ns=message_header_time_ns,
            timebase=timebase,
            header_from_bag_offset_ns=(
                header_from_bag_offset_ns
            ),
            header_anchors=header_anchors,
        )

        if message_time_ns is None:
            continue

        t_s = (message_time_ns - t0_ns) / 1e9

        if topic in available_targets:
            sample = TargetSample(
                t_s=t_s,
                track_id=find_track_id_field(msg),
                bbox_valid=target_bbox_validity(msg),
            )
            topic_samples = target_samples[topic]

            if (
                topic_samples
                and sample.t_s < topic_samples[-1].t_s
            ):
                continue

            if (
                topic_samples
                and sample.t_s == topic_samples[-1].t_s
            ):
                topic_samples[-1] = sample
            else:
                topic_samples.append(sample)

        if topic in available_statuses:
            raw_payload = getattr(msg, "data", None)

            if not isinstance(raw_payload, str):
                parsed = StatusSample(
                    t_s=t_s,
                    state=None,
                    target_track_id=None,
                    candidate_track_id=None,
                    publication_suppressed_reason=None,
                    positive_memory_updated=None,
                    positive_memory_update_reason=None,
                    positive_memory_bootstrap_event=None,
                    hard_negative_events=(),
                    available_fields=frozenset(),
                    payload_valid=False,
                )
            else:
                parsed = parse_status_payload(
                    t_s,
                    raw_payload,
                )

            topic_statuses = status_samples[topic]

            if (
                topic_statuses
                and parsed.t_s < topic_statuses[-1].t_s
            ):
                continue

            if (
                topic_statuses
                and parsed.t_s == topic_statuses[-1].t_s
            ):
                topic_statuses[-1] = parsed
            else:
                topic_statuses.append(parsed)

    return EvaluationBagSamples(
        target_samples=target_samples,
        status_samples=status_samples,
        time_origin_ns=int(t0_ns),
    )


def read_target_samples_from_bag(
    bag_path: Path,
    topics: Iterable[str],
    timebase: str,
) -> Dict[str, List[TargetSample]]:
    """Compatibility wrapper for selected-target-only evaluators."""
    result = read_evaluation_samples_from_bag(
        bag_path=bag_path,
        target_topics=topics,
        status_topics=(),
        timebase=timebase,
    )
    return result.target_samples


def read_status_samples_from_bag(
    bag_path: Path,
    topics: Iterable[str],
    timebase: str,
) -> Dict[str, List[StatusSample]]:
    """Read TIM status topics using the authoritative bag origin."""
    result = read_evaluation_samples_from_bag(
        bag_path=bag_path,
        target_topics=(),
        status_topics=topics,
        timebase=timebase,
    )
    return result.status_samples


def sample_at_time(
    samples: List[TargetSample],
    t_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> tuple[TargetSample | None, FreshnessResult]:
    if not samples or t_s < samples[0].t_s:
        return (
            None,
            FreshnessResult(
                "missing_output",
                False,
                None,
                None,
            ),
        )

    low = 0
    high = len(samples) - 1
    while low <= high:
        middle = (low + high) // 2
        if samples[middle].t_s <= t_s:
            low = middle + 1
        else:
            high = middle - 1

    sample = samples[max(0, high)]
    freshness = classify_relative_freshness(
        now_s=t_s,
        source_time_s=sample.t_s,
        max_age_s=max_output_age_s,
    )
    return sample, freshness


def sample_id_at_time(
    samples: List[TargetSample],
    t_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> int:
    sample, freshness = sample_at_time(
        samples,
        t_s,
        max_output_age_s,
    )
    if sample is None or not freshness.fresh:
        return 0
    return sample_output_id(sample)


def iter_interval_slices(
    interval: AnnotationInterval,
    step_s: float,
) -> Iterator[IntervalSlice]:
    """Yield the exact authoritative integration slices for one interval."""
    if step_s <= 0.0 or not math.isfinite(step_s):
        raise ValueError("step_s must be finite and greater than zero")
    if interval.duration_s <= 0.0:
        return

    raw_count = interval.duration_s / step_s
    nearest_count = round(raw_count)
    if math.isclose(
        raw_count,
        nearest_count,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        count = max(1, int(nearest_count))
    else:
        count = max(1, int(math.ceil(raw_count)))
    for index in range(count):
        time_s = min(
            interval.end_s,
            interval.start_s + index * step_s,
        )
        if index < count - 1:
            duration_s = step_s
        else:
            duration_s = interval.end_s - time_s
            if duration_s <= 0.0:
                duration_s = min(
                    step_s,
                    interval.duration_s,
                )
        yield IntervalSlice(
            t_s=time_s,
            duration_s=duration_s,
        )


def make_time_grid(
    interval: AnnotationInterval,
    step_s: float,
) -> List[float]:
    return [
        item.t_s
        for item in iter_interval_slices(interval, step_s)
    ]



@dataclass(frozen=True)
class ClassifiedSlice:
    """One authoritative interval slice with selected-target classification."""

    annotation_index: int
    bag_name: str
    event_type: str
    t_s: float
    duration_s: float
    classification: str
    output_track_id: int
    correct_target_track_id: int
    freshness_status: str

    @property
    def end_s(self) -> float:
        return self.t_s + self.duration_s


@dataclass(frozen=True)
class ContiguousEpisode:
    """One maximal contiguous run of an authoritative classification."""

    classification: str
    event_type: str
    start_s: float
    end_s: float
    duration_s: float
    slice_count: int
    output_track_ids: tuple[int, ...]


def classify_interval_slices(
    annotations: List[AnnotationInterval],
    samples: List[TargetSample],
    step_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> List[ClassifiedSlice]:
    """Classify every authoritative integration slice exactly once."""
    classified: List[ClassifiedSlice] = []

    for annotation_index, interval in enumerate(annotations):
        label = interval.target_label.upper()
        event_type = interval.event_type.strip() or "unlabeled"

        for item in iter_interval_slices(interval, step_s):
            sample, freshness = sample_at_time(
                samples,
                item.t_s,
                max_output_age_s,
            )
            output_id = (
                sample_output_id(sample)
                if sample is not None and freshness.fresh
                else 0
            )

            if label == "NO_TARGET_SELECTED":
                classification = "no_target_selected"
            elif (
                not interval.target_visible
                or label == "TARGET_NOT_VISIBLE"
            ):
                classification = (
                    "target_absent_output"
                    if output_id != 0
                    else "target_absent_clear"
                )
            elif output_id == interval.correct_target_track_id:
                classification = "correct"
            elif output_id == 0:
                classification = "lost"
            else:
                classification = "wrong"

            classified.append(
                ClassifiedSlice(
                    annotation_index=annotation_index,
                    bag_name=interval.bag_name,
                    event_type=event_type,
                    t_s=item.t_s,
                    duration_s=item.duration_s,
                    classification=classification,
                    output_track_id=output_id,
                    correct_target_track_id=(
                        interval.correct_target_track_id
                    ),
                    freshness_status=freshness.status,
                )
            )

    return classified


def contiguous_episodes(
    slices: Iterable[ClassifiedSlice],
    classification: Optional[str] = None,
    tolerance_s: float = 1e-9,
) -> List[ContiguousEpisode]:
    """Merge adjacent slices without crossing gaps or event boundaries."""
    if tolerance_s < 0.0 or not math.isfinite(tolerance_s):
        raise ValueError(
            "tolerance_s must be finite and non-negative"
        )

    selected = [
        item
        for item in slices
        if (
            classification is None
            or item.classification == classification
        )
    ]
    if not selected:
        return []

    episodes: List[ContiguousEpisode] = []
    current = selected[0]
    start_s = current.t_s
    end_s = current.end_s
    slice_count = 1
    output_track_ids = [current.output_track_id]

    def finish() -> None:
        episodes.append(
            ContiguousEpisode(
                classification=current.classification,
                event_type=current.event_type,
                start_s=start_s,
                end_s=end_s,
                duration_s=end_s - start_s,
                slice_count=slice_count,
                output_track_ids=tuple(
                    dict.fromkeys(output_track_ids)
                ),
            )
        )

    for item in selected[1:]:
        adjacent = abs(item.t_s - end_s) <= tolerance_s
        compatible = (
            item.classification == current.classification
            and item.event_type == current.event_type
            and item.bag_name == current.bag_name
            and adjacent
        )

        if compatible:
            end_s = item.end_s
            slice_count += 1
            output_track_ids.append(item.output_track_id)
            continue

        finish()
        current = item
        start_s = item.t_s
        end_s = item.end_s
        slice_count = 1
        output_track_ids = [item.output_track_id]

    finish()
    return episodes




@dataclass(frozen=True)
class EpisodeMetrics:
    """Aggregate metrics derived from authoritative classified episodes."""

    wrong_target_burst_count: int
    wrong_target_total_duration_s: float
    longest_wrong_target_burst_s: float
    wrong_handover_count: int
    target_absent_output_episode_count: int
    target_absent_output_total_duration_s: float
    longest_target_absent_output_episode_s: float


def count_output_handovers(
    slices: Iterable[ClassifiedSlice],
    *,
    classification: str = "wrong",
) -> int:
    """Count non-zero selected-ID transitions inside contiguous episodes."""
    handovers = 0

    for episode_slices in _contiguous_slice_groups(
        slices,
        classification=classification,
    ):
        previous_id: Optional[int] = None

        for item in episode_slices:
            current_id = item.output_track_id
            if current_id == 0:
                continue
            if (
                previous_id is not None
                and current_id != previous_id
            ):
                handovers += 1
            previous_id = current_id

    return handovers


def _contiguous_slice_groups(
    slices: Iterable[ClassifiedSlice],
    *,
    classification: Optional[str] = None,
    tolerance_s: float = 1e-9,
) -> List[List[ClassifiedSlice]]:
    """Return contiguous slice groups using the episode boundary contract."""
    if tolerance_s < 0.0 or not math.isfinite(tolerance_s):
        raise ValueError(
            "tolerance_s must be finite and non-negative"
        )

    selected = [
        item
        for item in slices
        if (
            classification is None
            or item.classification == classification
        )
    ]
    if not selected:
        return []

    groups: List[List[ClassifiedSlice]] = []
    current_group = [selected[0]]

    for item in selected[1:]:
        previous = current_group[-1]
        adjacent = abs(item.t_s - previous.end_s) <= tolerance_s
        compatible = (
            item.classification == previous.classification
            and item.event_type == previous.event_type
            and item.bag_name == previous.bag_name
            and adjacent
        )

        if compatible:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]

    groups.append(current_group)
    return groups


def summarise_episode_metrics(
    slices: Iterable[ClassifiedSlice],
) -> EpisodeMetrics:
    """Calculate deterministic burst, handover and absent-output metrics."""
    materialised = list(slices)

    wrong_episodes = contiguous_episodes(
        materialised,
        classification="wrong",
    )
    absent_output_episodes = contiguous_episodes(
        materialised,
        classification="target_absent_output",
    )

    wrong_durations = [
        episode.duration_s
        for episode in wrong_episodes
    ]
    absent_durations = [
        episode.duration_s
        for episode in absent_output_episodes
    ]

    return EpisodeMetrics(
        wrong_target_burst_count=len(wrong_episodes),
        wrong_target_total_duration_s=sum(wrong_durations),
        longest_wrong_target_burst_s=max(
            wrong_durations,
            default=0.0,
        ),
        wrong_handover_count=count_output_handovers(
            materialised,
            classification="wrong",
        ),
        target_absent_output_episode_count=(
            len(absent_output_episodes)
        ),
        target_absent_output_total_duration_s=sum(
            absent_durations
        ),
        longest_target_absent_output_episode_s=max(
            absent_durations,
            default=0.0,
        ),
    )




DEFAULT_STABLE_RECOVERY_S = 0.25


@dataclass(frozen=True)
class RecoveryEpisode:
    """One physical-absence recovery opportunity."""

    bag_name: str
    event_type: str
    disturbance_start_s: float
    disturbance_end_s: float
    first_eligible_recovery_s: Optional[float]
    first_correct_output_s: Optional[float]
    first_stable_correct_output_s: Optional[float]
    first_correct_latency_s: Optional[float]
    stable_correct_latency_s: Optional[float]
    result: str
    wrong_target_duration_before_recovery_s: float
    lost_duration_before_recovery_s: float
    target_track_id_before_disturbance: int
    target_track_id_after_recovery: int
    recovery_identity: str
    stable_recovery_required_s: float


def _annotation_target_absent(
    interval: AnnotationInterval,
) -> bool:
    label = interval.target_label.upper()
    return (
        label != "NO_TARGET_SELECTED"
        and (
            not interval.target_visible
            or label == "TARGET_NOT_VISIBLE"
        )
    )


def _annotation_target_visible(
    interval: AnnotationInterval,
) -> bool:
    label = interval.target_label.upper()
    return (
        interval.target_visible
        and label not in {
            "NO_TARGET_SELECTED",
            "TARGET_NOT_VISIBLE",
        }
    )


def _first_stable_correct_start(
    slices: List[ClassifiedSlice],
    stable_duration_s: float,
    tolerance_s: float,
) -> Optional[float]:
    """Return the start of the first sufficiently persistent correct run."""
    run_start: Optional[float] = None
    run_end: Optional[float] = None

    for item in slices:
        if item.classification != "correct":
            run_start = None
            run_end = None
            continue

        if (
            run_start is None
            or run_end is None
            or abs(item.t_s - run_end) > tolerance_s
        ):
            run_start = item.t_s

        run_end = item.end_s

        if run_end - run_start + tolerance_s >= stable_duration_s:
            return run_start

    return None


def build_absence_recovery_episodes(
    annotations: List[AnnotationInterval],
    classified_slices: Iterable[ClassifiedSlice],
    stable_duration_s: float = DEFAULT_STABLE_RECOVERY_S,
    tolerance_s: float = 1e-9,
) -> List[RecoveryEpisode]:
    """Evaluate physical-absence recovery without treating absence as failure."""
    if (
        stable_duration_s <= 0.0
        or not math.isfinite(stable_duration_s)
    ):
        raise ValueError(
            "stable_duration_s must be finite and greater than zero"
        )
    if tolerance_s < 0.0 or not math.isfinite(tolerance_s):
        raise ValueError(
            "tolerance_s must be finite and non-negative"
        )

    materialised = list(classified_slices)
    indexed_by_bag: Dict[
        str,
        List[tuple[int, AnnotationInterval]],
    ] = {}

    for index, interval in enumerate(annotations):
        indexed_by_bag.setdefault(
            interval.bag_name,
            [],
        ).append((index, interval))

    episodes: List[RecoveryEpisode] = []

    for bag_name in sorted(indexed_by_bag):
        bag_rows = sorted(
            indexed_by_bag[bag_name],
            key=lambda pair: (
                pair[1].start_s,
                pair[1].end_s,
                pair[0],
            ),
        )
        sequence_end_s = max(
            interval.end_s
            for _, interval in bag_rows
        )

        for position, (_, absent) in enumerate(bag_rows):
            if not _annotation_target_absent(absent):
                continue

            previous_visible = next(
                (
                    interval
                    for _, interval in reversed(
                        bag_rows[:position]
                    )
                    if (
                        _annotation_target_visible(interval)
                        and abs(
                            interval.end_s - absent.start_s
                        ) <= tolerance_s
                    )
                ),
                None,
            )

            next_visible_position: Optional[int] = None
            next_visible: Optional[AnnotationInterval] = None

            if position + 1 < len(bag_rows):
                candidate = bag_rows[position + 1][1]
                if (
                    _annotation_target_visible(candidate)
                    and abs(
                        candidate.start_s - absent.end_s
                    ) <= tolerance_s
                ):
                    next_visible_position = position + 1
                    next_visible = candidate

            before_id = (
                previous_visible.correct_target_track_id
                if previous_visible is not None
                else 0
            )

            if (
                next_visible is None
                or next_visible_position is None
            ):
                episodes.append(
                    RecoveryEpisode(
                        bag_name=bag_name,
                        event_type="target_absent",
                        disturbance_start_s=absent.start_s,
                        disturbance_end_s=absent.end_s,
                        first_eligible_recovery_s=None,
                        first_correct_output_s=None,
                        first_stable_correct_output_s=None,
                        first_correct_latency_s=None,
                        stable_correct_latency_s=None,
                        result="censored",
                        wrong_target_duration_before_recovery_s=0.0,
                        lost_duration_before_recovery_s=0.0,
                        target_track_id_before_disturbance=before_id,
                        target_track_id_after_recovery=0,
                        recovery_identity="unavailable",
                        stable_recovery_required_s=stable_duration_s,
                    )
                )
                continue

            eligible_s = next_visible.start_s
            after_id = next_visible.correct_target_track_id

            next_absence = next(
                (
                    interval
                    for _, interval in bag_rows[
                        next_visible_position + 1:
                    ]
                    if _annotation_target_absent(interval)
                ),
                None,
            )

            if next_absence is not None:
                episode_end_s = next_absence.start_s
                unsuccessful_result = "failure"
            else:
                episode_end_s = sequence_end_s
                unsuccessful_result = "censored"

            episode_slices = [
                item
                for item in materialised
                if (
                    item.bag_name == bag_name
                    and item.t_s + tolerance_s >= eligible_s
                    and item.t_s < episode_end_s - tolerance_s
                )
            ]

            first_correct = next(
                (
                    item.t_s
                    for item in episode_slices
                    if item.classification == "correct"
                ),
                None,
            )
            first_stable = _first_stable_correct_start(
                episode_slices,
                stable_duration_s,
                tolerance_s,
            )

            recovery_cutoff = (
                first_stable
                if first_stable is not None
                else episode_end_s
            )

            wrong_before = sum(
                item.duration_s
                for item in episode_slices
                if (
                    item.t_s < recovery_cutoff - tolerance_s
                    and item.classification == "wrong"
                )
            )
            lost_before = sum(
                item.duration_s
                for item in episode_slices
                if (
                    item.t_s < recovery_cutoff - tolerance_s
                    and item.classification == "lost"
                )
            )

            if first_stable is not None:
                result = "success"
            else:
                result = unsuccessful_result

            if before_id == 0 or after_id == 0:
                recovery_identity = "unavailable"
            elif before_id == after_id:
                recovery_identity = "same_id"
            else:
                recovery_identity = "new_id"

            episodes.append(
                RecoveryEpisode(
                    bag_name=bag_name,
                    event_type=(
                        next_visible.event_type.strip()
                        or "unlabeled"
                    ),
                    disturbance_start_s=absent.start_s,
                    disturbance_end_s=absent.end_s,
                    first_eligible_recovery_s=eligible_s,
                    first_correct_output_s=first_correct,
                    first_stable_correct_output_s=first_stable,
                    first_correct_latency_s=(
                        None
                        if first_correct is None
                        else first_correct - eligible_s
                    ),
                    stable_correct_latency_s=(
                        None
                        if first_stable is None
                        else first_stable - eligible_s
                    ),
                    result=result,
                    wrong_target_duration_before_recovery_s=(
                        wrong_before
                    ),
                    lost_duration_before_recovery_s=lost_before,
                    target_track_id_before_disturbance=before_id,
                    target_track_id_after_recovery=after_id,
                    recovery_identity=recovery_identity,
                    stable_recovery_required_s=stable_duration_s,
                )
            )

    return episodes




STATUS_FIELD_STATE = "state"
STATUS_FIELD_CANDIDATE_TRACK_ID = "candidate_track_id"
STATUS_FIELD_SUPPRESSION_REASON = "publication_suppressed_reason"
STATUS_FIELD_POSITIVE_MEMORY_UPDATED = "positive_memory_updated"
STATUS_FIELD_POSITIVE_MEMORY_BOOTSTRAP_EVENT = (
    "positive_memory_bootstrap_event"
)
STATUS_FIELD_HARD_NEGATIVE_EVENTS = "hard_negative_events"


@dataclass(frozen=True)
class StatusSample:
    """One parsed TIM-MARS status payload with field availability."""

    t_s: float
    state: Optional[str]
    target_track_id: Optional[int]
    candidate_track_id: Optional[int]
    publication_suppressed_reason: Optional[str]
    positive_memory_updated: Optional[bool]
    positive_memory_update_reason: Optional[str]
    positive_memory_bootstrap_event: Optional[
        dict[str, object]
    ]
    hard_negative_events: tuple[dict[str, object], ...]
    available_fields: frozenset[str]
    payload_valid: bool


@dataclass(frozen=True)
class StateOccupancy:
    """Half-open status-state occupancy with explicit availability."""

    available: bool
    total_duration_s: float
    duration_by_state_s: Dict[str, float]
    sample_count: int
    invalid_payload_count: int


def _optional_int(
    payload: dict[str, object],
    field: str,
) -> Optional[int]:
    if field not in payload or payload[field] is None:
        return None
    try:
        return int(payload[field])
    except (TypeError, ValueError):
        return None


def _optional_bool(
    payload: dict[str, object],
    field: str,
) -> Optional[bool]:
    if field not in payload or payload[field] is None:
        return None

    value = payload[field]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return None


def parse_status_payload(
    t_s: float,
    raw_payload: str,
) -> StatusSample:
    """Parse one schema-version-tolerant TIM-MARS status JSON payload."""
    try:
        decoded = json.loads(raw_payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return StatusSample(
            t_s=t_s,
            state=None,
            target_track_id=None,
            candidate_track_id=None,
            publication_suppressed_reason=None,
            positive_memory_updated=None,
            positive_memory_update_reason=None,
            positive_memory_bootstrap_event=None,
            hard_negative_events=(),
            available_fields=frozenset(),
            payload_valid=False,
        )

    if not isinstance(decoded, dict):
        return StatusSample(
            t_s=t_s,
            state=None,
            target_track_id=None,
            candidate_track_id=None,
            publication_suppressed_reason=None,
            positive_memory_updated=None,
            positive_memory_update_reason=None,
            positive_memory_bootstrap_event=None,
            hard_negative_events=(),
            available_fields=frozenset(),
            payload_valid=False,
        )

    available_fields = frozenset(
        str(key)
        for key in decoded
    )

    state_value = decoded.get("state")
    state = (
        str(state_value).strip()
        if state_value is not None
        and str(state_value).strip()
        else None
    )

    suppression_value = decoded.get(
        STATUS_FIELD_SUPPRESSION_REASON
    )
    suppression_reason = (
        str(suppression_value).strip()
        if suppression_value is not None
        and str(suppression_value).strip()
        else None
    )

    update_reason_value = decoded.get(
        "positive_memory_update_reason"
    )
    update_reason = (
        str(update_reason_value).strip()
        if update_reason_value is not None
        and str(update_reason_value).strip()
        else None
    )

    raw_bootstrap_event = decoded.get(
        STATUS_FIELD_POSITIVE_MEMORY_BOOTSTRAP_EVENT
    )
    positive_memory_bootstrap_event = (
        raw_bootstrap_event
        if isinstance(raw_bootstrap_event, dict)
        else None
    )

    raw_events = decoded.get(
        STATUS_FIELD_HARD_NEGATIVE_EVENTS,
        [],
    )
    if isinstance(raw_events, list):
        hard_negative_events = tuple(
            event
            for event in raw_events
            if isinstance(event, dict)
        )
    else:
        hard_negative_events = ()

    return StatusSample(
        t_s=float(t_s),
        state=state,
        target_track_id=_optional_int(
            decoded,
            "target_track_id",
        ),
        candidate_track_id=_optional_int(
            decoded,
            STATUS_FIELD_CANDIDATE_TRACK_ID,
        ),
        publication_suppressed_reason=suppression_reason,
        positive_memory_updated=_optional_bool(
            decoded,
            STATUS_FIELD_POSITIVE_MEMORY_UPDATED,
        ),
        positive_memory_update_reason=update_reason,
        positive_memory_bootstrap_event=(
            positive_memory_bootstrap_event
        ),
        hard_negative_events=hard_negative_events,
        available_fields=available_fields,
        payload_valid=True,
    )


def status_schema_availability(
    samples: Iterable[StatusSample],
) -> Dict[str, bool]:
    """Report whether each diagnostic field exists in any valid payload."""
    materialised = [
        sample
        for sample in samples
        if sample.payload_valid
    ]

    fields = (
        STATUS_FIELD_STATE,
        STATUS_FIELD_CANDIDATE_TRACK_ID,
        STATUS_FIELD_SUPPRESSION_REASON,
        STATUS_FIELD_POSITIVE_MEMORY_UPDATED,
        STATUS_FIELD_POSITIVE_MEMORY_BOOTSTRAP_EVENT,
        STATUS_FIELD_HARD_NEGATIVE_EVENTS,
    )

    return {
        field: any(
            field in sample.available_fields
            for sample in materialised
        )
        for field in fields
    }


def compute_state_occupancy(
    samples: Iterable[StatusSample],
    end_s: Optional[float] = None,
) -> StateOccupancy:
    """Integrate latest-status state occupancy over half-open intervals."""
    materialised = list(samples)
    invalid_count = sum(
        not sample.payload_valid
        for sample in materialised
    )
    valid = sorted(
        (
            sample
            for sample in materialised
            if sample.payload_valid
            and sample.state is not None
        ),
        key=lambda sample: sample.t_s,
    )

    deduplicated: List[StatusSample] = []
    for sample in valid:
        if (
            deduplicated
            and sample.t_s < deduplicated[-1].t_s
        ):
            continue
        if (
            deduplicated
            and sample.t_s == deduplicated[-1].t_s
        ):
            deduplicated[-1] = sample
        else:
            deduplicated.append(sample)

    if not deduplicated:
        return StateOccupancy(
            available=False,
            total_duration_s=0.0,
            duration_by_state_s={},
            sample_count=0,
            invalid_payload_count=invalid_count,
        )

    if end_s is None:
        resolved_end_s = deduplicated[-1].t_s
    else:
        resolved_end_s = float(end_s)

    if (
        not math.isfinite(resolved_end_s)
        or resolved_end_s < deduplicated[0].t_s
    ):
        raise ValueError(
            "end_s must be finite and not precede the first status sample"
        )

    duration_by_state: Dict[str, float] = {}

    for index, sample in enumerate(deduplicated):
        if index + 1 < len(deduplicated):
            interval_end_s = min(
                deduplicated[index + 1].t_s,
                resolved_end_s,
            )
        else:
            interval_end_s = resolved_end_s

        duration_s = max(
            0.0,
            interval_end_s - sample.t_s,
        )
        duration_by_state[sample.state] = (
            duration_by_state.get(sample.state, 0.0)
            + duration_s
        )

        if interval_end_s >= resolved_end_s:
            break

    return StateOccupancy(
        available=True,
        total_duration_s=sum(duration_by_state.values()),
        duration_by_state_s=dict(
            sorted(duration_by_state.items())
        ),
        sample_count=len(deduplicated),
        invalid_payload_count=invalid_count,
    )




RECOVERY_ATTEMPT_STATES = frozenset(
    {"UNCERTAIN", "LOST", "REACQUIRED"}
)


@dataclass(frozen=True)
class RecoveryAttempt:
    """One contiguous proposed-candidate recovery attempt."""

    candidate_track_id: int
    start_s: float
    end_s: float
    duration_s: float
    initial_state: str
    final_state: str
    sample_count: int


@dataclass(frozen=True)
class StatusRecoveryMetrics:
    """Status-derived recovery metrics with explicit availability."""

    recovery_attempts_available: bool
    recovery_attempt_count: int
    recovery_attempts: tuple[RecoveryAttempt, ...]
    correct_candidate_suppressed_available: bool
    correct_candidate_suppressed_duration_s: float
    correct_candidate_suppressed_episode_count: int


def _latest_status_at_time(
    samples: List[StatusSample],
    t_s: float,
) -> Optional[StatusSample]:
    """Return the latest valid status sample not later than t_s."""
    latest: Optional[StatusSample] = None

    for sample in samples:
        if sample.t_s > t_s:
            break
        if sample.payload_valid:
            latest = sample

    return latest


def recovery_attempts_from_status(
    samples: Iterable[StatusSample],
    end_s: Optional[float] = None,
) -> Optional[List[RecoveryAttempt]]:
    """Count contiguous candidate proposals during recovery states."""
    materialised = sorted(
        (
            sample
            for sample in samples
            if sample.payload_valid
        ),
        key=lambda sample: sample.t_s,
    )

    if not materialised:
        return None

    availability = status_schema_availability(materialised)
    if not availability[STATUS_FIELD_CANDIDATE_TRACK_ID]:
        return None

    deduplicated: List[StatusSample] = []
    for sample in materialised:
        if (
            deduplicated
            and sample.t_s == deduplicated[-1].t_s
        ):
            deduplicated[-1] = sample
        else:
            deduplicated.append(sample)

    if end_s is None:
        resolved_end_s = deduplicated[-1].t_s
    else:
        resolved_end_s = float(end_s)

    if (
        not math.isfinite(resolved_end_s)
        or resolved_end_s < deduplicated[0].t_s
    ):
        raise ValueError(
            "end_s must be finite and not precede the first status sample"
        )

    attempts: List[RecoveryAttempt] = []
    active_candidate: Optional[int] = None
    active_start_s = 0.0
    active_initial_state = ""
    active_final_state = ""
    active_sample_count = 0

    def finish(end_time_s: float) -> None:
        nonlocal active_candidate
        nonlocal active_start_s
        nonlocal active_initial_state
        nonlocal active_final_state
        nonlocal active_sample_count

        if active_candidate is None:
            return

        attempts.append(
            RecoveryAttempt(
                candidate_track_id=active_candidate,
                start_s=active_start_s,
                end_s=end_time_s,
                duration_s=max(
                    0.0,
                    end_time_s - active_start_s,
                ),
                initial_state=active_initial_state,
                final_state=active_final_state,
                sample_count=active_sample_count,
            )
        )

        active_candidate = None
        active_start_s = 0.0
        active_initial_state = ""
        active_final_state = ""
        active_sample_count = 0

    for sample in deduplicated:
        state = (sample.state or "").upper()
        candidate_id = sample.candidate_track_id

        eligible = (
            state in RECOVERY_ATTEMPT_STATES
            and candidate_id is not None
            and candidate_id != 0
        )

        if not eligible:
            finish(sample.t_s)
            continue

        candidate_id = int(candidate_id)

        if active_candidate is None:
            active_candidate = candidate_id
            active_start_s = sample.t_s
            active_initial_state = state
            active_final_state = state
            active_sample_count = 1
            continue

        if candidate_id != active_candidate:
            finish(sample.t_s)
            active_candidate = candidate_id
            active_start_s = sample.t_s
            active_initial_state = state
            active_final_state = state
            active_sample_count = 1
            continue

        active_final_state = state
        active_sample_count += 1

    finish(resolved_end_s)
    return attempts


def correct_candidate_suppression_metrics(
    classified_slices: Iterable[ClassifiedSlice],
    status_samples: Iterable[StatusSample],
) -> Optional[tuple[float, int]]:
    """Measure suppressed correct candidates using authoritative slices."""
    slices = list(classified_slices)
    statuses = sorted(
        (
            sample
            for sample in status_samples
            if sample.payload_valid
        ),
        key=lambda sample: sample.t_s,
    )

    if not statuses:
        return None

    availability = status_schema_availability(statuses)
    if (
        not availability[STATUS_FIELD_CANDIDATE_TRACK_ID]
        or not availability[STATUS_FIELD_SUPPRESSION_REASON]
    ):
        return None

    suppressed: List[ClassifiedSlice] = []

    for item in slices:
        if item.correct_target_track_id == 0:
            continue

        status = _latest_status_at_time(
            statuses,
            item.t_s,
        )
        if status is None:
            continue

        reason = (
            status.publication_suppressed_reason or ""
        ).strip()

        if (
            status.candidate_track_id
            == item.correct_target_track_id
            and bool(reason)
            and item.classification != "correct"
        ):
            suppressed.append(
                ClassifiedSlice(
                    annotation_index=item.annotation_index,
                    bag_name=item.bag_name,
                    event_type=item.event_type,
                    t_s=item.t_s,
                    duration_s=item.duration_s,
                    classification=(
                        "correct_candidate_suppressed"
                    ),
                    output_track_id=item.output_track_id,
                    correct_target_track_id=(
                        item.correct_target_track_id
                    ),
                    freshness_status=item.freshness_status,
                )
            )

    episodes = contiguous_episodes(
        suppressed,
        classification="correct_candidate_suppressed",
    )

    return (
        sum(item.duration_s for item in suppressed),
        len(episodes),
    )


def summarise_status_recovery_metrics(
    classified_slices: Iterable[ClassifiedSlice],
    status_samples: Iterable[StatusSample],
    end_s: Optional[float] = None,
) -> StatusRecoveryMetrics:
    """Aggregate status-derived attempts and correct suppression."""
    statuses = list(status_samples)
    attempts = recovery_attempts_from_status(
        statuses,
        end_s=end_s,
    )
    suppression = correct_candidate_suppression_metrics(
        classified_slices,
        statuses,
    )

    return StatusRecoveryMetrics(
        recovery_attempts_available=attempts is not None,
        recovery_attempt_count=(
            0 if attempts is None else len(attempts)
        ),
        recovery_attempts=(
            ()
            if attempts is None
            else tuple(attempts)
        ),
        correct_candidate_suppressed_available=(
            suppression is not None
        ),
        correct_candidate_suppressed_duration_s=(
            0.0
            if suppression is None
            else suppression[0]
        ),
        correct_candidate_suppressed_episode_count=(
            0
            if suppression is None
            else suppression[1]
        ),
    )




HARD_NEGATIVE_LEARNING_ACTIONS = frozenset(
    {"stage", "insert", "merge"}
)


@dataclass(frozen=True)
class MemoryEventMetrics:
    """Memory lifecycle and contamination counts."""

    hard_negative_events_available: bool
    hard_negative_event_count: int
    hard_negative_action_counts: Dict[str, int]
    hard_negative_contamination_count: int
    positive_memory_events_available: bool
    positive_memory_update_count: int
    positive_memory_bootstrap_count: int
    positive_memory_contamination_count: int
    total_memory_contamination_count: int


def _event_track_ids(
    event: dict[str, object],
) -> set[int]:
    track_ids: set[int] = set()

    source_track_id = event.get("source_track_id")
    try:
        if source_track_id is not None:
            track_ids.add(int(source_track_id))
    except (TypeError, ValueError):
        pass

    source_track_ids = event.get("source_track_ids")
    if isinstance(source_track_ids, list):
        for value in source_track_ids:
            try:
                track_ids.add(int(value))
            except (TypeError, ValueError):
                continue

    return track_ids


def _classified_slice_at_time(
    slices: List[ClassifiedSlice],
    t_s: float,
    tolerance_s: float = 1e-9,
) -> Optional[ClassifiedSlice]:
    for item in slices:
        if (
            item.t_s - tolerance_s
            <= t_s
            < item.end_s - tolerance_s
        ):
            return item
    return None


def summarise_memory_event_metrics(
    classified_slices: Iterable[ClassifiedSlice],
    status_samples: Iterable[StatusSample],
) -> MemoryEventMetrics:
    """Count lifecycle events and annotation-grounded contamination."""
    slices = sorted(
        list(classified_slices),
        key=lambda item: item.t_s,
    )
    statuses = sorted(
        (
            sample
            for sample in status_samples
            if sample.payload_valid
        ),
        key=lambda sample: sample.t_s,
    )

    availability = status_schema_availability(statuses)

    hard_negative_available = availability.get(
        STATUS_FIELD_HARD_NEGATIVE_EVENTS,
        False,
    )
    positive_update_available = availability.get(
        STATUS_FIELD_POSITIVE_MEMORY_UPDATED,
        False,
    )
    positive_bootstrap_available = availability.get(
        STATUS_FIELD_POSITIVE_MEMORY_BOOTSTRAP_EVENT,
        False,
    )
    positive_available = (
        positive_update_available
        or positive_bootstrap_available
    )

    hard_negative_action_counts: Dict[str, int] = {}
    hard_negative_event_count = 0
    hard_negative_contamination_count = 0
    positive_memory_update_count = 0
    positive_memory_bootstrap_count = 0
    positive_memory_contamination_count = 0

    for status in statuses:
        classified = _classified_slice_at_time(
            slices,
            status.t_s,
        )
        correct_track_id = (
            0
            if classified is None
            else classified.correct_target_track_id
        )

        if hard_negative_available:
            for event in status.hard_negative_events:
                action = str(
                    event.get("action", "")
                ).strip().lower()

                if not action:
                    action = "unknown"

                hard_negative_event_count += 1
                hard_negative_action_counts[action] = (
                    hard_negative_action_counts.get(
                        action,
                        0,
                    )
                    + 1
                )

                if (
                    action in HARD_NEGATIVE_LEARNING_ACTIONS
                    and correct_track_id != 0
                    and correct_track_id
                    in _event_track_ids(event)
                ):
                    hard_negative_contamination_count += 1

        if (
            positive_update_available
            and status.positive_memory_updated is True
        ):
            positive_memory_update_count += 1

            if (
                classified is not None
                and classified.classification == "wrong"
            ):
                positive_memory_contamination_count += 1

        if (
            positive_bootstrap_available
            and status.positive_memory_bootstrap_event
            is not None
        ):
            positive_memory_bootstrap_count += 1

            bootstrap_track_id = (
                status.positive_memory_bootstrap_event.get(
                    "track_id"
                )
            )
            try:
                parsed_bootstrap_track_id = int(
                    bootstrap_track_id
                )
            except (TypeError, ValueError):
                parsed_bootstrap_track_id = 0

            if (
                classified is not None
                and (
                    classified.classification == "wrong"
                    or (
                        correct_track_id != 0
                        and parsed_bootstrap_track_id != 0
                        and parsed_bootstrap_track_id
                        != correct_track_id
                    )
                )
            ):
                positive_memory_contamination_count += 1

    total_contamination = (
        hard_negative_contamination_count
        + positive_memory_contamination_count
    )

    return MemoryEventMetrics(
        hard_negative_events_available=(
            hard_negative_available
        ),
        hard_negative_event_count=(
            hard_negative_event_count
            if hard_negative_available
            else 0
        ),
        hard_negative_action_counts=(
            dict(sorted(hard_negative_action_counts.items()))
            if hard_negative_available
            else {}
        ),
        hard_negative_contamination_count=(
            hard_negative_contamination_count
            if hard_negative_available
            else 0
        ),
        positive_memory_events_available=positive_available,
        positive_memory_update_count=(
            positive_memory_update_count
            if positive_available
            else 0
        ),
        positive_memory_bootstrap_count=(
            positive_memory_bootstrap_count
            if positive_available
            else 0
        ),
        positive_memory_contamination_count=(
            positive_memory_contamination_count
            if positive_available
            else 0
        ),
        total_memory_contamination_count=(
            total_contamination
            if hard_negative_available
            or positive_available
            else 0
        ),
    )



def evaluate_stream(
    annotations: List[AnnotationInterval],
    samples: List[TargetSample],
    step_s: float,
    max_output_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
) -> DurationStats:
    stats = DurationStats()

    for interval in annotations:
        label = interval.target_label.upper()
        for item in iter_interval_slices(interval, step_s):
            sample, freshness = sample_at_time(
                samples,
                item.t_s,
                max_output_age_s,
            )
            if freshness.status == "stale_source":
                stats.stale_output_duration_s += item.duration_s
            output_id = (
                sample_output_id(sample)
                if sample is not None and freshness.fresh
                else 0
            )

            if label == "NO_TARGET_SELECTED":
                stats.no_target_selected_duration_s += item.duration_s
                continue
            if (
                not interval.target_visible
                or label == "TARGET_NOT_VISIBLE"
            ):
                stats.target_not_visible_duration_s += item.duration_s
                if output_id != 0:
                    stats.target_absent_but_output_valid_duration_s += (
                        item.duration_s
                    )
                continue

            stats.visible_target_duration_s += item.duration_s
            if output_id == interval.correct_target_track_id:
                stats.correct_target_duration_s += item.duration_s
            elif output_id == 0:
                stats.lost_target_duration_s += item.duration_s
            else:
                stats.wrong_target_duration_s += item.duration_s

    return stats


def fmt_float(value: float) -> str:
    if isinstance(value, float) and math.isnan(value):
        return "nan"
    return f"{value:.3f}"


def stats_to_row(
    stream_name: str,
    stats: DurationStats,
) -> Dict[str, str]:
    return {
        "stream": stream_name,
        "correct_target_duration_s": fmt_float(
            stats.correct_target_duration_s
        ),
        "wrong_target_duration_s": fmt_float(
            stats.wrong_target_duration_s
        ),
        "lost_target_duration_s": fmt_float(
            stats.lost_target_duration_s
        ),
        "target_not_visible_duration_s": fmt_float(
            stats.target_not_visible_duration_s
        ),
        "target_absent_but_output_valid_duration_s": fmt_float(
            stats.target_absent_but_output_valid_duration_s
        ),
        "no_target_selected_duration_s": fmt_float(
            stats.no_target_selected_duration_s
        ),
        "visible_target_duration_s": fmt_float(
            stats.visible_target_duration_s
        ),
        "stale_output_duration_s": fmt_float(
            stats.stale_output_duration_s
        ),
        "correct_target_ratio": fmt_float(
            stats.correct_target_ratio
        ),
        "wrong_target_ratio": fmt_float(
            stats.wrong_target_ratio
        ),
        "lost_target_ratio": fmt_float(
            stats.lost_target_ratio
        ),
    }
