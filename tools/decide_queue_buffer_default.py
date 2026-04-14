#!/usr/bin/env python3
"""Decide queue-buffer default from two live timing JSON reports.

This script compares queue-buffer=1 and queue-buffer=2 runs, enforces
workload-comparability gates, and emits a recommendation for the default.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


EPS = 1e-9


@dataclass
class RunMetrics:
    queue_buffers: int
    path: str
    run_label: str
    timing_hz: float
    e2e_det_p95: float
    pub_dt_p95: float
    pub_dt_p99: float
    det_per_msg_mean: Optional[float]
    det_zero_ratio: Optional[float]


@dataclass
class GateResult:
    name: str
    passed: bool
    details: str


def _load_json(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"root JSON is not an object: {path}")
    return payload


def _as_float(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(out):
        raise ValueError(f"{label} is not finite: {out}")
    return out


def _dict_get(d: Dict[str, object], key: str, label: str) -> object:
    if key not in d:
        raise ValueError(f"missing key {label}")
    return d[key]


def _extract_optional_detection_stats(payload: Dict[str, object]) -> Tuple[Optional[float], Optional[float]]:
    dstream = payload.get("detection_stream")
    if not isinstance(dstream, dict):
        return None, None

    dpm = dstream.get("detections_per_msg")
    if not isinstance(dpm, dict):
        return None, None

    mean = dpm.get("mean")
    zero_ratio = dpm.get("zero_ratio")
    if mean is None or zero_ratio is None:
        return None, None

    mean_f = _as_float(mean, "detection_stream.detections_per_msg.mean")
    zr_f = _as_float(zero_ratio, "detection_stream.detections_per_msg.zero_ratio")
    return mean_f, zr_f


def _extract_run_metrics(path: str, queue_buffers: int) -> RunMetrics:
    payload = _load_json(path)

    run_label_obj = payload.get("run_label", os.path.basename(path))
    run_label = str(run_label_obj)

    topics = _dict_get(payload, "topics", "topics")
    if not isinstance(topics, dict):
        raise ValueError("topics is not an object")

    timing_topic = _dict_get(topics, "/timing", "topics['/timing']")
    if not isinstance(timing_topic, dict):
        raise ValueError("topics['/timing'] is not an object")
    timing_hz = _as_float(_dict_get(timing_topic, "hz", "topics['/timing']['hz']"), "topics['/timing']['hz']")

    metrics = _dict_get(payload, "metrics", "metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metrics is not an object")

    timing_metrics = _dict_get(metrics, "/timing", "metrics['/timing']")
    if not isinstance(timing_metrics, dict):
        raise ValueError("metrics['/timing'] is not an object")

    e2e_det = _dict_get(timing_metrics, "e2e_det_ms", "metrics['/timing']['e2e_det_ms']")
    pub_dt = _dict_get(timing_metrics, "pub_dt_ms", "metrics['/timing']['pub_dt_ms']")
    if not isinstance(e2e_det, dict) or not isinstance(pub_dt, dict):
        raise ValueError("metrics['/timing'] entries are malformed")

    e2e_det_p95 = _as_float(_dict_get(e2e_det, "p95", "metrics['/timing']['e2e_det_ms']['p95']"), "metrics['/timing']['e2e_det_ms']['p95']")
    pub_dt_p95 = _as_float(_dict_get(pub_dt, "p95", "metrics['/timing']['pub_dt_ms']['p95']"), "metrics['/timing']['pub_dt_ms']['p95']")
    pub_dt_p99 = _as_float(_dict_get(pub_dt, "p99", "metrics['/timing']['pub_dt_ms']['p99']"), "metrics['/timing']['pub_dt_ms']['p99']")

    dpm_mean, zero_ratio = _extract_optional_detection_stats(payload)

    return RunMetrics(
        queue_buffers=queue_buffers,
        path=path,
        run_label=run_label,
        timing_hz=timing_hz,
        e2e_det_p95=e2e_det_p95,
        pub_dt_p95=pub_dt_p95,
        pub_dt_p99=pub_dt_p99,
        det_per_msg_mean=dpm_mean,
        det_zero_ratio=zero_ratio,
    )


def _fmt(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if not math.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def _relative_abs_delta(a: float, b: float) -> float:
    denom = max(abs(a), EPS)
    return abs(b - a) / denom


def _gate_min_hz(q1: RunMetrics, q2: RunMetrics, min_hz: float) -> GateResult:
    passed = (q1.timing_hz >= min_hz) and (q2.timing_hz >= min_hz)
    details = (
        f"q1={q1.timing_hz:.3f} Hz, q2={q2.timing_hz:.3f} Hz, "
        f"required >= {min_hz:.3f} Hz"
    )
    return GateResult(name="min_timing_hz", passed=passed, details=details)


def _gate_detection_load(
    baseline: RunMetrics,
    candidate: RunMetrics,
    mean_tol: float,
    zero_delta_max: float,
    allow_missing: bool,
) -> GateResult:
    if baseline.det_per_msg_mean is None or baseline.det_zero_ratio is None:
        msg = "baseline detection_stream stats missing"
        return GateResult(name="detection_load_comparability", passed=allow_missing, details=msg)
    if candidate.det_per_msg_mean is None or candidate.det_zero_ratio is None:
        msg = "candidate detection_stream stats missing"
        return GateResult(name="detection_load_comparability", passed=allow_missing, details=msg)

    mean_delta = _relative_abs_delta(baseline.det_per_msg_mean, candidate.det_per_msg_mean)
    zero_delta = abs(candidate.det_zero_ratio - baseline.det_zero_ratio)
    passed = (mean_delta <= mean_tol) and (zero_delta <= zero_delta_max)

    details = (
        f"mean_delta={mean_delta:.4f} (max {mean_tol:.4f}), "
        f"zero_ratio_delta={zero_delta:.4f} (max {zero_delta_max:.4f})"
    )
    return GateResult(name="detection_load_comparability", passed=passed, details=details)


def _winner_label(q1: RunMetrics, q2: RunMetrics, baseline_queue: int) -> Tuple[int, Dict[str, int], List[str]]:
    score = {1: 0, 2: 0}
    reasons: List[str] = []

    metrics = [
        ("/timing hz", q1.timing_hz, q2.timing_hz, "higher", 4),
        ("pub_dt_ms p95", q1.pub_dt_p95, q2.pub_dt_p95, "lower", 3),
        ("pub_dt_ms p99", q1.pub_dt_p99, q2.pub_dt_p99, "lower", 2),
        ("e2e_det_ms p95", q1.e2e_det_p95, q2.e2e_det_p95, "lower", 1),
    ]

    for name, v1, v2, direction, weight in metrics:
        if direction == "higher":
            if v1 > v2 + EPS:
                score[1] += weight
                reasons.append(f"q1 better {name} ({v1:.3f} vs {v2:.3f})")
            elif v2 > v1 + EPS:
                score[2] += weight
                reasons.append(f"q2 better {name} ({v2:.3f} vs {v1:.3f})")
        else:
            if v1 + EPS < v2:
                score[1] += weight
                reasons.append(f"q1 better {name} ({v1:.3f} vs {v2:.3f})")
            elif v2 + EPS < v1:
                score[2] += weight
                reasons.append(f"q2 better {name} ({v2:.3f} vs {v1:.3f})")

    if score[1] > score[2]:
        return 1, score, reasons
    if score[2] > score[1]:
        return 2, score, reasons
    return baseline_queue, score, reasons


def _print_run_summary(q1: RunMetrics, q2: RunMetrics, baseline_queue: int) -> None:
    print("\n=== Queue-buffer runs ===")
    print(f"q1 json: {q1.path}")
    print(f"q2 json: {q2.path}")
    print(f"baseline queue: {baseline_queue}")
    print()
    print(f"q1 label: {q1.run_label}")
    print(f"q2 label: {q2.run_label}")

    print("\nmetric                     q1            q2")
    print(f"/timing hz                 {_fmt(q1.timing_hz)}        {_fmt(q2.timing_hz)}")
    print(f"e2e_det_ms p95            {_fmt(q1.e2e_det_p95)}      {_fmt(q2.e2e_det_p95)}")
    print(f"pub_dt_ms p95             {_fmt(q1.pub_dt_p95)}      {_fmt(q2.pub_dt_p95)}")
    print(f"pub_dt_ms p99             {_fmt(q1.pub_dt_p99)}      {_fmt(q2.pub_dt_p99)}")
    print(f"detections_per_msg mean   {_fmt(q1.det_per_msg_mean)}       {_fmt(q2.det_per_msg_mean)}")
    print(f"detections zero_ratio     {_fmt(q1.det_zero_ratio)}       {_fmt(q2.det_zero_ratio)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Compare queue-buffer=1 vs queue-buffer=2 timing reports and "
            "recommend default setting with workload-comparability gates."
        )
    )
    p.add_argument("--q1-json", required=True, help="JSON report from --perception-hailo-queue-buffers 1")
    p.add_argument("--q2-json", required=True, help="JSON report from --perception-hailo-queue-buffers 2")
    p.add_argument("--baseline-queue", type=int, choices=[1, 2], default=2, help="Baseline queue setting for comparability reference and tie-break (default: 2)")
    p.add_argument("--min-timing-hz", type=float, default=9.0, help="Required minimum /timing mean Hz for both runs")
    p.add_argument("--dpm-mean-tolerance", type=float, default=0.10, help="Max relative delta for detections_per_msg.mean")
    p.add_argument("--zero-ratio-delta-max", type=float, default=0.05, help="Max absolute delta for detections_per_msg.zero_ratio")
    p.add_argument("--allow-missing-detection-load", action="store_true", help="Allow decision even if detection_stream stats are missing")
    p.add_argument(
        "--exit-zero-on-gate-fail",
        action="store_true",
        help="Return exit code 0 even when one or more gates fail (decision remains null).",
    )
    p.add_argument("--json-out", default="", help="Optional path to write decision JSON")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        q1 = _extract_run_metrics(args.q1_json, queue_buffers=1)
        q2 = _extract_run_metrics(args.q2_json, queue_buffers=2)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_run_summary(q1, q2, baseline_queue=args.baseline_queue)

    baseline = q1 if args.baseline_queue == 1 else q2
    candidate = q2 if args.baseline_queue == 1 else q1

    gates = [
        _gate_min_hz(q1=q1, q2=q2, min_hz=args.min_timing_hz),
        _gate_detection_load(
            baseline=baseline,
            candidate=candidate,
            mean_tol=args.dpm_mean_tolerance,
            zero_delta_max=args.zero_ratio_delta_max,
            allow_missing=args.allow_missing_detection_load,
        ),
    ]

    print("\n=== Gates ===")
    all_pass = True
    for g in gates:
        state = "PASS" if g.passed else "FAIL"
        print(f"[{state}] {g.name}: {g.details}")
        all_pass = all_pass and g.passed

    selected_queue = None
    score: Dict[str, int] = {}
    reasons: List[str] = []

    if all_pass:
        winner, score_raw, reasons = _winner_label(q1=q1, q2=q2, baseline_queue=args.baseline_queue)
        selected_queue = winner
        score = {"q1": score_raw[1], "q2": score_raw[2]}
        print("\n=== Decision ===")
        print(f"Selected default: --perception-hailo-queue-buffers {winner}")
        print(f"Score: q1={score_raw[1]} q2={score_raw[2]}")
        if reasons:
            for reason in reasons:
                print(f"- {reason}")
        else:
            print("- Scores tied on decision metrics; selected baseline queue as tie-break.")
    else:
        print("\n=== Decision ===")
        print("No default selected because one or more gates failed.")

    if args.json_out:
        out = {
            "q1": asdict(q1),
            "q2": asdict(q2),
            "baseline_queue": int(args.baseline_queue),
            "gates": [asdict(g) for g in gates],
            "all_gates_pass": bool(all_pass),
            "selected_queue": selected_queue,
            "score": score,
            "decision_reasons": reasons,
            "exit_zero_on_gate_fail": bool(args.exit_zero_on_gate_fail),
        }
        out_dir = os.path.dirname(args.json_out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"json_out: {args.json_out}")

    if all_pass:
        return 0
    if args.exit_zero_on_gate_fail:
        print("Gate failure reported, but returning 0 due to --exit-zero-on-gate-fail")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
