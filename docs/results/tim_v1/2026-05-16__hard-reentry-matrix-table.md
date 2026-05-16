# Hard Re-entry Tracker/TIM Matrix Table

Bag:

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`

## Useful TIM-on rows

| Tracker | Target rule | Raw valid / total [s] | TIM valid / total [s] | Reacq events | TIM p95 [ms] |
|---|---|---:|---:|---:|---:|
| SORT | target 1 | 43.856 / 119.845 | 119.408 / 119.845 | 15 | 1.239 |
| SORT | largest | 47.824 / 120.279 | 119.749 / 120.278 | 13 | 3.156 |
| OC-SORT | target 1 | 109.971 / 129.721 | 128.575 / 129.719 | 7 | 0.991 |
| OC-SORT | largest | 109.755 / 129.502 | 128.348 / 129.501 | 7 | 1.083 |
| DeepSORT | target 1 | 242.337 / 255.117 | 254.994 / 254.994 | 1 | 0.984 |

## Interpretation

TIM improves selected-target continuity for SORT and OC-SORT on this hard re-entry replay.

OC-SORT + TIM is the best lightweight result so far. It improves the raw selected-ID baseline from 109.971 / 129.721 s to 128.575 / 129.719 s, with TIM p95 latency below 1 ms.

DeepSORT gives the strongest raw selected-ID continuity, but it is computationally heavy. From tracker logs, DeepSORT update times were approximately 80-250 ms, making it a useful heavy baseline rather than the intended embedded solution.

ByteTrack is not included as a clean comparison yet because the current target-selection method is unstable for ByteTrack. It needs either tracker-specific target IDs verified manually, or a more robust stable-largest target-selection rule.

## Current conclusion

For the embedded thesis path, OC-SORT + TIM remains the strongest practical configuration among the lightweight trackers tested here.
