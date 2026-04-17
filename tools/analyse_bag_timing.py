#!/usr/bin/env python3
"""
Offline bag timing analysis for thesis ROS 2 slice.

Reads a rosbag2 directory (MCAP expected) and:
- Defines base window as [first /timing msg, last /timing msg] using bag timestamps.
- Computes stats for canonical /timing fields:
    mean, p50, p95, p99, min, max for:
        pre_ms, container_queue_ms, zmq_roundtrip_ms, infer_ms, e2e_det_ms, pub_dt_ms
    where legacy alias fallback is compatibility-only and deprecated:
        e2e_det_ms <- lat_ms, zmq_roundtrip_ms <- recv_ms
- Computes achieved Hz for topics using counts within the base window.
- Computes "active-only" window by excluding restart gaps using pub_dt_ms threshold:
    keep samples with pub_dt_ms <= gap-ms
  and computes:
    - active-only per-field stats (/timing)
    - active-only Hz per topic by counting messages inside the union of active segments
- If /timing_tracker exists:
    - reads track_ms samples inside active segments
    - reports stats + active-only Hz for /timing_tracker
- Saves figures under --figdir:
    e2e_det_ms_hist.png + e2e_det_ms_cdf.png
    pub_dt_ms_hist.png + pub_dt_ms_cdf.png
  Optional:
    pub_dt_ms_timeseries.png (enabled with --plot-timeseries)
    track_ms_hist.png + track_ms_cdf.png (if /timing_tracker present)
- Writes a markdown report to --out

Constraints: no new installs. Uses rosbag2_py + rclpy if available.
"""

import argparse
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from timing_contract import METRICS_SCHEMA_VERSION, METRIC_WARN_THRESHOLDS, METRIC_WINDOWS, candidates_for


def _percentile(sorted_vals: List[float], q: float) -> float:
    """Nearest-rank percentile with linear interpolation. q in [0, 100]."""
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return sorted_vals[0]
    if q >= 100:
        return sorted_vals[-1]
    n = len(sorted_vals)
    pos = (q / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    w = pos - lo
    return sorted_vals[lo] * (1.0 - w) + sorted_vals[hi] * w


@dataclass
class FieldStats:
    mean: float
    p50: float
    p95: float
    p99: float
    vmin: float
    vmax: float
    n: int


def _compute_stats(vals: List[float]) -> FieldStats:
    if not vals:
        nan = float("nan")
        return FieldStats(nan, nan, nan, nan, nan, nan, 0)
    s = sorted(vals)
    mean = sum(s) / len(s)
    return FieldStats(
        mean=mean,
        p50=_percentile(s, 50.0),
        p95=_percentile(s, 95.0),
        p99=_percentile(s, 99.0),
        vmin=s[0],
        vmax=s[-1],
        n=len(s),
    )


def _fmt(x: float) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "NA"
    return f"{x:.3f}"


def _try_import_ros() -> bool:
    try:
        import rclpy  # noqa: F401
        from rclpy.serialization import deserialize_message  # noqa: F401
        from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions  # noqa: F401
        return True
    except Exception:
        return False


def _filter_by_indices(vals: List[float], idx: List[int]) -> List[float]:
    return [vals[i] for i in idx]


def _read_bag_timing_and_counts(
    bag_dir: str,
    timing_topic: str = "/timing",
    topics_for_hz: Optional[List[str]] = None,
) -> Tuple[
    Dict[str, List[float]],            # timing_fields -> list of values
    List[int],                         # timing timestamps (ns) aligned to timing samples
    int, int,                          # base window start/end (ns)
    Dict[str, int],                    # counts in base window for topics_for_hz
    Dict[str, str],                    # topic -> type map
]:
    if topics_for_hz is None:
        topics_for_hz = ["/detections", "/timing", "/tracks", "/target"]

    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = SequentialReader()
    storage_options = StorageOptions(uri=bag_dir, storage_id="")
    converter_options = ConverterOptions(input_serialization_format="", output_serialization_format="")
    reader.open(storage_options, converter_options)

    topics_and_types = reader.get_all_topics_and_types()
    type_map = {t.name: t.type for t in topics_and_types}

    if timing_topic not in type_map:
        raise RuntimeError(f"Bag has no {timing_topic} topic. Available: {sorted(type_map.keys())}")

    timing_msg_type = get_message(type_map[timing_topic])

    field_candidates: Dict[str, List[str]] = {
        "pre_ms": candidates_for("pre_ms"),
        "container_queue_ms": candidates_for("container_queue_ms"),
        "zmq_roundtrip_ms": candidates_for("zmq_roundtrip_ms"),
        "infer_ms": candidates_for("infer_ms"),
        "e2e_det_ms": candidates_for("e2e_det_ms"),
        "pub_dt_ms": candidates_for("pub_dt_ms"),
    }
    timing_vals: Dict[str, List[float]] = {k: [] for k in field_candidates}
    timing_ts_ns: List[int] = []

    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        if topic != timing_topic:
            continue
        msg = deserialize_message(data, timing_msg_type)

        for out_key, candidates in field_candidates.items():
            value = None
            for in_key in candidates:
                if hasattr(msg, in_key):
                    value = float(getattr(msg, in_key))
                    break
            if value is None:
                raise RuntimeError(
                    f"{timing_topic} message type missing fields for '{out_key}': {candidates}."
                )
            timing_vals[out_key].append(value)

        timing_ts_ns.append(int(t_ns))

    if not timing_ts_ns:
        raise RuntimeError(f"No messages found on {timing_topic}.")

    base_start = timing_ts_ns[0]
    base_end = timing_ts_ns[-1]

    # Pass 2: count messages in base window
    reader2 = SequentialReader()
    reader2.open(storage_options, converter_options)

    counts: Dict[str, int] = {t: 0 for t in topics_for_hz}
    while reader2.has_next():
        topic, _data, t_ns = reader2.read_next()
        if topic not in counts:
            continue
        if base_start <= int(t_ns) <= base_end:
            counts[topic] += 1

    return timing_vals, timing_ts_ns, base_start, base_end, counts, type_map


def _save_plots(
    figdir: str,
    timing_vals: Dict[str, List[float]],
    timing_ts_ns: List[int],
    plot_timeseries: bool,
):
    import matplotlib.pyplot as plt

    os.makedirs(figdir, exist_ok=True)

    def save_hist_and_cdf(values: List[float], base: str, xlabel: str):
        plt.figure()
        plt.hist(values, bins=60)
        plt.xlabel(xlabel)
        plt.ylabel("Count")
        plt.tight_layout()
        plt.savefig(os.path.join(figdir, f"{base}_hist.png"), dpi=200)
        plt.close()

        s = sorted(values)
        n = len(s)
        y = [(i + 1) / n for i in range(n)]
        plt.figure()
        plt.plot(s, y)
        plt.xlabel(xlabel)
        plt.ylabel("CDF")
        plt.ylim(0.0, 1.0)
        plt.tight_layout()
        plt.savefig(os.path.join(figdir, f"{base}_cdf.png"), dpi=200)
        plt.close()

    if timing_vals.get("e2e_det_ms"):
        save_hist_and_cdf(timing_vals["e2e_det_ms"], "e2e_det_ms", "e2e_det_ms (ms)")

    if timing_vals.get("pub_dt_ms"):
        save_hist_and_cdf(timing_vals["pub_dt_ms"], "pub_dt_ms", "pub_dt_ms (ms)")

    if plot_timeseries and timing_vals.get("pub_dt_ms") and timing_ts_ns:
        t0 = timing_ts_ns[0]
        xs = [(t - t0) * 1e-9 for t in timing_ts_ns]
        ys = timing_vals["pub_dt_ms"]
        plt.figure()
        plt.plot(xs, ys)
        plt.xlabel("t from first /timing (s)")
        plt.ylabel("pub_dt_ms (ms)")
        plt.tight_layout()
        plt.savefig(os.path.join(figdir, "pub_dt_ms_timeseries.png"), dpi=200)
        plt.close()

    # Optional tracker runtime plots (if injected)
    if timing_vals.get("track_ms_tracker"):
        save_hist_and_cdf(timing_vals["track_ms_tracker"], "track_ms", "track_ms (ms)")


def _count_topics_in_segments(
    bag_dir: str,
    segments_ns: List[Tuple[int, int]],
    topics: List[str],
    storage_id: str = "",
) -> Dict[str, int]:
    """Count messages inside union of segments."""
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions

    counts = {t: 0 for t in topics}
    if not segments_ns:
        return counts

    reader = SequentialReader()
    storage_options = StorageOptions(uri=bag_dir, storage_id=storage_id)
    converter_options = ConverterOptions(input_serialization_format="", output_serialization_format="")
    reader.open(storage_options, converter_options)

    seg_i = 0
    seg_start, seg_end = segments_ns[seg_i]

    while reader.has_next() and seg_i < len(segments_ns):
        topic, _data, t_ns = reader.read_next()
        if topic not in counts:
            continue

        t_ns = int(t_ns)

        while seg_i < len(segments_ns) and t_ns > seg_end:
            seg_i += 1
            if seg_i < len(segments_ns):
                seg_start, seg_end = segments_ns[seg_i]

        if seg_i >= len(segments_ns):
            break

        if seg_start <= t_ns <= seg_end:
            counts[topic] += 1

    return counts


def _read_metric_in_segments(
    bag_dir: str,
    topic_name: str,
    field_name: str,
    segments_ns: List[Tuple[int, int]],
    type_map: Dict[str, str],
    storage_id: str = "",
) -> Tuple[List[float], List[int]]:
    """Read one numeric field from topic_name inside union of segments."""
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    if not segments_ns:
        return [], []
    if topic_name not in type_map:
        return [], []

    msg_type = get_message(type_map[topic_name])

    reader = SequentialReader()
    storage_options = StorageOptions(uri=bag_dir, storage_id=storage_id)
    converter_options = ConverterOptions(input_serialization_format="", output_serialization_format="")
    reader.open(storage_options, converter_options)

    seg_i = 0
    seg_start, seg_end = segments_ns[seg_i]

    vals: List[float] = []
    ts: List[int] = []

    while reader.has_next() and seg_i < len(segments_ns):
        topic, data, t_ns = reader.read_next()
        if topic != topic_name:
            continue

        t_ns = int(t_ns)

        while seg_i < len(segments_ns) and t_ns > seg_end:
            seg_i += 1
            if seg_i < len(segments_ns):
                seg_start, seg_end = segments_ns[seg_i]

        if seg_i >= len(segments_ns):
            break

        if seg_start <= t_ns <= seg_end:
            m = deserialize_message(data, msg_type)
            if hasattr(m, field_name):
                vals.append(float(getattr(m, field_name)))
                ts.append(t_ns)

    return vals, ts


def _write_markdown(
    out_path: str,
    bag_dir: str,
    base_start_ns: int,
    base_end_ns: int,
    timing_stats: Dict[str, FieldStats],
    hz_counts: Dict[str, int],
    figures_written: List[str],
    timing_stats_active: Optional[Dict[str, FieldStats]] = None,
    active_start_ns: Optional[int] = None,
    active_end_ns: Optional[int] = None,
    hz_counts_active: Optional[Dict[str, int]] = None,
    gap_ms: Optional[float] = None,
    active_duration_s: Optional[float] = None,
    tracker_stats: Optional[FieldStats] = None,
    tracker_hz: Optional[float] = None,
    timing_tracker_topic: Optional[str] = None,
    target_stats: Optional[FieldStats] = None,
    target_hz: Optional[float] = None,
    timing_target_topic: Optional[str] = None,
    gap_count: Optional[int] = None,
    gap_removed_s: Optional[float] = None,
):
    DEFAULT_STATS = FieldStats(
        float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), 0
    )

    base_duration_s = (base_end_ns - base_start_ns) * 1e-9
    if base_duration_s <= 0:
        base_duration_s = float("nan")

    lines: List[str] = []
    bag_name = os.path.basename(os.path.normpath(bag_dir))  
    lines.append(f"# Timing Summary: {bag_name}\n")
    lines.append(f"Bag: `{bag_dir}`\n")
    lines.append("Timing vocabulary: canonical fields only (`pub_dt_ms` is the cadence metric).\n")
    lines.append(f"Contract schema: `v{METRICS_SCHEMA_VERSION}`\n")
    lines.append(f"- metric_windows: `{METRIC_WINDOWS}`\n")
    lines.append(
        "- metric_thresholds_ms: "
        f"`{{'e2e_det_ms': {METRIC_WARN_THRESHOLDS['e2e_det_ms']}, 'pub_dt_ms': {METRIC_WARN_THRESHOLDS['pub_dt_ms']}, 'infer_ms': {METRIC_WARN_THRESHOLDS['infer_ms']}, 'container_queue_ms': {METRIC_WARN_THRESHOLDS['container_queue_ms']}, 'track_ms': {METRIC_WARN_THRESHOLDS['track_ms']}, 'e2e_target_ms': {METRIC_WARN_THRESHOLDS['e2e_target_ms']}}}`\n"
    )
    lines.append("Base window: first to last `/timing` message (bag timestamps)\n")
    lines.append(f"- start_ns: `{base_start_ns}`\n")
    lines.append(f"- end_ns: `{base_end_ns}`\n")
    lines.append(f"- duration_s: `{_fmt(base_duration_s)}`\n")

    lines.append("## Per-field stats (/timing)\n")
    lines.append("| field | n | mean | p50 | p95 | p99 | min | max |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|\n")
    for field in ["pre_ms", "container_queue_ms", "zmq_roundtrip_ms", "infer_ms", "e2e_det_ms", "pub_dt_ms"]:
        st = timing_stats.get(field, DEFAULT_STATS)
        lines.append(
            f"| {field} | {st.n} | {_fmt(st.mean)} | {_fmt(st.p50)} | {_fmt(st.p95)} | {_fmt(st.p99)} | {_fmt(st.vmin)} | {_fmt(st.vmax)} |\n"
        )

    lines.append("\n## Achieved Hz (counts over base window)\n")
    lines.append("| topic | count | Hz |\n")
    lines.append("|---|---:|---:|\n")
    for topic in sorted(hz_counts.keys()):
        c = int(hz_counts.get(topic, 0))
        hz = (c / base_duration_s) if base_duration_s and not math.isnan(base_duration_s) and base_duration_s > 0 else float("nan")
        lines.append(f"| {topic} | {c} | {_fmt(hz)} |\n")

    # Active-only block
    if (
        timing_stats_active is not None
        and active_start_ns is not None
        and active_end_ns is not None
        and hz_counts_active is not None
        and active_duration_s is not None
    ):
        duration2_s = float(active_duration_s) if active_duration_s > 0 else float("nan")

        lines.append("\n## Active-only window (gap-filtered)\n")
        if gap_ms is not None:
            lines.append(f"Definition: samples with `pub_dt_ms <= {gap_ms:.1f}` ms\n")
        lines.append(f"- start_ns: `{active_start_ns}`\n")
        lines.append(f"- end_ns: `{active_end_ns}`\n")
        lines.append(f"- duration_s: `{_fmt(duration2_s)}`\n")
        if gap_count is not None:
            lines.append(f"- gap_count: `{gap_count}`\n")
        if gap_removed_s is not None:
            lines.append(f"- gap_removed_s: `{_fmt(gap_removed_s)}`\n")

        # How many /timing samples were removed by the pub_dt gap filter
        try:
            base_n = int(timing_stats.get("pub_dt_ms", DEFAULT_STATS).n)
            active_n = int(timing_stats_active.get("pub_dt_ms", DEFAULT_STATS).n)
            lines.append(f"- dropped_samples: `{base_n - active_n}`\n")
        except Exception:
            pass

        lines.append("\n### Per-field stats (/timing), active-only\n")
        lines.append("| field | n | mean | p50 | p95 | p99 | min | max |\n")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for field in ["pre_ms", "container_queue_ms", "zmq_roundtrip_ms", "infer_ms", "e2e_det_ms", "pub_dt_ms"]:
            st = timing_stats_active.get(field, DEFAULT_STATS)
            lines.append(
                f"| {field} | {st.n} | {_fmt(st.mean)} | {_fmt(st.p50)} | {_fmt(st.p95)} | {_fmt(st.p99)} | {_fmt(st.vmin)} | {_fmt(st.vmax)} |\n"
            )

        lines.append("\n### Achieved Hz (active-only window)\n")
        lines.append("| topic | count | Hz |\n")
        lines.append("|---|---:|---:|\n")
        for topic in sorted(hz_counts_active.keys()):
            c = int(hz_counts_active.get(topic, 0))
            hz = (c / duration2_s) if duration2_s and not math.isnan(duration2_s) and duration2_s > 0 else float("nan")
            lines.append(f"| {topic} | {c} | {_fmt(hz)} |\n")

    # Tracker runtime section
    if tracker_stats is not None:
        lines.append("\n## Tracker runtime\n")
        if timing_tracker_topic:
            lines.append(f"Topic: `{timing_tracker_topic}` (field: `track_ms`)\n")
        lines.append("| metric | value |\n")
        lines.append("|---|---:|\n")
        lines.append(f"| n | {tracker_stats.n} |\n")
        lines.append(f"| mean (ms) | {_fmt(tracker_stats.mean)} |\n")
        lines.append(f"| p50 (ms) | {_fmt(tracker_stats.p50)} |\n")
        lines.append(f"| p95 (ms) | {_fmt(tracker_stats.p95)} |\n")
        lines.append(f"| p99 (ms) | {_fmt(tracker_stats.p99)} |\n")
        lines.append(f"| max (ms) | {_fmt(tracker_stats.vmax)} |\n")
        if tracker_hz is not None:
            lines.append(f"\nActive-only Hz (tracker timing): `{_fmt(tracker_hz)}`\n")

    if target_stats is not None:
        lines.append("\n## Target end-to-end runtime\n")
        if timing_target_topic:
            lines.append(f"Topic: `{timing_target_topic}` (field: `e2e_target_ms`)\n")
        lines.append("| metric | value |\n")
        lines.append("|---|---:|\n")
        lines.append(f"| n | {target_stats.n} |\n")
        lines.append(f"| mean (ms) | {_fmt(target_stats.mean)} |\n")
        lines.append(f"| p50 (ms) | {_fmt(target_stats.p50)} |\n")
        lines.append(f"| p95 (ms) | {_fmt(target_stats.p95)} |\n")
        lines.append(f"| p99 (ms) | {_fmt(target_stats.p99)} |\n")
        lines.append(f"| max (ms) | {_fmt(target_stats.vmax)} |\n")
        if target_hz is not None:
            lines.append(f"\nActive-only Hz (target timing): `{_fmt(target_hz)}`\n")

    if figures_written:
        lines.append("\n## Figures\n")
        for fpath in figures_written:
            lines.append(f"- `{fpath}`\n")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag", help="Path to rosbag2 directory (e.g. bags/raw/2026-02-25__slice__primary)")

    # Optional outputs, auto-filled if not given
    ap.add_argument("--out", default="", help="Output markdown path (default: reports/timing/<bag>__timing.md)")
    ap.add_argument("--figdir", default="", help="Directory to save figures (default: figures/timing/<bag>/)")

    ap.add_argument("--timing-topic", default="/timing")
    ap.add_argument(
        "--timing-tracker-topic",
        default="/timing_tracker",
        help="Topic publishing tracker runtime Timing messages (track_ms).",
    )
    ap.add_argument(
        "--timing-target-topic",
        default="/timing_target",
        help="Topic publishing target timing Timing messages (e2e_target_ms).",
    )
    ap.add_argument("--plot-timeseries", action="store_true", help="Also save pub_dt_ms time series plot")
    ap.add_argument(
        "--gap-ms",
        type=float,
        default=100.0,
        help="Treat samples with pub_dt_ms > gap-ms as restart gaps; compute active-only stats too.",
    )
    args = ap.parse_args()

    bag_dir = os.path.abspath(args.bag)
    bag_name = os.path.basename(os.path.normpath(bag_dir))

    # Default locations
    thesis_root = os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code"))
    default_out = os.path.join(thesis_root, "reports", "timing", f"{bag_name}__timing.md")
    default_figdir = os.path.join(thesis_root, "figures", "timing", bag_name)

    out_path = args.out if args.out.strip() else default_out
    figdir = args.figdir if args.figdir.strip() else default_figdir

    if not os.path.isdir(bag_dir):
        raise SystemExit(f"Bag dir not found: {bag_dir}")

    if not _try_import_ros():
        raise SystemExit(
            "Missing ROS python deps (rosbag2_py/rclpy). Fallback plan:\n"
            "1) Source ROS:\n"
            "   source /opt/ros/jazzy/setup.bash\n"
            "2) Run again with the ROS environment active.\n"
            "If that still fails, use:\n"
            "   ros2 bag info <bag>\n"
            "and tell me the exact output, then we will do a pure-metadata Hz summary without message parsing."
        )

    # base timing + base counts
    timing_vals, timing_ts_ns, base_start, base_end, base_counts, type_map = _read_bag_timing_and_counts(
        bag_dir,
        timing_topic=args.timing_topic,
        topics_for_hz=["/detections", "/timing", "/tracks", "/target", args.timing_tracker_topic],
    )
    timing_stats = {k: _compute_stats(v) for k, v in timing_vals.items()}

    base_duration_s = (base_end - base_start) * 1e-9

    # Active-only indices based on pub_dt_ms threshold
    gap_ms = float(args.gap_ms)
    pub_dt = timing_vals.get("pub_dt_ms", [])

    active_idx: List[int] = [i for i, v in enumerate(pub_dt) if v <= gap_ms] if pub_dt else []

    # Gap metrics (based on pub_dt_ms threshold)
    gap_count = len([1 for v in pub_dt if v > gap_ms]) if pub_dt else 0
    gap_removed_s: Optional[float] = None

    # Build active intervals from each accepted pub_dt sample interval [t_i - pub_dt_i, t_i].
    # This avoids severe underestimation from index-contiguity when valid samples are sparse.
    active_intervals_ns: List[Tuple[int, int]] = []
    if active_idx:
        for i in active_idx:
            t_end = int(timing_ts_ns[i])
            dt_ms = float(pub_dt[i]) if i < len(pub_dt) else 0.0
            if dt_ms <= 0.0:
                continue
            t_start = max(base_start, t_end - int(dt_ms * 1e6))
            if t_end > t_start:
                active_intervals_ns.append((t_start, t_end))

    active_intervals_ns.sort(key=lambda x: x[0])

    # Merge overlapping active intervals and compute active duration.
    active_segments_ns: List[Tuple[int, int]] = []
    active_duration_s = float("nan")
    active_start_ns = None
    active_end_ns = None

    if active_intervals_ns:
        cur_start, cur_end = active_intervals_ns[0]
        for s, e in active_intervals_ns[1:]:
            if s <= cur_end:
                cur_end = max(cur_end, e)
            else:
                active_segments_ns.append((cur_start, cur_end))
                cur_start, cur_end = s, e
        active_segments_ns.append((cur_start, cur_end))

        active_duration_s = 0.0
        for a_ns, b_ns in active_segments_ns:
            active_duration_s += (b_ns - a_ns) * 1e-9
        active_start_ns = active_segments_ns[0][0]
        active_end_ns = active_segments_ns[-1][1]

        if base_duration_s > 0:
            gap_removed_s = max(0.0, base_duration_s - active_duration_s)

    # active-only timing stats (/timing)
    timing_stats_active: Optional[Dict[str, FieldStats]] = None
    hz_counts_active: Optional[Dict[str, int]] = None

    if active_idx:
        timing_vals_active = {k: _filter_by_indices(v, active_idx) for k, v in timing_vals.items()}
        timing_stats_active = {k: _compute_stats(v) for k, v in timing_vals_active.items()}

        hz_counts_active = _count_topics_in_segments(
            bag_dir=bag_dir,
            segments_ns=active_segments_ns,
            topics=["/detections", "/timing", "/tracks", "/target", args.timing_tracker_topic],
            storage_id="",
        )

    # tracker runtime: read track_ms from /timing_tracker inside active segments
    track_ms_vals, _track_ts = _read_metric_in_segments(
        bag_dir=bag_dir,
        topic_name=args.timing_tracker_topic,
        field_name="track_ms",
        segments_ns=active_segments_ns if active_segments_ns else [],
        type_map=type_map,
        storage_id="",
    )
    target_e2e_vals, _target_ts = _read_metric_in_segments(
        bag_dir=bag_dir,
        topic_name=args.timing_target_topic,
        field_name="e2e_target_ms",
        segments_ns=active_segments_ns if active_segments_ns else [],
        type_map=type_map,
        storage_id="",
    )
    tracker_stats = _compute_stats(track_ms_vals) if track_ms_vals else None
    tracker_hz = (
        (len(track_ms_vals) / active_duration_s)
        if (track_ms_vals and not math.isnan(active_duration_s) and active_duration_s > 0)
        else float("nan")
    )
    target_stats = _compute_stats(target_e2e_vals) if target_e2e_vals else None
    target_hz = (
        (len(target_e2e_vals) / active_duration_s)
        if (target_e2e_vals and not math.isnan(active_duration_s) and active_duration_s > 0)
        else float("nan")
    )

    # Inject tracker runtime into plots if present
    if track_ms_vals:
        timing_vals["track_ms_tracker"] = track_ms_vals

    # Save figures
    _save_plots(
        figdir=os.path.abspath(figdir),
        timing_vals=timing_vals,
        timing_ts_ns=timing_ts_ns,
        plot_timeseries=bool(args.plot_timeseries),
    )

    figures_written = [
        os.path.join(figdir, "e2e_det_ms_hist.png"),
        os.path.join(figdir, "e2e_det_ms_cdf.png"),
        os.path.join(figdir, "pub_dt_ms_hist.png"),
        os.path.join(figdir, "pub_dt_ms_cdf.png"),
    ]
    if args.plot_timeseries:
        figures_written.append(os.path.join(figdir, "pub_dt_ms_timeseries.png"))
    if track_ms_vals:
        figures_written.append(os.path.join(figdir, "track_ms_hist.png"))
        figures_written.append(os.path.join(figdir, "track_ms_cdf.png"))

    _write_markdown(
        out_path=os.path.abspath(out_path),
        bag_dir=bag_dir,
        base_start_ns=base_start,
        base_end_ns=base_end,
        timing_stats=timing_stats,
        hz_counts=base_counts,
        figures_written=figures_written,
        timing_stats_active=timing_stats_active,
        active_start_ns=active_start_ns,
        active_end_ns=active_end_ns,
        hz_counts_active=hz_counts_active,
        gap_ms=gap_ms,
        active_duration_s=active_duration_s if not math.isnan(active_duration_s) else None,
        gap_count=gap_count if pub_dt else None,
        gap_removed_s=gap_removed_s if pub_dt else None,
        tracker_stats=tracker_stats,
        tracker_hz=tracker_hz,
        timing_tracker_topic=args.timing_tracker_topic if track_ms_vals else None,
        target_stats=target_stats,
        target_hz=target_hz,
        timing_target_topic=args.timing_target_topic if target_e2e_vals else None,
    )

    print(f"Wrote: {os.path.abspath(out_path)}")
    print(f"Figures in: {os.path.abspath(figdir)}")


if __name__ == "__main__":
    main()