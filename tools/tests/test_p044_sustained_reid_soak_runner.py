from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "tools/experiments/run_p044_sustained_reid_soak.sh"
)
ANALYSER = (
    ROOT
    / "tools/experiments/analyze_p044_sustained_soak.py"
)


def test_runner_preserves_experiment_boundary() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    required = (
        'APPEARANCE_POLICY="ambiguity_guarded"',
        'INTERVAL_MS="250.0"',
        'DEADLINE_MS="500.0"',
        '"cpu_mars_authoritative": true',
        '"repvgg_observational": true',
        '"canonical_policy_changed": false',
        '"production_nodes_modified": false',
    )

    for fragment in required:
        assert fragment in text


def test_runner_uses_timestamp_continuous_loop_path() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    required = (
        "--loop",
        "timeout",
        "--foreground",
        "--signal=TERM",
        "--kill-after=15s",
        "/camera/image_raw:=$SOURCE_IMAGE_TOPIC",
        "/tracks:=$SOURCE_TRACKS_TOPIC",
        "p044_soak_input_relay.py",
        "--condition sustained_soak",
        'playback_end_reason="duration_watchdog"',
    )

    for fragment in required:
        assert fragment in text

    executable_text = "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "--playback-duration" not in executable_text


def test_runner_collects_sustained_health_and_resources() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    required = (
        "sample_process_groups.py",
        "sample_p044_hardware_health.py",
        'DURATION_S="${5:-180.0}"',
        "--group \"perception=$perception_pgid\"",
        "--group \"tim=$tim_pgid\"",
        "--group \"relay=$relay_pgid\"",
        "analyze_p044_sustained_soak.py",
    )

    for fragment in required:
        assert fragment in text


def test_runner_avoids_forbidden_shell_exit_mode() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert "set -e" not in text
    assert "set +e" in text
    assert "set +u" in text


def test_analyser_declares_limited_claim_boundary() -> None:
    text = ANALYSER.read_text(encoding="utf-8")

    required = (
        '"cross_sequence_generality_proven": False',
        '"authoritative_repvgg_safety_proven": False',
        '"repvgg_ranking_enabled": False',
        '"repvgg_memory_enabled": False',
        '"repvgg_decision_integration_enabled": False',
    )

    for fragment in required:
        assert fragment in text


def test_runner_normalizes_no_match_log_scan_status() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    required = (
        "log_scan_raw_status=$?",
        'if [ "$log_scan_raw_status" -eq 0 ]',
        'elif [ "$log_scan_raw_status" -eq 1 ]',
        "log_scan_status=1",
        "log_scan_status=0",
        "log_scan_raw_status:%s",
        "log_scan_status:    %s",
    )

    for fragment in required:
        assert fragment in text
