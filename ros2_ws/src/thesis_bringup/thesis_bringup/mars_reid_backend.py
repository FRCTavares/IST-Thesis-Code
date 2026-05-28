"""MARS-small128 ReID backend for experimental TIM-V2Q MARS.

This module intentionally stays small and ROS-free. It wraps the already
validated DeepSORT MARS extractor so TIM-MARS uses the same crop/resize/model
path as the DeepSORT backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from thesis_bringup.target_memory import BBox
from thesis_tracker.backends.deepsort_core_backend import MarsSmall128Extractor


class MarsReIdBackend:
    """Thin wrapper around the DeepSORT MARS-small128 extractor."""

    def __init__(self, model_path: str | Path, batch_size: int = 32) -> None:
        self.model_path = str(model_path)
        self.batch_size = max(1, int(batch_size))
        self._extractor = MarsSmall128Extractor(
            self.model_path,
            batch_size=self.batch_size,
        )

    def encode(
        self,
        image_bgr: np.ndarray,
        boxes_xyxy: list[BBox],
    ) -> list[Optional[np.ndarray]]:
        """Return one L2-normalised 128D embedding per bbox, or None."""
        if image_bgr is None:
            return [None] * len(boxes_xyxy)

        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            return [None] * len(boxes_xyxy)

        return self._extractor.encode(image_bgr, boxes_xyxy)
