from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "analysis" / "aggregate_p032_runtime_report.py"
)

# Issue #58's frozen architecture and sequence identifiers. The join
# contract between #32 and #58 depends on #32 never silently renaming or
# reordering these -- this list intentionally duplicates the manifest's own
# values so a drift in either place is caught.
EXPECTED_ARCHITECTURE_IDS = [
    "bytetrack_raw",
    "bytetrack_tim",
    "sort_raw",
    "sort_tim",
    "deepsort_raw",
    "deepsort_tim",
]
EXPECTED_SEQUENCE_IDS = [
    "dev_may_hard_reentry",
    "dev_june_seq01",
    "dev_june_seq03",
    "dev_june_seq04",
]


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p032_aggregate_runtime_report",
        MODULE_PATH,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_replay_row_missing_file_is_status_missing_not_zero(
    tmp_path: Path,
) -> None:
    module = load_module()

    row = module.build_replay_row(
        {"id": "bytetrack_raw", "tim_enabled": False},
        "dev_may_hard_reentry",
        tmp_path / "does_not_exist",
    )

    assert row["status"] == "missing"
    assert "reason" in row
    # Must not silently report zero cost for missing evidence.
    assert "total_cpu_s" not in row


def test_build_replay_row_tim_disabled_marks_not_applicable(
    tmp_path: Path,
) -> None:
    module = load_module()

    replay_dir = tmp_path / "bytetrack_raw"
    replay_dir.mkdir()
    tracker_record = {
        "wall_s": 10.0,
        "user_cpu_s": 5.0,
        "sys_cpu_s": 1.0,
        "total_cpu_s": 6.0,
        "peak_rss_kib": 1000,
        "frame_count": 100,
        "mean_cpu_ms_per_frame": 60.0,
        "provenance": {"git_commit": "deadbeef"},
    }
    (replay_dir / "replay_cost_tracker.json").write_text(
        json.dumps(tracker_record)
    )

    row = module.build_replay_row(
        {"id": "bytetrack_raw", "tim_enabled": False},
        "dev_may_hard_reentry",
        replay_dir,
    )

    assert row["status"] == "measured"
    assert row["tim"]["status"] == module.NOT_APPLICABLE_TIM_DISABLED
    assert row["combined_total_cpu_s"] == 6.0
    assert row["combined_peak_rss_kib"] == 1000


def test_build_replay_row_tim_missing_is_unavailable_not_zero(
    tmp_path: Path,
) -> None:
    module = load_module()

    replay_dir = tmp_path / "bytetrack_tim"
    replay_dir.mkdir()
    tracker_record = {
        "wall_s": 10.0,
        "user_cpu_s": 5.0,
        "sys_cpu_s": 1.0,
        "total_cpu_s": 6.0,
        "peak_rss_kib": 1000,
        "frame_count": 100,
        "mean_cpu_ms_per_frame": 60.0,
        "provenance": {"git_commit": "deadbeef"},
    }
    (replay_dir / "replay_cost_tracker.json").write_text(
        json.dumps(tracker_record)
    )
    # No replay_cost_tim.json written -- TIM stage not yet run.

    row = module.build_replay_row(
        {"id": "bytetrack_tim", "tim_enabled": True},
        "dev_may_hard_reentry",
        replay_dir,
    )

    assert row["tim"]["status"] == "missing"
    assert row["combined_total_cpu_s"] is None
    assert row["combined_peak_rss_kib"] is None


def test_build_replay_row_combines_tracker_and_tim_cost(
    tmp_path: Path,
) -> None:
    module = load_module()

    replay_dir = tmp_path / "bytetrack_tim"
    replay_dir.mkdir()
    (replay_dir / "replay_cost_tracker.json").write_text(
        json.dumps(
            {
                "wall_s": 10.0,
                "user_cpu_s": 5.0,
                "sys_cpu_s": 1.0,
                "total_cpu_s": 6.0,
                "peak_rss_kib": 1000,
                "frame_count": 100,
                "mean_cpu_ms_per_frame": 60.0,
                "provenance": {"git_commit": "deadbeef"},
            }
        )
    )

    appearance_path = replay_dir / "appearance_workload.json"
    appearance_path.write_text(json.dumps({"schema": "p032_appearance_budget_v1"}))

    (replay_dir / "replay_cost_tim.json").write_text(
        json.dumps(
            {
                "wall_s": 8.0,
                "user_cpu_s": 4.0,
                "sys_cpu_s": 1.0,
                "total_cpu_s": 5.0,
                "peak_rss_kib": 2000,
                "appearance_budget_json": str(appearance_path),
                "provenance": {"git_commit": "deadbeef"},
            }
        )
    )

    row = module.build_replay_row(
        {"id": "bytetrack_tim", "tim_enabled": True},
        "dev_may_hard_reentry",
        replay_dir,
    )

    assert row["combined_total_cpu_s"] == pytest.approx(11.0)
    assert row["combined_peak_rss_kib"] == 2000
    assert row["tim"]["appearance_budget"]["schema"] == "p032_appearance_budget_v1"


def test_build_live_row_not_measured_when_no_path() -> None:
    module = load_module()

    row = module.build_live_row(None)

    assert row["status"] == module.NOT_MEASURED_LIVE
    assert row["source"] == "live_sustained"


def test_build_live_row_missing_file_is_status_missing(tmp_path: Path) -> None:
    module = load_module()

    row = module.build_live_row(tmp_path / "absent_sustained_analysis.json")

    assert row["status"] == "missing"


def test_build_live_row_flags_e2e_target_known_limitation_without_correction(
    tmp_path: Path,
) -> None:
    """Without a --live-e2e-target-latency correction file, the raw
    collect_live_timing_stats.py percentiles may mix the
    correlation-miss unavailable sentinel (0.0) with genuine
    measurements. The aggregator must carry a documented caveat
    alongside the raw value so it is never mistaken for a trustworthy
    measurement downstream (e.g. by Issue #58's join)."""
    module = load_module()

    analysis_path = tmp_path / "sustained_analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "passed": True,
                "violations": [],
                "observed_duration_s": 1200.0,
                "warm_up_s": 60.0,
                "timing": {
                    "metrics": {
                        "/timing": {"e2e_det_ms": {"p50": 12.0}},
                        "/timing_tracker": {"track_ms": {"p50": 3.8}},
                        "/timing_target": {
                            "e2e_target_ms": {
                                "n": 100,
                                "mean": 0.0,
                                "p50": 0.0,
                                "max": 0.0,
                            }
                        },
                    },
                    "cadence_consistency": {"within_tolerance": True},
                },
                "windows": {"resources": {}, "health": {}},
                "claim_boundary": {},
            }
        )
    )

    row = module.build_live_row(analysis_path)

    assert row["latency_ms"]["e2e_target"]["mean"] == 0.0
    assert "e2e_target_ms_known_limitation" in row
    assert "no corrected" in row["e2e_target_ms_known_limitation"].lower()


def test_build_live_row_uses_corrected_e2e_target_percentiles_when_supplied(
    tmp_path: Path,
) -> None:
    """When a corrected e2e_target_ms analysis is supplied, its
    genuine-measurement-only percentiles must be used instead of the raw
    (possibly sentinel-contaminated) collect_live_timing_stats.py value,
    and the row must report the coverage rate explicitly."""
    module = load_module()

    analysis_path = tmp_path / "sustained_analysis.json"
    analysis_path.write_text(
        json.dumps(
            {
                "passed": True,
                "violations": [],
                "observed_duration_s": 1200.0,
                "warm_up_s": 60.0,
                "timing": {
                    "metrics": {
                        "/timing": {"e2e_det_ms": {"p50": 12.0}},
                        "/timing_tracker": {"track_ms": {"p50": 3.8}},
                        "/timing_target": {
                            "e2e_target_ms": {
                                "n": 100,
                                "mean": 0.0,
                                "p50": 0.0,
                                "max": 0.0,
                            }
                        },
                    },
                    "cadence_consistency": {"within_tolerance": True},
                },
                "windows": {"resources": {}, "health": {}},
                "claim_boundary": {},
            }
        )
    )

    e2e_target_path = tmp_path / "e2e_target_latency.json"
    e2e_target_path.write_text(
        json.dumps(
            {
                "total_samples": 4109,
                "genuine_measurement_count": 1038,
                "unavailable_sentinel_count": 3071,
                "coverage_rate": 0.2526,
                "e2e_target_ms": {
                    "count": 1038,
                    "p50": 19.66,
                    "p90": 26.90,
                    "p95": 30.60,
                    "p99": 39.28,
                    "maximum": 52.39,
                    "minimum": 15.21,
                    "mean": 21.12,
                },
            }
        )
    )

    row = module.build_live_row(analysis_path, e2e_target_path)

    assert row["latency_ms"]["e2e_target"]["p50"] == 19.66
    assert row["latency_ms"]["e2e_target"]["p95"] == 30.60
    assert row["e2e_target_ms_coverage"]["coverage_rate"] == pytest.approx(0.2526)
    assert row["e2e_target_ms_coverage"]["genuine_measurement_count"] == 1038
    assert "e2e_target_ms_known_limitation" in row
    assert "fixed" in row["e2e_target_ms_known_limitation"].lower()


def test_comparative_overhead_computes_delta_when_both_present() -> None:
    module = load_module()

    rows_by_id = {
        "bytetrack_raw": {
            "replay": {"combined_total_cpu_s": 6.0, "combined_peak_rss_kib": 1000}
        },
        "bytetrack_tim": {
            "replay": {"combined_total_cpu_s": 11.0, "combined_peak_rss_kib": 2000}
        },
    }

    overhead = module.comparative_overhead(rows_by_id)
    bytetrack_entry = next(
        entry for entry in overhead if entry["tracker_type"] == "bytetrack"
    )

    assert bytetrack_entry["delta_total_cpu_s"] == pytest.approx(5.0)
    assert bytetrack_entry["delta_peak_rss_kib"] == 1000


def test_comparative_overhead_is_none_when_one_side_missing() -> None:
    module = load_module()

    rows_by_id = {
        "sort_raw": {"replay": {"combined_total_cpu_s": None, "combined_peak_rss_kib": None}},
        "sort_tim": {"replay": {"combined_total_cpu_s": None, "combined_peak_rss_kib": None}},
    }

    overhead = module.comparative_overhead(rows_by_id)
    sort_entry = next(entry for entry in overhead if entry["tracker_type"] == "sort")

    assert sort_entry["delta_total_cpu_s"] is None
    assert sort_entry["delta_peak_rss_kib"] is None


def _write_minimal_manifest(path: Path) -> None:
    manifest = {
        "architectures": [
            {"id": arch_id, "tracker_type": arch_id.split("_")[0], "tim_enabled": arch_id.endswith("_tim")}
            for arch_id in EXPECTED_ARCHITECTURE_IDS
        ],
        "issue_58_join": {
            "join_keys": ["architecture_id", "sequence_id"],
            "architecture_id_values": EXPECTED_ARCHITECTURE_IDS,
            "sequence_id_values": EXPECTED_SEQUENCE_IDS,
        },
        "power": {"status": "unavailable_no_calibrated_sensor"},
    }
    path.write_text(yaml.safe_dump(manifest))


def test_issue_58_join_schema_matches_frozen_identifiers(tmp_path: Path) -> None:
    """The join contract is only useful if the identifiers never silently
    drift from Issue #58's own naming. This pins the exact expected set."""
    module = load_module()

    manifest_path = tmp_path / "manifest.yaml"
    _write_minimal_manifest(manifest_path)
    manifest = module.load_manifest(manifest_path)

    assert (
        manifest["issue_58_join"]["architecture_id_values"]
        == EXPECTED_ARCHITECTURE_IDS
    )
    assert (
        manifest["issue_58_join"]["sequence_id_values"] == EXPECTED_SEQUENCE_IDS
    )


def test_main_produces_deterministic_row_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()

    manifest_path = tmp_path / "manifest.yaml"
    _write_minimal_manifest(manifest_path)

    replay_root = tmp_path / "replay"
    replay_root.mkdir()

    json_out = tmp_path / "aggregate.json"
    csv_out = tmp_path / "aggregate.csv"
    markdown_out = tmp_path / "aggregate.md"

    argv = [
        "aggregate_p032_runtime_report.py",
        "--manifest",
        str(manifest_path),
        "--sequence-id",
        "dev_may_hard_reentry",
        "--replay-root",
        str(replay_root),
        "--json-out",
        str(json_out),
        "--csv-out",
        str(csv_out),
        "--markdown-out",
        str(markdown_out),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    exit_code = module.main()
    assert exit_code == 0

    output = json.loads(json_out.read_text())
    row_ids = [row["architecture_id"] for row in output["rows"]]
    assert row_ids == EXPECTED_ARCHITECTURE_IDS

    # All rows report "missing" replay evidence (no fixtures were staged)
    # rather than a fabricated zero-cost measurement.
    assert all(row["replay"]["status"] == "missing" for row in output["rows"])

    with csv_out.open(newline="", encoding="utf-8") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert [row["architecture_id"] for row in csv_rows] == EXPECTED_ARCHITECTURE_IDS

    assert markdown_out.is_file()
