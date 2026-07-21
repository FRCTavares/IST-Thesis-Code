"""DeepSORT backend with matching cascade, Mahalanobis gating, and appearance gallery.

This follows the structure of nwojke/deep_sort while fitting the local tracker
backend interface. A real ReID CNN can be plugged in later; until then, the
appearance feature is an L2-normalized color-histogram crop descriptor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import math
from pathlib import Path
from typing import Callable, List

import numpy as np
from sensor_msgs.msg import Image
from thesis_tracker.core import sort_tracker

from . import BBox, TrackOutput

CHI2INV95 = {
    1: 3.8415,
    2: 5.9915,
    3: 7.8147,
    4: 9.4877,
    5: 11.070,
    6: 12.592,
    7: 14.067,
    8: 15.507,
    9: 16.919,
}
INFTY_COST = 1e5


def _xyxy_to_xyah(bbox: BBox) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    w = max(1e-3, float(x2) - float(x1))
    h = max(1e-3, float(y2) - float(y1))
    return np.asarray([float(x1) + 0.5 * w, float(y1) + 0.5 * h, w / h, h], dtype=np.float32)


def _xyah_to_xyxy(xyah: np.ndarray) -> BBox:
    cx, cy, aspect, h = [float(v) for v in xyah[:4]]
    h = max(1e-3, h)
    aspect = max(1e-3, aspect)
    w = aspect * h
    return (cx - 0.5 * w, cy - 0.5 * h, cx + 0.5 * w, cy + 0.5 * h)


def _tlwh_from_xyxy(bbox: BBox) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return np.asarray([x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)], dtype=np.float32)


class DeepSortKalmanFilter:
    """8D image-space Kalman filter used by DeepSORT."""

    def __init__(self) -> None:
        ndim = 4
        self._motion_mat = np.eye(2 * ndim, dtype=np.float32)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = 1.0
        self._update_mat = np.eye(ndim, 2 * ndim, dtype=np.float32)
        self._std_weight_position = 1.0 / 20.0
        self._std_weight_velocity = 1.0 / 160.0

    def initiate(self, measurement: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        mean = np.r_[measurement, np.zeros_like(measurement)].astype(np.float32)
        h = max(1e-3, float(measurement[3]))
        std = np.asarray(
            [
                2.0 * self._std_weight_position * h,
                2.0 * self._std_weight_position * h,
                1e-2,
                2.0 * self._std_weight_position * h,
                10.0 * self._std_weight_velocity * h,
                10.0 * self._std_weight_velocity * h,
                1e-5,
                10.0 * self._std_weight_velocity * h,
            ],
            dtype=np.float32,
        )
        return mean, np.diag(np.square(std)).astype(np.float32)

    def predict(self, mean: np.ndarray, covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = max(1e-3, float(mean[3]))
        std_pos = np.asarray(
            [
                self._std_weight_position * h,
                self._std_weight_position * h,
                1e-2,
                self._std_weight_position * h,
            ],
            dtype=np.float32,
        )
        std_vel = np.asarray(
            [
                self._std_weight_velocity * h,
                self._std_weight_velocity * h,
                1e-5,
                self._std_weight_velocity * h,
            ],
            dtype=np.float32,
        )
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel])).astype(np.float32)
        mean = self._motion_mat @ mean
        covariance = self._motion_mat @ covariance @ self._motion_mat.T + motion_cov
        return mean.astype(np.float32), covariance.astype(np.float32)

    def project(self, mean: np.ndarray, covariance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = max(1e-3, float(mean[3]))
        std = np.asarray(
            [
                self._std_weight_position * h,
                self._std_weight_position * h,
                1e-1,
                self._std_weight_position * h,
            ],
            dtype=np.float32,
        )
        innovation_cov = np.diag(np.square(std)).astype(np.float32)
        projected_mean = self._update_mat @ mean
        projected_cov = self._update_mat @ covariance @ self._update_mat.T
        return projected_mean.astype(np.float32), (projected_cov + innovation_cov).astype(np.float32)

    def update(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurement: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        projected_mean, projected_cov = self.project(mean, covariance)
        innovation = measurement - projected_mean
        kalman_gain = covariance @ self._update_mat.T @ np.linalg.inv(projected_cov)
        new_mean = mean + kalman_gain @ innovation
        new_covariance = covariance - kalman_gain @ projected_cov @ kalman_gain.T
        return new_mean.astype(np.float32), new_covariance.astype(np.float32)

    def gating_distance(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurements: np.ndarray,
        only_position: bool = False,
    ) -> np.ndarray:
        projected_mean, projected_cov = self.project(mean, covariance)
        if only_position:
            projected_mean = projected_mean[:2]
            projected_cov = projected_cov[:2, :2]
            measurements = measurements[:, :2]

        cholesky = np.linalg.cholesky(projected_cov)
        d = measurements - projected_mean
        z = np.linalg.solve(cholesky, d.T)
        return np.sum(z * z, axis=0)


class DeepSortTrackState(IntEnum):
    TENTATIVE = 1
    CONFIRMED = 2
    DELETED = 3


@dataclass
class DeepSortDetection:
    bbox_xyxy: BBox
    score: float
    feature: np.ndarray | None

    def to_xyah(self) -> np.ndarray:
        return _xyxy_to_xyah(self.bbox_xyxy)

    def to_tlwh(self) -> np.ndarray:
        return _tlwh_from_xyxy(self.bbox_xyxy)


@dataclass
class DeepSortTrack:
    mean: np.ndarray
    covariance: np.ndarray
    track_id: int
    n_init: int
    max_age: int
    score: float
    features: list[np.ndarray] = field(default_factory=list)
    hits: int = 1
    age: int = 1
    time_since_update: int = 0
    state: DeepSortTrackState = DeepSortTrackState.TENTATIVE

    def to_xyxy(self) -> BBox:
        return _xyah_to_xyxy(self.mean[:4])

    def to_tlwh(self) -> np.ndarray:
        x1, y1, x2, y2 = self.to_xyxy()
        return np.asarray([x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)], dtype=np.float32)

    def predict(self, kf: DeepSortKalmanFilter) -> None:
        self.mean, self.covariance = kf.predict(self.mean, self.covariance)
        self.age += 1
        self.time_since_update += 1

    def update(self, kf: DeepSortKalmanFilter, detection: DeepSortDetection) -> None:
        self.mean, self.covariance = kf.update(self.mean, self.covariance, detection.to_xyah())
        self.score = detection.score
        if detection.feature is not None:
            self.features.append(detection.feature)
        self.hits += 1
        self.time_since_update = 0
        if self.state == DeepSortTrackState.TENTATIVE and self.hits >= self.n_init:
            self.state = DeepSortTrackState.CONFIRMED

    def mark_missed(self) -> None:
        if self.state == DeepSortTrackState.TENTATIVE:
            self.state = DeepSortTrackState.DELETED
        elif self.time_since_update > self.max_age:
            self.state = DeepSortTrackState.DELETED

    def is_tentative(self) -> bool:
        return self.state == DeepSortTrackState.TENTATIVE

    def is_confirmed(self) -> bool:
        return self.state == DeepSortTrackState.CONFIRMED

    def is_deleted(self) -> bool:
        return self.state == DeepSortTrackState.DELETED


class NearestNeighborCosineMetric:
    """Nearest-neighbor cosine metric with a per-track feature budget."""

    def __init__(self, matching_threshold: float = 0.2, budget: int | None = 100) -> None:
        self.matching_threshold = float(matching_threshold)
        self.budget = None if budget is None or budget <= 0 else int(budget)
        self.samples: dict[int, list[np.ndarray]] = {}

    @staticmethod
    def _normalize(features: np.ndarray) -> np.ndarray:
        features = np.asarray(features, dtype=np.float32)
        if features.ndim == 1:
            features = features.reshape(1, -1)
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        return features / np.maximum(norms, 1e-12)

    def distance(self, features: np.ndarray, targets: np.ndarray) -> np.ndarray:
        features = self._normalize(features)
        cost = np.zeros((len(targets), len(features)), dtype=np.float32)
        for row, target in enumerate(targets):
            samples = self.samples.get(int(target), [])
            if len(samples) == 0:
                cost[row, :] = self.matching_threshold + 1e-5
                continue
            sample_matrix = self._normalize(np.asarray(samples, dtype=np.float32))
            distances = 1.0 - sample_matrix @ features.T
            cost[row, :] = np.maximum(0.0, np.min(distances, axis=0))
        return cost

    def partial_fit(self, features: np.ndarray, targets: np.ndarray, active_targets: list[int]) -> None:
        if len(features) > 0:
            features = self._normalize(features)
            for feature, target in zip(features, targets):
                target_id = int(target)
                self.samples.setdefault(target_id, []).append(feature.astype(np.float32, copy=True))
                if self.budget is not None:
                    self.samples[target_id] = self.samples[target_id][-self.budget :]

        active = set(int(t) for t in active_targets)
        self.samples = {target: samples for target, samples in self.samples.items() if target in active}


def _min_cost_matching(
    distance_metric: Callable[[list[DeepSortTrack], list[DeepSortDetection], list[int], list[int]], np.ndarray],
    max_distance: float,
    tracks: list[DeepSortTrack],
    detections: list[DeepSortDetection],
    track_indices: list[int],
    detection_indices: list[int],
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    if len(track_indices) == 0 or len(detection_indices) == 0:
        return [], track_indices, detection_indices

    cost_matrix = distance_metric(tracks, detections, track_indices, detection_indices)
    cost_matrix = np.asarray(cost_matrix, dtype=np.float32)
    cost_matrix[cost_matrix > max_distance] = max_distance + 1e-5

    if sort_tracker.HAVE_SCIPY:
        rows, cols = sort_tracker.linear_sum_assignment(cost_matrix)
        assignment = list(zip(rows.tolist(), cols.tolist()))
    else:
        entries = sorted(
            (float(cost_matrix[r, c]), r, c)
            for r in range(cost_matrix.shape[0])
            for c in range(cost_matrix.shape[1])
        )
        used_rows: set[int] = set()
        used_cols: set[int] = set()
        assignment = []
        for _cost, row, col in entries:
            if row in used_rows or col in used_cols:
                continue
            used_rows.add(row)
            used_cols.add(col)
            assignment.append((row, col))

    matched_rows = {row for row, _col in assignment}
    matched_cols = {col for _row, col in assignment}
    unmatched_tracks = [idx for row, idx in enumerate(track_indices) if row not in matched_rows]
    unmatched_dets = [idx for col, idx in enumerate(detection_indices) if col not in matched_cols]
    matches: list[tuple[int, int]] = []

    for row, col in assignment:
        track_idx = track_indices[row]
        detection_idx = detection_indices[col]
        if cost_matrix[row, col] > max_distance:
            unmatched_tracks.append(track_idx)
            unmatched_dets.append(detection_idx)
        else:
            matches.append((track_idx, detection_idx))

    return matches, unmatched_tracks, unmatched_dets


def _matching_cascade(
    distance_metric: Callable[[list[DeepSortTrack], list[DeepSortDetection], list[int], list[int]], np.ndarray],
    max_distance: float,
    cascade_depth: int,
    tracks: list[DeepSortTrack],
    detections: list[DeepSortDetection],
    track_indices: list[int],
    detection_indices: list[int],
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    unmatched_detections = list(detection_indices)
    matches: list[tuple[int, int]] = []

    for level in range(cascade_depth):
        if len(unmatched_detections) == 0:
            break
        level_tracks = [
            idx for idx in track_indices
            if tracks[idx].time_since_update == level + 1
        ]
        if len(level_tracks) == 0:
            continue
        level_matches, _unmatched_tracks, unmatched_detections = _min_cost_matching(
            distance_metric,
            max_distance,
            tracks,
            detections,
            level_tracks,
            unmatched_detections,
        )
        matches.extend(level_matches)

    matched_tracks = {track_idx for track_idx, _det_idx in matches}
    unmatched_tracks = [idx for idx in track_indices if idx not in matched_tracks]
    return matches, unmatched_tracks, unmatched_detections


class MarsSmall128Extractor:
    """Optional TensorFlow extractor for DeepSORT mars-small128.pb."""

    def __init__(self, model_path: str, batch_size: int = 32) -> None:
        self.model_path = str(model_path)
        self.batch_size = max(1, int(batch_size))

        if not Path(self.model_path).is_file():
            raise FileNotFoundError(f"ReID model not found: {self.model_path}")

        try:
            import tensorflow.compat.v1 as tf
            tf.disable_v2_behavior()
        except Exception as exc:
            raise RuntimeError(f"TensorFlow is not available: {exc}") from exc

        self.tf = tf
        self.graph = tf.Graph()

        with self.graph.as_default():
            graph_def = tf.GraphDef()

            with tf.gfile.GFile(self.model_path, "rb") as f:
                graph_def.ParseFromString(f.read())

            tf.import_graph_def(graph_def, name="net")

            self.input_var = self.graph.get_tensor_by_name("net/images:0")
            self.output_var = self.graph.get_tensor_by_name("net/features:0")

            input_shape = self.input_var.get_shape().as_list()
            self.image_shape = input_shape[1:4]

            config = tf.ConfigProto()
            config.gpu_options.allow_growth = True
            self.session = tf.Session(graph=self.graph, config=config)

    def _extract_patch(self, image: np.ndarray, bbox: BBox) -> np.ndarray | None:
        image_h, image_w = image.shape[:2]
        x1, y1, x2, y2 = bbox

        xi1 = int(max(0, min(image_w, math.floor(float(x1)))))
        yi1 = int(max(0, min(image_h, math.floor(float(y1)))))
        xi2 = int(max(0, min(image_w, math.ceil(float(x2)))))
        yi2 = int(max(0, min(image_h, math.ceil(float(y2)))))

        if xi2 <= xi1 or yi2 <= yi1:
            return None

        crop = image[yi1:yi2, xi1:xi2]
        if crop.size == 0:
            return None

        try:
            import cv2
        except Exception as exc:
            raise RuntimeError(f"OpenCV is required for ReID crop resize: {exc}") from exc

        target_h = int(self.image_shape[0])
        target_w = int(self.image_shape[1])

        patch = cv2.resize(crop, (target_w, target_h))
        return patch.astype(np.uint8, copy=False)

    def encode(self, image: np.ndarray, boxes: list[BBox]) -> list[np.ndarray | None]:
        patches: list[np.ndarray] = []
        valid_indices: list[int] = []

        for idx, box in enumerate(boxes):
            patch = self._extract_patch(image, box)
            if patch is None:
                continue

            patches.append(patch)
            valid_indices.append(idx)

        outputs: list[np.ndarray | None] = [None] * len(boxes)

        if not patches:
            return outputs

        for start in range(0, len(patches), self.batch_size):
            batch = np.asarray(
                patches[start:start + self.batch_size],
                dtype=np.uint8,
            )

            features = self.session.run(
                self.output_var,
                feed_dict={self.input_var: batch},
            )

            features = np.asarray(features, dtype=np.float32)
            norms = np.linalg.norm(features, axis=1, keepdims=True)
            features = features / np.maximum(norms, 1e-12)

            for local_idx, feature in enumerate(features):
                global_idx = valid_indices[start + local_idx]
                outputs[global_idx] = feature.astype(np.float32, copy=True)

        return outputs


class DeepSortBackend:
    """DeepSORT tracker backend using local crop features as the appearance descriptor."""

    def __init__(
        self,
        max_age: int = 30,
        n_init: int = 3,
        max_cosine_distance: float = 0.2,
        nn_budget: int = 100,
        max_iou_distance: float = 0.7,
        only_position_gating: bool = False,
        reid_model_path: str = "/home/francisco/Desktop/Thesis-Code/models/reid/mars-small128.pb",
        reid_batch_size: int = 32,
    ) -> None:
        self.max_age = int(max_age)
        self.n_init = int(n_init)
        self.max_iou_distance = float(max_iou_distance)
        self.only_position_gating = bool(only_position_gating)

        self.metric = NearestNeighborCosineMetric(
            matching_threshold=float(max_cosine_distance),
            budget=int(nn_budget),
        )

        self.kf = DeepSortKalmanFilter()
        self._next_id = 1
        self._tracks: list[DeepSortTrack] = []
        self._latest_image: np.ndarray | None = None
        self._latest_image_stamp_ns: int = 0

        if not reid_model_path:
            raise ValueError(
                "Faithful DeepSORT requires reid_model_path pointing to mars-small128.pb"
            )

        self.reid_model_path = str(reid_model_path)
        self.reid_extractor = MarsSmall128Extractor(
            self.reid_model_path,
            batch_size=reid_batch_size,
        )

        print(f"[DeepSORT] Loaded MARS ReID model: {self.reid_model_path}", flush=True)

    def reset(self) -> None:
        self._tracks.clear()
        self.metric.samples.clear()
        self._next_id = 1
        self._latest_image = None
        self._latest_image_stamp_ns = 0

    def update_latest_image(self, image_msg: Image) -> None:
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
            img = np.frombuffer(image_msg.data, dtype=np.uint8).reshape(
                image_height,
                image_width,
                3,
            )
        except Exception:
            return

        # MARS model path follows the original OpenCV-based DeepSORT pipeline.
        # If ROS gives RGB, convert to BGR before crop extraction.
        if image_encoding == "rgb8":
            img = img[:, :, ::-1]

        self._latest_image = np.ascontiguousarray(img.copy())
        self._latest_image_stamp_ns = (
            int(image_msg.header.stamp.sec) * 1_000_000_000
            + int(image_msg.header.stamp.nanosec)
        )

    def _make_detections(
        self,
        dets_xyxy: list[BBox],
        scores: list[float],
        frame_time_ns: int,
    ) -> list[DeepSortDetection]:
        del frame_time_ns

        if self._latest_image is None:
            return []

        features = self.reid_extractor.encode(self._latest_image, dets_xyxy)

        detections: list[DeepSortDetection] = []

        for idx, bbox in enumerate(dets_xyxy):
            feature = features[idx]

            # Faithful DeepSORT requires a valid deep appearance feature.
            # If the crop is invalid, skip the detection.
            if feature is None:
                continue

            detections.append(
                DeepSortDetection(
                    bbox_xyxy=bbox,
                    score=float(scores[idx]) if idx < len(scores) else 0.0,
                    feature=feature,
                )
            )

        return detections

    def _gate_cost_matrix(
        self,
        cost_matrix: np.ndarray,
        detections: list[DeepSortDetection],
        track_indices: list[int],
        detection_indices: list[int],
    ) -> np.ndarray:
        gating_dim = 2 if self.only_position_gating else 4
        gating_threshold = CHI2INV95[gating_dim]
        measurements = np.asarray([detections[i].to_xyah() for i in detection_indices], dtype=np.float32)
        gated = np.asarray(cost_matrix, dtype=np.float32).copy()
        for row, track_idx in enumerate(track_indices):
            track = self._tracks[track_idx]
            distances = self.kf.gating_distance(
                track.mean,
                track.covariance,
                measurements,
                self.only_position_gating,
            )
            gated[row, distances > gating_threshold] = INFTY_COST
        return gated

    def _gated_metric(
        self,
        tracks: list[DeepSortTrack],
        detections: list[DeepSortDetection],
        track_indices: list[int],
        detection_indices: list[int],
    ) -> np.ndarray:
        del tracks

        features = np.asarray(
            [detections[i].feature for i in detection_indices],
            dtype=np.float32,
        )

        targets = np.asarray(
            [self._tracks[i].track_id for i in track_indices],
            dtype=np.int32,
        )

        cost = self.metric.distance(features, targets)

        return self._gate_cost_matrix(
            cost,
            detections,
            track_indices,
            detection_indices,
        )

    def _iou_cost(
        self,
        tracks: list[DeepSortTrack],
        detections: list[DeepSortDetection],
        track_indices: list[int],
        detection_indices: list[int],
    ) -> np.ndarray:
        if len(track_indices) == 0 or len(detection_indices) == 0:
            return np.empty((len(track_indices), len(detection_indices)), dtype=np.float32)

        track_boxes = np.asarray([tracks[i].to_xyxy() for i in track_indices], dtype=np.float32)
        det_boxes = np.asarray([detections[i].bbox_xyxy for i in detection_indices], dtype=np.float32)
        ious = sort_tracker.iou_batch(track_boxes, det_boxes)
        cost = 1.0 - ious

        for row, track_idx in enumerate(track_indices):
            if tracks[track_idx].time_since_update > 1:
                cost[row, :] = INFTY_COST
        return cost.astype(np.float32)

    def _match(
        self,
        detections: list[DeepSortDetection],
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        confirmed_tracks = [idx for idx, track in enumerate(self._tracks) if track.is_confirmed()]
        unconfirmed_tracks = [idx for idx, track in enumerate(self._tracks) if not track.is_confirmed()]

        matches_a, unmatched_tracks_a, unmatched_detections = _matching_cascade(
            self._gated_metric,
            self.metric.matching_threshold,
            self.max_age,
            self._tracks,
            detections,
            confirmed_tracks,
            list(range(len(detections))),
        )

        iou_candidates = unconfirmed_tracks + [
            idx for idx in unmatched_tracks_a
            if self._tracks[idx].time_since_update == 1
        ]
        unmatched_tracks_a = [
            idx for idx in unmatched_tracks_a
            if self._tracks[idx].time_since_update != 1
        ]

        matches_b, unmatched_tracks_b, unmatched_detections = _min_cost_matching(
            self._iou_cost,
            self.max_iou_distance,
            self._tracks,
            detections,
            iou_candidates,
            unmatched_detections,
        )

        matches = matches_a + matches_b
        unmatched_tracks = list(set(unmatched_tracks_a + unmatched_tracks_b))
        return matches, unmatched_tracks, unmatched_detections

    def _initiate_track(self, detection: DeepSortDetection) -> None:
        mean, covariance = self.kf.initiate(detection.to_xyah())
        track = DeepSortTrack(
            mean=mean,
            covariance=covariance,
            track_id=self._next_id,
            n_init=self.n_init,
            max_age=self.max_age,
            score=detection.score,
        )
        if detection.feature is not None:
            track.features.append(detection.feature)
        self._next_id += 1
        self._tracks.append(track)

    def update(
        self,
        dets_xyxy: List[BBox],
        scores: List[float],
        frame_time_ns: int,
    ) -> List[TrackOutput]:
        detections = self._make_detections(dets_xyxy, scores, frame_time_ns)

        for track in self._tracks:
            track.predict(self.kf)

        matches, unmatched_tracks, unmatched_detections = self._match(detections)

        for track_idx, detection_idx in matches:
            self._tracks[track_idx].update(self.kf, detections[detection_idx])

        for track_idx in unmatched_tracks:
            self._tracks[track_idx].mark_missed()

        for detection_idx in unmatched_detections:
            self._initiate_track(detections[detection_idx])

        self._tracks = [track for track in self._tracks if not track.is_deleted()]

        active_targets = [track.track_id for track in self._tracks if track.is_confirmed()]
        metric_features: list[np.ndarray] = []
        metric_targets: list[int] = []
        for track in self._tracks:
            if not track.is_confirmed():
                continue
            metric_features.extend(track.features)
            metric_targets.extend([track.track_id] * len(track.features))
            track.features = []
        self.metric.partial_fit(
            np.asarray(metric_features, dtype=np.float32),
            np.asarray(metric_targets, dtype=np.int32),
            active_targets,
        )

        outputs: List[TrackOutput] = []
        for track in self._tracks:
            if not track.is_confirmed() or track.time_since_update != 0:
                continue
            outputs.append(
                TrackOutput(
                    track_id=track.track_id,
                    bbox_xyxy=track.to_xyxy(),
                    score=track.score,
                    age=track.age,
                    time_since_update=track.time_since_update,
                )
            )
        return outputs
