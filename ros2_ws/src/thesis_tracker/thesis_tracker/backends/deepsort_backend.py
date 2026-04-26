"""Legacy DeepSORT prototype kept for history.

The active tracker node imports :mod:`deepsort_core_backend`, which implements
the DeepSORT association structure. This older module is intentionally not used
by runtime wiring.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from sensor_msgs.msg import Image

from . import BBox, TrackOutput
from .. import sort_tracker
from ..sort_tracker import KalmanBox


@dataclass
class DeepSortTrack:
    """Track state following a minimal DeepSORT-style lifecycle."""

    track_id: int
    kf: KalmanBox
    score: float
    appearance: np.ndarray | None = None
    hits: int = 1
    age: int = 1
    time_since_update: int = 0
    is_confirmed: bool = False

    def predict(self) -> None:
        """Advance the motion model before association."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1

    def update(
        self,
        bbox: BBox,
        score: float,
        n_init: int,
        appearance: np.ndarray | None,
        appearance_update_alpha: float,
    ) -> None:
        """Update track from a matched detection."""
        self.kf.update(bbox)
        self.score = score
        self.hits += 1
        self.time_since_update = 0
        if appearance is not None:
            if self.appearance is None:
                self.appearance = appearance.copy()
            else:
                alpha = float(np.clip(appearance_update_alpha, 0.0, 1.0))
                self.appearance = ((1.0 - alpha) * self.appearance) + (alpha * appearance)
                norm = float(np.sum(self.appearance))
                if norm > 0.0:
                    self.appearance /= norm
        if self.hits >= n_init:
            self.is_confirmed = True

    def bbox(self) -> BBox:
        """Return the current predicted box."""
        return self.kf.bbox()


class DeepSortBackend:
    """Minimal backend skeleton for DeepSORT without appearance embeddings."""

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        match_thresh: float = 0.25,
        centre_gate: float = 200.0,
        appearance_enabled: bool = True,
        appearance_max_frame_age_ms: float = 120.0,
        appearance_hist_bins: int = 8,
        appearance_weight: float = 0.35,
        appearance_max_distance: float = 0.6,
        appearance_min_crop_size: int = 12,
        appearance_update_alpha: float = 0.2,
    ) -> None:
        self.max_age = max_age
        self.n_init = n_init
        self.match_thresh = match_thresh
        self.centre_gate = centre_gate
        self.appearance_enabled = appearance_enabled
        self.appearance_max_frame_age_ns = int(max(0.0, appearance_max_frame_age_ms) * 1e6)
        self.appearance_hist_bins = max(2, int(appearance_hist_bins))
        self.appearance_weight = float(np.clip(appearance_weight, 0.0, 1.0))
        self.appearance_max_distance = float(np.clip(appearance_max_distance, 0.0, 1.0))
        self.appearance_min_crop_size = max(1, int(appearance_min_crop_size))
        self.appearance_update_alpha = float(np.clip(appearance_update_alpha, 0.0, 1.0))

        self._next_id = 1
        self._tracks: List[DeepSortTrack] = []
        self._latest_image: np.ndarray | None = None
        self._latest_image_stamp_ns: int = 0

    def reset(self) -> None:
        """Reset all tracker state."""
        self._tracks.clear()
        self._next_id = 1
        self._latest_image = None
        self._latest_image_stamp_ns = 0

    def update_latest_image(self, image_msg: Image) -> None:
        """Store the latest image for optional appearance extraction."""
        image_encoding = str(image_msg.encoding).lower()
        if image_encoding not in ("rgb8", "bgr8"):
            return

        image_height = int(image_msg.height)
        image_width = int(image_msg.width)
        image_step = int(image_msg.step)
        expected_step = image_width * 3
        if image_height <= 0 or image_width <= 0 or image_step != expected_step:
            return

        expected_bytes = image_height * image_step
        if len(image_msg.data) != expected_bytes:
            return

        try:
            img = np.frombuffer(image_msg.data, dtype=np.uint8).reshape(image_height, image_width, 3)
        except Exception:
            return

        self._latest_image = np.ascontiguousarray(img.copy())
        self._latest_image_stamp_ns = int(image_msg.header.stamp.sec) * 1_000_000_000 + int(
            image_msg.header.stamp.nanosec
        )

    def _compute_descriptor(
        self,
        bbox: BBox,
        frame_time_ns: int,
    ) -> np.ndarray | None:
        """Compute a normalized per-channel histogram from the latest crop."""
        if not self.appearance_enabled or self._latest_image is None:
            return None

        if self.appearance_max_frame_age_ns > 0 and self._latest_image_stamp_ns > 0:
            frame_age_ns = abs(int(frame_time_ns) - self._latest_image_stamp_ns)
            if frame_age_ns > self.appearance_max_frame_age_ns:
                return None

        image = self._latest_image
        image_h, image_w = image.shape[:2]
        x1, y1, x2, y2 = bbox
        xi1 = int(max(0, min(image_w, np.floor(x1))))
        yi1 = int(max(0, min(image_h, np.floor(y1))))
        xi2 = int(max(0, min(image_w, np.ceil(x2))))
        yi2 = int(max(0, min(image_h, np.ceil(y2))))
        crop_w = xi2 - xi1
        crop_h = yi2 - yi1
        if crop_w < self.appearance_min_crop_size or crop_h < self.appearance_min_crop_size:
            return None

        crop = image[yi1:yi2, xi1:xi2]
        if crop.size == 0:
            return None

        hist_parts: list[np.ndarray] = []
        bins = self.appearance_hist_bins
        for channel in range(3):
            hist, _ = np.histogram(crop[:, :, channel], bins=bins, range=(0, 256))
            hist_parts.append(hist.astype(np.float32, copy=False))

        descriptor = np.concatenate(hist_parts, axis=0)
        norm = float(np.sum(descriptor))
        if norm <= 0.0:
            return None
        descriptor /= norm
        return descriptor

    @staticmethod
    def _appearance_distance(
        track_desc: np.ndarray | None,
        det_desc: np.ndarray | None,
    ) -> float | None:
        """Histogram intersection distance in [0, 1]."""
        if track_desc is None or det_desc is None:
            return None
        intersection = float(np.minimum(track_desc, det_desc).sum())
        return float(np.clip(1.0 - intersection, 0.0, 1.0))

    def _match_with_appearance(
        self,
        dets_xyxy: List[BBox],
        det_descriptors: List[np.ndarray | None],
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Match tracks to detections using IoU with optional appearance blending."""
        n_tracks = len(self._tracks)
        n_dets = len(dets_xyxy)
        if n_tracks == 0 or n_dets == 0:
            return [], list(range(n_tracks)), list(range(n_dets))

        track_boxes = np.asarray([track.bbox() for track in self._tracks], dtype=np.float32).reshape(n_tracks, 4)
        det_boxes = np.asarray(dets_xyxy, dtype=np.float32).reshape(n_dets, 4)

        track_cx = (track_boxes[:, 0] + track_boxes[:, 2]) * 0.5
        track_cy = (track_boxes[:, 1] + track_boxes[:, 3]) * 0.5
        det_cx = (det_boxes[:, 0] + det_boxes[:, 2]) * 0.5
        det_cy = (det_boxes[:, 1] + det_boxes[:, 3]) * 0.5
        dx = track_cx[:, None] - det_cx[None, :]
        dy = track_cy[:, None] - det_cy[None, :]
        gate_mask = (dx * dx + dy * dy) <= float(self.centre_gate) * float(self.centre_gate)

        ious = sort_tracker.iou_batch(track_boxes, det_boxes)
        ious = np.where(gate_mask, ious, 0.0)

        rows_ok = np.any(ious >= float(self.match_thresh), axis=1)
        cols_ok = np.any(ious >= float(self.match_thresh), axis=0)
        if not rows_ok.any() or not cols_ok.any():
            return [], list(range(n_tracks)), list(range(n_dets))

        row_map = np.nonzero(rows_ok)[0]
        col_map = np.nonzero(cols_ok)[0]
        reduced_ious = ious[np.ix_(rows_ok, cols_ok)]
        cost = 1.0 - reduced_ious

        for ri, track_index in enumerate(row_map):
            track = self._tracks[int(track_index)]
            for ci, det_index in enumerate(col_map):
                appearance_distance = self._appearance_distance(
                    track.appearance,
                    det_descriptors[int(det_index)],
                )
                if appearance_distance is None:
                    continue
                if appearance_distance > self.appearance_max_distance:
                    cost[ri, ci] = 1.0 + self.appearance_weight
                    continue
                geom_cost = 1.0 - reduced_ious[ri, ci]
                cost[ri, ci] = ((1.0 - self.appearance_weight) * geom_cost) + (
                    self.appearance_weight * appearance_distance
                )

        if sort_tracker.HAVE_SCIPY:
            row_ind, col_ind = sort_tracker.linear_sum_assignment(cost)
            pairs = [(int(row_map[r]), int(col_map[c])) for r, c in zip(row_ind.tolist(), col_ind.tolist())]
        else:
            entries = sorted(
                [
                    (float(cost[ri, ci]), int(row_map[ri]), int(col_map[ci]))
                    for ri in range(cost.shape[0])
                    for ci in range(cost.shape[1])
                ]
            )
            used_t_g: set[int] = set()
            used_d_g: set[int] = set()
            pairs = []
            for _c, ti, di in entries:
                if ti in used_t_g or di in used_d_g:
                    continue
                used_t_g.add(ti)
                used_d_g.add(di)
                pairs.append((ti, di))

        used_t: set[int] = set()
        used_d: set[int] = set()
        matches: list[tuple[int, int]] = []
        for track_index, det_index in pairs:
            if ious[track_index, det_index] < float(self.match_thresh):
                continue
            appearance_distance = self._appearance_distance(
                self._tracks[track_index].appearance,
                det_descriptors[det_index],
            )
            if (
                appearance_distance is not None
                and appearance_distance > self.appearance_max_distance
            ):
                continue
            used_t.add(track_index)
            used_d.add(det_index)
            matches.append((track_index, det_index))

        unmatched_tracks = [i for i in range(n_tracks) if i not in used_t]
        unmatched_dets = [i for i in range(n_dets) if i not in used_d]
        return matches, unmatched_tracks, unmatched_dets

    def _start_track(self, bbox: BBox, score: float, appearance: np.ndarray | None) -> None:
        """Create a new tentative track."""
        kf = KalmanBox()
        kf.initiate(bbox)
        track = DeepSortTrack(
            track_id=self._next_id,
            kf=kf,
            score=score,
            appearance=None if appearance is None else appearance.copy(),
            hits=1,
            age=1,
            time_since_update=0,
            is_confirmed=(self.n_init <= 1),
        )
        self._next_id += 1
        self._tracks.append(track)

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int,
    ) -> List[TrackOutput]:
        """Update the backend using IoU plus lightweight appearance cues."""
        det_descriptors = [
            self._compute_descriptor(bbox, frame_time_ns) for bbox in dets_xyxy
        ]

        for track in self._tracks:
            track.predict()

        matches, _unmatched_tracks, unmatched_dets = self._match_with_appearance(
            dets_xyxy,
            det_descriptors,
        )

        for track_index, det_index in matches:
            self._tracks[track_index].update(
                dets_xyxy[det_index],
                scores[det_index],
                self.n_init,
                det_descriptors[det_index],
                self.appearance_update_alpha,
            )

        for det_index in unmatched_dets:
            self._start_track(
                dets_xyxy[det_index],
                scores[det_index],
                det_descriptors[det_index],
            )

        self._tracks = [
            track for track in self._tracks if track.time_since_update <= self.max_age
        ]

        outputs: List[TrackOutput] = []
        for track in self._tracks:
            if not track.is_confirmed or track.time_since_update != 0:
                continue
            outputs.append(
                TrackOutput(
                    track_id=track.track_id,
                    bbox_xyxy=track.bbox(),
                    score=track.score,
                    age=track.age,
                    time_since_update=track.time_since_update,
                )
            )
        return outputs
