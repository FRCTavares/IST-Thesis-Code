# TIM-V2Q MARS margin probe, hard re-entry

## Purpose

Test whether the existing DeepSORT MARS ReID descriptor can improve TIM when used with a relative-margin policy instead of the V2H absolute-threshold policy.

## Key idea

V2H uses absolute similarity thresholds. This was ineffective for MARS because both target and distractor often have positive similarity.

V2Q instead compares candidates relatively:

```text
if candidate_sim - current_selected_sim >= margin:
    allow candidate switch or reacquisition
```

## Inputs

- Scores: `reports/tim_v0/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/target_memory_all_scores.csv`
- MARS similarity: `reports/tim_v2p_mars_reid/hard_reviewed_online_memory/all_similarity_scores.csv`
- Base timeline: `reports/tim_v2p_mars_reid/hard_reviewed_online_memory/v2h_policy/timeline.csv`

## Best probe result

Best conservative margin: 0.08

| Method | Correct s | Wrong s | Lost s |
|---|---:|---:|---:|
| Probe raw baseline | 89.031 | 33.735 | 0.000 |
| V2Q MARS margin 0.08 | 103.292 | 19.473 | 5.726 |

Relative change:

- Correct time: +14.261 s
- Wrong-target time: -14.262 s
- Lost time: +5.726 s

## Margin sweep

| Margin | Switches | Correct s | Wrong s | Lost s |
|---:|---:|---:|---:|---:|
| 0.05 | 214 | 103.292 | 19.473 | 5.726 |
| 0.08 | 214 | 103.292 | 19.473 | 5.726 |
| 0.10 | 210 | 102.707 | 20.058 | 5.726 |
| 0.12 | 199 | 101.562 | 21.203 | 5.726 |
| 0.15 | 182 | 100.590 | 22.175 | 5.726 |
| 0.18 | 161 | 98.642 | 24.123 | 5.726 |
| 0.20 | 146 | 97.844 | 24.921 | 5.726 |
| 0.25 | 64 | 91.187 | 31.578 | 5.726 |
| 0.30 | 25 | 89.232 | 33.534 | 5.726 |

## Interpretation

The MARS descriptor contains useful same-run relative identity signal in the hard-reentry failure window. The previous V2H threshold policy failed because it used absolute thresholds, not candidate-vs-current margins.

V2Q is promising as a policy-design result, but the current numbers come from a quick probe accumulator. They should not be mixed directly with the official V2H simulator metrics until V2Q is converted into a proper saved simulator.

## Next action

Convert the V2Q margin logic into a permanent analysis script, then rerun the selected margin 0.08 with a formal report.
