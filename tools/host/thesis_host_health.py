#!/usr/bin/env python3
"""Conservative host-only availability monitor for the thesis Raspberry Pi.

The monitor may reconnect the configured NetworkManager device, restart
tailscaled, or restart the SSH socket after repeated failures. It never starts
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
    root_path: Path,
    min_free_bytes: int,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
) -> dict[str, Any]:
    """Collect the minimal host state needed for safe recovery decisions."""
    nm_state = command_stdout(
        runner,
        ["nmcli", "-g", "GENERAL.STATE", "device", "show", interface],
    )
    default_route = bool(
        command_stdout(runner, ["ip", "route", "show", "default"])
    )

    tailscale_backend = "Unavailable"
    tailscale_online = False
    tailscale_raw = command_stdout(runner, ["tailscale", "status", "--json"])
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
    network_ok = network_manager_active and network_connected and default_route
    tailscale_ok = (
        tailscaled_active
        and tailscale_backend == "Running"
        and tailscale_online
    )
    ssh_ok = ssh_socket_active or ssh_service_active

    return {
        "network_manager_active": network_manager_active,
        "network_connected": network_connected,
        "default_route": default_route,
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
) -> list[str]:
    """Choose bounded host-only recovery actions."""
    actions: list[str] = []

    def eligible(name: str) -> bool:
        failures = state[f"{name}_failures"]
        last_recovery = state[f"last_{name}_recovery_epoch"]
        return (
            failures >= failure_threshold
            and now_epoch - last_recovery >= cooldown_seconds
        )

    if not snapshot["network_ok"] and eligible("network"):
        actions.append("network_reconnect")
    if (
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
    "tailscale_restart": ["systemctl", "restart", "tailscaled.service"],
    "ssh_socket_restart": ["systemctl", "restart", "ssh.socket"],
}

ACTION_STATE_NAMES = {
    "network_reconnect": "network",
    "tailscale_restart": "tailscale",
    "ssh_socket_restart": "ssh",
}


def execute_actions(
    actions: Sequence[str],
    *,
    interface: str,
    dry_run: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = run_command,
) -> dict[str, int]:
    """Execute selected actions and return their result codes."""
    results: dict[str, int] = {}
    for action in actions:
        command = list(ACTION_COMMANDS[action])
        if action == "network_reconnect":
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
        "--interface",
        default=os.environ.get("THESIS_HOST_INTERFACE", "wlan0"),
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

    state_path = args.state_dir / "state.json"
    state = load_state(state_path)
    snapshot = inspect_host(
        interface=args.interface,
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
    )
    action_results = execute_actions(
        actions,
        interface=args.interface,
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
        "snapshot": public_snapshot,
        "state": updated,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
