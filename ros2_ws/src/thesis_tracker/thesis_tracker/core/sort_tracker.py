#!/usr/bin/env python3

from dataclasses import dataclass, field
import math
import time
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


def iou_batch(boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
    """Vectorized pairwise IoU for boxes in xyxy format.

    Args:
        boxes1: Array of shape (N, 4).
        boxes2: Array of shape (M, 4).

    Returns:
        IoU matrix of shape (N, M).
    """
    n = int(boxes1.shape[0]) if boxes1.ndim == 2 else 0
    m = int(boxes2.shape[0]) if boxes2.ndim == 2 else 0
    if n == 0 or m == 0:
        return np.empty((n, m), dtype=np.float32)

    b1 = boxes1.astype(np.float32, copy=False)
    b2 = boxes2.astype(np.float32, copy=False)

    # Broadcast to (N, M) for pairwise intersections.
    inter_x1 = np.maximum(b1[:, None, 0], b2[None, :, 0])
    inter_y1 = np.maximum(b1[:, None, 1], b2[None, :, 1])
    inter_x2 = np.minimum(b1[:, None, 2], b2[None, :, 2])
    inter_y2 = np.minimum(b1[:, None, 3], b2[None, :, 3])

    inter_w = np.clip(inter_x2 - inter_x1, a_min=0.0, a_max=None)
    inter_h = np.clip(inter_y2 - inter_y1, a_min=0.0, a_max=None)
    inter = inter_w * inter_h

    area1 = np.clip(b1[:, 2] - b1[:, 0], a_min=0.0, a_max=None) * np.clip(
        b1[:, 3] - b1[:, 1], a_min=0.0, a_max=None
    )
    area2 = np.clip(b2[:, 2] - b2[:, 0], a_min=0.0, a_max=None) * np.clip(
        b2[:, 3] - b2[:, 1], a_min=0.0, a_max=None
    )
    union = area1[:, None] + area2[None, :] - inter

    out = np.zeros((n, m), dtype=np.float32)
    valid = union > 0.0
    np.divide(inter, union, out=out, where=valid)
    return out


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
        identity = np.eye(
            self.P.shape[0],
            dtype=np.float32,
        )
        self.P = (identity - (K @ self.H)) @ self.P

    def bbox(self) -> BBox:
        return x_to_xyxy(self.x[:4])


def associate(
    tracks: List["SortTrack"],
    detections: List[BBox],
    iou_thresh: float,
    gate_x: Optional[float] = None,
    gate_y: Optional[float] = None,
    cost_buf: Optional[np.ndarray] = None,
    gate_mask_buf: Optional[np.ndarray] = None,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Associate tracks to detections using vectorized IoU + Hungarian.

    Returns:
        matches, unmatched_detections, unmatched_tracks
    """
    n_tracks = len(tracks)
    n_dets = len(detections)
    if n_tracks == 0:
        return [], list(range(n_dets)), []
    if n_dets == 0:
        return [], [], list(range(n_tracks))

    iou_thresh_f = float(iou_thresh)
    gate_x_f = float(gate_x) if gate_x is not None else None
    gate_y_f = float(gate_y) if gate_y is not None else None

    # Fast-path common low-cardinality cases to avoid full matrix/Hungarian overhead.
    if n_tracks == 1 and n_dets == 1:
        tb = tracks[0].bbox()
        db = detections[0]
        if gate_x_f is not None:
            tcx = (tb[0] + tb[2]) * 0.5
            dcx = (db[0] + db[2]) * 0.5
            if abs(tcx - dcx) >= gate_x_f:
                return [], [0], [0]
        if gate_y_f is not None:
            tcy = (tb[1] + tb[3]) * 0.5
            dcy = (db[1] + db[3]) * 0.5
            if abs(tcy - dcy) >= gate_y_f:
                return [], [0], [0]

        if iou(tb, db) >= iou_thresh_f:
            return [(0, 0)], [], []
        return [], [0], [0]

    if n_tracks == 1:
        tb = tracks[0].bbox()
        tcx = (tb[0] + tb[2]) * 0.5
        tcy = (tb[1] + tb[3]) * 0.5
        best_di = -1
        best_iou = -1.0

        for di, db in enumerate(detections):
            if gate_x_f is not None:
                dcx = (db[0] + db[2]) * 0.5
                if abs(tcx - dcx) >= gate_x_f:
                    continue
            if gate_y_f is not None:
                dcy = (db[1] + db[3]) * 0.5
                if abs(tcy - dcy) >= gate_y_f:
                    continue

            iou_v = iou(tb, db)
            if iou_v > best_iou:
                best_iou = iou_v
                best_di = di

        if best_di >= 0 and best_iou >= iou_thresh_f:
            unmatched_dets = [i for i in range(n_dets) if i != best_di]
            return [(0, best_di)], unmatched_dets, []
        return [], list(range(n_dets)), [0]

    if n_dets == 1:
        db = detections[0]
        dcx = (db[0] + db[2]) * 0.5
        dcy = (db[1] + db[3]) * 0.5
        best_ti = -1
        best_iou = -1.0

        for ti, track in enumerate(tracks):
            tb = track.bbox()
            if gate_x_f is not None:
                tcx = (tb[0] + tb[2]) * 0.5
                if abs(tcx - dcx) >= gate_x_f:
                    continue
            if gate_y_f is not None:
                tcy = (tb[1] + tb[3]) * 0.5
                if abs(tcy - dcy) >= gate_y_f:
                    continue

            iou_v = iou(tb, db)
            if iou_v > best_iou:
                best_iou = iou_v
                best_ti = ti

        if best_ti >= 0 and best_iou >= iou_thresh_f:
            unmatched_tracks = [i for i in range(n_tracks) if i != best_ti]
            return [(best_ti, 0)], [], unmatched_tracks
        return [], [0], list(range(n_tracks))

    track_boxes = np.array([t.bbox() for t in tracks], dtype=np.float32)
    det_boxes = np.array(detections, dtype=np.float32)

    # Reuse caller-provided buffers when shapes are stable.
    if cost_buf is not None and cost_buf.shape == (n_tracks, n_dets):
        cost = cost_buf
    else:
        cost = np.empty((n_tracks, n_dets), dtype=np.float32)

    gate_mask = None
    if gate_x is not None or gate_y is not None:
        if gate_mask_buf is not None and gate_mask_buf.shape == (n_tracks, n_dets):
            gate_mask = gate_mask_buf
            gate_mask.fill(True)
        else:
            gate_mask = np.ones((n_tracks, n_dets), dtype=bool)

        track_cx = (track_boxes[:, 0] + track_boxes[:, 2]) * 0.5
        track_cy = (track_boxes[:, 1] + track_boxes[:, 3]) * 0.5
        det_cx = (det_boxes[:, 0] + det_boxes[:, 2]) * 0.5
        det_cy = (det_boxes[:, 1] + det_boxes[:, 3]) * 0.5

        if gate_x is not None:
            dx = np.abs(track_cx[:, None] - det_cx[None, :])
            gate_mask &= dx < gate_x_f
        if gate_y is not None:
            dy = np.abs(track_cy[:, None] - det_cy[None, :])
            gate_mask &= dy < gate_y_f

    # IoU matrix (vectorized, no Python loops)
    ious = iou_batch(track_boxes, det_boxes)
    if gate_mask is not None:
        ious = np.where(gate_mask, ious, 0.0)

    # Cost matrix (vectorized, no Python loops)
    np.subtract(1.0, ious, out=cost)

    rows_ok = np.any(ious >= iou_thresh_f, axis=1)
    cols_ok = np.any(ious >= iou_thresh_f, axis=0)
    if not rows_ok.any() or not cols_ok.any():
        return [], list(range(n_dets)), list(range(n_tracks))

    reduced_cost = cost[np.ix_(rows_ok, cols_ok)]
    row_map = np.nonzero(rows_ok)[0]
    col_map = np.nonzero(cols_ok)[0]

    if HAVE_SCIPY:
        row_ind, col_ind = linear_sum_assignment(reduced_cost)
        pairs = [
            (int(row_map[row]), int(col_map[column]))
            for row, column in zip(
                row_ind.tolist(),
                col_ind.tolist(),
            )
        ]
    else:
        # Greedy fallback: sort all (cost, ti, di) and pick greedily
        entries = sorted(
            [(float(reduced_cost[ri, ci]), int(row_map[ri]), int(col_map[ci]))
             for ri in range(reduced_cost.shape[0])
             for ci in range(reduced_cost.shape[1])]
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
        if ious[ti, di] < iou_thresh_f:
            continue
        used_t.add(ti)
        used_d.add(di)
        matches.append((ti, di))

    unmatched_tracks = [i for i in range(n_tracks) if i not in used_t]
    unmatched_dets = [i for i in range(n_dets) if i not in used_d]
    return matches, unmatched_dets, unmatched_tracks


def hungarian_match_iou(
    tracks: List[BBox],
    dets: List[BBox],
    iou_thresh: float,
    centre_gate: float = 200.0,
) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
    """Backward-compatible matcher API used by OC-SORT/ByteTrack backends.

    Returns:
        matches, unmatched_tracks, unmatched_detections
    """
    n_tracks = len(tracks)
    n_dets = len(dets)
    if n_tracks == 0 or n_dets == 0:
        return [], list(range(n_tracks)), list(range(n_dets))

    track_boxes = np.asarray(tracks, dtype=np.float32).reshape(n_tracks, 4)
    det_boxes = np.asarray(dets, dtype=np.float32).reshape(n_dets, 4)

    track_cx = (track_boxes[:, 0] + track_boxes[:, 2]) * 0.5
    track_cy = (track_boxes[:, 1] + track_boxes[:, 3]) * 0.5
    det_cx = (det_boxes[:, 0] + det_boxes[:, 2]) * 0.5
    det_cy = (det_boxes[:, 1] + det_boxes[:, 3]) * 0.5

    dx = track_cx[:, None] - det_cx[None, :]
    dy = track_cy[:, None] - det_cy[None, :]
    gate_mask = (dx * dx + dy * dy) <= float(centre_gate) * float(centre_gate)

    ious = iou_batch(track_boxes, det_boxes)
    ious = np.where(gate_mask, ious, 0.0)

    rows_ok = np.any(ious >= float(iou_thresh), axis=1)
    cols_ok = np.any(ious >= float(iou_thresh), axis=0)
    if not rows_ok.any() or not cols_ok.any():
        return [], list(range(n_tracks)), list(range(n_dets))

    cost = 1.0 - ious[np.ix_(rows_ok, cols_ok)]
    row_map = np.nonzero(rows_ok)[0]
    col_map = np.nonzero(cols_ok)[0]

    if HAVE_SCIPY:
        row_ind, col_ind = linear_sum_assignment(cost)
        pairs = [
            (int(row_map[row]), int(col_map[column]))
            for row, column in zip(
                row_ind.tolist(),
                col_ind.tolist(),
            )
        ]
    else:
        entries = sorted(
            [(float(cost[ri, ci]), int(row_map[ri]), int(col_map[ci]))
             for ri in range(cost.shape[0])
             for ci in range(cost.shape[1])]
        )
        used_t_g: set = set()
        used_d_g: set = set()
        pairs = []
        for _c, ti, di in entries:
            if ti in used_t_g or di in used_d_g:
                continue
            used_t_g.add(ti)
            used_d_g.add(di)
            pairs.append((ti, di))

    used_t: set = set()
    used_d: set = set()
    matches: List[Tuple[int, int]] = []
    for ti, di in pairs:
        if ious[ti, di] < float(iou_thresh):
            continue
        used_t.add(ti)
        used_d.add(di)
        matches.append((ti, di))

    unmatched_t = [i for i in range(n_tracks) if i not in used_t]
    unmatched_d = [i for i in range(n_dets) if i not in used_d]
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
    gate_x: Optional[float] = None
    gate_y: Optional[float] = None
    _next_id: int = 1
    tracks: List[SortTrack] = field(default_factory=list)
    last_match_ms: float = 0.0
    last_iou_ms: float = 0.0
    _cost_buf: Optional[np.ndarray] = None
    _gate_mask_buf: Optional[np.ndarray] = None

    def _ensure_match_buffers(self, n_tracks: int, n_dets: int) -> None:
        if n_tracks <= 0 or n_dets <= 0:
            return
        shape = (n_tracks, n_dets)
        if self._cost_buf is None or self._cost_buf.shape != shape:
            self._cost_buf = np.empty(shape, dtype=np.float32)
        if self._gate_mask_buf is None or self._gate_mask_buf.shape != shape:
            self._gate_mask_buf = np.empty(shape, dtype=bool)

    def update(self, dets: List[BBox], frame_id: Optional[int] = None) -> List[SortTrack]:
        # Predict existing tracks
        for tr in self.tracks:
            tr.predict()

        self._ensure_match_buffers(len(self.tracks), len(dets))
        t0 = time.perf_counter()
        matches, unmatched_d, unmatched_t = associate(
            self.tracks,
            dets,
            self.iou_thresh,
            gate_x=self.gate_x if self.gate_x is not None else self.centre_gate,
            gate_y=self.gate_y if self.gate_y is not None else self.centre_gate,
            cost_buf=self._cost_buf,
            gate_mask_buf=self._gate_mask_buf,
        )
        self.last_match_ms = (time.perf_counter() - t0) * 1000.0
        self.last_iou_ms = self.last_match_ms

        # Update matched
        for ti, di in matches:
            self.tracks[ti].update(dets[di], frame_id)

        # Create new tracks
        for di in unmatched_d:
            kf = KalmanBox()
            kf.initiate(dets[di])
            tid = self._next_id
            self._next_id += 1
            self.tracks.append(
                SortTrack(
                    track_id=tid,
                    kf=kf,
                    hits=1,
                    age=0,
                    time_since_update=0,
                    last_frame_id=frame_id,
                )
            )

        # Prune dead
        self.tracks = [tr for tr in self.tracks if tr.time_since_update <= self.max_age]

        return self.tracks
