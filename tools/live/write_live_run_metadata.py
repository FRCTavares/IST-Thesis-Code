#!/usr/bin/env python3
"""Write a versioned, machine-readable provenance record for one live run.

Issue #54 requires that every retained recording carry a metadata record
containing: Git commit/state, the exact invocation, scenario/date, hardware
and software versions, model/config SHA-256 hashes, the resolved ROS
parameters each node was launched with, a topic/QoS inventory, the selected
target, and the runtime switch history. This script assembles schema v1 of
that record from information the live launcher already has (or can cheaply
introspect via `ros2 topic info`) and writes it atomically beside the
recording it describes.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_state(repo_root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    commit = run("rev-parse", "HEAD") or None
    branch = run("rev-parse", "--abbrev-ref", "HEAD") or None
    status = run("status", "--short")
    dirty_files = [line for line in status.splitlines() if line.strip()]
    return {
        "commit": commit,
        "branch": branch,
        "dirty": len(dirty_files) > 0,
        "dirty_file_count": len(dirty_files),
    }


def hardware_software(ros_distro: str) -> dict[str, Any]:
    hailort_version = None
    try:
        result = subprocess.run(
            ["hailortcli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            hailort_version = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass

    return {
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "python_version": platform.python_version(),
        "ros_distro": ros_distro or os.environ.get("ROS_DISTRO", ""),
        "hailort_version": hailort_version,
    }


def parse_hash_files(items: list[str]) -> dict[str, Any]:
    hashes: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--hash-file must be LABEL=PATH, got: {item}")
        label, raw_path = item.split("=", 1)
        path = Path(raw_path)
        hashes[label] = {
            "path": str(path),
            "exists": path.is_file(),
            "sha256": sha256_file(path),
        }
    return hashes


def parse_params(items: list[str]) -> dict[str, dict[str, str]]:
    params: dict[str, dict[str, str]] = {}
    for item in items:
        if ":" not in item or "=" not in item.split(":", 1)[1]:
            raise SystemExit(f"--param must be NODE:KEY=VALUE, got: {item}")
        node, rest = item.split(":", 1)
        key, value = rest.split("=", 1)
        params.setdefault(node, {})[key] = value
    return params


def introspect_topic_qos(topic: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["ros2", "topic", "info", "-v", topic],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}

    if result.returncode != 0:
        return {"error": result.stderr.strip() or "ros2 topic info failed"}

    text = result.stdout
    pub_count_val: int | None = None
    sub_count_val: int | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Publisher count:"):
            try:
                pub_count_val = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("Subscription count:"):
            try:
                sub_count_val = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass

    qos_fields = {}
    for key in ("Reliability", "Durability", "History", "Depth", "Lifespan"):
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key}:"):
                qos_fields[key.lower()] = stripped.split(":", 1)[1].strip()
                break

    return {
        "publisher_count": pub_count_val,
        "subscription_count": sub_count_val,
        "qos": qos_fields,
    }


def read_switch_history(log_path: Path | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if log_path is None or not log_path.is_file():
        return [], {"initial_selection": None, "final_selection": None, "switch_count": 0}

    events: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # dashboard_bridge_node always logs a "startup" event first (generation
    # 0), whatever the initial state is -- use that literal first event
    # rather than the first *selection*, which would wrongly report the
    # first mid-run operator pick as if it were the starting state.
    initial_selection = events[0].get("requested_target_id") if events else None

    final_selection = None
    if events:
        last = events[-1]
        if last.get("authority_state") == "selection_requested":
            final_selection = last.get("requested_target_id")

    target_summary = {
        "initial_selection": initial_selection,
        "final_selection": final_selection,
        "switch_count": len(events),
    }
    return events, target_summary


def write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scenario-tag", default="")
    parser.add_argument("--command", required=True)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--ros-distro", default="")
    parser.add_argument("--bag-kind", required=True, choices=["video", "dataset", "raw_image", "source"])
    parser.add_argument("--bag-out-dir", required=True)
    parser.add_argument("--recorded-topic", action="append", default=[])
    parser.add_argument("--hash-file", action="append", default=[], help="LABEL=PATH, repeatable")
    parser.add_argument("--param", action="append", default=[], help="NODE:KEY=VALUE, repeatable")
    parser.add_argument("--switch-history-log", type=Path, default=None)
    parser.add_argument(
        "--skip-topic-introspection",
        action="store_true",
        help="Do not shell out to `ros2 topic info` (for offline/unit-test use).",
    )
    args = parser.parse_args()

    switch_history, target_summary = read_switch_history(args.switch_history_log)

    topic_qos_inventory: dict[str, Any] = {}
    if not args.skip_topic_introspection:
        for topic in args.recorded_topic:
            topic_qos_inventory[topic] = introspect_topic_qos(topic)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.run_id,
        "scenario_tag": args.scenario_tag,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "bag": {
            "kind": args.bag_kind,
            "out_dir": args.bag_out_dir,
            "recorded_topics": list(args.recorded_topic),
        },
        "invocation": {
            "command": args.command,
            "cwd": os.getcwd(),
            "hostname": socket.gethostname(),
            "user": getpass.getuser(),
        },
        "git": git_state(args.repo_root),
        "hardware_software": hardware_software(args.ros_distro),
        "hashes": parse_hash_files(args.hash_file),
        "resolved_parameters": parse_params(args.param),
        "topic_qos_inventory": topic_qos_inventory,
        "target": target_summary,
        "runtime_switch_history": switch_history,
    }

    write_atomic(args.output, payload)
    print(f"[ok] wrote live-run metadata: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
