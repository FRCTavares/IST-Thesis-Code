"""Base interface for tracking backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Tuple

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2


@dataclass
class TrackOutput:
    """Unified track output format for all backends."""

    track_id: int
    bbox_xyxy: BBox  # x1, y1, x2, y2
    score: float
    age: int = 0
    time_since_update: int = 0


class TrackerBackend(Protocol):
    """Protocol defining the interface all tracker backends must implement."""

    def reset(self) -> None:
        """Reset the tracker state (clear all tracks)."""
        ...

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int
    ) -> List[TrackOutput]:
        """Update the tracker with one frame of detections.

        Args
        ----
        dets_xyxy:
            Detection bounding boxes in corner-coordinate form.
        scores:
            Detection confidence scores corresponding to the boxes.
        frame_time_ns:
            Source frame timestamp in nanoseconds.

        Returns
        -------
        list[TrackOutput]
            Active tracks produced by the backend.

        """
        ...
