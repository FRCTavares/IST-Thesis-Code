#!/usr/bin/env python3
"""Retrieve an explicitly identified Pixhawk DataFlash log through MAVROS.

Issue #50 retained-evidence helper.

The scientific association workflow is deliberately explicit:

1. capture a DataFlash catalogue before the retained run;
2. capture another catalogue after the run;
3. compare the two catalogues;
4. require exactly one newly observed log ID;
5. explicitly supply that ID and its reported size to ``download``.

The helper never chooses the highest ID, newest timestamp, newest file, or
filesystem mtime. An ambiguous catalogue comparison fails closed.

The MAVROS path was physically validated on 25 September 2026 against the real
Pixhawk while disarmed, using target 10.1 through the canonical field network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

LIST_SERVICE = "/mavros/log_transfer/raw/log_request_list"
DATA_SERVICE = "/mavros/log_transfer/raw/log_request_data"
END_SERVICE = "/mavros/log_transfer/raw/log_request_end"
ENTRY_TOPIC = "/mavros/log_transfer/raw/log_entry"
DATA_TOPIC = "/mavros/log_transfer/raw/log_data"
STATE_TOPIC = "/mavros/state"

UTC_USABLE_AFTER = 946684800  # 2000-01-01; rejects epoch/boot-like timestamps.


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_new(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")

    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.link(tmp_path, path)
        tmp_path.unlink()
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _write_bytes_new(path: Path, payload: bytes | bytearray) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")

    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp)

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        os.link(tmp_path, path)
        tmp_path.unlink()
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _load_catalogue(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported catalogue schema: {path}")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError(f"catalogue entries missing or invalid: {path}")

    ids: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid catalogue entry in {path}")

        log_id = entry.get("id")
        size = entry.get("size")

        if not isinstance(log_id, int) or not (0 <= log_id <= 0xFFFF):
            raise ValueError(f"invalid DataFlash log id in {path}: {log_id!r}")

        if not isinstance(size, int) or size <= 0:
            raise ValueError(
                f"invalid DataFlash size for log {log_id} in {path}: {size!r}"
            )

        if log_id in ids:
            raise ValueError(f"duplicate DataFlash log id {log_id} in {path}")

        ids.add(log_id)

    return payload


def compare_catalogues(
    before_path: Path,
    after_path: Path,
) -> tuple[int, dict[str, Any]]:
    before = _load_catalogue(before_path)
    after = _load_catalogue(after_path)

    before_entries = {int(entry["id"]): entry for entry in before["entries"]}
    after_entries = {int(entry["id"]): entry for entry in after["entries"]}

    before_ids = set(before_entries)
    after_ids = set(after_entries)

    new_ids = sorted(after_ids - before_ids)
    removed_ids = sorted(before_ids - after_ids)

    selected = after_entries[new_ids[0]] if len(new_ids) == 1 else None

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "compared_at_utc": _utc_now(),
        "before": str(before_path.resolve()),
        "after": str(after_path.resolve()),
        "before_log_ids": sorted(before_ids),
        "after_log_ids": sorted(after_ids),
        "new_log_ids": new_ids,
        "removed_log_ids": removed_ids,
        "status": "unique_new_log" if selected is not None else "ambiguous",
        "selected": selected,
    }

    return (0 if selected is not None else 2), result


def _import_ros():
    import rclpy
    from mavros_msgs.msg import LogData, LogEntry, State
    from mavros_msgs.srv import LogRequestData, LogRequestEnd, LogRequestList

    return (
        rclpy,
        State,
        LogEntry,
        LogData,
        LogRequestList,
        LogRequestData,
        LogRequestEnd,
    )


def _wait_disarmed(node, rclpy, State, timeout_s: float = 5.0) -> dict[str, Any]:
    latest = None

    def on_state(msg):
        nonlocal latest
        latest = msg

    subscription = node.create_subscription(State, STATE_TOPIC, on_state, 10)
    deadline = time.monotonic() + timeout_s

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if latest is not None:
                break
    finally:
        node.destroy_subscription(subscription)

    if latest is None:
        raise RuntimeError(f"no MAVROS state received from {STATE_TOPIC}")

    if not bool(latest.connected):
        raise RuntimeError("MAVROS reports FCU disconnected")

    if bool(latest.armed):
        raise RuntimeError("aircraft is armed; DataFlash retrieval refused")

    return {
        "connected": bool(latest.connected),
        "armed": bool(latest.armed),
        "guided": bool(latest.guided),
        "manual_input": bool(latest.manual_input),
        "mode": str(latest.mode),
        "system_status": int(latest.system_status),
    }


def _call_service(node, rclpy, client, request, timeout_s: float):
    future = client.call_async(request)
    deadline = time.monotonic() + timeout_s

    while rclpy.ok() and not future.done() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)

    if not future.done() or future.result() is None:
        raise RuntimeError("MAVROS service call timed out")

    return future.result()


def _end_transfer(node, rclpy, LogRequestEnd) -> str:
    client = node.create_client(LogRequestEnd, END_SERVICE)

    if not client.wait_for_service(timeout_sec=2.0):
        return "service_unavailable"

    try:
        response = _call_service(
            node,
            rclpy,
            client,
            LogRequestEnd.Request(),
            timeout_s=5.0,
        )
    except RuntimeError:
        return "timeout"

    return "success" if bool(response.success) else "rejected"


def capture_catalogue(
    output: Path,
    *,
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    (
        rclpy,
        State,
        LogEntry,
        _LogData,
        LogRequestList,
        _LogRequestData,
        LogRequestEnd,
    ) = _import_ros()

    rclpy.init()
    node = rclpy.create_node("thesis_dataflash_catalogue")

    entries: dict[int, Any] = {}
    reported_num_logs: int | None = None
    reported_last_log_num: int | None = None
    last_rx: float | None = None

    def on_entry(msg):
        nonlocal reported_num_logs, reported_last_log_num, last_rx
        entries[int(msg.id)] = msg
        reported_num_logs = int(msg.num_logs)
        reported_last_log_num = int(msg.last_log_num)
        last_rx = time.monotonic()

    try:
        state = _wait_disarmed(node, rclpy, State)

        subscription = node.create_subscription(
            LogEntry,
            ENTRY_TOPIC,
            on_entry,
            100,
        )
        client = node.create_client(LogRequestList, LIST_SERVICE)

        if not client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(f"service unavailable: {LIST_SERVICE}")

        request = LogRequestList.Request()
        request.start = 0
        request.end = 0xFFFF

        future = client.call_async(request)
        deadline = time.monotonic() + timeout_s

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

            if future.done() and future.result() is not None:
                if not bool(future.result().success):
                    raise RuntimeError("LogRequestList returned success=false")

                if (
                    reported_num_logs is not None
                    and len(entries) >= reported_num_logs
                ):
                    break

                if (
                    entries
                    and last_rx is not None
                    and time.monotonic() - last_rx >= 2.0
                ):
                    break

        if not future.done() or future.result() is None:
            raise RuntimeError("DataFlash catalogue request timed out")

        if not bool(future.result().success):
            raise RuntimeError("DataFlash catalogue request rejected")

        if not entries:
            raise RuntimeError("DataFlash catalogue returned no entries")

        serialized = []
        for log_id in sorted(entries):
            msg = entries[log_id]
            sec = int(msg.time_utc.sec)
            nanosec = int(msg.time_utc.nanosec)
            usable = sec >= UTC_USABLE_AFTER

            serialized.append(
                {
                    "id": int(msg.id),
                    "num_logs": int(msg.num_logs),
                    "last_log_num": int(msg.last_log_num),
                    "size": int(msg.size),
                    "time_utc": {
                        "sec": sec,
                        "nanosec": nanosec,
                        "usable": usable,
                        "iso8601": (
                            datetime.fromtimestamp(
                                sec + nanosec / 1_000_000_000,
                                tz=timezone.utc,
                            ).isoformat()
                            if usable
                            else None
                        ),
                    },
                }
            )

        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "captured_at_utc": _utc_now(),
            "hardware_path": "mavros_log_transfer",
            "hardware_validation": "validated_2026-09-25",
            "state": state,
            "service": LIST_SERVICE,
            "topic": ENTRY_TOPIC,
            "reported_num_logs": reported_num_logs,
            "reported_last_log_num": reported_last_log_num,
            "entries_received": len(serialized),
            "entries": serialized,
        }

        _write_json_new(output, payload)
        node.destroy_subscription(subscription)
        return payload
    finally:
        try:
            result = _end_transfer(node, rclpy, LogRequestEnd)
            print(f"log_request_end={result}")
        finally:
            node.destroy_node()
            rclpy.shutdown()


def _missing_ranges(mask: bytearray) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    cursor = 0
    size = len(mask)

    while cursor < size:
        start = mask.find(b"\x00", cursor)
        if start < 0:
            break

        end = mask.find(b"\x01", start)
        if end < 0:
            end = size

        result.append((start, end - start))
        cursor = end

    return result


def download_log(
    *,
    log_id: int,
    expected_size: int,
    output: Path,
    retries: int = 5,
    timeout_s: float = 300.0,
    quiet_s: float = 3.0,
) -> dict[str, Any]:
    if not (0 <= log_id <= 0xFFFF):
        raise ValueError("--log-id must fit uint16")

    if not (0 < expected_size <= 0xFFFFFFFF):
        raise ValueError("--expected-size must fit positive uint32")

    if retries < 0:
        raise ValueError("--retries must be >= 0")

    output = output.resolve()
    metadata_path = output.with_name(output.name + ".retrieval.json")

    if output.exists() or metadata_path.exists():
        raise FileExistsError(
            "refusing to overwrite existing DataFlash output or retrieval metadata"
        )

    (
        rclpy,
        State,
        _LogEntry,
        LogData,
        _LogRequestList,
        LogRequestData,
        LogRequestEnd,
    ) = _import_ros()

    rclpy.init()
    node = rclpy.create_node("thesis_dataflash_explicit_download")

    payload = bytearray(expected_size)
    covered = bytearray(expected_size)
    last_rx: float | None = None
    message_count = 0

    def on_data(msg):
        nonlocal last_rx, message_count

        if int(msg.id) != log_id:
            return

        offset = int(msg.offset)
        chunk = bytes(msg.data)

        if not chunk or offset < 0 or offset >= expected_size:
            return

        end = min(offset + len(chunk), expected_size)
        chunk = chunk[: end - offset]

        payload[offset:end] = chunk
        covered[offset:end] = b"\x01" * len(chunk)

        last_rx = time.monotonic()
        message_count += 1

    def request_range(client, offset: int, count: int) -> None:
        request = LogRequestData.Request()
        request.id = log_id
        request.offset = offset
        request.count = count

        response = _call_service(
            node,
            rclpy,
            client,
            request,
            timeout_s=5.0,
        )

        if not bool(response.success):
            raise RuntimeError(
                f"DataFlash request rejected: id={log_id} "
                f"offset={offset} count={count}"
            )

    def receive_until_quiet() -> None:
        nonlocal last_rx

        deadline = time.monotonic() + timeout_s

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)

            if last_rx is not None and time.monotonic() - last_rx >= quiet_s:
                return

        raise RuntimeError("DataFlash transfer did not become quiescent in time")

    try:
        state = _wait_disarmed(node, rclpy, State)

        subscription = node.create_subscription(
            LogData,
            DATA_TOPIC,
            on_data,
            10000,
        )
        client = node.create_client(LogRequestData, DATA_SERVICE)

        if not client.wait_for_service(timeout_sec=5.0):
            raise RuntimeError(f"service unavailable: {DATA_SERVICE}")

        print(
            f"requesting explicit DataFlash id={log_id} "
            f"size={expected_size}"
        )

        request_range(client, 0, expected_size)
        receive_until_quiet()

        for retry in range(1, retries + 1):
            gaps = _missing_ranges(covered)

            if not gaps:
                break

            missing = expected_size - covered.count(1)
            print(
                f"retry={retry} missing_ranges={len(gaps)} "
                f"missing_bytes={missing}"
            )

            for offset, count in gaps:
                request_range(client, offset, count)

            last_rx = None
            receive_until_quiet()

        missing_ranges = _missing_ranges(covered)

        if missing_ranges:
            missing_bytes = expected_size - covered.count(1)
            raise RuntimeError(
                f"incomplete DataFlash transfer: "
                f"{missing_bytes} bytes remain across "
                f"{len(missing_ranges)} ranges"
            )

        _write_bytes_new(output, payload)

        sha256 = hashlib.sha256(payload).hexdigest()

        metadata: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "retrieved_at_utc": _utc_now(),
            "hardware_path": "mavros_log_transfer",
            "hardware_validation": "validated_2026-09-25",
            "selection": "explicit_log_id",
            "log_id": log_id,
            "expected_size": expected_size,
            "bytes": output.stat().st_size,
            "sha256": sha256,
            "output": str(output),
            "state": state,
            "service": DATA_SERVICE,
            "topic": DATA_TOPIC,
            "log_data_messages": message_count,
        }

        _write_json_new(metadata_path, metadata)
        node.destroy_subscription(subscription)
        return metadata
    finally:
        try:
            result = _end_transfer(node, rclpy, LogRequestEnd)
            print(f"log_request_end={result}")
        finally:
            node.destroy_node()
            rclpy.shutdown()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    catalogue = sub.add_parser(
        "catalogue",
        help="capture the FCU DataFlash catalogue without selecting a log",
    )
    catalogue.add_argument("--output", required=True, type=Path)
    catalogue.add_argument("--timeout", type=float, default=20.0)

    compare = sub.add_parser(
        "compare",
        help="compare explicit before/after catalogues and require one new ID",
    )
    compare.add_argument("--before", required=True, type=Path)
    compare.add_argument("--after", required=True, type=Path)
    compare.add_argument("--output", required=True, type=Path)

    download = sub.add_parser(
        "download",
        help="download one explicitly supplied DataFlash log ID",
    )
    download.add_argument("--log-id", required=True, type=int)
    download.add_argument("--expected-size", required=True, type=int)
    download.add_argument("--output", required=True, type=Path)
    download.add_argument("--retries", type=int, default=5)
    download.add_argument("--timeout", type=float, default=300.0)
    download.add_argument("--quiet", type=float, default=3.0)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "catalogue":
            payload = capture_catalogue(
                args.output,
                timeout_s=args.timeout,
            )
            print(
                f"[ok] catalogue: {payload['entries_received']} entries -> "
                f"{args.output.resolve()}"
            )
            return 0

        if args.command == "compare":
            code, result = compare_catalogues(args.before, args.after)
            _write_json_new(args.output, result)

            print(f"status={result['status']}")
            print(f"new_log_ids={result['new_log_ids']}")
            print(f"removed_log_ids={result['removed_log_ids']}")

            if code == 0:
                selected = result["selected"]
                print(f"log_id={selected['id']}")
                print(f"expected_size={selected['size']}")
                print(
                    f"[ok] unique new DataFlash log -> "
                    f"{args.output.resolve()}"
                )
            else:
                print(
                    "[error] catalogue comparison is ambiguous; "
                    "do not guess a DataFlash log ID",
                    file=sys.stderr,
                )

            return code

        if args.command == "download":
            metadata = download_log(
                log_id=args.log_id,
                expected_size=args.expected_size,
                output=args.output,
                retries=args.retries,
                timeout_s=args.timeout,
                quiet_s=args.quiet,
            )

            print(
                f"[ok] downloaded explicit log id={metadata['log_id']} "
                f"bytes={metadata['bytes']} "
                f"sha256={metadata['sha256']}"
            )
            print(f"path={metadata['output']}")
            return 0

        raise RuntimeError(f"unsupported command: {args.command}")

    except (
        FileExistsError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
