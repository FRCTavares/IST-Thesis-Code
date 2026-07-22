"""Shared output-freshness classification for live and offline consumers."""

from __future__ import annotations

from dataclasses import dataclass


FRESHNESS_CONTRACT_VERSION = "tim_mars_output_freshness_v1"
DEFAULT_MAX_OUTPUT_AGE_S = 0.90
DEFAULT_FUTURE_TOLERANCE_S = 0.05


@dataclass(frozen=True)
class FreshnessResult:
    """One deterministic classification of a timestamped observation."""

    status: str
    fresh: bool
    source_age_s: float | None
    receive_age_s: float | None


def classify_freshness(
    *,
    now_ns: int,
    source_stamp_ns: int | None,
    max_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
    receive_stamp_ns: int | None = None,
    future_tolerance_s: float = DEFAULT_FUTURE_TOLERANCE_S,
    previous_source_stamp_ns: int | None = None,
    reject_duplicate: bool = False,
) -> FreshnessResult:
    """Classify source and optional local-receive age in one clock domain.

    Invalid, future, non-monotonic, and explicitly rejected duplicate source
    timestamps fail closed. A duplicate can otherwise remain fresh until the
    maximum age; this is used by offline latest-preceding sampling, where
    holding a value briefly is intentional.
    """
    now_ns = int(now_ns)
    max_age_s = float(max_age_s)
    future_tolerance_s = max(0.0, float(future_tolerance_s))

    if now_ns <= 0:
        return FreshnessResult("invalid_now", False, None, None)
    if max_age_s <= 0.0:
        return FreshnessResult("invalid_max_age", False, None, None)
    if source_stamp_ns is None or int(source_stamp_ns) <= 0:
        return FreshnessResult("invalid_source", False, None, None)

    source_stamp_ns = int(source_stamp_ns)
    source_age_s = float(now_ns - source_stamp_ns) / 1e9

    receive_age_s = None
    if receive_stamp_ns is not None:
        receive_stamp_ns = int(receive_stamp_ns)
        if receive_stamp_ns <= 0:
            return FreshnessResult(
                "invalid_receive",
                False,
                source_age_s,
                None,
            )
        receive_age_s = float(now_ns - receive_stamp_ns) / 1e9
        if receive_age_s < -future_tolerance_s:
            return FreshnessResult(
                "future_receive",
                False,
                source_age_s,
                receive_age_s,
            )

    if source_age_s < -future_tolerance_s:
        return FreshnessResult(
            "future_source",
            False,
            source_age_s,
            receive_age_s,
        )

    if previous_source_stamp_ns is not None:
        previous_source_stamp_ns = int(previous_source_stamp_ns)
        if source_stamp_ns < previous_source_stamp_ns:
            return FreshnessResult(
                "non_monotonic_source",
                False,
                source_age_s,
                receive_age_s,
            )
        if reject_duplicate and source_stamp_ns == previous_source_stamp_ns:
            return FreshnessResult(
                "duplicate_source",
                False,
                source_age_s,
                receive_age_s,
            )

    if source_age_s > max_age_s:
        return FreshnessResult(
            "stale_source",
            False,
            source_age_s,
            receive_age_s,
        )
    if receive_age_s is not None and receive_age_s > max_age_s:
        return FreshnessResult(
            "stale_receive",
            False,
            source_age_s,
            receive_age_s,
        )

    return FreshnessResult(
        "fresh",
        True,
        max(0.0, source_age_s),
        None if receive_age_s is None else max(0.0, receive_age_s),
    )


def classify_relative_freshness(
    *,
    now_s: float,
    source_time_s: float | None,
    max_age_s: float = DEFAULT_MAX_OUTPUT_AGE_S,
    future_tolerance_s: float = DEFAULT_FUTURE_TOLERANCE_S,
) -> FreshnessResult:
    """Apply the same contract to an offline timeline whose origin is zero."""
    if source_time_s is None:
        return FreshnessResult("invalid_source", False, None, None)

    origin_ns = 1_000_000_000_000
    return classify_freshness(
        now_ns=origin_ns + int(round(float(now_s) * 1e9)),
        source_stamp_ns=(
            origin_ns + int(round(float(source_time_s) * 1e9))
        ),
        max_age_s=max_age_s,
        future_tolerance_s=future_tolerance_s,
    )
