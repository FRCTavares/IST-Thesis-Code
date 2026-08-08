from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "analysis" / "analyze_p032_sustained_run.py"
)

DURATION_S = 300.0
DURATION_NS = int(DURATION_S * 1e9)
SAMPLE_COUNT = 160


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_analyze_sustained_run",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload))


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def _resource_samples(
    *, cpu_late_spike: bool = False, groups=("perception", "tim", "relay")
) -> list[dict]:
    rows = []
    for i in range(SAMPLE_COUNT):
        timestamp = int(i * DURATION_NS / SAMPLE_COUNT)
        cpu = 20.0
        if cpu_late_spike and i > (2 * SAMPLE_COUNT // 3):
            cpu = 500.0
        for group in groups:
            rows.append(
                {
                    "sample_monotonic_ns": timestamp,
                    "group": group,
                    "cpu_percent": cpu,
                    "rss_kib": 100_000,
                }
            )
    return rows


def _health_samples(
    *, temperature_c: float = 55.0, throttled: int = 0
) -> list[dict]:
    rows = []
    for i in range(SAMPLE_COUNT):
        timestamp = int(i * DURATION_NS / SAMPLE_COUNT)
        rows.append(
            {
                "monotonic_ns": timestamp,
                "temperature_c": temperature_c,
                "arm_frequency_hz": 2_400_000_000,
                "mem_available_kib": 4_000_000,
                "throttled": throttled,
            }
        )
    return rows


def _timing_summary(*, cadence_ok: bool = True) -> dict:
    return {
        "duration_s": DURATION_S - 60.0,
        "topics": {
            "/timing": {"count": 1000, "frame_id_missing_estimate": 0},
            "/timing_tracker": {"count": 1000, "frame_id_missing_estimate": 0},
            "/timing_target": {"count": 1000, "frame_id_missing_estimate": 0},
        },
        "metrics": {
            "/timing": {"e2e_det_ms": {"p50": 40.0, "p95": 80.0}},
            "/timing_tracker": {"track_ms": {"p50": 5.0}},
            "/timing_target": {"e2e_target_ms": {"p95": 90.0}},
        },
        "cadence_consistency": {"within_tolerance": cadence_ok},
    }


def _relay_summary(*, accounting_ok: bool = True) -> dict:
    published = 1000 if accounting_ok else 990
    return {
        "schema": "p044_soak_input_relay_summary_v1",
        "counters": {
            "images_received": 1000,
            "images_published": published,
            "tracks_received": 1000,
            "tracks_published": 1000,
            "image_publication_errors": 0,
            "track_publication_errors": 0,
        },
        "source_image_rewinds": 2,
        "source_track_rewinds": 2,
    }


def _resources_summary() -> dict:
    return {
        "groups": {
            "perception": {"sample_count": SAMPLE_COUNT},
            "tim": {"sample_count": SAMPLE_COUNT},
            "relay": {"sample_count": SAMPLE_COUNT},
        }
    }


def _health_summary(
    *, temperature_maximum: float = 60.0, throttle_count: int = 0
) -> dict:
    return {
        "schema": "p044_hardware_health_summary_v1",
        "sample_count": SAMPLE_COUNT,
        "samples_with_errors": 0,
        "nonzero_throttle_sample_count": throttle_count,
        "temperature_c": {"maximum": temperature_maximum},
        "mem_available_kib": {"minimum": 4_000_000},
    }


def _run_analysis(
    tmp_path: Path,
    module: ModuleType,
    *,
    timing_summary: dict,
    relay_summary: dict,
    resources_summary: dict,
    resource_samples: list[dict],
    health_summary: dict,
    health_samples: list[dict],
) -> dict:
    timing_path = tmp_path / "timing_summary.json"
    relay_path = tmp_path / "relay_summary.json"
    resources_summary_path = tmp_path / "resources_summary.json"
    resources_samples_path = tmp_path / "resources_samples.jsonl"
    health_summary_path = tmp_path / "health_summary.json"
    health_samples_path = tmp_path / "health_samples.jsonl"
    output_path = tmp_path / "sustained_analysis.json"

    _write_json(timing_path, timing_summary)
    _write_json(relay_path, relay_summary)
    _write_json(resources_summary_path, resources_summary)
    _write_jsonl(resources_samples_path, resource_samples)
    _write_json(health_summary_path, health_summary)
    _write_jsonl(health_samples_path, health_samples)

    argv = [
        "analyze_p032_sustained_run.py",
        "--timing-summary",
        str(timing_path),
        "--relay-summary",
        str(relay_path),
        "--resources-summary",
        str(resources_summary_path),
        "--resources-samples",
        str(resources_samples_path),
        "--health-summary",
        str(health_summary_path),
        "--health-samples",
        str(health_samples_path),
        "--duration-s",
        str(DURATION_S),
        "--warm-up-s",
        "60.0",
        "--output",
        str(output_path),
    ]

    import sys as _sys

    original_argv = _sys.argv
    _sys.argv = argv
    try:
        exit_code = module.main()
    finally:
        _sys.argv = original_argv

    result = json.loads(output_path.read_text())
    result["_exit_code"] = exit_code
    return result


def test_passing_run_has_no_violations(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(),
        health_samples=_health_samples(),
    )

    assert result["_exit_code"] == 0
    assert result["passed"] is True
    assert result["violations"] == []


def test_nonzero_throttle_fails_closed(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(throttle_count=3),
        health_samples=_health_samples(throttled=1),
    )

    assert result["_exit_code"] == 1
    assert "nonzero_throttle_observed" in result["violations"]


def test_cadence_inconsistency_is_a_violation(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(cadence_ok=False),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(),
        health_samples=_health_samples(),
    )

    assert "cadence_inconsistent_with_detection_rate" in result["violations"]


def test_relay_accounting_mismatch_is_a_violation(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(accounting_ok=False),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(),
        health_samples=_health_samples(),
    )

    assert "relay_image_accounting" in result["violations"]


def test_temperature_over_ceiling_is_a_violation(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(temperature_maximum=95.0),
        health_samples=_health_samples(temperature_c=95.0),
    )

    assert "temperature_limit" in result["violations"]


def test_cpu_drift_late_spike_is_a_violation(tmp_path: Path) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(cpu_late_spike=True),
        health_summary=_health_summary(),
        health_samples=_health_samples(),
    )

    assert any(
        violation.endswith("_cpu_drift") for violation in result["violations"]
    )


def test_empty_health_samples_fails_closed(tmp_path: Path) -> None:
    module = load_module()

    with pytest.raises(SystemExit, match="no hardware-health samples"):
        _run_analysis(
            tmp_path,
            module,
            timing_summary=_timing_summary(),
            relay_summary=_relay_summary(),
            resources_summary=_resources_summary(),
            resource_samples=_resource_samples(),
            health_summary=_health_summary(),
            health_samples=[],
        )


def test_claim_boundary_documents_replayed_source_not_live_camera(
    tmp_path: Path,
) -> None:
    module = load_module()

    result = _run_analysis(
        tmp_path,
        module,
        timing_summary=_timing_summary(),
        relay_summary=_relay_summary(),
        resources_summary=_resources_summary(),
        resource_samples=_resource_samples(),
        health_summary=_health_summary(),
        health_samples=_health_samples(),
    )

    assert result["claim_boundary"]["physically_live_camera"] is False
    assert (
        result["claim_boundary"]["source_category"]
        == "replayed_bag_via_timestamp_refresh_relay"
    )
