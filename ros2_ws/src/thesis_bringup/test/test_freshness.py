"""Tests for the shared live/offline freshness contract."""

import pytest

from thesis_bringup.freshness import classify_freshness


NOW_NS = 10_000_000_000


def classify(
    source_age_s: float,
    *,
    receive_age_s: float | None = 0.01,
    previous_source_stamp_ns: int | None = None,
    reject_duplicate: bool = False,
):
    receive_stamp_ns = None
    if receive_age_s is not None:
        receive_stamp_ns = NOW_NS - int(receive_age_s * 1e9)
    return classify_freshness(
        now_ns=NOW_NS,
        source_stamp_ns=NOW_NS - int(source_age_s * 1e9),
        receive_stamp_ns=receive_stamp_ns,
        max_age_s=0.20,
        future_tolerance_s=0.05,
        previous_source_stamp_ns=previous_source_stamp_ns,
        reject_duplicate=reject_duplicate,
    )


def test_freshness_boundary_is_inclusive():
    result = classify(0.20, receive_age_s=0.20)

    assert result.fresh is True
    assert result.status == "fresh"
    assert result.source_age_s == pytest.approx(0.20)
    assert result.receive_age_s == pytest.approx(0.20)


@pytest.mark.parametrize(
    ("source_age_s", "receive_age_s", "status"),
    [
        (0.201, 0.01, "stale_source"),
        (0.01, 0.201, "stale_receive"),
        (-0.051, 0.01, "future_source"),
    ],
)
def test_source_receive_and_future_fail_closed(
    source_age_s,
    receive_age_s,
    status,
):
    result = classify(source_age_s, receive_age_s=receive_age_s)

    assert result.fresh is False
    assert result.status == status


def test_missing_and_invalid_timestamps_fail_closed():
    missing = classify_freshness(
        now_ns=NOW_NS,
        source_stamp_ns=None,
        max_age_s=0.20,
    )
    zero = classify_freshness(
        now_ns=NOW_NS,
        source_stamp_ns=0,
        max_age_s=0.20,
    )

    assert missing.status == "invalid_source"
    assert zero.status == "invalid_source"


def test_duplicate_policy_is_explicit():
    source_stamp_ns = NOW_NS - 10_000_000

    held = classify(
        0.01,
        previous_source_stamp_ns=source_stamp_ns,
        reject_duplicate=False,
    )
    replayed = classify(
        0.01,
        previous_source_stamp_ns=source_stamp_ns,
        reject_duplicate=True,
    )

    assert held.status == "fresh"
    assert replayed.status == "duplicate_source"


def test_non_monotonic_timestamp_fails_closed():
    source_stamp_ns = NOW_NS - 20_000_000
    result = classify(
        0.02,
        previous_source_stamp_ns=source_stamp_ns + 1,
        reject_duplicate=True,
    )

    assert result.fresh is False
    assert result.status == "non_monotonic_source"
