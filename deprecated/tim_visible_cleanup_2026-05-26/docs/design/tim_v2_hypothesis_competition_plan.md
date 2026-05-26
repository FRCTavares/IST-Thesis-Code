# TIM-V2 Plan - Hypothesis-Based Selected-Target Memory

Date: 2026-05-16
Scope: thesis TIM improvement after TIM-V1 failure analysis

## 1. Motivation

TIM-V1 improved selected-target continuity compared with raw tracker-ID following, but hard crossing tests showed that valid target output is not enough. TIM can remain valid while following the wrong person.

Hard re-entry OC-SORT correctness result:

| Metric | Raw /target | TIM /target_memory |
|---|---:|---:|
| Correct ratio | 0.500 | 0.680 |
| Wrong ratio | 0.381 | 0.310 |
| Lost ratio | 0.119 | 0.009 |

TIM-V1 reduced lost time strongly, but wrong-target duration remained high. The next improvement must reduce wrong-target duration, not only increase valid target duration.

## 2. TIM-V1 Failure Diagnosis

Manual review and all-score diagnostics showed that during close crossings, the selected person can change tracker ID while the distractor inherits the old geometrically smooth track.

Observed failure pattern:

- selected target starts as ID 1,
- after crossing, the selected person changes to new IDs,
- the distractor becomes or remains ID 1,
- TIM keeps following ID 1 because geometry remains highly confident.

The key failure is not only target loss. The key failure is wrong target confidence.

## 3. Why Simple Fixes Were Not Enough

### Stronger HSV descriptor

A stronger handcrafted HSV descriptor was tested. It did not improve the useful operating point and worsened wrong-target risk in permissive settings.

Decision: rejected as default.

### Three-frame LOST confirmation

A simple confirmation rule requiring the same candidate to pass the LOST threshold for three frames was tested. It did not improve the useful threshold and made permissive settings less safe.

Decision: rejected as default.

### Appearance challenge gate

A first appearance challenge mechanism was added, but it did not activate in the tested configuration.

Observation:

- appearance_challenge_uncertain: 0 rows
- appearance_raw nonzero rows: 1423 / 2804
- appearance_gate_passed rows: 11

Decision: useful diagnostic mechanism, not sufficient alone.

### Appearance update cooldown

A cooldown after reacquisition was added and activated correctly.

Cooldown result:

| Metric | Baseline TIM | Cooldown TIM |
|---|---:|---:|
| Correct ratio | 0.680 | 0.608 |
| Wrong ratio | 0.310 | 0.285 |
| Lost ratio | 0.009 | 0.107 |

Decision: useful safety component, not a complete solution.

## 4. TIM-V2 Core Idea

TIM-V2 should use hypothesis competition.

Current TIM-V1 logic is roughly:

current frame -> best candidate -> accept/reject

TIM-V2 logic should be:

current frame -> candidate scores -> update hypothesis memory -> decide target state

The key question becomes:

Which candidate has behaved most like the selected target over recent frames?

not only:

Which candidate is geometrically closest right now?

## 5. Hypothesis Model

For each candidate track ID j, maintain a hypothesis score:

H_j = accumulated target evidence for candidate j

At each frame:

H_j(t) = decay * H_j(t-1) + evidence_j(t)

Evidence may include:

- geometry score
- detection confidence
- scale consistency
- appearance similarity
- candidate persistence
- ambiguity penalty
- recent distractor penalty

Suggested starting values:

| Parameter | Initial value |
|---|---:|
| hypothesis_decay | 0.85 |
| minimum_persistence_frames | 3 |
| challenger_min_score | 0.45 |
| switch_margin | 0.15 |
| uncertain_margin | 0.10 |
| hypothesis_ttl_frames | 15 |

## 6. State Logic

TIM-V2 should preserve the existing states:

- NO_TARGET
- LOCKED
- UNCERTAIN
- LOST
- REACQUIRED

But transitions should use hypothesis evidence.

### LOCKED

Stay LOCKED only if the current target hypothesis is clearly dominant.

If a challenger is close to the current hypothesis, enter UNCERTAIN instead of confidently outputting the wrong target.

### UNCERTAIN

Use UNCERTAIN when multiple plausible candidates exist.

This is safer than following a possibly wrong person.

### REACQUIRED

Only reacquire when one hypothesis becomes dominant by a margin.

### LOST

Use LOST when no candidate hypothesis is strong enough.

## 7. Appearance Memory Policy

TIM-V2 must avoid learning the wrong person.

Appearance should update only when:

- state is LOCKED,
- current hypothesis dominance is high,
- no strong challenger exists,
- no recent ID switch occurred,
- cooldown is zero.

Do not update appearance during:

- UNCERTAIN,
- LOST,
- REACQUIRED,
- cooldown after ID switch,
- close crossing ambiguity.

## 8. Distractor Memory

TIM-V2 should remember likely distractors briefly.

If a candidate repeatedly competes with the selected target but is rejected or later found wrong, assign a temporary penalty.

This prevents persistent distractors from repeatedly winning due to geometry.

## 9. Offline Simulation First

Before changing live TIM behaviour, implement an offline simulator using:

- target_memory_all_scores.csv
- target_correctness_annotations.csv

Create:

tools/analysis/simulate_tim_hypothesis_policy.py

The simulator should test candidate-hypothesis policies without ROS replay.

Output:

- correct duration
- wrong duration
- lost duration
- correct ratio
- wrong ratio
- lost ratio
- chosen hypothesis timeline
- state timeline

Primary optimisation priority:

1. minimise wrong ratio,
2. maximise correct ratio,
3. minimise lost ratio.

For UAV control, wrong target is worse than lost target.

## 10. TIM-V2 Success Criteria

TIM-V2 should be accepted only if it improves correctness, not just validity.

Current TIM-V1 hard re-entry result:

| Metric | TIM-V1 |
|---|---:|
| Correct ratio | 0.680 |
| Wrong ratio | 0.310 |
| Lost ratio | 0.009 |

TIM-V2 target:

- wrong ratio clearly below 0.310,
- correct ratio equal or higher if possible,
- lost ratio allowed to increase moderately if wrong ratio drops.

Minimum acceptable behaviour:

- wrong ratio decreases substantially,
- correct ratio does not collapse,
- lost ratio remains acceptable.

## 11. Thesis Framing

TIM-V2 should be framed as:

A selected-target hypothesis memory layer for control-safe person following.

Not as generic multi-object tracking.

Generic MOT tries to preserve all identities.
TIM-V2 tries to preserve one selected control target safely.

The novelty is the control-oriented policy:

prioritise wrong-target suppression over always outputting a valid target.

## 12. Implementation Steps

1. Freeze one exact eval bag for development.
2. Use its all-scores CSV and correctness annotation.
3. Implement offline hypothesis simulator.
4. Run parameter sweeps.
5. Compare hypothesis policy against TIM-V1.
6. Integrate into TargetIdentityMemory only if offline results improve wrong ratio.
7. Replay the same frozen eval bag and verify the online implementation matches the offline simulation.

## 13. Definition of Done

TIM-V2 is not done when it produces more valid target output.

TIM-V2 is done when it shows:

- lower wrong-target duration,
- safe behaviour during ambiguity,
- bounded latency,
- repeatability across at least two hard bags.

Required evidence:

- target-correctness table,
- wrong/lost/correct ratios,
- comparison against raw /target,
- comparison against TIM-V1,
- timing overhead,
- qualitative overlay video.
