#!/usr/bin/env python3
"""
Offline TIM-V2 hypothesis-policy simulator.

Uses target_memory_all_scores.csv and target correctness annotations.

Important:
- Wrong target is worse than lost target.
- This script does not modify live TIM logic.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class Params:
    decay: float = 0.85
    ttl_frames: int = 15
    min_hypothesis: float = 0.50
    margin: float = 0.15
    candidate_min_total: float = 0.35
    app_weight: float = 0.0
    evidence_mode: str = "total"

    # TIM-V2B anti-switch policy.
    keep_current_margin: float = 0.10
    switch_margin: float = 0.35
    switch_confirm_frames: int = 5

    # TIM-V2D contradiction gate.
    contradiction_enabled: bool = False
    contradiction_margin: float = 0.45
    contradiction_confirm_frames: int = 3
    contradiction_frame_margin: float = 0.20


@dataclass
class Hypothesis:
    track_id: int
    score: float = 0.0
    last_seen_frame: int = 0
    seen_count: int = 0
    last_candidate_score: float = 0.0


@dataclass
class Candidate:
    frame: int
    t: float
    track_id: int
    total: float
    iou: float = 0.0
    distance: float = 0.0
    scale: float = 0.0
    confidence: float = 0.0
    id_bonus: float = 0.0
    appearance_raw: float = 0.0


@dataclass
class AnnotationInterval:
    start_s: float
    end_s: float
    target_visible: bool
    correct_target_track_id: int
    event_type: str
    target_label: str


@dataclass
class OutputFrame:
    frame: int
    t: float
    selected_track_id: int
    state: str
    best_hypothesis: float
    second_hypothesis: float
    correct_target_track_id: int
    eval_label: str


def as_float(value, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except ValueError:
        return default


def as_int(value, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except ValueError:
        return default


def as_bool(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def load_scores(path: Path) -> Dict[int, List[Candidate]]:
    by_frame: Dict[int, List[Candidate]] = {}

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)

        required = {"frame_id", "t", "score_track_id", "total"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Missing required score columns: {sorted(missing)}")

        for row in reader:
            frame = as_int(row.get("frame_id"))
            t = as_float(row.get("t"))
            track_id = as_int(row.get("score_track_id"))
            total = as_float(row.get("total"), default=float("nan"))
            iou = as_float(row.get("iou"), default=0.0)
            distance = as_float(row.get("distance"), default=0.0)
            scale = as_float(row.get("scale"), default=0.0)
            confidence = as_float(row.get("confidence"), default=0.0)
            id_bonus = as_float(row.get("id_bonus"), default=0.0)
            appearance_raw = as_float(row.get("appearance_raw"), default=0.0)

            if frame <= 0 or track_id <= 0 or math.isnan(total):
                continue

            by_frame.setdefault(frame, []).append(
                Candidate(
                    frame=frame,
                    t=t,
                    track_id=track_id,
                    total=total,
                    iou=iou,
                    distance=distance,
                    scale=scale,
                    confidence=confidence,
                    id_bonus=id_bonus,
                    appearance_raw=appearance_raw,
                )
            )

    return by_frame


def load_annotations(path: Path) -> List[AnnotationInterval]:
    intervals: List[AnnotationInterval] = []

    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)

        required = {"start_s", "end_s", "target_visible", "correct_target_track_id", "event_type", "target_label"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"Missing required annotation columns: {sorted(missing)}")

        for row in reader:
            intervals.append(
                AnnotationInterval(
                    start_s=as_float(row.get("start_s")),
                    end_s=as_float(row.get("end_s")),
                    target_visible=as_bool(row.get("target_visible")),
                    correct_target_track_id=as_int(row.get("correct_target_track_id")),
                    event_type=str(row.get("event_type", "")).strip(),
                    target_label=str(row.get("target_label", "")).strip(),
                )
            )

    intervals.sort(key=lambda x: x.start_s)
    return intervals


def annotation_for_time(t: float, intervals: List[AnnotationInterval]) -> Optional[AnnotationInterval]:
    for interval in intervals:
        if interval.start_s <= t < interval.end_s:
            return interval
    return None


def select_from_hypotheses(hypotheses: Dict[int, Hypothesis], params: Params) -> Tuple[int, str, float, float]:
    if not hypotheses:
        return 0, "LOST", 0.0, 0.0

    ranked = sorted(hypotheses.values(), key=lambda h: h.score, reverse=True)
    best = ranked[0]
    second_score = ranked[1].score if len(ranked) > 1 else 0.0

    if best.score < params.min_hypothesis:
        return 0, "LOST", best.score, second_score

    if best.score - second_score < params.margin:
        return 0, "UNCERTAIN", best.score, second_score

    return best.track_id, "LOCKED", best.score, second_score


def candidate_evidence(c: Candidate, params: Params) -> float:
    if params.evidence_mode == "total":
        base = c.total
    elif params.evidence_mode == "neutral":
        # TIM-V1 total without incumbent identity bonus.
        # Current implementation uses w_id_bonus = 0.08.
        base = max(0.0, c.total - 0.08 * c.id_bonus)
    elif params.evidence_mode == "geometry":
        # Explicit identity-neutral TIM-V1 geometry/confidence score.
        base = (
            0.34 * c.iou
            + 0.26 * c.distance
            + 0.18 * c.scale
            + 0.14 * c.confidence
        )
    else:
        raise ValueError(f"unknown evidence_mode: {params.evidence_mode}")

    return base + params.app_weight * c.appearance_raw


def simulate(
    scores_by_frame: Dict[int, List[Candidate]],
    annotations: List[AnnotationInterval],
    params: Params,
) -> List[OutputFrame]:
    hypotheses: Dict[int, Hypothesis] = {}
    outputs: List[OutputFrame] = []

    # TIM-V2B selected-hypothesis state.
    selected_memory_id = 0
    challenger_id = 0
    challenger_count = 0
    contradiction_id = 0
    contradiction_count = 0

    all_frames = sorted(scores_by_frame.keys())
    if not all_frames:
        return outputs

    frame_min = min(all_frames)
    frame_max = max(all_frames)
    last_t = 0.0

    for frame in range(frame_min, frame_max + 1):
        candidates = scores_by_frame.get(frame, [])
        if candidates:
            last_t = candidates[0].t

        # Decay all hypotheses.
        for h in hypotheses.values():
            h.score *= params.decay

        # Update hypotheses from candidate evidence.
        for c in candidates:
            if c.total < params.candidate_min_total:
                continue

            evidence = candidate_evidence(c, params)

            h = hypotheses.get(c.track_id)
            if h is None:
                h = Hypothesis(track_id=c.track_id)
                hypotheses[c.track_id] = h

            h.score += evidence
            h.last_seen_frame = frame
            h.seen_count += 1
            h.last_candidate_score = evidence

        # Remove stale hypotheses.
        stale_ids = [
            tid for tid, h in hypotheses.items()
            if frame - h.last_seen_frame > params.ttl_frames
        ]
        for tid in stale_ids:
            del hypotheses[tid]

        # Base ranking.
        ranked = sorted(hypotheses.values(), key=lambda h: h.score, reverse=True)
        best = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None

        best_score = best.score if best else 0.0
        second_score = second.score if second else 0.0
        best_id = best.track_id if best else 0

        current = hypotheses.get(selected_memory_id) if selected_memory_id > 0 else None
        current_score = current.score if current else 0.0

        # TIM-V2B decision:
        # - Hold current ID while still plausible.
        # - Do not switch immediately to a new candidate.
        # - Require sustained challenger dominance.
        if best is None or best_score < params.min_hypothesis:
            selected_id = 0
            state = "LOST"
            selected_memory_id = 0
            challenger_id = 0
            challenger_count = 0

        elif selected_memory_id == 0:
            if best_score - second_score >= params.margin:
                selected_memory_id = best_id
                selected_id = selected_memory_id
                state = "LOCKED"
            else:
                selected_id = 0
                state = "UNCERTAIN"

        elif current is not None and current_score >= params.min_hypothesis:
            if best_id == selected_memory_id:
                selected_id = selected_memory_id
                state = "LOCKED"
                challenger_id = 0
                challenger_count = 0
            else:
                challenger_advantage = best_score - current_score

                if challenger_advantage < params.keep_current_margin:
                    # TIM-V2D: even if current remains best, a persistent close
                    # challenger means identity is contested. Suppress control.
                    close_challenger = second is not None and second.track_id != selected_memory_id and (current_score - second.score) < params.contradiction_margin

                    if params.contradiction_enabled and close_challenger:
                        if contradiction_id == second.track_id:
                            contradiction_count += 1
                        else:
                            contradiction_id = second.track_id
                            contradiction_count = 1

                        if contradiction_count >= params.contradiction_confirm_frames:
                            selected_id = 0
                            state = "UNCERTAIN"
                        else:
                            selected_id = selected_memory_id
                            state = "LOCKED"
                    else:
                        contradiction_id = 0
                        contradiction_count = 0
                        selected_id = selected_memory_id
                        state = "LOCKED"

                    challenger_id = 0
                    challenger_count = 0
                elif challenger_advantage < params.switch_margin:
                    selected_id = 0
                    state = "UNCERTAIN"
                    if challenger_id == best_id:
                        challenger_count += 1
                    else:
                        challenger_id = best_id
                        challenger_count = 1
                else:
                    if challenger_id == best_id:
                        challenger_count += 1
                    else:
                        challenger_id = best_id
                        challenger_count = 1

                    if challenger_count >= params.switch_confirm_frames:
                        selected_memory_id = best_id
                        selected_id = selected_memory_id
                        state = "LOCKED"
                        challenger_id = 0
                        challenger_count = 0
                    else:
                        selected_id = 0
                        state = "UNCERTAIN"

        else:
            # Current hypothesis expired or fell below threshold.
            # Require the best candidate to be unambiguous before reacquiring.
            if best_score >= params.min_hypothesis and best_score - second_score >= params.margin:
                selected_memory_id = best_id
                selected_id = selected_memory_id
                state = "LOCKED"
                challenger_id = 0
                challenger_count = 0
            else:
                selected_id = 0
                state = "LOST"
                selected_memory_id = 0
                challenger_id = 0
                challenger_count = 0

        # TIM-V2D post-decision contradiction gate.
        # Use per-frame candidate competition, not accumulated hypothesis scores.
        # This avoids hiding ambiguity after the memory has drifted.
        if params.contradiction_enabled and state == "LOCKED" and selected_id > 0:
            selected_candidate = None
            best_other_candidate = None

            for c in candidates:
                ev = candidate_evidence(c, params)

                if c.track_id == selected_id:
                    if selected_candidate is None or ev > selected_candidate[1]:
                        selected_candidate = (c.track_id, ev)
                else:
                    if best_other_candidate is None or ev > best_other_candidate[1]:
                        best_other_candidate = (c.track_id, ev)

            if selected_candidate is not None and best_other_candidate is not None:
                selected_ev = selected_candidate[1]
                other_id = best_other_candidate[0]
                other_ev = best_other_candidate[1]
                frame_gap = selected_ev - other_ev

                if frame_gap < params.contradiction_frame_margin:
                    if contradiction_id == other_id:
                        contradiction_count += 1
                    else:
                        contradiction_id = other_id
                        contradiction_count = 1

                    if contradiction_count >= params.contradiction_confirm_frames:
                        selected_id = 0
                        state = "UNCERTAIN"
                else:
                    contradiction_id = 0
                    contradiction_count = 0
            else:
                contradiction_id = 0
                contradiction_count = 0
        elif state not in {"LOCKED"}:
            contradiction_id = 0
            contradiction_count = 0

        ann = annotation_for_time(last_t, annotations)
        if ann is None:
            correct_id = 0
            eval_label = "ignore"
        elif ann.event_type == "pre_selection" or ann.target_label == "NO_TARGET_SELECTED":
            correct_id = ann.correct_target_track_id
            eval_label = "ignore"
        elif not ann.target_visible or ann.correct_target_track_id <= 0:
            correct_id = ann.correct_target_track_id
            eval_label = "lost"
        elif selected_id <= 0 or state in {"LOST", "UNCERTAIN"}:
            correct_id = ann.correct_target_track_id
            eval_label = "lost"
        elif selected_id == ann.correct_target_track_id:
            correct_id = ann.correct_target_track_id
            eval_label = "correct"
        else:
            correct_id = ann.correct_target_track_id
            eval_label = "wrong"

        outputs.append(
            OutputFrame(
                frame=frame,
                t=last_t,
                selected_track_id=selected_id,
                state=state,
                best_hypothesis=best_score,
                second_hypothesis=second_score,
                correct_target_track_id=correct_id,
                eval_label=eval_label,
            )
        )

    return outputs


def evaluate(outputs: List[OutputFrame]) -> dict:
    valid = [o for o in outputs if o.eval_label != "ignore"]

    if not valid:
        return {
            "frames": 0,
            "correct_frames": 0,
            "wrong_frames": 0,
            "lost_frames": 0,
            "correct_ratio": 0.0,
            "wrong_ratio": 0.0,
            "lost_ratio": 0.0,
            "correct_s": 0.0,
            "wrong_s": 0.0,
            "lost_s": 0.0,
        }

    correct_frames = sum(1 for o in valid if o.eval_label == "correct")
    wrong_frames = sum(1 for o in valid if o.eval_label == "wrong")
    lost_frames = sum(1 for o in valid if o.eval_label == "lost")

    total_frames = len(valid)

    # Prefer time-derived duration when possible.
    # For ratios, frame counts are enough because annotations and scores are aligned.
    if len(valid) >= 2:
        dt_values = [
            valid[i + 1].t - valid[i].t
            for i in range(len(valid) - 1)
            if valid[i + 1].t > valid[i].t
        ]
        mean_dt = sum(dt_values) / len(dt_values) if dt_values else 1.0 / 30.0
    else:
        mean_dt = 1.0 / 30.0

    return {
        "frames": total_frames,
        "correct_frames": correct_frames,
        "wrong_frames": wrong_frames,
        "lost_frames": lost_frames,
        "correct_ratio": correct_frames / total_frames,
        "wrong_ratio": wrong_frames / total_frames,
        "lost_ratio": lost_frames / total_frames,
        "correct_s": correct_frames * mean_dt,
        "wrong_s": wrong_frames * mean_dt,
        "lost_s": lost_frames * mean_dt,
    }


def write_timeline(path: Path, outputs: List[OutputFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "frame",
                "t",
                "selected_track_id",
                "state",
                "best_hypothesis",
                "second_hypothesis",
                "correct_target_track_id",
                "eval_label",
            ],
        )
        writer.writeheader()

        for o in outputs:
            writer.writerow({
                "frame": o.frame,
                "t": f"{o.t:.9f}",
                "selected_track_id": o.selected_track_id,
                "state": o.state,
                "best_hypothesis": f"{o.best_hypothesis:.6f}",
                "second_hypothesis": f"{o.second_hypothesis:.6f}",
                "correct_target_track_id": o.correct_target_track_id,
                "eval_label": o.eval_label,
            })


def write_summary_csv(path: Path, params: Params, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as f:
        fieldnames = [
            "decay",
            "ttl_frames",
            "min_hypothesis",
            "margin",
            "candidate_min_total",
            "app_weight",
            "correct_ratio",
            "wrong_ratio",
            "lost_ratio",
            "correct_s",
            "wrong_s",
            "lost_s",
            "frames",
            "correct_frames",
            "wrong_frames",
            "lost_frames",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        writer.writerow({
            "decay": params.decay,
            "ttl_frames": params.ttl_frames,
            "min_hypothesis": params.min_hypothesis,
            "margin": params.margin,
            "candidate_min_total": params.candidate_min_total,
            "app_weight": params.app_weight,
            **metrics,
        })


def write_summary_md(path: Path, params: Params, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    text = f"""# TIM-V2 Offline Hypothesis Simulation

## Parameters

| Parameter | Value |
|---|---:|
| decay | {params.decay} |
| ttl_frames | {params.ttl_frames} |
| min_hypothesis | {params.min_hypothesis} |
| margin | {params.margin} |
| candidate_min_total | {params.candidate_min_total} |
| app_weight | {params.app_weight} |
| evidence_mode | {params.evidence_mode} |
| keep_current_margin | {params.keep_current_margin} |
| switch_margin | {params.switch_margin} |
| switch_confirm_frames | {params.switch_confirm_frames} |
| contradiction_enabled | {params.contradiction_enabled} |
| contradiction_margin | {params.contradiction_margin} |
| contradiction_confirm_frames | {params.contradiction_confirm_frames} |
| contradiction_frame_margin | {params.contradiction_frame_margin} |

## Result

| Metric | Value |
|---|---:|
| correct_ratio | {metrics["correct_ratio"]:.3f} |
| wrong_ratio | {metrics["wrong_ratio"]:.3f} |
| lost_ratio | {metrics["lost_ratio"]:.3f} |
| correct_s | {metrics["correct_s"]:.2f} |
| wrong_s | {metrics["wrong_s"]:.2f} |
| lost_s | {metrics["lost_s"]:.2f} |
| frames | {metrics["frames"]} |
| correct_frames | {metrics["correct_frames"]} |
| wrong_frames | {metrics["wrong_frames"]} |
| lost_frames | {metrics["lost_frames"]} |

## Baseline Reference

TIM-V1 hard re-entry reference:

- correct_ratio: 0.680
- wrong_ratio: 0.310
- lost_ratio: 0.009

## Decision Rule

Accept only if wrong_ratio decreases below 0.310 without collapsing most frames into LOST.
"""

    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)

    parser.add_argument("--decay", type=float, default=0.85)
    parser.add_argument("--ttl-frames", type=int, default=15)
    parser.add_argument("--min-hypothesis", type=float, default=0.50)
    parser.add_argument("--margin", type=float, default=0.15)
    parser.add_argument("--candidate-min-total", type=float, default=0.35)
    parser.add_argument("--app-weight", type=float, default=0.0)
    parser.add_argument("--evidence-mode", choices=["total", "neutral", "geometry"], default="total")
    parser.add_argument("--keep-current-margin", type=float, default=0.10)
    parser.add_argument("--switch-margin", type=float, default=0.35)
    parser.add_argument("--switch-confirm-frames", type=int, default=5)
    parser.add_argument("--contradiction-enabled", action="store_true")
    parser.add_argument("--contradiction-margin", type=float, default=0.45)
    parser.add_argument("--contradiction-confirm-frames", type=int, default=3)
    parser.add_argument("--contradiction-frame-margin", type=float, default=0.20)

    args = parser.parse_args()

    params = Params(
        decay=args.decay,
        ttl_frames=args.ttl_frames,
        min_hypothesis=args.min_hypothesis,
        margin=args.margin,
        candidate_min_total=args.candidate_min_total,
        app_weight=args.app_weight,
        evidence_mode=args.evidence_mode,
        keep_current_margin=args.keep_current_margin,
        switch_margin=args.switch_margin,
        switch_confirm_frames=args.switch_confirm_frames,
        contradiction_enabled=args.contradiction_enabled,
        contradiction_margin=args.contradiction_margin,
        contradiction_confirm_frames=args.contradiction_confirm_frames,
        contradiction_frame_margin=args.contradiction_frame_margin,
    )

    scores_by_frame = load_scores(args.scores)
    annotations = load_annotations(args.annotations)

    if not scores_by_frame:
        raise SystemExit(f"No usable candidate scores loaded from: {args.scores}")

    if not annotations:
        raise SystemExit(f"No usable annotations loaded from: {args.annotations}")

    outputs = simulate(scores_by_frame, annotations, params)
    metrics = evaluate(outputs)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    write_timeline(args.out_dir / "timeline.csv", outputs)
    write_summary_csv(args.out_dir / "summary.csv", params, metrics)
    write_summary_md(args.out_dir / "summary.md", params, metrics)

    print("TIM-V2 offline simulation complete")
    print(f"out_dir: {args.out_dir}")
    print(f"correct_ratio: {metrics['correct_ratio']:.3f}")
    print(f"wrong_ratio:   {metrics['wrong_ratio']:.3f}")
    print(f"lost_ratio:    {metrics['lost_ratio']:.3f}")


if __name__ == "__main__":
    main()
