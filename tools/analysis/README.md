# Analysis Tools

This folder contains offline and live analysis tools for thesis evaluation,
performance validation, and TIM-MARS diagnostics.

The tools are split into three groups:

- **Core final evaluation**: scripts used to compute final selected-target
  correctness metrics for TIM-MARS.
- **Diagnostic support**: scripts used to explain TIM-MARS decisions or inspect
  tracker/perception behavior.
- **Live timing validation**: scripts used while running the live stack.

## Core final evaluation

| Tool | Purpose | Use for final metrics? |
| --- | --- | --- |
| `evaluate_tim_target_correctness.py` | Compares raw `/target` and TIM-MARS `/target_memory_mars` against annotation intervals using track-ID correctness and duration metrics. | Yes |
| `evaluate_tim_target_bbox_correctness.py` | Evaluates bbox correctness using the annotated target track as spatial reference on a common `/tracks` clock. | Yes, as spatial complement |
| `evaluate_tim_by_event_type.py` | Aggregates selected-target correctness by annotation `event_type`. | Yes, for event-level tables |

## Diagnostic support

| Tool | Purpose | Notes |
| --- | --- | --- |
| `extract_tim_all_scores.py` | Extracts TIM-MARS `all_scores` candidate diagnostics from `/target_memory_mars/status`. | Use to explain accept/reject decisions. |
| `extract_tim_mars_reid_similarity.py` | Evaluates MARS/ReID similarity over TIM appearance experiment crops. | Appearance-diagnostics only. |
| `analyse_bag_tracking.py` | Computes tracker/target continuity diagnostics from bags. | Useful for tracker analysis, not final TIM correctness. |
| `analyse_bag_timing.py` | Computes offline timing statistics and plots from rosbag2 timing topics. | Useful for performance sections. |

## Live timing validation

| Tool | Purpose | Notes |
| --- | --- | --- |
| `check_live_timing_invariants.py` | Checks live `/timing`, `/timing_tracker`, `/timing_target`, and `/detections` ordering/sanity invariants. | Short live health test. |
| `collect_live_timing_stats.py` | Collects live timing percentiles, topic rates, and optional JSON reports. | Useful for ablation and performance checks. |

## Annotation contract

Final selected-target evaluators expect annotation CSVs with interval timing and
target visibility/correct-track fields. Use the template in:

`tools/analysis/templates/target_correctness_annotations_template.csv`

Intervals use half-open `[start_s, end_s)` boundaries. Gaps are permitted and
remain unscored. Positive-duration overlaps, negative durations, and non-finite
times are rejected because they make duration totals ambiguous. Zero-duration
rows are permitted but contribute no time.

Manual annotation files should be created by the user through the annotation UI;
these tools only consume annotations.

## Target-output validity

A selected-target output is valid only when its ID is non-zero and, when bbox
fields are present, all bbox values are finite with positive width and height.
A zero ID with a non-zero bbox and a non-zero ID with an invalid bbox are both
scored as no valid output. This rule is shared by the track-ID and bbox
evaluators.

## Recommended final workflow

For final TIM-MARS selected-target evaluation:

1. Produce or select a replay bag.
2. Use `evaluate_tim_target_correctness.py` for selected-track duration metrics.
3. Use `evaluate_tim_target_bbox_correctness.py` when spatial bbox agreement is
   needed.
4. Use `evaluate_tim_by_event_type.py` to summarize behavior by event type.
5. Use `extract_tim_all_scores.py` only when a decision needs explanation.

## Important distinction

Full-pipeline reruns from `/camera/image_raw` can regenerate tracker IDs. Manual
annotations created for one tracker run are not automatically valid for a new
full-pipeline run unless the IDs still match or an ID-independent evaluator is
used.
