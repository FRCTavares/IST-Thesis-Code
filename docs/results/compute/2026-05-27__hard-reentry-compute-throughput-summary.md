# Compute and Throughput Summary - Hard Re-entry Comparison

Date: 2026-05-27  
Dataset: `2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`

## Compared configurations

| Configuration | Tracker | TIM |
|---|---|---|
| Raw OCSORT | OCSORT | off |
| DeepSORT MARS | DeepSORT + MARS appearance | off |
| OCSORT + TIM | OCSORT | on |

## Bag-level topic throughput

| Pipeline | Duration (s) | `/camera/image_raw` Hz | `/detections` Hz | `/tracks` Hz | Target output Hz |
|---|---:|---:|---:|---:|---:|
| Raw OCSORT | 135.674 | 5.40 | 7.02 | 7.02 | 7.03 |
| DeepSORT MARS | 134.737 | 4.04 | 7.01 | 6.41 | 6.42 |
| OCSORT + TIM | 135.674 | 5.80 | 7.02 | 6.98 | 6.98 |

For OCSORT + TIM, the target output rate refers to `/target_memory`. The TIM diagnostic output `/target_memory/status` was also emitted at 6.98 Hz.

## Whole-replay resource measurement

Measured using `/usr/bin/time -v` around `tools/experiments/run_one_clean_tim_replay.sh`.

| Pipeline | Wall time (s) | User CPU (s) | System CPU (s) | CPU % | Peak RSS (MB) |
|---|---:|---:|---:|---:|---:|
| Raw OCSORT | 174.03 | 19.71 | 6.89 | 15 | 681.6 |
| DeepSORT MARS | 174.31 | 18.03 | 6.06 | 13 | 681.4 |
| OCSORT + TIM | 178.88 | 27.14 | 8.69 | 20 | 677.1 |

## Interpretation

DeepSORT MARS did not run faster in this experiment. It produced fewer image and tracking updates over the same real-world interval, which explains why it appears faster in max-frame playback.

OCSORT + TIM maintained nearly the same tracking and selected-target output cadence as raw OCSORT. TIM added `/target_memory` and `/target_memory/status` at approximately 6.98 Hz, close to the raw OCSORT `/target` output rate of 7.03 Hz.

The whole-replay timing results should be interpreted cautiously because they include ROS launch, bag replay, recording, cleanup, analysis, and waiting overhead. They are useful as system-level evidence, not as isolated algorithm profiling.

## Thesis-safe conclusion

The comparison suggests that TIM adds selected-target memory output with limited impact on update cadence and similar peak memory at the replay-system level. DeepSORT MARS should not be described as faster based on the qualitative video, because its apparent speed comes from fewer recorded frames being played at a fixed video frame rate.
