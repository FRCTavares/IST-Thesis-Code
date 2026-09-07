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


def runtime(enabled=True):
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


def initialized(enabled=True):
    rt = runtime(enabled)
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
