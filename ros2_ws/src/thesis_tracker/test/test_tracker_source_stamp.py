"""Tests for causal source-stamp propagation through the tracker."""

from types import SimpleNamespace

from thesis_tracker.nodes.tracker_node import _resolve_source_stamp_ns


def header(sec: int, nanosec: int):
    return SimpleNamespace(
        stamp=SimpleNamespace(sec=sec, nanosec=nanosec)
    )


def test_timing_context_source_stamp_has_priority():
    assert _resolve_source_stamp_ns(123, header(4, 5)) == 123


def test_detection_header_is_causal_fallback_when_timing_arrives_late():
    assert _resolve_source_stamp_ns(0, header(4, 5)) == 4_000_000_005


def test_invalid_context_and_header_fail_closed():
    assert _resolve_source_stamp_ns(0, SimpleNamespace()) == 0
