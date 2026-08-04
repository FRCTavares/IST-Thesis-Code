"""Contracts for the Issue #44 paired Hailo ReID evidence tools."""

from pathlib import Path
from types import SimpleNamespace
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

def test_collector_reads_flat_request_crop_fields():
    """Match the generated AppearanceEmbeddingRequest schema."""
    module = load_collector_module()
    accumulator = module.EvidenceAccumulator(
        condition="treatment"
    )

    message = SimpleNamespace(
        request_id=17,
        submitted_ns=1_000,
        deadline_ns=501_000,
        source_frame_id=42,
        source_image_timestamp_ns=900,
        source_image_seq=12,
        frame_generation=3,
        candidate_index=1,
        track_id=7,
        track_generation=5,
        backend_name="repvgg-a0-person-reid",
        embedding_space="repvgg-a0-person-reid-512",
        backend_dimension=512,
        crop_height=80,
        crop_width=40,
    )

    event = accumulator.add_request(message)

    assert event["request_id"] == 17
    assert event["crop_height"] == 80
    assert event["crop_width"] == 40
    assert accumulator.request_count == 1
    assert (
        accumulator.requests_by_id[17][
            "submitted_ns"
        ]
        == 1_000
    )


def test_collector_has_no_nested_crop_message_access():
    """Prevent regression to a nonexistent nested crop message."""
    source = COLLECTOR.read_text(
        encoding="utf-8"
    )

    assert "message.crop." not in source
    assert "message.crop_height" in source
    assert "message.crop_width" in source

def test_runner_launches_background_jobs_in_new_sessions():
    """Make each recorded PID the process-group identifier."""
    source = RUNNER.read_text(encoding="utf-8")

    required = (
        'setsid "$THESIS_ROOT/thesis_env/bin/python"',
        "setsid env",
        "ros2 run thesis_bringup perception_pipeline_node",
        "setsid ros2 run thesis_bringup target_memory_mars_node",
        "setsid ros2 bag record",
        "setsid pidstat",
        'setsid ros2 bag play "$BAG_PATH"',
    )

    for fragment in required:
        assert fragment in source

    assert (
        source.index("setsid env")
        < source.index(
            "ros2 run thesis_bringup "
            "perception_pipeline_node"
        )
    )
    assert "command -v setsid" in source


def test_runner_stops_complete_process_groups():
    """Signal wrappers and their spawned ROS executables together."""
    source = RUNNER.read_text(encoding="utf-8")

    assert "def process_group_alive" not in source
    assert "process_group_alive()" in source
    assert 'kill -0 -- "-$group_id"' in source
    assert 'kill -INT -- "-$pid"' in source
    assert 'kill -TERM -- "-$pid"' in source
    assert 'kill -KILL -- "-$pid"' in source
    assert "cleanup_status=$?" in source
    assert "condition cleanup failed" in source


def test_runner_has_fallback_process_cleanup_and_verification():
    """Detect children that escaped an expected process group."""
    source = RUNNER.read_text(encoding="utf-8")

    assert "matching_smoke_pids()" in source
    assert "stop_matching_smoke_processes()" in source
    assert "unmatched smoke processes remain" in source
    assert (
        "trap 'cleanup_all >/dev/null 2>&1 || true'"
        in source
    )

def test_collector_accepts_load_matrix_condition_labels():
    """Preserve pair labels and accept both load conditions."""
    module = load_collector_module()

    assert module.CONDITION_CHOICES == (
        "reference",
        "treatment",
        "selective",
        "forced_frequent",
        "all_candidates_hailo",
        "ambiguity_guarded_hailo",
        "pass_through",
        "suppressed_result",
        "backend_failure",
        "delayed_result",
    )


def test_collector_handles_external_shutdown_idempotently():
    """Avoid a traceback when ROS has already shut down."""
    source = COLLECTOR.read_text(
        encoding="utf-8"
    )

    assert (
        "ExternalShutdownException"
        in source
    )
    assert (
        "except (KeyboardInterrupt, "
        "ExternalShutdownException):"
        in source
    )
    assert "if rclpy.ok():" in source
