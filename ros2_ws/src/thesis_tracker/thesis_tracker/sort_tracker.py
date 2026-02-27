#!/usr/bin/env python3
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

try:
    from scipy.optimize import linear_sum_assignment
    HAVE_SCIPY = True
except Exception:
    HAVE_SCIPY = False

# ---------------------------------------------------------------------------
# sort_tracker.py — Minimal SORT tracker (Kalman filter + Hungarian IoU match)
#
# Implements a simplified version of SORT (Simple Online and Realtime
# Tracking) for associating per-frame bounding box detections into persistent
# tracks.  Key components:
#
#   KalmanBox   — 7D constant-velocity Kalman filter per track, state is
#                 [cx, cy, area, aspect, vx, vy, v_area].
#   SortTrack   — Wraps a KalmanBox with track metadata (ID, hit count, age,
#                 time-since-update).
#   Sort        — Top-level tracker.  Each call to update():
#                   1. Predicts all existing tracks one step forward.
#                   2. Hungarian algorithm (scipy) IoU matching between
#                      predicted bboxes and detections — globally optimal
#                      assignment, fewer ID switches than greedy.
#                      Falls back to greedy if scipy is unavailable.
#                      Centre-distance gating skips IoU computation for
#                      pairs that are too far apart, keeping cost O(sparse).
#                   3. Updates matched tracks with the Kalman correction step.
#                   4. Spawns new tracks for unmatched detections.
#                   5. Prunes tracks that have not been matched for > max_age
#                      consecutive frames.
#
# Typical usage:
#   tracker = Sort(iou_thresh=0.2, max_age=8, min_hits=3)
#   tracks  = tracker.update(det_bboxes_xyxy, frame_id=frame_id)
#   confirmed = [t for t in tracks if t.hits >= tracker.min_hits
#                                  and t.time_since_update == 0]
# ---------------------------------------------------------------------------

BBox = Tuple[float, float, float, float]  # x1,y1,x2,y2 in pixels


def iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom > 0 else 0.0


def xyxy_to_z(b: BBox) -> np.ndarray:
    # [x, y, s, r] with centre (x,y), scale s = area, aspect r = w/h
    x1, y1, x2, y2 = b
    w = max(1e-3, x2 - x1)
    h = max(1e-3, y2 - y1)
    x = x1 + w / 2.0
    y = y1 + h / 2.0
    s = w * h
    r = w / h
    return np.array([[x], [y], [s], [r]], dtype=np.float32)


def x_to_xyxy(x: np.ndarray) -> BBox:
    # from [x,y,s,r] to xyxy
    cx, cy, s, r = float(x[0]), float(x[1]), float(x[2]), float(x[3])
    s = max(1e-3, s)
    r = max(1e-3, r)
    w = math.sqrt(s * r)
    h = s / w
    x1 = cx - w / 2.0
    y1 = cy - h / 2.0
    x2 = cx + w / 2.0
    y2 = cy + h / 2.0
    return (x1, y1, x2, y2)


@dataclass
class KalmanBox:
    # 7D state: [x,y,s,r, vx,vy,vs]
    x: np.ndarray = field(default_factory=lambda: np.zeros((7, 1), dtype=np.float32))
    P: np.ndarray = field(default_factory=lambda: np.eye(7, dtype=np.float32))
    F: np.ndarray = field(default_factory=lambda: np.eye(7, dtype=np.float32))
    Q: np.ndarray = field(default_factory=lambda: np.eye(7, dtype=np.float32))
    H: np.ndarray = field(default_factory=lambda: np.zeros((4, 7), dtype=np.float32))
    R: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float32))

    def __post_init__(self) -> None:
        # Constant velocity model
        self.F = np.eye(7, dtype=np.float32)
        for i in range(4):
            if i < 3:  # x,y,s have velocities
                self.F[i, i + 4] = 1.0

        self.H = np.zeros((4, 7), dtype=np.float32)
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0
        self.H[3, 3] = 1.0

        # Tuned for 30 FPS-ish. Keep simple.
        self.P *= 10.0
        self.P[4:, 4:] *= 100.0  # velocities uncertain

        self.R = np.eye(4, dtype=np.float32)
        self.R *= 1.0

        self.Q = np.eye(7, dtype=np.float32)
        self.Q *= 0.01
        self.Q[4:, 4:] *= 0.1

    def initiate(self, bbox: BBox) -> None:
        z = xyxy_to_z(bbox)
        self.x[:4] = z
        self.x[4:] = 0.0

    def predict(self) -> None:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, bbox: BBox) -> None:
        z = xyxy_to_z(bbox)
        y = z - (self.H @ self.x)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + (K @ y)
        I = np.eye(self.P.shape[0], dtype=np.float32)
        self.P = (I - (K @ self.H)) @ self.P

    def bbox(self) -> BBox:
        return x_to_xyxy(self.x[:4])


def _bbox_centre(b: BBox) -> Tuple[float, float]:
    return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0


def hungarian_match_iou(
    tracks: List[BBox],
    dets: List[BBox],
    iou_thresh: float,
    centre_gate: float = 200.0,   # skip IoU if centres are farther apart (px)
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Optimal assignment via Hungarian (scipy) with centre-distance gating.
    Falls back to greedy matching if scipy is not available."""
    if not tracks or not dets:
        return [], list(range(len(tracks))), list(range(len(dets)))

    # Build cost matrix (1 - IoU); gated pairs get cost 1.0 (worst possible)
    cost = np.ones((len(tracks), len(dets)), dtype=np.float32)
    tc = [_bbox_centre(b) for b in tracks]
    dc = [_bbox_centre(b) for b in dets]
    gate2 = centre_gate ** 2
    for ti, tb in enumerate(tracks):
        for di, db in enumerate(dets):
            dx = tc[ti][0] - dc[di][0]
            dy = tc[ti][1] - dc[di][1]
            if dx * dx + dy * dy > gate2:
                continue   # too far — leave cost at 1.0
            cost[ti, di] = 1.0 - iou(tb, db)

    if HAVE_SCIPY:
        row_ind, col_ind = linear_sum_assignment(cost)
        pairs = list(zip(row_ind.tolist(), col_ind.tolist()))
    else:
        # Greedy fallback: sort all (cost, ti, di) and pick greedily
        entries = sorted(
            [(cost[ti, di], ti, di)
             for ti in range(len(tracks))
             for di in range(len(dets))]
        )
        used_t_g: set = set()
        used_d_g: set = set()
        pairs = []
        for c, ti, di in entries:
            if ti in used_t_g or di in used_d_g:
                continue
            used_t_g.add(ti)
            used_d_g.add(di)
            pairs.append((ti, di))

    used_t: set = set()
    used_d: set = set()
    matches = []
    for ti, di in pairs:
        if cost[ti, di] > 1.0 - iou_thresh:  # IoU below threshold
            continue
        used_t.add(ti)
        used_d.add(di)
        matches.append((ti, di))

    unmatched_t = [i for i in range(len(tracks)) if i not in used_t]
    unmatched_d = [i for i in range(len(dets)) if i not in used_d]
    return matches, unmatched_t, unmatched_d


@dataclass
class SortTrack:
    track_id: int
    kf: KalmanBox
    hits: int = 1
    age: int = 0          # total frames since created
    time_since_update: int = 0
    last_frame_id: Optional[int] = None

    def predict(self) -> None:
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1

    def update(self, bbox: BBox, frame_id: Optional[int]) -> None:
        self.kf.update(bbox)
        self.hits += 1
        self.time_since_update = 0
        self.last_frame_id = frame_id

    def bbox(self) -> BBox:
        return self.kf.bbox()


@dataclass
class Sort:
    iou_thresh: float = 0.2
    max_age: int = 8
    min_hits: int = 3
    centre_gate: float = 200.0
    _next_id: int = 1
    tracks: List[SortTrack] = field(default_factory=list)
    last_match_ms: float = 0.0

    def update(self, dets: List[BBox], frame_id: Optional[int] = None) -> List[SortTrack]:
        # Predict existing tracks
        for tr in self.tracks:
            tr.predict()

        track_bboxes = [tr.bbox() for tr in self.tracks]
        t0 = time.perf_counter()
        matches, unmatched_t, unmatched_d = hungarian_match_iou(
            track_bboxes, dets, self.iou_thresh, self.centre_gate
        )
        self.last_match_ms = (time.perf_counter() - t0) * 1000.0

        # Update matched
        for ti, di in matches:
            self.tracks[ti].update(dets[di], frame_id)

        # Create new tracks
        for di in unmatched_d:
            kf = KalmanBox()
            kf.initiate(dets[di])
            tid = self._next_id
            self._next_id += 1
            self.tracks.append(SortTrack(track_id=tid, kf=kf, hits=1, age=0, time_since_update=0, last_frame_id=frame_id))

        # Prune dead
        self.tracks = [tr for tr in self.tracks if tr.time_since_update <= self.max_age]

        return self.tracks