"""Regression tests for Issue #32's e2e_target_ms correlation fix.

dashboard_bridge_node._compute_e2e_target_ms is the sole publisher of
/timing_target's e2e_target_ms. Before the fix, tracker_node's
frame_context correlation miss (see test_tracker_timing_correlation.py)
meant the incoming /tracks message's t_cam_msg_seen_ns was always 0, so
this computation was always skipped and the field always published at its
schema default 0.0 -- indistinguishable from a genuine sub-millisecond
measurement. This function must never be given a reason to fabricate a
positive value from invalid input, and must return None (not 0.0) exactly
when the input is invalid.
"""

from __future__ import annotations

from thesis_bringup.dashboard.dashboard_bridge_node import (
    _compute_e2e_target_ms,
)


def test_valid_same_frame_timestamps_yield_a_genuine_positive_latency():
    # t_cam_msg_seen_ns and t_target_cb_end_ns are both host-monotonic ns.
    t_cam_msg_seen_ns = 1_000_000_000
    t_target_cb_end_ns = 1_000_000_000 + 50_000_000  # 50 ms later

    result = _compute_e2e_target_ms(t_cam_msg_seen_ns, t_target_cb_end_ns)

    assert result == 50.0


def test_missing_timing_context_returns_none_not_zero():
    """Missing timing context must never be reported as a real latency.

    The frame_context correlation-miss sentinel (0) must never be
    silently treated as a valid zero-latency measurement.
    """
    assert _compute_e2e_target_ms(0, 1_000_000_000) is None


def test_negative_or_zero_t_cam_msg_seen_ns_returns_none():
    assert _compute_e2e_target_ms(-1, 1_000_000_000) is None


def test_implausible_stale_frame_pairing_returns_none():
    """An impossible same-frame pairing must not report a measurement.

    t_target_cb_end_ns earlier than t_cam_msg_seen_ns would mean the
    target callback finished before the frame it claims to belong to was
    even seen.
    """
    t_cam_msg_seen_ns = 2_000_000_000
    t_target_cb_end_ns = 1_000_000_000  # earlier than the frame

    assert _compute_e2e_target_ms(t_cam_msg_seen_ns, t_target_cb_end_ns) is None


def test_result_is_never_negative_when_not_none():
    result = _compute_e2e_target_ms(1_000_000_000, 1_000_000_000)

    assert result is not None
    assert result >= 0.0


def test_result_has_millisecond_scale_from_nanoseconds():
    result = _compute_e2e_target_ms(0 + 1, 1_000_000 + 1)

    assert result is not None
    assert result == 1.0
