import json
from types import SimpleNamespace

from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
)
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
        geometry_score=0.73,
        ranking_score=0.81,
        appearance=0.2,
        appearance_available=True,
        appearance_evaluated=True,
        appearance_similarity_passed=True,
        appearance_used=True,
        appearance_accepted_for_publication=True,
        appearance_raw=0.85,
        protected_anchor_similarity=0.83,
        trusted_gallery_similarity=0.76,
        adaptive_similarity=0.91,
        positive_similarity=0.83,
        positive_support_source="protected_anchor",
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
        acceptance_memory_source="protected_anchor",
        positive_memory_updated=True,
        positive_memory_update_reason=(
            "trusted_locked_adaptive_update"
        ),
        positive_memory_bootstrap_event=SimpleNamespace(
            action="protected_anchor_bootstrap",
            track_id=7,
            accepted_bbox=(10.0, 20.0, 50.0, 80.0),
            acceptance_memory_source="operator_continuity",
            memory_update_eligible=True,
            ambiguous=False,
            hard_negative_reject=False,
            operator_track_id=7,
            current_lineage_track_id=7,
            current_lineage_supported=True,
            frame_id=41,
            track_timestamp_ns=1_500_000_000,
            selected_image_timestamp_ns=1_480_000_000,
            image_track_offset_ms=20.0,
            appearance_source_frame_id=41,
            appearance_source_image_timestamp_ns=(
                1_480_000_000
            ),
            appearance_embedded_ns=1_500_000_000,
            appearance_embedding_age_ms=0.0,
            appearance_frame_generation=2,
            appearance_track_generation=3,
            appearance_source_bbox=(
                10.0,
                20.0,
                50.0,
                80.0,
            ),
            accepted_crop_quality=None,
            appearance_source_crop_quality=None,
        ),
        protected_anchor_available=True,
        trusted_gallery_size=3,
        appearance_lineage_trusted=True,
        appearance_trusted_lock_streak=4,
        appearance_margin_best_vs_second=0.3,
        geometry_strength=0.8,
        risk_hard_negative=False,
        hard_negative_memory_size=2,
        hard_negative_events=(
            SimpleNamespace(
                action="merge",
                source="trusted_locked_distractor",
                source_track_id=8,
                selected_track_id=7,
                source_track_ids=(8, 9),
                selected_track_ids=(7,),
                observations=3,
                positive_similarity=0.74,
                geometry_strength=0.81,
                prototype_similarity=0.92,
                memory_size=2,
            ),
        ),
        risk_absence=False,
        risk_scene_ambiguity=False,
        candidate_track_id=3,
        candidate_score=0.72,
        publication_suppressed_reason="",
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
    payload = json.loads(
        status_only_json(
            _output(),
            selection_generation=7,
            selection_session_id="session-a",
        )
    )

    assert payload["state"] == "LOCKED"
    assert payload["control_mode"] == "FULL"
    assert payload["selection_generation"] == 7
    assert payload["selection_session_id"] == "session-a"
    assert payload["target_track_id"] == 7
    assert payload["visible"] is True
    assert payload["quality"] == 0.73
    assert payload["reason"] == "accepted"
    assert payload["candidate_track_id"] == 3
    assert payload["candidate_score"] == 0.72
    assert payload["publication_suppressed_reason"] == ""
    assert (
        payload["acceptance_memory_source"]
        == "protected_anchor"
    )
    assert payload["positive_memory_updated"] is True
    assert (
        payload["positive_memory_update_reason"]
        == "trusted_locked_adaptive_update"
    )
    assert payload["positive_memory_bootstrap_event"] == {
        "action": "protected_anchor_bootstrap",
        "track_id": 7,
        "accepted_bbox": [
            10.0,
            20.0,
            50.0,
            80.0,
        ],
        "acceptance_memory_source": (
            "operator_continuity"
        ),
        "memory_update_eligible": True,
        "ambiguous": False,
        "hard_negative_reject": False,
        "operator_track_id": 7,
        "current_lineage_track_id": 7,
        "current_lineage_supported": True,
        "frame_id": 41,
        "track_timestamp_ns": 1_500_000_000,
        "selected_image_timestamp_ns": 1_480_000_000,
        "image_track_offset_ms": 20.0,
        "appearance_source_frame_id": 41,
        "appearance_source_image_timestamp_ns": (
            1_480_000_000
        ),
        "appearance_embedded_ns": 1_500_000_000,
        "appearance_embedding_age_ms": 0.0,
        "appearance_frame_generation": 2,
        "appearance_track_generation": 3,
        "appearance_source_bbox": [
            10.0,
            20.0,
            50.0,
            80.0,
        ],
        "accepted_crop_quality": None,
        "appearance_source_crop_quality": None,
    }
    assert payload["protected_anchor_available"] is True
    assert payload["trusted_gallery_size"] == 3
    assert payload["appearance_lineage_trusted"] is True
    assert payload["appearance_trusted_lock_streak"] == 4
    assert payload["hard_negative_memory_size"] == 2
    assert payload["hard_negative_events"] == [
        {
            "action": "merge",
            "source": "trusted_locked_distractor",
            "source_track_id": 8,
            "selected_track_id": 7,
            "source_track_ids": [8, 9],
            "selected_track_ids": [7],
            "observations": 3,
            "positive_similarity": 0.74,
            "geometry_strength": 0.81,
            "prototype_similarity": 0.92,
            "memory_size": 2,
        }
    ]


def test_status_json_includes_scores_and_appearance_diagnostics():
    payload = json.loads(
        status_json_from_output(
            _output(),
            selection_generation=11,
            selection_session_id="session-b",
            frame_id=42,
            tim_mars_processing_ms=1.5,
            num_tracks=3,
            appearance_enabled=True,
            appearance_candidates=2,
            appearance_request_policy="geometry_winner",
            appearance_request_reason="geometry_winner",
            appearance_request_candidates=1,
            appearance_request_track_ids=(8,),
            appearance_request_encoding_eligible=1,
            appearance_features_valid=1,
            appearance_image_age_ms=12.5,
            appearance_skip_reason="ok",
            track_timestamp_ns=2_000_000_000,
            selected_image_timestamp_ns=1_987_500_000,
            image_track_offset_ms=12.5,
            appearance_warning=None,
            candidate_track_ids=(7, 8),
            appearance_compute_min_interval_ms=250.0,
            appearance_cache_ttl_ms=750.0,
            appearance_cache_size=4,
            appearance_cache_lookups=7,
            appearance_cache_hits=3,
            appearance_cache_misses=2,
            appearance_cache_expired=1,
            appearance_cache_invalidated=1,
            appearance_embedding_age_ms_by_track_id={
                7: 0.0,
                8: 125.0,
            },
            appearance_crop_quality_by_track_id={
                7: AppearanceCropQuality(
                    crop_width_px=40.0,
                    crop_height_px=80.0,
                    clipping_fraction=0.0,
                    aspect_ratio=0.5,
                    max_iou_with_other=0.2,
                    min_centre_distance_norm=0.03,
                    encoding_eligible=True,
                    memory_update_eligible=False,
                    rejection_reasons=(
                        "overlap_with_person",
                    ),
                ),
            },
            appearance_encoding_rejected=0,
            appearance_memory_update_ineligible=1,
            appearance_encoding_eligible=2,
            appearance_backend_calls=1,
            appearance_backend_requested=2,
            appearance_backend_returned=2,
            appearance_backend_valid=1,
            appearance_backend_wall_ms=4.25,
            appearance_update_cooldown_remaining=0,
            freshness_contract="tim_mars_output_freshness_v1",
            freshness_status="fresh",
            freshness_is_fresh=True,
            freshness_source_age_ms=12.5,
            freshness_max_output_age_ms=900.0,
        )
    )

    assert payload["frame_id"] == 42
    assert payload["selection_generation"] == 11
    assert payload["selection_session_id"] == "session-b"
    assert payload["tim_mars_processing_ms"] == 1.5
    assert "lat_ms" not in payload
    assert payload["num_tracks"] == 3
    assert payload["appearance_enabled"] is True
    assert payload["appearance_request_policy"] == "geometry_winner"
    assert payload["appearance_request_reason"] == "geometry_winner"
    assert payload["appearance_request_candidates"] == 1
    assert payload["appearance_request_track_ids"] == [8]
    assert (
        payload["appearance_request_encoding_eligible"]
        == 1
    )
    assert payload["appearance_cache_size"] == 4
    assert payload["appearance_cache_lookups"] == 7
    assert payload["appearance_cache_hits"] == 3
    assert payload["appearance_cache_misses"] == 2
    assert payload["appearance_cache_expired"] == 1
    assert payload["appearance_cache_invalidated"] == 1
    assert payload["appearance_cache_lookups"] == (
        payload["appearance_cache_hits"]
        + payload["appearance_cache_misses"]
        + payload["appearance_cache_expired"]
        + payload["appearance_cache_invalidated"]
    )
    assert payload["appearance_embedding_age_ms_by_track_id"] == {
        "7": 0.0,
        "8": 125.0,
    }
    assert payload["appearance_crop_quality_by_track_id"]["7"] == {
        "crop_width_px": 40.0,
        "crop_height_px": 80.0,
        "clipping_fraction": 0.0,
        "aspect_ratio": 0.5,
        "max_iou_with_other": 0.2,
        "min_centre_distance_norm": 0.03,
        "encoding_eligible": True,
        "memory_update_eligible": False,
        "rejection_reasons": [
            "overlap_with_person",
        ],
    }
    assert payload["appearance_encoding_rejected"] == 0
    assert payload["appearance_memory_update_ineligible"] == 1
    assert payload["appearance_encoding_eligible"] == 2
    assert payload["appearance_backend_calls"] == 1
    assert payload["appearance_backend_requested"] == 2
    assert payload["appearance_backend_returned"] == 2
    assert payload["appearance_backend_valid"] == 1
    assert payload["appearance_backend_wall_ms"] == 4.25
    assert payload["freshness_contract"] == "tim_mars_output_freshness_v1"
    assert payload["freshness_status"] == "fresh"
    assert payload["freshness_is_fresh"] is True
    assert payload["freshness_source_age_ms"] == 12.5
    assert payload["freshness_max_output_age_ms"] == 900.0
    assert payload["track_timestamp_ns"] == 2_000_000_000
    assert payload["selected_image_timestamp_ns"] == 1_987_500_000
    assert payload["image_track_offset_ms"] == 12.5
    assert payload["appearance_warning"] is None
    assert payload["candidate_track_ids"] == [7, 8]
    assert payload["best"]["track_id"] == 7
    assert payload["best"]["geometry_score"] == 0.73
    assert payload["best"]["ranking_score"] == 0.81
    assert payload["best"]["appearance_available"] is True
    assert payload["best"]["appearance_evaluated"] is True
    assert (
        payload["best"]["appearance_similarity_passed"]
        is True
    )
    assert (
        payload["best"]["appearance_accepted_for_publication"]
        is True
    )
    assert (
        payload["best"]["protected_anchor_similarity"]
        == 0.83
    )
    assert (
        payload["best"]["trusted_gallery_similarity"]
        == 0.76
    )
    assert payload["best"]["adaptive_similarity"] == 0.91
    assert payload["best"]["positive_similarity"] == 0.83
    assert (
        payload["best"]["positive_support_source"]
        == "protected_anchor"
    )
    assert payload["all_scores"][0]["confidence"] == 0.91
