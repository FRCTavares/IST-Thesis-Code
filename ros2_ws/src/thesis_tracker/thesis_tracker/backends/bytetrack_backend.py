"""Faithful ByteTrack backend.

Reference-aligned implementation of ByteTrack:
- 8D Kalman state in xyah form: [x, y, aspect, h, vx, vy, va, vh]
- high-score first association
- low-score second association
- unconfirmed track handling
- tracked/lost/removed state machine
- duplicate track cleanup

Adapted to local tracker backend interface:
    update(dets_xyxy, scores, frame_time_ns) -> list[TrackOutput]
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, List, Optional, Tuple

import numpy as np
from thesis_tracker.core import sort_tracker
from thesis_tracker.core.sort_tracker import iou_batch

from . import BBox, TrackOutput


class TrackState(IntEnum):
    """Enumerate the lifecycle states used by ByteTrack tracklets."""

    New = 0
    Tracked = 1
    Lost = 2
    Removed = 3


def tlbr_to_tlwh(tlbr: np.ndarray) -> np.ndarray:
    """Convert a top-left/bottom-right box to top-left/width/height form."""
    ret = np.asarray(tlbr, dtype=np.float64).copy()
    ret[2:] -= ret[:2]
    return ret


def tlwh_to_tlbr(tlwh: np.ndarray) -> np.ndarray:
    """Convert a top-left/width/height box to top-left/bottom-right form."""
    ret = np.asarray(tlwh, dtype=np.float64).copy()
    ret[2:] += ret[:2]
    return ret


def tlwh_to_xyah(tlwh: np.ndarray) -> np.ndarray:
    """Convert a box to center-x, center-y, aspect, and height form."""
    ret = np.asarray(tlwh, dtype=np.float64).copy()
    ret[:2] += ret[2:] / 2.0
    ret[2] /= max(1e-6, ret[3])
    return ret


def linear_assignment(
    cost_matrix: np.ndarray,
    thresh: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Solve a thresholded assignment problem in distance space.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        Matched pairs, unmatched rows, and unmatched columns.

    """
    if cost_matrix.size == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(cost_matrix.shape[0], dtype=int),
            np.arange(cost_matrix.shape[1], dtype=int),
        )

    if sort_tracker.HAVE_SCIPY:
        rows, cols = sort_tracker.linear_sum_assignment(cost_matrix)
        pairs = np.asarray(list(zip(rows, cols)), dtype=int)
    else:
        entries = sorted(
            (float(cost_matrix[r, c]), r, c)
            for r in range(cost_matrix.shape[0])
            for c in range(cost_matrix.shape[1])
        )
        used_r: set[int] = set()
        used_c: set[int] = set()
        out: List[Tuple[int, int]] = []
        for _cost, r, c in entries:
            if r in used_r or c in used_c:
                continue
            used_r.add(r)
            used_c.add(c)
            out.append((r, c))
        pairs = np.asarray(out, dtype=int)

    if pairs.size == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(cost_matrix.shape[0], dtype=int),
            np.arange(cost_matrix.shape[1], dtype=int),
        )

    matches: List[Tuple[int, int]] = []
    unmatched_rows = set(range(cost_matrix.shape[0]))
    unmatched_cols = set(range(cost_matrix.shape[1]))

    for r, c in pairs:
        if cost_matrix[r, c] > thresh:
            continue
        matches.append((int(r), int(c)))
        unmatched_rows.discard(int(r))
        unmatched_cols.discard(int(c))

    return (
        np.asarray(matches, dtype=int),
        np.asarray(sorted(unmatched_rows), dtype=int),
        np.asarray(sorted(unmatched_cols), dtype=int),
    )


def iou_distance(a_tracks: List["STrack"], b_tracks: List["STrack"]) -> np.ndarray:
    """Compute pairwise IoU distances between two tracklet collections."""
    if len(a_tracks) == 0 or len(b_tracks) == 0:
        return np.zeros((len(a_tracks), len(b_tracks)), dtype=np.float64)

    a_boxes = np.asarray([t.tlbr for t in a_tracks], dtype=np.float64)
    b_boxes = np.asarray([t.tlbr for t in b_tracks], dtype=np.float64)

    ious = iou_batch(a_boxes.astype(np.float32), b_boxes.astype(np.float32)).astype(np.float64)
    return 1.0 - ious


def fuse_score(dists: np.ndarray, detections: List["STrack"]) -> np.ndarray:
    """Fuse ByteTrack IoU distances with detection confidence scores."""
    if dists.size == 0:
        return dists

    iou_sim = 1.0 - dists
    det_scores = np.asarray([det.score for det in detections], dtype=np.float64)
    fuse_sim = iou_sim * det_scores.reshape(1, -1)
    return 1.0 - fuse_sim


class KalmanFilterXYAH:
    """Kalman filter used by ByteTrack/DeepSORT style trackers.

    State:
        [x, y, a, h, vx, vy, va, vh]
    Measurement:
        [x, y, a, h]
    """

    def __init__(self) -> None:
        """Initialize the constant-velocity XYAH motion and observation models."""
        ndim = 4
        dt = 1.0

        self._motion_mat = np.eye(2 * ndim, 2 * ndim, dtype=np.float64)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = dt

        self._update_mat = np.eye(ndim, 2 * ndim, dtype=np.float64)

        self._std_weight_position = 1.0 / 20.0
        self._std_weight_velocity = 1.0 / 160.0

    def initiate(self, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Initialize an XYAH state and covariance from a detection measurement."""
        mean_pos = measurement.astype(np.float64)
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        h = measurement[3]
        std = np.asarray(
            [
                2 * self._std_weight_position * h,
                2 * self._std_weight_position * h,
                1e-2,
                2 * self._std_weight_position * h,
                10 * self._std_weight_velocity * h,
                10 * self._std_weight_velocity * h,
                1e-5,
                10 * self._std_weight_velocity * h,
            ],
            dtype=np.float64,
        )
        covariance = np.diag(np.square(std))
        return mean, covariance

    def predict(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict the next XYAH state and covariance."""
        h = mean[3]
        std_pos = np.asarray(
            [
                self._std_weight_position * h,
                self._std_weight_position * h,
                1e-2,
                self._std_weight_position * h,
            ],
            dtype=np.float64,
        )
        std_vel = np.asarray(
            [
                self._std_weight_velocity * h,
                self._std_weight_velocity * h,
                1e-5,
                self._std_weight_velocity * h,
            ],
            dtype=np.float64,
        )
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

        mean = self._motion_mat @ mean
        covariance = self._motion_mat @ covariance @ self._motion_mat.T + motion_cov
        return mean, covariance

    def project(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Project an XYAH state distribution into measurement space."""
        h = mean[3]
        std = np.asarray(
            [
                self._std_weight_position * h,
                self._std_weight_position * h,
                1e-1,
                self._std_weight_position * h,
            ],
            dtype=np.float64,
        )
        innovation_cov = np.diag(np.square(std))

        projected_mean = self._update_mat @ mean
        projected_cov = self._update_mat @ covariance @ self._update_mat.T + innovation_cov
        return projected_mean, projected_cov

    def update(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurement: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Correct an XYAH state estimate with a measurement."""
        projected_mean, projected_cov = self.project(mean, covariance)

        kalman_gain = covariance @ self._update_mat.T @ np.linalg.inv(projected_cov)
        innovation = measurement - projected_mean

        new_mean = mean + kalman_gain @ innovation
        new_covariance = covariance - kalman_gain @ projected_cov @ kalman_gain.T
        return new_mean, new_covariance

    def multi_predict(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict a batch of XYAH states and covariances."""
        if len(mean) == 0:
            return mean, covariance

        out_mean = mean.copy()
        out_cov = covariance.copy()

        for i in range(len(out_mean)):
            out_mean[i], out_cov[i] = self.predict(out_mean[i], out_cov[i])

        return out_mean, out_cov


@dataclass
class STrack:
    """ByteTrack single track."""

    tlwh_in: np.ndarray
    score: float

    shared_kalman: ClassVar[KalmanFilterXYAH] = KalmanFilterXYAH()
    _next_id: ClassVar[int] = 1

    def __post_init__(self) -> None:
        """Initialize mutable state for a newly created ByteTrack tracklet."""
        self._tlwh = np.asarray(self.tlwh_in, dtype=np.float64)
        self.kalman_filter: Optional[KalmanFilterXYAH] = None
        self.mean: Optional[np.ndarray] = None
        self.covariance: Optional[np.ndarray] = None
        self.is_activated = False
        self.tracklet_len = 0
        self.track_id = 0
        self.state = TrackState.New
        self.frame_id = 0
        self.start_frame = 0

    @classmethod
    def reset_id(cls) -> None:
        """Reset the shared track identifier counter."""
        cls._next_id = 1

    @classmethod
    def next_id(cls) -> int:
        """Return the next shared track identifier."""
        tid = cls._next_id
        cls._next_id += 1
        return tid

    @property
    def end_frame(self) -> int:
        """Return the most recent frame associated with the tracklet."""
        return self.frame_id

    @property
    def tlwh(self) -> np.ndarray:
        """Return the current box in top-left/width/height form."""
        if self.mean is None:
            return self._tlwh.copy()

        ret = self.mean[:4].copy()
        ret[2] *= ret[3]
        ret[:2] -= ret[2:] / 2.0
        return ret

    @property
    def tlbr(self) -> np.ndarray:
        """Return the current box in top-left/bottom-right form."""
        return tlwh_to_tlbr(self.tlwh)

    def to_xyah(self) -> np.ndarray:
        """Return the current box as center-x, center-y, aspect, and height."""
        return tlwh_to_xyah(self.tlwh)

    def predict(self) -> None:
        """Advance this tracklet through the motion model."""
        if self.mean is None or self.covariance is None or self.kalman_filter is None:
            return

        mean_state = self.mean.copy()

        if self.state != TrackState.Tracked:
            mean_state[7] = 0.0

        self.mean, self.covariance = self.kalman_filter.predict(mean_state, self.covariance)

    @staticmethod
    def multi_predict(stracks: List["STrack"]) -> None:
        """Advance all initialized tracklets through the shared motion model."""
        if len(stracks) == 0:
            return

        valid = [s for s in stracks if s.mean is not None and s.covariance is not None]
        if len(valid) == 0:
            return

        multi_mean = np.asarray([s.mean.copy() for s in valid], dtype=np.float64)
        multi_covariance = np.asarray([s.covariance.copy() for s in valid], dtype=np.float64)

        for i, st in enumerate(valid):
            if st.state != TrackState.Tracked:
                multi_mean[i][7] = 0.0

        multi_mean, multi_covariance = STrack.shared_kalman.multi_predict(
            multi_mean,
            multi_covariance,
        )

        for i, st in enumerate(valid):
            st.mean = multi_mean[i]
            st.covariance = multi_covariance[i]

    def activate(self, kalman_filter: KalmanFilterXYAH, frame_id: int) -> None:
        """Activate a new tracklet from its initial detection."""
        self.kalman_filter = kalman_filter
        self.track_id = self.next_id()

        self.mean, self.covariance = self.kalman_filter.initiate(tlwh_to_xyah(self._tlwh))
        self.tracklet_len = 0
        self.state = TrackState.Tracked

        # Faithful ByteTrack: only initial-frame tracks are immediately activated.
        if frame_id == 1:
            self.is_activated = True

        self.frame_id = int(frame_id)
        self.start_frame = int(frame_id)

    def re_activate(self, new_track: "STrack", frame_id: int, new_id: bool = False) -> None:
        """Re-activate a lost tracklet from a matched detection."""
        assert self.kalman_filter is not None
        assert self.mean is not None
        assert self.covariance is not None

        self.mean, self.covariance = self.kalman_filter.update(
            self.mean,
            self.covariance,
            new_track.to_xyah(),
        )
        self.tracklet_len = 0
        self.state = TrackState.Tracked
        self.is_activated = True
        self.frame_id = int(frame_id)

        if new_id:
            self.track_id = self.next_id()

        self.score = float(new_track.score)

    def update(self, new_track: "STrack", frame_id: int) -> None:
        """Update a tracked tracklet from a matched detection."""
        assert self.kalman_filter is not None
        assert self.mean is not None
        assert self.covariance is not None

        self.frame_id = int(frame_id)
        self.tracklet_len += 1

        self.mean, self.covariance = self.kalman_filter.update(
            self.mean,
            self.covariance,
            new_track.to_xyah(),
        )
        self.state = TrackState.Tracked
        self.is_activated = True
        self.score = float(new_track.score)

    def mark_lost(self) -> None:
        """Mark the tracklet as lost."""
        self.state = TrackState.Lost

    def mark_removed(self) -> None:
        """Mark the tracklet as removed."""
        self.state = TrackState.Removed


def joint_stracks(a: List[STrack], b: List[STrack]) -> List[STrack]:
    """Merge two tracklet lists while preserving unique track identifiers."""
    exists: dict[int, int] = {}
    out: List[STrack] = []

    for t in a:
        exists[t.track_id] = 1
        out.append(t)

    for t in b:
        if not exists.get(t.track_id, 0):
            exists[t.track_id] = 1
            out.append(t)

    return out


def sub_stracks(a: List[STrack], b: List[STrack]) -> List[STrack]:
    """Remove tracklets whose identifiers occur in a second list."""
    stracks = {t.track_id: t for t in a}
    for t in b:
        if t.track_id in stracks:
            del stracks[t.track_id]
    return list(stracks.values())


def remove_duplicate_stracks(
    tracked: List[STrack],
    lost: List[STrack],
) -> Tuple[List[STrack], List[STrack]]:
    """Remove overlapping duplicates from tracked and lost tracklet lists."""
    pdist = iou_distance(tracked, lost)
    if pdist.size == 0:
        return tracked, lost

    pairs = np.where(pdist < 0.15)

    dup_tracked: list[int] = []
    dup_lost: list[int] = []

    for p, q in zip(*pairs):
        time_p = tracked[p].frame_id - tracked[p].start_frame
        time_q = lost[q].frame_id - lost[q].start_frame

        if time_p > time_q:
            dup_lost.append(q)
        else:
            dup_tracked.append(p)

    tracked_out = [t for i, t in enumerate(tracked) if i not in dup_tracked]
    lost_out = [t for i, t in enumerate(lost) if i not in dup_lost]
    return tracked_out, lost_out


class ByteTrackBackend:
    """Reference-aligned ByteTrack backend."""

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
        frame_rate: int = 30,
        low_thresh: float = 0.1,
        new_track_thresh: Optional[float] = None,
        second_match_thresh: float = 0.5,
        unconfirmed_match_thresh: float = 0.7,
        fuse_scores: bool = True,
        mot20: bool = False,
        min_box_area: float = 0.0,
        **_ignored,
    ) -> None:
        """Initialize ByteTrack thresholds, buffers, and state containers."""
        self.track_thresh = float(track_thresh)
        self.match_thresh = float(match_thresh)
        self.track_buffer = int(track_buffer)
        self.frame_rate = int(frame_rate)
        self.low_thresh = float(low_thresh)

        # Official ByteTrack uses track_thresh + 0.1 for new-track activation.
        self.new_track_thresh = (
            float(track_thresh) + 0.1 if new_track_thresh is None else float(new_track_thresh)
        )

        self.second_match_thresh = float(second_match_thresh)
        self.unconfirmed_match_thresh = float(unconfirmed_match_thresh)
        self.fuse_scores = bool(fuse_scores)
        self.mot20 = bool(mot20)
        self.min_box_area = float(min_box_area)

        self.buffer_size = int(float(frame_rate) / 30.0 * float(track_buffer))
        self.max_time_lost = self.buffer_size

        self.kalman_filter = KalmanFilterXYAH()

        self.tracked_stracks: List[STrack] = []
        self.lost_stracks: List[STrack] = []
        self.removed_stracks: List[STrack] = []

        self.frame_id = 0
        STrack.reset_id()

    def reset(self) -> None:
        """Reset all ByteTrack state and identifier counters."""
        self.tracked_stracks.clear()
        self.lost_stracks.clear()
        self.removed_stracks.clear()
        self.frame_id = 0
        self.kalman_filter = KalmanFilterXYAH()
        STrack.reset_id()

    @staticmethod
    def _to_detections(dets: np.ndarray, scores: np.ndarray) -> List[STrack]:
        if len(dets) == 0:
            return []
        return [
            STrack(tlbr_to_tlwh(tlbr), float(score))
            for tlbr, score in zip(dets, scores)
        ]

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int,
    ) -> List[TrackOutput]:
        """Associate detections for one frame and return active track outputs."""
        del frame_time_ns

        self.frame_id += 1

        activated_stracks: List[STrack] = []
        refind_stracks: List[STrack] = []
        lost_stracks: List[STrack] = []
        removed_stracks: List[STrack] = []

        if len(dets_xyxy) == 0:
            bboxes = np.empty((0, 4), dtype=np.float64)
            score_arr = np.empty((0,), dtype=np.float64)
        else:
            bboxes = np.asarray(dets_xyxy, dtype=np.float64).reshape(-1, 4)
            score_arr = np.asarray(scores, dtype=np.float64).reshape(-1)

            if len(score_arr) != len(bboxes):
                # Conservative fallback. Bad score input should not crash tracking.
                score_arr = np.ones((len(bboxes),), dtype=np.float64)

        # Faithful score split.
        remain_inds = score_arr > self.track_thresh
        inds_low = score_arr > self.low_thresh
        inds_high = score_arr < self.track_thresh
        inds_second = np.logical_and(inds_low, inds_high)

        dets = bboxes[remain_inds]
        scores_keep = score_arr[remain_inds]

        dets_second = bboxes[inds_second]
        scores_second = score_arr[inds_second]

        detections = self._to_detections(dets, scores_keep)
        detections_second = self._to_detections(dets_second, scores_second)

        unconfirmed: List[STrack] = []
        tracked_stracks: List[STrack] = []

        for track in self.tracked_stracks:
            if not track.is_activated:
                unconfirmed.append(track)
            else:
                tracked_stracks.append(track)

        # Step 1: first association with high-score detections.
        strack_pool = joint_stracks(tracked_stracks, self.lost_stracks)
        STrack.multi_predict(strack_pool)

        dists = iou_distance(strack_pool, detections)
        if not self.mot20 and self.fuse_scores:
            dists = fuse_score(dists, detections)

        matches, u_track, u_detection = linear_assignment(dists, thresh=self.match_thresh)

        for itracked, idet in matches:
            track = strack_pool[int(itracked)]
            det = detections[int(idet)]

            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        # Step 2: second association with low-score detections.
        r_tracked_stracks = [
            strack_pool[int(i)]
            for i in u_track
            if strack_pool[int(i)].state == TrackState.Tracked
        ]

        dists = iou_distance(r_tracked_stracks, detections_second)
        matches, u_track_second, _u_detection_second = linear_assignment(
            dists,
            thresh=self.second_match_thresh,
        )

        for itracked, idet in matches:
            track = r_tracked_stracks[int(itracked)]
            det = detections_second[int(idet)]

            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        for it in u_track_second:
            track = r_tracked_stracks[int(it)]
            if track.state != TrackState.Lost:
                track.mark_lost()
                lost_stracks.append(track)

        # Step 3: unconfirmed tracks, usually one-frame tracks.
        detections_left = [detections[int(i)] for i in u_detection]

        dists = iou_distance(unconfirmed, detections_left)
        if not self.mot20 and self.fuse_scores:
            dists = fuse_score(dists, detections_left)

        matches, u_unconfirmed, u_detection_left = linear_assignment(
            dists,
            thresh=self.unconfirmed_match_thresh,
        )

        for itracked, idet in matches:
            unconfirmed[int(itracked)].update(detections_left[int(idet)], self.frame_id)
            activated_stracks.append(unconfirmed[int(itracked)])

        for it in u_unconfirmed:
            track = unconfirmed[int(it)]
            track.mark_removed()
            removed_stracks.append(track)

        # Step 4: initialise new tracks.
        for inew in u_detection_left:
            track = detections_left[int(inew)]

            if track.score < self.new_track_thresh:
                continue

            track.activate(self.kalman_filter, self.frame_id)
            activated_stracks.append(track)

        # Step 5: remove old lost tracks.
        for track in self.lost_stracks:
            if self.frame_id - track.end_frame > self.max_time_lost:
                track.mark_removed()
                removed_stracks.append(track)

        # Step 6: update state pools.
        self.tracked_stracks = [
            t for t in self.tracked_stracks
            if t.state == TrackState.Tracked
        ]
        self.tracked_stracks = joint_stracks(self.tracked_stracks, activated_stracks)
        self.tracked_stracks = joint_stracks(self.tracked_stracks, refind_stracks)

        self.lost_stracks = sub_stracks(self.lost_stracks, self.tracked_stracks)
        self.lost_stracks.extend(lost_stracks)
        self.lost_stracks = sub_stracks(self.lost_stracks, self.removed_stracks)

        self.removed_stracks.extend(removed_stracks)

        self.tracked_stracks, self.lost_stracks = remove_duplicate_stracks(
            self.tracked_stracks,
            self.lost_stracks,
        )

        output_stracks = [track for track in self.tracked_stracks if track.is_activated]

        outputs: List[TrackOutput] = []
        for trk in output_stracks:
            tlbr = trk.tlbr
            w = tlbr[2] - tlbr[0]
            h = tlbr[3] - tlbr[1]

            if w * h < self.min_box_area:
                continue

            outputs.append(
                TrackOutput(
                    track_id=int(trk.track_id),
                    bbox_xyxy=(
                        float(tlbr[0]),
                        float(tlbr[1]),
                        float(tlbr[2]),
                        float(tlbr[3]),
                    ),
                    score=float(trk.score),
                    age=int(trk.frame_id - trk.start_frame),
                    time_since_update=0,
                )
            )

        return outputs
