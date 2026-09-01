#!/usr/bin/env python3
"""Canonical runtime timing metric contract for the direct-Hailo thesis stack.

Schema v4 describes only the current architecture:

    camera callback
      -> preprocessing
      -> direct in-process Hailo detector
      -> tracker
      -> TIM-MARS validated selected-target publication

There are intentionally no container/ZMQ compatibility aliases and no
historical field fallbacks. Historical bags created with older Timing message
layouts must be analysed with the historical code that produced them rather
than silently reinterpreted under this contract.

Metric tiers:

- Operator KPI: compact safety/availability/runtime metrics for live monitoring
  and cross-architecture comparison.
- Diagnostic: stage-level decomposition used to locate runtime cost.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# Contract identity
# ---------------------------------------------------------------------------

METRICS_SCHEMA_VERSION: int = 4

DET_OUT_FPS_WINDOW_SECONDS: float = 3.0

METRIC_WINDOWS: Dict[str, float] = {
    "det_out_fps_seconds": DET_OUT_FPS_WINDOW_SECONDS,
}

# Canonical detector publication-cadence field.
CADENCE_METRIC: str = "pub_dt_ms"


# ---------------------------------------------------------------------------
# Canonical metrics
# ---------------------------------------------------------------------------

CANONICAL_METRICS: List[str] = [
    # Detector input / preprocessing.
    "ros_wait_ms",
    "pre_ms",
    "ros_to_np_ms",
    "resize_ms",
    "color_ms",

    # Direct-Hailo detector.
    "pre_infer_wait_ms",
    "infer_ms",
    "post_ms",
    "det_pub_ms",
    "e2e_det_ms",
    "pub_dt_ms",

    # Tracker.
    "track_ms",

    # Validated selected-target authority.
    "tim_mars_processing_ms",
    "e2e_validated_target_ms",
]


OPERATOR_KPI_METRICS: List[str] = [
    "e2e_det_ms",
    CADENCE_METRIC,
    "pre_infer_wait_ms",
    "infer_ms",
    "track_ms",
    "tim_mars_processing_ms",
    "e2e_validated_target_ms",
]


DIAGNOSTIC_METRICS: List[str] = [
    "ros_wait_ms",
    "pre_ms",
    "ros_to_np_ms",
    "resize_ms",
    "color_ms",
    "post_ms",
    "det_pub_ms",
]


TOPIC_CANONICAL_FIELDS: Dict[str, List[str]] = {
    "/timing": [
        "ros_wait_ms",
        "pre_ms",
        "ros_to_np_ms",
        "resize_ms",
        "color_ms",
        "pre_infer_wait_ms",
        "infer_ms",
        "post_ms",
        "det_pub_ms",
        "e2e_det_ms",
        "pub_dt_ms",
    ],
    "/timing_tracker": [
        "track_ms",
    ],
    "/timing_target": [
        "tim_mars_processing_ms",
        "e2e_validated_target_ms",
    ],
}


# ---------------------------------------------------------------------------
# Dashboard contract
# ---------------------------------------------------------------------------

# The current dashboard exposes only detector-level runtime metrics.
# Target-authority timing is retained in /timing_target for analysis and #58.
DASHBOARD_CANONICAL_FIELDS: List[str] = [
    "camera_input_fps",
    "det_out_fps",
    "e2e_det_ms",
    CADENCE_METRIC,
]

DASHBOARD_REQUIRED_METADATA_FIELDS: List[str] = [
    "metrics_schema_version",
    "metric_windows",
    "metric_thresholds_ms",
]


# ---------------------------------------------------------------------------
# Human-facing labels / units
# ---------------------------------------------------------------------------

METRIC_LABELS: Dict[str, str] = {
    "ros_wait_ms": "Perception Callback Wait",
    "pre_ms": "Detector Preprocessing",
    "ros_to_np_ms": "ROS Image to NumPy",
    "resize_ms": "Detector Resize",
    "color_ms": "Detector Colour Conversion",
    "pre_infer_wait_ms": "Direct-Hailo Pre-Inference Wait",
    "infer_ms": "Hailo Detector Inference",
    "post_ms": "Detector Post-processing",
    "det_pub_ms": "Detection Publication",
    "e2e_det_ms": "Detection End-to-End Latency",
    "pub_dt_ms": "Detection Publication Interval",
    "track_ms": "Tracker Backend Compute",
    "tim_mars_processing_ms": "TIM-MARS Processing",
    "e2e_validated_target_ms": "Validated Target End-to-End Latency",
}

METRIC_UNITS: Dict[str, str] = {
    field: "ms"
    for field in CANONICAL_METRICS
}


# ---------------------------------------------------------------------------
# Existing operational warning limits
# ---------------------------------------------------------------------------

# These are warning/reference limits, not scientific acceptance criteria.
#
# Do not infer a limit for tim_mars_processing_ms here: #32 must first measure
# its actual distribution and #58 must compare the architecture-level cost.
#
# e2e_validated_target_ms likewise has no per-sample warning threshold here.
# The thesis control contract is evaluated statistically (including p95) rather
# than by silently converting that requirement into a per-sample alarm.
METRIC_WARN_THRESHOLDS: Dict[str, float] = {
    "e2e_det_ms": 120.0,
    "pub_dt_ms": 120.0,
    "pre_infer_wait_ms": 100.0,
    "infer_ms": 20.0,
    "track_ms": 25.0,
}


# Tolerance for consistency between measured detection FPS and interval-derived
# detection FPS.
FPS_INTERVAL_RELATIVE_DELTA_MAX: float = 0.35


# ---------------------------------------------------------------------------
# Canonical-only access helpers
# ---------------------------------------------------------------------------

def candidates_for(field: str) -> List[str]:
    """Return the sole schema-v4 field name.

    The helper name is retained because several current analysis tools use it,
    but schema v4 performs no alias or historical fallback resolution.
    """
    return [field]


def resolve_metric(obj: Any, field: str) -> Tuple[float, str]:
    """Read exactly one canonical schema-v4 metric from an object."""
    if not hasattr(obj, field):
        raise KeyError(field)
    return float(getattr(obj, field)), field


def finite_non_negative(v: float) -> bool:
    return math.isfinite(v) and v >= 0.0


def resolve_from_dict(
    payload: Dict[str, Any],
    field: str,
) -> Tuple[float, str]:
    """Read exactly one canonical schema-v4 metric from a dictionary."""
    if field not in payload:
        raise KeyError(field)
    return float(payload[field]), field


def topic_fields(topic: str) -> Sequence[str]:
    return tuple(TOPIC_CANONICAL_FIELDS.get(topic, []))


def metric_label(field: str) -> str:
    return METRIC_LABELS.get(field, field)


def metric_unit(field: str) -> str:
    return METRIC_UNITS.get(field, "")


def metric_warn_threshold(field: str) -> float | None:
    return METRIC_WARN_THRESHOLDS.get(field)
