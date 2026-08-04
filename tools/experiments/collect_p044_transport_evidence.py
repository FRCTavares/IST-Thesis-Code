#!/usr/bin/env python3
"""Collect Issue #44 detector and asynchronous ReID evidence as JSONL."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import threading
import time
from pathlib import Path
from typing import Any, Iterable

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from std_msgs.msg import String

from thesis_msgs.msg import (
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
    Timing,
)

CONDITION_CHOICES = (
    "reference",
    "treatment",
    "selective",
    "forced_frequent",
    "all_candidates_hailo",
    "ambiguity_guarded_hailo",
    "pass_through",
    "suppressed_result",
    "backend_failure",
    "delayed_result",
)



def percentile(
    values: Iterable[float],
    probability: float,
) -> float | None:
    """Return a linearly interpolated percentile."""
    data = sorted(float(value) for value in values)

    if not data:
        return None

    probability = min(
        1.0,
        max(0.0, float(probability)),
    )

    position = probability * (len(data) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return data[lower]

    fraction = position - lower

    return (
        data[lower] * (1.0 - fraction)
        + data[upper] * fraction
    )


def metric_summary(
    values: Iterable[float],
) -> dict[str, float | int | None]:
    """Summarise one numeric evidence series."""
    data = [
        float(value)
        for value in values
        if math.isfinite(float(value))
    ]

    if not data:
        return {
            "count": 0,
            "mean": None,
            "minimum": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "maximum": None,
        }

    return {
        "count": len(data),
        "mean": statistics.fmean(data),
        "minimum": min(data),
        "p50": percentile(data, 0.50),
        "p95": percentile(data, 0.95),
        "p99": percentile(data, 0.99),
        "maximum": max(data),
    }


class EvidenceAccumulator:
    """Thread-safe in-memory evidence aggregation."""

    def __init__(
        self,
        *,
        condition: str,
    ) -> None:
        self.condition = str(condition)
        self.started_ns = time.monotonic_ns()

        self.timing_count = 0
        self.request_count = 0
        self.result_count = 0
        self.successful_results = 0
        self.failed_results = 0
        self.tim_status_count = 0
        self.reid_status_count = 0

        self.infer_ms: list[float] = []
        self.e2e_det_ms: list[float] = []
        self.container_queue_ms: list[float] = []
        self.pub_dt_ms: list[float] = []

        self.reid_queue_delay_ms: list[float] = []
        self.reid_worker_ms: list[float] = []
        self.reid_e2e_ms: list[float] = []

        self.requests_by_id: dict[int, dict[str, int]] = {}

        self.latest_reid_status: dict[str, Any] | None = None
        self.latest_tim_status: dict[str, Any] | None = None

        self.maximum_executor_queued = 0
        self.maximum_engine_active_calls = 0

        self._lock = threading.Lock()

    def add_timing(
        self,
        message: Timing,
    ) -> dict[str, Any]:
        """Store one detector timing sample."""
        event = {
            "type": "timing",
            "received_monotonic_ns": time.monotonic_ns(),
            "seq": int(message.seq),
            "frame_id": int(message.frame_id),
            "src_stamp_ns": int(message.src_stamp_ns),
            "infer_ms": float(message.infer_ms),
            "e2e_det_ms": float(message.e2e_det_ms),
            "container_queue_ms": float(
                message.container_queue_ms
            ),
            "pub_dt_ms": float(message.pub_dt_ms),
        }

        with self._lock:
            self.timing_count += 1
            self.infer_ms.append(event["infer_ms"])
            self.e2e_det_ms.append(event["e2e_det_ms"])
            self.container_queue_ms.append(
                event["container_queue_ms"]
            )

            if event["pub_dt_ms"] > 0.0:
                self.pub_dt_ms.append(
                    event["pub_dt_ms"]
                )

        return event

    def add_request(
        self,
        message: AppearanceEmbeddingRequest,
    ) -> dict[str, Any]:
        """Store request provenance without serialising the crop."""
        request_id = int(message.request_id)

        event = {
            "type": "reid_request",
            "received_monotonic_ns": time.monotonic_ns(),
            "request_id": request_id,
            "submitted_ns": int(message.submitted_ns),
            "deadline_ns": int(message.deadline_ns),
            "source_frame_id": int(
                message.source_frame_id
            ),
            "source_image_timestamp_ns": int(
                message.source_image_timestamp_ns
            ),
            "source_image_seq": int(
                message.source_image_seq
            ),
            "frame_generation": int(
                message.frame_generation
            ),
            "candidate_index": int(
                message.candidate_index
            ),
            "track_id": int(message.track_id),
            "track_generation": int(
                message.track_generation
            ),
            "backend_name": str(
                message.backend_name
            ),
            "embedding_space": str(
                message.embedding_space
            ),
            "backend_dimension": int(
                message.backend_dimension
            ),
            "crop_height": int(
                message.crop_height
            ),
            "crop_width": int(
                message.crop_width
            ),
        }

        with self._lock:
            self.request_count += 1
            self.requests_by_id[request_id] = {
                "submitted_ns": event["submitted_ns"],
                "deadline_ns": event["deadline_ns"],
            }

        return event

    def add_result(
        self,
        message: AppearanceEmbeddingResult,
    ) -> dict[str, Any]:
        """Store one worker result and derive causal timing."""
        request_id = int(message.request_id)
        started_ns = int(message.started_ns)
        completed_ns = int(message.completed_ns)

        event = {
            "type": "reid_result",
            "received_monotonic_ns": time.monotonic_ns(),
            "request_id": request_id,
            "started_ns": started_ns,
            "completed_ns": completed_ns,
            "succeeded": bool(message.succeeded),
            "dimension": int(message.dimension),
            "error": str(message.error),
            "backend_name": str(
                message.backend_name
            ),
            "embedding_space": str(
                message.embedding_space
            ),
            "queue_delay_ms": None,
            "worker_ms": None,
            "end_to_end_ms": None,
        }

        with self._lock:
            self.result_count += 1

            if event["succeeded"]:
                self.successful_results += 1
            else:
                self.failed_results += 1

            request = self.requests_by_id.get(
                request_id
            )

            if request is not None:
                submitted_ns = int(
                    request["submitted_ns"]
                )

                queue_delay_ms = (
                    started_ns - submitted_ns
                ) / 1_000_000.0
                worker_ms = (
                    completed_ns - started_ns
                ) / 1_000_000.0
                end_to_end_ms = (
                    completed_ns - submitted_ns
                ) / 1_000_000.0

                event["queue_delay_ms"] = (
                    queue_delay_ms
                )
                event["worker_ms"] = worker_ms
                event["end_to_end_ms"] = (
                    end_to_end_ms
                )

                if queue_delay_ms >= 0.0:
                    self.reid_queue_delay_ms.append(
                        queue_delay_ms
                    )

                if worker_ms >= 0.0:
                    self.reid_worker_ms.append(
                        worker_ms
                    )

                if end_to_end_ms >= 0.0:
                    self.reid_e2e_ms.append(
                        end_to_end_ms
                    )

        return event

    def add_reid_status(
        self,
        message: String,
    ) -> dict[str, Any]:
        """Store one perception ReID status snapshot."""
        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError:
            payload = {
                "parse_error": True,
                "raw": str(message.data),
            }

        event = {
            "type": "perception_reid_status",
            "received_monotonic_ns": time.monotonic_ns(),
            "payload": payload,
        }

        with self._lock:
            self.reid_status_count += 1
            self.latest_reid_status = payload

            executor = payload.get(
                "executor",
                {},
            )

            self.maximum_executor_queued = max(
                self.maximum_executor_queued,
                int(executor.get("queued", 0)),
                int(
                    executor.get(
                        "maximum_queued",
                        0,
                    )
                ),
            )
            self.maximum_engine_active_calls = max(
                self.maximum_engine_active_calls,
                int(
                    payload.get(
                        "engine_active_calls",
                        0,
                    )
                ),
            )

        return event

    def add_tim_status(
        self,
        message: String,
    ) -> dict[str, Any]:
        """Store one TIM status snapshot."""
        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError:
            payload = {
                "parse_error": True,
                "raw": str(message.data),
            }

        event = {
            "type": "tim_status",
            "received_monotonic_ns": time.monotonic_ns(),
            "payload": payload,
        }

        with self._lock:
            self.tim_status_count += 1
            self.latest_tim_status = payload

        return event

    def summary(self) -> dict[str, Any]:
        """Build the final machine-readable run summary."""
        with self._lock:
            latest_executor = {}

            if self.latest_reid_status:
                latest_executor = (
                    self.latest_reid_status.get(
                        "executor",
                        {},
                    )
                )

            latest_tim_transport = {}

            if self.latest_tim_status:
                latest_tim_transport = (
                    self.latest_tim_status.get(
                        "appearance_async_reid",
                        {},
                    )
                )

            return {
                "schema": "p044_transport_evidence_summary_v1",
                "condition": self.condition,
                "started_ns": self.started_ns,
                "completed_ns": time.monotonic_ns(),
                "counts": {
                    "timing": self.timing_count,
                    "requests": self.request_count,
                    "results": self.result_count,
                    "successful_results": (
                        self.successful_results
                    ),
                    "failed_results": (
                        self.failed_results
                    ),
                    "reid_status": (
                        self.reid_status_count
                    ),
                    "tim_status": self.tim_status_count,
                },
                "detector": {
                    "infer_ms": metric_summary(
                        self.infer_ms
                    ),
                    "e2e_det_ms": metric_summary(
                        self.e2e_det_ms
                    ),
                    "container_queue_ms": (
                        metric_summary(
                            self.container_queue_ms
                        )
                    ),
                    "pub_dt_ms": metric_summary(
                        self.pub_dt_ms
                    ),
                },
                "reid": {
                    "queue_delay_ms": metric_summary(
                        self.reid_queue_delay_ms
                    ),
                    "worker_ms": metric_summary(
                        self.reid_worker_ms
                    ),
                    "end_to_end_ms": metric_summary(
                        self.reid_e2e_ms
                    ),
                    "maximum_executor_queued": (
                        self.maximum_executor_queued
                    ),
                    "maximum_engine_active_calls": (
                        self.maximum_engine_active_calls
                    ),
                    "latest_executor": latest_executor,
                    "latest_tim_transport": (
                        latest_tim_transport
                    ),
                },
            }


class EvidenceCollectorNode(Node):
    """Subscribe to all evidence topics and write compact JSONL."""

    def __init__(
        self,
        *,
        output_dir: Path,
        condition: str,
    ) -> None:
        super().__init__(
            "p044_transport_evidence_collector"
        )

        self.output_dir = output_dir
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.events_path = (
            self.output_dir / "events.jsonl"
        )
        self.summary_path = (
            self.output_dir / "summary.json"
        )

        self.accumulator = EvidenceAccumulator(
            condition=condition
        )
        self._event_file = self.events_path.open(
            "w",
            encoding="utf-8",
        )
        self._write_lock = threading.Lock()

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.create_subscription(
            Timing,
            "/timing",
            self._on_timing,
            qos,
        )
        self.create_subscription(
            String,
            "/perception/reid/status",
            self._on_reid_status,
            qos,
        )
        self.create_subscription(
            AppearanceEmbeddingRequest,
            "/appearance/reid/request",
            self._on_request,
            qos,
        )
        self.create_subscription(
            AppearanceEmbeddingResult,
            "/appearance/reid/result",
            self._on_result,
            qos,
        )
        self.create_subscription(
            String,
            "/target_memory_mars/status",
            self._on_tim_status,
            qos,
        )

    def _write_event(
        self,
        event: dict[str, Any],
    ) -> None:
        line = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
        )

        with self._write_lock:
            self._event_file.write(line + "\n")
            self._event_file.flush()

    def _on_timing(
        self,
        message: Timing,
    ) -> None:
        self._write_event(
            self.accumulator.add_timing(message)
        )

    def _on_request(
        self,
        message: AppearanceEmbeddingRequest,
    ) -> None:
        self._write_event(
            self.accumulator.add_request(message)
        )

    def _on_result(
        self,
        message: AppearanceEmbeddingResult,
    ) -> None:
        self._write_event(
            self.accumulator.add_result(message)
        )

    def _on_reid_status(
        self,
        message: String,
    ) -> None:
        self._write_event(
            self.accumulator.add_reid_status(
                message
            )
        )

    def _on_tim_status(
        self,
        message: String,
    ) -> None:
        self._write_event(
            self.accumulator.add_tim_status(
                message
            )
        )

    def close(self) -> None:
        """Flush events and write the final summary."""
        summary = self.accumulator.summary()

        self.summary_path.write_text(
            json.dumps(
                summary,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with self._write_lock:
            self._event_file.flush()
            self._event_file.close()


def parse_args() -> argparse.Namespace:
    """Parse collector arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--condition",
        required=True,
        choices=CONDITION_CHOICES,
    )
    return parser.parse_args()


def main() -> int:
    """Run the ROS evidence collector."""
    args = parse_args()

    rclpy.init()
    node = EvidenceCollectorNode(
        output_dir=args.output_dir,
        condition=args.condition,
    )

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
