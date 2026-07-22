"""SORT (Simple Online and Realtime Tracking) backend."""

from __future__ import annotations

from typing import List

from thesis_tracker.core.sort_tracker import Sort

from . import BBox, TrackOutput


class SortBackend:
    """SORT tracker backend."""

    def __init__(
        self,
        iou_threshold: float = 0.18,
        max_age: int = 4,
        min_hits: int = 3,
        centre_gate: float = 200.0,
        gate_x: float | None = None,
        gate_y: float | None = None,
    ):
        """Initialize the SORT tracker backend.

        Parameters
        ----------
        iou_threshold:
            Minimum IoU required to match a track and detection.
        max_age:
            Maximum unmatched frames before deleting a track.
        min_hits:
            Minimum matched detections required for confirmation.
        centre_gate:
            Default center-distance gate in pixels.
        gate_x:
            Optional horizontal center-distance gate in pixels.
        gate_y:
            Optional vertical center-distance gate in pixels.

        """
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.centre_gate = centre_gate
        self.gate_x = gate_x
        self.gate_y = gate_y

        self.tracker = Sort(
            iou_thresh=iou_threshold,
            max_age=max_age,
            min_hits=min_hits,
            centre_gate=centre_gate,
            gate_x=gate_x,
            gate_y=gate_y,
        )

    def reset(self) -> None:
        """Reset tracker state."""
        self.tracker.tracks.clear()
        self.tracker._next_id = 1

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int
    ) -> List[TrackOutput]:
        """Update SORT with one frame of detections.

        Args
        ----
        dets_xyxy:
            Detection bounding boxes in corner-coordinate form.
        scores:
            Detection scores accepted for backend compatibility.
        frame_time_ns:
            Frame timestamp accepted for backend compatibility.

        Returns
        -------
        list[TrackOutput]
            Confirmed tracks matched in the current frame.

        """
        # SORT doesn't use scores or timestamps internally,
        # but we accept them for interface consistency
        sort_tracks = self.tracker.update(dets_xyxy, frame_id=None)

        # Convert to TrackOutput, filter to confirmed tracks only
        outputs = []
        for tr in sort_tracks:
            # SORT confirmation rule: hits >= min_hits AND recently matched
            confirmed = (tr.hits >= self.min_hits) and (tr.time_since_update == 0)
            if not confirmed:
                continue

            outputs.append(TrackOutput(
                track_id=tr.track_id,
                bbox_xyxy=tr.bbox(),
                score=0.0,  # SORT doesn't maintain detection scores
                age=tr.age,
                time_since_update=tr.time_since_update
            ))

        return outputs
