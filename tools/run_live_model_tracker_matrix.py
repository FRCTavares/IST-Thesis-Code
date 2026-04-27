#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_TRACKERS = ["sort", "ocsort", "bytetrack", "deepsort"]


def slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", s.strip())


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def nested(d: dict[str, Any], path: list[str], default: Any = "") -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def fetch_models(api_base: str) -> list[str]:
    data = http_json("GET", f"{api_base}/api/models")
    models = []
    for item in data.get("models", []):
        if item.get("available", False):
            models.append(str(item["key"]))
    return models


def post_model(api_base: str, model: str) -> dict[str, Any]:
    return http_json("POST", f"{api_base}/api/model", {"model": model})


def post_tracker(api_base: str, tracker: str) -> dict[str, Any]:
    return http_json("POST", f"{api_base}/api/tracker", {"tracker": tracker})


def run_cmd(cmd: list[str], log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
    return int(proc.returncode)

def run_ros2(args: list[str], timeout: float = 10.0) -> str:
    proc = subprocess.run(
        ["ros2", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
    )
    return proc.stdout.strip()


def tracker_param_matches(expected_tracker: str) -> tuple[bool, str]:
    try:
        value = run_ros2(["param", "get", "/tracker_node", "tracker_type"])
        return expected_tracker.lower() in value.lower(), value
    except Exception as exc:
        return False, repr(exc)


def summarise_json(json_path: Path) -> dict[str, Any]:
    if not json_path.exists():
        return {}

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "health_score": nested(data, ["health", "score"]),
        "detections_hz": nested(data, ["detection_stream", "hz"]),
        "timing_hz": nested(data, ["topics", "/timing", "hz"]),
        "tracker_hz": nested(data, ["topics", "/timing_tracker", "hz"]),
        "target_hz": nested(data, ["topics", "/timing_target", "hz"]),

        "e2e_det_p50_ms": nested(data, ["metrics", "/timing", "e2e_det_ms", "p50"]),
        "e2e_det_p95_ms": nested(data, ["metrics", "/timing", "e2e_det_ms", "p95"]),
        "e2e_det_p99_ms": nested(data, ["metrics", "/timing", "e2e_det_ms", "p99"]),

        "infer_p50_ms": nested(data, ["metrics", "/timing", "infer_ms", "p50"]),
        "infer_p95_ms": nested(data, ["metrics", "/timing", "infer_ms", "p95"]),
        "infer_p99_ms": nested(data, ["metrics", "/timing", "infer_ms", "p99"]),

        "pre_p95_ms": nested(data, ["metrics", "/timing", "pre_ms", "p95"]),
        "container_queue_p95_ms": nested(data, ["metrics", "/timing", "container_queue_ms", "p95"]),
        "pub_dt_p95_ms": nested(data, ["metrics", "/timing", "pub_dt_ms", "p95"]),

        "track_p50_ms": nested(data, ["metrics", "/timing_tracker", "track_ms", "p50"]),
        "track_p95_ms": nested(data, ["metrics", "/timing_tracker", "track_ms", "p95"]),
        "track_p99_ms": nested(data, ["metrics", "/timing_tracker", "track_ms", "p99"]),

        "e2e_target_p95_ms": nested(data, ["metrics", "/timing_target", "e2e_target_ms", "p95"]),
        "target_p95_ms": nested(data, ["metrics", "/timing_target", "target_ms", "p95"]),

        "det_per_msg_mean": nested(data, ["detection_stream", "detections_per_msg", "mean"]),
        "det_zero_ratio": nested(data, ["detection_stream", "detections_per_msg", "zero_ratio"]),
    }


def write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    if not rows:
        return

    keys = [
        "model",
        "tracker",
        "status",
        "json_path",
        "health_score",
        "detections_hz",
        "timing_hz",
        "tracker_hz",
        "target_hz",
        "e2e_det_p50_ms",
        "e2e_det_p95_ms",
        "e2e_det_p99_ms",
        "infer_p50_ms",
        "infer_p95_ms",
        "infer_p99_ms",
        "pre_p95_ms",
        "container_queue_p95_ms",
        "pub_dt_p95_ms",
        "track_p50_ms",
        "track_p95_ms",
        "track_p99_ms",
        "e2e_target_p95_ms",
        "target_p95_ms",
        "det_per_msg_mean",
        "det_zero_ratio",
        "notes",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in keys})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live model × tracker timing comparison matrix")
    parser.add_argument("--api-base", default="http://127.0.0.1:8090")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--warmup", type=float, default=8.0)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--trackers", nargs="*", default=DEFAULT_TRACKERS)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    root = Path(os.environ.get("THESIS_ROOT", ".")).resolve()
    os.chdir(root)

    run_stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else root / "reports" / "timing" / f"live_matrix_{run_stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    models = args.models if args.models else fetch_models(args.api_base)
    trackers = args.trackers

    print(f"root: {root}")
    print(f"out_dir: {out_dir}")
    print(f"models: {models}")
    print(f"trackers: {trackers}")
    print(f"duration per combo: {args.duration}s, warmup: {args.warmup}s")
    print(f"total combos: {len(models) * len(trackers)}")

    rows: list[dict[str, Any]] = []

    for model in models:
        for tracker in trackers:
            label = f"{slug(model)}__{slug(tracker)}"
            json_path = out_dir / f"{label}.json"
            log_path = out_dir / f"{label}.log"

            row: dict[str, Any] = {
                "model": model,
                "tracker": tracker,
                "json_path": str(json_path),
                "status": "pending",
                "notes": "",
            }

            if args.skip_existing and json_path.exists():
                row.update(summarise_json(json_path))
                row["status"] = "skipped_existing"
                rows.append(row)
                write_csv(rows, out_dir / "summary.csv")
                print(f"[skip] {label}")
                continue

            print(f"\n=== {label} ===")

            try:
                model_resp = post_model(args.api_base, model)
                if not model_resp.get("ok", False):
                    row["status"] = "model_switch_failed"
                    row["notes"] = json.dumps(model_resp)
                    rows.append(row)
                    write_csv(rows, out_dir / "summary.csv")
                    print(f"[fail] model switch: {model_resp}")
                    continue

                time.sleep(args.warmup)

                try:
                    tracker_resp = post_tracker(args.api_base, tracker)
                    if not tracker_resp.get("ok", False):
                        ok, param_msg = tracker_param_matches(tracker)
                        if not ok:
                            row["status"] = "tracker_switch_failed"
                            row["notes"] = f"api_response={json.dumps(tracker_resp)}; tracker_param={param_msg}"
                            rows.append(row)
                            write_csv(rows, out_dir / "summary.csv")
                            print(f"[fail] tracker switch: {row['notes']}")
                            continue
                except Exception as exc:
                    ok, param_msg = tracker_param_matches(tracker)
                    if not ok:
                        row["status"] = "api_error"
                        row["notes"] = f"{exc}; tracker_param={param_msg}"
                        rows.append(row)
                        write_csv(rows, out_dir / "summary.csv")
                        print(f"[fail] tracker API: {row['notes']}")
                        continue

                    print(f"[warn] tracker API returned error, but ROS param confirms tracker={tracker}: {exc}")

                time.sleep(args.warmup)

                cmd = [
                    sys.executable,
                    "tools/collect_live_timing_stats.py",
                    "--duration",
                    str(args.duration),
                    "--run-label",
                    label,
                    "--json-out",
                    str(json_path),
                ]

                rc = run_cmd(cmd, log_path)
                if rc != 0:
                    row["status"] = "collector_failed"
                    row["notes"] = f"collector rc={rc}; see {log_path}"
                else:
                    row["status"] = "ok"
                    row.update(summarise_json(json_path))

            except urllib.error.URLError as exc:
                row["status"] = "api_error"
                row["notes"] = str(exc)
            except Exception as exc:
                row["status"] = "error"
                row["notes"] = repr(exc)

            rows.append(row)
            write_csv(rows, out_dir / "summary.csv")
            print(f"[{row['status']}] {label}")

    write_csv(rows, out_dir / "summary.csv")
    print(f"\nsummary: {out_dir / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
