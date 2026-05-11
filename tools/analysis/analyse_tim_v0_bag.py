#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

import rclpy
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import rosbag2_py


STATE_ORDER = {
    "NO_TARGET": 0,
    "LOCKED": 1,
    "UNCERTAIN": 2,
    "LOST": 3,
    "REACQUIRED": 4,
}

MODE_ORDER = {
    "NO_CONTROL": 0,
    "NORMAL": 1,
    "YAW_ONLY": 2,
    "HOVER": 3,
    "CONFIRM": 4,
}


def safe_float(x: Any, default: float = math.nan) -> float:
    try:
        return float(x)
    except Exception:
        return default


def read_bag(bag_path: Path) -> dict[str, list[dict[str, Any]]]:
    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="")
    converter_options = rosbag2_py.ConverterOptions("", "")
    reader.open(storage_options, converter_options)

    topic_types = {
        topic_metadata.name: topic_metadata.type
        for topic_metadata in reader.get_all_topics_and_types()
    }
    msg_types = {
        topic: get_message(type_name)
        for topic, type_name in topic_types.items()
    }

    data: dict[str, list[dict[str, Any]]] = {
        "target": [],
        "target_memory": [],
        "target_memory_status": [],
    }

    first_t_ns: int | None = None

    while reader.has_next():
        topic, raw, t_ns = reader.read_next()
        if first_t_ns is None:
            first_t_ns = int(t_ns)
        t_s = (int(t_ns) - first_t_ns) / 1e9

        if topic not in msg_types:
            continue

        msg = deserialize_message(raw, msg_types[topic])

        if topic == "/target":
            data["target"].append({
                "t": t_s,
                "id": int(msg.id),
                "cx": float(msg.cx),
                "cy": float(msg.cy),
                "w": float(msg.w),
                "h": float(msg.h),
                "score": float(msg.score),
                "quality": float(msg.quality),
                "valid": int(msg.id) != 0 and float(msg.quality) > 0.0,
            })

        elif topic == "/target_memory":
            data["target_memory"].append({
                "t": t_s,
                "id": int(msg.id),
                "cx": float(msg.cx),
                "cy": float(msg.cy),
                "w": float(msg.w),
                "h": float(msg.h),
                "score": float(msg.score),
                "quality": float(msg.quality),
                "valid": int(msg.id) != 0 and float(msg.quality) > 0.0,
            })

        elif topic == "/target_memory/status":
            try:
                payload = json.loads(msg.data)
            except Exception:
                continue

            best = payload.get("best") or {}
            data["target_memory_status"].append({
                "t": t_s,
                "state": str(payload.get("state", "")),
                "control_mode": str(payload.get("control_mode", "")),
                "reason": str(payload.get("reason", "")),
                "target_track_id": payload.get("target_track_id", None),
                "visible": bool(payload.get("visible", False)),
                "reacquired": bool(payload.get("reacquired", False)),
                "quality": safe_float(payload.get("quality")),
                "lat_ms": safe_float(payload.get("lat_ms")),
                "frames_since_seen": int(payload.get("frames_since_seen", 0)),
                "num_tracks": int(payload.get("num_tracks", 0)),
                "appearance_enabled": bool(payload.get("appearance_enabled", False)),
                "appearance_candidates": int(payload.get("appearance_candidates", 0) or 0),
                "appearance_features_valid": int(payload.get("appearance_features_valid", 0) or 0),
                "appearance_image_age_ms": safe_float(payload.get("appearance_image_age_ms")),
                "appearance_skip_reason": str(payload.get("appearance_skip_reason", "")),
                "best_total": safe_float(best.get("total")),
                "best_iou": safe_float(best.get("iou")),
                "best_distance": safe_float(best.get("distance")),
                "best_scale": safe_float(best.get("scale")),
                "best_confidence": safe_float(best.get("confidence")),
                "best_track_id": best.get("track_id", None),
                "best_appearance": safe_float(best.get("appearance")),
                "best_appearance_used": bool(best.get("appearance_used", False)),
            })

    return data


def transitions(rows: list[dict[str, Any]], key: str) -> list[tuple[float, str, str]]:
    out = []
    prev = None
    for r in rows:
        cur = r.get(key, "")
        if prev is not None and cur != prev:
            out.append((float(r["t"]), str(prev), str(cur)))
        prev = cur
    return out


def percentile(xs: list[float], p: float) -> float:
    xs = sorted(x for x in xs if not math.isnan(x))
    if not xs:
        return math.nan
    k = (len(xs) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] * (c - k) + xs[c] * (k - f)


def _sample_durations(rows: list[dict[str, Any]]) -> list[float]:
    """Return per-row durations using next timestamp, with median dt for the final row."""
    if len(rows) < 2:
        return [0.0 for _ in rows]

    dts = [
        max(0.0, float(rows[i + 1]["t"]) - float(rows[i]["t"]))
        for i in range(len(rows) - 1)
    ]
    valid = sorted(dt for dt in dts if dt > 0.0)
    fallback = valid[len(valid) // 2] if valid else 0.0
    return dts + [fallback]


def total_duration(rows: list[dict[str, Any]]) -> float:
    return sum(_sample_durations(rows))


def valid_duration(rows: list[dict[str, Any]]) -> float:
    dts = _sample_durations(rows)
    return sum(dt for dt, row in zip(dts, rows) if bool(row.get("valid", False)))


def duration_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, float]:
    dts = _sample_durations(rows)
    out: dict[str, float] = {}
    for dt, row in zip(dts, rows):
        value = str(row.get(key, ""))
        out[value] = out.get(value, 0.0) + dt
    return out


def first_transition_duration(
    rows: list[dict[str, Any]],
    from_state: str,
    to_state: str,
) -> float:
    """Return first duration from entering from_state to entering to_state."""
    enter_t = None
    prev = None
    for row in rows:
        state = str(row.get("state", ""))
        t = float(row["t"])

        if state == from_state and prev != from_state:
            enter_t = t

        if enter_t is not None and state == to_state and prev != to_state:
            return max(0.0, t - enter_t)

        prev = state

    return math.nan


def append_duration_table(lines: list[str], durations: dict[str, float]) -> None:
    total = sum(durations.values())
    lines.append("| value | duration [s] | percentage |")
    lines.append("|---|---:|---:|")
    for key, value in sorted(durations.items(), key=lambda kv: kv[0]):
        pct = 100.0 * value / total if total > 0 else 0.0
        lines.append(f"| {key} | {value:.3f} | {pct:.1f}% |")


def save_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def plot_state_timeline(rows: list[dict[str, Any]], out: Path) -> None:
    if not rows:
        return
    t = [r["t"] for r in rows]
    y = [STATE_ORDER.get(r["state"], -1) for r in rows]

    plt.figure(figsize=(12, 4))
    plt.step(t, y, where="post")
    plt.yticks(list(STATE_ORDER.values()), list(STATE_ORDER.keys()))
    plt.xlabel("time [s]")
    plt.ylabel("TIM state")
    plt.title("TIM-V0 state timeline")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def plot_validity(raw: list[dict[str, Any]], tim: list[dict[str, Any]], out: Path) -> None:
    plt.figure(figsize=(12, 4))

    if raw:
        plt.step([r["t"] for r in raw], [1 if r["valid"] else 0 for r in raw], where="post", label="/target raw")
    if tim:
        plt.step([r["t"] for r in tim], [1 if r["valid"] else 0 for r in tim], where="post", label="/target_memory TIM")

    plt.yticks([0, 1], ["invalid", "valid"])
    plt.xlabel("time [s]")
    plt.ylabel("target validity")
    plt.title("Raw target vs TIM target validity")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def plot_quality(rows: list[dict[str, Any]], out: Path) -> None:
    if not rows:
        return
    plt.figure(figsize=(12, 4))
    plt.plot([r["t"] for r in rows], [r["quality"] for r in rows])
    plt.xlabel("time [s]")
    plt.ylabel("TIM quality")
    plt.title("TIM-V0 quality timeline")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def plot_latency(rows: list[dict[str, Any]], out: Path) -> None:
    vals = [r["lat_ms"] for r in rows if not math.isnan(r["lat_ms"])]
    if not vals:
        return
    plt.figure(figsize=(8, 4))
    plt.hist(vals, bins=40)
    plt.xlabel("TIM update latency [ms]")
    plt.ylabel("count")
    plt.title("TIM-V0 latency distribution")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def write_summary(
    path: Path,
    bag_path: Path,
    raw: list[dict[str, Any]],
    tim: list[dict[str, Any]],
    status: list[dict[str, Any]],
) -> None:
    state_counts = Counter(r["state"] for r in status)
    mode_counts = Counter(r["control_mode"] for r in status)
    state_transitions = transitions(status, "state")
    reacq_rows = [r for r in status if r["reacquired"] or r["state"] == "REACQUIRED"]
    lat = [r["lat_ms"] for r in status if not math.isnan(r["lat_ms"])]

    raw_valid = sum(1 for r in raw if r["valid"])
    tim_valid = sum(1 for r in tim if r["valid"])

    # Fair comparison window: start when TIM first leaves NO_TARGET.
    post_start_t = None
    for r in status:
        if r.get("state") != "NO_TARGET":
            post_start_t = float(r["t"])
            break

    raw_post = [r for r in raw if post_start_t is not None and float(r["t"]) >= post_start_t]
    tim_post = [r for r in tim if post_start_t is not None and float(r["t"]) >= post_start_t]
    raw_post_valid = sum(1 for r in raw_post if r["valid"])
    tim_post_valid = sum(1 for r in tim_post if r["valid"])

    state_durations = duration_by_key(status, "state")
    mode_durations = duration_by_key(status, "control_mode")

    raw_post_total_s = total_duration(raw_post)
    tim_post_total_s = total_duration(tim_post)
    raw_post_valid_s = valid_duration(raw_post)
    tim_post_valid_s = valid_duration(tim_post)

    uncertain_to_reacquired_s = first_transition_duration(status, "UNCERTAIN", "REACQUIRED")
    lost_to_reacquired_s = first_transition_duration(status, "LOST", "REACQUIRED")

    lines = []
    lines.append("# TIM-V0 Bag Analysis")
    lines.append("")
    lines.append(f"- Bag: `{bag_path}`")
    lines.append(f"- Raw `/target` samples: {len(raw)}")
    lines.append(f"- TIM `/target_memory` samples: {len(tim)}")
    lines.append(f"- TIM status samples: {len(status)}")
    lines.append("")
    lines.append("## Validity")
    lines.append("")
    lines.append(f"- Raw valid samples: {raw_valid}/{len(raw)}" if raw else "- Raw `/target`: not present in bag")
    lines.append(f"- TIM valid samples: {tim_valid}/{len(tim)}" if tim else "- TIM `/target_memory`: not present in bag")
    lines.append("")
    lines.append("## Post-selection validity")
    lines.append("")
    if post_start_t is None:
        lines.append("- TIM never left NO_TARGET, no fair post-selection window available.")
    else:
        lines.append(f"- Post-selection window starts at t={post_start_t:.2f}s")
        lines.append(f"- Raw valid samples after TIM selection: {raw_post_valid}/{len(raw_post)}" if raw_post else "- Raw post-selection samples: none")
        lines.append(f"- TIM valid samples after TIM selection: {tim_post_valid}/{len(tim_post)}" if tim_post else "- TIM post-selection samples: none")
        lines.append(f"- Raw valid duration after TIM selection: {raw_post_valid_s:.3f}/{raw_post_total_s:.3f} s" if raw_post else "- Raw post-selection duration: none")
        lines.append(f"- TIM valid duration after TIM selection: {tim_post_valid_s:.3f}/{tim_post_total_s:.3f} s" if tim_post else "- TIM post-selection duration: none")
    lines.append("")
    lines.append("## State counts")
    lines.append("")
    for k, v in state_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Control mode counts")
    lines.append("")
    for k, v in mode_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## State durations")
    lines.append("")
    append_duration_table(lines, state_durations)
    lines.append("")

    lines.append("## Control mode durations")
    lines.append("")
    append_duration_table(lines, mode_durations)
    lines.append("")

    lines.append("## Transition timing")
    lines.append("")
    if math.isnan(uncertain_to_reacquired_s):
        lines.append("- First UNCERTAIN -> REACQUIRED duration: n/a")
    else:
        lines.append(f"- First UNCERTAIN -> REACQUIRED duration: {uncertain_to_reacquired_s:.3f} s")
    if math.isnan(lost_to_reacquired_s):
        lines.append("- First LOST -> REACQUIRED duration: n/a")
    else:
        lines.append(f"- First LOST -> REACQUIRED duration: {lost_to_reacquired_s:.3f} s")
    lines.append("")
    lines.append("## Reacquisition")
    lines.append("")
    lines.append(f"- Reacquisition samples/events observed: {len(reacq_rows)}")
    for r in reacq_rows[:20]:
        lines.append(
            f"  - t={r['t']:.2f}s state={r['state']} "
            f"target_track_id={r['target_track_id']} q={r['quality']:.3f} reason={r['reason']}"
        )
    lines.append("")
    lines.append("## State transitions")
    lines.append("")
    for t, a, b in state_transitions:
        lines.append(f"- t={t:.2f}s: {a} -> {b}")
    lines.append("")
    lines.append("## TIM latency")
    lines.append("")
    lines.append(f"- mean: {sum(lat) / len(lat):.4f} ms" if lat else "- mean: n/a")
    lines.append(f"- p50: {percentile(lat, 50):.4f} ms" if lat else "- p50: n/a")
    lines.append(f"- p95: {percentile(lat, 95):.4f} ms" if lat else "- p95: n/a")
    lines.append(f"- p99: {percentile(lat, 99):.4f} ms" if lat else "- p99: n/a")
    lines.append(f"- max: {max(lat):.4f} ms" if lat else "- max: n/a")
    lines.append("")
    lines.append("## Interpretation template")
    lines.append("")
    lines.append(
        "TIM-V0 adds a selected-target memory layer above tracker outputs. "
        "In normal tracking it should match the raw selected target with negligible latency. "
        "During temporary loss it exposes UNCERTAIN/LOST states and conservative control modes. "
        "When the tracker reassigns the person to a new track ID, TIM can transition through "
        "REACQUIRED and continue publishing the selected target, while a raw ID-based selector may remain invalid."
    )

    path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--out-root", type=Path, default=Path("reports/tim_v0"))
    args = parser.parse_args()

    bag_path = args.bag.resolve()
    out_dir = args.out_root / bag_path.name
    out_dir.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    try:
        data = read_bag(bag_path)
    finally:
        if rclpy.ok():
            rclpy.shutdown()

    raw = data["target"]
    tim = data["target_memory"]
    status = data["target_memory_status"]

    save_csv(out_dir / "target_raw.csv", raw)
    save_csv(out_dir / "target_memory.csv", tim)
    save_csv(out_dir / "target_memory_status.csv", status)

    plot_state_timeline(status, out_dir / "tim_state_timeline.png")
    plot_validity(raw, tim, out_dir / "raw_vs_tim_validity.png")
    plot_quality(status, out_dir / "quality_timeline.png")
    plot_latency(status, out_dir / "latency_histogram.png")

    write_summary(out_dir / "summary.md", bag_path, raw, tim, status)

    print(f"[ok] wrote {out_dir}")
    print(f"[ok] summary: {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
