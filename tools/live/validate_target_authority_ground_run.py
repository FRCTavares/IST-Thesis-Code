#!/usr/bin/env python3
"""Run one isolated ROS ground check of the live target-authority chain.

The check starts only dashboard_bridge_node, target_memory_mars_node, a
MAVROS-disabled control_ref_node, and a small rosbag recorder in a dedicated
ROS domain. Synthetic track and raw-target messages exercise the authority
contract without starting a camera, detector, tracker, MAVROS, or aircraft.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _configure_probe_ros_domain() -> None:
    """Set the requested domain before importing any ROS Python modules."""
    try:
        value_index = sys.argv.index("--ros-domain-id") + 1
        requested_domain = int(sys.argv[value_index])
    except (ValueError, IndexError):
        return
    os.environ["ROS_DOMAIN_ID"] = str(requested_domain)
    os.environ["RMW_FASTRTPS_USE_SHM"] = "0"


_configure_probe_ros_domain()

from geometry_msgs.msg import TwistStamped  # noqa: E402

import rclpy  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import (  # noqa: E402
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from std_msgs.msg import String  # noqa: E402

from thesis_msgs.msg import (  # noqa: E402
    TargetState,
    Track2D,
    Track2DArray,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TIM_CONFIG = (
    REPO_ROOT
    / "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
)
COMMAND_EPSILON = 1e-6
TARGET_ID = 7


class GroundCheckFailure(RuntimeError):
    """Raised when a live authority invariant is not observed."""


@dataclass
class ManagedProcess:
    """One isolated ROS process and its captured log stream."""

    name: str
    command: list[str]
    process: subprocess.Popen[bytes]
    log_path: Path
    log_stream: Any


class ProcessSet:
    """Start and stop the ROS processes owned by one ground run."""

    def __init__(self, *, cwd: Path, env: dict[str, str], log_dir: Path) -> None:
        """Create an empty managed process collection."""
        self._cwd = cwd
        self._env = env
        self._log_dir = log_dir
        self._processes: dict[str, ManagedProcess] = {}

    def start(self, name: str, command: list[str]) -> ManagedProcess:
        """Start one process group and capture its combined output."""
        log_path = self._log_dir / f"{name}.log"
        log_stream = log_path.open("wb")
        process = subprocess.Popen(
            command,
            cwd=self._cwd,
            env=self._env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        managed = ManagedProcess(
            name=name,
            command=command,
            process=process,
            log_path=log_path,
            log_stream=log_stream,
        )
        self._processes[name] = managed
        return managed

    def assert_alive(self) -> None:
        """Fail when any currently managed process has exited."""
        failed = [
            managed.name
            for managed in self._processes.values()
            if managed.process.poll() is not None
        ]
        if failed:
            raise GroundCheckFailure(
                "ROS process exited unexpectedly: " + ", ".join(failed)
            )

    def stop(self, name: str) -> None:
        """Stop and remove one managed process."""
        managed = self._processes.pop(name, None)
        if managed is None:
            return
        self._stop_managed(managed)

    def stop_all(self) -> None:
        """Stop all managed processes in reverse launch order."""
        for name in reversed(list(self._processes)):
            self.stop(name)

    @staticmethod
    def _stop_managed(managed: ManagedProcess) -> None:
        process = managed.process
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=4.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=2.0)
        managed.log_stream.close()

    def manifest(self) -> list[dict[str, Any]]:
        """Describe processes and commands for the evidence summary."""
        return [
            {
                "name": managed.name,
                "command": managed.command,
                "log": str(managed.log_path),
                "returncode": managed.process.poll(),
            }
            for managed in self._processes.values()
        ]


class AuthorityProbe(Node):
    """Publish synthetic inputs and collect controller-facing outputs."""

    def __init__(self) -> None:
        """Create synthetic publishers and evidence subscriptions."""
        super().__init__("target_authority_ground_probe")
        sensor_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.tracks_pub = self.create_publisher(
            Track2DArray,
            "/tracks",
            sensor_qos,
        )
        self.raw_target_pub = self.create_publisher(
            TargetState,
            "/target",
            sensor_qos,
        )
        self.create_subscription(
            TargetState,
            "/target_memory_mars",
            self._on_validated_target,
            sensor_qos,
        )
        self.create_subscription(
            TwistStamped,
            "/control_ref/cmd_vel",
            self._on_command,
            10,
        )
        self.create_subscription(
            String,
            "/target_memory_mars/status",
            self._on_status,
            sensor_qos,
        )
        self.commands: list[dict[str, Any]] = []
        self.validated_targets: list[dict[str, Any]] = []
        self.statuses: list[dict[str, Any]] = []
        self._frame_id = 0

    def _on_command(self, msg: TwistStamped) -> None:
        self.commands.append(
            {
                "monotonic_ns": time.monotonic_ns(),
                "vx": float(msg.twist.linear.x),
                "vy": float(msg.twist.linear.y),
                "yaw_z": float(msg.twist.angular.z),
            }
        )

    def _on_validated_target(self, msg: TargetState) -> None:
        self.validated_targets.append(
            {
                "monotonic_ns": time.monotonic_ns(),
                "id": int(msg.id),
                "cx": float(msg.cx),
                "h": float(msg.h),
                "score": float(msg.score),
                "quality": float(msg.quality),
            }
        )

    def _on_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            payload = {"raw": msg.data}
        payload["monotonic_ns"] = time.monotonic_ns()
        self.statuses.append(payload)

    def publish_raw_target(self) -> None:
        """Publish one plausible but non-authoritative raw target."""
        msg = TargetState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.frame_id = self._frame_id
        msg.id = TARGET_ID
        msg.cx = 500.0
        msg.cy = 320.0
        msg.w = 80.0
        msg.h = 80.0
        msg.score = 0.95
        msg.quality = 1.0
        self.raw_target_pub.publish(msg)

    def publish_tracks(self) -> None:
        """Publish one synthetic tracker observation for the selected ID."""
        self._frame_id += 1
        now = self.get_clock().now()
        msg = Track2DArray()
        msg.header.stamp = now.to_msg()
        msg.frame_id = self._frame_id
        msg.src_stamp_ns = now.nanoseconds
        msg.t_cam_msg_seen_ns = time.monotonic_ns()
        msg.t_track_cb_start_ns = msg.t_cam_msg_seen_ns
        msg.t_track_cb_end_ns = msg.t_cam_msg_seen_ns

        track = Track2D()
        track.id = TARGET_ID
        track.cx = 500.0
        track.cy = 320.0
        track.w = 80.0
        track.h = 80.0
        track.score = 0.95
        track.label = "person"
        msg.tracks.append(track)
        self.tracks_pub.publish(msg)

    def observe(
        self,
        duration_s: float,
        *,
        publish_tracks: bool = False,
        publish_raw: bool = False,
        health_check: Callable[[], None] | None = None,
    ) -> None:
        """Spin for a duration while optionally publishing synthetic inputs."""
        deadline = time.monotonic() + duration_s
        next_publish = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_publish:
                if publish_tracks:
                    self.publish_tracks()
                if publish_raw:
                    self.publish_raw_target()
                next_publish = now + 0.05
            rclpy.spin_once(self, timeout_sec=0.02)
            if health_check is not None:
                health_check()

    def wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_s: float,
        publish_tracks: bool = False,
        publish_raw: bool = False,
        health_check: Callable[[], None] | None = None,
    ) -> None:
        """Spin until a predicate passes or the timeout expires."""
        deadline = time.monotonic() + timeout_s
        next_publish = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_publish:
                if publish_tracks:
                    self.publish_tracks()
                if publish_raw:
                    self.publish_raw_target()
                next_publish = now + 0.05
            rclpy.spin_once(self, timeout_sec=0.02)
            if health_check is not None:
                health_check()
            if predicate():
                return
        raise GroundCheckFailure("Timed out waiting for a ROS authority condition")

    def mark(self) -> tuple[int, int, int]:
        """Return current sample offsets for a new evidence phase."""
        return len(self.commands), len(self.validated_targets), len(self.statuses)

    def has_subscription(self, topic_name: str, node_name: str) -> bool:
        """Return whether the named node owns a subscription endpoint."""
        return any(
            endpoint.node_name == node_name
            for endpoint in self.get_subscriptions_info_by_topic(topic_name)
        )

    def metrics_since(self, mark: tuple[int, int, int]) -> dict[str, Any]:
        """Summarize control, validated-target, and TIM status samples."""
        commands = self.commands[mark[0]:]
        targets = self.validated_targets[mark[1]:]
        statuses = self.statuses[mark[2]:]
        magnitudes = [command_magnitude(command) for command in commands]
        return {
            "command_samples": len(commands),
            "max_command_abs": max(magnitudes, default=0.0),
            "nonzero_command_samples": sum(
                magnitude > COMMAND_EPSILON for magnitude in magnitudes
            ),
            "validated_target_samples": len(targets),
            "validated_target_ids": sorted({target["id"] for target in targets}),
            "status_samples": len(statuses),
            "status_reasons": sorted(
                {
                    str(status.get("reason", ""))
                    for status in statuses
                    if status.get("reason")
                }
            ),
        }


def command_magnitude(command: dict[str, Any]) -> float:
    """Return the largest controlled-axis magnitude."""
    return max(abs(command["vx"]), abs(command["vy"]), abs(command["yaw_z"]))


def require(condition: bool, message: str) -> None:
    """Raise a ground-check failure when an invariant is false."""
    if not condition:
        raise GroundCheckFailure(message)


def api_post(api_port: int, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST JSON to the isolated dashboard and return status plus JSON."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{api_port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            status = int(response.status)
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read()
    return status, json.loads(body.decode("utf-8"))


def wait_for_dashboard(api_port: int, processes: ProcessSet) -> None:
    """Wait for the isolated dashboard HTTP API."""
    deadline = time.monotonic() + 10.0
    url = f"http://127.0.0.1:{api_port}/api/models"
    while time.monotonic() < deadline:
        processes.assert_alive()
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise GroundCheckFailure("Dashboard API did not become ready")


def wait_for_graph(probe: AuthorityProbe, processes: ProcessSet) -> None:
    """Wait for the exact TIM and control ROS graph endpoints."""
    deadline = time.monotonic() + 10.0
    graph: dict[str, int] = {}
    while time.monotonic() < deadline:
        rclpy.spin_once(probe, timeout_sec=0.05)
        processes.assert_alive()
        graph = {
            "tim_tracks_subscription": int(
                probe.has_subscription("/tracks", "target_memory_mars_node")
            ),
            "validated_publishers": probe.count_publishers(
                "/target_memory_mars"
            ),
            "command_publishers": probe.count_publishers(
                "/control_ref/cmd_vel"
            ),
            "command_samples": len(probe.commands),
        }
        if (
            graph["tim_tracks_subscription"] == 1
            and graph["validated_publishers"] >= 1
            and graph["command_publishers"] >= 1
            and graph["command_samples"] >= 3
        ):
            return
    raise GroundCheckFailure(f"ROS graph did not become ready: {graph}")


def assert_zero_phase(metrics: dict[str, Any], name: str) -> None:
    """Require a populated phase containing only zero control commands."""
    require(metrics["command_samples"] >= 3, f"{name}: too few control samples")
    require(
        metrics["max_command_abs"] <= COMMAND_EPSILON,
        f"{name}: observed non-zero control {metrics['max_command_abs']}",
    )


def wait_for_selected_target(
    probe: AuthorityProbe,
    processes: ProcessSet,
    mark: tuple[int, int, int],
) -> None:
    """Wait for validated target output and non-zero control."""
    probe.wait_until(
        lambda: (
            any(
                target["id"] == TARGET_ID
                for target in probe.validated_targets[mark[1]:]
            )
            and any(
                command_magnitude(command) > COMMAND_EPSILON
                for command in probe.commands[mark[0]:]
            )
        ),
        timeout_s=3.0,
        publish_tracks=True,
        health_check=processes.assert_alive,
    )


def wait_for_zero_target(
    probe: AuthorityProbe,
    processes: ProcessSet,
    mark: tuple[int, int, int],
) -> None:
    """Wait for an explicit zero validated-target message."""
    probe.wait_until(
        lambda: any(
            target["id"] == 0
            for target in probe.validated_targets[mark[1]:]
        ),
        timeout_s=2.0,
        publish_tracks=True,
        health_check=processes.assert_alive,
    )


def select_target(
    probe: AuthorityProbe,
    processes: ProcessSet,
    api_port: int,
    api_events: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Request explicit selection after TIM command discovery completes."""
    mark = probe.mark()
    deadline = time.monotonic() + 5.0
    while True:
        status, body = api_post(
            api_port,
            "/api/target",
            {"target": TARGET_ID},
        )
        api_events.append(
            {"path": "/api/target", "status": status, "body": body}
        )
        if status != 503 or time.monotonic() >= deadline:
            break
        probe.observe(0.10, health_check=processes.assert_alive)
    require(status == 200, f"Target selection returned HTTP {status}: {body}")
    wait_for_selected_target(probe, processes, mark)
    return mark


def settled_zero_metrics(
    probe: AuthorityProbe,
    processes: ProcessSet,
    *,
    publish_tracks: bool = True,
    publish_raw: bool = False,
) -> dict[str, Any]:
    """Collect a settled zero-control phase after a reset."""
    probe.observe(
        0.15,
        publish_tracks=publish_tracks,
        publish_raw=publish_raw,
        health_check=processes.assert_alive,
    )
    mark = probe.mark()
    probe.observe(
        0.45,
        publish_tracks=publish_tracks,
        publish_raw=publish_raw,
        health_check=processes.assert_alive,
    )
    return probe.metrics_since(mark)


def sha256_file(path: Path) -> str:
    """Hash one retained evidence artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_text(*args: str) -> str:
    """Return stripped stdout from a non-mutating Git command."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def load_authority_events(path: Path) -> list[dict[str, Any]]:
    """Load the dashboard authority-generation JSONL stream."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON evidence summary with atomic replacement."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    """Parse isolated ground-run paths, domain, and ports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ros-domain-id", type=int, required=True)
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--ws-port", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    """Run all authority phases and retain the resulting evidence."""
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"[error] output directory is not empty: {output_dir}", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir()
    bag_dir = output_dir / "rosbag"
    event_log = output_dir / "target_authority_events.jsonl"

    env = dict(os.environ)
    env["ROS_DOMAIN_ID"] = str(args.ros_domain_id)
    env["RMW_FASTRTPS_USE_SHM"] = "0"
    env["ROS_LOG_DIR"] = str(output_dir / "ros_logs")

    dashboard_command = [
        "ros2", "run", "thesis_bringup", "dashboard_bridge_node",
        "--ros-args",
        "-p", "api_host:=127.0.0.1",
        "-p", f"api_port:={args.api_port}",
        "-p", "ws_host:=127.0.0.1",
        "-p", f"ws_port:={args.ws_port}",
        "-p", "runtime_reconfiguration_enabled:=false",
        "-p", f"target_authority_event_log_path:={event_log}",
        "-p", "validated_target_topic:=/target_memory_mars",
        "-p", "target_select_topic:=/target_memory_mars/select",
        "-p", "target_clear_topic:=/target_memory_mars/clear",
    ]
    tim_command = [
        "ros2", "run", "thesis_bringup", "target_memory_mars_node",
        "--ros-args", "--params-file", str(TIM_CONFIG),
        "-p", "appearance_enabled:=false",
        "-p", "auto_select_largest:=false",
        "-p", "mirror_raw_target_selection:=false",
        "-p", "target_topic:=/target_memory_mars",
        "-p", "status_topic:=/target_memory_mars/status",
        "-p", "select_topic:=/target_memory_mars/select",
        "-p", "clear_topic:=/target_memory_mars/clear",
    ]
    control_command = [
        "ros2", "run", "thesis_bringup", "control_ref_node",
        "--ros-args",
        "-p", "target_topic:=/target_memory_mars",
        "-p", "cmd_topic:=/control_ref/cmd_vel",
        "-p", "enable_mavros:=false",
        "-p", "rate_hz:=50.0",
        "-p", "stale_timeout_s:=0.25",
        "-p", "max_delta_yaw_z:=0.10",
        "-p", "max_delta_vx:=0.10",
    ]
    bag_command = [
        "ros2", "bag", "record", "--storage", "mcap",
        "-o", str(bag_dir), "--topics",
        "/tracks",
        "/target",
        "/target_memory_mars/select",
        "/target_memory_mars/clear",
        "/target_memory_mars",
        "/target_memory_mars/status",
        "/control_ref/cmd_vel",
    ]

    processes = ProcessSet(cwd=REPO_ROOT, env=env, log_dir=log_dir)
    summary: dict[str, Any] = {
        "evidence_schema_version": 1,
        "run_id": args.run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": False,
        "failure": None,
        "repository": {
            "commit": git_text("rev-parse", "HEAD"),
            "status_porcelain": git_text("status", "--porcelain"),
        },
        "isolation": {
            "ros_domain_id": args.ros_domain_id,
            "api_port": args.api_port,
            "ws_port": args.ws_port,
            "camera_started": False,
            "tracker_started": False,
            "mavros_started": False,
            "mavros_control_enabled": False,
        },
        "phases": {},
        "api_events": [],
    }
    probe: AuthorityProbe | None = None
    ros_initialised = False

    try:
        processes.start("dashboard", dashboard_command)
        processes.start("tim", tim_command)
        processes.start("control", control_command)
        processes.start("rosbag", bag_command)
        wait_for_dashboard(args.api_port, processes)

        rclpy.init(args=[])
        ros_initialised = True
        probe = AuthorityProbe()
        wait_for_graph(probe, processes)
        probe.observe(1.5, health_check=processes.assert_alive)

        mark = probe.mark()
        probe.observe(
            0.75,
            publish_raw=True,
            health_check=processes.assert_alive,
        )
        metrics = probe.metrics_since(mark)
        assert_zero_phase(metrics, "raw_target_bypass")
        summary["phases"]["raw_target_bypass"] = metrics

        mark = select_target(
            probe,
            processes,
            args.api_port,
            summary["api_events"],
        )
        probe.observe(
            0.30,
            publish_tracks=True,
            health_check=processes.assert_alive,
        )
        metrics = probe.metrics_since(mark)
        require(TARGET_ID in metrics["validated_target_ids"], "TIM did not validate target")
        require(metrics["nonzero_command_samples"] > 0, "Validated target did not drive control")
        summary["phases"]["explicit_select"] = metrics

        clear_mark = probe.mark()
        status, body = api_post(args.api_port, "/api/target", {"target": 0})
        summary["api_events"].append(
            {"path": "/api/target", "status": status, "body": body}
        )
        require(status == 200, f"Target clear returned HTTP {status}: {body}")
        wait_for_zero_target(probe, processes, clear_mark)
        metrics = settled_zero_metrics(probe, processes)
        assert_zero_phase(metrics, "explicit_clear")
        summary["phases"]["explicit_clear"] = metrics

        metrics = settled_zero_metrics(
            probe,
            processes,
            publish_tracks=True,
            publish_raw=True,
        )
        assert_zero_phase(metrics, "id_reuse_without_selection")
        require(
            metrics["validated_target_ids"] in ([0], []),
            "Reused tracker ID regained authority without selection",
        )
        summary["phases"]["id_reuse_without_selection"] = metrics

        select_target(probe, processes, args.api_port, summary["api_events"])
        switch_mark = probe.mark()
        status, body = api_post(
            args.api_port,
            "/api/model",
            {"model": "yolov8n"},
        )
        summary["api_events"].append(
            {"path": "/api/model", "status": status, "body": body}
        )
        require(status == 409, f"Frozen model switch returned HTTP {status}")
        wait_for_zero_target(probe, processes, switch_mark)
        metrics = settled_zero_metrics(probe, processes)
        assert_zero_phase(metrics, "model_switch_rejected")
        summary["phases"]["model_switch_rejected"] = metrics

        select_target(probe, processes, args.api_port, summary["api_events"])
        switch_mark = probe.mark()
        status, body = api_post(
            args.api_port,
            "/api/tracker",
            {"tracker": "bytetrack"},
        )
        summary["api_events"].append(
            {"path": "/api/tracker", "status": status, "body": body}
        )
        require(status == 409, f"Frozen tracker switch returned HTTP {status}")
        wait_for_zero_target(probe, processes, switch_mark)
        metrics = settled_zero_metrics(probe, processes)
        assert_zero_phase(metrics, "tracker_switch_rejected")
        summary["phases"]["tracker_switch_rejected"] = metrics

        select_target(probe, processes, args.api_port, summary["api_events"])
        stale_mark = probe.mark()
        probe.observe(0.60, health_check=processes.assert_alive)
        stale_metrics = probe.metrics_since(stale_mark)
        require(
            stale_metrics["nonzero_command_samples"] > 0,
            "Stale phase did not begin with a prior non-zero command",
        )
        settled_mark = probe.mark()
        probe.observe(0.30, health_check=processes.assert_alive)
        settled_stale = probe.metrics_since(settled_mark)
        assert_zero_phase(settled_stale, "stale_validated_target")
        stale_metrics["settled_zero_window"] = settled_stale
        summary["phases"]["stale_validated_target"] = stale_metrics

        reacquire_mark = probe.mark()
        wait_for_selected_target(probe, processes, reacquire_mark)
        processes.stop("tim")
        probe.observe(0.60, health_check=processes.assert_alive)
        stopped_mark = probe.mark()
        probe.observe(0.30, health_check=processes.assert_alive)
        stopped_metrics = probe.metrics_since(stopped_mark)
        assert_zero_phase(stopped_metrics, "tim_node_restart_stopped")

        processes.start("tim_restart", tim_command)
        probe.wait_until(
            lambda: probe.has_subscription(
                "/tracks",
                "target_memory_mars_node",
            ),
            timeout_s=5.0,
            health_check=processes.assert_alive,
        )
        restarted_metrics = settled_zero_metrics(
            probe,
            processes,
            publish_tracks=True,
            publish_raw=True,
        )
        assert_zero_phase(restarted_metrics, "tim_node_restart")
        require(
            restarted_metrics["validated_target_ids"] == [0],
            "Restarted TIM accepted an ID without explicit selection",
        )
        summary["phases"]["tim_node_restart"] = {
            "stopped": stopped_metrics,
            "restarted": restarted_metrics,
        }

        require(event_log.is_file(), "Authority event log was not written")
        authority_events = load_authority_events(event_log)
        generations = [int(event["generation"]) for event in authority_events]
        require(generations == list(range(8)), f"Unexpected authority generations: {generations}")
        reasons = [str(event["reason"]) for event in authority_events]
        for required_reason in {
            "startup",
            "operator_select",
            "operator_clear",
            "model_switch:yolov8n",
            "tracker_switch:bytetrack",
        }:
            require(required_reason in reasons, f"Missing authority event: {required_reason}")
        summary["authority_events"] = authority_events
        summary["passed"] = True
    except Exception as exc:
        summary["failure"] = f"{type(exc).__name__}: {exc}"
    finally:
        if probe is not None:
            probe.destroy_node()
        if ros_initialised:
            rclpy.shutdown()
        summary["processes_before_stop"] = processes.manifest()
        processes.stop_all()

    summary["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    bag_metadata = bag_dir / "metadata.yaml"
    bag_files = sorted(bag_dir.glob("*.mcap")) if bag_dir.is_dir() else []
    summary["artifacts"] = {
        "authority_event_log": str(event_log),
        "authority_event_log_sha256": (
            sha256_file(event_log) if event_log.is_file() else None
        ),
        "rosbag": str(bag_dir),
        "rosbag_metadata_present": bag_metadata.is_file(),
        "rosbag_mcap_files": [
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in bag_files
        ],
    }
    if not bag_metadata.is_file() or not bag_files:
        summary["passed"] = False
        if summary["failure"] is None:
            summary["failure"] = "Ground evidence rosbag did not finalize"

    summary_path = output_dir / "ground_check_summary.json"
    write_json_atomic(summary_path, summary)
    print(json.dumps({
        "passed": summary["passed"],
        "summary": str(summary_path),
        "failure": summary["failure"],
    }, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
