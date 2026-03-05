#!/usr/bin/env python3
import argparse
import os
import numpy as np

from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

import matplotlib.pyplot as plt


def read_bag(bag_dir, topics):
    storage_options = StorageOptions(uri=bag_dir, storage_id="mcap")
    converter_options = ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr")
    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    topic_types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    wanted = {t: topic_types[t] for t in topics if t in topic_types}
    msg_classes = {t: get_message(typ) for t, typ in wanted.items()}

    data = {t: [] for t in wanted.keys()}
    while reader.has_next():
        topic, raw, t_ns = reader.read_next()
        if topic not in wanted:
            continue
        msg = deserialize_message(raw, msg_classes[topic])
        data[topic].append((int(t_ns), msg))
    return data


def stats(x):
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return None
    return {
        "n": int(x.size),
        "mean": float(np.mean(x)),
        "p50": float(np.percentile(x, 50)),
        "p95": float(np.percentile(x, 95)),
        "p99": float(np.percentile(x, 99)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def longest_true_segment(t_s, flag, max_gap_s=0.2):
    best = 0.0
    cur_start = None
    last_t = None
    for ti, fi in zip(t_s, flag):
        if fi:
            if cur_start is None:
                cur_start = ti
            if last_t is not None and (ti - last_t) > max_gap_s:
                best = max(best, last_t - cur_start)
                cur_start = ti
        else:
            if cur_start is not None and last_t is not None:
                best = max(best, last_t - cur_start)
            cur_start = None
        last_t = ti
    if cur_start is not None and last_t is not None:
        best = max(best, last_t - cur_start)
    return best


def reacq_times(t_s, has):
    out = []
    lost = False
    t0 = None
    for ti, ht in zip(t_s, has):
        if (not lost) and (not ht):
            lost = True
            t0 = ti
        elif lost and ht:
            out.append(ti - t0)
            lost = False
            t0 = None
    return out


def target_switches_debounced(has, ids, k=8):
    sw = 0
    last = None
    cand = None
    cand_count = 0

    for ht, tid in zip(has, ids):
        if not ht:
            cand = None
            cand_count = 0
            continue

        if last is None:
            last = tid
            continue

        if tid == last:
            cand = None
            cand_count = 0
            continue

        # candidate new id
        if cand is None or tid != cand:
            cand = tid
            cand_count = 1
        else:
            cand_count += 1
            if cand_count >= k:
                sw += 1
                last = cand
                cand = None
                cand_count = 0

    return sw


def write_md(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag_dir")
    ap.add_argument(
        "--out_root",
        default=os.path.join(os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code")), "reports", "tracking"),
    )
    ap.add_argument("--tag", default="", help="Optional; if empty and bag name ends with __<tracker>, reuse that")
    ap.add_argument("--quality_thr", type=float, default=0.0, help="has_target := quality > thr")
    args = ap.parse_args()

    bag_dir = os.path.abspath(args.bag_dir)
    base = os.path.basename(os.path.normpath(bag_dir))
    # Auto-detect tracker tag from bag name if not supplied
    if not args.tag:
        parts = base.split("__")
        if len(parts) >= 2:
            args.tag = parts[-1]  # last token is tracker name by convention
    name = base if (not args.tag or base.endswith(f"__{args.tag}")) else f"{base}__{args.tag}"
    out_dir = os.path.join(os.path.abspath(args.out_root), name)
    os.makedirs(out_dir, exist_ok=True)

    data = read_bag(bag_dir, ["/target", "/timing_tracker"])

    if "/target" not in data or len(data["/target"]) == 0:
        raise SystemExit("No /target in bag")

    t_ns = np.array([x[0] for x in data["/target"]], dtype=np.int64)
    t_s = (t_ns - t_ns[0]) / 1e9

    # TargetState fields
    quality = np.array([float(x[1].quality) for x in data["/target"]], dtype=float)
    ids = np.array([int(x[1].id) for x in data["/target"]], dtype=np.int64)
    has = quality > args.quality_thr

    continuity = longest_true_segment(t_s, has)
    reacq = reacq_times(t_s, has)
    switches = target_switches_debounced(has, ids)

    # Extended metrics
    duration_s = t_s[-1] if len(t_s) > 1 else 0.0
    switches_per_min = switches / (duration_s / 60.0) if duration_s > 0 else 0.0

    # time_locked_pct: fraction of *time* (not samples) where has=True
    locked_time_s = sum(
        t_s[i] - t_s[i - 1] for i in range(1, len(t_s)) if has[i]
    )
    total_lost_time_s = sum(
        t_s[i] - t_s[i - 1] for i in range(1, len(t_s)) if not has[i]
    )
    time_locked_pct = 100.0 * locked_time_s / duration_s if duration_s > 0 else 0.0

    track_ms = []
    if "/timing_tracker" in data and len(data["/timing_tracker"]) > 0:
        track_ms = [float(x[1].track_ms) for x in data["/timing_tracker"]]
    s_track = stats(track_ms)

    # Plot: has_target timeline
    plt.figure()
    plt.plot(t_s, has.astype(int))
    plt.xlabel("t (s)")
    plt.ylabel("has_target")
    plt.title("Target lock timeline (quality gate)")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "target_lock_timeseries.png"), dpi=200)
    plt.close()

    # Plot: track_ms CDF
    if s_track is not None:
        x = np.sort(np.asarray(track_ms))
        y = np.arange(1, x.size + 1) / x.size
        plt.figure()
        plt.plot(x, y)
        plt.xlabel("track_ms (ms)")
        plt.ylabel("CDF")
        plt.title("Tracker runtime CDF")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "track_ms_cdf.png"), dpi=200)
        plt.close()

    # Plot: reacquisition hist
    if len(reacq) > 0:
        plt.figure()
        plt.hist(reacq, bins=20)
        plt.xlabel("reacquisition time (s)")
        plt.ylabel("count")
        plt.title("Reacquisition times")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "reacq_hist.png"), dpi=200)
        plt.close()

    # Markdown
    md = []
    md.append(f"# Tracking Summary: {name}\n\n")
    md.append(f"- Bag: `{bag_dir}`\n")
    md.append(f"- Duration: {duration_s:.3f} s\n")
    md.append(f"- /target msgs: {len(has)}\n")
    md.append(f"- /timing_tracker msgs: {len(track_ms)}\n\n")

    md.append("## Metrics\n")
    md.append(f"- Time locked: **{time_locked_pct:.1f}%** ({locked_time_s:.1f} s / {duration_s:.1f} s)\n")
    md.append(f"- Total lost time: **{total_lost_time_s:.3f} s**\n")
    md.append(f"- Target lock continuity (longest): **{continuity:.3f} s**\n")
    md.append(f"- Reacquisition events: **{len(reacq)}**\n")
    if len(reacq) > 0:
        md.append(f"- Reacq mean: **{np.mean(reacq):.3f} s**, p95: **{np.percentile(reacq, 95):.3f} s**\n")
    md.append(f"- Target switches (id changes while locked): **{switches}**\n")
    md.append(f"- Switches per minute: **{switches_per_min:.2f}**\n\n")

    md.append("## Tracker runtime (/timing_tracker.track_ms)\n")
    if s_track is None:
        md.append("- No /timing_tracker samples.\n\n")
    else:
        md.append(f"- n: {s_track['n']}\n")
        md.append(f"- mean: {s_track['mean']:.4f} ms\n")
        md.append(f"- p50: {s_track['p50']:.4f} ms\n")
        md.append(f"- p95: {s_track['p95']:.4f} ms\n")
        md.append(f"- p99: {s_track['p99']:.4f} ms\n")
        md.append(f"- max: {s_track['max']:.4f} ms\n\n")

    md.append("## Plots\n")
    md.append("![target_lock_timeseries](target_lock_timeseries.png)\n\n")
    if s_track is not None:
        md.append("![track_ms_cdf](track_ms_cdf.png)\n\n")
    if len(reacq) > 0:
        md.append("![reacq_hist](reacq_hist.png)\n\n")

    report_path = os.path.join(out_dir, "summary.md")
    write_md(report_path, "".join(md))
    print(f"[ok] wrote {report_path}")


if __name__ == "__main__":
    main()