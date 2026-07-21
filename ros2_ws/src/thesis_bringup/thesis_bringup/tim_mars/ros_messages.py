"""ROS message and JSON diagnostic conversion for TIM-MARS.

This module converts pure TargetMemoryOutput objects into ROS-facing
TargetState messages and JSON status payloads. It keeps message formatting and
diagnostic serialization separate from the selected-target algorithm.

It must not contain target-selection policy, scoring logic, or memory-state
transitions.
"""

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
        "protected_anchor_similarity": float(
            getattr(
                score,
                "protected_anchor_similarity",
                0.0,
            )
        ),
        "trusted_gallery_similarity": float(
            getattr(
                score,
                "trusted_gallery_similarity",
                0.0,
            )
        ),
        "adaptive_similarity": float(
            getattr(score, "adaptive_similarity", 0.0)
        ),
        "positive_similarity": float(
            getattr(score, "positive_similarity", 0.0)
        ),
        "positive_support_source": str(
            getattr(
                score,
                "positive_support_source",
                "none",
            )
        ),
        "appearance_gate_passed": bool(score.appearance_gate_passed),
        "geometry_allows_appearance": bool(score.geometry_allows_appearance),
        "hard_negative_similarity": float(score.hard_negative_similarity),
        "hard_negative_margin": float(score.hard_negative_margin),
        "hard_negative_reject": bool(score.hard_negative_reject),
        "ambiguous": bool(score.ambiguous),
    }


def _hard_negative_event_payload(
    event: object,
) -> dict[str, object]:
    source_track_id = getattr(event, "source_track_id", None)
    selected_track_id = getattr(event, "selected_track_id", None)

    return {
        "action": str(getattr(event, "action", "")),
        "source": str(getattr(event, "source", "")),
        "source_track_id": (
            int(source_track_id)
            if source_track_id is not None
            else None
        ),
        "selected_track_id": (
            int(selected_track_id)
            if selected_track_id is not None
            else None
        ),
        "source_track_ids": [
            int(track_id)
            for track_id in getattr(
                event,
                "source_track_ids",
                (),
            )
        ],
        "selected_track_ids": [
            int(track_id)
            for track_id in getattr(
                event,
                "selected_track_ids",
                (),
            )
        ],
        "observations": int(
            getattr(event, "observations", 0)
        ),
        "positive_similarity": float(
            getattr(event, "positive_similarity", 0.0)
        ),
        "geometry_strength": float(
            getattr(event, "geometry_strength", 0.0)
        ),
        "prototype_similarity": float(
            getattr(event, "prototype_similarity", 0.0)
        ),
        "memory_size": int(
            getattr(event, "memory_size", 0)
        ),
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
        "acceptance_memory_source": str(
            getattr(
                out,
                "acceptance_memory_source",
                "none",
            )
        ),
        "positive_memory_updated": bool(
            getattr(out, "positive_memory_updated", False)
        ),
        "positive_memory_update_reason": str(
            getattr(
                out,
                "positive_memory_update_reason",
                "",
            )
        ),
        "protected_anchor_available": bool(
            getattr(
                out,
                "protected_anchor_available",
                False,
            )
        ),
        "trusted_gallery_size": int(
            getattr(out, "trusted_gallery_size", 0)
        ),
        "appearance_lineage_trusted": bool(
            getattr(
                out,
                "appearance_lineage_trusted",
                False,
            )
        ),
        "appearance_trusted_lock_streak": int(
            getattr(
                out,
                "appearance_trusted_lock_streak",
                0,
            )
        ),
        "appearance_margin_best_vs_second": float(out.appearance_margin_best_vs_second),
        "geometry_strength": float(out.geometry_strength),
        "risk_hard_negative": bool(out.risk_hard_negative),
        "hard_negative_memory_size": int(
            getattr(out, "hard_negative_memory_size", 0)
        ),
        "hard_negative_events": [
            _hard_negative_event_payload(event)
            for event in getattr(
                out,
                "hard_negative_events",
                (),
            )
        ],
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
    track_timestamp_ns: int | None,
    selected_image_timestamp_ns: int | None,
    image_track_offset_ms: float | None,
    appearance_warning: str | None,
    candidate_track_ids: tuple[int, ...],
    appearance_compute_min_interval_ms: float,
    appearance_cache_ttl_ms: float,
    appearance_cache_size: int,
    appearance_embedding_age_ms_by_track_id: dict[int, float],
    appearance_crop_quality_by_track_id: dict[int, object],
    appearance_encoding_rejected: int,
    appearance_memory_update_ineligible: int,
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
            "track_timestamp_ns": track_timestamp_ns,
            "selected_image_timestamp_ns": selected_image_timestamp_ns,
            "image_track_offset_ms": image_track_offset_ms,
            "appearance_warning": appearance_warning,
            "candidate_track_ids": [
                int(track_id)
                for track_id in candidate_track_ids
            ],
            "appearance_compute_min_interval_ms": float(appearance_compute_min_interval_ms),
            "appearance_cache_ttl_ms": float(appearance_cache_ttl_ms),
            "appearance_cache_size": int(appearance_cache_size),
            "appearance_embedding_age_ms_by_track_id": {
                str(int(track_id)): float(age_ms)
                for track_id, age_ms in sorted(
                    appearance_embedding_age_ms_by_track_id.items()
                )
            },
            "appearance_crop_quality_by_track_id": {
                str(int(track_id)): {
                    "crop_width_px": float(
                        quality.crop_width_px
                    ),
                    "crop_height_px": float(
                        quality.crop_height_px
                    ),
                    "clipping_fraction": float(
                        quality.clipping_fraction
                    ),
                    "aspect_ratio": float(
                        quality.aspect_ratio
                    ),
                    "max_iou_with_other": float(
                        quality.max_iou_with_other
                    ),
                    "min_centre_distance_norm": float(
                        quality.min_centre_distance_norm
                    ),
                    "encoding_eligible": bool(
                        quality.encoding_eligible
                    ),
                    "memory_update_eligible": bool(
                        quality.memory_update_eligible
                    ),
                    "rejection_reasons": list(
                        quality.rejection_reasons
                    ),
                }
                for track_id, quality in sorted(
                    appearance_crop_quality_by_track_id.items()
                )
            },
            "appearance_encoding_rejected": int(
                appearance_encoding_rejected
            ),
            "appearance_memory_update_ineligible": int(
                appearance_memory_update_ineligible
            ),
            "appearance_update_cooldown_remaining": int(
                appearance_update_cooldown_remaining
            ),
            "best": None if best is None else _score_payload(best),
            "all_scores": [_score_payload(score) for score in out.all_scores],
        }
    )
    return json.dumps(payload, sort_keys=True)
