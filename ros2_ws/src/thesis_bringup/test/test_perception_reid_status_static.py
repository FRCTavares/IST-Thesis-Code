"""Static contracts for perception ReID executor status publication."""

from pathlib import Path


NODE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "perception"
    / "perception_pipeline_node.py"
)


def source() -> str:
    """Read the perception node source."""
    return NODE.read_text(encoding="utf-8")


def test_status_parameters_have_stable_defaults():
    """Expose a stable evidence topic without enabling ReID."""
    text = source()

    assert '"reid_status_topic"' in text
    assert '"/perception/reid/status"' in text
    assert '"reid_status_period_s"' in text
    assert "0.5," in text


def test_status_publisher_exists_in_reference_and_treatment():
    """Publish diagnostics even when the ReID service is disabled."""
    text = source()

    service_index = text.index(
        "self._setup_reid_service()"
    )
    status_index = text.index(
        "self._setup_reid_status_publisher()"
    )

    assert service_index < status_index
    assert (
        "def _setup_reid_status_publisher("
        in text
    )
    assert "self.create_timer(" in text


def test_status_uses_executor_diagnostics_snapshot():
    """Expose bounded queue and execution accounting."""
    text = source()

    assert "diagnostics = executor.diagnostics()" in text

    required = (
        '"accepting"',
        '"queued"',
        '"in_flight_request_id"',
        '"maximum_queued"',
        '"submitted"',
        '"executed"',
        '"succeeded"',
        '"failed"',
        '"rejected"',
        '"emitted_results"',
        '"reasons"',
    )

    for fragment in required:
        assert fragment in text


def test_status_exposes_shared_engine_contention_state():
    """Expose whether detector or ReID currently owns the engine."""
    text = source()

    assert "with self._engine_lock:" in text
    assert '"engine_active_calls"' in text
    assert "self._engine_active_calls" in text


def test_status_schema_is_machine_readable_and_versioned():
    """Provide compact deterministic JSON for evidence extraction."""
    text = source()

    assert (
        '"perception_reid_executor_status_v1"'
        in text
    )
    assert '"timestamp_ns"' in text
    assert '"enabled"' in text
    assert '"active_backend"' in text
    assert '"malformed_requests"' in text
    assert "json.dumps(" in text
    assert "sort_keys=True" in text
    assert 'separators=(",", ":")' in text


def test_status_does_not_change_reid_activation_default():
    """Keep the Hailo ReID endpoint disabled by default."""
    text = source()

    declaration = (
        'self.declare_parameter("reid_enabled", False)'
    )

    assert declaration in text
