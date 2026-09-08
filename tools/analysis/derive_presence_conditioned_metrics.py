#!/usr/bin/env python3
"""Presence-conditioned identity reporting -- pure downstream of the frozen
``tim_physical_target_bbox_v2`` evaluator.

This module implements the presence-conditioned identity-performance formulas
that were **already predeclared** in the Issue #27 Stage-7 prospective freeze
(the ``primary_metric_contract`` of
``docs/results/selected_target_tracking/``
``tim_mars_prospective_freeze_20260908.json``). It adds no scientific
methodology: it only performs arithmetic on the duration buckets the frozen
evaluator already produced.

It deliberately does NOT:

- import, re-run, or duplicate Stage-A identity classification;
- open bags or recompute any identity attribution;
- modify the original evaluator report;
- introduce any pass/fail threshold, tuning, or reinterpretation.

The frozen present-time denominator (never widened with reference-unavailable
or reference-gap time) is:

    physical_target_present_duration_s
        = correct_target_output_duration_s
        + wrong_person_output_duration_s
        + identity_unresolved_duration_s
        + lost_or_suppressed_duration_s

Key result field ``correct_while_present_pct``:

    100 * correct_target_output_duration_s / physical_target_present_duration_s

Companion evaluator files -- unchanged and not imported here:
``tools/analysis/physical_target_bbox_evaluation_v2.py``,
``tools/analysis/physical_target_reference_v2.py``,
``tools/analysis/evaluate_physical_target_bbox_v2.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# DERIVED reporting schema identifier. This is NOT a physical-v2 evaluator
# contract version; it names the arithmetic reporting layer only.
DERIVED_REPORTING_SCHEMA = "tim_presence_conditioned_metrics_v1"

# The frozen physical-v2 evaluator reconciles primary buckets to the total
# evaluated duration with ``residual <= 1e-6`` (physical_target_bbox_evaluation
# _v2.py). The derived layer inherits exactly that absolute tolerance and never
# tightens or loosens it.
ABS_TOLERANCE_S = 1e-6
PCT_ABS_TOLERANCE = 1e-6

EXPECTED_CONTRACT_VERSION = "tim_physical_target_bbox_v2"
EXPECTED_EVALUATOR = "physical_target_bbox_evaluation_v2"

# Buckets consumed from ``report["duration_buckets"]``.
_PRESENT_BUCKETS = (
    "correct_target_output_duration_s",
    "wrong_person_output_duration_s",
    "identity_unresolved_duration_s",
    "lost_or_suppressed_duration_s",
)
_OTHER_REQUIRED_BUCKETS = (
    "target_absent_duration_s",
    "target_absent_with_output_duration_s",
    "reference_unavailable_duration_s",
    "reference_gap_duration_s",
)
_REQUIRED_BUCKETS = _PRESENT_BUCKETS + _OTHER_REQUIRED_BUCKETS


class PresenceConditionedError(ValueError):
    """Raised when the input report cannot be safely transformed."""


def _pct(numerator: float, denominator: float) -> float | None:
    """Percentage, or ``None`` when the denominator is not positive.

    ``None`` (JSON ``null``) is deliberate: a missing denominator must never be
    silently reported as ``0``.
    """
    if denominator <= 0.0:
        return None
    return 100.0 * numerator / denominator


def _require_mapping(report: object) -> dict:
    if not isinstance(report, dict):
        raise PresenceConditionedError(
            "input is not a JSON object / physical-v2 evaluator report"
        )
    return report


def _validate_is_physical_v2_report(report: dict) -> None:
    contract_version = report.get("contract_version")
    schema_version = report.get("schema_version")
    evaluator = report.get("evaluator")

    if contract_version != EXPECTED_CONTRACT_VERSION:
        raise PresenceConditionedError(
            "not a tim_physical_target_bbox_v2 report: contract_version="
            f"{contract_version!r} (expected {EXPECTED_CONTRACT_VERSION!r})"
        )
    if schema_version != 2:
        raise PresenceConditionedError(
            f"unexpected schema_version={schema_version!r} (expected 2)"
        )
    if evaluator is not None and evaluator != EXPECTED_EVALUATOR:
        raise PresenceConditionedError(
            f"unexpected evaluator={evaluator!r} "
            f"(expected {EXPECTED_EVALUATOR!r})"
        )
    if not isinstance(report.get("duration_buckets"), dict):
        raise PresenceConditionedError(
            "report has no 'duration_buckets' object"
        )
    if "total_evaluated_duration_s" not in report:
        raise PresenceConditionedError(
            "report has no 'total_evaluated_duration_s'"
        )


def _extract_buckets(report: dict) -> dict:
    raw = report["duration_buckets"]
    missing = [key for key in _REQUIRED_BUCKETS if key not in raw]
    if missing:
        raise PresenceConditionedError(
            "report duration_buckets missing required key(s): "
            + ", ".join(sorted(missing))
        )
    values: dict[str, float] = {}
    for key in _REQUIRED_BUCKETS:
        value = raw[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PresenceConditionedError(
                f"duration bucket {key!r} is not numeric: {value!r}"
            )
        values[key] = float(value)
    return values


def _validate_bucket_sanity(
    buckets: dict, total_evaluated_s: float, tolerance_s: float
) -> None:
    for key, value in buckets.items():
        if value < -tolerance_s:
            raise PresenceConditionedError(
                f"negative duration bucket {key!r}: {value!r}"
            )
    if not isinstance(total_evaluated_s, (int, float)) or isinstance(
        total_evaluated_s, bool
    ):
        raise PresenceConditionedError(
            f"total_evaluated_duration_s is not numeric: {total_evaluated_s!r}"
        )
    if total_evaluated_s < -tolerance_s:
        raise PresenceConditionedError(
            f"negative total_evaluated_duration_s: {total_evaluated_s!r}"
        )

    absent_s = buckets["target_absent_duration_s"]
    leakage_s = buckets["target_absent_with_output_duration_s"]
    if leakage_s > absent_s + tolerance_s:
        raise PresenceConditionedError(
            "target_absent_with_output_duration_s "
            f"({leakage_s}) exceeds target_absent_duration_s ({absent_s})"
        )


def _validate_reconciliation(
    report: dict,
    buckets: dict,
    present_s: float,
    total_evaluated_s: float,
    tolerance_s: float,
) -> dict:
    """Independent duration-partition check plus the source evaluator's own
    reconciliation verdict. Source values are never adjusted to force a match.
    """
    absent_s = buckets["target_absent_duration_s"]
    unavailable_s = buckets["reference_unavailable_duration_s"]
    gap_s = buckets["reference_gap_duration_s"]

    partition_sum_s = present_s + absent_s + unavailable_s + gap_s
    partition_residual_s = abs(partition_sum_s - total_evaluated_s)
    partition_ok = partition_residual_s <= tolerance_s

    source_recon = report.get("reconciliation")
    source_recon_ok: bool | None = None
    source_recon_residual_s: float | None = None
    if isinstance(source_recon, dict):
        if isinstance(source_recon.get("ok"), bool):
            source_recon_ok = source_recon["ok"]
        residual = source_recon.get("residual_s")
        if isinstance(residual, (int, float)) and not isinstance(
            residual, bool
        ):
            source_recon_residual_s = float(residual)

    if source_recon_ok is False:
        raise PresenceConditionedError(
            "source evaluator reconciliation failed "
            f"(residual_s={source_recon_residual_s})"
        )
    if not partition_ok:
        raise PresenceConditionedError(
            "duration partition does not reconcile to "
            "total_evaluated_duration_s: "
            f"present({present_s}) + absent({absent_s}) + "
            f"reference_unavailable({unavailable_s}) + "
            f"reference_gap({gap_s}) = {partition_sum_s}, "
            f"total={total_evaluated_s}, residual={partition_residual_s} "
            f"> tol {tolerance_s}"
        )

    # Cross-check the derived present denominator against the evaluator's own
    # reference-covered duration when it is available.
    coverage = report.get("coverage")
    covered_residual_s: float | None = None
    if isinstance(coverage, dict):
        covered = coverage.get("reference_covered_duration_s")
        if isinstance(covered, (int, float)) and not isinstance(covered, bool):
            covered_residual_s = abs(float(covered) - present_s)
            if covered_residual_s > tolerance_s:
                raise PresenceConditionedError(
                    "derived physical_target_present_duration_s "
                    f"({present_s}) is inconsistent with the evaluator's "
                    f"coverage.reference_covered_duration_s ({covered}); "
                    f"residual {covered_residual_s} > tol {tolerance_s}"
                )

    return {
        "absolute_tolerance_s": tolerance_s,
        "duration_partition_sum_s": partition_sum_s,
        "duration_partition_total_s": total_evaluated_s,
        "duration_partition_residual_s": partition_residual_s,
        "duration_partition_ok": partition_ok,
        "present_denominator_vs_reference_covered_residual_s": (
            covered_residual_s
        ),
        "source_evaluator_reconciliation_ok": source_recon_ok,
        "source_evaluator_reconciliation_residual_s": source_recon_residual_s,
    }


def _source_report_provenance(report: dict) -> dict:
    keys = (
        "contract_version",
        "schema_version",
        "evaluator",
        "evaluator_mode",
        "stream",
        "source_bag_name",
        "source_bag_path",
        "physical_reference_path",
        "physical_reference_sha256",
        "repo_commit",
        "repo_dirty",
        "total_evaluated_duration_s",
    )
    provenance = {key: report.get(key) for key in keys}
    window = report.get("evaluation_window")
    if isinstance(window, dict):
        provenance["evaluation_window"] = {
            "start_s": window.get("start_s"),
            "end_s": window.get("end_s"),
        }
    return provenance


def derive_presence_conditioned_metrics(
    report: object,
    *,
    label: str | None = None,
    tolerance_s: float = ABS_TOLERANCE_S,
) -> dict:
    """Transform one frozen physical-v2 evaluator report into the derived
    presence-conditioned reporting structure. Pure arithmetic; deterministic.
    """
    report = _require_mapping(report)
    _validate_is_physical_v2_report(report)
    buckets = _extract_buckets(report)
    total_evaluated_s = float(report["total_evaluated_duration_s"])
    _validate_bucket_sanity(buckets, total_evaluated_s, tolerance_s)

    correct_s = buckets["correct_target_output_duration_s"]
    wrong_s = buckets["wrong_person_output_duration_s"]
    unresolved_s = buckets["identity_unresolved_duration_s"]
    lost_s = buckets["lost_or_suppressed_duration_s"]
    absent_s = buckets["target_absent_duration_s"]
    leakage_s = buckets["target_absent_with_output_duration_s"]
    unavailable_s = buckets["reference_unavailable_duration_s"]
    gap_s = buckets["reference_gap_duration_s"]

    present_s = correct_s + wrong_s + unresolved_s + lost_s

    reconciliation = _validate_reconciliation(
        report, buckets, present_s, total_evaluated_s, tolerance_s
    )

    correct_pct = _pct(correct_s, present_s)
    wrong_pct = _pct(wrong_s, present_s)
    unresolved_pct = _pct(unresolved_s, present_s)
    lost_pct = _pct(lost_s, present_s)

    present_pct_components_sum: float | None
    present_pct_components_sum_ok: bool | None
    if None in (correct_pct, wrong_pct, unresolved_pct, lost_pct):
        present_pct_components_sum = None
        present_pct_components_sum_ok = None
    else:
        present_pct_components_sum = (
            correct_pct + wrong_pct + unresolved_pct + lost_pct
        )
        present_pct_components_sum_ok = (
            abs(present_pct_components_sum - 100.0) <= PCT_ABS_TOLERANCE
        )
    reconciliation["present_pct_components_sum"] = present_pct_components_sum
    reconciliation["present_pct_components_sum_ok"] = (
        present_pct_components_sum_ok
    )

    safe_clear_s = absent_s - leakage_s

    # Exact Stage-7 percent_time_target_present: the denominator is the
    # physically-classified present+absent time ONLY. reference_unavailable and
    # reference_gap are separate physical-v2 conditions and never enter it.
    present_plus_absent_s = present_s + absent_s

    derived = {
        "derived_reporting_schema": DERIVED_REPORTING_SCHEMA,
        "derived_reporting_schema_note": (
            "DERIVED reporting layer. Pure arithmetic transformation of "
            "the frozen tim_physical_target_bbox_v2 duration buckets, "
            "implementing the presence-conditioned formulas predeclared in "
            "the Issue #27 Stage-7 prospective freeze primary_metric_contract "
            "(docs/results/selected_target_tracking/"
            "tim_mars_prospective_freeze_20260908.json). This is NOT a "
            "physical-v2 evaluator contract and does not modify, supersede or "
            "reinterpret it. No pass/fail threshold is introduced."
        ),
        "label": label,
        "source_report": _source_report_provenance(report),
        "frozen_bucket_inputs_s": {
            key: buckets[key] for key in _REQUIRED_BUCKETS
        },
        "target_presence_accounting": {
            "physical_target_present_duration_s": present_s,
            "physical_target_present_definition": (
                "correct_target_output_duration_s "
                "+ wrong_person_output_duration_s "
                "+ identity_unresolved_duration_s "
                "+ lost_or_suppressed_duration_s"
            ),
            "physical_target_absent_duration_s": absent_s,
            "present_plus_absent_duration_s": present_plus_absent_s,
            "reference_unavailable_duration_s": unavailable_s,
            "reference_gap_duration_s": gap_s,
            "total_evaluated_duration_s": total_evaluated_s,
            # Exact Stage-7 percent_time_target_present: denominator is
            # present + absent ONLY (reference_unavailable and reference_gap
            # are deliberately excluded).
            "percent_time_target_present": _pct(
                present_s, present_plus_absent_s
            ),
            "percent_time_target_absent": _pct(
                absent_s, present_plus_absent_s
            ),
            "percent_time_target_present_denominator": (
                "physical_target_present_duration_s "
                "+ physical_target_absent_duration_s"
            ),
            # Secondary descriptive accounting: denominator is the complete
            # evaluated window; the field names state the denominator, and
            # neither maps to Stage-7 percent_time_target_present.
            "physical_target_present_pct_of_total": _pct(
                present_s, total_evaluated_s
            ),
            "physical_target_absent_pct_of_total": _pct(
                absent_s, total_evaluated_s
            ),
            "reference_unavailable_pct_of_total": _pct(
                unavailable_s, total_evaluated_s
            ),
            "reference_gap_pct_of_total": _pct(gap_s, total_evaluated_s),
        },
        "while_target_present": {
            "denominator_s": present_s,
            "correct_while_present_duration_s": correct_s,
            "correct_while_present_pct": correct_pct,
            "wrong_while_present_duration_s": wrong_s,
            "wrong_while_present_pct": wrong_pct,
            "identity_unresolved_while_present_duration_s": unresolved_s,
            "identity_unresolved_while_present_pct": unresolved_pct,
            "lost_or_suppressed_while_present_duration_s": lost_s,
            "lost_or_suppressed_while_present_pct": lost_pct,
        },
        "while_target_absent": {
            "denominator_s": absent_s,
            "absence_leakage_duration_s": leakage_s,
            "absence_leakage_pct": _pct(leakage_s, absent_s),
            "safe_clear_while_absent_duration_s": safe_clear_s,
            "safe_clear_while_absent_pct": _pct(safe_clear_s, absent_s),
        },
        "reconciliation": reconciliation,
        "stage7_primary_metric_contract_mapping": {
            "physical_target_present_duration_s": (
                "target_presence_accounting.physical_target_present_duration_s"
            ),
            "percent_time_target_present": (
                "target_presence_accounting.percent_time_target_present "
                "= 100 * physical_target_present_duration_s / "
                "(physical_target_present_duration_s "
                "+ physical_target_absent_duration_s); "
                "reference_unavailable_duration_s and "
                "reference_gap_duration_s are excluded from the denominator. "
                "The separately named "
                "physical_target_present_pct_of_total (denominator "
                "total_evaluated_duration_s) is a secondary descriptive "
                "quantity and is NOT this Stage-7 metric."
            ),
            "percent_time_target_absent": (
                "target_presence_accounting.percent_time_target_absent "
                "= 100 * physical_target_absent_duration_s / "
                "(physical_target_present_duration_s "
                "+ physical_target_absent_duration_s)"
            ),
            "correct_target_authority_pct": (
                "while_target_present.correct_while_present_pct"
            ),
            "wrong_person_authority_pct": (
                "while_target_present.wrong_while_present_pct"
            ),
            "lost_or_suppressed_pct": (
                "while_target_present.lost_or_suppressed_while_present_pct"
            ),
            "leakage_pct_of_absent_time": (
                "while_target_absent.absence_leakage_pct (null when "
                "target_absent_duration_s == 0)"
            ),
            "safe_clear_duration_s": (
                "while_target_absent.safe_clear_while_absent_duration_s"
            ),
        },
    }
    return derived


def _fmt_s(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.6f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f}%"


def _label_of(derived: dict) -> str:
    return (
        derived.get("label")
        or derived["source_report"].get("stream")
        or "?"
    )


def _row(name: str, seconds: float | None, pct: float | None) -> str:
    return f"| {name} | {_fmt_s(seconds)} | {_fmt_pct(pct)} |"


def render_markdown(derived: dict) -> str:
    tpa = derived["target_presence_accounting"]
    wtp = derived["while_target_present"]
    wta = derived["while_target_absent"]
    recon = derived["reconciliation"]
    src = derived["source_report"]
    ref_sha = str(src.get("physical_reference_sha256"))[:12]

    lines = [
        f"# Presence-conditioned identity metrics -- {_label_of(derived)}",
        "",
        "Derived reporting layer "
        f"(`{derived['derived_reporting_schema']}`). Pure arithmetic on "
        "the frozen `tim_physical_target_bbox_v2` duration buckets; "
        "implements the Stage-7 prospective-freeze "
        "`primary_metric_contract`. No evaluator change, no tuning, no "
        "pass/fail threshold.",
        "",
        f"- Source stream: `{src.get('stream')}`",
        f"- Physical reference: `{src.get('physical_reference_path')}` "
        f"(sha256 `{ref_sha}...`)",
        f"- Source replay commit: `{src.get('repo_commit')}` "
        f"(dirty={src.get('repo_dirty')})",
        "",
        "## Target-presence accounting (exact Stage-7)",
        "",
        "`percent_time_target_present` / `percent_time_target_absent` use the "
        "physically-classified present+absent time as denominator "
        f"({_fmt_s(tpa['present_plus_absent_duration_s'])} s). "
        "`reference_unavailable` and `reference_gap` are separate physical-v2 "
        "conditions and are **never** in this denominator.",
        "",
        "| Quantity | Duration (s) | % of present+absent time |",
        "|---|---:|---:|",
        _row(
            "target present",
            tpa["physical_target_present_duration_s"],
            tpa["percent_time_target_present"],
        ),
        _row(
            "target absent",
            tpa["physical_target_absent_duration_s"],
            tpa["percent_time_target_absent"],
        ),
        "",
        "## Secondary accounting -- % of complete evaluated window",
        "",
        "Denominator is `total_evaluated_duration_s` "
        f"({_fmt_s(tpa['total_evaluated_duration_s'])} s). These are "
        "descriptive only; neither is the Stage-7 "
        "`percent_time_target_present`.",
        "",
        "| Quantity | Duration (s) | % of complete evaluated window |",
        "|---|---:|---:|",
        _row(
            "target present",
            tpa["physical_target_present_duration_s"],
            tpa["physical_target_present_pct_of_total"],
        ),
        _row(
            "target absent",
            tpa["physical_target_absent_duration_s"],
            tpa["physical_target_absent_pct_of_total"],
        ),
        _row(
            "reference_unavailable",
            tpa["reference_unavailable_duration_s"],
            tpa["reference_unavailable_pct_of_total"],
        ),
        _row(
            "reference_gap",
            tpa["reference_gap_duration_s"],
            tpa["reference_gap_pct_of_total"],
        ),
        f"| total_evaluated | {_fmt_s(tpa['total_evaluated_duration_s'])} "
        "| 100% |",
        "",
        "## While physical target present "
        f"(denominator = {_fmt_s(wtp['denominator_s'])} s)",
        "",
        "| Outcome | Duration (s) | % while present |",
        "|---|---:|---:|",
        _row(
            "correct",
            wtp["correct_while_present_duration_s"],
            wtp["correct_while_present_pct"],
        ),
        _row(
            "wrong person",
            wtp["wrong_while_present_duration_s"],
            wtp["wrong_while_present_pct"],
        ),
        _row(
            "identity unresolved",
            wtp["identity_unresolved_while_present_duration_s"],
            wtp["identity_unresolved_while_present_pct"],
        ),
        _row(
            "lost / suppressed",
            wtp["lost_or_suppressed_while_present_duration_s"],
            wtp["lost_or_suppressed_while_present_pct"],
        ),
        "",
        "## While physical target absent "
        f"(denominator = {_fmt_s(wta['denominator_s'])} s)",
        "",
        f"- absence leakage: "
        f"{_fmt_s(wta['absence_leakage_duration_s'])} s "
        f"({_fmt_pct(wta['absence_leakage_pct'])})",
        f"- safe clear: "
        f"{_fmt_s(wta['safe_clear_while_absent_duration_s'])} s "
        f"({_fmt_pct(wta['safe_clear_while_absent_pct'])})",
        "",
        "## Reconciliation",
        "",
        f"- present-% components sum: "
        f"{_fmt_pct(recon['present_pct_components_sum'])} "
        f"(ok={recon['present_pct_components_sum_ok']})",
        f"- duration partition residual: "
        f"{recon['duration_partition_residual_s']:.2e} s "
        f"(ok={recon['duration_partition_ok']}, "
        f"tol={recon['absolute_tolerance_s']:.0e} s)",
        f"- source evaluator reconciliation ok: "
        f"{recon['source_evaluator_reconciliation_ok']}",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_human(derived: dict) -> str:
    wtp = derived["while_target_present"]
    wta = derived["while_target_absent"]
    tpa = derived["target_presence_accounting"]
    present_s = _fmt_s(tpa["physical_target_present_duration_s"])
    absent_s = _fmt_s(tpa["physical_target_absent_duration_s"])
    total_s = _fmt_s(tpa["total_evaluated_duration_s"])
    rows = [
        f"[{_label_of(derived)}] present={present_s}s absent={absent_s}s "
        f"total={total_s}s",
        f"  percent_time_target_present (Stage-7, /present+absent) = "
        f"{_fmt_pct(tpa['percent_time_target_present'])}",
        f"  physical_target_present_pct_of_total (/complete window) = "
        f"{_fmt_pct(tpa['physical_target_present_pct_of_total'])}",
        f"  correct_while_present_pct             = "
        f"{_fmt_pct(wtp['correct_while_present_pct'])}",
        f"  wrong_while_present_pct               = "
        f"{_fmt_pct(wtp['wrong_while_present_pct'])}",
        f"  identity_unresolved_while_present_pct = "
        f"{_fmt_pct(wtp['identity_unresolved_while_present_pct'])}",
        f"  lost_or_suppressed_while_present_pct  = "
        f"{_fmt_pct(wtp['lost_or_suppressed_while_present_pct'])}",
        f"  absence_leakage_pct                  = "
        f"{_fmt_pct(wta['absence_leakage_pct'])}",
        f"  safe_clear_while_absent_pct           = "
        f"{_fmt_pct(wta['safe_clear_while_absent_pct'])}",
    ]
    return "\n".join(rows) + "\n"


def _load_report(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PresenceConditionedError(
            f"input report not found: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise PresenceConditionedError(
            f"input report is not valid JSON: {path} ({exc})"
        ) from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Derive presence-conditioned identity metrics from one frozen "
            "tim_physical_target_bbox_v2 evaluator report. Pure arithmetic "
            "downstream layer implementing the Stage-7 prospective-freeze "
            "primary_metric_contract; it never re-runs the evaluator, "
            "re-opens bags, re-classifies identity, or introduces a "
            "pass/fail threshold."
        )
    )
    parser.add_argument(
        "input_report",
        type=Path,
        help="Path to a tim_physical_target_bbox_v2 evaluator JSON report.",
    )
    parser.add_argument("--label", default=None)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Write the deterministic derived JSON structure to this path.",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Write the Markdown rendering to this path.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the derived JSON to stdout instead of the summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = _load_report(args.input_report)
        derived = derive_presence_conditioned_metrics(
            report, label=args.label
        )
    except PresenceConditionedError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(derived, indent=2, sort_keys=True) + "\n"
    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(payload, encoding="utf-8")
        print(f"Wrote: {args.out_json}")
    if args.out_md is not None:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(derived), encoding="utf-8")
        print(f"Wrote: {args.out_md}")

    if args.print_json:
        sys.stdout.write(payload)
    elif args.out_json is None and args.out_md is None:
        sys.stdout.write(render_human(derived))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
