"""Safety-first threshold selector for the Issue #58 Target-ReID baseline.

Selection preserves the historical Issue #58 asymmetric calibration contract:

1. fail closed against the raw tracker safety reference;
2. among promotable candidates, minimize wrong-person duration;
3. break ties by minimizing lost/suppressed duration.

No safety/availability weighted scalar is used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


WRONG_TOLERANCE_S = 0.05
ABSENCE_OUTPUT_TOLERANCE_S = 0.05


@dataclass(frozen=True)
class TargetReIdCalibrationRow:
    threshold: float
    correct_s: float
    wrong_s: float
    unresolved_s: float
    lost_s: float
    absent_with_output_s: float


def select_target_reid_threshold(
    *,
    rows: Sequence[TargetReIdCalibrationRow],
    raw_wrong_s: float,
    raw_absent_with_output_s: float,
    wrong_tolerance_s: float = WRONG_TOLERANCE_S,
    absence_output_tolerance_s: float = ABSENCE_OUTPUT_TOLERANCE_S,
) -> TargetReIdCalibrationRow:
    """Select one threshold using the inherited Issue #58 safety rule."""
    if not rows:
        raise ValueError("no Target-ReID calibration rows")

    promotable = [
        row
        for row in rows
        if (
            row.wrong_s
            <= float(raw_wrong_s) + float(wrong_tolerance_s)
            and row.absent_with_output_s
            <= (
                float(raw_absent_with_output_s)
                + float(absence_output_tolerance_s)
            )
        )
    ]

    if not promotable:
        raise ValueError(
            "no Target-ReID threshold passes the asymmetric safety gate"
        )

    return min(
        promotable,
        key=lambda row: (
            row.wrong_s,
            row.lost_s,
            -row.threshold,
        ),
    )
