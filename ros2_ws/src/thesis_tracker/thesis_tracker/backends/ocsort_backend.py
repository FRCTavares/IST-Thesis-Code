"""OC-SORT backend.

Implements observation-centric association with velocity-direction consistency
and observation-centric recovery updates for missed frames.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from . import BBox, TrackOutput
from .. import sort_tracker
from ..sort_tracker import KalmanBox, iou


@dataclass
class OCSortTrack:
    """OC-SORT track with observation-centric history and momentum."""
    track_id: int
    kf: KalmanBox
    score: float
    delta_t: int
    hits: int = 1
    age: int = 0
    time_since_update: int = 0
    hit_streak: int = 1
    last_observation: Optional[BBox] = None
    observations: Dict[int, BBox] = field(default_factory=dict)
    velocity: np.ndarray = field(default_factory=lambda: np.zeros((2,), dtype=np.float32))
    
    def predict(self) -> None:
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
    
    def _center(self, bbox: BBox) -> np.ndarray:
        x1, y1, x2, y2 = bbox
        return np.asarray([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np.float32)

    def _observation_at_delta_t(self) -> Optional[Tuple[int, BBox]]:
        if not self.observations:
            return None
        target_age = max(0, self.age - int(max(1, self.delta_t)))
        candidate_ages = [age for age in self.observations if age <= target_age]
        if candidate_ages:
            age = max(candidate_ages)
            return age, self.observations[age]
        age = min(self.observations.keys())
        return age, self.observations[age]

    def update(self, bbox: BBox, score: float) -> None:
        """Update with a real observation and refresh momentum state."""
        prev_obs = self._observation_at_delta_t()
        if prev_obs is not None:
            prev_age, prev_bbox = prev_obs
            dt = max(1, self.age - int(prev_age))
            velocity = self._center(bbox) - self._center(prev_bbox)
            self.velocity = velocity / float(dt)

        self.kf.update(bbox)
        self.last_observation = bbox
        self.observations[self.age] = bbox
        self.score = float(score)
        self.hits += 1
        self.hit_streak += 1
        self.time_since_update = 0
    
    def bbox(self) -> BBox:
        """Get current bounding box."""
        return self.kf.bbox()
    
    def recover_with_virtual_observations(self, bbox: BBox, score: float) -> None:
        """Re-update with linearly interpolated observations across a miss gap."""
        if self.last_observation is None or self.time_since_update <= 1:
            self.update(bbox, score)
            return

        start = np.asarray(self.last_observation, dtype=np.float32)
        end = np.asarray(bbox, dtype=np.float32)
        missed = int(self.time_since_update - 1)
        for step in range(1, missed + 1):
            alpha = float(step) / float(missed + 1)
            interp = (1.0 - alpha) * start + alpha * end
            interp_bbox = tuple(float(v) for v in interp.tolist())
            self.kf.update(interp_bbox)

        self.update(bbox, score)


def _center(bbox: BBox) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return np.asarray([(x1 + x2) * 0.5, (y1 + y2) * 0.5], dtype=np.float32)


def _linear_assignment(cost_matrix: np.ndarray) -> List[Tuple[int, int]]:
    if cost_matrix.size == 0:
        return []
    if sort_tracker.HAVE_SCIPY:
        rows, cols = sort_tracker.linear_sum_assignment(cost_matrix)
        return list(zip(rows.tolist(), cols.tolist()))

    entries = sorted(
        (float(cost_matrix[r, c]), r, c)
        for r in range(cost_matrix.shape[0])
        for c in range(cost_matrix.shape[1])
    )
    used_rows: set[int] = set()
    used_cols: set[int] = set()
    out: List[Tuple[int, int]] = []
    for _cost, row, col in entries:
        if row in used_rows or col in used_cols:
            continue
        used_rows.add(row)
        used_cols.add(col)
        out.append((row, col))
    return out


class OCSortBackend:
    """OC-SORT tracker backend with observation-centric association."""
    
    def __init__(
        self,
        iou_threshold: float = 0.18,
        max_age: int = 4,
        min_hits: int = 3,
        centre_gate: float = 200.0,
        delta_t: int = 3,  # Frames for second-stage association
        asso_threshold: float = 0.1,
        inertia: float = 0.2,
    ):
        """
        Initialize OC-SORT tracker.
        
        Args:
            iou_threshold: Primary IoU threshold for matching
            max_age: Maximum frames to keep track alive
            min_hits: Minimum hits before track is confirmed
            centre_gate: Centre distance gating (pixels)
            delta_t: Frames to look back for second-stage association
            asso_threshold: IoU threshold for observation-centric second-stage matching
            inertia: Velocity-direction consistency gain in first association
        """
        self.iou_threshold = float(iou_threshold)
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.centre_gate = float(centre_gate)
        self.delta_t = int(max(1, delta_t))
        self.asso_threshold = float(asso_threshold)
        self.inertia = float(max(0.0, inertia))
        
        self._next_id = 1
        self.tracks: List[OCSortTrack] = []
    
    def reset(self) -> None:
        """Reset tracker state."""
        self.tracks.clear()
        self._next_id = 1

    def _associate_with_velocity(
        self,
        track_indices: List[int],
        det_indices: List[int],
        dets_xyxy: List[BBox],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not track_indices or not det_indices:
            return [], track_indices, det_indices

        cost = np.full((len(track_indices), len(det_indices)), 1e5, dtype=np.float32)
        gate_sq = self.centre_gate * self.centre_gate

        for r, ti in enumerate(track_indices):
            tr = self.tracks[ti]
            pred_bbox = tr.bbox()
            pred_center = _center(pred_bbox)
            last_obs = tr.last_observation
            last_center = _center(last_obs) if last_obs is not None else pred_center
            speed = np.linalg.norm(tr.velocity)

            for c, di in enumerate(det_indices):
                det_bbox = dets_xyxy[di]
                det_center = _center(det_bbox)
                dxy = det_center - pred_center
                if float(dxy[0] * dxy[0] + dxy[1] * dxy[1]) > gate_sq:
                    continue

                iou_score = iou(pred_bbox, det_bbox)
                if iou_score < self.iou_threshold:
                    continue

                vdc = 0.0
                if speed > 1e-6:
                    obs_dir = det_center - last_center
                    obs_norm = np.linalg.norm(obs_dir)
                    if obs_norm > 1e-6:
                        cos_sim = float(np.dot(tr.velocity, obs_dir) / (speed * obs_norm))
                        vdc = max(0.0, cos_sim)

                affinity = iou_score + self.inertia * vdc
                cost[r, c] = 1.0 - float(affinity)

        assignment = _linear_assignment(cost)
        matched_rows: set[int] = set()
        matched_cols: set[int] = set()
        matches: List[Tuple[int, int]] = []

        for row, col in assignment:
            if cost[row, col] >= 1e4:
                continue
            ti = track_indices[row]
            di = det_indices[col]
            matches.append((ti, di))
            matched_rows.add(row)
            matched_cols.add(col)

        unmatched_t = [track_indices[i] for i in range(len(track_indices)) if i not in matched_rows]
        unmatched_d = [det_indices[i] for i in range(len(det_indices)) if i not in matched_cols]
        return matches, unmatched_t, unmatched_d

    def _associate_observation_centric(
        self,
        track_indices: List[int],
        det_indices: List[int],
        dets_xyxy: List[BBox],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        if not track_indices or not det_indices:
            return [], track_indices, det_indices

        cost = np.full((len(track_indices), len(det_indices)), 1e5, dtype=np.float32)
        gate_sq = self.centre_gate * self.centre_gate

        for r, ti in enumerate(track_indices):
            tr = self.tracks[ti]
            obs_bbox = tr.last_observation if tr.last_observation is not None else tr.bbox()
            obs_center = _center(obs_bbox)
            for c, di in enumerate(det_indices):
                det_bbox = dets_xyxy[di]
                det_center = _center(det_bbox)
                dxy = det_center - obs_center
                if float(dxy[0] * dxy[0] + dxy[1] * dxy[1]) > gate_sq:
                    continue
                ov = iou(obs_bbox, det_bbox)
                if ov < self.asso_threshold:
                    continue
                cost[r, c] = 1.0 - float(ov)

        assignment = _linear_assignment(cost)
        matched_rows: set[int] = set()
        matched_cols: set[int] = set()
        matches: List[Tuple[int, int]] = []

        for row, col in assignment:
            if cost[row, col] >= 1e4:
                continue
            ti = track_indices[row]
            di = det_indices[col]
            matches.append((ti, di))
            matched_rows.add(row)
            matched_cols.add(col)

        unmatched_t = [track_indices[i] for i in range(len(track_indices)) if i not in matched_rows]
        unmatched_d = [det_indices[i] for i in range(len(det_indices)) if i not in matched_cols]
        return matches, unmatched_t, unmatched_d
    
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
        del frame_time_ns

        # Predict all tracks.
        for tr in self.tracks:
            tr.predict()

        all_track_indices = list(range(len(self.tracks)))
        all_det_indices = list(range(len(dets_xyxy)))

        # Stage 1: prediction-centric association with velocity-direction consistency.
        matches, unmatched_t, unmatched_d = self._associate_with_velocity(
            all_track_indices,
            all_det_indices,
            dets_xyxy,
        )

        for ti, di in matches:
            score = float(scores[di]) if di < len(scores) else 0.0
            self.tracks[ti].update(dets_xyxy[di], score)

        # Stage 2: observation-centric recovery for unmatched tracks.
        if unmatched_t and unmatched_d:
            second_matches, unmatched_t, unmatched_d = self._associate_observation_centric(
                unmatched_t,
                unmatched_d,
                dets_xyxy,
            )
            for ti, di in second_matches:
                score = float(scores[di]) if di < len(scores) else 0.0
                self.tracks[ti].recover_with_virtual_observations(dets_xyxy[di], score)

        # Create new tracks for remaining unmatched detections
        for di in unmatched_d:
            kf = KalmanBox()
            kf.initiate(dets_xyxy[di])
            tid = self._next_id
            self._next_id += 1
            score = float(scores[di]) if di < len(scores) else 0.0
            self.tracks.append(OCSortTrack(
                track_id=tid,
                kf=kf,
                score=score,
                delta_t=self.delta_t,
                hits=1,
                age=0,
                time_since_update=0,
                last_observation=dets_xyxy[di]
            ))
            self.tracks[-1].observations[0] = dets_xyxy[di]
        
        # Prune dead tracks
        self.tracks = [tr for tr in self.tracks if tr.time_since_update <= self.max_age]

        # Return confirmed tracks only
        outputs = []
        for tr in self.tracks:
            confirmed = (
                tr.time_since_update == 0
                and (tr.hits >= self.min_hits or tr.age < self.min_hits)
            )
            if not confirmed:
                continue

            outputs.append(TrackOutput(
                track_id=tr.track_id,
                bbox_xyxy=tr.bbox(),
                score=float(tr.score),
                age=tr.age,
                time_since_update=tr.time_since_update
            ))

        return outputs
