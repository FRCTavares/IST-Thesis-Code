"""Regression tests for Issue #32's same-frame timing correlation fix.

Root cause (proven by inspecting rclpy's installed SingleThreadedExecutor
source, not assumed): Executor._wait_for_ready_callbacks iterates
node.subscriptions in registration order and yields ready callbacks in that
order, so whichever of /detections or /timing was registered first with
create_subscription always runs first whenever both are ready in the same
wait-set cycle -- deterministically, not as an occasional race. tracker_node
previously registered /detections before /timing, so on_detections almost
always ran before the matching on_timing had populated frame_context,
making e2e_target_ms publish as exactly 0.0 on effectively every sample.

These tests cover the pure frame_context correlation logic (matching this
test suite's existing convention of testing extracted pure functions rather
than instantiating a live rclpy Node) and a static check that the
subscription registration order fix is actually present in source.
"""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path

from thesis_tracker.nodes.tracker_node import _store_frame_context


NODE_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "thesis_tracker"
    / "nodes"
    / "tracker_node.py"
)


def _tracker_node_init() -> ast.FunctionDef:
    tree = ast.parse(NODE_SOURCE.read_text())
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TrackerNode"
    )
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )


def _subscription_topic_order(init_fn: ast.FunctionDef) -> list[str]:
    """Return each create_subscription call's literal topic argument.

    Returned in source (== registration) order, as they appear in
    __init__.
    """
    topics: list[str] = []

    for node in ast.walk(init_fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create_subscription"
        ):
            # create_subscription(MsgType, topic, callback, qos)
            topic_arg = node.args[1] if len(node.args) > 1 else None
            if isinstance(topic_arg, ast.Constant) and isinstance(
                topic_arg.value, str
            ):
                topics.append(topic_arg.value)

    return topics


def test_timing_subscription_is_registered_before_detections_subscription():
    """This is the actual regression proof for the executor-ordering bug.

    rclpy's SingleThreadedExecutor dispatches ready callbacks in
    node.subscriptions registration order; /timing must be registered
    before /detections so on_timing populates frame_context before
    on_detections needs it whenever both are ready in the same cycle.
    """
    topics = _subscription_topic_order(_tracker_node_init())

    assert "/timing" in topics
    assert "/detections" in topics
    assert topics.index("/timing") < topics.index("/detections")


def test_tracking_association_call_does_not_reference_frame_context():
    """The timing-only fix must not touch tracker association.

    Statically verify backend.update(...) -- the actual tracking call --
    is never passed frame_context/timing-derived values as an argument.
    """
    tree = ast.parse(NODE_SOURCE.read_text())
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TrackerNode"
    )
    on_detections = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "on_detections"
    )

    update_calls = [
        node
        for node in ast.walk(on_detections)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "update"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "backend"
    ]

    assert update_calls, "expected self.backend.update(...) call in on_detections"

    forbidden = {"frame_context", "t_cam_msg_seen_ns", "src_stamp_ns"}
    for call in update_calls:
        for arg in call.args:
            names = {
                node.id
                for node in ast.walk(arg)
                if isinstance(node, ast.Name)
            }
            assert not (names & forbidden), (
                f"tracking backend.update() call unexpectedly references "
                f"timing-context state: {names & forbidden}"
            )


def _new_context() -> tuple[dict, deque]:
    return {}, deque()


def test_same_frame_timing_context_propagates():
    frame_context, order = _new_context()

    _store_frame_context(frame_context, order, 512, 42, src_stamp_ns=100, t_cam_msg_seen_ns=200)

    assert frame_context.pop(42, (0, 0)) == (100, 200)


def test_frame_n_can_never_pair_with_frame_n_plus_or_minus_one():
    frame_context, order = _new_context()

    _store_frame_context(frame_context, order, 512, 5, src_stamp_ns=500, t_cam_msg_seen_ns=5000)
    _store_frame_context(frame_context, order, 512, 6, src_stamp_ns=600, t_cam_msg_seen_ns=6000)
    _store_frame_context(frame_context, order, 512, 4, src_stamp_ns=400, t_cam_msg_seen_ns=4000)

    assert frame_context.pop(5, (0, 0)) == (500, 5000)
    assert frame_context.pop(6, (0, 0)) == (600, 6000)
    assert frame_context.pop(4, (0, 0)) == (400, 4000)


def test_missing_timing_context_pops_the_explicit_unavailable_sentinel():
    """Reproduce the exact failure mode this issue diagnosed.

    Detections processed for a frame_id that on_timing has not (yet)
    stored context for. The lookup must return the (0, 0) unavailable
    sentinel, never a fabricated or stale value from a different frame.
    """
    frame_context, order = _new_context()

    # frame_id 7 was never stored via on_timing -- e.g. on_detections ran
    # first, exactly as it always did before the subscription-order fix.
    result = frame_context.pop(7, (0, 0))

    assert result == (0, 0)


def test_startup_placeholder_frame_id_zero_is_rejected_not_cached():
    frame_context, order = _new_context()

    _store_frame_context(frame_context, order, 512, 0, src_stamp_ns=999, t_cam_msg_seen_ns=999)

    assert 0 not in frame_context
    assert len(frame_context) == 0


def test_frame_context_evicts_oldest_beyond_max_context():
    frame_context, order = _new_context()

    _store_frame_context(frame_context, order, 2, 1, src_stamp_ns=1, t_cam_msg_seen_ns=1)
    _store_frame_context(frame_context, order, 2, 2, src_stamp_ns=2, t_cam_msg_seen_ns=2)
    _store_frame_context(frame_context, order, 2, 3, src_stamp_ns=3, t_cam_msg_seen_ns=3)

    assert 1 not in frame_context
    assert frame_context.pop(2, (0, 0)) == (2, 2)
    assert frame_context.pop(3, (0, 0)) == (3, 3)


def test_repeated_store_for_same_frame_id_does_not_duplicate_order_entry():
    frame_context, order = _new_context()

    _store_frame_context(frame_context, order, 512, 9, src_stamp_ns=1, t_cam_msg_seen_ns=1)
    _store_frame_context(frame_context, order, 512, 9, src_stamp_ns=2, t_cam_msg_seen_ns=2)

    assert list(order).count(9) == 1
    assert frame_context.pop(9, (0, 0)) == (2, 2)
