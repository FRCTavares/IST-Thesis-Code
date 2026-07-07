#!/usr/bin/env python3
"""Small utility helpers for the perception pipeline node."""

from __future__ import annotations

import time


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def stamp_to_ns(stamp) -> int:
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def now_ns() -> int:
    return time.monotonic_ns()


def _ms(dt_ns: int) -> float:
    return float(dt_ns) / 1e6


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _normalize_label(value: str | None) -> str | None:
    if value is None:
        return None
    out = str(value).strip().lower()
    if not out:
        return None
    if out in ("none", "all", "*"):
        return None
    return out


def _bbox_to_xywh(bbox) -> tuple[float | None, float | None, float | None, float | None]:
    if hasattr(bbox, "xmin") and hasattr(bbox, "width"):
        return (
            float(bbox.xmin()),
            float(bbox.ymin()),
            float(bbox.width()),
            float(bbox.height()),
        )

    if hasattr(bbox, "get_xmin") and hasattr(bbox, "get_width"):
        return (
            float(bbox.get_xmin()),
            float(bbox.get_ymin()),
            float(bbox.get_width()),
            float(bbox.get_height()),
        )

    return None, None, None, None


