"""Canonical fragment-safety regressions for Issue #17."""

from pathlib import Path
from typing import Any

import numpy as np

from thesis_bringup.tim_mars.hard_negative_memory import (
    HardNegativeEntry,
)
from thesis_bringup.tim_mars.target_memory import (
    TargetIdentityMemory,
)
from thesis_bringup.tim_mars.types import (
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)
import yaml


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "tim_mars_canonical.yaml"
)


def feat(values: list[float]) -> np.ndarray:
    """Return a normalised appearance vector."""
    vector = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError("Appearance vector must be non-zero.")
    return vector / norm


def tr(
    track_id: int,
    bbox: tuple[float, float, float, float],
    appearance: np.ndarray,
) -> CandidateTrack:
    """Build a candidate for the focused identity tests."""
    return CandidateTrack(
        track_id=track_id,
        bbox=bbox,
        score=0.95,
        appearance=appearance,
    )


def _find_canonical_parameters(value: Any) -> dict[str, Any]:
    """Find the ROS parameter mapping in the canonical YAML."""
    if isinstance(value, dict):
        if "hard_negative_max_positive_similarity" in value:
            return value

        for child in value.values():
            try:
                return _find_canonical_parameters(child)
            except LookupError:
                continue

    if isinstance(value, list):
        for child in value:
            try:
                return _find_canonical_parameters(child)
            except LookupError:
                continue

    raise LookupError(
        "Canonical hard-negative parameters were not found."
    )


def canonical_fragment_cfg() -> TargetMemoryConfig:
    """Build the focused policy from the real canonical YAML."""
    document = yaml.safe_load(
        CONFIG_PATH.read_text(encoding="utf-8")
    )
    parameters = _find_canonical_parameters(document)
    fields = TargetMemoryConfig.__dataclass_fields__

    protected_policy_names = {
        "appearance_protected_memory_enabled",
        "appearance_trusted_gallery_max_entries",
        "appearance_gallery_min_anchor_similarity",
        "appearance_trusted_lock_frames_before_update",
        "same_id_hijack_protection_enabled",
    }

    canonical_policy = {
        name: value
        for name, value in parameters.items()
        if (
            name in fields
            and (
                name.startswith("hard_negative_")
                or name in protected_policy_names
            )
        )
    }

    return TargetMemoryConfig(
        image_width=640,
        image_height=480,
        appearance_enabled=True,
        appearance_ambiguous_only=True,
        appearance_update_alpha=0.0,
        appearance_conservative_enabled=True,
        appearance_conservative_require_appearance=False,
        appearance_conservative_min_similarity=0.65,
        appearance_conservative_margin=0.05,
        **canonical_policy,
    )


def confirmation_observations(
    cfg: TargetMemoryConfig,
) -> int:
    """Return the canonical repeated-observation requirement."""
    return max(
        1,
        int(cfg.hard_negative_confirm_observations),
    )


def establish_trusted_lineage(
    tim: TargetIdentityMemory,
    appearance: np.ndarray,
    *,
    track_id: int = 1,
) -> None:
    """Advance accepted same-ID frames until protected lineage is trusted."""
    maximum_updates = max(
        2,
        int(
            tim.cfg
            .appearance_trusted_lock_frames_before_update
        )
        + 2,
    )

    for index in range(maximum_updates):
        if tim._positive_appearance.lineage_trusted:
            break

        offset = float(index)
        output = tim.update(
            [
                tr(
                    track_id,
                    (
                        101.0 + offset,
                        100.0,
                        161.0 + offset,
                        240.0,
                    ),
                    appearance,
                )
            ]
        )

        assert output.state == TargetState.LOCKED
        assert output.target_track_id == track_id

    assert tim._positive_appearance.protected_anchor is not None
    assert tim._positive_appearance.lineage_trusted


def assert_negative_memory_empty(
    tim: TargetIdentityMemory,
) -> None:
    """Require both pending and committed negative memory to be empty."""
    assert len(tim._hard_negative_memory) == 0
    assert tim._hard_negative_memory.pending_entries == ()


def test_canonical_profile_excludes_target_like_fragment_from_negative_memory():
    """Reject a near-duplicate under the actual canonical profile."""
    selected = feat([1.0, 0.0, 0.0])
    target_fragment = feat([0.995, 0.100, 0.0])
    cfg = canonical_fragment_cfg()
    tim = TargetIdentityMemory(cfg)

    tim.select(
        tr(
            1,
            (100.0, 100.0, 160.0, 240.0),
            selected,
        )
    )
    establish_trusted_lineage(tim, selected)

    output = None
    for index in range(confirmation_observations(cfg)):
        offset = float(index)
        output = tim.update(
            [
                tr(
                    1,
                    (
                        102.0 + offset,
                        100.0,
                        162.0 + offset,
                        240.0,
                    ),
                    selected,
                ),
                tr(
                    20 + index,
                    (
                        104.0 + offset,
                        101.0,
                        164.0 + offset,
                        241.0,
                    ),
                    target_fragment,
                ),
            ]
        )

    assert output is not None
    assert output.state == TargetState.LOCKED
    assert output.target_track_id == 1
    assert_negative_memory_empty(tim)


def test_protected_anchor_excludes_fragment_after_selected_pose_shift():
    """Protect trusted history when the current selected pose changes."""
    protected_anchor = feat([1.0, 0.0, 0.0])
    shifted_selected = feat([0.800, 0.600, 0.0])
    anchor_like_fragment = feat([0.995, 0.100, 0.0])
    cfg = canonical_fragment_cfg()
    tim = TargetIdentityMemory(cfg)

    tim.select(
        tr(
            1,
            (100.0, 100.0, 160.0, 240.0),
            protected_anchor,
        )
    )

    establish_trusted_lineage(
        tim,
        protected_anchor,
    )
    assert tim._positive_appearance.protected_anchor is not None

    output = None
    for index in range(confirmation_observations(cfg)):
        offset = float(index)
        output = tim.update(
            [
                tr(
                    1,
                    (
                        104.0 + offset,
                        100.0,
                        164.0 + offset,
                        240.0,
                    ),
                    shifted_selected,
                ),
                tr(
                    30 + index,
                    (
                        106.0 + offset,
                        101.0,
                        166.0 + offset,
                        241.0,
                    ),
                    anchor_like_fragment,
                ),
            ]
        )

    assert output is not None
    assert output.state == TargetState.LOCKED
    assert output.target_track_id == 1
    assert_negative_memory_empty(tim)


def test_trusted_gallery_excludes_target_like_fragment():
    """Protect recent trusted target history as well as the anchor."""
    protected_anchor = feat([1.0, 0.0, 0.0])
    trusted_pose = feat([0.600, 0.800, 0.0])
    current_selected = feat([0.900, -0.435, 0.0])
    gallery_like_fragment = feat([0.660, 0.750, 0.0])
    cfg = canonical_fragment_cfg()
    tim = TargetIdentityMemory(cfg)

    tim.select(
        tr(
            1,
            (100.0, 100.0, 160.0, 240.0),
            protected_anchor,
        )
    )
    establish_trusted_lineage(
        tim,
        protected_anchor,
    )

    tim._positive_appearance.trusted_gallery = [
        trusted_pose.copy()
    ]

    output = None
    for index in range(confirmation_observations(cfg)):
        offset = float(index)
        output = tim.update(
            [
                tr(
                    1,
                    (
                        104.0 + offset,
                        100.0,
                        164.0 + offset,
                        240.0,
                    ),
                    current_selected,
                ),
                tr(
                    50 + index,
                    (
                        190.0 + offset,
                        100.0,
                        250.0 + offset,
                        240.0,
                    ),
                    gallery_like_fragment,
                ),
            ]
        )

    assert output is not None
    assert output.state == TargetState.LOCKED
    assert output.target_track_id == 1

    fragment_scores = [
        score
        for score in output.all_scores
        if score.track_id != 1
    ]
    assert len(fragment_scores) == 1

    fragment_score = fragment_scores[0]
    assert fragment_score.trusted_gallery_similarity > 0.99
    assert fragment_score.protected_anchor_similarity < 0.75
    assert_negative_memory_empty(tim)


def test_canonical_uninterrupted_same_id_survives_negative_conflict():
    """Preserve strong uninterrupted same-ID continuity only while LOCKED."""
    selected = feat([1.0, 0.0, 0.0])
    learned_distractor = feat([0.600, 0.800, 0.0])
    shifted_selected = feat([0.660, 0.750, 0.0])
    cfg = canonical_fragment_cfg()
    tim = TargetIdentityMemory(cfg)

    tim.select(
        tr(
            1,
            (100.0, 100.0, 160.0, 240.0),
            selected,
        )
    )
    establish_trusted_lineage(tim, selected)

    # Admission and repeated-observation behaviour are tested separately
    # above. Seed one provenance-bearing negative here so this test isolates
    # candidate rejection and uninterrupted same-ID continuity.
    tim._hard_negative_memory._memory.append(
        HardNegativeEntry(
            appearance=learned_distractor,
            source_track_ids=(40, 41),
            selected_track_ids=(1,),
            source="trusted_locked_distractor",
            observations=2,
            positive_similarity=0.80,
            geometry_strength=0.80,
        )
    )

    assert len(tim._hard_negative_memory) == 1
    assert (
        tim._hard_negative_memory
        .entries[0]
        .observations
        == 2
    )

    continued = tim.update(
        [
            tr(
                1,
                (104.0, 100.0, 164.0, 240.0),
                shifted_selected,
            )
        ]
    )

    assert continued.best_score is not None
    assert continued.best_score.track_id == 1
    assert continued.best_score.hard_negative_reject
    assert continued.state == TargetState.LOCKED
    assert continued.target_track_id == 1
    assert continued.visible
    assert continued.control_valid
