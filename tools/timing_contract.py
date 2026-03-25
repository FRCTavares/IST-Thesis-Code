#!/usr/bin/env python3
"""Shared canonical timing metric contract.

Canonical outputs should use only the fields listed here. Legacy aliases are
accepted only as input fallback for historical bags/messages.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

# User-approved canonical metrics across the pipeline.
CANONICAL_METRICS: List[str] = [
    "e2e_det_ms",
    "e2e_target_ms",
    "infer_ms",
    "zmq_roundtrip_ms",
    "pub_dt_ms",
    "track_ms",
    "pre_ms",
]

# Canonical per-topic fields for collectors and reports.
TOPIC_CANONICAL_FIELDS: Dict[str, List[str]] = {
    "/timing": ["pre_ms", "zmq_roundtrip_ms", "infer_ms", "e2e_det_ms", "pub_dt_ms"],
    "/timing_tracker": ["track_ms"],
    "/timing_target": ["e2e_target_ms"],
}

# Backward-compatible alias fallbacks for reads only.
# Keep canonical field first so newer producers always win.
FIELD_FALLBACKS: Dict[str, List[str]] = {
    "e2e_det_ms": ["e2e_det_ms", "lat_ms"],
    "zmq_roundtrip_ms": ["zmq_roundtrip_ms", "recv_ms"],
    "decode_ms": ["decode_ms", "json_ms"],
    "e2e_target_ms": ["e2e_target_ms"],
    "infer_ms": ["infer_ms"],
    "pub_dt_ms": ["pub_dt_ms"],
    "track_ms": ["track_ms"],
    "pre_ms": ["pre_ms"],
}

LEGACY_ALIASES: List[str] = ["lat_ms", "recv_ms", "json_ms", "loop_ms"]


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
