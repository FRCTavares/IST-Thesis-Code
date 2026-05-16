# Hard Re-entry Tracker/TIM Matrix Summary

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw

## Completed runs

| Tracker | TIM mode | Target rule | Main result |
|---|---|---|---|
| SORT | off | fixed/largest variants | Raw selected-ID baseline loses target frequently |
| SORT | on | fixed/largest variants | TIM greatly improves valid target continuity |
| OC-SORT | off | fixed/largest variants | Stronger raw selected-ID baseline |
| OC-SORT | on | fixed/largest variants | Best lightweight result so far |
| ByteTrack | off | fixed/largest variants | Runs complete, but target ID selection needs manual verification |
| ByteTrack | on | fixed/largest variants | Target selection unstable under current largest-ID rule |
| DeepSORT | off | largest / fixed run available | Strong raw selected-ID baseline, but heavy tracker runtime |
| DeepSORT | on | target 1 | TIM closes remaining validity gap, appearance not used |

## Key clean results

### SORT + TIM

- Raw valid duration after selection: 43.856 / 119.845 s
- TIM valid duration after selection: 119.408 / 119.845 s
- TIM p95 latency: 1.2389 ms

### OC-SORT + TIM

- Raw valid duration after selection: 109.971 / 129.721 s
- TIM valid duration after selection: 128.575 / 129.719 s
- TIM p95 latency: 0.9906 ms

### DeepSORT + TIM

- Raw valid duration after selection: 242.337 / 255.117 s
- TIM valid duration after selection: 254.994 / 254.994 s
- TIM p95 latency: 0.9838 ms
- Appearance-used rows: 0
- DeepSORT tracker update times were much heavier, approximately 80-250 ms from logs.

## Interpretation

TIM improves selected-target continuity for both SORT and OC-SORT on the hard re-entry replay.

DeepSORT gives strong continuity, but it is computationally heavy and appearance-heavy, so it is a useful upper/heavy baseline rather than the intended embedded solution.

ByteTrack needs tracker-independent target selection before final comparison. A single numeric target ID, or single-frame largest selection, is not reliable enough across trackers.

## Next step

Generate a report table automatically from `reports/tim_v0/*hard_reentry*tracker*` summaries and add video overlays for the clean runs.
