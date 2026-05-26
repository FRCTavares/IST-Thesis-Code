#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def as_float(value, default=None):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def as_int(value, default=0):
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except Exception:
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def build_similarity_lookup(rows: list[dict[str, str]]):
    sims = []
    for row in rows:
        t = as_float(row.get("t"))
        track_id = as_int(row.get("track_id"))
        sim = as_float(row.get("similarity_to_train_memory"))
        if t is not None and track_id > 0 and sim is not None:
            sims.append((t, track_id, sim))
    return sims


def nearest_similarity(sims, t: float, track_id: int, max_dt: float):
    best = None
    best_dt = None
    for sample_t, sample_track_id, sim in sims:
        if sample_track_id != track_id:
            continue
        dt = abs(sample_t - t)
        if dt <= max_dt and (best_dt is None or dt < best_dt):
            best = sim
            best_dt = dt
    return best


def build_scores_by_frame(rows: list[dict[str, str]]):
    scores_by_frame = {}
    for row in rows:
        frame_id = as_int(row.get("frame_id"))
        track_id = as_int(row.get("score_track_id"))
        total = as_float(row.get("total"), 0.0)
        rank = as_int(row.get("rank"))
        t = as_float(row.get("t"))
        if frame_id <= 0 or track_id <= 0 or t is None:
            continue
        scores_by_frame.setdefault(frame_id, []).append({
            "track_id": track_id,
            "total": total,
            "rank": rank,
            "t": t,
        })
    return scores_by_frame



def label_selection(event_type: str, selected: int, correct_id: int) -> str:
    if event_type == "pre_selection":
        return "pre_selection"
    if selected <= 0:
        return "lost"
    if correct_id > 0 and selected == correct_id:
        return "correct"
    if correct_id > 0:
        return "wrong"
    return "lost"


def apply_margin_policy(timeline_rows, scores_by_frame, sims, margin, min_candidate_total, max_sim_dt):
    out_rows = []
    switches = 0

    for row in timeline_rows:
        frame_id = as_int(row.get("frame_id"))
        t = as_float(row.get("t"))
        raw_selected = as_int(row.get("raw_selected"))
        correct_id = as_int(row.get("correct_id"))

        selected = raw_selected
        reason = "raw"
        current_sim = None
        if t is not None and raw_selected > 0:
            current_sim = nearest_similarity(sims, t, raw_selected, max_sim_dt)

        best = None
        if t is not None and current_sim is not None:
            for candidate in scores_by_frame.get(frame_id, []):
                candidate_id = int(candidate["track_id"])
                if candidate_id == raw_selected:
                    continue
                if float(candidate["total"]) < min_candidate_total:
                    continue

                candidate_sim = nearest_similarity(sims, t, candidate_id, max_sim_dt)
                if candidate_sim is None:
                    continue

                advantage = candidate_sim - current_sim
                if advantage < margin:
                    continue

                if best is None or candidate_sim > best["candidate_sim"]:
                    best = {
                        "track_id": candidate_id,
                        "candidate_sim": candidate_sim,
                        "advantage": advantage,
                        "total": float(candidate["total"]),
                    }

        if best is not None:
            selected = int(best["track_id"])
            reason = "mars_margin_switch"
            switches += 1

        label = label_selection(str(row.get("event_type", "")), selected, correct_id)

        out = dict(row)
        out["v2q_selected"] = str(selected)
        out["v2q_label"] = label
        out["v2q_reason"] = reason
        out["v2q_current_sim"] = "" if current_sim is None else "{:.6f}".format(current_sim)
        out["v2q_best_candidate"] = "0" if best is None else str(best["track_id"])
        out["v2q_best_sim"] = "" if best is None else "{:.6f}".format(best["candidate_sim"])
        out["v2q_margin"] = "" if best is None else "{:.6f}".format(best["advantage"])
        out_rows.append(out)

    return out_rows, switches



def apply_stable_margin_policy(
    timeline_rows,
    scores_by_frame,
    sims,
    margin,
    min_candidate_total,
    max_sim_dt,
    confirm_frames,
    raw_switch_margin,
    allow_raw_switch_without_current_sim,
    max_mars_total_gap,
):
    """Stateful V2Q policy.

    Difference from apply_margin_policy:
    - keeps the previous selected ID instead of blindly following raw_selected every frame;
    - only switches to a MARS candidate after confirm_frames consecutive support;
    - only accepts a raw-selected ID switch if the previous selected ID has no usable similarity,
      or if raw has enough similarity advantage over the previous selected ID.

    This is still offline/probe logic, not live TIM behaviour.
    """
    out_rows = []
    switches = 0
    confirmed_margin_switches = 0
    raw_guard_switches = 0
    raw_rejected_switches = 0

    stable_selected = None
    pending_candidate = None
    pending_count = 0

    for row in timeline_rows:
        frame_id = as_int(row.get("frame_id"))
        t = as_float(row.get("t"))
        raw_selected = as_int(row.get("raw_selected"))
        correct_id = as_int(row.get("correct_id"))
        event_type = str(row.get("event_type", ""))

        if stable_selected is None:
            stable_selected = raw_selected

        selected_before = stable_selected
        selected = stable_selected
        reason = "stable_keep"

        current_sim = None
        raw_sim = None
        best = None

        if t is not None and stable_selected > 0:
            current_sim = nearest_similarity(sims, t, stable_selected, max_sim_dt)

        if t is not None and raw_selected > 0:
            raw_sim = nearest_similarity(sims, t, raw_selected, max_sim_dt)

        # Raw switch guard:
        # Do not blindly follow raw ID changes. They are the main source of correct->wrong jumps.
        if raw_selected > 0 and raw_selected != stable_selected:
            if current_sim is None and allow_raw_switch_without_current_sim:
                selected = raw_selected
                stable_selected = raw_selected
                reason = "raw_switch_no_current_similarity"
                raw_guard_switches += 1
            elif current_sim is None:
                selected = stable_selected
                reason = "raw_switch_rejected_no_current_similarity"
                raw_rejected_switches += 1
            elif raw_sim is not None and (raw_sim - current_sim) >= raw_switch_margin:
                selected = raw_selected
                stable_selected = raw_selected
                reason = "raw_switch_similarity_guard"
                raw_guard_switches += 1
            else:
                selected = stable_selected
                reason = "raw_switch_rejected"
                raw_rejected_switches += 1
        else:
            selected = stable_selected

        # MARS relative-margin candidate search against the current stable selection.
        # Candidate validity guard:
        # MARS may prefer the wrong person in ambiguous re-entry frames. Therefore,
        # a MARS switch is only allowed when the candidate is also geometrically
        # plausible according to TIM's score table. If the current selected track
        # is present with a much stronger TIM total score, the appearance cue is
        # not allowed to override it.
        current_sim = None
        current_total = None
        for score_candidate in scores_by_frame.get(frame_id, []):
            if int(score_candidate["track_id"]) == stable_selected:
                current_total = float(score_candidate["total"])
                break

        if t is not None and stable_selected > 0:
            current_sim = nearest_similarity(sims, t, stable_selected, max_sim_dt)

        if t is not None and current_sim is not None:
            for candidate in scores_by_frame.get(frame_id, []):
                candidate_id = int(candidate["track_id"])
                candidate_total = float(candidate["total"])

                if candidate_id == stable_selected:
                    continue
                if candidate_total < min_candidate_total:
                    continue
                if current_total is not None and candidate_total < (current_total - max_mars_total_gap):
                    continue

                candidate_sim = nearest_similarity(sims, t, candidate_id, max_sim_dt)
                if candidate_sim is None:
                    continue

                advantage = candidate_sim - current_sim
                if advantage < margin:
                    continue

                if best is None or candidate_sim > best["candidate_sim"]:
                    best = {
                        "track_id": candidate_id,
                        "candidate_sim": candidate_sim,
                        "advantage": advantage,
                        "total": candidate_total,
                        "current_total": current_total,
                    }

        if best is not None:
            candidate_id = int(best["track_id"])
            if pending_candidate == candidate_id:
                pending_count += 1
            else:
                pending_candidate = candidate_id
                pending_count = 1

            if pending_count >= confirm_frames:
                stable_selected = candidate_id
                selected = stable_selected
                reason = "mars_margin_confirmed_switch"
                confirmed_margin_switches += 1
                pending_candidate = None
                pending_count = 0
            else:
                selected = stable_selected
                reason = "mars_margin_pending"
        else:
            pending_candidate = None
            pending_count = 0
            selected = stable_selected

        if selected != selected_before:
            switches += 1

        label = label_selection(event_type, selected, correct_id)

        out = dict(row)
        out["v2q_selected"] = str(selected)
        out["v2q_label"] = label
        out["v2q_reason"] = reason
        out["v2q_current_sim"] = "" if current_sim is None else "{:.6f}".format(current_sim)
        out["v2q_raw_sim"] = "" if raw_sim is None else "{:.6f}".format(raw_sim)
        out["v2q_best_candidate"] = "0" if best is None else str(best["track_id"])
        out["v2q_best_sim"] = "" if best is None else "{:.6f}".format(best["candidate_sim"])
        out["v2q_margin"] = "" if best is None else "{:.6f}".format(best["advantage"])
        out["v2q_pending_candidate"] = "0" if pending_candidate is None else str(pending_candidate)
        out["v2q_pending_count"] = str(pending_count)
        out_rows.append(out)

    stats = {
        "switches": switches,
        "confirmed_margin_switches": confirmed_margin_switches,
        "raw_guard_switches": raw_guard_switches,
        "raw_rejected_switches": raw_rejected_switches,
    }
    return out_rows, stats


def compute_durations(rows: list[dict[str, str]], label_column: str):
    correct = 0.0
    wrong = 0.0
    lost = 0.0

    for current, nxt in zip(rows, rows[1:]):
        current_t = as_float(current.get("t"), 0.0)
        next_t = as_float(nxt.get("t"), current_t)
        dt = max(0.0, next_t - current_t)
        label = current.get(label_column, "")

        if label == "correct":
            correct += dt
        elif label == "wrong":
            wrong += dt
        elif label == "lost":
            lost += dt

    return correct, wrong, lost


def write_outputs(output_dir: Path, rows, switches, margin, min_candidate_total, max_sim_dt):
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_c, raw_w, raw_l = compute_durations(rows, "label_raw")
    v2q_c, v2q_w, v2q_l = compute_durations(rows, "v2q_label")

    timeline_path = output_dir / "timeline.csv"
    with timeline_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_csv = output_dir / "summary.csv"
    summary_csv.write_text(
        "margin,switches,raw_correct,raw_wrong,raw_lost,v2q_correct,v2q_wrong,v2q_lost\n"
        + "{},{},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}\n".format(
            margin, switches, raw_c, raw_w, raw_l, v2q_c, v2q_w, v2q_l
        ),
        encoding="utf-8",
    )

    summary_md = output_dir / "summary.md"
    summary_md.write_text(
        "# TIM-V2Q MARS margin policy\n\n"
        + "## Parameters\n\n"
        + "- margin: {}\n".format(margin)
        + "- min candidate total: {}\n".format(min_candidate_total)
        + "- max similarity dt: {}\n".format(max_sim_dt)
        + "- switches: {}\n\n".format(switches)
        + "## Global result\n\n"
        + "| Metric | Raw | V2Q |\n"
        + "|---|---:|---:|\n"
        + "| correct_s | {:.3f} | {:.3f} |\n".format(raw_c, v2q_c)
        + "| wrong_s | {:.3f} | {:.3f} |\n".format(raw_w, v2q_w)
        + "| lost_s | {:.3f} | {:.3f} |\n".format(raw_l, v2q_l),
        encoding="utf-8",
    )

    return summary_md


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--similarity", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--margin", type=float, default=0.08)
    parser.add_argument("--min-candidate-total", type=float, default=0.30)
    parser.add_argument("--max-sim-dt", type=float, default=0.50)
    parser.add_argument("--stable", action="store_true", help="Use stateful anti-raw-switch and confirmed MARS policy")
    parser.add_argument("--confirm-frames", type=int, default=3)
    parser.add_argument("--raw-switch-margin", type=float, default=0.20)
    parser.add_argument(
        "--allow-raw-switch-without-current-sim",
        action="store_true",
        help="Allow raw ID changes when the current stable ID has no nearby similarity sample",
    )
    parser.add_argument(
        "--max-mars-total-gap",
        type=float,
        default=0.20,
        help="Reject MARS switches when candidate TIM total is more than this below current selected TIM total",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    timeline_rows = read_csv(args.timeline)
    score_rows = read_csv(args.scores)
    similarity_rows = read_csv(args.similarity)

    sims = build_similarity_lookup(similarity_rows)
    scores_by_frame = build_scores_by_frame(score_rows)

    if args.stable:
        rows, stats = apply_stable_margin_policy(
            timeline_rows=timeline_rows,
            scores_by_frame=scores_by_frame,
            sims=sims,
            margin=args.margin,
            min_candidate_total=args.min_candidate_total,
            max_sim_dt=args.max_sim_dt,
            confirm_frames=args.confirm_frames,
            raw_switch_margin=args.raw_switch_margin,
            allow_raw_switch_without_current_sim=args.allow_raw_switch_without_current_sim,
            max_mars_total_gap=args.max_mars_total_gap,
        )
        switches = stats["switches"]
    else:
        rows, switches = apply_margin_policy(
            timeline_rows=timeline_rows,
            scores_by_frame=scores_by_frame,
            sims=sims,
            margin=args.margin,
            min_candidate_total=args.min_candidate_total,
            max_sim_dt=args.max_sim_dt,
        )
        stats = {"switches": switches}

    summary = write_outputs(
        output_dir=args.output_dir,
        rows=rows,
        switches=switches,
        margin=args.margin,
        min_candidate_total=args.min_candidate_total,
        max_sim_dt=args.max_sim_dt,
    )

    if args.stable:
        with (args.output_dir / "stable_policy_stats.txt").open("w", encoding="utf-8") as f:
            for k, v in stats.items():
                f.write(f"{k}: {v}\n")
            f.write(f"confirm_frames: {args.confirm_frames}\n")
            f.write(f"raw_switch_margin: {args.raw_switch_margin}\n")
            f.write(f"allow_raw_switch_without_current_sim: {args.allow_raw_switch_without_current_sim}\n")
            f.write(f"max_mars_total_gap: {args.max_mars_total_gap}\n")

    print(summary.read_text(encoding="utf-8"))
    print("[ok] wrote", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
