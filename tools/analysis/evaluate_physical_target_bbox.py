#!/usr/bin/env python3
"""Issue #25 identity-independent selected-target bbox evaluator.

THIS IS NOT THE LEGACY EVALUATOR. It scores controller-facing output
against a ``tim_physical_target_bbox_v1`` physical-reference artifact
(``tools/analysis/physical_target_reference.py``), never against
``correct_target_track_id``/``/tracks`` lookups. Tracker IDs cannot
change this evaluator's result -- see the regenerated-tracker-ID
invariance test in ``tools/tests/test_physical_target_bbox_evaluation.py``.

For the historical, tracker-ID-dependent evaluator (valid only when
tracker IDs in this run match the annotation stream), use
``tools/analysis/evaluate_tim_target_bbox_correctness.py`` instead --
that script is not suitable for regenerated-tracker-ID evidence and is
not changed by this one.

All scoring logic (Stage A identity attribution, Stage B localisation,
duration-bucket accounting, aggregation) lives in
``physical_target_bbox_evaluation.py``; this file only reads the bag,
gathers provenance, and writes the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_reference as ptr  # noqa: E402
import physical_target_bbox_evaluation as pbe  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_TOPIC_RAW = "/target"
TARGET_TOPIC_TIM = "/target_memory_mars"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit_and_dirty(repo_root: Path) -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None

    if commit.returncode != 0:
        return None, None

    commit_sha = commit.stdout.strip() or None
    dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    return commit_sha, dirty


def msg_box_xyxy(msg: Any) -> pbe.BBoxXYXY | None:
    """Convert a TargetState-style cx,cy,w,h message to xyxy, or None if the
    message does not represent a valid selection (zero ID or invalid bbox)."""

    if int(msg.id) == 0:
        return None
    cx, cy, w, h = float(msg.cx), float(msg.cy), float(msg.w), float(msg.h)
    if not all(v == v for v in (cx, cy, w, h)):  # NaN check
        return None
    if w <= 0.0 or h <= 0.0:
        return None
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)


def read_output_samples_from_bag(
    bag_path: Path, topics: list[str]
) -> dict[str, list[pbe.OutputSample]]:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr", output_serialization_format="cdr"
        ),
    )

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    missing = [topic for topic in topics if topic not in topic_types]
    if missing:
        raise RuntimeError(f"Bag is missing required topics: {missing}")

    msg_types = {topic: get_message(topic_types[topic]) for topic in topics}
    samples: dict[str, list[pbe.OutputSample]] = {topic: [] for topic in topics}
    first_t: int | None = None

    while reader.has_next():
        topic, data, t = reader.read_next()
        if first_t is None:
            first_t = t
        if topic not in msg_types:
            continue

        t_s = (t - first_t) / 1e9
        msg = deserialize_message(data, msg_types[topic])
        sample = pbe.OutputSample(
            t_s=t_s, track_id=int(msg.id), bbox_xyxy=msg_box_xyxy(msg)
        )

        stream = samples[topic]
        if stream and t_s < stream[-1].t_s:
            continue  # non-monotonic; keep the earlier reading
        if stream and t_s == stream[-1].t_s:
            stream[-1] = sample
        else:
            stream.append(sample)

    return samples


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name
    if bag_name == "metadata.yaml" and bag_path.parent:
        bag_name = bag_path.parent.name
    return REPO_ROOT / "reports" / "p025_physical_target_bbox" / bag_name


def write_report(out_dir: Path, stream_name: str, report: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stream_name}.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    buckets = report["duration_buckets"]
    loc = report["localisation"]
    md_lines = [
        f"# Physical-reference bbox evaluation -- {stream_name}",
        "",
        f"- Evaluator mode: `{report['evaluator_mode']}` "
        "(identity-independent; not the legacy tracker-ID evaluator)",
        f"- Physical reference: `{report['physical_reference_path']}` "
        f"(sha256 `{report['physical_reference_sha256'][:12]}...`)",
        f"- Source bag: `{report['source_bag_name']}`",
        f"- Coordinate convention: `{report['coordinate_convention']}`",
        f"- Repository commit: `{report['repo_commit']}` "
        f"(dirty={report['repo_dirty']})",
        "",
        "## Duration buckets (primary, mutually exclusive)",
        "",
        "| Bucket | Duration (s) |",
        "|---|---:|",
    ]
    for key in (
        "correct_target_output_duration_s",
        "wrong_person_output_duration_s",
        "identity_unresolved_duration_s",
        "lost_or_suppressed_duration_s",
        "target_absent_duration_s",
        "reference_unavailable_duration_s",
    ):
        md_lines.append(f"| `{key}` | {buckets[key]:.3f} |")

    md_lines.extend(
        [
            "",
            "## Conditional/subset metrics",
            "",
            f"- `localisation_scored_duration_s`: {buckets['localisation_scored_duration_s']:.3f} "
            "(subset of correct_target_output_duration_s)",
            f"- `target_absent_with_output_duration_s`: "
            f"{buckets['target_absent_with_output_duration_s']:.3f} "
            "(subset of target_absent_duration_s -- safety-relevant)",
            "",
            "## Stage B localisation (target-attributed samples only, no quality gate)",
            "",
            f"- n samples: {loc['n_samples']}",
            f"- IoU duration-weighted mean: {loc['iou_duration_weighted_mean']}",
            f"- IoU min/median/max: {loc['iou_min']} / {loc['iou_median']} / {loc['iou_max']}",
            f"- Centre error (px) duration-weighted mean: "
            f"{loc['centre_error_px_duration_weighted_mean']}",
            f"- Centre error (ref-height-normalised) duration-weighted mean: "
            f"{loc['centre_error_ref_h_duration_weighted_mean']}",
            "",
            "## Reconciliation",
            "",
            f"- ok: {report['reconciliation']['ok']}",
            f"- primary bucket total (s): {report['reconciliation']['primary_bucket_total_s']:.6f}",
            f"- total evaluated duration (s): {report['total_evaluated_duration_s']:.6f}",
        ]
    )
    (out_dir / f"{stream_name}.md").write_text("\n".join(md_lines) + "\n")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {out_dir / f'{stream_name}.md'}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Issue #25 identity-independent bbox evaluator. Scores "
            "controller-facing output against a tim_physical_target_bbox_v1 "
            "physical-reference artifact -- NOT against correct_target_track_id "
            "/tracks lookups. For the legacy tracker-ID-dependent evaluator, use "
            "evaluate_tim_target_bbox_correctness.py instead; it is not changed "
            "by this tool and is not suitable for regenerated-tracker-ID evidence."
        )
    )
    parser.add_argument("bag_path", type=Path)
    parser.add_argument(
        "--physical-reference",
        required=True,
        type=Path,
        help="Path to a tim_physical_target_bbox_v1 JSON artifact.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--step-s", type=float, default=pbe.DEFAULT_STEP_S)
    parser.add_argument(
        "--max-output-age-s", type=float, default=pbe.DEFAULT_MAX_OUTPUT_AGE_S
    )
    parser.add_argument("--raw-topic", default=TARGET_TOPIC_RAW)
    parser.add_argument("--tim-topic", default=TARGET_TOPIC_TIM)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    reference = ptr.load_physical_reference(args.physical_reference)
    reference_sha256 = sha256_file(args.physical_reference)
    repo_commit, repo_dirty = git_commit_and_dirty(REPO_ROOT)

    try:
        reference_rel = str(args.physical_reference.resolve().relative_to(REPO_ROOT))
    except ValueError:
        reference_rel = str(args.physical_reference)

    output_samples = read_output_samples_from_bag(
        args.bag_path, [args.raw_topic, args.tim_topic]
    )

    out_dir = args.out_dir or default_report_dir(args.bag_path)

    for stream_name, topic in (
        ("raw_target", args.raw_topic),
        ("tim_target_memory", args.tim_topic),
    ):
        result = pbe.evaluate_physical_target_bbox(
            reference=reference,
            output_samples=output_samples[topic],
            step_s=args.step_s,
            max_output_age_s=args.max_output_age_s,
        )
        report = pbe.build_report(
            result=result,
            stream_name=stream_name,
            provenance=reference.provenance,
            physical_reference_path=reference_rel,
            physical_reference_sha256=reference_sha256,
            repo_commit=repo_commit,
            repo_dirty=repo_dirty,
        )
        write_report(out_dir, stream_name, report)

        if not result.reconciliation_ok:
            print(
                f"[error] {stream_name}: duration reconciliation failed "
                f"(residual={result.reconciliation_residual_s}s)",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
