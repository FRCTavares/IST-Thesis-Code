# Daily Log - 2026-05-26 - TIM-V2Q margin stabilisation

## Goal

Continue the TIM-V2Q MARS relative-margin investigation on the hard re-entry OC-SORT case.

Main question:

> Can the promising MARS relative-margin result be stabilised so that wrong-target time decreases without creating excessive selected-ID switching?

## Starting point

Previous formal V2Q margin result:

| Output | correct_s | wrong_s | lost_s |
|---|---:|---:|---:|
| Raw | 89.031 | 33.735 | 0.000 |
| V2Q MARS relative margin, margin 0.08 | 103.292 | 19.473 | 5.726 |

Initial interpretation:

- MARS absolute thresholding did not solve the problem.
- Same-run relative MARS similarity was useful.
- The first margin policy reduced wrong-target time, but needed switch-level inspection.

## Work completed

### 1. Added switch analysis tool

Created:

    tools/analysis/analyse_tim_v2q_switches.py

The tool analyses a V2Q timeline and exports:

- selected-ID switches,
- transition counts,
- switches per second,
- selected-ID segments,
- markdown summary.

Output for pure V2Q formal margin 0.08:

    reports/tim_v2q_switch_analysis/formal_m008/

Important correction:

- The formal pure V2Q summary reported 214 switches.
- The exported timeline had 9 actual selected-ID transitions.
- The 214 value should be interpreted as simulator margin events, not actual selected-ID changes.

### 2. Inspected hard re-entry intervals

Focused intervals:

- 73.9 to 86.0 s
- 87.8 to 105.1 s
- 110.4 to 116.5 s

Observation:

- The margin policy made useful corrections in parts of the hard re-entry.
- However, it still accepted unsafe transitions.
- Several dangerous transitions were raw-driven, not MARS-driven.

### 3. Added timeline-level stabiliser probe

Created:

    tools/analysis/simulate_tim_v2q_timeline_stabiliser.py

This tested simple confirmation and cooldown on the already-exported V2Q timeline.

Result:

- Confirmation improved the score slightly.
- It did not remove the dangerous transitions.
- Conclusion: delaying selected-ID changes alone is not enough.

### 4. Patched the real V2Q margin simulator with stable mode

Updated:

    tools/analysis/simulate_tim_v2q_mars_margin_policy.py

Added optional stateful mode:

    --stable
    --confirm-frames
    --raw-switch-margin
    --allow-raw-switch-without-current-sim

Stable-mode idea:

- keep persistent selected ID,
- confirm MARS margin candidates over multiple frames,
- reject raw tracker-ID switches unless similarity evidence supports them,
- optionally allow raw recovery when the current stable ID has no nearby similarity sample.

### 5. Tested strict raw blocking as a negative result

Strict policy:

- rejected raw switches when current stable ID had no nearby similarity sample.

Result:

| Output | correct_s | wrong_s | lost_s | switches |
|---|---:|---:|---:|---:|
| Strict stable probe | 75.398 | 47.367 | 5.726 | 1 |

Interpretation:

- This policy was over-conservative.
- It reduced selected-ID switching, but stayed trapped on a wrong ID.
- This confirms that switch count alone is not the correct objective.

### 6. Ran non-strict stable sweep

Best result:

    reports/tim_v2q_mars_margin_stable_sweep_allow_raw_no_sim/m0p25_confirm5_rawguard0p10_allow_raw_no_sim

Best parameters:

| Parameter | Value |
|---|---:|
| MARS margin | 0.25 |
| confirm frames | 5 |
| raw switch margin | 0.10 |
| min candidate total | 0.30 |
| max similarity dt | 0.50 s |
| allow raw switch without current similarity | true |

Best result:

| Output | correct_s | wrong_s | lost_s | selected-ID switches | score |
|---|---:|---:|---:|---:|---:|
| Raw | 89.031 | 33.735 | 0.000 | n/a | 21.561 |
| Pure V2Q margin 0.08 | 103.292 | 19.473 | 5.726 | 9 | 61.483 |
| Stable V2Q best | 107.699 | 15.066 | 5.726 | 6 | 74.704 |

Score:

    score = correct_s - 2 * wrong_s - 0.5 * lost_s

Best stable policy stats:

| Metric | Value |
|---|---:|
| switches | 6 |
| confirmed MARS margin switches | 2 |
| raw guard switches | 4 |
| raw rejected switches | 210 |

## Interpretation

The best stable V2Q policy is the strongest offline result so far on this hard re-entry sequence.

Main result:

- Wrong-target time decreased from 33.735 s raw to 15.066 s.
- Correct time increased from 89.031 s raw to 107.699 s.
- Compared with pure V2Q margin, wrong-target time also decreased from 19.473 s to 15.066 s.
- Actual selected-ID transitions decreased from 9 to 6.

The result supports the thesis direction:

> Appearance is useful when used as conservative selected-target memory evidence, but it must be combined with state, confirmation, and recovery logic.

## Remaining issue

The best stable policy still has unsafe transitions:

| Transition | Count |
|---|---:|
| correct -> wrong | 4 |
| wrong -> wrong | 2 |

So this is not ready for live TIM integration.

## Next steps

1. Inspect the six remaining selected-ID transitions.
2. Determine why the first confirmed MARS switch changes from correct to wrong.
3. Add candidate-validity constraints combining MARS relative margin with geometry/TIM score consistency.
4. Repeat the sweep after adding the candidate-validity guard.
5. Only adapt to live TIM after offline behaviour is stable across more than one hard sequence.
