"""Frozen development threshold grid for Issue #58 Target-ReID."""

from __future__ import annotations


THRESHOLDS = tuple(
    round(step * 0.05, 2)
    for step in range(20)
)

SEQUENCE_ID = "dev_may_hard_reentry"

CALIBRATION_RULE = {
    "wrong_tolerance_s": 0.05,
    "absence_output_tolerance_s": 0.05,
    "primary": "minimum_wrong_person_duration",
    "secondary": "minimum_lost_or_suppressed_duration",
    "final_deterministic_tie_break": "higher_threshold",
}
