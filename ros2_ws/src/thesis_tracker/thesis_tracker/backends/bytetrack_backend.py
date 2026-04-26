"""ByteTrack backend.

ByteTrack uses low-confidence detections to rescue tracks during
occlusions and challenging conditions with a tracked/lost/removed state
machine and duplicate-track cleanup.
"""
from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass
from enum import IntEnum

from . import BBox, TrackOutput
from ..sort_tracker import KalmanBox, iou, hungarian_match_iou


class TrackState(IntEnum):
    Tracked = 1
    Lost = 2
    Removed = 3


@dataclass
class ByteTrackTrack:
    """ByteTrack per-track state."""
    track_id: int
    kf: KalmanBox
    score: float
    state: TrackState = TrackState.Tracked
    is_activated: bool = False
    start_frame: int = 0
    frame_id: int = 0
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    tracklet_len: int = 0

    def predict(self) -> None:
        """Predict next state."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1

    def activate(self, frame_id: int) -> None:
        self.state = TrackState.Tracked
        self.is_activated = True
        self.start_frame = int(frame_id)
        self.frame_id = int(frame_id)
        self.hits = 1
        self.tracklet_len = 1
        self.time_since_update = 0

    def update(self, bbox: BBox, score: float, frame_id: int) -> None:
        """Update with new observation."""
        self.kf.update(bbox)
        self.score = score
        self.state = TrackState.Tracked
        self.is_activated = True
        self.hits += 1
        self.frame_id = int(frame_id)
        self.time_since_update = 0
        self.tracklet_len += 1

    def re_activate(self, bbox: BBox, score: float, frame_id: int, new_id: int | None = None) -> None:
        self.update(bbox, score, frame_id)
        if new_id is not None:
            self.track_id = int(new_id)

    def mark_lost(self) -> None:
        self.state = TrackState.Lost

    def mark_removed(self) -> None:
        self.state = TrackState.Removed

    def bbox(self) -> BBox:
        """Get current bounding box."""
        return self.kf.bbox()


class ByteTrackBackend:
    """ByteTrack tracker backend."""

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        det_thresh: float = 0.1,
        second_match_thresh: float = 0.5,
        centre_gate: float = 200.0,
        unconfirmed_match_thresh: float = 0.7,
        duplicate_iou_threshold: float = 0.85,
    ):
        """
        Initialize ByteTrack.
        
        Args:
            track_thresh: High-confidence detection threshold
            match_thresh: First-stage association threshold in distance domain
            track_buffer: Max frames to keep lost tracks for recovery
            det_thresh: Detection floor for low-score association
            second_match_thresh: Second-stage threshold in distance domain
            centre_gate: Pixel centre-distance gate for associations
            unconfirmed_match_thresh: Matching threshold for unconfirmed tracks
            duplicate_iou_threshold: Duplicate prune threshold (IoU)
        """
        self.track_thresh = float(track_thresh)
        self.match_thresh = float(match_thresh)
        self.track_buffer = int(track_buffer)
        self.det_thresh = float(det_thresh)
        self.second_match_thresh = float(second_match_thresh)
        self.centre_gate = float(centre_gate)
        self.unconfirmed_match_thresh = float(unconfirmed_match_thresh)
        self.duplicate_iou_threshold = float(duplicate_iou_threshold)

        self._next_id = 1
        self.frame_id = 0
        self.tracked_tracks: List[ByteTrackTrack] = []
        self.lost_tracks: List[ByteTrackTrack] = []
        self.removed_tracks: List[ByteTrackTrack] = []

    def reset(self) -> None:
        """Reset tracker state."""
        self.tracked_tracks.clear()
        self.lost_tracks.clear()
        self.removed_tracks.clear()
        self._next_id = 1
        self.frame_id = 0

    def _next_track_id(self) -> int:
        tid = self._next_id
        self._next_id += 1
        return tid

    @staticmethod
    def _join_tracks(a: List[ByteTrackTrack], b: List[ByteTrackTrack]) -> List[ByteTrackTrack]:
        out: List[ByteTrackTrack] = []
        seen: set[int] = set()
        for tr in a + b:
            if tr.track_id in seen:
                continue
            seen.add(tr.track_id)
            out.append(tr)
        return out

    @staticmethod
    def _sub_tracks(a: List[ByteTrackTrack], b: List[ByteTrackTrack]) -> List[ByteTrackTrack]:
        remove_ids = {tr.track_id for tr in b}
        return [tr for tr in a if tr.track_id not in remove_ids]

    def _remove_duplicate_tracks(
        self,
        tracked: List[ByteTrackTrack],
        lost: List[ByteTrackTrack],
    ) -> Tuple[List[ByteTrackTrack], List[ByteTrackTrack]]:
        if not tracked or not lost:
            return tracked, lost

        remove_tracked: set[int] = set()
        remove_lost: set[int] = set()
        for ti, ta in enumerate(tracked):
            ba = ta.bbox()
            len_a = ta.frame_id - ta.start_frame
            for li, lb in enumerate(lost):
                ov = iou(ba, lb.bbox())
                if ov < self.duplicate_iou_threshold:
                    continue
                len_b = lb.frame_id - lb.start_frame
                if len_a > len_b:
                    remove_lost.add(li)
                else:
                    remove_tracked.add(ti)

        tracked = [t for idx, t in enumerate(tracked) if idx not in remove_tracked]
        lost = [t for idx, t in enumerate(lost) if idx not in remove_lost]
        return tracked, lost

    def _distance_thresh_to_iou_thresh(self, distance_thresh: float) -> float:
        # ByteTrack thresholds are commonly stated in distance space.
        return max(0.0, min(1.0, 1.0 - float(distance_thresh)))

    def _match(
        self,
        tracks: List[ByteTrackTrack],
        dets: List[Tuple[BBox, float]],
        distance_thresh: float,
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        track_boxes = [tr.bbox() for tr in tracks]
        det_boxes = [d[0] for d in dets]
        iou_thresh = self._distance_thresh_to_iou_thresh(distance_thresh)
        return hungarian_match_iou(track_boxes, det_boxes, iou_thresh, centre_gate=self.centre_gate)

    def _split_detections(
        self,
        dets_xyxy: List[BBox],
        scores: List[float]
    ) -> Tuple[List[Tuple[BBox, float]], List[Tuple[BBox, float]]]:
        """Split detections into high and low confidence."""
        high_dets: List[Tuple[BBox, float]] = []
        low_dets: List[Tuple[BBox, float]] = []

        for bbox, score in zip(dets_xyxy, scores):
            if score >= self.track_thresh:
                high_dets.append((bbox, score))
            elif score >= self.det_thresh:
                low_dets.append((bbox, score))

        return high_dets, low_dets

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int
    ) -> List[TrackOutput]:
        """
        Update ByteTrack with new detections.
        
        Args:
            dets_xyxy: Detection bounding boxes in xyxy format
            scores: Detection confidence scores
            frame_time_ns: Frame timestamp
            
        Returns:
            List of active tracks
        """
        del frame_time_ns

        self.frame_id += 1

        # Predict all candidate tracks (tracked + lost).
        for tr in self._join_tracks(self.tracked_tracks, self.lost_tracks):
            tr.predict()

        # Split detections by score as in ByteTrack.
        high_dets, low_dets = self._split_detections(dets_xyxy, scores)

        activated_tracks: List[ByteTrackTrack] = []
        refind_tracks: List[ByteTrackTrack] = []
        lost_tracks: List[ByteTrackTrack] = []
        removed_tracks: List[ByteTrackTrack] = []

        confirmed_tracked = [t for t in self.tracked_tracks if t.is_activated]
        unconfirmed = [t for t in self.tracked_tracks if not t.is_activated]

        track_pool = self._join_tracks(confirmed_tracked, self.lost_tracks)

        # Stage 1: associate tracked+lost pool with high-score detections.
        matches, u_track, u_det = self._match(track_pool, high_dets, self.match_thresh)
        for ti, di in matches:
            tr = track_pool[ti]
            bbox, score = high_dets[di]
            if tr.state == TrackState.Tracked:
                tr.update(bbox, score, self.frame_id)
                activated_tracks.append(tr)
            else:
                tr.re_activate(bbox, score, self.frame_id, new_id=None)
                refind_tracks.append(tr)

        unmatched_track_pool = [track_pool[i] for i in u_track]
        remaining_high = [high_dets[i] for i in u_det]

        # Stage 2: associate unmatched tracked with low-score detections.
        r_tracked = [t for t in unmatched_track_pool if t.state == TrackState.Tracked]
        matches_low, u_r_tracked, _u_low = self._match(r_tracked, low_dets, self.second_match_thresh)
        for ti, di in matches_low:
            tr = r_tracked[ti]
            bbox, score = low_dets[di]
            tr.update(bbox, score, self.frame_id)
            activated_tracks.append(tr)

        for idx in u_r_tracked:
            tr = r_tracked[idx]
            tr.mark_lost()
            lost_tracks.append(tr)

        # Stage 3: unconfirmed tracks with leftover high-score detections.
        matches_unc, u_unconfirmed, u_high_after_unc = self._match(
            unconfirmed,
            remaining_high,
            self.unconfirmed_match_thresh,
        )
        for ti, di in matches_unc:
            tr = unconfirmed[ti]
            bbox, score = remaining_high[di]
            tr.update(bbox, score, self.frame_id)
            tr.is_activated = True
            activated_tracks.append(tr)

        for idx in u_unconfirmed:
            tr = unconfirmed[idx]
            tr.mark_removed()
            removed_tracks.append(tr)

        # Stage 4: initialize brand new tracks from unmatched high-score detections.
        for di in u_high_after_unc:
            bbox, score = remaining_high[di]
            if score < self.track_thresh:
                continue
            kf = KalmanBox()
            kf.initiate(bbox)
            new_track = ByteTrackTrack(
                track_id=self._next_track_id(),
                kf=kf,
                score=score,
                hits=1,
                age=0,
                time_since_update=0,
                state=TrackState.Tracked,
                is_activated=True,
                start_frame=self.frame_id,
                frame_id=self.frame_id,
                tracklet_len=1,
            )
            new_track.activate(self.frame_id)
            activated_tracks.append(new_track)

        # Mark old lost tracks as removed when timeout expires.
        for tr in self.lost_tracks:
            if self.frame_id - tr.frame_id > self.track_buffer:
                tr.mark_removed()
                removed_tracks.append(tr)

        # Update tracked/lost/removed pools.
        self.tracked_tracks = [t for t in self.tracked_tracks if t.state == TrackState.Tracked]
        self.tracked_tracks = self._join_tracks(self.tracked_tracks, activated_tracks)
        self.tracked_tracks = self._join_tracks(self.tracked_tracks, refind_tracks)

        self.lost_tracks = self._sub_tracks(self.lost_tracks, self.tracked_tracks)
        self.lost_tracks.extend(lost_tracks)
        self.lost_tracks = [t for t in self.lost_tracks if t.state == TrackState.Lost]

        self.removed_tracks.extend(removed_tracks)

        self.tracked_tracks, self.lost_tracks = self._remove_duplicate_tracks(
            self.tracked_tracks,
            self.lost_tracks,
        )

        # Return activated tracked outputs only.
        outputs: List[TrackOutput] = []
        for tr in self.tracked_tracks:
            if tr.state != TrackState.Tracked:
                continue
            if tr.time_since_update != 0:
                continue
            outputs.append(TrackOutput(
                track_id=tr.track_id,
                bbox_xyxy=tr.bbox(),
                score=tr.score,
                age=tr.age,
                time_since_update=tr.time_since_update
            ))
        
        return outputs
