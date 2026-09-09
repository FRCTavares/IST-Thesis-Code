#!/usr/bin/env python3
"""Write a versioned, machine-readable provenance record for one live run.

Issue #54 requires that every retained recording carry a metadata record
containing: Git commit/state, the exact invocation, scenario/date, hardware
and software versions, model/config SHA-256 hashes, the resolved ROS
parameters each node was launched with, a topic/QoS inventory, the selected
target, and the runtime switch history. This script assembles schema v1 of
that record from information the live launcher already has (or can cheaply
introspect via `ros2 topic info` / `ros2 param dump`) and writes it atomically
beside the recording it describes. Node parameters that must reflect the
running node (e.g. control_ref_node) are read live and, on query failure, are
recorded as query_ok=false -- never backfilled from source-code defaults.
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


def _parse_param_dump(text: str, node: str) -> dict[str, Any]:
    """Parse `ros2 param dump <node>` YAML into a flat {name: value} dict.

    Raises ValueError when the text does not contain a usable parameter block
    for the node -- we must never silently fall back to source-code defaults.
    """
    import yaml  # PyYAML ships with the ROS 2 tooling.

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ValueError(f"parameter dump is not valid YAML: {exc}") from exc

    if not isinstance(loaded, dict):
        raise ValueError("parameter dump did not contain a mapping")

    block = None
    for candidate in (node, node.lstrip("/"), f"/{node.lstrip('/')}"):
        if candidate in loaded and isinstance(loaded[candidate], dict):
            block = loaded[candidate]
            break
    if block is None and len(loaded) == 1:
        # `ros2 param dump` emits exactly one top-level node key.
        (only_value,) = loaded.values()
        if isinstance(only_value, dict):
            block = only_value
    if block is None:
        raise ValueError(f"no parameter block for node {node!r} in dump")

    params = block.get("ros__parameters", block)
    if not isinstance(params, dict) or not params:
        raise ValueError(f"node {node!r} exposed no parameters")

    return {str(key): value for key, value in params.items()}


def query_node_parameters(
    node: str,
    *,
    dump_file: str | None = None,
    skip_live: bool = False,
    timeout_s: float = 8.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a running node's parameters, or record why it could not.

    Returns ``(parameters, meta)``. On any failure ``parameters`` is empty and
    ``meta['query_ok']`` is False with an ``error`` string -- the caller must
    surface that as a provenance failure rather than substituting defaults.
    """
    if dump_file is not None:
        source = "file"
        try:
            text = Path(dump_file).read_text(encoding="utf-8")
        except OSError as exc:
            return {}, {"source": source, "query_ok": False, "error": str(exc)}
        try:
            params = _parse_param_dump(text, node)
        except ValueError as exc:
            return {}, {"source": source, "query_ok": False, "error": str(exc)}
        return params, {
            "source": source,
            "query_ok": True,
            "parameter_count": len(params),
            "dump_file": dump_file,
        }

    source = "runtime_query"
    if skip_live:
        return {}, {
            "source": source,
            "query_ok": False,
            "error": "live node parameter query skipped (--skip-node-param-query)",
        }

    node_fqn = node if node.startswith("/") else f"/{node}"
    try:
        result = subprocess.run(
            ["ros2", "param", "dump", node_fqn, "--timeout", "3"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, {"source": source, "query_ok": False, "error": str(exc)}

    # `ros2 param dump` exits 0 even when the node is absent, printing a
    # diagnostic to stderr, so the exit code alone is not trustworthy.
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        return {}, {
            "source": source,
            "query_ok": False,
            "error": stderr or f"ros2 param dump exited {result.returncode}",
        }
    if not (result.stdout or "").strip():
        return {}, {
            "source": source,
            "query_ok": False,
            "error": stderr or "ros2 param dump produced no output (node not found)",
        }
    try:
        params = _parse_param_dump(result.stdout, node_fqn)
    except ValueError as exc:
        return {}, {"source": source, "query_ok": False, "error": str(exc)}

    return params, {
        "source": source,
        "query_ok": True,
        "parameter_count": len(params),
    }


def parse_expected_params(items: list[str]) -> dict[str, dict[str, Any]]:
    """Parse `--expect-param NODE:KEY[=VALUE]` into {node: {key: value|None}}."""
    expected: dict[str, dict[str, Any]] = {}
    for item in items:
        if ":" not in item:
            raise SystemExit(f"--expect-param must be NODE:KEY[=VALUE], got: {item}")
        node, rest = item.split(":", 1)
        if "=" in rest:
            key, value = rest.split("=", 1)
            expected.setdefault(node, {})[key] = value
        else:
            expected.setdefault(node, {})[rest] = None
    return expected


def _stringify_param(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value)


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
    parser.add_argument(
        "--resolved-node-params",
        action="append",
        default=[],
        metavar="NODE",
        help=(
            "Query the running NODE's resolved parameters via `ros2 param "
            "dump` and record them (repeatable). A failed query is recorded "
            "as query_ok=false, never replaced with source defaults."
        ),
    )
    parser.add_argument(
        "--resolved-node-params-file",
        action="append",
        default=[],
        metavar="NODE=PATH",
        help=(
            "Read NODE's resolved parameters from a `ros2 param dump` YAML "
            "file instead of a live query (offline / test use; repeatable)."
        ),
    )
    parser.add_argument(
        "--expect-param",
        action="append",
        default=[],
        metavar="NODE:KEY[=VALUE]",
        help=(
            "Assert a specific resolved parameter is present (and optionally "
            "equals VALUE); recorded for the validator (repeatable)."
        ),
    )
    parser.add_argument(
        "--skip-node-param-query",
        action="store_true",
        help=(
            "Do not run the live `ros2 param dump` for --resolved-node-params "
            "(offline / test use). The node is then recorded as query_ok=false "
            "and never backfilled from defaults."
        ),
    )
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

    resolved_parameters = parse_params(args.param)
    resolved_parameters_meta: dict[str, Any] = {}

    dump_files: dict[str, str] = {}
    for item in args.resolved_node_params_file:
        if "=" not in item:
            raise SystemExit(
                f"--resolved-node-params-file must be NODE=PATH, got: {item}"
            )
        node, path = item.split("=", 1)
        dump_files[node] = path

    query_nodes = list(dict.fromkeys(list(args.resolved_node_params) + list(dump_files)))
    for node in query_nodes:
        params, meta = query_node_parameters(
            node,
            dump_file=dump_files.get(node),
            skip_live=args.skip_node_param_query and node not in dump_files,
        )
        resolved_parameters_meta[node] = meta
        if params:
            merged = dict(resolved_parameters.get(node, {}))
            for key, value in params.items():
                merged[key] = _stringify_param(value)
            resolved_parameters[node] = merged

    expected_parameters = parse_expected_params(args.expect_param)

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
        "resolved_parameters": resolved_parameters,
        "resolved_parameters_meta": resolved_parameters_meta,
        "expected_parameters": expected_parameters,
        "topic_qos_inventory": topic_qos_inventory,
        "target": target_summary,
        "runtime_switch_history": switch_history,
    }

    write_atomic(args.output, payload)
    print(f"[ok] wrote live-run metadata: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
