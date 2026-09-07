"""Synthetic identity challenges and redundant-gallery recovery contracts."""

from dataclasses import replace

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_attachment import AppearanceAttachmentConfig
from thesis_bringup.tim_mars.appearance_request_policy import (
    AppearanceRequestDecision, AppearanceRequestPolicy,
)
from thesis_bringup.tim_mars.candidate_safety_policy import (
    protected_gallery_reacquisition_reject_reason,
)
from thesis_bringup.tim_mars.runtime import (
    AppearanceFrame, TimMarsRuntime, TimMarsRuntimeConfig,
)
from thesis_bringup.tim_mars.types import (
    CandidateScore, CandidateTrack, TargetMemoryConfig, TargetState,
)


TARGET = np.array([1., 0., 0.], dtype=np.float32)
OTHER = np.array([0., 1., 0.], dtype=np.float32)


class Encoder:
    def __init__(self):
        self.feature = TARGET
        self.calls = []

    def encode(self, image, boxes):
        self.calls.append(boxes)
        return [self.feature for _ in boxes]


def runtime(
    enabled=True,
    *,
    disable_forced_challenge=False,
    restore_general_negative_exemption=False,
):
    config = TargetMemoryConfig(
        appearance_enabled=True,
        appearance_protected_memory_enabled=True,
        same_id_hijack_protection_enabled=True,
        same_id_fresh_challenge_enabled=enabled,
        id_switch_min_appearance_similarity=.78,
        hard_negative_memory_enabled=True,
        appearance_conservative_enabled=False,
    )
    return TimMarsRuntime(TimMarsRuntimeConfig(
        memory=config,
        appearance=AppearanceAttachmentConfig(True, 250., 250., 750.),
        image_width=640., image_height=640.,
        development_ablation_disable_forced_same_id_challenge=(
            disable_forced_challenge
        ),
        development_ablation_restore_same_id_general_negative_exemption=(
            restore_general_negative_exemption
        ),
    ), mars_backend=Encoder())


def candidates():
    return [CandidateTrack(7, (100., 100., 140., 220.)),
            CandidateTrack(8, (150., 100., 190., 220.))]


def attach(rt, items, timestamp, frame, image=True):
    return rt._attach_appearance(
        candidates=items, track_timestamp_ns=timestamp, frame_id=frame,
        selected_image=AppearanceFrame(
            timestamp, np.zeros((640, 640, 3), dtype=np.uint8),
        ) if image else None,
        appearance_request=AppearanceRequestDecision(
            AppearanceRequestPolicy.ALL_CANDIDATES, rt.memory.state,
            tuple(range(len(items))), tuple(c.track_id for c in items),
            "all_candidates",
        ),
    )


def initialized(enabled=True, **kwargs):
    rt = runtime(enabled, **kwargs)
    items, _ = attach(rt, candidates(), 1_000_000_000, 1)
    rt.memory.select(items[0], frame_id=1, timestamp_ns=1_000_000_000)
    return rt


def test_risk_challenge_refreshes_only_selected_candidate_before_interval():
    rt = initialized()
    rt.mars_backend.feature = OTHER
    rt.memory._hard_negative_memory._memory = [OTHER]
    items, diag = attach(rt, candidates(), 1_030_000_000, 2)
    assert diag.skip_reason == "fresh_identity_challenge"
    assert len(rt.mars_backend.calls[-1]) == 1
    assert rt.appearance_state.last_mars_compute_ns == 1_000_000_000
    output = rt.memory.update(items, frame_id=2, timestamp_ns=1_030_000_000)
    assert not output.visible
    assert output.reason.startswith("same_id_hijack_reject")
    assert not output.positive_memory_updated


def test_correct_challenge_retains_selected_authority():
    rt = initialized()
    items, _ = attach(rt, candidates(), 1_030_000_000, 2)
    output = rt.memory.update(items, frame_id=2, timestamp_ns=1_030_000_000)
    assert output.visible
    assert output.target_track_id == 7


def test_no_distractor_retains_normal_cache_cadence():
    rt = initialized()
    items, diag = attach(rt, candidates()[:1], 1_030_000_000, 2)
    assert diag.skip_reason == "cached_interval"
    assert len(rt.mars_backend.calls) == 1
    assert rt.memory.update(items).visible


def test_drifting_same_id_does_not_reuse_positive_cache_during_challenge():
    rt = initialized()
    rt.mars_backend.feature = OTHER
    drifted = candidates()
    drifted[0] = replace(drifted[0], bbox=(110., 100., 150., 220.))
    items, diag = attach(rt, drifted, 1_030_000_000, 2)
    assert diag.embedding_age_ms_by_track_id[7] == 0.
    np.testing.assert_array_equal(items[0].appearance, OTHER)
    assert not rt.memory.update(items).visible


@pytest.mark.parametrize("image", [True, False])
def test_failed_challenge_suppresses_cached_authority(image):
    rt = initialized()
    rt.mars_backend = None
    items, _ = attach(rt, candidates(), 1_030_000_000, 2, image=image)
    assert items[0].appearance_challenge_failed
    output = rt.memory.update(items)
    assert not output.visible
    assert output.reason == "same_id_fresh_challenge_reject:no_fresh_evidence"


def test_same_image_guard_is_not_bypassed_for_challenge():
    rt = initialized()
    items, diag = attach(rt, candidates(), 1_000_000_000, 2)
    assert diag.skip_reason == "cached_same_image"
    assert len(rt.mars_backend.calls) == 1
    assert not rt.memory.update(items).visible


def test_strong_negative_rejects_same_id_even_without_challenger():
    rt = initialized()
    rt.memory._hard_negative_memory._memory = [OTHER]
    item = replace(candidates()[0], appearance=OTHER)
    output = rt.memory.update([item])
    assert not output.visible
    assert output.reason.startswith("hard_negative_reject")


def test_ab11_disables_forced_scheduling_but_keeps_general_negative_veto():
    rt = initialized(disable_forced_challenge=True)
    rt.mars_backend.feature = OTHER

    items, diag = attach(
        rt,
        candidates(),
        1_030_000_000,
        2,
    )

    assert diag.skip_reason == "cached_interval"
    assert len(rt.mars_backend.calls) == 1

    rt.memory._hard_negative_memory._memory = [OTHER]
    wrong = replace(
        candidates()[0],
        appearance=OTHER,
    )
    output = rt.memory.update([wrong])

    assert not output.visible
    assert output.reason.startswith("hard_negative_reject")


def test_ab18_restores_only_general_same_id_negative_exemption():
    rt = initialized(
        restore_general_negative_exemption=True,
    )
    rt.memory._hard_negative_memory._memory = [OTHER]

    wrong = replace(
        candidates()[0],
        appearance=OTHER,
    )

    # No current challenger: the later general same-ID negative veto is
    # experimentally exempted.
    output = rt.memory.update([wrong])
    assert output.visible
    assert output.target_track_id == 7


def test_ab18_keeps_challenger_specific_negative_rejection():
    rt = initialized(
        restore_general_negative_exemption=True,
    )
    rt.memory._hard_negative_memory._memory = [OTHER]

    items = candidates()
    items[0] = replace(
        items[0],
        appearance=OTHER,
    )

    output = rt.memory.update(items)

    assert not output.visible
    assert output.reason.startswith("same_id_hijack_reject")
    assert "hard_negative" in output.reason


@pytest.mark.parametrize("count,accepted", [(0, False), (1, False), (2, True)])
def test_gallery_recovery_requires_redundant_support(count, accepted):
    cfg = TargetMemoryConfig(
        appearance_protected_memory_enabled=True,
        appearance_gallery_min_anchor_similarity=.75,
        appearance_gallery_consensus_recovery_enabled=True,
    )
    score = CandidateScore(7, .8, .5, .9, .9, .9, 0.,
                           positive_support_source="trusted_gallery",
                           protected_anchor_similarity=.5)
    reason = protected_gallery_reacquisition_reject_reason(
        cfg=cfg, candidate=candidates()[0], score=score,
        reacquired=True, gallery_support_count=count,
    )
    assert (reason is None) == accepted
    untrusted = replace(candidates()[0], appearance_memory_update_eligible=False)
    assert protected_gallery_reacquisition_reject_reason(
        cfg=cfg, candidate=untrusted, score=score, reacquired=True,
        gallery_support_count=count,
    ) is not None


def test_experiments_disabled_preserve_cached_same_id_continuity():
    rt = initialized(enabled=False)
    rt.mars_backend.feature = OTHER
    items, diag = attach(rt, candidates(), 1_030_000_000, 2)
    assert diag.skip_reason == "cached_interval"
    assert rt.memory.update(items).state == TargetState.LOCKED


def test_consensus_global_recovery_and_correct_post_recovery_continuation():
    rt = initialized()
    rt.memory.cfg.appearance_gallery_consensus_recovery_enabled = True
    rt.memory.cfg.global_reacquisition_enabled = True
    rt.memory.cfg.global_reacquisition_after_missed_frames = 1
    rt.memory.cfg.max_uncertain_frames = 1
    rt.memory.cfg.id_switch_spatial_gate_enabled = False
    rt.memory.cfg.min_confirm_frames_after_reacquire = 1
    rt.memory._positive_appearance.trusted_gallery = [
        np.array([0., 1., .2]) / np.sqrt(1.04),
        np.array([0., 1., -.2]) / np.sqrt(1.04),
    ]
    for _ in range(10):
        rt.memory.update([])
    assert rt.memory.state == TargetState.LOST
    returned = replace(candidates()[0], track_id=19, appearance=OTHER)
    first = rt.memory.update([returned])
    assert first.state == TargetState.REACQUIRED
    assert not first.visible
    second = rt.memory.update([returned])
    assert second.state == TargetState.LOCKED
    assert second.visible
    assert rt.memory.update([returned]).visible
    np.testing.assert_array_equal(rt.memory._positive_appearance.protected_anchor, TARGET)


@pytest.mark.parametrize("image", [True, False])
def test_available_image_policy_keeps_existing_identity_gates(image):
    rt = initialized()
    rt.memory.cfg.same_id_challenge_available_images_only = True
    items, diag = attach(rt, candidates(), 1_000_000_000, 2, image=image)
    assert diag.skip_reason in {"cached_same_image", "no_image"}
    assert not items[0].appearance_challenge_failed
    assert rt.memory.update(items).visible
    rt.memory._hard_negative_memory._memory = [OTHER]
    wrong = replace(items[0], appearance=OTHER)
    assert not rt.memory.update([wrong, items[1]]).visible


def test_available_image_policy_still_fails_closed_on_backend_failure():
    rt = initialized()
    rt.memory.cfg.same_id_challenge_available_images_only = True
    rt.mars_backend = None
    items, _ = attach(rt, candidates(), 1_030_000_000, 2)
    assert items[0].appearance_challenge_failed
    assert not rt.memory.update(items).visible


def test_available_image_policy_does_not_extend_cache_expiry():
    rt = initialized()
    rt.memory.cfg.same_id_challenge_available_images_only = True
    items, diag = attach(rt, candidates(), 2_000_000_000, 2, image=False)
    assert diag.cache_expired == 2
    assert items[0].appearance is None
    assert not rt.memory.update(items).visible


def test_available_image_policy_still_challenges_new_visual_observation():
    rt = initialized()
    rt.memory.cfg.same_id_challenge_available_images_only = True
    rt.mars_backend.feature = OTHER
    items, diag = attach(rt, candidates(), 1_030_000_000, 2)
    assert diag.skip_reason == "fresh_identity_challenge"
    assert not rt.memory.update(items).visible
