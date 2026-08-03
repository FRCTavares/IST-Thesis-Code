from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    REPO_ROOT
    / "tools"
    / "experiments"
    / "run_p044_guarded_cpu_policy_matrix.sh"
)


def runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_guarded_matrix_runner_has_valid_shell_syntax():
    result = subprocess.run(
        ["bash", "-n", str(RUNNER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_guarded_matrix_runner_defines_only_accepted_conditions():
    text = runner_text()

    assert '"all_candidates"' in text
    assert '"ambiguity_guarded"' in text
    assert 'TIM_APPEARANCE_COMPUTE_MIN_INTERVAL_MS="250"' in text

    assert "geometry_winner_250ms" not in text
    assert "all_candidates_0ms" not in text
    assert "ambiguity_guarded_0ms" not in text


def test_guarded_matrix_runner_uses_exact_four_sequences():
    text = runner_text()

    required = (
        "may_hard_reentry",
        "seq01_clean",
        "seq03_crossing",
        "seq04_occlusion",
        "bytetrack_hard_reentry.csv",
        "seq01_bytetrack.csv",
        "seq03_ocsort_305578f3.csv",
        "seq04_ocsort_305578f3.csv",
        "p006b_hard_negative_03409564_2026_07_21/seq03",
        "p006b_hard_negative_03409564_2026_07_21/seq04",
    )

    for token in required:
        assert token in text, token


def test_guarded_matrix_runner_preserves_authoritative_cpu_boundary():
    text = runner_text()

    required = (
        'RAW_TARGET_MODE="source"',
        'TIM_MIRROR_RAW_TARGET_SELECTION="false"',
        'MARS_MODEL_PATH="$MARS_MODEL"',
        '"cpu_mars_authoritative": True',
        '"repvgg_ranking_enabled": False',
        '"repvgg_memory_enabled": False',
        '"repvgg_decision_integration_enabled": False',
        '"canonical_policy_changed": False',
    )

    for token in required:
        assert token in text, token


def test_guarded_matrix_runner_avoids_forbidden_shell_mode_and_root_logs():
    text = runner_text()

    assert "set -e" not in text
    assert 'COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"' in text
    assert 'HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"' in text
    assert "[ -e log ]" in text
    assert "[ -e hailort.log ]" in text


def test_guarded_matrix_runner_records_complete_execution_provenance():
    text = runner_text()

    required = (
        "run_manifest.json",
        "run_status.tsv",
        "execution_summary.json",
        "expected_runs",
        "observed_runs",
        "successful_runs",
        "git_head",
        "canonical_config",
        "appearance_request_policy",
        "appearance_compute_min_interval_ms",
    )

    for token in required:
        assert token in text, token
