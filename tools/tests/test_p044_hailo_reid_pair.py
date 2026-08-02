"""Contracts for the Issue #44 paired Hailo ReID evidence tools."""

from pathlib import Path
import importlib.util
import json


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_p044_hailo_reid_pair.sh"
)
COLLECTOR = (
    ROOT
    / "tools"
    / "experiments"
    / "collect_p044_transport_evidence.py"
)


def load_collector_module():
    """Load the collector without installing the tools package."""
    specification = (
        importlib.util.spec_from_file_location(
            "p044_collector",
            COLLECTOR,
        )
    )

    assert specification is not None
    assert specification.loader is not None

    module = importlib.util.module_from_spec(
        specification
    )
    specification.loader.exec_module(module)
    return module


def test_runner_avoids_fail_fast_shell_mode():
    """Do not terminate the user's shell through set -e."""
    source = RUNNER.read_text(encoding="utf-8")

    assert "set -e" not in source
    assert "set +e" in source
    assert "set +u" in source


def test_runner_uses_identical_source_topics_for_pair():
    """Only ReID activation should differ between conditions."""
    source = RUNNER.read_text(encoding="utf-8")

    assert (
        'ros2 bag play "$BAG_PATH"'
        in source
    )
    assert (
        '--topics "$IMAGE_TOPIC" /tracks'
        in source
    )
    assert (
        "run_condition reference"
        in source
    )
    assert (
        "run_condition treatment"
        in source
    )


def test_runner_preserves_cpu_mars_reference_policy():
    """Keep the existing CPU MARS safety path unchanged."""
    source = RUNNER.read_text(encoding="utf-8")

    assert (
        "-p appearance_request_policy:=all_candidates"
        in source
    )
    assert (
        "-p appearance_compute_min_interval_ms:=250.0"
        in source
    )
    assert (
        "-p appearance_enabled:=true"
        in source
    )


def test_runner_switches_both_reid_endpoints_together():
    """Enable perception and TIM transport only in treatment."""
    source = RUNNER.read_text(encoding="utf-8")

    assert 'reid_enabled="false"' in source
    assert 'async_enabled="false"' in source
    assert (
        'if [ "$condition" = "treatment" ]'
        in source
    )
    assert 'reid_enabled="true"' in source
    assert 'async_enabled="true"' in source
    assert (
        '-p reid_enabled:="$reid_enabled"'
        in source
    )
    assert (
        '-p appearance_async_reid_enabled:="$async_enabled"'
        in source
    )


def test_runner_records_required_evidence_topics():
    """Record timing, status, causal transport, and TIM output."""
    source = RUNNER.read_text(encoding="utf-8")

    required = (
        "/timing",
        "/perception/reid/status",
        "/appearance/reid/request",
        "/appearance/reid/result",
        "/target_memory_mars/status",
    )

    for topic in required:
        assert topic in source


def test_collector_metric_summary():
    """Summarise deterministic timing values."""
    module = load_collector_module()

    summary = module.metric_summary(
        [1.0, 2.0, 3.0, 4.0]
    )

    assert summary["count"] == 4
    assert summary["mean"] == 2.5
    assert summary["minimum"] == 1.0
    assert summary["p50"] == 2.5
    assert summary["maximum"] == 4.0


def test_collector_empty_metric_summary():
    """Represent absent evidence explicitly."""
    module = load_collector_module()

    summary = module.metric_summary([])

    assert summary == {
        "count": 0,
        "mean": None,
        "minimum": None,
        "p50": None,
        "p95": None,
        "p99": None,
        "maximum": None,
    }


def test_runner_metadata_is_versioned():
    """Keep report and comparison schemas machine-readable."""
    source = RUNNER.read_text(encoding="utf-8")

    assert (
        "p044_hailo_reid_pair_run_v1"
        in source
    )
    assert (
        "p044_hailo_reid_pair_comparison_v1"
        in source
    )

    collector = COLLECTOR.read_text(
        encoding="utf-8"
    )

    assert (
        "p044_transport_evidence_summary_v1"
        in collector
    )
    assert "events.jsonl" in collector
    assert "summary.json" in collector
