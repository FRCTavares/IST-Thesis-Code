#!/usr/bin/env python3
"""Append one structured operator event to a physical-trial event log.

Issue #50/#74 evidence retention: the live stack records target select/clear
transactions (``target_authority_events.jsonl``) but nothing records operator
decisions during a physical trial -- trial boundaries, pilot takeover, aborts
and their reasons, and whether a trial is accepted or rejected for
physical/integrity reasons. Those are needed to reconstruct the
controller-facing thesis metrics afterward and are not derivable from the bag.

This is a small append-only JSONL writer. Each invocation appends exactly one
event and prints the exact file path written. The log is tied to an explicit
``RUN_ID`` (matching the live-stack run directory) so it can be archived with
the retained bag, and it is never truncated or overwritten.

Timebase: every event carries ``ts_utc`` (system wall clock, UTC) which aligns
directly with ROS bag timestamps and message header stamps (the live stack
uses no simulated time). When written on the Pi it also carries
``ts_monotonic_ns`` (``time.monotonic_ns``), host-local, which aligns with the
pipeline ``t_*_ns`` fields; ``trial_start`` additionally records a
``clock_pair`` sample so any monotonic-domain measurement can be mapped to bag
time.

Examples:
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" \
        --condition baseline --scenario following
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" \
        --track-id 7 --intended-physical-person "person in red jacket"
    python3 tools/live/operator_event.py operator_takeover --run-id "$RUN_ID" \
        --trigger pilot_rc --from-mode GUIDED --to-mode LOITER
    python3 tools/live/operator_event.py abort --run-id "$RUN_ID" \
        --abort-class safety --reason "wrong-target authority near distractor"
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" \
        --verdict rejected --integrity-reason wrong_scenario
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_LOG_NAME = "operator_events.jsonl"

EVENT_TYPES = (
    "trial_start",
    "trial_end",
    "target_selected",
    "operator_takeover",
    "abort",
    "unexpected_behavior",
    "trial_verdict",
)

ABORT_CLASSES = (
    "safety",
    "geofence",
    "behaviour",
    "equipment",
    "weather",
    "communications",
    "other",
)

TRIAL_CONDITIONS = ("baseline", "candidate")
VERDICTS = ("accepted", "rejected")
SEVERITIES = ("info", "concern", "critical")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_sha(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def resolve_run_id(explicit: str | None) -> str:
    run_id = explicit or os.environ.get("RUN_ID") or ""
    run_id = run_id.strip()
    if not run_id:
        raise SystemExit(
            "[error] no RUN_ID: pass --run-id or export RUN_ID to the exact "
            "live-stack run id (shown at live-stack startup and used as the "
            "bag-name / ros2_ws/log/live_stack/<run-id>/ prefix)"
        )
    if not all(ch.isalnum() or ch in "_.-" for ch in run_id) or ".." in run_id:
        raise SystemExit(
            f"[error] RUN_ID must use letters, digits, '_', '-', '.' without "
            f"'..': {run_id!r}"
        )
    return run_id


def resolve_log_path(run_id: str, log_dir: str | None) -> Path:
    """Always nest the JSONL under the run id so two runs never share a file.

    Default base is the live-stack run directory
    (``ros2_ws/log/live_stack/<run-id>/``), where the launcher's stop-time
    archival picks it up.
    """
    base = (
        Path(log_dir).expanduser()
        if log_dir
        else _repo_root() / "ros2_ws" / "log" / "live_stack"
    )
    return base / run_id / DEFAULT_LOG_NAME


def build_detail(args: argparse.Namespace) -> dict[str, Any]:
    event = args.event
    if event == "trial_start":
        detail: dict[str, Any] = {
            "condition": args.condition,
            "scenario": args.scenario,
            "recovery_enabled": bool(args.recovery_enabled),
        }
        detail["clock_pair"] = {
            "monotonic_ns": time.monotonic_ns(),
            "system_ns": time.time_ns(),
        }
        if args.invocation:
            detail["invocation"] = args.invocation
        return detail
    if event == "trial_end":
        return {"end_reason": args.end_reason}
    if event == "target_selected":
        return {
            "requested_track_id": args.track_id,
            "method": args.method,
            "intended_physical_person": args.intended_physical_person,
        }
    if event == "operator_takeover":
        return {
            "trigger": args.trigger,
            "expected_from_mode": args.from_mode,
            "expected_to_mode": args.to_mode,
        }
    if event == "abort":
        return {"abort_class": args.abort_class, "reason": args.reason}
    if event == "unexpected_behavior":
        return {"description": args.description, "severity": args.severity}
    if event == "trial_verdict":
        return {
            "verdict": args.verdict,
            "integrity_reason": args.integrity_reason,
        }
    raise SystemExit(f"[error] unhandled event type: {event}")


def validate_event(record: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems; empty means the event is valid.

    Importable by readers and tests so the same rules apply everywhere.
    """
    errors: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {SCHEMA_VERSION}, got "
            f"{record.get('schema_version')!r}"
        )

    event = record.get("event")
    if event not in EVENT_TYPES:
        errors.append(f"event must be one of {EVENT_TYPES}, got {event!r}")

    ts_utc = record.get("ts_utc")
    if not isinstance(ts_utc, str) or not ts_utc:
        errors.append("ts_utc missing or not a string")
    else:
        try:
            datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"ts_utc is not ISO-8601: {ts_utc!r}")

    run_id = record.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        errors.append("run_id missing or not a string")

    detail = record.get("detail")
    if not isinstance(detail, dict):
        errors.append("detail missing or not an object")
        return errors

    if event == "abort":
        if detail.get("abort_class") not in ABORT_CLASSES:
            errors.append(
                f"abort.detail.abort_class must be one of {ABORT_CLASSES}"
            )
        if not str(detail.get("reason") or "").strip():
            errors.append("abort.detail.reason must be a non-empty string")
    elif event == "trial_start":
        if detail.get("condition") not in TRIAL_CONDITIONS:
            errors.append(
                f"trial_start.detail.condition must be one of {TRIAL_CONDITIONS}"
            )
        if not str(detail.get("scenario") or "").strip():
            errors.append("trial_start.detail.scenario must be non-empty")
    elif event == "trial_verdict":
        if detail.get("verdict") not in VERDICTS:
            errors.append(
                f"trial_verdict.detail.verdict must be one of {VERDICTS}"
            )
        if not str(detail.get("integrity_reason") or "").strip():
            errors.append(
                "trial_verdict.detail.integrity_reason must be non-empty"
            )
    elif event == "target_selected":
        if not isinstance(detail.get("requested_track_id"), int):
            errors.append(
                "target_selected.detail.requested_track_id must be an integer"
            )
        if not str(detail.get("intended_physical_person") or "").strip():
            errors.append(
                "target_selected.detail.intended_physical_person must be "
                "non-empty (the human intent behind the track id)"
            )
    elif event == "operator_takeover":
        if not str(detail.get("trigger") or "").strip():
            errors.append("operator_takeover.detail.trigger must be non-empty")
    elif event == "unexpected_behavior":
        if not str(detail.get("description") or "").strip():
            errors.append(
                "unexpected_behavior.detail.description must be non-empty"
            )
    elif event == "trial_end":
        if not str(detail.get("end_reason") or "").strip():
            errors.append("trial_end.detail.end_reason must be non-empty")

    return errors


def append_event(path: Path, record: dict[str, Any]) -> None:
    """Append one event as a single JSON line. Never truncates the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o640)
    try:
        os.write(fd, encoded)
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--trial-id", default=None)
    parser.add_argument(
        "--log-dir",
        default=None,
        help=(
            "Directory for the JSONL log (default: "
            "ros2_ws/log/live_stack/<run-id>/)."
        ),
    )
    parser.add_argument("--note", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="event", required=True)

    p = sub.add_parser("trial_start", help="Start of a retained trial.")
    _add_common(p)
    p.add_argument("--condition", required=True, choices=TRIAL_CONDITIONS)
    p.add_argument("--scenario", required=True)
    p.add_argument(
        "--recovery-enabled",
        action="store_true",
        help="Record that candidate yaw recovery was armed for this trial.",
    )
    p.add_argument(
        "--invocation",
        default=None,
        help="The exact start_live_stack.sh command used for this trial.",
    )

    p = sub.add_parser("trial_end", help="End of a retained trial.")
    _add_common(p)
    p.add_argument("--end-reason", required=True)

    p = sub.add_parser("target_selected", help="Operator selected a target.")
    _add_common(p)
    p.add_argument("--track-id", required=True, type=int)
    p.add_argument("--method", default="dashboard")
    p.add_argument("--intended-physical-person", required=True)

    p = sub.add_parser("operator_takeover", help="Pilot/operator took control.")
    _add_common(p)
    p.add_argument("--trigger", required=True)
    p.add_argument("--from-mode", default=None)
    p.add_argument("--to-mode", default=None)

    p = sub.add_parser("abort", help="Trial aborted.")
    _add_common(p)
    p.add_argument(
        "--abort-class", required=True, choices=ABORT_CLASSES, dest="abort_class"
    )
    p.add_argument("--reason", required=True)

    p = sub.add_parser(
        "unexpected_behavior", help="Something unexpected was observed."
    )
    _add_common(p)
    p.add_argument("--description", required=True)
    p.add_argument("--severity", default="concern", choices=SEVERITIES)

    p = sub.add_parser(
        "trial_verdict", help="Accept or reject a trial for physical/integrity reasons."
    )
    _add_common(p)
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--integrity-reason", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    run_id = resolve_run_id(args.run_id)
    log_path = resolve_log_path(run_id, args.log_dir)

    repo_root = _repo_root()
    now = datetime.now(timezone.utc)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event": args.event,
        "ts_utc": now.isoformat().replace("+00:00", "Z"),
        "ts_monotonic_ns": time.monotonic_ns(),
        "host": os.uname().nodename,
        "run_id": run_id,
        "trial_id": args.trial_id,
        "git_sha": _git_sha(repo_root),
        "detail": build_detail(args),
    }
    if args.note:
        record["detail"].setdefault("note", args.note)

    problems = validate_event(record)
    if problems:
        for problem in problems:
            print(f"[error] {problem}", file=sys.stderr)
        return 2

    append_event(log_path, record)
    print(str(log_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
