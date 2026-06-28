import json
from types import SimpleNamespace

from thesis_bringup.tim_mars.ros_messages import (
    bbox_to_msg_geometry,
    status_json_from_output,
    status_only_json,
    target_msg_from_output,
)


class _Enum:
    def __init__(self, value):
        self.value = value


def _score(track_id=7):
    return SimpleNamespace(
        track_id=track_id,
        total=0.8,
        iou=0.7,
        distance=0.6,
        scale=0.5,
        confidence=0.91,
        id_bonus=0.1,
        appearance=0.2,
        appearance_used=True,
        appearance_raw=0.85,
        appearance_gate_passed=True,
        geometry_allows_appearance=True,
        hard_negative_similarity=0.1,
        hard_negative_margin=0.2,
        hard_negative_reject=False,
        ambiguous=False,
    )


def _output(control_valid=True):
    best = _score()
    return SimpleNamespace(
        bbox=(10.0, 20.0, 50.0, 80.0),
        target_track_id=7,
        track_id=7,
        control_valid=control_valid,
        best_score=best,
        all_scores=[best],
        state=_Enum("LOCKED"),
        control_mode=_Enum("FULL"),
        visible=True,
        reacquired=False,
        quality=0.73,
        frames_since_seen=0,
        reason="accepted",
        memory_update_frozen=False,
        memory_update_freeze_reason="",
        same_id_appearance_ambiguity=False,
        appearance_margin_best_vs_second=0.3,
        geometry_strength=0.8,
        risk_hard_negative=False,
        risk_absence=False,
        risk_scene_ambiguity=False,
        v4a_publish_allowed=True,
    )


def test_bbox_to_msg_geometry_pixel_tracks():
    assert bbox_to_msg_geometry(
        (10.0, 20.0, 50.0, 80.0),
        image_width=100.0,
        image_height=100.0,
        tracks_are_normalized=False,
    ) == (30.0, 50.0, 40.0, 60.0)


def test_bbox_to_msg_geometry_normalized_tracks():
    assert bbox_to_msg_geometry(
        (10.0, 20.0, 50.0, 80.0),
        image_width=100.0,
        image_height=100.0,
        tracks_are_normalized=True,
    ) == (0.3, 0.5, 0.4, 0.6)


def test_target_msg_from_visible_output_preserves_old_semantics():
    msg = target_msg_from_output(
        _output(control_valid=True),
        image_width=100.0,
        image_height=100.0,
        tracks_are_normalized=False,
        zero_id_when_not_visible=True,
    )

    assert msg.id == 7
    assert msg.cx == 30.0
    assert msg.cy == 50.0
    assert msg.w == 40.0
    assert msg.h == 60.0
    assert msg.score == 0.91
    assert msg.quality == 0.73


def test_target_msg_from_invalid_output_zeros_controller_fields():
    msg = target_msg_from_output(
        _output(control_valid=False),
        image_width=100.0,
        image_height=100.0,
        tracks_are_normalized=False,
        zero_id_when_not_visible=True,
    )

    assert msg.id == 0
    assert msg.cx == 0.0
    assert msg.cy == 0.0
    assert msg.w == 0.0
    assert msg.h == 0.0
    assert msg.score == 0.0
    assert msg.quality == 0.0


def test_status_only_json_preserves_core_diagnostics():
    payload = json.loads(status_only_json(_output()))

    assert payload["state"] == "LOCKED"
    assert payload["control_mode"] == "FULL"
    assert payload["target_track_id"] == 7
    assert payload["visible"] is True
    assert payload["quality"] == 0.73
    assert payload["reason"] == "accepted"
    assert payload["v4a_publish_allowed"] is True


def test_status_json_includes_scores_and_appearance_diagnostics():
    payload = json.loads(
        status_json_from_output(
            _output(),
            frame_id=42,
            lat_ms=1.5,
            num_tracks=3,
            appearance_enabled=True,
            appearance_candidates=2,
            appearance_features_valid=1,
            appearance_image_age_ms=12.5,
            appearance_skip_reason="ok",
            appearance_compute_min_interval_ms=250.0,
            appearance_cache_ttl_ms=750.0,
            appearance_cache_size=4,
            appearance_update_cooldown_remaining=0,
        )
    )

    assert payload["frame_id"] == 42
    assert payload["lat_ms"] == 1.5
    assert payload["num_tracks"] == 3
    assert payload["appearance_enabled"] is True
    assert payload["appearance_cache_size"] == 4
    assert payload["best"]["track_id"] == 7
    assert payload["all_scores"][0]["confidence"] == 0.91
