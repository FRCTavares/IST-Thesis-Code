"""ByteTrack backend.

ByteTrack uses low-confidence detections to rescue tracks during
occlusions and challenging conditions. Key innovation: two-stage matching
with high-conf and low-conf detections.
"""
from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass

from . import BBox, TrackOutput
from ..sort_tracker import KalmanBox, iou, hungarian_match_iou


@dataclass
class ByteTrackTrack:
    """ByteTrack track with score tracking."""
    track_id: int
    kf: KalmanBox
    score: float
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    tracklet_len: int = 0  # Number of frames track has existed
    
    def predict(self) -> None:
        """Predict next state."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1
        if self.time_since_update == 0:
            self.tracklet_len += 1
    
    def update(self, bbox: BBox, score: float) -> None:
        """Update with new observation."""
        self.kf.update(bbox)
        self.score = score
        self.hits += 1
        self.time_since_update = 0
        self.tracklet_len += 1
    
    def bbox(self) -> BBox:
        """Get current bounding box."""
        return self.kf.bbox()


class ByteTrackBackend:
    """ByteTrack tracker backend."""
    
    def __init__(
        self,
        track_thresh: float = 0.5,     # High confidence threshold
        match_thresh: float = 0.25,    # IoU threshold for first matching
        track_buffer: int = 30,        # Frames to keep lost tracks
        det_thresh: float = 0.2,       # Low confidence threshold
        second_match_thresh: float = 0.2  # IoU for second matching (lower)
    ):
        """
        Initialize ByteTrack.
        
        Args:
            track_thresh: High confidence threshold for detections
            match_thresh: Minimum IoU threshold for first-stage matching
            track_buffer: Max frames to keep lost tracks for recovery
            det_thresh: Low confidence threshold (below this, ignore detection)
            second_match_thresh: Minimum IoU threshold for second-stage matching with low-conf dets
        """
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self.det_thresh = det_thresh
        self.second_match_thresh = second_match_thresh
        
        self._next_id = 1
        self.tracked_tracks: List[ByteTrackTrack] = []  # Active confirmed tracks
        self.lost_tracks: List[ByteTrackTrack] = []     # Recently lost tracks
    
    def reset(self) -> None:
        """Reset tracker state."""
        self.tracked_tracks.clear()
        self.lost_tracks.clear()
        self._next_id = 1
    
    def _split_detections(
        self, 
        dets_xyxy: List[BBox], 
        scores: List[float]
    ) -> Tuple[List[Tuple[BBox, float]], List[Tuple[BBox, float]]]:
        """Split detections into high and low confidence."""
        high_dets = []
        low_dets = []
        
        for bbox, score in zip(dets_xyxy, scores):
            if score >= self.track_thresh:
                high_dets.append((bbox, score))
            elif score >= self.det_thresh:
                low_dets.append((bbox, score))
            # else: too low, ignore
        
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
        # Predict all tracks
        for tr in self.tracked_tracks:
            tr.predict()
        for tr in self.lost_tracks:
            tr.predict()
        
        # Split detections by confidence
        high_dets, low_dets = self._split_detections(dets_xyxy, scores)
        
        # First matching: tracked tracks with high-confidence detections
        if high_dets:
            track_bboxes = [tr.bbox() for tr in self.tracked_tracks]
            high_bboxes = [d[0] for d in high_dets]
            high_scores = [d[1] for d in high_dets]
            
            matches, unmatched_t, unmatched_d = hungarian_match_iou(
                track_bboxes, high_bboxes, self.match_thresh, centre_gate=200.0
            )
            
            # Update matched tracks
            for ti, di in matches:
                self.tracked_tracks[ti].update(high_bboxes[di], high_scores[di])
            
            # Move unmatched tracked tracks to lost
            unmatched_tracked = [self.tracked_tracks[i] for i in unmatched_t]
            self.tracked_tracks = [tr for i, tr in enumerate(self.tracked_tracks) if i not in unmatched_t]
            
            # Second matching: lost tracks + unmatched tracked with remaining high-conf dets
            remaining_high_dets = [high_dets[i] for i in unmatched_d]
        else:
            # No high-conf detections, move all tracked to lost
            unmatched_tracked = self.tracked_tracks.copy()
            self.tracked_tracks.clear()
            remaining_high_dets = []
        
        # Combine lost tracks with newly unmatched tracked
        candidate_tracks = self.lost_tracks + unmatched_tracked
        
        if candidate_tracks and remaining_high_dets:
            candidate_bboxes = [tr.bbox() for tr in candidate_tracks]
            remaining_bboxes = [d[0] for d in remaining_high_dets]
            remaining_scores = [d[1] for d in remaining_high_dets]
            
            matches2, unmatched_t2, unmatched_d2 = hungarian_match_iou(
                candidate_bboxes, remaining_bboxes, self.match_thresh, centre_gate=200.0
            )
            
            # Recover matched tracks
            for ti, di in matches2:
                candidate_tracks[ti].update(remaining_bboxes[di], remaining_scores[di])
                self.tracked_tracks.append(candidate_tracks[ti])
            
            # Update lost tracks and remaining detections
            candidate_tracks = [tr for i, tr in enumerate(candidate_tracks) if i not in [m[0] for m in matches2]]
            remaining_high_dets = [remaining_high_dets[i] for i in unmatched_d2]
        
        # Third matching: remaining lost tracks with low-confidence detections
        # This is the key ByteTrack innovation: rescue tracks with low-conf dets
        if candidate_tracks and low_dets:
            candidate_bboxes = [tr.bbox() for tr in candidate_tracks]
            low_bboxes = [d[0] for d in low_dets]
            low_scores = [d[1] for d in low_dets]
            
            matches3, unmatched_t3, _ = hungarian_match_iou(
                candidate_bboxes, low_bboxes, self.second_match_thresh, centre_gate=200.0
            )
            
            # Recover tracks matched with low-conf dets
            for ti, di in matches3:
                candidate_tracks[ti].update(low_bboxes[di], low_scores[di])
                self.tracked_tracks.append(candidate_tracks[ti])
            
            # Update lost tracks
            candidate_tracks = [tr for i, tr in enumerate(candidate_tracks) if i not in [m[0] for m in matches3]]
        
        # Store remaining candidates as lost tracks
        self.lost_tracks = candidate_tracks
        
        # Create new tracks from remaining high-confidence detections
        for bbox, score in remaining_high_dets:
            kf = KalmanBox()
            kf.initiate(bbox)
            tid = self._next_id
            self._next_id += 1
            new_track = ByteTrackTrack(
                track_id=tid,
                kf=kf,
                score=score,
                hits=1,
                age=0,
                time_since_update=0
            )
            self.tracked_tracks.append(new_track)
        
        # Prune old lost tracks
        self.lost_tracks = [tr for tr in self.lost_tracks if tr.time_since_update <= self.track_buffer]
        
        # Return all active tracked tracks
        outputs = []
        for tr in self.tracked_tracks:
            outputs.append(TrackOutput(
                track_id=tr.track_id,
                bbox_xyxy=tr.bbox(),
                score=tr.score,
                age=tr.age,
                time_since_update=tr.time_since_update
            ))
        
        return outputs
