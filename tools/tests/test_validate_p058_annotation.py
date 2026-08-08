"""Tests for the Issue #58 annotation validator, in particular the
fail-closed stale-source-bag guard.

The two "must fail" tests exercise the exact real, tracked files this
guard exists to catch (docs/data/annotations/june_hard_sequences/
seq03_deepsort.csv, seq04_deepsort.csv), not synthetic stand-ins -- this
is the regression test proving the guard actually fires on the known
problem, not just on a fixture shaped like it.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "tools" / "analysis" / "validate_p058_annotation.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("validate_p058_annotation", MODULE_PATH)


class TestKnownStaleAnnotationsAreRejected:
    def test_seq04_deepsort_fails_on_the_real_tracked_file(self):
        path = (
            REPO_ROOT
            / "docs"
            / "data"
            / "annotations"
            / "june_hard_sequences"
            / "seq04_deepsort.csv"
        )
        problems = MODULE.validate(path, "dev_june_seq04", "deepsort")
        assert problems
        assert any("KNOWN-STALE" in p for p in problems)
        assert any("2026-06-19__12-59-53" in p for p in problems)

    def test_seq03_deepsort_fails_on_the_real_tracked_file(self):
        path = (
            REPO_ROOT
            / "docs"
            / "data"
            / "annotations"
            / "june_hard_sequences"
            / "seq03_deepsort.csv"
        )
        problems = MODULE.validate(path, "dev_june_seq03", "deepsort")
        assert problems
        assert any("KNOWN-STALE" in p for p in problems)
        assert any("2026-06-19__12-55-58" in p for p in problems)


class TestKnownValidAnnotationsPass:
    def test_may_sort_annotation_passes(self):
        path = (
            REPO_ROOT
            / "docs"
            / "data"
            / "annotations"
            / "may_hard_reentry"
            / "sort_f17cdf80_autonomous.csv"
        )
        problems = MODULE.validate(path, "dev_may_hard_reentry", "sort")
        assert problems == []

    def test_may_deepsort_annotation_passes(self):
        path = (
            REPO_ROOT
            / "docs"
            / "data"
            / "annotations"
            / "may_hard_reentry"
            / "deepsort_f17cdf80_autonomous.csv"
        )
        problems = MODULE.validate(path, "dev_may_hard_reentry", "deepsort")
        assert problems == []


class TestSourceAssociationCheck:
    def test_wrong_sequence_pattern_is_rejected(self):
        rows = [
            {
                "bag_name": "2026-06-19__12-57-48__...__tracker_deepsort__...",
                "start_s": "0.0",
                "end_s": "10.0",
                "target_visible": "true",
                "correct_target_track_id": "1",
                "event_type": "clean_visible",
            }
        ]
        # This row is the Seq03 pattern, checked against Seq04's expectation.
        problems = MODULE.check_source_association(rows, "dev_june_seq04")
        assert problems

    def test_unregistered_sequence_fails_closed_not_silently_passes(self):
        problems = MODULE.check_source_association([{"bag_name": "x"}], "dev_unknown_sequence")
        assert problems
        assert "no known canonical source pattern" in problems[0]


class TestIntervalContinuity:
    def test_gap_between_intervals_is_detected(self):
        rows = [
            {"start_s": "0.0", "end_s": "10.0"},
            {"start_s": "10.5", "end_s": "20.0"},
        ]
        problems = MODULE.check_interval_continuity(rows)
        assert any("gap or overlap" in p for p in problems)

    def test_overlap_between_intervals_is_detected(self):
        rows = [
            {"start_s": "0.0", "end_s": "10.0"},
            {"start_s": "9.0", "end_s": "20.0"},
        ]
        problems = MODULE.check_interval_continuity(rows)
        assert any("gap or overlap" in p for p in problems)

    def test_contiguous_intervals_pass(self):
        rows = [
            {"start_s": "0.0", "end_s": "10.0"},
            {"start_s": "10.0", "end_s": "20.0"},
        ]
        problems = MODULE.check_interval_continuity(rows)
        assert problems == []

    def test_inverted_interval_is_rejected(self):
        rows = [{"start_s": "10.0", "end_s": "5.0"}]
        problems = MODULE.check_interval_continuity(rows)
        assert any("end_s must be greater than start_s" in p for p in problems)


class TestVisibilitySemantics:
    def test_visible_without_track_id_is_rejected(self):
        rows = [
            {"target_visible": "true", "correct_target_track_id": "", "event_type": "clean_visible"}
        ]
        problems = MODULE.check_visibility_semantics(rows)
        assert problems

    def test_absent_with_track_id_is_rejected(self):
        rows = [
            {"target_visible": "false", "correct_target_track_id": "3", "event_type": "target_absent"}
        ]
        problems = MODULE.check_visibility_semantics(rows)
        assert problems

    def test_consistent_visible_row_passes(self):
        rows = [
            {"target_visible": "true", "correct_target_track_id": "3", "event_type": "clean_visible"}
        ]
        assert MODULE.check_visibility_semantics(rows) == []

    def test_consistent_absent_row_passes(self):
        rows = [
            {"target_visible": "false", "correct_target_track_id": "", "event_type": "target_absent"}
        ]
        assert MODULE.check_visibility_semantics(rows) == []


class TestNeverAutoCorrects:
    def test_validate_only_reports_never_rewrites_the_file(self, tmp_path):
        src = (
            REPO_ROOT
            / "docs"
            / "data"
            / "annotations"
            / "june_hard_sequences"
            / "seq04_deepsort.csv"
        )
        before = src.read_bytes()
        MODULE.validate(src, "dev_june_seq04", "deepsort")
        after = src.read_bytes()
        assert before == after
