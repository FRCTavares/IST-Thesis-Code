"""Tests for the TIM-MARS CPU ReID workload analyser."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis"
    / "analyse_tim_reid_workload.py"
)

SPEC = importlib.util.spec_from_file_location(
    "analyse_tim_reid_workload",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def payload(
    *,
    processing_ms: float,
    backend_calls: int,
    requested: int = 0,
    returned: int = 0,
    valid: int = 0,
    wall_ms: float = 0.0,
    cache_lookups: int = 0,
    cache_hits: int = 0,
    cache_misses: int = 0,
    cache_expired: int = 0,
    cache_invalidated: int = 0,
) -> dict[str, object]:
    return {
        "tim_mars_processing_ms": processing_ms,
        "appearance_candidates": 3,
        "appearance_features_valid": valid,
        "appearance_encoding_eligible": requested,
        "appearance_backend_calls": backend_calls,
        "appearance_backend_requested": requested,
        "appearance_backend_returned": returned,
        "appearance_backend_valid": valid,
        "appearance_backend_wall_ms": wall_ms,
        "appearance_cache_lookups": cache_lookups,
        "appearance_cache_hits": cache_hits,
        "appearance_cache_misses": cache_misses,
        "appearance_cache_expired": cache_expired,
        "appearance_cache_invalidated": cache_invalidated,
    }


def test_excludes_isolated_first_call_warmup():
    records = [
        (
            0,
            payload(
                processing_ms=1.0,
                backend_calls=0,
            ),
        ),
        (
            1_000_000_000,
            payload(
                processing_ms=301.0,
                backend_calls=1,
                requested=2,
                returned=2,
                valid=2,
                wall_ms=300.0,
            ),
        ),
        (
            2_000_000_000,
            payload(
                processing_ms=41.0,
                backend_calls=1,
                requested=2,
                returned=2,
                valid=2,
                wall_ms=40.0,
            ),
        ),
        (
            3_000_000_000,
            payload(
                processing_ms=1.5,
                backend_calls=0,
            ),
        ),
    ]

    result = MODULE.analyse_records(
        records,
        run_name="synthetic",
        git_commit="abc",
    )

    assert result["warmup"][
        "first_call_is_warmup_outlier"
    ] is True
    assert result["warmup"][
        "warmup_reference_median_backend_wall_ms"
    ] == 40.0
    assert result["warmup"][
        "warmup_threshold_ms"
    ] == 120.0
    assert result["backend_wall_ms_all"]["n"] == 2
    assert (
        result["backend_wall_ms_steady_state"]["n"]
        == 1
    )
    assert (
        result["backend_wall_ms_steady_state"]["mean"]
        == 40.0
    )
    assert (
        result["warmup"][
            "excluded_backend_calls_from_steady_state"
        ]
        == 1
    )


def test_keeps_first_call_when_not_an_outlier():
    records = [
        (
            0,
            payload(
                processing_ms=41.0,
                backend_calls=1,
                requested=2,
                returned=2,
                valid=2,
                wall_ms=40.0,
            ),
        ),
        (
            1_000_000_000,
            payload(
                processing_ms=46.0,
                backend_calls=1,
                requested=2,
                returned=2,
                valid=2,
                wall_ms=45.0,
            ),
        ),
    ]

    result = MODULE.analyse_records(
        records,
        run_name="synthetic",
    )

    assert result["warmup"][
        "first_call_is_warmup_outlier"
    ] is False
    assert (
        result["backend_wall_ms_steady_state"]["n"]
        == 2
    )


def test_reports_callback_displacement_and_integrity():
    records = [
        (
            0,
            payload(
                processing_ms=1.0,
                backend_calls=0,
            ),
        ),
        (
            1_000_000_000,
            payload(
                processing_ms=21.5,
                backend_calls=1,
                requested=1,
                returned=1,
                valid=1,
                wall_ms=20.0,
            ),
        ),
        (
            2_000_000_000,
            payload(
                processing_ms=1.5,
                backend_calls=0,
            ),
        ),
    ]

    result = MODULE.analyse_records(
        records,
        run_name="synthetic",
    )

    assert (
        result["processing_displacement_mean_ms"]
        == 20.25
    )
    assert result["non_backend_processing_ms"]["mean"] == 1.5
    assert result["integrity"][
        "returned_not_greater_than_requested"
    ] is True
    assert result["integrity"][
        "valid_not_greater_than_returned"
    ] is True


def test_descriptive_stats_include_std_and_p90():
    stats = MODULE.descriptive_stats([1.0, 2.0, 3.0])

    assert stats["n"] == 3
    assert stats["mean"] == 2.0
    assert stats["std"] == pytest.approx(0.816496580927726)
    assert stats["p50"] == 2.0
    assert stats["p90"] == pytest.approx(2.8)
    assert stats["p95"] == pytest.approx(2.9)
    assert stats["p99"] == pytest.approx(2.98)


def test_reports_exact_cache_accounting():
    records = [
        (
            0,
            payload(
                processing_ms=1.0,
                backend_calls=0,
                cache_lookups=2,
                cache_hits=1,
                cache_misses=1,
            ),
        ),
        (
            1_000_000_000,
            payload(
                processing_ms=21.0,
                backend_calls=1,
                requested=1,
                returned=1,
                valid=1,
                wall_ms=20.0,
                cache_lookups=1,
                cache_expired=1,
            ),
        ),
    ]

    result = MODULE.analyse_records(
        records,
        run_name="synthetic",
    )

    totals = result["totals"]
    assert totals["appearance_cache_lookups"] == 3
    assert totals["appearance_cache_hits"] == 1
    assert totals["appearance_cache_misses"] == 1
    assert totals["appearance_cache_expired"] == 1
    assert totals["appearance_cache_invalidated"] == 0
    assert result["ratios"]["cache_hit_rate"] == pytest.approx(1.0 / 3.0)
    assert result["ratios"]["valid_embeddings_per_second"] == 1.0
    assert result["integrity"]["cache_accounting_identity_totals"] is True
    assert (
        result["integrity"]["cache_accounting_identity_all_records"]
        is True
    )


def test_render_markdown_contains_steady_state_contract():
    records = [
        (
            0,
            payload(
                processing_ms=21.0,
                backend_calls=1,
                requested=1,
                returned=1,
                valid=1,
                wall_ms=20.0,
            ),
        )
    ]

    result = MODULE.analyse_records(
        records,
        run_name="synthetic",
    )
    markdown = MODULE.render_markdown(result)

    assert "## Backend timing" in markdown
    assert "steady state" in markdown
    assert "## Warm-up classification" in markdown
    assert MODULE.SUMMARY_SCHEMA in markdown
