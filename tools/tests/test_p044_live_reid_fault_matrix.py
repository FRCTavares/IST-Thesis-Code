"""Static contracts for the P044 live ReID fault matrix runner."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (
    ROOT
    / "tools"
    / "experiments"
    / "run_p044_live_reid_fault_matrix.sh"
)
COLLECTOR = (
    ROOT
    / "tools"
    / "experiments"
    / "collect_p044_transport_evidence.py"
)


def source() -> str:
    return RUNNER.read_text(
        encoding="utf-8"
    )


def test_runner_avoids_fail_fast_shell_mode():
    text = source()

    assert "set -e" not in text
    assert "set +e" in text
    assert "set +u" in text
    assert "set -o pipefail" in text


def test_runner_defines_exact_fault_conditions():
    text = source()

    required = (
        "pass_through)",
        "suppressed_result)",
        "backend_failure)",
        "delayed_result)",
        '"none"',
        '"suppress_result"',
        '"backend_failure"',
        '"delay_result"',
    )

    for fragment in required:
        assert fragment in text


def test_runner_holds_request_policy_and_interval_constant():
    text = source()

    assert (
        'APPEARANCE_POLICY="ambiguity_guarded"'
        in text
    )
    assert 'INTERVAL_MS="250.0"' in text
    assert 'DEADLINE_MS="500.0"' in text
    assert 'DELAY_MS="1000.0"' in text

    assert (
        "-p appearance_request_policy:"
        '="$APPEARANCE_POLICY"'
        in text
    )
    assert (
        "-p appearance_compute_min_interval_ms:"
        '="$INTERVAL_MS"'
        in text
    )


def test_runner_inserts_relay_between_raw_and_final_topics():
    text = source()

    assert (
        'RAW_RESULT_TOPIC="/appearance/reid/result_raw"'
        in text
    )
    assert (
        'RESULT_TOPIC="/appearance/reid/result"'
        in text
    )
    assert (
        '-p reid_result_topic:="$RAW_RESULT_TOPIC"'
        in text
    )
    assert (
        "--input-topic "
        '"$RAW_RESULT_TOPIC"'
        in text
    )
    assert (
        "--output-topic "
        '"$RESULT_TOPIC"'
        in text
    )
    assert (
        "-p appearance_async_reid_result_topic:"
        '="$RESULT_TOPIC"'
        in text
    )


def test_runner_records_raw_final_and_relay_status_topics():
    text = source()

    required = (
        '"$REQUEST_TOPIC"',
        '"$RAW_RESULT_TOPIC"',
        '"$RESULT_TOPIC"',
        '"$RELAY_STATUS_TOPIC"',
        "/perception/reid/status",
        "/target_memory_mars/status",
    )

    for fragment in required:
        assert fragment in text


def test_runner_validates_condition_specific_fail_closed_results():
    text = source()

    required = (
        "suppressed-result TIM accounting is invalid",
        "backend failure was accepted",
        "TIM did not report backend_failure",
        "delayed-result TIM accounting is invalid",
        "TIM did not reject delayed results as unknown",
        "TIM ledger did not drain",
        "relay delayed queue did not drain",
        "real Hailo executor reported a backend failure",
    )

    for fragment in required:
        assert fragment in text


def test_runner_uses_isolated_process_groups_and_cleanup():
    text = source()

    required = (
        "setsid",
        "register_process",
        "stop_process_group",
        "cleanup_registered",
        "cleanup_unmatched",
        "p044_reid_fault_relay.py",
        "sample_process_groups.py",
    )

    for fragment in required:
        assert fragment in text


def test_runner_rotates_all_four_conditions():
    text = source()

    expected_orders = (
        "pass_through suppressed_result backend_failure delayed_result",
        "suppressed_result backend_failure delayed_result pass_through",
        "backend_failure delayed_result pass_through suppressed_result",
        "delayed_result pass_through suppressed_result backend_failure",
    )

    for order in expected_orders:
        assert order in text


def test_runner_writes_versioned_machine_readable_evidence():
    text = source()

    required = (
        "p044_live_reid_fault_matrix_v1",
        "p044_live_reid_fault_run_v1",
        "p044_live_reid_fault_comparison_v1",
        "fault_matrix_summary.json",
        '"cpu_mars_authoritative": True',
        '"repvgg_observational": True',
        '"canonical_policy_changed": False',
    )

    for fragment in required:
        assert fragment in text


def test_collector_accepts_fault_matrix_labels():
    text = COLLECTOR.read_text(
        encoding="utf-8"
    )

    required = (
        '"pass_through"',
        '"suppressed_result"',
        '"backend_failure"',
        '"delayed_result"',
    )

    for fragment in required:
        assert fragment in text
