#!/usr/bin/env python3
"""Shared canonical timing metric contract.

Canonical outputs should use only the fields listed here. Legacy aliases are
accepted only as input fallback for historical artifacts/bags/messages.

Legacy alias removal plan:
- Keep legacy aliases read-only until all producers emit metrics_schema_version >= 3
    and compatibility validators pass against canonical-only consumers.
- Remove alias writes first (runtime/dashboard producers), then remove alias reads
    from UI and analysis tooling after one thesis reporting cycle with no alias hits.
- Finally remove alias fields from thesis_msgs/Timing.msg in the next schema bump.

Metric tiers:
- Operator KPI: default metrics shown in dashboards and summaries.
- Diagnostic: deeper engineering metrics, hidden by default.
- Legacy: read-only aliases for historical compatibility.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

# Contract version for timing semantics. Kept out of ROS message payload for
# now to preserve compatibility with historical rosbag message layouts.
METRICS_SCHEMA_VERSION: int = 3

# Rolling window metadata used by dashboard and validation tooling.
DET_OUT_FPS_WINDOW_SECONDS: float = 3.0
METRIC_WINDOWS: Dict[str, float] = {
    "det_out_fps_seconds": DET_OUT_FPS_WINDOW_SECONDS,
}

# Canonical semantic for publication cadence metric.
CADENCE_METRIC: str = "pub_dt_ms"

# User-approved canonical metrics across the pipeline.
CANONICAL_METRICS: List[str] = [
    "e2e_det_ms",
    "e2e_target_ms",
    "infer_ms",
    "container_queue_ms",
    "zmq_roundtrip_ms",
    "pub_dt_ms",
    "track_ms",
    "pre_ms",
]

# Default dashboard/report KPI set (balanced 6-8 metrics).
OPERATOR_KPI_METRICS: List[str] = [
    "e2e_det_ms",
    CADENCE_METRIC,
    "container_queue_ms",
    "infer_ms",
    "track_ms",
    "e2e_target_ms",
]

# Additional engineering diagnostics that are useful during profiling but
# should remain out of the default operator-facing view.
DIAGNOSTIC_METRICS: List[str] = [
    "pre_ms",
    "zmq_roundtrip_ms",
]

# Canonical per-topic fields for collectors and reports.
TOPIC_CANONICAL_FIELDS: Dict[str, List[str]] = {
    "/timing": ["pre_ms", "container_queue_ms", "zmq_roundtrip_ms", "infer_ms", "e2e_det_ms", "pub_dt_ms"],
    "/timing_tracker": ["track_ms"],
    "/timing_target": ["e2e_target_ms"],
}

# Canonical dashboard telemetry keys (bridge -> frontend payload).
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

# Backward-compatible alias fallbacks for reads only.
# All alias names below are deprecated compatibility/history-only paths.
# Keep canonical field first so newer producers always win.
LEGACY_ALIAS_TO_CANONICAL: Dict[str, str] = {
    "lat_ms": "e2e_det_ms",
    "recv_ms": "zmq_roundtrip_ms",
    "json_ms": "decode_ms",
    "q_wait_ms": "container_queue_ms",
    "det_interval_ms": "pub_dt_ms",
    "fps": "camera_input_fps",
    "video_fps": "camera_input_fps",
    "det_fps": "det_out_fps",
    "latency_ms": "e2e_det_ms",
    "loop_ms": "loop_ms",
}

FIELD_FALLBACKS: Dict[str, List[str]] = {
    "e2e_det_ms": ["e2e_det_ms", "lat_ms"],
    "zmq_roundtrip_ms": ["zmq_roundtrip_ms", "recv_ms"],
    "decode_ms": ["decode_ms", "json_ms"],
    "e2e_target_ms": ["e2e_target_ms"],
    "infer_ms": ["infer_ms"],
    "container_queue_ms": ["container_queue_ms", "q_wait_ms"],
    "pub_dt_ms": ["pub_dt_ms"],
    "track_ms": ["track_ms"],
    "pre_ms": ["pre_ms"],
}

LEGACY_ALIASES: List[str] = sorted(LEGACY_ALIAS_TO_CANONICAL.keys())

# Human-facing labels for hybrid naming (UI label + technical key).
METRIC_LABELS: Dict[str, str] = {
    "e2e_det_ms": "Detection E2E Latency",
    "e2e_target_ms": "Target E2E Latency",
    "infer_ms": "Inference Compute",
    "container_queue_ms": "Pre-Infer Queue Wait",
    "zmq_roundtrip_ms": "ZMQ Roundtrip",
    "pub_dt_ms": "Detection Cadence Interval",
    "track_ms": "Tracker Compute",
    "pre_ms": "Preprocess Compute",
}

METRIC_UNITS: Dict[str, str] = {
    "e2e_det_ms": "ms",
    "e2e_target_ms": "ms",
    "infer_ms": "ms",
    "container_queue_ms": "ms",
    "zmq_roundtrip_ms": "ms",
    "pub_dt_ms": "ms",
    "track_ms": "ms",
    "pre_ms": "ms",
}

# Central thresholds for warning logic in tooling and telemetry surfaces.
METRIC_WARN_THRESHOLDS: Dict[str, float] = {
    "e2e_det_ms": 120.0,
    "pub_dt_ms": 120.0,
    "container_queue_ms": 100.0,
    "infer_ms": 20.0,
    "track_ms": 25.0,
    "e2e_target_ms": 150.0,
}

# Tolerance for cadence-consistency checks comparing measured FPS and interval-derived FPS.
FPS_INTERVAL_RELATIVE_DELTA_MAX: float = 0.35


def candidates_for(field: str) -> List[str]:
    return list(FIELD_FALLBACKS.get(field, [field]))


def resolve_metric(obj: Any, field: str) -> Tuple[float, str]:
    """Resolve a metric value from canonical field + fallback aliases.

    Returns (value, source_field_name). Raises KeyError if no candidate exists.
    """
    for name in candidates_for(field):
        if hasattr(obj, name):
            value = float(getattr(obj, name))
            return value, name
    raise KeyError(field)


def finite_non_negative(v: float) -> bool:
    return math.isfinite(v) and v >= 0.0


def resolve_from_dict(payload: Dict[str, Any], field: str) -> Tuple[float, str]:
    """Resolve a metric value from dict payload with fallback aliases."""
    for name in candidates_for(field):
        if name in payload:
            return float(payload[name]), name
    raise KeyError(field)


def topic_fields(topic: str) -> Sequence[str]:
    return tuple(TOPIC_CANONICAL_FIELDS.get(topic, []))


def metric_label(field: str) -> str:
    return METRIC_LABELS.get(field, field)


def metric_unit(field: str) -> str:
    return METRIC_UNITS.get(field, "")


def metric_warn_threshold(field: str) -> float | None:
    return METRIC_WARN_THRESHOLDS.get(field)


def is_legacy_alias(field: str) -> bool:
    return field in LEGACY_ALIAS_TO_CANONICAL
