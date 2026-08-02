from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_p044_hailo_reid_load_matrix.sh"
)


def source() -> str:
    return RUNNER.read_text(
        encoding="utf-8"
    )


def test_runner_defines_exact_controlled_conditions() -> None:
    text = source()

    assert "reference)" in text
    assert "selective)" in text
    assert "forced_frequent)" in text

    assert text.count(
        '"appearance_request_policy": "all_candidates"'
    ) >= 3

    assert (
        '"appearance_compute_min_interval_ms": 250.0'
        in text
    )
    assert (
        '"appearance_compute_min_interval_ms": 0.0'
        in text
    )

    assert (
        "-p appearance_request_policy:=geometry_winner"
        not in text
    )
    assert (
        '"appearance_request_policy": "geometry_winner"'
        not in text
    )


def test_runner_changes_only_interval_between_reid_conditions() -> None:
    text = source()

    assert (
        'selective)\n'
        '      printf \'%s %s %s\\n\' \\\n'
        '        "true" \\\n'
        '        "true" \\\n'
        '        "250.0"'
        in text
    )
    assert (
        'forced_frequent)\n'
        '      printf \'%s %s %s\\n\' \\\n'
        '        "true" \\\n'
        '        "true" \\\n'
        '        "0.0"'
        in text
    )


def test_runner_samples_complete_process_groups() -> None:
    text = source()

    assert "sample_process_groups.py" in text
    assert (
        '--group "perception=$perception_pgid"'
        in text
    )
    assert (
        '--group "tim=$tim_pgid"'
        in text
    )
    assert "resolve_pgid" in text

    assert (
        "perception_pipeline_node"
        in text
    )
    assert (
        "target_memory_mars_node"
        in text
    )


def test_runner_rotates_condition_order() -> None:
    text = source()

    assert (
        'order="reference selective forced_frequent"'
        in text
    )
    assert (
        'order="selective forced_frequent reference"'
        in text
    )
    assert (
        'order="forced_frequent reference selective"'
        in text
    )


def test_runner_builds_resource_and_latency_comparison() -> None:
    text = source()

    assert "load_comparison.json" in text
    assert "selective_vs_reference" in text
    assert "forced_frequent_vs_reference" in text
    assert "forced_frequent_vs_selective" in text
    assert "perception_cpu_mean_delta_percent" in text
    assert "tim_cpu_mean_delta_percent" in text
    assert "detector_infer_mean_delta_ms" in text
    assert "detector_infer_p95_delta_ms" in text


def test_accepted_pair_runner_is_not_replaced() -> None:
    pair_runner = (
        ROOT
        / "tools"
        / "experiments"
        / "run_p044_hailo_reid_pair.sh"
    )

    assert pair_runner.is_file()
    assert RUNNER != pair_runner
