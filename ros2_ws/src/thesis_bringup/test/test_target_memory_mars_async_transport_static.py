"""Static contracts for TIM causal RepVGG ROS transport wiring."""

from pathlib import Path


NODE = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "tim_mars"
    / "target_memory_mars_node.py"
)

PARAMS = (
    Path(__file__).resolve().parents[1]
    / "thesis_bringup"
    / "tim_mars"
    / "ros_params.py"
)


def test_transport_is_disabled_by_default():
    """Keep the canonical CPU path unchanged unless explicitly enabled."""
    source = PARAMS.read_text(
        encoding="utf-8"
    )

    assert (
        '"appearance_async_reid_enabled",\n'
        "        False,"
        in source
    )
    assert (
        '"/appearance/reid/request"'
        in source
    )
    assert (
        '"/appearance/reid/result"'
        in source
    )


def test_node_uses_matching_volatile_best_effort_qos():
    """Match the perception-side request and result transport contract."""
    source = NODE.read_text(
        encoding="utf-8"
    )

    assert (
        "ReliabilityPolicy.BEST_EFFORT"
        in source
    )
    assert (
        "DurabilityPolicy.VOLATILE"
        in source
    )
    assert (
        "AppearanceEmbeddingRequest"
        in source
    )
    assert (
        "AppearanceEmbeddingResult"
        in source
    )


def test_request_is_admitted_before_publication():
    """Record each request in the ledger before publishing it."""
    source = NODE.read_text(
        encoding="utf-8"
    )

    stage_index = source.index(
        "batch = transport.stage("
    )
    publish_index = source.index(
        "publisher.publish("
    )

    assert stage_index < publish_index
    assert "request_to_ros_message(request)" in source


def test_result_passes_through_current_lifecycle_gate():
    """Use authoritative current frame and track generations."""
    source = NODE.read_text(
        encoding="utf-8"
    )

    required = (
        "result_from_ros_message(",
        "transport.complete(",
        ".appearance_state",
        ".frame_generation",
        ".track_generation_by_id",
        "current_frame_generation=",
        "current_track_generations=",
    )

    for fragment in required:
        assert fragment in source


def test_lifecycle_resets_cancel_transport():
    """Reject late results after selection, clear, reset, or shutdown."""
    source = NODE.read_text(
        encoding="utf-8"
    )

    required_reasons = (
        "mirrored_target_selection",
        "operator_select_clear",
        "operator_selection",
        "operator_clear",
        "source_frame_generation_change",
        "node_shutdown",
    )

    for reason in required_reasons:
        assert reason in source

    assert "def destroy_node(self):" in source
    assert "self._cancel_async_reid(" in source


def test_status_exposes_transport_diagnostics_only_when_enabled():
    """Expose transport accounting without changing CPU MARS decisions."""
    source = NODE.read_text(
        encoding="utf-8"
    )

    required = (
        '"appearance_async_reid"',
        '"constructed"',
        '"published"',
        '"in_flight"',
        '"accepted_results"',
        '"drop_reasons"',
        '"result_reasons"',
        "last_accepted_request_id",
        "last_accepted_track_id",
    )

    for fragment in required:
        assert fragment in source
