"""AB-16 production promotion: source-aware adaptive positive-memory updates.

The Stage-1 AB-16 mechanism is promoted to a canonical ``TargetMemoryConfig``
switch. These contracts cover the production parameter and prove it activates
exactly the already-tested last-source suppression, that the historical
development-only control still works, that either path is sufficient, and that
no adjacent behaviour (gallery admission, trusted-only mutation, missing
provenance, clear/reset, operator initialisation) changes.
"""

from types import SimpleNamespace

import numpy as np

from thesis_bringup.tim_mars.crop_quality import AppearanceCropQuality
from thesis_bringup.tim_mars.positive_appearance_memory import (
    PositiveAppearanceMemory,
)
from thesis_bringup.tim_mars.target_memory import (
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
    TargetState,
)
from thesis_bringup.tim_mars.types import AppearanceObservationProvenance


TARGET = np.array([1.0, 0.0, 0.0], dtype=np.float32)
POSE = np.array([0.8, 0.6, 0.0], dtype=np.float32)


def _quality():
    return AppearanceCropQuality(
        crop_width_px=40.0,
        crop_height_px=120.0,
        clipping_fraction=0.0,
        aspect_ratio=0.5,
        max_iou_with_other=0.05,
        min_centre_distance_norm=0.10,
        encoding_eligible=True,
        memory_update_eligible=True,
    )


def _provenance(*, source_frame_id, source_image_timestamp_ns):
    return AppearanceObservationProvenance(
        source_frame_id=source_frame_id,
        source_image_timestamp_ns=source_image_timestamp_ns,
        embedded_ns=1_000,
        embedding_age_ms=4.0,
        frame_generation=2,
        track_generation=3,
        source_bbox=(100.0, 100.0, 160.0, 240.0),
        source_crop_quality=_quality(),
    )


def _candidate(*, source_frame_id=None, source_image_timestamp_ns=None):
    return CandidateTrack(
        track_id=1,
        bbox=(100.0, 100.0, 160.0, 240.0),
        score=0.95,
        appearance=POSE,
        appearance_crop_quality=_quality(),
        appearance_memory_update_eligible=True,
        appearance_provenance=_provenance(
            source_frame_id=source_frame_id,
            source_image_timestamp_ns=source_image_timestamp_ns,
        ),
    )


def _cfg(**overrides):
    values = {
        "image_width": 640,
        "image_height": 480,
        "appearance_enabled": True,
        "appearance_protected_memory_enabled": True,
        "appearance_update_alpha": 0.5,
        "appearance_trusted_gallery_max_entries": 4,
        "appearance_conservative_enabled": False,
        "hard_negative_memory_enabled": False,
        "rank_aware_reacquisition_enabled": False,
        "candidate_belief_enabled": False,
        "absence_recovery_enabled": False,
        "short_gap_new_id_suppression_enabled": False,
    }
    values.update(overrides)
    return TargetMemoryConfig(**values)


def _trusted_memory(cfg, *, dev_control=False, init_source=("image_timestamp_ns", 500)):
    tim = TargetIdentityMemory(
        cfg,
        development_ablation_prevent_repeated_source_adaptive_update=dev_control,
    )
    positive = tim._positive_appearance
    positive.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=init_source,
    )
    positive.lineage_trusted = True
    return tim


def _apply_locked_update(tim, candidate):
    tim._update_accept_appearance_memory(
        candidate=candidate,
        best_score=SimpleNamespace(
            ambiguous=False,
            hard_negative_reject=False,
        ),
        previous_state=TargetState.LOCKED,
        previous_track_id=1,
        new_state=TargetState.LOCKED,
        memory_update_frozen=False,
    )


# --------------------------------------------------------------------------
# Production parameter surface
# --------------------------------------------------------------------------

def test_production_parameter_defaults_to_disabled():
    assert (
        TargetMemoryConfig().appearance_prevent_repeated_source_adaptive_update
        is False
    )


# --------------------------------------------------------------------------
# Production switch drives the tested suppression through the state machine
# --------------------------------------------------------------------------

def test_production_switch_suppresses_repeated_source_update():
    tim = _trusted_memory(
        _cfg(appearance_prevent_repeated_source_adaptive_update=True)
    )
    before = tim._positive_appearance.adaptive_prototype.copy()

    _apply_locked_update(
        tim, _candidate(source_image_timestamp_ns=500)
    )

    np.testing.assert_allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


def test_both_controls_disabled_preserves_baseline_repeated_source_update():
    tim = _trusted_memory(_cfg())
    before = tim._positive_appearance.adaptive_prototype.copy()

    _apply_locked_update(
        tim, _candidate(source_image_timestamp_ns=500)
    )

    assert not np.allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


def test_development_control_alone_still_suppresses_repeated_source_update():
    tim = _trusted_memory(_cfg(), dev_control=True)
    before = tim._positive_appearance.adaptive_prototype.copy()

    _apply_locked_update(
        tim, _candidate(source_image_timestamp_ns=500)
    )

    np.testing.assert_allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


def test_new_source_updates_under_production_switch():
    tim = _trusted_memory(
        _cfg(appearance_prevent_repeated_source_adaptive_update=True)
    )
    before = tim._positive_appearance.adaptive_prototype.copy()

    _apply_locked_update(
        tim, _candidate(source_image_timestamp_ns=777)
    )

    assert not np.allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


# --------------------------------------------------------------------------
# Source-identifier resolution
# --------------------------------------------------------------------------

def test_image_timestamp_is_preferred_over_source_frame_id():
    observation = TargetIdentityMemory._appearance_source_observation(
        _candidate(source_frame_id=9, source_image_timestamp_ns=500)
    )
    assert observation == ("image_timestamp_ns", 500)


def test_source_frame_id_is_the_fallback_identifier():
    observation = TargetIdentityMemory._appearance_source_observation(
        _candidate(source_frame_id=9, source_image_timestamp_ns=None)
    )
    assert observation == ("source_frame_id", 9)

    tim = _trusted_memory(
        _cfg(appearance_prevent_repeated_source_adaptive_update=True),
        init_source=("source_frame_id", 9),
    )
    before = tim._positive_appearance.adaptive_prototype.copy()
    _apply_locked_update(
        tim, _candidate(source_frame_id=9, source_image_timestamp_ns=None)
    )
    np.testing.assert_allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


def test_missing_provenance_does_not_suppress_adaptation():
    assert (
        TargetIdentityMemory._appearance_source_observation(
            CandidateTrack(
                track_id=1,
                bbox=(100.0, 100.0, 160.0, 240.0),
                score=0.95,
                appearance=POSE,
            )
        )
        is None
    )

    tim = _trusted_memory(
        _cfg(appearance_prevent_repeated_source_adaptive_update=True)
    )
    before = tim._positive_appearance.adaptive_prototype.copy()
    tim._update_accept_appearance_memory(
        candidate=CandidateTrack(
            track_id=1,
            bbox=(100.0, 100.0, 160.0, 240.0),
            score=0.95,
            appearance=POSE,
            appearance_memory_update_eligible=True,
        ),
        best_score=SimpleNamespace(ambiguous=False, hard_negative_reject=False),
        previous_state=TargetState.LOCKED,
        previous_track_id=1,
        new_state=TargetState.LOCKED,
        memory_update_frozen=False,
    )
    assert not np.allclose(
        tim._positive_appearance.adaptive_prototype, before
    )


# --------------------------------------------------------------------------
# Mechanism-level contracts on PositiveAppearanceMemory
# --------------------------------------------------------------------------

def test_repeated_source_is_last_source_only_abab_allowed():
    memory = PositiveAppearanceMemory()
    memory.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 1),
    )
    memory.lineage_trusted = True

    def update(source):
        return memory.update_trusted(
            appearance=POSE,
            alpha=0.5,
            gallery_max_entries=0,
            prevent_repeated_adaptive_source=True,
            source_observation=("image_timestamp_ns", source),
        )

    assert update(1) is False          # equals the initialised source
    assert update(2) is True           # A -> B
    assert update(3) is True           # B -> A (distinct again)
    assert update(2) is True           # A -> B
    assert update(2) is False          # repeated last source


def test_distinct_source_updates_even_with_identical_embedding_values():
    memory = PositiveAppearanceMemory()
    memory.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 1),
    )
    memory.lineage_trusted = True

    assert memory.update_trusted(
        appearance=POSE,
        alpha=0.5,
        gallery_max_entries=0,
        prevent_repeated_adaptive_source=True,
        source_observation=("image_timestamp_ns", 2),
    )
    first = memory.adaptive_prototype.copy()

    assert memory.update_trusted(
        appearance=POSE,
        alpha=0.5,
        gallery_max_entries=0,
        prevent_repeated_adaptive_source=True,
        source_observation=("image_timestamp_ns", 3),
    )
    assert memory.last_update_adaptive_updated is True
    assert not np.allclose(memory.adaptive_prototype, first)


def test_clear_resets_remembered_adaptive_source():
    memory = PositiveAppearanceMemory()
    memory.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 5),
    )
    assert memory.last_adaptive_source_observation == ("image_timestamp_ns", 5)

    memory.clear()
    assert memory.last_adaptive_source_observation is None

    memory.select_operator(
        track_id=2,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 5),
    )
    memory.lineage_trusted = True
    assert memory.update_trusted(
        appearance=POSE,
        alpha=0.5,
        gallery_max_entries=0,
        prevent_repeated_adaptive_source=True,
        source_observation=("image_timestamp_ns", 5),
    ) is False


def test_operator_bootstrap_initialises_remembered_adaptive_source():
    memory = PositiveAppearanceMemory()
    memory.operator_track_id = 1
    memory.current_lineage_track_id = 1
    memory.current_lineage_supported = True

    memory.bootstrap_operator_anchor(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 42),
    )
    assert memory.last_adaptive_source_observation == ("image_timestamp_ns", 42)


def test_gallery_admission_still_runs_when_adaptive_update_is_skipped():
    memory = PositiveAppearanceMemory()
    memory.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 1),
    )
    memory.lineage_trusted = True

    admitted = memory.update_trusted(
        appearance=POSE,
        alpha=0.5,
        gallery_max_entries=4,
        prevent_repeated_adaptive_source=True,
        source_observation=("image_timestamp_ns", 1),
    )

    assert admitted is True
    assert memory.last_update_adaptive_updated is False
    assert memory.last_update_gallery_updated is True
    assert len(memory.trusted_gallery) == 1


def test_untrusted_lineage_cannot_mutate_positive_memory():
    memory = PositiveAppearanceMemory()
    memory.select_operator(
        track_id=1,
        appearance=TARGET,
        source_observation=("image_timestamp_ns", 1),
    )
    anchor = memory.protected_anchor.copy()
    adaptive = memory.adaptive_prototype.copy()

    assert memory.update_trusted(
        appearance=POSE,
        alpha=0.5,
        gallery_max_entries=4,
        prevent_repeated_adaptive_source=True,
        source_observation=("image_timestamp_ns", 9),
    ) is False
    np.testing.assert_allclose(memory.protected_anchor, anchor)
    np.testing.assert_allclose(memory.adaptive_prototype, adaptive)
    assert memory.trusted_gallery == []


def test_candidate_persistence_is_untouched_by_source_aware_updates():
    tim = _trusted_memory(
        _cfg(appearance_prevent_repeated_source_adaptive_update=True)
    )
    tracker = tim._candidate_persistence

    assert tracker.observe(
        7, source_observation=("image_timestamp_ns", 100)
    ) == 1
    assert tracker.observe(
        7, source_observation=("image_timestamp_ns", 100)
    ) == 2
