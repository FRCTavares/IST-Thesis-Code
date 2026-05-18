# TIM-V2 Offline Design Conclusion

Date: 2026-05-18

## Purpose

This note consolidates the TIM-V2 offline experiments after TIM-V1 hard-crossing and appearance-critical failure analysis.

The main objective is not simply to maximise valid target duration. For UAV control, wrong target output is more dangerous than LOST/UNCERTAIN output.

Therefore, the TIM-V2 design objective is:

> reduce wrong-control duration while preserving enough correct target availability for useful following.

## Bags Used

### Hard re-entry bag

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

Annotation:

`docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv`

### Appearance-critical bag

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Annotation:

`docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

All-scores extraction:

`reports/tim_v2_sources/tim_v1m_appearance_critical_crossing/target_memory_all_scores__tm_extract.csv`

## Main Findings

### 1. Naive hypothesis accumulation failed

Naive TIM-V2A/B/C variants accumulated TIM-V1 candidate scores over time. This did not solve wrong-target duration because the candidate scores are relative to the already-drifted TIM memory.

Once TIM-V1 drifts onto the wrong person, geometry-based candidate scores can reinforce the wrong identity.

Conclusion:

> candidate accumulation over drifted TIM-V1 scores is not sufficient.

### 2. Geometry-only contradiction helps safety, but loses too much target availability

TIM-V2E used frame-level contradiction to suppress control-valid output when identity was contested.

Best practical hard-reentry result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |
| TIM-V2E | 0.574 | 0.247 | 0.179 |

Conclusion:

> contradiction gating reduces wrong-target duration, but can convert too much of the sequence into LOST/UNCERTAIN.

### 3. Geometry-only runner-up recovery helps one bag but does not generalise

TIM-V2F used persistent runner-up evidence.

Hard-reentry result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |
| TIM-V2F | 0.693 | 0.277 | 0.030 |

This is the best result on the first hard-reentry bag.

However, on the TIM-V1M appearance-critical bag, the same fixed policy failed:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2F fixed | 0.422 | 0.351 | 0.227 |

Conclusion:

> geometry-only runner-up recovery is not a robust general TIM-V2 solution.

### 4. Appearance is useful, but additive weighting is weak

TIM-V2G added appearance as an additive score.

Best usable TIM-V1M result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2G | 0.439 | 0.284 | 0.277 |

Appearance improved wrong-target suppression slightly, but not enough.

Conclusion:

> appearance should not be used as a weak additive term only.

### 5. Appearance works better as a gate

TIM-V2H used appearance as a confirmation gate for runner-up switching.

Best usable TIM-V1M result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2H | 0.574 | 0.171 | 0.255 |

TIM-V2I used appearance-confirmed LOST reacquisition.

Best usable TIM-V1M result:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2I | 0.599 | 0.164 | 0.237 |

Conclusion:

> appearance gating is substantially better than additive appearance weighting, but the current HSV cue is still not strong enough for high-correct, low-wrong recovery.

## Appearance Diagnostic

The current HSV cue has useful aggregate separation:

| Signal | Correct candidates | Wrong candidates |
|---|---:|---:|
| appearance_raw mean | 0.641 | 0.275 |
| appearance_raw median | 0.703 | 0.336 |
| geometry mean | 0.602 | 0.337 |
| geometry median | 0.436 | 0.334 |

But frame-level dominance is limited:

| Condition | Frames |
|---|---:|
| correct_app > best_wrong_app | 288 / 844 |
| correct_geom > best_wrong_geom | 263 / 844 |

Conclusion:

> the cue is informative but not reliable enough frame-by-frame.

## Design Direction for TIM-V2J

The next TIM-V2 version should improve the appearance evidence itself.

Recommended TIM-V2J policy:

1. Maintain a frozen pre-occlusion target appearance template.
2. Update this template only during stable LOCKED intervals.
3. Freeze template updates during UNCERTAIN, LOST, and immediately after REACQUIRED.
4. Compare re-entry candidates against the frozen template.
5. Use appearance as a confirmation gate, not as a small additive score.
6. If appearance evidence is unavailable or contradictory, output LOST/UNCERTAIN rather than wrong LOCKED.

## Implementation Implication

Live TIM-V2 should not be implemented yet as a simple hypothesis accumulator.

The next implementation step should be offline TIM-V2J:

- reconstruct candidate crops from `/camera/dashboard` and `/tracks`,
- compute frozen-template HSV similarity offline,
- compare against the current `appearance_raw`,
- test whether frozen-template appearance improves TIM-V1M.

If frozen HSV still fails, the thesis should move to a lightweight learned embedding as the selected-target identity cue.
