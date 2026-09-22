#!/usr/bin/env python3
"""Post-access source-time correction for the frozen physical-v2 evaluator.

The H01-H03 physical-reference artifacts use source-image semantic time:
positive ``sensor_msgs/Image.header.stamp`` with bag-record time only as the
fallback. The frozen ``evaluate_physical_target_bbox_v2.py`` wrapper instead
inherited the v1 reader, which expresses output times relative to the first
MCAP record.

This wrapper repairs only that clock alignment. It deliberately reuses the
frozen ``physical_target_reference_v2.py`` contract and the unchanged
``physical_target_bbox_evaluation_v2.py`` scoring core. It is a post-access
correctness repair, not a new prospective experiment or scoring contract.

Reference origin:
    first source-image positive header.stamp, else its bag-record timestamp.

Output timestamp precedence:
    positive src_stamp_ns, else positive header.stamp, else bag-record time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_bbox_evaluation_v2 as pbe2  # noqa: E402
import physical_target_reference_v2 as ptr2  # noqa: E402
from evaluate_physical_target_bbox import (  # noqa: E402
    git_commit_and_dirty,
    msg_box_xyxy,
    sha256_file,
)
from evaluate_physical_target_bbox_v2 import write_report as write_v2_report  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_TOPIC_RAW = "/target"
TARGET_TOPIC_TIM = "/target_memory_mars"

REPAIR_VERSION = "p058_source_time_repair_v1"

REFERENCE_TIMESTAMP_POLICY = (
    "first source-image positive header.stamp else bag-record timestamp"
)
OUTPUT_TIMESTAMP_POLICY = (
    "positive src_stamp_ns else positive header.stamp else bag-record timestamp"
)


def positive_header_stamp_ns(message: Any) -> int | None:
    """Return a positive ROS header stamp in nanoseconds, if available."""
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None

    value = (
        int(getattr(stamp, "sec", 0)) * 1_000_000_000
        + int(getattr(stamp, "nanosec", 0))
    )
    return value if value > 0 else None


def source_image_time_ns(
    message: Any,
    record_time_ns: int,
) -> tuple[int, str]:
    """Match the timestamp authority used to create the CVAT frame manifest."""
    header_time_ns = positive_header_stamp_ns(message)
    if header_time_ns is not None:
        return header_time_ns, "header.stamp"
    return int(record_time_ns), "bag_record_timestamp"


def output_message_time_ns(
    message: Any,
    record_time_ns: int,
) -> tuple[int, str]:
    """Resolve one output message onto the source semantic timeline."""
    source_time_ns = int(getattr(message, "src_stamp_ns", 0))
    if source_time_ns > 0:
        return source_time_ns, "src_stamp_ns"

    header_time_ns = positive_header_stamp_ns(message)
    if header_time_ns is not None:
        return header_time_ns, "header.stamp"

    return int(record_time_ns), "bag_record_timestamp"


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag_path),
            storage_id="mcap",
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    return reader


def source_image_origin_ns(
    source_bag: Path,
    source_image_topic: str,
) -> tuple[int, str]:
    """Return the exact semantic origin used by the annotation preparation."""
    reader = open_reader(source_bag)
    topic_types = {
        item.name: item.type
        for item in reader.get_all_topics_and_types()
    }

    if source_image_topic not in topic_types:
        raise RuntimeError(
            f"Source bag is missing image topic {source_image_topic!r}"
        )

    message_type = get_message(topic_types[source_image_topic])

    while reader.has_next():
        topic, raw, record_time_ns = reader.read_next()
        if topic != source_image_topic:
            continue

        message = deserialize_message(raw, message_type)
        return source_image_time_ns(message, int(record_time_ns))

    raise RuntimeError(
        f"No messages found on source image topic {source_image_topic!r}"
    )


def read_output_samples_from_bag_source_time(
    bag_path: Path,
    topics: list[str],
    *,
    origin_ns: int,
) -> tuple[
    dict[str, list[pbe2.OutputSample]],
    dict[str, dict[str, int]],
]:
    """Read output streams on the physical-reference source-time axis.

    Duplicate and non-monotonic handling intentionally matches the frozen v1/v2
    bag reader: a duplicate timestamp replaces the previous sample and a
    backwards timestamp is skipped.
    """
    unique_topics = list(dict.fromkeys(topics))

    reader = open_reader(bag_path)
    topic_types = {
        item.name: item.type
        for item in reader.get_all_topics_and_types()
    }

    missing = [
        topic
        for topic in unique_topics
        if topic not in topic_types
    ]
    if missing:
        raise RuntimeError(
            f"Bag is missing required topics: {missing}"
        )

    message_types = {
        topic: get_message(topic_types[topic])
        for topic in unique_topics
    }

    samples: dict[str, list[pbe2.OutputSample]] = {
        topic: []
        for topic in unique_topics
    }

    stats: dict[str, dict[str, int]] = {
        topic: {
            "messages_seen": 0,
            "src_stamp_ns": 0,
            "header.stamp": 0,
            "bag_record_timestamp": 0,
            "non_monotonic_skipped": 0,
            "duplicate_replaced": 0,
        }
        for topic in unique_topics
    }

    while reader.has_next():
        topic, raw, record_time_ns = reader.read_next()
        if topic not in message_types:
            continue

        message = deserialize_message(
            raw,
            message_types[topic],
        )

        semantic_time_ns, timestamp_source = output_message_time_ns(
            message,
            int(record_time_ns),
        )

        topic_stats = stats[topic]
        topic_stats["messages_seen"] += 1
        topic_stats[timestamp_source] += 1

        t_s = (semantic_time_ns - origin_ns) / 1e9

        sample = pbe2.OutputSample(
            t_s=t_s,
            track_id=int(message.id),
            bbox_xyxy=msg_box_xyxy(message),
        )

        stream = samples[topic]

        if stream and t_s < stream[-1].t_s:
            topic_stats["non_monotonic_skipped"] += 1
            continue

        if stream and t_s == stream[-1].t_s:
            stream[-1] = sample
            topic_stats["duplicate_replaced"] += 1
        else:
            stream.append(sample)

    return samples, stats


def repo_relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name
    if bag_name == "metadata.yaml" and bag_path.parent:
        bag_name = bag_path.parent.name

    return (
        REPO_ROOT
        / "reports"
        / "p058_source_time_evaluator_repair"
        / bag_name
    )


def write_report(
    out_dir: Path,
    stream_name: str,
    report: dict,
) -> None:
    """Use the frozen v2 report writer, then append repair provenance."""
    write_v2_report(out_dir, stream_name, report)

    repair = report["timebase_repair"]
    md_path = out_dir / f"{stream_name}.md"

    with md_path.open("a", encoding="utf-8") as handle:
        handle.write("\n## Post-access source-time repair provenance\n\n")
        handle.write(
            f"- Repair version: `{repair['repair_version']}`\n"
        )
        handle.write(
            f"- Evaluation wrapper: `{report['evaluation_wrapper']}`\n"
        )
        handle.write(
            f"- Reference origin topic: "
            f"`{repair['source_image_topic']}`\n"
        )
        handle.write(
            f"- Reference origin ns: "
            f"`{repair['source_time_origin_ns']}`\n"
        )
        handle.write(
            f"- Reference origin clock: "
            f"`{repair['source_time_origin_clock']}`\n"
        )
        handle.write(
            f"- Reference timestamp policy: "
            f"`{repair['reference_timestamp_policy']}`\n"
        )
        handle.write(
            f"- Output timestamp policy: "
            f"`{repair['output_timestamp_policy']}`\n"
        )
        handle.write(
            f"- Source bag used for clock origin: "
            f"`{repair['source_bag_path']}`\n"
        )
        handle.write(
            f"- Output bag evaluated: "
            f"`{repair['output_bag_path']}`\n"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Post-access source-time correction for the frozen physical-v2 "
            "selected-target evaluator. Scoring semantics remain those of "
            "physical_target_bbox_evaluation_v2.py; only the output/reference "
            "clock alignment is corrected."
        )
    )

    parser.add_argument(
        "bag_path",
        type=Path,
        help="Generated output bag to evaluate.",
    )
    parser.add_argument(
        "--source-bag",
        required=True,
        type=Path,
        help=(
            "Retained source bag named by physical-reference provenance. "
            "Its first source-image semantic timestamp defines t=0."
        ),
    )
    parser.add_argument(
        "--physical-reference",
        required=True,
        type=Path,
        help="Path to a tim_physical_target_bbox_v2 JSON artifact.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--step-s",
        type=float,
        default=pbe2.DEFAULT_STEP_S,
    )
    parser.add_argument(
        "--max-output-age-s",
        type=float,
        default=pbe2.DEFAULT_MAX_OUTPUT_AGE_S,
    )
    parser.add_argument(
        "--raw-topic",
        default=TARGET_TOPIC_RAW,
    )
    parser.add_argument(
        "--tim-topic",
        default=TARGET_TOPIC_TIM,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    reference = ptr2.load_physical_reference(
        args.physical_reference
    )
    reference_sha256 = sha256_file(
        args.physical_reference
    )

    expected_source_bag = (
        REPO_ROOT
        / reference.provenance.source_bag_path
    ).resolve()
    actual_source_bag = args.source_bag.resolve()

    if actual_source_bag != expected_source_bag:
        raise SystemExit(
            "Source bag does not match physical-reference provenance:\n"
            f"  expected: {expected_source_bag}\n"
            f"  supplied: {actual_source_bag}"
        )

    if actual_source_bag.name != reference.provenance.source_bag_name:
        raise SystemExit(
            "Source bag name does not match physical-reference provenance"
        )

    origin_ns, origin_clock = source_image_origin_ns(
        actual_source_bag,
        reference.provenance.source_image_topic,
    )

    output_samples, output_read_stats = (
        read_output_samples_from_bag_source_time(
            args.bag_path,
            [args.raw_topic, args.tim_topic],
            origin_ns=origin_ns,
        )
    )

    repo_commit, repo_dirty = git_commit_and_dirty(
        REPO_ROOT
    )

    try:
        reference_rel = str(
            args.physical_reference.resolve().relative_to(
                REPO_ROOT
            )
        )
    except ValueError:
        reference_rel = str(
            args.physical_reference.resolve()
        )

    out_dir = (
        args.out_dir
        or default_report_dir(args.bag_path)
    )

    repair_provenance = {
        "repair_version": REPAIR_VERSION,
        "source_time_origin_ns": origin_ns,
        "source_time_origin_clock": origin_clock,
        "source_image_topic": (
            reference.provenance.source_image_topic
        ),
        "reference_timestamp_policy": (
            REFERENCE_TIMESTAMP_POLICY
        ),
        "output_timestamp_policy": (
            OUTPUT_TIMESTAMP_POLICY
        ),
        "source_bag_path": repo_relative_or_absolute(
            actual_source_bag
        ),
        "output_bag_path": repo_relative_or_absolute(
            args.bag_path
        ),
        "output_read_stats": output_read_stats,
    }

    for stream_name, topic in (
        ("raw_target", args.raw_topic),
        ("tim_target_memory", args.tim_topic),
    ):
        result = pbe2.evaluate_physical_target_bbox_v2(
            reference=reference,
            output_samples=output_samples[topic],
            step_s=args.step_s,
            max_output_age_s=args.max_output_age_s,
        )

        report = pbe2.build_report(
            result=result,
            stream_name=stream_name,
            provenance=reference.provenance,
            physical_reference_path=reference_rel,
            physical_reference_sha256=reference_sha256,
            repo_commit=repo_commit,
            repo_dirty=repo_dirty,
        )

        report["evaluation_wrapper"] = Path(
            __file__
        ).name
        report["timebase_repair"] = repair_provenance

        write_report(
            out_dir,
            stream_name,
            report,
        )

        if not result.reconciliation_ok:
            print(
                f"[error] {stream_name}: duration "
                f"reconciliation failed "
                f"(residual="
                f"{result.reconciliation_residual_s}s)",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
