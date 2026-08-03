"""Contracts for the guarded Issue #44 Hailo load matrix."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_p044_guarded_hailo_load_matrix.sh"
)

ACCEPTED_RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_p044_hailo_reid_load_matrix.sh"
)

COLLECTOR = (
    ROOT
    / "tools"
    / "experiments"
    / "collect_p044_transport_evidence.py"
)


def source() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_has_valid_shell_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_runner_defines_exact_guarded_conditions() -> None:
    text = source()

    required = (
        "reference)",
        "all_candidates_hailo)",
        "ambiguity_guarded_hailo)",
        'order="reference all_candidates_hailo '
        'ambiguity_guarded_hailo"',
        'order="all_candidates_hailo '
        'ambiguity_guarded_hailo reference"',
        'order="ambiguity_guarded_hailo reference '
        'all_candidates_hailo"',
    )

    for token in required:
        assert token in text, token


def test_all_conditions_use_the_250_ms_interval() -> None:
    text = source()

    start = text.index("condition_settings()")
    end = text.index('section "1. Preflight"')
    settings = text[start:end]

    assert settings.count('"250.0"') == 3
    assert '"0.0"' not in settings

    assert (
        '"appearance_compute_min_interval_ms": 0.0'
        not in text
    )


def test_policy_mapping_is_explicit_and_condition_specific() -> None:
    text = source()

    required = (
        '"all_candidates_hailo": {',
        '"ambiguity_guarded_hailo": {',
        '"appearance_request_policy": "all_candidates"',
        (
            '"appearance_request_policy": '
            '"ambiguity_guarded"'
        ),
        'appearance_policy <<< "$settings"',
        (
            '-p appearance_request_policy:='
            '"$appearance_policy"'
        ),
        (
            '"appearance_request_policy": '
            '"$appearance_policy"'
        ),
    )

    for token in required:
        assert token in text, token


def test_runner_preserves_cpu_authority_and_claim_boundary() -> None:
    text = source()

    required = (
        '"cpu_mars_authoritative": true',
        '"repvgg_ranking_enabled": false',
        '"repvgg_memory_enabled": false',
        (
            '"repvgg_decision_integration_enabled": '
            "false"
        ),
        '"ambiguity_guarded_used": True',
        '"canonical_policy_changed": False',
    )

    for token in required:
        assert token in text, token


def test_runner_reuses_resource_and_transport_evidence() -> None:
    text = source()

    required = (
        "collect_p044_transport_evidence.py",
        "sample_process_groups.py",
        "/appearance/reid/request",
        "/appearance/reid/result",
        "/perception/reid/status",
        "/target_memory_mars/status",
        "maximum_executor_queued",
        "maximum_engine_active_calls",
        "request_delivery_percent",
        "result_delivery_percent",
        "detector_infer_mean_delta_ms",
        "tim_cpu_mean_delta_percent",
        "perception_cpu_mean_delta_percent",
    )

    for token in required:
        assert token in text, token


def test_runner_has_new_versioned_evidence_schemas() -> None:
    text = source()

    required = (
        "p044_guarded_hailo_load_matrix_v1",
        "p044_guarded_hailo_load_run_v1",
        "p044_guarded_hailo_load_comparison_v1",
        "all_candidates_hailo_vs_reference",
        "ambiguity_guarded_hailo_vs_reference",
        (
            "ambiguity_guarded_hailo_vs_"
            "all_candidates_hailo"
        ),
    )

    for token in required:
        assert token in text, token


def test_runner_does_not_use_forbidden_shell_mode() -> None:
    text = source()

    assert "set -e" not in text
    assert "set +e" in text
    assert "set +u" in text
    assert (
        'HAILORT_LOGGER_PATH="$THESIS_ROOT/'
        'ros2_ws/log/hailort"'
        in text
    )


def test_collector_accepts_guarded_condition_labels() -> None:
    text = COLLECTOR.read_text(encoding="utf-8")

    assert '"all_candidates_hailo"' in text
    assert '"ambiguity_guarded_hailo"' in text


def test_accepted_load_runner_remains_separate() -> None:
    assert ACCEPTED_RUNNER.is_file()
    assert RUNNER.is_file()
    assert RUNNER != ACCEPTED_RUNNER
