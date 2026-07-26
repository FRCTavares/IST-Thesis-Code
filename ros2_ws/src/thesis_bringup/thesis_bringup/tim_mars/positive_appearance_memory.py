"""Protected and adaptive positive appearance memory for TIM-MARS.

The operator-selected anchor and trusted gallery provide independent identity
evidence. The adaptive prototype represents recent trusted appearance but must
not independently authorize risky ID-switch or long-gap recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from thesis_bringup.tim_mars.appearance_memory import (
    cosine_similarity,
    update_feature_memory,
)
from thesis_bringup.tim_mars.geometry_scoring import clamp01


@dataclass
class PositiveAppearanceMemory:
    """Separated positive identity representations and lineage trust."""

    protected_anchor: Any = None
    trusted_gallery: list[Any] = field(default_factory=list)
    adaptive_prototype: Any = None

    operator_track_id: int | None = None
    current_lineage_track_id: int | None = None
    current_lineage_supported: bool = False
    lineage_trusted: bool = False
    trusted_lock_streak: int = 0

    def clear(self) -> None:
        self.protected_anchor = None
        self.trusted_gallery = []
        self.adaptive_prototype = None
        self.operator_track_id = None
        self.current_lineage_track_id = None
        self.current_lineage_supported = False
        self.lineage_trusted = False
        self.trusted_lock_streak = 0

    def select_operator(
        self,
        *,
        track_id: int,
        appearance: Any,
    ) -> bool:
        """Start a new operator-authorized identity lineage."""
        self.clear()
        self.operator_track_id = int(track_id)
        self.current_lineage_track_id = int(track_id)
        self.current_lineage_supported = True
        self.lineage_trusted = False
        self.trusted_lock_streak = 0

        if appearance is None:
            return False

        self.protected_anchor = update_feature_memory(
            None,
            appearance,
            alpha=1.0,
        )
        self.adaptive_prototype = update_feature_memory(
            None,
            appearance,
            alpha=1.0,
        )
        self.trusted_lock_streak = 1
        return self.protected_anchor is not None

    @property
    def has_any(self) -> bool:
        return bool(
            self.protected_anchor is not None
            or self.trusted_gallery
            or self.adaptive_prototype is not None
        )

    def similarities(
        self,
        appearance: Any,
    ) -> tuple[float, float, float]:
        if appearance is None:
            return 0.0, 0.0, 0.0

        anchor_similarity = (
            clamp01(
                cosine_similarity(
                    self.protected_anchor,
                    appearance,
                )
            )
            if self.protected_anchor is not None
            else 0.0
        )

        gallery_similarity = max(
            (
                clamp01(
                    cosine_similarity(
                        prototype,
                        appearance,
                    )
                )
                for prototype in self.trusted_gallery
            ),
            default=0.0,
        )

        adaptive_similarity = (
            clamp01(
                cosine_similarity(
                    self.adaptive_prototype,
                    appearance,
                )
            )
            if self.adaptive_prototype is not None
            else 0.0
        )

        return (
            float(anchor_similarity),
            float(gallery_similarity),
            float(adaptive_similarity),
        )

    def effective_similarity(
        self,
        *,
        appearance: Any,
        protected_only: bool,
    ) -> tuple[float, str, float, float, float]:
        (
            anchor_similarity,
            gallery_similarity,
            adaptive_similarity,
        ) = self.similarities(appearance)

        if gallery_similarity > anchor_similarity:
            protected_similarity = gallery_similarity
            protected_source = "trusted_gallery"
        else:
            protected_similarity = anchor_similarity
            protected_source = "protected_anchor"

        if protected_only:
            if protected_similarity <= 0.0:
                source = "none"
            else:
                source = protected_source

            return (
                protected_similarity,
                source,
                anchor_similarity,
                gallery_similarity,
                adaptive_similarity,
            )

        if adaptive_similarity > protected_similarity:
            similarity = adaptive_similarity
            source = (
                "adaptive_prototype"
                if adaptive_similarity > 0.0
                else "none"
            )
        else:
            similarity = protected_similarity
            source = (
                protected_source
                if protected_similarity > 0.0
                else "none"
            )

        return (
            similarity,
            source,
            anchor_similarity,
            gallery_similarity,
            adaptive_similarity,
        )

    def begin_reacquired_lineage(
        self,
        *,
        track_id: int,
        independently_supported: bool,
    ) -> None:
        self.current_lineage_track_id = int(track_id)
        self.current_lineage_supported = bool(
            independently_supported
        )
        self.lineage_trusted = False
        self.trusted_lock_streak = 0

    def observe_locked(
        self,
        *,
        track_id: int,
        required_frames: int,
    ) -> bool:
        if (
            self.current_lineage_track_id is None
            or int(track_id)
            != int(self.current_lineage_track_id)
            or not self.current_lineage_supported
        ):
            self.lineage_trusted = False
            self.trusted_lock_streak = 0
            return False

        self.trusted_lock_streak += 1
        required = max(1, int(required_frames))

        if self.trusted_lock_streak >= required:
            self.lineage_trusted = True

        return self.lineage_trusted

    def bootstrap_operator_anchor(
        self,
        *,
        track_id: int,
        appearance: Any,
    ) -> bool:
        """Create the first anchor only from operator-authorized continuity."""
        if self.protected_anchor is not None:
            return False
        if self.operator_track_id is None:
            return False
        if int(track_id) != int(self.operator_track_id):
            return False
        if (
            self.current_lineage_track_id is None
            or int(track_id) != int(self.current_lineage_track_id)
            or not self.current_lineage_supported
        ):
            return False
        if appearance is None:
            return False

        self.protected_anchor = update_feature_memory(
            None,
            appearance,
            alpha=1.0,
        )
        self.adaptive_prototype = update_feature_memory(
            None,
            appearance,
            alpha=1.0,
        )
        self.current_lineage_track_id = int(track_id)
        self.current_lineage_supported = True
        self.lineage_trusted = False
        self.trusted_lock_streak = 1

        return self.protected_anchor is not None

    def update_trusted(
        self,
        *,
        appearance: Any,
        alpha: float,
        gallery_max_entries: int,
    ) -> bool:
        if not self.lineage_trusted:
            return False
        if appearance is None:
            return False

        updated = update_feature_memory(
            self.adaptive_prototype,
            appearance,
            alpha=alpha,
        )
        if updated is None:
            return False

        self.adaptive_prototype = updated

        similarities = [
            clamp01(
                cosine_similarity(
                    prototype,
                    appearance,
                )
            )
            for prototype in (
                [self.protected_anchor]
                + list(self.trusted_gallery)
            )
            if prototype is not None
        ]

        max_existing_similarity = max(
            similarities,
            default=0.0,
        )

        if max_existing_similarity < 0.98:
            prototype = update_feature_memory(
                None,
                appearance,
                alpha=1.0,
            )
            if prototype is not None:
                self.trusted_gallery.append(prototype)

                max_entries = max(
                    0,
                    int(gallery_max_entries),
                )
                if max_entries == 0:
                    self.trusted_gallery = []
                elif len(self.trusted_gallery) > max_entries:
                    self.trusted_gallery = (
                        self.trusted_gallery[-max_entries:]
                    )

        return True

    def protected_reference(self) -> Any:
        if self.protected_anchor is not None:
            return self.protected_anchor
        if self.trusted_gallery:
            return self.trusted_gallery[0]
        return None


__all__ = ["PositiveAppearanceMemory"]
