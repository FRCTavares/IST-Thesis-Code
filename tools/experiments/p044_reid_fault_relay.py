#!/usr/bin/env python3
"""Experiment-only ROS relay for P044 ReID result fault injection.

The perception process publishes genuine executor results on an isolated raw
topic. This relay either forwards, suppresses, converts, or delays those
results before TIM-MARS receives them.

The relay is evidence infrastructure only. It does not import or modify the
TIM-MARS runtime, target memory, target selection, CPU MARS scoring, canonical
configuration, perception executor, or Hailo inference implementation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import heapq
import json
from pathlib import Path
import sys
import time
from typing import Any

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
from thesis_msgs.msg import AppearanceEmbeddingResult as RosResult

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceEmbeddingResult as DomainResult,
)
from thesis_bringup.tim_mars.appearance_ros_transport import (
    result_from_ros_message,
    result_to_ros_message,
)


FAULT_MODES = (
    "none",
    "suppress_result",
    "backend_failure",
    "delay_result",
)

STATUS_SCHEMA = "p044_reid_fault_relay_status_v1"
SUMMARY_SCHEMA = "p044_reid_fault_relay_summary_v1"
INJECTED_FAILURE_REASON = "p044_injected_backend_failure"


@dataclass(frozen=True)
class FaultConfiguration:
    """Validated immutable relay configuration."""

    mode: str
    delay_ms: float


def validate_fault_configuration(
    mode: str,
    delay_ms: float,
) -> FaultConfiguration:
    """Validate one explicit experiment fault configuration."""
    resolved_mode = str(mode).strip()
    resolved_delay_ms = float(delay_ms)

    if resolved_mode not in FAULT_MODES:
        raise ValueError(
            f"unsupported P044 fault mode: {resolved_mode}"
        )

    if resolved_delay_ms < 0.0:
        raise ValueError(
            "fault delay must be non-negative"
        )

    if (
        resolved_mode == "delay_result"
        and resolved_delay_ms <= 0.0
    ):
        raise ValueError(
            "delay_result requires a positive delay"
        )

    return FaultConfiguration(
        mode=resolved_mode,
        delay_ms=resolved_delay_ms,
    )


def delay_ns_from_ms(delay_ms: float) -> int:
    """Convert a validated millisecond delay to nanoseconds."""
    value = float(delay_ms)

    if value < 0.0:
        raise ValueError(
            "delay must be non-negative"
        )

    return int(round(value * 1_000_000.0))


def injected_backend_failure(
    result: DomainResult,
    *,
    now_ns: int,
) -> DomainResult:
    """Replace a valid worker result with one explicit failure result."""
    started_ns = max(
        1,
        int(result.started_ns),
    )
    completed_ns = max(
        started_ns,
        int(now_ns),
    )

    return DomainResult(
        request_id=int(result.request_id),
        backend_name=str(result.backend_name),
        embedding_space=str(
            result.embedding_space
        ),
        dimension=int(result.dimension),
        started_ns=started_ns,
        completed_ns=completed_ns,
        embedding=None,
        error=INJECTED_FAILURE_REASON,
    )


class P044ReidFaultRelay(Node):
    """Relay RepVGG result messages under one explicit fault mode."""

    def __init__(
        self,
        *,
        input_topic: str,
        output_topic: str,
        status_topic: str,
        status_period_s: float,
        summary_path: Path,
        mode: str,
        delay_ms: float,
    ) -> None:
        super().__init__(
            "p044_reid_fault_relay"
        )

        configuration = (
            validate_fault_configuration(
                mode,
                delay_ms,
            )
        )

        self.input_topic = str(
            input_topic
        ).strip()
        self.output_topic = str(
            output_topic
        ).strip()
        self.status_topic = str(
            status_topic
        ).strip()
        self.status_period_s = max(
            0.05,
            float(status_period_s),
        )
        self.summary_path = Path(
            summary_path
        )
        self.mode = configuration.mode
        self.delay_ms = (
            configuration.delay_ms
        )
        self.delay_ns = delay_ns_from_ms(
            self.delay_ms
        )

        if not self.input_topic:
            raise ValueError(
                "input topic cannot be empty"
            )

        if not self.output_topic:
            raise ValueError(
                "output topic cannot be empty"
            )

        if self.input_topic == self.output_topic:
            raise ValueError(
                "input and output topics must differ"
            )

        self.started_ns = time.monotonic_ns()

        self.received = 0
        self.forwarded = 0
        self.suppressed = 0
        self.injected_backend_failures = 0
        self.delayed_scheduled = 0
        self.delayed_published = 0
        self.malformed_inputs = 0
        self.publish_errors = 0

        self._delay_sequence = 0
        self._delayed: list[
            tuple[int, int, RosResult]
        ] = []

        transport_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=(
                ReliabilityPolicy.BEST_EFFORT
            ),
            durability=DurabilityPolicy.VOLATILE,
        )

        status_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=(
                ReliabilityPolicy.BEST_EFFORT
            ),
            durability=DurabilityPolicy.VOLATILE,
        )

        self._publisher = self.create_publisher(
            RosResult,
            self.output_topic,
            transport_qos,
        )
        self._subscriber = (
            self.create_subscription(
                RosResult,
                self.input_topic,
                self._on_result,
                transport_qos,
            )
        )
        self._status_publisher = (
            self.create_publisher(
                String,
                self.status_topic,
                status_qos,
            )
        )

        drain_period_s = min(
            0.05,
            max(
                0.005,
                (
                    self.delay_ms / 1000.0
                    / 10.0
                    if self.delay_ms > 0.0
                    else 0.05
                ),
            ),
        )

        self._delay_timer = self.create_timer(
            drain_period_s,
            self._drain_delayed,
        )
        self._status_timer = self.create_timer(
            self.status_period_s,
            self._publish_status,
        )

        self.get_logger().info(
            "Enabled experiment-only P044 ReID fault relay "
            f"(mode={self.mode}, "
            f"delay_ms={self.delay_ms:.3f}, "
            f"input={self.input_topic}, "
            f"output={self.output_topic}, "
            f"status={self.status_topic})"
        )

    def _publish_result(
        self,
        message: RosResult,
        *,
        delayed: bool,
    ) -> None:
        try:
            self._publisher.publish(
                message
            )
        except Exception as exc:
            self.publish_errors += 1
            self.get_logger().error(
                "P044 fault relay publication failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        self.forwarded += 1

        if delayed:
            self.delayed_published += 1

    def _on_result(
        self,
        message: RosResult,
    ) -> None:
        self.received += 1

        try:
            result = result_from_ros_message(
                message
            )
        except Exception as exc:
            self.malformed_inputs += 1
            self.get_logger().warning(
                "P044 relay rejected malformed result: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        if self.mode == "suppress_result":
            self.suppressed += 1
            return

        if self.mode == "backend_failure":
            failure = injected_backend_failure(
                result,
                now_ns=time.monotonic_ns(),
            )
            self.injected_backend_failures += 1
            self._publish_result(
                result_to_ros_message(
                    failure
                ),
                delayed=False,
            )
            return

        outbound = result_to_ros_message(
            result
        )

        if self.mode == "delay_result":
            self._delay_sequence += 1
            due_ns = (
                time.monotonic_ns()
                + self.delay_ns
            )
            heapq.heappush(
                self._delayed,
                (
                    due_ns,
                    self._delay_sequence,
                    outbound,
                ),
            )
            self.delayed_scheduled += 1
            return

        self._publish_result(
            outbound,
            delayed=False,
        )

    def _drain_delayed(self) -> None:
        if not self._delayed:
            return

        now_ns = time.monotonic_ns()

        while (
            self._delayed
            and self._delayed[0][0] <= now_ns
        ):
            _, _, message = heapq.heappop(
                self._delayed
            )
            self._publish_result(
                message,
                delayed=True,
            )

    def status_payload(
        self,
    ) -> dict[str, Any]:
        """Return one machine-readable fault-relay snapshot."""
        return {
            "schema": STATUS_SCHEMA,
            "timestamp_ns": (
                time.monotonic_ns()
            ),
            "started_ns": int(
                self.started_ns
            ),
            "mode": self.mode,
            "delay_ms": self.delay_ms,
            "input_topic": self.input_topic,
            "output_topic": self.output_topic,
            "status_topic": self.status_topic,
            "counts": {
                "received": int(
                    self.received
                ),
                "forwarded": int(
                    self.forwarded
                ),
                "suppressed": int(
                    self.suppressed
                ),
                "injected_backend_failures": int(
                    self.injected_backend_failures
                ),
                "delayed_scheduled": int(
                    self.delayed_scheduled
                ),
                "delayed_published": int(
                    self.delayed_published
                ),
                "malformed_inputs": int(
                    self.malformed_inputs
                ),
                "publish_errors": int(
                    self.publish_errors
                ),
            },
            "delayed_queue_depth": len(
                self._delayed
            ),
            "claim_boundary": {
                "experiment_only": True,
                "production_node_modified": False,
                "cpu_mars_authoritative": True,
                "repvgg_observational": True,
                "target_memory_modified": False,
                "target_selection_modified": False,
                "canonical_policy_modified": False,
            },
        }

    def _publish_status(self) -> None:
        message = String()
        message.data = json.dumps(
            self.status_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )

        try:
            self._status_publisher.publish(
                message
            )
        except Exception:
            return

    def write_summary(self) -> None:
        """Write final local evidence accounting."""
        payload = self.status_payload()
        payload["schema"] = SUMMARY_SCHEMA
        payload["completed_ns"] = (
            time.monotonic_ns()
        )
        payload["abandoned_delayed"] = len(
            self._delayed
        )

        self.summary_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.summary_path.write_text(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the experiment-only relay CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Inject controlled P044 faults between "
            "perception ReID results and TIM-MARS."
        )
    )
    parser.add_argument(
        "--input-topic",
        default="/appearance/reid/result_raw",
    )
    parser.add_argument(
        "--output-topic",
        default="/appearance/reid/result",
    )
    parser.add_argument(
        "--status-topic",
        default="/p044/reid_fault/status",
    )
    parser.add_argument(
        "--status-period-s",
        type=float,
        default=0.25,
    )
    parser.add_argument(
        "--mode",
        choices=FAULT_MODES,
        default="none",
    )
    parser.add_argument(
        "--delay-ms",
        type=float,
        default=1000.0,
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        required=True,
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        configuration = (
            validate_fault_configuration(
                args.mode,
                args.delay_ms,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))

    rclpy.init(args=[])

    node: P044ReidFaultRelay | None = None
    status = 0

    try:
        node = P044ReidFaultRelay(
            input_topic=args.input_topic,
            output_topic=args.output_topic,
            status_topic=args.status_topic,
            status_period_s=(
                args.status_period_s
            ),
            summary_path=args.summary_path,
            mode=configuration.mode,
            delay_ms=(
                configuration.delay_ms
            ),
        )
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except ExternalShutdownException:
        pass
    except Exception as exc:
        print(
            "ERROR: P044 fault relay failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        status = 1
    finally:
        if node is not None:
            try:
                node.write_summary()
            except Exception as exc:
                print(
                    "ERROR: could not write relay summary: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
                status = 1

            try:
                node.destroy_node()
            except Exception:
                pass

        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

    return status


if __name__ == "__main__":
    raise SystemExit(main())
