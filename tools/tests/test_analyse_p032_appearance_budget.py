from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "analysis" / "analyse_p032_appearance_budget.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_appearance_budget",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_payload(
    *,
    backend_calls: int = 0,
    backend_requested: int = 0,
    backend_valid: int = 0,
    features_valid: int = 0,
    backend_wall_ms: float = 0.0,
    lat_ms: float = 1.0,
    skip_reason: str = "",
) -> dict:
    return {
        "appearance_backend_calls": backend_calls,
        "appearance_backend_requested": backend_requested,
        "appearance_backend_returned": backend_requested,
        "appearance_backend_valid": backend_valid,
        "appearance_backend_wall_ms": backend_wall_ms,
        "appearance_features_valid": features_valid,
        "appearance_skip_reason": skip_reason,
        "lat_ms": lat_ms,
    }


def test_percentile_matches_known_values() -> None:
    module = load_module()

    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    assert module.percentile(values, 0.0) == 10.0
    assert module.percentile(values, 1.0) == 50.0
    assert module.percentile(values, 0.5) == 30.0


def test_percentile_empty_returns_none() -> None:
    module = load_module()

    assert module.percentile([], 0.5) is None


def test_analyse_rejects_empty_records() -> None:
    module = load_module()

    with pytest.raises(ValueError):
        module.analyse(
            [],
            run_name="empty",
            git_commit="deadbeef",
            bag_path="/nonexistent",
        )


def test_replay_mode_nulls_latency_not_zero() -> None:
    """Deterministic replay hardcodes lat_ms/wall_ms to 0.0. The analyser
    must report this as unavailable (null), never as a real zero-latency
    measurement -- fabricating a zero would be a false safety/perf claim."""
    module = load_module()

    records = [
        (
            1_000_000_000 * i,
            make_payload(
                backend_calls=1,
                backend_requested=1,
                backend_valid=1,
                features_valid=1,
                backend_wall_ms=0.0,
                lat_ms=0.0,
            ),
        )
        for i in range(5)
    ]

    summary = module.analyse(
        records,
        run_name="replay_run",
        git_commit="deadbeef",
        bag_path="/tmp/tim.bag",
        measurement_mode=module.REPLAY_MODE,
    )

    assert summary["tim_core_latency_ms"] is None
    assert summary["appearance_backend_wall_ms"] is None
    assert summary["latency_unavailable_reason"] is not None
    assert "hardcodes" in summary["latency_unavailable_reason"]

    # Count-based budget metrics are unaffected by the replay timing
    # limitation and must still be reported.
    assert summary["candidates_encoded_total"] == 5
    assert summary["embeddings_valid_total"] == 5


def test_live_mode_reports_real_latency_percentiles() -> None:
    module = load_module()

    records = [
        (
            1_000_000_000 * i,
            make_payload(
                backend_calls=1,
                backend_requested=1,
                backend_valid=1,
                features_valid=1,
                backend_wall_ms=float(i + 1) * 10.0,
                lat_ms=float(i + 1) * 5.0,
            ),
        )
        for i in range(10)
    ]

    summary = module.analyse(
        records,
        run_name="live_run",
        git_commit="deadbeef",
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )

    assert summary["latency_unavailable_reason"] is None
    assert summary["tim_core_latency_ms"] is not None
    assert summary["appearance_backend_wall_ms"] is not None
    assert summary["tim_core_latency_ms"]["count"] == 10
    assert summary["tim_core_latency_ms"]["maximum"] == 50.0


def test_cache_hit_rate_derived_from_published_counters() -> None:
    """cache_served = features_valid in excess of fresh backend_valid."""
    module = load_module()

    records = [
        (
            0,
            make_payload(
                backend_calls=1,
                backend_requested=1,
                backend_valid=1,
                features_valid=4,
                lat_ms=1.0,
            ),
        )
    ]

    summary = module.analyse(
        records,
        run_name="cache_run",
        git_commit="deadbeef",
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )

    assert summary["cache_served_total"] == 3
    assert summary["cache_hit_rate"] == pytest.approx(3.0 / 4.0)


def test_cache_hit_rate_none_when_no_valid_features() -> None:
    module = load_module()

    records = [
        (0, make_payload(backend_calls=0, features_valid=0, lat_ms=1.0)),
    ]

    summary = module.analyse(
        records,
        run_name="no_features",
        git_commit=None,
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )

    assert summary["cache_hit_rate"] is None


def test_fraction_frames_invoking_appearance_denominator_is_total_records() -> None:
    module = load_module()

    records = [
        (0, make_payload(backend_calls=1, lat_ms=1.0)),
        (1, make_payload(backend_calls=0, lat_ms=1.0)),
        (2, make_payload(backend_calls=0, lat_ms=1.0)),
        (3, make_payload(backend_calls=0, lat_ms=1.0)),
    ]

    summary = module.analyse(
        records,
        run_name="denom_run",
        git_commit=None,
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )

    assert summary["record_count"] == 4
    assert summary["frames_invoking_appearance"] == 1
    assert summary["fraction_frames_invoking_appearance"] == pytest.approx(0.25)


def test_analyse_fails_closed_on_missing_required_field() -> None:
    module = load_module()

    records = [(0, {"appearance_backend_calls": 0})]

    with pytest.raises(KeyError):
        module.analyse(
            records,
            run_name="malformed",
            git_commit=None,
            bag_path="/tmp/tim.bag",
            measurement_mode=module.LIVE_MODE,
        )


def test_analyse_orders_records_by_timestamp_deterministically() -> None:
    module = load_module()

    records = [
        (3_000_000_000, make_payload(lat_ms=3.0)),
        (1_000_000_000, make_payload(lat_ms=1.0)),
        (2_000_000_000, make_payload(lat_ms=2.0)),
    ]

    summary_a = module.analyse(
        records,
        run_name="order_a",
        git_commit=None,
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )
    summary_b = module.analyse(
        list(reversed(records)),
        run_name="order_b",
        git_commit=None,
        bag_path="/tmp/tim.bag",
        measurement_mode=module.LIVE_MODE,
    )

    assert summary_a["duration_s"] == pytest.approx(summary_b["duration_s"])
    assert summary_a["tim_core_latency_ms"] == summary_b["tim_core_latency_ms"]


def test_render_markdown_never_raises_on_unavailable_latency() -> None:
    module = load_module()

    records = [(0, make_payload(lat_ms=0.0, backend_wall_ms=0.0))]
    summary = module.analyse(
        records,
        run_name="markdown_check",
        git_commit=None,
        bag_path="/tmp/tim.bag",
        measurement_mode=module.REPLAY_MODE,
    )

    rendered = module.render_markdown(summary)
    assert "unavailable" in rendered.lower()
