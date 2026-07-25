#!/usr/bin/env python3
"""Conservative host-only availability monitor for the thesis Raspberry Pi.

In unattended mode the monitor may reconnect Wi-Fi, restart tailscaled, or
restart the SSH socket after repeated failures. In Pixhawk mode it requires the
configured AERONEXT Wi-Fi profile and keeps tailscaled stopped. It never starts
ROS, MAVROS, the live thesis stack, or any aircraft-facing process.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence


DEFAULT_STATE: dict[str, int] = {
    "network_failures": 0,
    "tailscale_failures": 0,
    "ssh_failures": 0,
    "last_network_recovery_epoch": 0,
    "last_network_manager_recovery_epoch": 0,
    "last_tailscale_recovery_epoch": 0,
    "last_ssh_recovery_epoch": 0,
}


def run_command(
    command: Sequence[str],
    *,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded command without invoking a shell."""
    try:
        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            list(command),
            124,
            "",
            str(exc),
        )


def command_ok(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: Sequence[str],
) -> bool:
    """Return whether a bounded command completed successfully."""
    return runner(command, timeout=15.0).returncode == 0


def command_stdout(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: Sequence[str],
) -> str:
    """Return stripped stdout, or an empty string on failure."""
    result = runner(command, timeout=15.0)
    return result.stdout.strip() if result.returncode == 0 else ""


def inspect_host(
    *,
    interface: str,
    mode: str,
    pixhawk_wifi_connection: str,
    root_path: Path,
    min_free_bytes: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
) -> dict[str, Any]:
    """Collect the minimal host state needed for safe recovery decisions."""
    nm_state = command_stdout(
        runner,
        ["nmcli", "-g", "GENERAL.STATE", "device", "show", interface],
    )
    active_wifi_connection = command_stdout(
        runner,
        ["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", interface],
    )
    default_route_raw = command_stdout(
        runner,
        ["ip", "route", "show", "default", "dev", interface],
    )
    default_route = bool(default_route_raw)
    default_gateway = ""
    route_fields = default_route_raw.split()
    if "via" in route_fields:
        gateway_index = route_fields.index("via") + 1
        if gateway_index < len(route_fields):
            default_gateway = route_fields[gateway_index]

    gateway_reachable = False
    if mode == "unattended" and default_gateway:
        gateway_reachable = command_ok(
            runner,
            [
                "ping",
                "-I",
                interface,
                "-c",
                "1",
                "-W",
                "2",
                default_gateway,
            ],
        )

    tailscale_backend = "Unavailable"
    tailscale_online = False
    tailscale_raw = ""
    if mode == "unattended":
        tailscale_raw = command_stdout(
            runner, ["tailscale", "status", "--json"]
        )
    if tailscale_raw:
        try:
            tailscale_status = json.loads(tailscale_raw)
            tailscale_backend = str(
                tailscale_status.get("BackendState", "Unknown")
            )
            tailscale_online = bool(
                (tailscale_status.get("Self") or {}).get("Online", False)
            )
        except (TypeError, ValueError):
            tailscale_backend = "InvalidStatus"

    disk = shutil.disk_usage(root_path)
    network_manager_active = command_ok(
        runner,
        ["systemctl", "is-active", "--quiet", "NetworkManager.service"],
    )
    tailscaled_active = command_ok(
        runner,
        ["systemctl", "is-active", "--quiet", "tailscaled.service"],
    )
    ssh_socket_active = command_ok(
        runner,
        ["systemctl", "is-active", "--quiet", "ssh.socket"],
    )
    ssh_service_active = command_ok(
        runner,
        ["systemctl", "is-active", "--quiet", "ssh.service"],
    )

    network_connected = nm_state.startswith("100")
    expected_wifi_active = (
        mode != "pixhawk"
        or active_wifi_connection == pixhawk_wifi_connection
    )
    network_config_ok = (
        network_manager_active
        and network_connected
        and default_route
        and expected_wifi_active
    )
    network_ok = (
        network_config_ok
        if mode == "pixhawk"
        else network_config_ok and gateway_reachable
    )
    if mode == "pixhawk":
        tailscale_backend = "DisabledByPixhawkMode"
        tailscale_ok = not tailscaled_active
    else:
        tailscale_ok = (
            tailscaled_active
            and tailscale_backend == "Running"
            and tailscale_online
        )
    ssh_ok = ssh_socket_active or ssh_service_active

    return {
        "network_manager_active": network_manager_active,
        "network_connected": network_connected,
        "active_wifi_connection": active_wifi_connection,
        "expected_wifi_active": expected_wifi_active,
        "default_route": default_route,
        "default_gateway": default_gateway,
        "gateway_reachable": gateway_reachable,
        "network_config_ok": network_config_ok,
        "network_ok": network_ok,
        "tailscaled_active": tailscaled_active,
        "tailscale_backend": tailscale_backend,
        "tailscale_online": tailscale_online,
        "tailscale_ok": tailscale_ok,
        "ssh_socket_active": ssh_socket_active,
        "ssh_service_active": ssh_service_active,
        "ssh_ok": ssh_ok,
        "root_free_bytes": disk.free,
        "root_total_bytes": disk.total,
        "disk_ok": disk.free >= min_free_bytes,
    }


def load_state(path: Path) -> dict[str, int]:
    """Load recovery counters, treating missing or malformed state as empty."""
    state = dict(DEFAULT_STATE)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return state

    if not isinstance(payload, Mapping):
        return state
    for key in state:
        value = payload.get(key)
        if isinstance(value, int) and value >= 0:
            state[key] = value
    return state


def save_state(path: Path, state: Mapping[str, int]) -> None:
    """Atomically save root-owned monitor state."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(dict(state), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def update_failure_counters(
    snapshot: Mapping[str, Any],
    state: Mapping[str, int],
) -> dict[str, int]:
    """Update consecutive-failure counters from the current snapshot."""
    updated = dict(state)
    for name in ("network", "tailscale", "ssh"):
        key = f"{name}_failures"
        updated[key] = 0 if snapshot[f"{name}_ok"] else state[key] + 1
    return updated


def choose_recovery_actions(
    snapshot: Mapping[str, Any],
    state: Mapping[str, int],
    *,
    now_epoch: int,
    failure_threshold: int,
    cooldown_seconds: int,
    mode: str = "unattended",
) -> list[str]:
    """Choose bounded host-only recovery actions."""
    actions: list[str] = []

    def eligible(
        failure_name: str,
        recovery_name: str | None = None,
        *,
        threshold_multiplier: int = 1,
    ) -> bool:
        recovery_name = recovery_name or failure_name
        failures = state[f"{failure_name}_failures"]
        last_recovery = state[f"last_{recovery_name}_recovery_epoch"]
        return (
            failures >= failure_threshold * threshold_multiplier
            and now_epoch - last_recovery >= cooldown_seconds
        )

    if not snapshot["network_ok"]:
        if eligible(
            "network",
            "network_manager",
            threshold_multiplier=2,
        ):
            actions.append("network_manager_restart")
        elif eligible("network"):
            actions.append("network_reconnect")
    if mode == "pixhawk":
        if snapshot["tailscaled_active"]:
            actions.append("tailscale_stop")
    elif (
        snapshot["network_ok"]
        and not snapshot["tailscale_ok"]
        and eligible("tailscale")
    ):
        actions.append("tailscale_restart")
    if not snapshot["ssh_ok"] and eligible("ssh"):
        actions.append("ssh_socket_restart")
    return actions


ACTION_COMMANDS: dict[str, list[str]] = {
    "network_reconnect": ["nmcli", "device", "connect"],
    "network_manager_restart": [
        "systemctl",
        "restart",
        "NetworkManager.service",
    ],
    "tailscale_restart": ["systemctl", "restart", "tailscaled.service"],
    "tailscale_stop": ["systemctl", "stop", "tailscaled.service"],
    "ssh_socket_restart": ["systemctl", "restart", "ssh.socket"],
}

ACTION_STATE_NAMES = {
    "network_reconnect": "network",
    "network_manager_restart": "network_manager",
    "tailscale_restart": "tailscale",
    "tailscale_stop": "tailscale",
    "ssh_socket_restart": "ssh",
}


def execute_actions(
    actions: Sequence[str],
    *,
    interface: str,
    mode: str = "unattended",
    pixhawk_wifi_connection: str = "",
    dry_run: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
) -> dict[str, int]:
    """Execute selected actions and return their result codes."""
    results: dict[str, int] = {}
    for action in actions:
        command = list(ACTION_COMMANDS[action])
        if action == "network_reconnect":
            if mode == "pixhawk":
                command = [
                    "nmcli",
                    "connection",
                    "up",
                    pixhawk_wifi_connection,
                    "ifname",
                    interface,
                ]
            else:
                command.append(interface)
        if dry_run:
            results[action] = 0
            continue
        results[action] = runner(command, timeout=45.0).returncode
    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line and environment configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("unattended", "pixhawk"),
        default=os.environ.get("THESIS_HOST_MODE", "unattended"),
    )
    parser.add_argument(
        "--interface",
        default=os.environ.get("THESIS_HOST_INTERFACE", "wlan0"),
    )
    parser.add_argument(
        "--pixhawk-wifi-connection",
        default=os.environ.get(
            "THESIS_HOST_PIXHAWK_WIFI_CONNECTION", "ISR Aero.Next GCS"
        ),
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "THESIS_HOST_STATE_DIR",
                "/var/lib/thesis-host-health",
            )
        ),
    )
    parser.add_argument(
        "--failure-threshold",
        type=int,
        default=int(os.environ.get("THESIS_HOST_FAILURE_THRESHOLD", "3")),
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=int(os.environ.get("THESIS_HOST_COOLDOWN_SECONDS", "900")),
    )
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=float(os.environ.get("THESIS_HOST_MIN_FREE_GIB", "20")),
    )
    parser.add_argument("--root-path", type=Path, default=Path("/"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Inspect the host, apply bounded recovery, and emit redacted JSON."""
    args = parse_args(argv)
    if args.failure_threshold < 1:
        raise SystemExit("--failure-threshold must be at least 1")
    if args.cooldown_seconds < 60:
        raise SystemExit("--cooldown-seconds must be at least 60")
    if args.min_free_gib <= 0:
        raise SystemExit("--min-free-gib must be positive")
    if args.mode == "pixhawk" and not args.pixhawk_wifi_connection.strip():
        raise SystemExit("Pixhawk mode requires a Wi-Fi connection profile")

    state_path = args.state_dir / "state.json"
    state = load_state(state_path)
    snapshot = inspect_host(
        interface=args.interface,
        mode=args.mode,
        pixhawk_wifi_connection=args.pixhawk_wifi_connection,
        root_path=args.root_path,
        min_free_bytes=int(args.min_free_gib * 1024**3),
    )
    updated = update_failure_counters(snapshot, state)
    now_epoch = int(time.time())
    actions = choose_recovery_actions(
        snapshot,
        updated,
        now_epoch=now_epoch,
        failure_threshold=args.failure_threshold,
        cooldown_seconds=args.cooldown_seconds,
        mode=args.mode,
    )
    action_results = execute_actions(
        actions,
        interface=args.interface,
        mode=args.mode,
        pixhawk_wifi_connection=args.pixhawk_wifi_connection,
        dry_run=args.dry_run,
    )

    for action, result in action_results.items():
        if result == 0:
            name = ACTION_STATE_NAMES[action]
            updated[f"last_{name}_recovery_epoch"] = now_epoch

    if not args.dry_run:
        save_state(state_path, updated)

    public_snapshot = dict(snapshot)
    public_snapshot["root_free_gib"] = round(
        public_snapshot.pop("root_free_bytes") / 1024**3,
        2,
    )
    public_snapshot["root_total_gib"] = round(
        public_snapshot.pop("root_total_bytes") / 1024**3,
        2,
    )
    report = {
        "actions": action_results,
        "dry_run": args.dry_run,
        "interface": args.interface,
        "mode": args.mode,
        "snapshot": public_snapshot,
        "state": updated,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
