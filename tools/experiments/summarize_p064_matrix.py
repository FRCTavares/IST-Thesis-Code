#!/usr/bin/env python3
"""Summarize the frozen eight-cell source-resolution runtime qualification."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CELLS = {
    1: ("vga", "bytetrack", "mars", "p064_vga_tim_r1"),
    2: ("vga", "bytetrack", "off", "p064_vga_bytetrack_raw"),
    3: ("vga", "deepsort", "off", "p064_vga_deepsort_raw"),
    4: ("vga", "bytetrack", "mars", "p064_vga_tim_r2"),
    5: ("hd", "bytetrack", "mars", "p064_hd_tim_r1"),
    6: ("hd", "bytetrack", "off", "p064_hd_bytetrack_raw"),
    7: ("hd", "deepsort", "off", "p064_hd_deepsort_raw"),
    8: ("hd", "bytetrack", "mars", "p064_hd_tim_r2"),
}
STREAMS = ("/camera/fps", "/detections", "/tracks", "/target", "/timing", "/timing_tracker")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def finite(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * fraction
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def window_stats(stamps: list[int], start: int, end: int) -> dict[str, Any]:
    window = [stamp for stamp in stamps if start <= stamp <= end]
    gaps = [(b - a) / 1e9 for a, b in zip(window, window[1:])]
    return {
        "count": len(window),
        "first_boundary_gap_s": (window[0] - start) / 1e9 if window else None,
        "last_boundary_gap_s": (end - window[-1]) / 1e9 if window else None,
        "effective_rate_hz": len(window) / ((end - start) / 1e9),
        "gap_p50_s": percentile(gaps, .5),
        "gap_p95_s": percentile(gaps, .95),
        "gap_p99_s": percentile(gaps, .99),
        "gap_max_s": max(gaps) if gaps else None,
    }


def bag_samples(bag: Path) -> tuple[dict[str, list[int]], dict[str, list[tuple[int, Any]]]]:
    from rclpy.serialization import deserialize_message
    from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
    from rosidl_runtime_py.utilities import get_message
    reader = SequentialReader()
    reader.open(StorageOptions(uri=str(bag), storage_id="mcap"), ConverterOptions("", ""))
    types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    selected = set(STREAMS) | {"/target_memory_mars", "/timing_target", "/target_memory_mars/status"}
    classes = {topic: get_message(types[topic]) for topic in selected & types.keys()
               if topic in {"/timing", "/timing_tracker", "/timing_target", "/target_memory_mars/status"}}
    stamps: dict[str, list[int]] = {topic: [] for topic in selected}
    messages: dict[str, list[tuple[int, Any]]] = {topic: [] for topic in classes}
    while reader.has_next():
        topic, raw, ns = reader.read_next()
        if topic in selected:
            stamps[topic].append(int(ns))
        if topic in classes:
            messages[topic].append((int(ns), deserialize_message(raw, classes[topic])))
    return stamps, messages


def resource_window(run_dir: Path) -> tuple[int, int, dict[str, Any]]:
    folder = run_dir / "p032_resources"
    provenance = read_json(folder / "provenance.json")
    analysis = read_json(folder / "analysis.json")
    coverage = read_json(folder / "coverage.json")
    if not provenance or not analysis or not coverage:
        raise ValueError("resource provenance, analysis, or coverage missing")
    if provenance.get("duration_s") != 240 or provenance.get("warm_up_s") != 60:
        raise ValueError("resource sampler did not use 240 s / 60 s")
    measurement = analysis.get("measurement_window", {})
    start = measurement.get("analysis_start_monotonic_ns")
    end = measurement.get("analysis_end_monotonic_ns")
    if not isinstance(start, int) or not isinstance(end, int) or end - start < 240_000_000_000:
        raise ValueError("resource measurement interval incomplete")
    hardware = folder / "hardware/samples.jsonl"
    samples = [json.loads(line) for line in hardware.read_text().splitlines() if line.strip()]
    anchors = [sample for sample in samples if isinstance(sample.get("wall_time_ns"), int)
               and isinstance(sample.get("monotonic_ns"), int)]
    if not anchors:
        raise ValueError("resource wall/monotonic time anchor missing")
    anchor = min(anchors, key=lambda row: abs(row["monotonic_ns"] - start))
    offset = anchor["wall_time_ns"] - anchor["monotonic_ns"]
    return start + offset, end + offset, analysis


def camera_ros_faults(run_dir: Path, interval_end_ns: int | None) -> tuple[list[str], int]:
    signatures = ("i2c timeout", "stream on failed", "csi2_stop_channel",
                  "camera stalled", "traceback (most recent call last)",
                  "segmentation fault")
    faults: list[str] = []
    teardown_context_errors = 0
    for name in ("perception_camera.log", "tracker.log", "web_video.log",
                 "target_memory_mars.log"):
        path = run_dir / name
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        shutdown_at: int | None = None
        for index, line in enumerate(lines):
            match = re.fullmatch(
                r"\[shutdown\] managed application stop requested wall_ns=(\d+)",
                line,
            )
            if match and name == "perception_camera.log":
                shutdown_at = int(match.group(1))
            if not any(signature in line.lower() for signature in signatures):
                continue
            if (name == "perception_camera.log"
                    and "traceback (most recent call last)" in line.lower()
                    and shutdown_at is not None
                    and (interval_end_ns is None or shutdown_at > interval_end_ns)
                    and index > 0
                    and lines[index - 1] == "Exception in thread perception_camera_capture:"):
                trace = "\n".join(lines[index:index + 14])
                if ("_dashboard_pub.publish(msg)" in trace
                        and "rclpy._rclpy_pybind11.RCLError: Failed to publish: publisher's context is invalid"
                        in trace):
                    teardown_context_errors += 1
                    continue
            faults.append(f"{name}: {line[:200]}")
    return faults, teardown_context_errors


def summarize(cell: int, run_id: str, bag: Path, run_dir: Path,
              *, operator_target_id: int | None = None) -> dict[str, Any]:
    res, tracker, memory, tag = CELLS[cell]
    result: dict[str, Any] = {"schema": "p064_cell_result_v1", "cell": cell,
        "run_id": run_id, "tag": tag, "resolution": res, "tracker": tracker,
        "memory": memory, "control": "off", "bag_dir": str(bag), "run_dir": str(run_dir),
        "classification": "invalid", "reasons": [], "metrics": {}}
    reasons: list[str] = result["reasons"]
    collection = read_json(run_dir / "p064_collection_status.json")
    if (not collection or collection.get("formal") is not True
            or collection.get("cell") != cell or collection.get("run_id") != run_id
            or collection.get("tag") != tag
            or collection.get("launcher_ready") is not True
            or collection.get("launcher_finalized") is not True
            or collection.get("sampler_returncode") != 0
            or collection.get("analysis_returncodes") != {
                "per_topic": 0, "full_horizon_timing": 0, "transport": 0,
                "provenance": 0, "package": 0}):
        reasons.append("formal collection or post-run analysis did not complete")
    package = read_json(bag / "evidence_package_status.json")
    transport = read_json(bag / "recorder_transport_status.json")
    visual = read_json(bag / "visual_evidence_status.json")
    metadata = read_json(bag / "run_metadata.json")
    integrity = read_json(bag / "bag_integrity.json")
    result["recorder_transport_status"] = transport.get("quality_status") if transport else None
    result["provenance_status"] = (package or {}).get("provenance_validation", {}).get("passed")
    result["visual_status"] = visual.get("passed") if visual else None
    if not package or package.get("runtime_status") != "complete_runtime_evidence":
        reasons.append("runtime evidence package incomplete")
    if result["recorder_transport_status"] != "observed_zero":
        reasons.append("recorder transport not observed zero")
    if result["provenance_status"] is not True:
        reasons.append("provenance invalid or unavailable")
    if result["visual_status"] is not True:
        reasons.append("visual evidence invalid or unavailable")
    if not integrity or integrity.get("passed") is not True:
        reasons.append("structured bag integrity invalid or unavailable")
    assessment = read_json(bag / "per_topic_quality.json")
    if not assessment or assessment.get("checks_passed") is not True:
        reasons.append("per-topic assessment invalid or unavailable")
    elif (not isinstance(assessment.get("topics"), dict)
          or any(not isinstance(item, dict) or item.get("timestamp_monotonic") is not True
                 for item in assessment["topics"].values())):
        reasons.append("per-topic recorded timestamps are not monotonic")
    if not (bag / "timing_full_horizon.md").is_file() or not (bag / "timing_full_horizon.md").stat().st_size:
        reasons.append("full-horizon timing analysis missing")
    if not metadata or metadata.get("run_id") != run_id or metadata.get("scenario_tag") != tag:
        reasons.append("run ID or tag provenance mismatch")
    if metadata:
        bag_meta = metadata.get("bag") if isinstance(metadata.get("bag"), dict) else {}
        inventory = metadata.get("topic_qos_inventory") if isinstance(metadata.get("topic_qos_inventory"), dict) else {}
        topics = bag_meta.get("recorded_topics") if isinstance(bag_meta.get("recorded_topics"), list) else []
        for topic in topics:
            info = inventory.get(topic)
            count = info.get("publisher_count") if isinstance(info, dict) else None
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                reasons.append(f"{topic} had no trustworthy live publisher inventory")
        visual_meta = metadata.get("visual") if isinstance(metadata.get("visual"), dict) else {}
        if visual_meta.get("file") != str(bag / f"visual_{run_id}.mkv") or not visual_meta.get("started_at_utc"):
            reasons.append("visual file or start timestamp provenance mismatch")
        resolved = metadata.get("resolved_parameters") if isinstance(metadata.get("resolved_parameters"), dict) else {}
        params = resolved.get("perception_camera_node") if isinstance(resolved.get("perception_camera_node"), dict) else {}
        expected = (640, 480) if res == "vga" else (1280, 720)
        if (params.get("width"), params.get("height")) != tuple(map(str, expected)):
            reasons.append("source capture geometry mismatch")
        invocation = metadata.get("invocation") if isinstance(metadata.get("invocation"), dict) else {}
        command = invocation.get("command") if isinstance(invocation.get("command"), str) else ""
        if "--no-control" not in command or any(flag in command for flag in
                ("--control-mavros", "--field-record", "--record-raw")):
            reasons.append("no-control invocation contract mismatch")
    if memory == "mars":
        if (not isinstance(operator_target_id, int) or operator_target_id <= 0
                or not collection or collection.get("operator_target_id") != operator_target_id
                or not collection.get("physical_target_description")):
            reasons.append("human target selection and description not recorded")
        else:
            result["physical_target_description"] = collection["physical_target_description"]
    try:
        start, end, resources = resource_window(run_dir)
    except (OSError, ValueError, KeyError) as exc:
        reasons.append(str(exc))
        return result
    steady_start = start + 60_000_000_000
    if metadata and visual:
        from datetime import datetime
        try:
            visual_started = datetime.fromisoformat(
                metadata["visual"]["started_at_utc"].replace("Z", "+00:00")
            ).timestamp() * 1e9
            if visual_started > start or visual_started + (visual.get("duration_s", 0) + 5) * 1e9 < end:
                reasons.append("visual file does not cover the full resource interval")
        except (KeyError, TypeError, ValueError):
            reasons.append("visual interval cannot be established")
    required_groups = ["detector", "tracker"] + (["tim"] if memory == "mars" else [])
    provenance = read_json(run_dir / "p032_resources/provenance.json") or {}
    if memory == "mars":
        try:
            events = [json.loads(line) for line in (bag / "target_authority_events.jsonl").read_text().splitlines() if line.strip()]
        except (OSError, ValueError):
            events = []
        selections = [event for event in events if event.get("authority_state") == "selection_requested"
                      and isinstance(event.get("requested_target_id"), int)
                      and event["requested_target_id"] > 0]
        result["metrics"]["selected_target_ids"] = [event["requested_target_id"] for event in selections]
        mono_start = resources.get("measurement_window", {}).get("analysis_start_monotonic_ns")
        if (not selections or selections[0].get("requested_target_id") != operator_target_id
                or not isinstance(mono_start, int)
                or selections[0].get("monotonic_ns", mono_start + 1) > mono_start):
            reasons.append("target selection event missing, mismatched, or after sampler start")
        if len({event["requested_target_id"] for event in selections}) > 1:
            reasons.append("target ID changed during the cell; human review required")
    if provenance.get("architecture_groups") != required_groups:
        reasons.append("resource process groups mismatch")
    required_integrity = (
        "resource_records_have_known_sample_schema",
        "hardware_records_have_known_sample_schema",
        "architecture_has_complete_samples",
        "live_resource_roots_present_throughout_window",
        "steady_state_resource_samples_present",
        "steady_state_hardware_samples_present",
    )
    if (any(resources.get("integrity", {}).get(key) is not True for key in required_integrity)
            or resources.get("architecture_total", {}).get("missing_requested_groups")):
        reasons.append("resource integrity or process roots incomplete")
    hw = resources.get("hardware", {})
    cpu = resources.get("architecture_total", {}).get("cpu_percent", {}).get("steady_state", {}).get("mean")
    rss = resources.get("architecture_total", {}).get("rss_kib", {}).get("steady_state", {}).get("mean")
    temp = hw.get("temperature_c", {}).get("steady_state", {}).get("maximum")
    arm_frequency = hw.get("arm_frequency_hz", {}).get("steady_state", {}).get("mean")
    memory_min = hw.get("mem_available_kib", {}).get("steady_state", {}).get("minimum")
    memory_max = hw.get("mem_available_kib", {}).get("steady_state", {}).get("maximum")
    throttle = hw.get("throttling", {}).get("steady_state", {}).get("nonzero_count")
    result["metrics"].update(cpu_percent=cpu, rss_kib=rss, temperature_c_max=temp,
                             arm_frequency_hz_mean=arm_frequency,
                             throttling_nonzero_samples=throttle,
                             memory_available_kib_min=memory_min,
                             memory_available_kib_max=memory_max)
    if any(not finite(value) for value in (cpu, rss, temp, arm_frequency,
                                            memory_min, memory_max, throttle)):
        reasons.append("resource or thermal metric missing")
    if throttle:
        reasons.append("thermal throttling requires explanation before acceptance")
    if hw.get("samples_with_errors", {}).get("steady_state"):
        reasons.append("hardware health sampler reported errors")
    try:
        stamps, messages = bag_samples(bag)
    except Exception as exc:
        reasons.append(f"cannot read structured bag: {exc}")
        return result
    required_topics = list(STREAMS) + (["/target_memory_mars", "/timing_target", "/target_memory_mars/status"] if memory == "mars" else [])
    topic_stats = {topic: window_stats(stamps[topic], steady_start, end) for topic in required_topics}
    result["metrics"]["steady_topics"] = topic_stats
    for topic in required_topics:
        if topic_stats[topic]["count"] < 2 or topic_stats[topic]["gap_max_s"] is None:
            reasons.append(f"{topic} has no complete active interval")
        elif (topic_stats[topic]["first_boundary_gap_s"] >= .5
              or topic_stats[topic]["last_boundary_gap_s"] >= .5):
            reasons.append(f"{topic} does not span the full active interval")
    detector = topic_stats["/detections"]; tracks = topic_stats["/tracks"]
    result["metrics"].update(detector_effective_rate_hz=detector["effective_rate_hz"],
        tracker_effective_rate_hz=tracks["effective_rate_hz"],
        maximum_relevant_publication_gap_s=max((topic_stats[t]["gap_max_s"] or 0) for t in required_topics))
    timing_fields = {"/timing": "e2e_det_ms", "/timing_tracker": "track_ms"}
    if memory == "mars":
        timing_fields["/timing_target"] = "e2e_validated_target_ms"
    for topic, field in timing_fields.items():
        values = [float(getattr(msg, field)) for ns, msg in messages.get(topic, [])
                  if steady_start <= ns <= end and hasattr(msg, field)]
        value = percentile(values, .95)
        result["metrics"][f"{field}_p95"] = value
        if not finite(value):
            reasons.append(f"{field} p95 missing")
    if memory == "mars":
        try:
            status = [(ns, json.loads(msg.data)) for ns, msg in messages.get("/target_memory_mars/status", [])
                      if steady_start <= ns <= end]
            if any(not isinstance(row, dict) for _, row in status):
                raise ValueError("status payload is not an object")
        except (AttributeError, TypeError, ValueError) as exc:
            reasons.append(f"TIM status evidence cannot be parsed: {exc}")
            return result
        try:
            eligible = [row for _, row in status if row.get("appearance_candidates", 0) > 0
                        and finite(row.get("appearance_image_age_ms"))]
            stale = sum(row.get("appearance_skip_reason") == "stale_image" for row in eligible)
        except (TypeError, ValueError) as exc:
            reasons.append(f"TIM appearance status fields invalid: {exc}")
            return result
        result["metrics"].update(validated_target_effective_rate_hz=topic_stats["/target_memory_mars"]["effective_rate_hz"],
            status_sample_count=len(status),
            tim_mars_processing_ms_p95=percentile([float(row["tim_mars_processing_ms"])
                for _, row in status if finite(row.get("tim_mars_processing_ms"))], .95),
            stale_appearance_image_skips=stale, eligible_appearance_attempts=len(eligible),
            stale_appearance_fraction=stale / len(eligible) if eligible else None,
            appearance_image_age_ms_p50=percentile([row["appearance_image_age_ms"] for row in eligible], .5),
            appearance_image_age_ms_p95=percentile([row["appearance_image_age_ms"] for row in eligible], .95),
            appearance_image_age_ms_p99=percentile([row["appearance_image_age_ms"] for row in eligible], .99),
            backend_calls=sum(int(row.get("appearance_backend_calls", 0)) for _, row in status),
            valid_embeddings=sum(int(row.get("appearance_backend_valid", 0)) for _, row in status))
        if not eligible:
            reasons.append("eligible appearance attempts missing")
    faults, teardown_context_errors = camera_ros_faults(run_dir, end)
    result["metrics"]["camera_ros_fault_signatures"] = faults
    result["metrics"]["camera_teardown_context_errors"] = teardown_context_errors
    if faults:
        reasons.append("camera or ROS fault signature requires review")
    if reasons:
        return result
    gate_reasons: list[str] = []
    if cell >= 5:
        if detector["effective_rate_hz"] < 15: gate_reasons.append("detector rate below 15 Hz")
        if tracks["effective_rate_hz"] < 15: gate_reasons.append("tracker rate below 15 Hz")
        if result["metrics"]["maximum_relevant_publication_gap_s"] >= .5:
            gate_reasons.append("steady publication gap at least 0.5 s")
        if memory == "mars":
            if result["metrics"]["validated_target_effective_rate_hz"] < 15:
                gate_reasons.append("validated-target rate below 15 Hz")
            if result["metrics"]["e2e_validated_target_ms_p95"] > 200:
                gate_reasons.append("validated-target p95 above 200 ms")
            if result["metrics"]["stale_appearance_fraction"] > .1:
                gate_reasons.append("stale appearance fraction above 10 percent")
    result["reasons"] = gate_reasons
    result["classification"] = "fail" if gate_reasons else "pass"
    return result


def matrix(root: Path) -> dict[str, Any]:
    cells = []
    for cell, (_, _, _, tag) in CELLS.items():
        matches = sorted((root / "bags/live_camera").glob(f"*__video__{tag}/p064_cell_result.json"))
        matches += sorted((root / "ros2_ws/log/live_stack").glob("*/p064_cell_result.json"))
        candidates = [item for path in matches if (item := read_json(path)) and item.get("cell") == cell]
        valid = [item for item in candidates if item.get("classification") in ("pass", "fail")]
        cells.append(valid[-1] if valid else candidates[-1] if candidates else
                     {"cell": cell, "classification": "missing", "run_id": None})
    for index in range(4, 8):
        hd, vga = cells[index], cells[index - 4]
        hd_metrics, vga_metrics = hd.get("metrics", {}), vga.get("metrics", {})
        increases = {}
        for name in ("cpu_percent", "rss_kib"):
            h, v = hd_metrics.get(name), vga_metrics.get(name)
            increases[name] = h - v if finite(h) and finite(v) else None
        hd["matched_vga_cell"] = index - 3
        hd["resource_increase_vs_vga"] = increases
    complete = all(item["classification"] in ("pass", "fail") for item in cells)
    hd_pass = complete and all(item["classification"] == "pass" for item in cells[4:])
    return {"schema": "p064_matrix_summary_v1", "cells": cells, "matrix_complete": complete,
            "hd_runtime_qualified": hd_pass if complete else None,
            "decision": ("retain_vga_runtime_failure" if complete and not hd_pass else
                         "small_distant_identity_comparison_required" if hd_pass else "pending_matrix")}


def render_matrix(data: dict[str, Any]) -> str:
    columns = ("cell", "run_id", "resolution", "tracker", "memory", "recorder_transport_status",
               "provenance_status", "visual_status", "detector_effective_rate_hz",
               "tracker_effective_rate_hz", "maximum_relevant_publication_gap_s",
               "validated_target_effective_rate_hz", "e2e_validated_target_ms_p95",
               "stale_appearance_image_skips", "eligible_appearance_attempts",
               "cpu_percent", "rss_kib", "temperature_c_max", "throttling_nonzero_samples",
               "classification", "reasons")
    def value(item: dict[str, Any], name: str) -> str:
        raw = item.get(name, item.get("metrics", {}).get(name))
        if name == "reasons": raw = "; ".join(raw or [])
        if raw is None: return "—"
        if isinstance(raw, float): return f"{raw:.3f}"
        return str(raw).replace("|", "/")
    lines = ["# Issue #64 runtime matrix", "", f"Decision state: `{data['decision']}`", "",
             "| " + " | ".join(columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    for cell in data["cells"]:
        lines.append("| " + " | ".join(value(cell, name) for name in columns) + " |")
    lines += ["", "Matched HD minus VGA resource values (CPU percentage points, RSS KiB):", "",
              "| HD cell | VGA cell | CPU | RSS |", "| --- | --- | ---: | ---: |"]
    for cell in data["cells"][4:]:
        increase = cell.get("resource_increase_vs_vga", {})
        lines.append(f"| {cell['cell']} | {cell['matched_vga_cell']} | "
                     f"{value({'metrics': increase}, 'cpu_percent')} | "
                     f"{value({'metrics': increase}, 'rss_kib')} |")
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", type=int, choices=CELLS)
    parser.add_argument("--run-id")
    parser.add_argument("--operator-target-id", type=int)
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    if args.matrix:
        output = matrix(ROOT)
        dest = ROOT / "reports/p064_matrix_summary.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
    else:
        if args.cell is None or not args.run_id:
            parser.error("--cell and --run-id are required for a cell summary")
        tag = CELLS[args.cell][3]
        bag = ROOT / "bags/live_camera" / f"{args.run_id}__video__{tag}"
        run_dir = ROOT / "ros2_ws/log/live_stack" / args.run_id
        output = summarize(args.cell, args.run_id, bag, run_dir,
                           operator_target_id=args.operator_target_id)
        dest = (bag if bag.is_dir() else run_dir) / "p064_cell_result.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    if args.matrix:
        (ROOT / "reports/p064_matrix_summary.md").write_text(render_matrix(output))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if args.matrix or output["classification"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
