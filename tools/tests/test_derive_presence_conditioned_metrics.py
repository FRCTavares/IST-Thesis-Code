"""Tests for the presence-conditioned reporting layer.

This layer is pure arithmetic downstream of the frozen
``tim_physical_target_bbox_v2`` evaluator. These tests never touch the frozen
evaluator, its tests, or any bag.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "derive_presence_conditioned_metrics.py"
)
SPEC = importlib.util.spec_from_file_location(
    "derive_presence_conditioned_metrics", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

derive = MODULE.derive_presence_conditioned_metrics
PresenceConditionedError = MODULE.PresenceConditionedError


def make_report(**buckets: float) -> dict:
    """A minimal well-formed tim_physical_target_bbox_v2 report.

    ``total_evaluated_duration_s`` defaults to the exact partition sum so the
    report reconciles unless a test overrides it.
    """
    b = {
        "correct_target_output_duration_s": 0.0,
        "wrong_person_output_duration_s": 0.0,
        "identity_unresolved_duration_s": 0.0,
        "lost_or_suppressed_duration_s": 0.0,
        "target_absent_duration_s": 0.0,
        "target_absent_with_output_duration_s": 0.0,
        "reference_unavailable_duration_s": 0.0,
        "reference_gap_duration_s": 0.0,
        "localisation_scored_duration_s": 0.0,
        "reference_gap_with_output_duration_s": 0.0,
    }
    b.update(buckets)
    present = (
        b["correct_target_output_duration_s"]
        + b["wrong_person_output_duration_s"]
        + b["identity_unresolved_duration_s"]
        + b["lost_or_suppressed_duration_s"]
    )
    total = (
        present
        + b["target_absent_duration_s"]
        + b["reference_unavailable_duration_s"]
        + b["reference_gap_duration_s"]
    )
    return {
        "schema_version": 2,
        "contract_version": "tim_physical_target_bbox_v2",
        "evaluator": "physical_target_bbox_evaluation_v2",
        "evaluator_mode": "physical_reference_v2",
        "stream": "tim_target_memory",
        "physical_reference_path": "docs/data/physical_target_references/x.json",
        "physical_reference_sha256": "0" * 64,
        "repo_commit": "deadbeef",
        "repo_dirty": False,
        "evaluation_window": {"start_s": 0.0, "end_s": total},
        "total_evaluated_duration_s": total,
        "duration_buckets": b,
        "coverage": {
            "reference_covered_duration_s": present,
            "reference_gap_duration_s": b["reference_gap_duration_s"],
            "reference_coverage_fraction": (
                present / total if total > 0 else None
            ),
            "interpolated_reference_duration_s": present,
        },
        "reconciliation": {
            "ok": True,
            "primary_bucket_total_s": total,
            "residual_s": 0.0,
        },
    }


# 1. normal target-present case
def test_normal_target_present_case():
    report = make_report(
        correct_target_output_duration_s=62.79632971200054,
        wrong_person_output_duration_s=0.03339424100000343,
        lost_or_suppressed_duration_s=5.035185820999448,
    )
    d = derive(report, label="may")
    tpa = d["target_presence_accounting"]
    wtp = d["while_target_present"]
    assert tpa["physical_target_present_duration_s"] == pytest.approx(
        67.864909774, abs=1e-6
    )
    assert wtp["correct_while_present_pct"] == pytest.approx(92.5314, abs=1e-3)
    assert wtp["wrong_while_present_pct"] == pytest.approx(0.0492, abs=1e-3)
    assert wtp["lost_or_suppressed_while_present_pct"] == pytest.approx(
        7.4194, abs=1e-3
    )


# 2. 100% correct case
def test_hundred_percent_correct_case():
    report = make_report(correct_target_output_duration_s=61.200516816)
    d = derive(report, label="seq01")
    wtp = d["while_target_present"]
    assert wtp["correct_while_present_pct"] == pytest.approx(100.0, abs=1e-9)
    assert wtp["wrong_while_present_pct"] == pytest.approx(0.0, abs=1e-9)
    assert wtp["lost_or_suppressed_while_present_pct"] == pytest.approx(
        0.0, abs=1e-9
    )
    assert d["while_target_absent"]["absence_leakage_pct"] is None


# 3. target-present mixture summing to 100%
def test_target_present_components_sum_to_100():
    report = make_report(
        correct_target_output_duration_s=24.600414281999996,
        lost_or_suppressed_duration_s=59.166383501000006,
        reference_gap_duration_s=0.1004533710000004,
    )
    d = derive(report, label="seq03")
    recon = d["reconciliation"]
    assert recon["present_pct_components_sum"] == pytest.approx(100.0, abs=1e-6)
    assert recon["present_pct_components_sum_ok"] is True
    wtp = d["while_target_present"]
    assert wtp["correct_while_present_pct"] == pytest.approx(29.3677, abs=1e-3)
    assert wtp["lost_or_suppressed_while_present_pct"] == pytest.approx(
        70.6323, abs=1e-3
    )


# 4. zero absent duration -> absent percentages null
def test_zero_absent_duration_yields_null_absent_percentages():
    report = make_report(
        correct_target_output_duration_s=24.6,
        lost_or_suppressed_duration_s=59.1,
        target_absent_duration_s=0.0,
        target_absent_with_output_duration_s=0.0,
    )
    d = derive(report)
    wta = d["while_target_absent"]
    assert wta["denominator_s"] == 0.0
    assert wta["absence_leakage_pct"] is None
    assert wta["safe_clear_while_absent_pct"] is None
    # JSON serialises the null explicitly, never as 0.
    payload = json.dumps(d, indent=2, sort_keys=True)
    assert '"absence_leakage_pct": null' in payload


# 5. non-zero absence leakage
def test_non_zero_absence_leakage():
    report = make_report(
        correct_target_output_duration_s=40.0,
        lost_or_suppressed_duration_s=10.0,
        target_absent_duration_s=8.0,
        target_absent_with_output_duration_s=2.0,
    )
    d = derive(report)
    wta = d["while_target_absent"]
    assert wta["absence_leakage_duration_s"] == 2.0
    assert wta["absence_leakage_pct"] == pytest.approx(25.0, abs=1e-9)


# 6. safe-clear derivation
def test_safe_clear_derivation():
    report = make_report(
        correct_target_output_duration_s=48.766241081999965,
        lost_or_suppressed_duration_s=23.733800690000038,
        target_absent_duration_s=13.900030159000003,
        target_absent_with_output_duration_s=0.0,
        reference_gap_duration_s=0.10088379499999434,
    )
    d = derive(report, label="seq04")
    wta = d["while_target_absent"]
    assert wta["safe_clear_while_absent_duration_s"] == pytest.approx(
        13.900030159000003, abs=1e-9
    )
    assert wta["safe_clear_while_absent_pct"] == pytest.approx(100.0, abs=1e-9)
    assert wta["absence_leakage_pct"] == pytest.approx(0.0, abs=1e-9)
    assert d["while_target_present"][
        "correct_while_present_pct"
    ] == pytest.approx(67.2637, abs=1e-3)


# 7. reference gap / unavailable stay outside the present denominator
def test_reference_gap_and_unavailable_outside_present_denominator():
    report = make_report(
        correct_target_output_duration_s=50.0,
        lost_or_suppressed_duration_s=10.0,
        reference_unavailable_duration_s=3.0,
        reference_gap_duration_s=4.0,
    )
    d = derive(report)
    tpa = d["target_presence_accounting"]
    assert tpa["physical_target_present_duration_s"] == pytest.approx(
        60.0, abs=1e-9
    )
    assert tpa["reference_unavailable_duration_s"] == 3.0
    assert tpa["reference_gap_duration_s"] == 4.0
    # denominator excludes the 7 s of gap/unavailable
    assert d["while_target_present"]["denominator_s"] == pytest.approx(
        60.0, abs=1e-9
    )
    assert d["while_target_present"][
        "correct_while_present_pct"
    ] == pytest.approx(100.0 * 50.0 / 60.0, abs=1e-9)


# --- exact Stage-7 percent_time_target_present ---------------------------------


def test_reference_gap_does_not_reduce_percent_time_target_present():
    """Frozen percent_time_target_present denominator is present+absent only."""
    no_gap = derive(
        make_report(
            correct_target_output_duration_s=40.0,
            lost_or_suppressed_duration_s=10.0,
            target_absent_duration_s=0.0,
        )
    )["target_presence_accounting"]
    with_gap = derive(
        make_report(
            correct_target_output_duration_s=40.0,
            lost_or_suppressed_duration_s=10.0,
            target_absent_duration_s=0.0,
            reference_gap_duration_s=5.0,
        )
    )["target_presence_accounting"]
    assert no_gap["percent_time_target_present"] == pytest.approx(100.0)
    assert with_gap["percent_time_target_present"] == pytest.approx(100.0)
    assert with_gap["present_plus_absent_duration_s"] == pytest.approx(50.0)
    # the gap only moves the secondary "% of total" quantity
    assert with_gap["physical_target_present_pct_of_total"] == pytest.approx(
        100.0 * 50.0 / 55.0
    )


def test_reference_unavailable_not_in_percent_time_denominator():
    tpa = derive(
        make_report(
            correct_target_output_duration_s=30.0,
            lost_or_suppressed_duration_s=10.0,
            target_absent_duration_s=10.0,
            reference_unavailable_duration_s=7.0,
        )
    )["target_presence_accounting"]
    assert tpa["present_plus_absent_duration_s"] == pytest.approx(50.0)
    assert tpa["percent_time_target_present"] == pytest.approx(80.0)
    assert tpa["percent_time_target_absent"] == pytest.approx(20.0)
    assert tpa["physical_target_present_pct_of_total"] == pytest.approx(
        100.0 * 40.0 / 57.0
    )


def test_seq03_like_present_positive_absent_zero_gap_positive():
    tpa = derive(
        make_report(
            correct_target_output_duration_s=24.600414281999996,
            lost_or_suppressed_duration_s=59.166383501000006,
            target_absent_duration_s=0.0,
            reference_gap_duration_s=0.1004533710000004,
        )
    )["target_presence_accounting"]
    assert tpa["percent_time_target_present"] == pytest.approx(100.0)
    assert tpa["percent_time_target_absent"] == pytest.approx(0.0)
    assert tpa["physical_target_present_pct_of_total"] < 100.0
    assert tpa["physical_target_present_pct_of_total"] == pytest.approx(
        99.88, abs=1e-2
    )


def test_percent_time_present_and_absent_sum_to_100():
    tpa = derive(
        make_report(
            correct_target_output_duration_s=48.766241081999965,
            lost_or_suppressed_duration_s=23.733800690000038,
            target_absent_duration_s=13.900030159000003,
            reference_gap_duration_s=0.10088379499999434,
        )
    )["target_presence_accounting"]
    assert tpa["percent_time_target_present"] == pytest.approx(83.9120, abs=1e-3)
    assert (
        tpa["percent_time_target_present"] + tpa["percent_time_target_absent"]
    ) == pytest.approx(100.0, abs=1e-9)


def test_zero_present_plus_absent_yields_null_percent_time():
    tpa = derive(
        make_report(
            reference_unavailable_duration_s=5.0,
            reference_gap_duration_s=3.0,
        )
    )["target_presence_accounting"]
    assert tpa["present_plus_absent_duration_s"] == 0.0
    assert tpa["percent_time_target_present"] is None
    assert tpa["percent_time_target_absent"] is None


def test_percent_time_target_present_not_equal_pct_of_total_with_gap():
    tpa = derive(
        make_report(
            correct_target_output_duration_s=72.500041772,
            target_absent_duration_s=13.900030159000003,
            reference_gap_duration_s=0.10088379499999434,
        )
    )["target_presence_accounting"]
    assert tpa["percent_time_target_present"] != pytest.approx(
        tpa["physical_target_present_pct_of_total"], abs=1e-6
    )


def test_stage7_mapping_points_at_exact_field():
    d = derive(make_report(correct_target_output_duration_s=10.0))
    mapping = d["stage7_primary_metric_contract_mapping"]
    text = mapping["percent_time_target_present"]
    assert "percent_time_target_present" in text
    assert (
        "physical_target_present_duration_s "
        "+ physical_target_absent_duration_s"
    ) in text
    assert "NOT this Stage-7 metric" in text


# 8. invalid negative durations rejected
def test_negative_duration_rejected():
    report = make_report(correct_target_output_duration_s=10.0)
    report["duration_buckets"]["lost_or_suppressed_duration_s"] = -1.0
    with pytest.raises(PresenceConditionedError, match="negative duration"):
        derive(report)


# 9. leakage > absent rejected
def test_leakage_exceeds_absent_rejected():
    report = make_report(
        correct_target_output_duration_s=10.0,
        target_absent_duration_s=2.0,
        target_absent_with_output_duration_s=3.0,
    )
    # keep total consistent so we exercise the leakage check, not reconciliation
    report["total_evaluated_duration_s"] = 12.0
    report["reconciliation"]["primary_bucket_total_s"] = 12.0
    with pytest.raises(PresenceConditionedError, match="exceeds"):
        derive(report)


# 10. inconsistent reconciliation rejected
def test_inconsistent_reconciliation_rejected():
    report = make_report(
        correct_target_output_duration_s=10.0,
        lost_or_suppressed_duration_s=5.0,
    )
    report["total_evaluated_duration_s"] = 99.0  # partition sum is 15.0
    with pytest.raises(PresenceConditionedError, match="reconcile"):
        derive(report)


def test_source_evaluator_reconciliation_false_rejected():
    report = make_report(correct_target_output_duration_s=10.0)
    report["reconciliation"]["ok"] = False
    with pytest.raises(
        PresenceConditionedError, match="source evaluator reconciliation"
    ):
        derive(report)


def test_present_denominator_inconsistent_with_reference_covered_rejected():
    report = make_report(
        correct_target_output_duration_s=10.0,
        lost_or_suppressed_duration_s=5.0,
    )
    report["coverage"]["reference_covered_duration_s"] = 42.0
    with pytest.raises(PresenceConditionedError, match="reference_covered"):
        derive(report)


def test_rejects_non_v2_report():
    report = make_report(correct_target_output_duration_s=1.0)
    report["contract_version"] = "tim_physical_target_bbox_v1"
    with pytest.raises(PresenceConditionedError, match="tim_physical_target_bbox_v2"):
        derive(report)


def test_rejects_missing_bucket():
    report = make_report(correct_target_output_duration_s=1.0)
    del report["duration_buckets"]["reference_gap_duration_s"]
    with pytest.raises(PresenceConditionedError, match="missing required key"):
        derive(report)


# 11. deterministic output
def test_deterministic_output():
    report = make_report(
        correct_target_output_duration_s=48.766241081999965,
        lost_or_suppressed_duration_s=23.733800690000038,
        target_absent_duration_s=13.900030159000003,
        reference_gap_duration_s=0.10088379499999434,
    )
    a = json.dumps(
        derive(copy.deepcopy(report), label="seq04"), indent=2, sort_keys=True
    )
    b = json.dumps(
        derive(copy.deepcopy(report), label="seq04"), indent=2, sort_keys=True
    )
    assert a == b


def test_pct_of_total_uses_total_denominator():
    report = make_report(
        correct_target_output_duration_s=48.766241081999965,
        lost_or_suppressed_duration_s=23.733800690000038,
        target_absent_duration_s=13.900030159000003,
        reference_gap_duration_s=0.10088379499999434,
    )
    d = derive(report)
    tpa = d["target_presence_accounting"]
    total = tpa["total_evaluated_duration_s"]
    assert tpa["physical_target_present_pct_of_total"] == pytest.approx(
        100.0 * tpa["physical_target_present_duration_s"] / total, abs=1e-9
    )
    assert tpa["physical_target_absent_pct_of_total"] == pytest.approx(
        100.0 * tpa["physical_target_absent_duration_s"] / total, abs=1e-9
    )
