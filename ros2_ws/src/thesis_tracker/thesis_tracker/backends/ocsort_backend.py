"""Faithful OC-SORT backend.

Reference-aligned implementation of OC-SORT:
- 7D SORT Kalman state: [x, y, s, r, vx, vy, vs]
- Observation-Centric Momentum, OCM
- Observation-Centric Re-Update, ORU
- Optional BYTE-style low-score second association

Adapted to the local tracker backend interface:
    update(dets_xyxy, scores, frame_time_ns) -> list[TrackOutput]
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import ClassVar, Dict, List, Optional, Tuple

import numpy as np
from thesis_tracker.core import sort_tracker
from thesis_tracker.core.sort_tracker import iou_batch

from . import BBox, TrackOutput


def convert_bbox_to_z(bbox: np.ndarray) -> np.ndarray:
    """xyxy or xyxyscore -> [cx, cy, area, aspect]."""
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w / 2.0
    y = bbox[1] + h / 2.0
    s = w * h
    r = w / float(h + 1e-6)
    return np.array([x, y, s, r], dtype=np.float64).reshape((4, 1))


def convert_x_to_bbox(x: np.ndarray, score: Optional[float] = None) -> np.ndarray:
    """[cx, cy, area, aspect] -> xyxy or xyxyscore."""
    w = np.sqrt(max(1e-6, float(x[2] * x[3])))
    h = float(x[2]) / w

    out = [
        float(x[0] - w / 2.0),
        float(x[1] - h / 2.0),
        float(x[0] + w / 2.0),
        float(x[1] + h / 2.0),
    ]

    if score is not None:
        out.append(float(score))

    return np.asarray(out, dtype=np.float64).reshape(1, -1)


def speed_direction(bbox1: np.ndarray, bbox2: np.ndarray) -> np.ndarray:
    """Official OC-SORT direction convention: [dy, dx]."""
    cx1 = (bbox1[0] + bbox1[2]) / 2.0
    cy1 = (bbox1[1] + bbox1[3]) / 2.0
    cx2 = (bbox2[0] + bbox2[2]) / 2.0
    cy2 = (bbox2[1] + bbox2[3]) / 2.0

    speed = np.array([cy2 - cy1, cx2 - cx1], dtype=np.float64)
    norm = np.sqrt((cy2 - cy1) ** 2 + (cx2 - cx1) ** 2) + 1e-6
    return speed / norm


def speed_direction_batch(dets: np.ndarray, tracks: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return Y, X direction components for all track-detection pairs."""
    tracks = tracks[..., np.newaxis]

    cx1 = (dets[:, 0] + dets[:, 2]) / 2.0
    cy1 = (dets[:, 1] + dets[:, 3]) / 2.0
    cx2 = (tracks[:, 0] + tracks[:, 2]) / 2.0
    cy2 = (tracks[:, 1] + tracks[:, 3]) / 2.0

    dx = cx1 - cx2
    dy = cy1 - cy2
    norm = np.sqrt(dx ** 2 + dy ** 2) + 1e-6

    dx = dx / norm
    dy = dy / norm

    return dy, dx


def k_previous_obs(observations: Dict[int, np.ndarray], cur_age: int, k: int) -> np.ndarray:
    """Official OC-SORT previous-observation lookup."""
    if len(observations) == 0:
        return np.array([-1, -1, -1, -1, -1], dtype=np.float64)

    for i in range(k):
        dt = k - i
        if cur_age - dt in observations:
            return observations[cur_age - dt]

    max_age = max(observations.keys())
    return observations[max_age]


def linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
    if cost_matrix.size == 0:
        return np.empty((0, 2), dtype=int)

    if sort_tracker.HAVE_SCIPY:
        rows, cols = sort_tracker.linear_sum_assignment(cost_matrix)
        return np.asarray(list(zip(rows, cols)), dtype=int)

    entries = sorted(
        (float(cost_matrix[r, c]), r, c)
        for r in range(cost_matrix.shape[0])
        for c in range(cost_matrix.shape[1])
    )

    used_rows: set[int] = set()
    used_cols: set[int] = set()
    out: List[Tuple[int, int]] = []

    for _cost, r, c in entries:
        if r in used_rows or c in used_cols:
            continue
        used_rows.add(r)
        used_cols.add(c)
        out.append((r, c))

    return np.asarray(out, dtype=int)


def _filter_matches(
    matched_indices: np.ndarray,
    iou_matrix: np.ndarray,
    iou_threshold: float,
    num_dets: int,
    num_trks: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if matched_indices.shape[0] == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(num_dets, dtype=int),
            np.arange(num_trks, dtype=int),
        )

    unmatched_dets = np.setdiff1d(np.arange(num_dets), matched_indices[:, 0])
    unmatched_trks = np.setdiff1d(np.arange(num_trks), matched_indices[:, 1])

    iou_vals = iou_matrix[matched_indices[:, 0], matched_indices[:, 1]]
    low_iou_mask = iou_vals < iou_threshold

    unmatched_dets = np.concatenate([unmatched_dets, matched_indices[low_iou_mask, 0]])
    unmatched_trks = np.concatenate([unmatched_trks, matched_indices[low_iou_mask, 1]])

    matches = matched_indices[~low_iou_mask]

    return matches.astype(int), unmatched_dets.astype(int), unmatched_trks.astype(int)


def associate(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float,
    velocities: np.ndarray,
    previous_obs: np.ndarray,
    vdc_weight: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Official-style OC-SORT first association with OCM."""
    if len(trackers) == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(len(detections), dtype=int),
            np.empty((0,), dtype=int),
        )

    y_dir, x_dir = speed_direction_batch(detections, previous_obs)

    inertia_y = velocities[:, 0][:, np.newaxis]
    inertia_x = velocities[:, 1][:, np.newaxis]

    diff_angle_cos = inertia_x * x_dir + inertia_y * y_dir
    diff_angle_cos = np.clip(diff_angle_cos, -1.0, 1.0)

    diff_angle = np.arccos(diff_angle_cos)
    diff_angle = (np.pi / 2.0 - np.abs(diff_angle)) / np.pi

    valid_mask = np.ones(previous_obs.shape[0], dtype=np.float64)
    valid_mask[previous_obs[:, 4] < 0] = 0.0
    valid_mask = valid_mask[:, np.newaxis]

    scores = detections[:, -1][:, np.newaxis]

    angle_diff_cost = (valid_mask * diff_angle) * float(vdc_weight)
    angle_diff_cost = angle_diff_cost.T
    angle_diff_cost = angle_diff_cost * scores

    iou_matrix = iou_batch(detections[:, :4], trackers[:, :4])

    if min(iou_matrix.shape) > 0:
        unique_mask = (iou_matrix > iou_threshold).astype(np.int32)

        if unique_mask.sum(1).max() == 1 and unique_mask.sum(0).max() == 1:
            matched_indices = np.stack(np.where(unique_mask), axis=1)
        else:
            matched_indices = linear_assignment(-(iou_matrix + angle_diff_cost))
    else:
        matched_indices = np.empty((0, 2), dtype=int)

    return _filter_matches(
        matched_indices,
        iou_matrix,
        iou_threshold,
        len(detections),
        len(trackers),
    )


class OCKalmanFilter:
    """Minimal OC-SORT KalmanFilterNew behaviour with freeze/unfreeze ORU."""

    def __init__(self) -> None:
        self.dim_x = 7
        self.dim_z = 4

        self.x = np.zeros((7, 1), dtype=np.float64)
        self.P = np.eye(7, dtype=np.float64)
        self.Q = np.eye(7, dtype=np.float64)
        self.R = np.eye(4, dtype=np.float64)

        self.F = np.array(
            [
                [1, 0, 0, 0, 1, 0, 0],
                [0, 1, 0, 0, 0, 1, 0],
                [0, 0, 1, 0, 0, 0, 1],
                [0, 0, 0, 1, 0, 0, 0],
                [0, 0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 0, 1],
            ],
            dtype=np.float64,
        )

        self.H = np.array(
            [
                [1, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0, 0],
            ],
            dtype=np.float64,
        )

        self.R[2:, 2:] *= 10.0
        self.P[4:, 4:] *= 1000.0
        self.P *= 10.0
        self.Q[-1, -1] *= 0.01
        self.Q[4:, 4:] *= 0.01

        self.K = np.zeros((7, 4), dtype=np.float64)
        self.y = np.zeros((4, 1), dtype=np.float64)
        self.S = np.zeros((4, 4), dtype=np.float64)
        self.SI = np.zeros((4, 4), dtype=np.float64)
        self._I = np.eye(7, dtype=np.float64)

        self.x_prior = self.x.copy()
        self.P_prior = self.P.copy()
        self.x_post = self.x.copy()
        self.P_post = self.P.copy()

        self.z = np.array([[None] * self.dim_z]).T

        self.history_obs: List[Optional[np.ndarray]] = []
        self.attr_saved: Optional[dict] = None
        self.observed = False

    def predict(self) -> None:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        self.x_prior = self.x.copy()
        self.P_prior = self.P.copy()

    def freeze(self) -> None:
        self.attr_saved = {
            "x": self.x.copy(),
            "P": self.P.copy(),
            "Q": self.Q.copy(),
            "R": self.R.copy(),
            "F": self.F.copy(),
            "H": self.H.copy(),
            "K": self.K.copy(),
            "y": self.y.copy(),
            "S": self.S.copy(),
            "SI": self.SI.copy(),
            "_I": self._I.copy(),
            "x_prior": self.x_prior.copy(),
            "P_prior": self.P_prior.copy(),
            "x_post": self.x_post.copy(),
            "P_post": self.P_post.copy(),
            "z": deepcopy(self.z),
            "history_obs": list(self.history_obs),
            "observed": self.observed,
        }

    def unfreeze(self) -> None:
        if self.attr_saved is None:
            return

        new_history = self.history_obs
        saved = self.attr_saved

        for key, val in saved.items():
            setattr(self, key, val)

        self.attr_saved = None
        self.history_obs = self.history_obs[:-1]

        occur = [int(obs is None) for obs in new_history]
        indices = np.where(np.asarray(occur) == 0)[0]

        if len(indices) < 2:
            return

        index1 = int(indices[-2])
        index2 = int(indices[-1])

        box1 = new_history[index1].flatten()
        box2 = new_history[index2].flatten()

        x1, y1, s1, r1 = box1
        x2, y2, s2, r2 = box2

        w1 = np.sqrt(s1 * r1)
        h1 = np.sqrt(s1 / r1)
        w2 = np.sqrt(s2 * r2)
        h2 = np.sqrt(s2 / r2)

        time_gap = max(1, index2 - index1)

        dx = (x2 - x1) / time_gap
        dy = (y2 - y1) / time_gap
        dw = (w2 - w1) / time_gap
        dh = (h2 - h1) / time_gap

        for i in range(index2 - index1):
            x = x1 + (i + 1) * dx
            y = y1 + (i + 1) * dy
            w = max(1e-6, w1 + (i + 1) * dw)
            h = max(1e-6, h1 + (i + 1) * dh)
            s = w * h
            r = w / float(h)

            virtual_z = np.array([x, y, s, r], dtype=np.float64).reshape((4, 1))

            self.update(virtual_z)

            if i != index2 - index1 - 1:
                self.predict()

    def update(self, z: Optional[np.ndarray]) -> None:
        self.history_obs.append(z)

        if z is None:
            if self.observed:
                self.freeze()

            self.observed = False
            self.z = np.array([[None] * self.dim_z]).T
            self.x_post = self.x.copy()
            self.P_post = self.P.copy()
            self.y = np.zeros((4, 1), dtype=np.float64)
            return

        if not self.observed:
            self.unfreeze()
            self.observed = True

        z = np.asarray(z, dtype=np.float64).reshape((4, 1))

        self.y = z - self.H @ self.x

        pht = self.P @ self.H.T
        self.S = self.H @ pht + self.R
        self.SI = np.linalg.inv(self.S)
        self.K = pht @ self.SI

        self.x = self.x + self.K @ self.y

        i_kh = self._I - self.K @ self.H
        self.P = i_kh @ self.P @ i_kh.T + self.K @ self.R @ self.K.T

        self.z = z.copy()
        self.x_post = self.x.copy()
        self.P_post = self.P.copy()


@dataclass
class OCKalmanBoxTracker:
    bbox: np.ndarray
    delta_t: int = 3

    count: ClassVar[int] = 0

    def __post_init__(self) -> None:
        self.kf = OCKalmanFilter()
        self.kf.x[:4] = convert_bbox_to_z(self.bbox)

        self.time_since_update = 0
        self.id = OCKalmanBoxTracker.count
        OCKalmanBoxTracker.count += 1

        self.history: List[np.ndarray] = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0

        self.last_observation = np.asarray(self.bbox, dtype=np.float64)
        self.observations: Dict[int, np.ndarray] = {self.age: self.last_observation}
        self.history_observations: List[np.ndarray] = [self.last_observation]
        self.velocity: Optional[np.ndarray] = None

    def update(self, bbox: Optional[np.ndarray]) -> None:
        if bbox is not None:
            bbox = np.asarray(bbox, dtype=np.float64)

            if self.last_observation.sum() >= 0:
                previous_box = None

                for i in range(self.delta_t):
                    dt = self.delta_t - i
                    if self.age - dt in self.observations:
                        previous_box = self.observations[self.age - dt]
                        break

                if previous_box is None:
                    previous_box = self.last_observation

                self.velocity = speed_direction(previous_box, bbox)

            self.last_observation = bbox
            self.observations[self.age] = bbox
            self.history_observations.append(bbox)

            self.time_since_update = 0
            self.history.clear()
            self.hits += 1
            self.hit_streak += 1

            self.kf.update(convert_bbox_to_z(bbox))
        else:
            self.kf.update(None)

    def predict(self) -> np.ndarray:
        if self.kf.x[6] + self.kf.x[2] <= 0:
            self.kf.x[6] *= 0.0

        self.kf.predict()

        self.age += 1

        if self.time_since_update > 0:
            self.hit_streak = 0

        self.time_since_update += 1

        pred = convert_x_to_bbox(self.kf.x)
        self.history.append(pred)

        return pred

    def get_state(self) -> np.ndarray:
        return convert_x_to_bbox(self.kf.x)


class OCSortBackend:
    """Reference-aligned OC-SORT backend."""

    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_age: int = 30,
        min_hits: int = 3,
        det_thresh: float = 0.35,
        delta_t: int = 3,
        inertia: float = 0.2,
        use_byte: bool = False,
        **_ignored,
    ) -> None:
        self.iou_threshold = float(iou_threshold)
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.det_thresh = float(det_thresh)
        self.delta_t = int(delta_t)
        self.inertia = float(inertia)
        self.use_byte = bool(use_byte)

        self.trackers: List[OCKalmanBoxTracker] = []
        self.frame_count = 0

        OCKalmanBoxTracker.count = 0

    def reset(self) -> None:
        self.trackers.clear()
        self.frame_count = 0
        OCKalmanBoxTracker.count = 0

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int,
    ) -> List[TrackOutput]:
        del frame_time_ns

        self.frame_count += 1

        if len(dets_xyxy) == 0:
            output_results = np.empty((0, 5), dtype=np.float64)
        else:
            output_results = np.asarray(
                [
                    [
                        float(b[0]),
                        float(b[1]),
                        float(b[2]),
                        float(b[3]),
                        float(scores[i]) if i < len(scores) else 1.0,
                    ]
                    for i, b in enumerate(dets_xyxy)
                ],
                dtype=np.float64,
            )

        if output_results.shape[0] == 0:
            dets = np.empty((0, 5), dtype=np.float64)
            dets_second = np.empty((0, 5), dtype=np.float64)
        else:
            all_scores = output_results[:, 4]

            inds_low = all_scores > 0.1
            inds_high = all_scores < self.det_thresh
            inds_second = np.logical_and(inds_low, inds_high)

            dets_second = output_results[inds_second]
            dets = output_results[all_scores > self.det_thresh]

        trks = np.zeros((len(self.trackers), 5), dtype=np.float64)
        to_del: List[int] = []

        for t in range(len(self.trackers)):
            pos = self.trackers[t].predict()[0]
            trks[t, :] = [pos[0], pos[1], pos[2], pos[3], 0.0]

            if np.any(np.isnan(pos)):
                to_del.append(t)

        if len(to_del) > 0:
            trks = np.ma.compress_rows(np.ma.masked_invalid(trks))

            for t in reversed(to_del):
                self.trackers.pop(t)

        zero_vel = np.array((0.0, 0.0), dtype=np.float64)

        velocities = np.asarray(
            [
                trk.velocity if trk.velocity is not None else zero_vel
                for trk in self.trackers
            ],
            dtype=np.float64,
        )

        last_boxes = np.asarray(
            [trk.last_observation for trk in self.trackers],
            dtype=np.float64,
        )

        k_observations = np.asarray(
            [
                k_previous_obs(trk.observations, trk.age, self.delta_t)
                for trk in self.trackers
            ],
            dtype=np.float64,
        )

        matched, unmatched_dets, unmatched_trks = associate(
            dets,
            trks,
            self.iou_threshold,
            velocities,
            k_observations,
            self.inertia,
        )

        for det_idx, trk_idx in matched:
            self.trackers[int(trk_idx)].update(dets[int(det_idx), :])

        # Optional BYTE-style association using low-score detections.
        if self.use_byte and len(dets_second) > 0 and len(unmatched_trks) > 0:
            u_trks = trks[unmatched_trks]
            iou_left = iou_batch(dets_second[:, :4], u_trks[:, :4])

            if iou_left.size > 0 and iou_left.max() > self.iou_threshold:
                matched_indices = linear_assignment(-iou_left)

                to_remove_trk_indices: List[int] = []

                for det_idx, local_trk_idx in matched_indices:
                    global_trk_idx = int(unmatched_trks[local_trk_idx])

                    if iou_left[det_idx, local_trk_idx] < self.iou_threshold:
                        continue

                    self.trackers[global_trk_idx].update(dets_second[det_idx, :])
                    to_remove_trk_indices.append(global_trk_idx)

                unmatched_trks = np.setdiff1d(
                    unmatched_trks,
                    np.asarray(to_remove_trk_indices, dtype=int),
                )

        # Observation-centric re-association.
        if len(unmatched_dets) > 0 and len(unmatched_trks) > 0:
            left_dets = dets[unmatched_dets]
            left_trks = last_boxes[unmatched_trks]

            iou_left = iou_batch(left_dets[:, :4], left_trks[:, :4])

            if iou_left.size > 0 and iou_left.max() > self.iou_threshold:
                rematched_indices = linear_assignment(-iou_left)

                to_remove_det_indices: List[int] = []
                to_remove_trk_indices: List[int] = []

                for local_det_idx, local_trk_idx in rematched_indices:
                    det_idx = int(unmatched_dets[local_det_idx])
                    trk_idx = int(unmatched_trks[local_trk_idx])

                    if iou_left[local_det_idx, local_trk_idx] < self.iou_threshold:
                        continue

                    self.trackers[trk_idx].update(dets[det_idx, :])
                    to_remove_det_indices.append(det_idx)
                    to_remove_trk_indices.append(trk_idx)

                unmatched_dets = np.setdiff1d(
                    unmatched_dets,
                    np.asarray(to_remove_det_indices, dtype=int),
                )
                unmatched_trks = np.setdiff1d(
                    unmatched_trks,
                    np.asarray(to_remove_trk_indices, dtype=int),
                )

        # Important for ORU: unmatched tracks receive None observations.
        for trk_idx in unmatched_trks:
            self.trackers[int(trk_idx)].update(None)

        # Create new tracks only from remaining high-score detections.
        for det_idx in unmatched_dets:
            self.trackers.append(
                OCKalmanBoxTracker(
                    bbox=dets[int(det_idx), :],
                    delta_t=self.delta_t,
                )
            )

        outputs: List[TrackOutput] = []

        i = len(self.trackers)

        for trk in reversed(self.trackers):
            if trk.last_observation.sum() < 0:
                d = trk.get_state()[0]
                score = 0.0
            else:
                d = trk.last_observation[:4]
                score = float(trk.last_observation[4]) if trk.last_observation.shape[0] >= 5 else 0.0

            if trk.time_since_update < 1:
                if trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits:
                    outputs.append(
                        TrackOutput(
                            track_id=int(trk.id + 1),
                            bbox_xyxy=(
                                float(d[0]),
                                float(d[1]),
                                float(d[2]),
                                float(d[3]),
                            ),
                            score=score,
                            age=int(trk.age),
                            time_since_update=int(trk.time_since_update),
                        )
                    )

            i -= 1

            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        outputs.reverse()
        return outputs
