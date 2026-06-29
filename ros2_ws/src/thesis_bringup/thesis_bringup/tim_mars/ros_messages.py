from __future__ import annotations

import json

from thesis_msgs.msg import TargetState

from thesis_bringup.tim_mars.target_memory import BBox, TargetMemoryOutput


def _value_text(value: object) -> str:
    return str(value.value if hasattr(value, "value") else value)


def bbox_to_msg_geometry(
    bbox: BBox,
    *,
    image_width: float,
    image_height: float,
    tracks_are_normalized: bool,
) -> tuple[float, float, float, float]:
    """Convert TIM bbox xyxy into TargetState cx/cy/w/h geometry."""

    x1, y1, x2, y2 = bbox
    cx = 0.5 * (x1 + x2)
    cy = 0.5 * (y1 + y2)
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)

    if tracks_are_normalized:
        return (
            cx / image_width,
            cy / image_height,
            w / image_width,
            h / image_height,
        )

    return cx, cy, w, h


def target_msg_from_output(
    out: TargetMemoryOutput,
    *,
    image_width: float,
    image_height: float,
    tracks_are_normalized: bool,
    zero_id_when_not_visible: bool,
) -> TargetState:
    """Create the controller-facing TargetState message from TIM output."""

    target_msg = TargetState()

    if (
        out.bbox is None
        or out.target_track_id is None
        or (zero_id_when_not_visible and not out.control_valid)
    ):
        target_msg.id = 0
        target_msg.cx = 0.0
        target_msg.cy = 0.0
        target_msg.w = 0.0
        target_msg.h = 0.0
        target_msg.score = 0.0
        target_msg.quality = 0.0
        return target_msg

    target_msg.id = int(out.target_track_id)

    cx, cy, w, h = bbox_to_msg_geometry(
        out.bbox,
        image_width=image_width,
        image_height=image_height,
        tracks_are_normalized=tracks_are_normalized,
    )
    target_msg.cx = float(cx)
    target_msg.cy = float(cy)
    target_msg.w = float(w)
    target_msg.h = float(h)

    target_msg.score = (
        float(out.best_score.confidence)
        if out.control_valid and out.best_score
        else 0.0
    )
    target_msg.quality = float(out.quality)
    return target_msg


def _score_payload(score: object) -> dict[str, object]:
    return {
        "track_id": int(score.track_id),
        "total": float(score.total),
        "iou": float(score.iou),
        "distance": float(score.distance),
        "scale": float(score.scale),
        "confidence": float(score.confidence),
        "id_bonus": float(score.id_bonus),
        "appearance": float(score.appearance),
        "appearance_used": bool(score.appearance_used),
        "appearance_raw": float(score.appearance_raw),
        "appearance_gate_passed": bool(score.appearance_gate_passed),
        "geometry_allows_appearance": bool(score.geometry_allows_appearance),
        "hard_negative_similarity": float(score.hard_negative_similarity),
        "hard_negative_margin": float(score.hard_negative_margin),
        "hard_negative_reject": bool(score.hard_negative_reject),
        "ambiguous": bool(score.ambiguous),
    }


def status_payload_base(out: TargetMemoryOutput) -> dict[str, object]:
    return {
        "state": _value_text(out.state),
        "control_mode": _value_text(out.control_mode),
        "target_track_id": out.target_track_id,
        "visible": bool(out.visible),
        "reacquired": bool(out.reacquired),
        "quality": float(out.quality),
        "frames_since_seen": int(out.frames_since_seen),
        "reason": str(out.reason),
        "memory_update_frozen": bool(out.memory_update_frozen),
        "memory_update_freeze_reason": str(out.memory_update_freeze_reason),
        "appearance_margin_best_vs_second": float(out.appearance_margin_best_vs_second),
        "geometry_strength": float(out.geometry_strength),
        "risk_hard_negative": bool(out.risk_hard_negative),
        "risk_absence": bool(out.risk_absence),
        "risk_scene_ambiguity": bool(out.risk_scene_ambiguity),
        "candidate_track_id": out.candidate_track_id,
        "candidate_score": float(out.candidate_score),
        "publication_suppressed_reason": out.publication_suppressed_reason,
    }


def status_only_json(out: TargetMemoryOutput) -> str:
    return json.dumps(status_payload_base(out), sort_keys=True)


def status_json_from_output(
    out: TargetMemoryOutput,
    *,
    frame_id: int,
    lat_ms: float,
    num_tracks: int,
    appearance_enabled: bool,
    appearance_candidates: int,
    appearance_features_valid: int,
    appearance_image_age_ms: float | None,
    appearance_skip_reason: str,
    appearance_compute_min_interval_ms: float,
    appearance_cache_ttl_ms: float,
    appearance_cache_size: int,
    appearance_update_cooldown_remaining: int,
) -> str:
    best = out.best_score
    payload = status_payload_base(out)
    payload.update(
        {
            "frame_id": int(frame_id),
            "lat_ms": float(lat_ms),
            "num_tracks": int(num_tracks),
            "appearance_enabled": bool(appearance_enabled),
            "appearance_candidates": int(appearance_candidates),
            "appearance_features_valid": int(appearance_features_valid),
            "appearance_image_age_ms": appearance_image_age_ms,
            "appearance_skip_reason": str(appearance_skip_reason),
            "appearance_compute_min_interval_ms": float(appearance_compute_min_interval_ms),
            "appearance_cache_ttl_ms": float(appearance_cache_ttl_ms),
            "appearance_cache_size": int(appearance_cache_size),
            "appearance_update_cooldown_remaining": int(
                appearance_update_cooldown_remaining
            ),
            "best": None if best is None else _score_payload(best),
            "all_scores": [_score_payload(score) for score in out.all_scores],
        }
    )
    return json.dumps(payload, sort_keys=True)
