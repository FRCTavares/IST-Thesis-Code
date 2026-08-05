"""Shared selected-target evaluation semantics.

This module is the single authority for annotation parsing, target-message
validity, bag/header time origins, latest-preceding output freshness, interval
integration, and track-ID correctness classification.
"""

from __future__ import annotations

import csv
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


def read_target_samples_from_bag(
    bag_path: Path,
    topics: Iterable[str],
    timebase: str,
) -> Dict[str, List[TargetSample]]:
    (
        SequentialReader,
        StorageOptions,
        ConverterOptions,
        deserialize_message,
        get_message,
    ) = import_rosbag_tools()

    if timebase not in {"bag", "header"}:
        raise ValueError(f"Unsupported timebase: {timebase}")

    requested = set(topics)
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
    available_targets = requested & set(topic_types)
    if not available_targets:
        raise RuntimeError(
            "None of the requested topics were found in bag. "
            f"Requested={sorted(requested)}. "
            f"Available={sorted(topic_types)}"
        )

    image_topics = [
        topic
        for topic in IMAGE_TOPICS_FOR_T0
        if topic in topic_types
    ]
    topics_needed_for_t0 = set(available_targets)
    if timebase == "header":
        topics_needed_for_t0 |= set(image_topics)

    t0_types = {
        topic: get_message(topic_types[topic])
        for topic in topics_needed_for_t0
    }
    first_image_time_ns: Optional[int] = None
    first_target_time_ns: Optional[int] = None

    while reader.has_next():
        topic, data, bag_time_ns = reader.read_next()
        if topic not in topics_needed_for_t0:
            continue
        msg = deserialize_message(data, t0_types[topic])
        message_time_ns = (
            header_time_ns(msg)
            if timebase == "header"
            else bag_time_ns
        )
        if message_time_ns is None:
            continue

        if (
            topic in available_targets
            and first_target_time_ns is None
        ):
            first_target_time_ns = message_time_ns
        if (
            topic in image_topics
            and first_image_time_ns is None
        ):
            first_image_time_ns = message_time_ns

        if (
            timebase == "header"
            and first_image_time_ns is not None
        ):
            break
        if (
            timebase == "bag"
            and first_target_time_ns is not None
        ):
            break

    if (
        timebase == "header"
        and first_image_time_ns is not None
    ):
        first_time_ns = first_image_time_ns
    elif first_target_time_ns is not None:
        first_time_ns = first_target_time_ns
    else:
        raise RuntimeError(
            "Could not determine time origin for evaluation"
        )

    reader = SequentialReader()
    reader.open(storage_options, converter_options)
    message_types = {
        topic: get_message(topic_types[topic])
        for topic in available_targets
    }
    samples: Dict[str, List[TargetSample]] = {
        topic: []
        for topic in requested
    }

    while reader.has_next():
        topic, data, bag_time_ns = reader.read_next()
        if topic not in available_targets:
            continue
        msg = deserialize_message(data, message_types[topic])
        message_time_ns = (
            header_time_ns(msg)
            if timebase == "header"
            else bag_time_ns
        )
        if message_time_ns is None:
            continue

        sample = TargetSample(
            t_s=(message_time_ns - first_time_ns) * 1e-9,
            track_id=find_track_id_field(msg),
            bbox_valid=target_bbox_validity(msg),
        )
        topic_samples = samples[topic]
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

    return samples


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
