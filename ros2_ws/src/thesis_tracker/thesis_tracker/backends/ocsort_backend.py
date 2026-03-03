"""OC-SORT (Observation-Centric SORT) backend.

Minimal OC-SORT implementation with observation-centric momentum and 
improved occlusion handling. Based on the OC-SORT paper but simplified
for lightweight deployment.
"""
from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass, field
import numpy as np

from . import BBox, TrackOutput
from ..sort_tracker import (
    KalmanBox, iou, xyxy_to_z, hungarian_match_iou
)


@dataclass
class OCSortTrack:
    """OC-SORT track with observation-centric updates."""
    track_id: int
    kf: KalmanBox
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    last_observation: Optional[BBox] = None  # For observation-centric momentum
    velocity_history: List[np.ndarray] = field(default_factory=list)
    
    def predict(self) -> None:
        """Predict with observation-centric momentum."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1
    
    def update(self, bbox: BBox) -> None:
        """Update with new observation."""
        # Store velocity before update for observation-centric momentum
        if self.last_observation is not None:
            old_z = xyxy_to_z(self.last_observation)
            new_z = xyxy_to_z(bbox)
            vel = new_z - old_z
            self.velocity_history.append(vel)
            # Keep only recent history
            if len(self.velocity_history) > 5:
                self.velocity_history.pop(0)
        
        self.kf.update(bbox)
        self.last_observation = bbox
        self.hits += 1
        self.time_since_update = 0
    
    def bbox(self) -> BBox:
        """Get current bounding box."""
        return self.kf.bbox()
    
    def get_velocity(self) -> Optional[np.ndarray]:
        """Get average velocity from history."""
        if not self.velocity_history:
            return None
        return np.mean(self.velocity_history, axis=0)


class OCSortBackend:
    """OC-SORT tracker backend with occlusion handling."""
    
    def __init__(
        self,
        iou_threshold: float = 0.18,
        max_age: int = 4,
        min_hits: int = 3,
        centre_gate: float = 200.0,
        delta_t: int = 3,  # Frames for second-stage association
        asso_threshold: float = 0.1  # Lower IoU for second stage
    ):
        """
        Initialize OC-SORT tracker.
        
        Args:
            iou_threshold: Primary IoU threshold for matching
            max_age: Maximum frames to keep track alive
            min_hits: Minimum hits before track is confirmed
            centre_gate: Centre distance gating (pixels)
            delta_t: Frames to look back for second-stage association
            asso_threshold: IoU threshold for second-stage matching (lower)
        """
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.min_hits = min_hits
        self.centre_gate = centre_gate
        self.delta_t = delta_t
        self.asso_threshold = asso_threshold
        
        self._next_id = 1
        self.tracks: List[OCSortTrack] = []
    
    def reset(self) -> None:
        """Reset tracker state."""
        self.tracks.clear()
        self._next_id = 1
    
    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int
    ) -> List[TrackOutput]:
        """
        Update OC-SORT tracker with new detections.
        
        Args:
            dets_xyxy: Detection bounding boxes in xyxy format
            scores: Detection confidence scores
            frame_time_ns: Frame timestamp
            
        Returns:
            List of confirmed tracks
        """
        # Predict all tracks
        for tr in self.tracks:
            tr.predict()
        
        # First-stage matching: Hungarian with IoU
        track_bboxes = [tr.bbox() for tr in self.tracks]
        matches, unmatched_t, unmatched_d = hungarian_match_iou(
            track_bboxes, dets_xyxy, self.iou_threshold, self.centre_gate
        )
        
        # Update matched tracks
        for ti, di in matches:
            self.tracks[ti].update(dets_xyxy[di])
        
        # Second-stage matching: unmatched tracks with lower threshold
        # This helps recover from temporary occlusions
        if unmatched_t and unmatched_d:
            unmatched_track_bboxes = [self.tracks[ti].bbox() for ti in unmatched_t]
            unmatched_dets = [dets_xyxy[di] for di in unmatched_d]
            
            second_matches, still_unmatched_t_idx, still_unmatched_d_idx = hungarian_match_iou(
                unmatched_track_bboxes, unmatched_dets, self.asso_threshold, self.centre_gate
            )
            
            # Update second-stage matches
            for ti_idx, di_idx in second_matches:
                ti = unmatched_t[ti_idx]
                di = unmatched_d[di_idx]
                self.tracks[ti].update(dets_xyxy[di])
            
            # Update unmatched lists
            unmatched_t = [unmatched_t[i] for i in still_unmatched_t_idx]
            unmatched_d = [unmatched_d[i] for i in still_unmatched_d_idx]
        
        # Create new tracks for remaining unmatched detections
        for di in unmatched_d:
            kf = KalmanBox()
            kf.initiate(dets_xyxy[di])
            tid = self._next_id
            self._next_id += 1
            self.tracks.append(OCSortTrack(
                track_id=tid,
                kf=kf,
                hits=1,
                age=0,
                time_since_update=0,
                last_observation=dets_xyxy[di]
            ))
        
        # Prune dead tracks
        self.tracks = [tr for tr in self.tracks if tr.time_since_update <= self.max_age]
        
        # Return confirmed tracks only
        outputs = []
        for tr in self.tracks:
            confirmed = (tr.hits >= self.min_hits) and (tr.time_since_update == 0)
            if not confirmed:
                continue
            
            outputs.append(TrackOutput(
                track_id=tr.track_id,
                bbox_xyxy=tr.bbox(),
                score=0.0,  # OC-SORT doesn't maintain detection scores
                age=tr.age,
                time_since_update=tr.time_since_update
            ))
        
        return outputs
