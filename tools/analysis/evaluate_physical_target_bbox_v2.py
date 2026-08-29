#!/usr/bin/env python3
"""Issue #25 identity-independent selected-target bbox evaluator -- v2.

THIS IS THE ``tim_physical_target_bbox_v2`` EVALUATOR, distinct from both:

- ``evaluate_tim_target_bbox_correctness.py`` -- the legacy,
  tracker-ID-dependent evaluator, unrelated to either physical-reference
  contract and not changed by this file;
- ``evaluate_physical_target_bbox.py`` -- the v1
  (``tim_physical_target_bbox_v1``) evaluator. v1 remains valid on its
  own terms for v1 artifacts and is not modified or replaced by this
  file. v1's evaluator silently step-holds stale keyframe geometry across
  gaps between sparse ``distractors_complete`` samples; this v2 evaluator
  exists specifically because that behaviour is not scientifically valid
  once ``distractors_complete`` is the dominant regime across a sequence
  (see ``docs/issues/p1-10-physical-reference-v2-contract.md``). A v1
  artifact cannot be evaluated by this tool, and a v2 artifact cannot be
  evaluated by ``evaluate_physical_target_bbox.py`` -- both fail fast via
  their respective schema-version checks, never silently.

All v2 scoring logic (interval-aware reference resolution, Stage A
identity attribution, Stage B localisation, the seven-bucket duration
account, coverage metrics) lives in
``physical_target_bbox_evaluation_v2.py``; this file only reads the bag,
gathers provenance, and writes the report -- mirroring
``evaluate_physical_target_bbox.py``'s own split exactly.

Bag-reading helpers (``sha256_file``, ``git_commit_and_dirty``,
``read_output_samples_from_bag``) are schema-version-independent -- they
read ``/target``/``/target_memory_mars`` messages into the same
``OutputSample`` shape regardless of which physical-reference contract
will score them -- and are imported directly from
``evaluate_physical_target_bbox.py`` (v1's CLI) rather than duplicated.
That file is not modified by this one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import physical_target_bbox_evaluation_v2 as pbe2  # noqa: E402
import physical_target_reference_v2 as ptr2  # noqa: E402
from evaluate_physical_target_bbox import (  # noqa: E402
    git_commit_and_dirty,
    read_output_samples_from_bag,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

TARGET_TOPIC_RAW = "/target"
TARGET_TOPIC_TIM = "/target_memory_mars"


def default_report_dir(bag_path: Path) -> Path:
    bag_name = bag_path.name
    if bag_name == "metadata.yaml" and bag_path.parent:
        bag_name = bag_path.parent.name
    return REPO_ROOT / "reports" / "p025_physical_target_bbox_v2" / bag_name


def write_report(out_dir: Path, stream_name: str, report: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stream_name}.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    buckets = report["duration_buckets"]
    coverage = report["coverage"]
    loc = report["localisation"]
    window = report["evaluation_window"]
    md_lines = [
        f"# Physical-reference bbox evaluation (v2) -- {stream_name}",
        "",
        f"- Evaluator mode: `{report['evaluator_mode']}` "
        "(identity-independent, interval-aware -- no stale-geometry step-hold)",
        f"- Physical reference: `{report['physical_reference_path']}` "
        f"(sha256 `{report['physical_reference_sha256'][:12]}...`)",
        f"- Source bag: `{report['source_bag_name']}`",
        f"- Coordinate convention: `{report['coordinate_convention']}`",
        f"- Evaluation window: [{window['start_s']}, {window['end_s']})",
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
        "reference_gap_duration_s",
    ):
        md_lines.append(f"| `{key}` | {buckets[key]:.3f} |")

    md_lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- `reference_covered_duration_s`: "
            f"{coverage['reference_covered_duration_s']:.3f}",
            f"- `reference_gap_duration_s`: {coverage['reference_gap_duration_s']:.3f}",
            f"- `reference_coverage_fraction`: {coverage['reference_coverage_fraction']}",
            f"- `interpolated_reference_duration_s`: "
            f"{coverage['interpolated_reference_duration_s']:.3f}",
            "",
            "## Conditional/subset metrics",
            "",
            f"- `localisation_scored_duration_s`: "
            f"{buckets['localisation_scored_duration_s']:.3f} "
            "(subset of correct_target_output_duration_s)",
            f"- `target_absent_with_output_duration_s`: "
            f"{buckets['target_absent_with_output_duration_s']:.3f} "
            "(subset of target_absent_duration_s -- safety-relevant)",
            f"- `reference_gap_with_output_duration_s`: "
            f"{buckets['reference_gap_with_output_duration_s']:.3f} "
            "(subset of reference_gap_duration_s -- diagnostic only)",
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
            "Issue #25 identity-independent bbox evaluator -- v2 "
            "(tim_physical_target_bbox_v2). Interval-aware: eliminates v1's "
            "stale-geometry step-hold between sparse distractors_complete "
            "keyframes -- uncovered intervals are honestly reported as "
            "reference_gap_duration_s, never silently scored. For v1 "
            "(tim_physical_target_bbox_v1) artifacts, use "
            "evaluate_physical_target_bbox.py instead; it is not changed "
            "by this tool. For the legacy tracker-ID-dependent evaluator, "
            "use evaluate_tim_target_bbox_correctness.py."
        )
    )
    parser.add_argument("bag_path", type=Path)
    parser.add_argument(
        "--physical-reference",
        required=True,
        type=Path,
        help="Path to a tim_physical_target_bbox_v2 JSON artifact.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--step-s", type=float, default=pbe2.DEFAULT_STEP_S)
    parser.add_argument(
        "--max-output-age-s", type=float, default=pbe2.DEFAULT_MAX_OUTPUT_AGE_S
    )
    parser.add_argument("--raw-topic", default=TARGET_TOPIC_RAW)
    parser.add_argument("--tim-topic", default=TARGET_TOPIC_TIM)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    reference = ptr2.load_physical_reference(args.physical_reference)
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
