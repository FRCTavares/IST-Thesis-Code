# TIM-MARS Research Position and Novelty Contract

## 1. Purpose

This file defines what TIM-MARS is intended to contribute, what the current evidence supports, and what must still be demonstrated before making the final thesis claim.

TIM-MARS is a control-facing selected-target identity validation layer for RGB-only UAV person following.

It is not:

- a detector;
- a multi-object tracker;
- a new person ReID network;
- a formal safety guarantee;
- a solution to arbitrary long-term person re-identification.

## 2. Research problem

A multi-object tracker may continue producing plausible tracks while assigning the selected person the wrong identity after:

- crossings;
- occlusion;
- track fragmentation;
- tracker-ID changes;
- disappearance and re-entry;
- interaction with distractors.

For generic tracking, this is an association error.

For UAV person following, a valid-looking wrong target may produce a command toward the wrong person.

The selected-target objective is therefore asymmetric:

1. minimise wrong-target publication;
2. retain correct-target publication;
3. accept temporary loss when identity evidence is insufficient.

The central safety principle is:

> A temporarily lost target is preferable to a confidently published wrong target.

A conceptual control-oriented loss is:

    J = C_wrong T_wrong + C_lost T_lost + C_switch N_switch

subject to:

    C_wrong > C_lost

This expresses the safety ordering. The coefficients must not be presented as universal constants unless experimentally justified.

## 3. Research gap

Detectors and multi-object trackers maintain observations and identities for all candidates.

They do not directly certify that one operator-selected person remains safe to publish to a controller.

A tracker ID is an association label, not an identity guarantee.

TIM-MARS addresses the narrower problem of deciding whether one selected target is sufficiently trusted for controller-facing publication.

## 4. Intended contribution

The strongest defensible contribution is the combination of the following ideas into a selected-target safety layer.

### 4.1 Modular selected-target validation

TIM-MARS is placed after:

1. person detection;
2. multi-object tracking;
3. raw target selection.

It separates tracker association from controller-facing identity validation.

### 4.2 Persistent selected-target memory

TIM-MARS keeps memory of the selected person across tracker instability using:

- the last trusted tracker ID;
- trusted target geometry;
- target quality;
- temporal state;
- positive appearance evidence;
- optional distractor evidence.

### 4.3 Conservative publication

TIM-MARS may suppress output even when the tracker provides plausible candidates.

Only a trusted `LOCKED` target should be considered controller-valid.

`UNCERTAIN`, `LOST`, and `REACQUIRED` represent states where publication is suppressed or confirmation is still required.

### 4.4 Appearance-supported identity validation

A pretrained MARS-small128 model provides appearance evidence.

The novelty is not MARS itself.

The intended contribution is how pretrained appearance evidence is combined with geometry, temporal memory, distractor evidence, and conservative publication for one selected target.

### 4.5 Distractor-aware identity evidence

TIM-MARS can compare a candidate against:

- positive selected-target appearance memory;
- hard-negative or distractor appearance memory.

The intended acceptance condition is not merely that a candidate resembles the target, but that it resembles the target more strongly than plausible distractors.

### 4.6 Selected-target safety evaluation

TIM-MARS is evaluated using control-facing metrics:

- correct-target duration;
- wrong-target duration;
- lost-target duration;
- target-absent-but-output duration;
- reacquisition delay;
- unsafe handover count;
- event-specific performance.

This is different from reporting only generic MOT metrics.

## 5. Minimal defensible final algorithm

The final thesis algorithm should contain only:

1. trusted target memory;
2. geometric candidate plausibility;
3. positive appearance similarity;
4. distractor-aware appearance margin;
5. temporal recovery confirmation;
6. one unified final safety gate;
7. conservative state transition and publication;
8. trusted-only memory updates.

Parallel recovery paths and unevaluated experimental policies should not remain part of the final algorithm claim.

## 6. Current evidence

The promoted repository evidence currently shows:

| Sequence | Raw ByteTrack C/W/L | ByteTrack + TIM-MARS C/W/L | Interpretation |
|---|---:|---:|---|
| Clean visible | 1.000 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 | No degradation |
| May hard re-entry | 0.708 / 0.138 / 0.154 | 0.943 / 0.024 / 0.034 | Strong improvement after corrected ID-handover annotation |
| Crossing ambiguity | 0.553 / 0.002 / 0.445 | 0.546 / 0.002 / 0.452 | No meaningful improvement |
| Occlusion/no-exit | 0.381 / 0.182 / 0.438 | 0.381 / 0.181 / 0.439 | No meaningful improvement |

The earlier May result set of `0.728 / 0.118 / 0.154` for raw ByteTrack and `0.963 / 0.003 / 0.034` for TIM-MARS was generated before correction of the target-ID handover boundary.

Commit `6a4ef843` moved the annotated ID transition from 48.800 s to 50.233 s. The canonical post-correction report is:

- raw ByteTrack: 0.708 / 0.138 / 0.154;
- ByteTrack + TIM-MARS: 0.943 / 0.024 / 0.034.

The obsolete pre-correction report remains only for provenance and must not be quoted as final.

The sequence audit also reports:

- DeepSORT selected-ID raw: wrong ratio 0.028;
- DeepSORT + TIM-MARS: wrong ratio 0.466.

Therefore TIM-MARS is not currently tracker-independent in demonstrated safety. Under at least one evaluated configuration, it makes the selected-target output substantially less safe.

## 7. Claim currently supported

The evidence currently supports only the following narrow claim:

> TIM-MARS can substantially improve selected-target correctness in some recoverable ByteTrack identity-switch and re-entry cases while preserving clean tracking.

The evidence does not currently support:

> TIM-MARS generally improves selected-person tracking across trackers, crossings, occlusions, disappearance, and re-entry.

## 8. Novelty fragilities

### 8.1 Combination may be viewed as incremental

The individual components are established:

- geometric consistency;
- tracker-ID continuity;
- cosine similarity;
- person ReID;
- state machines;
- temporal confirmation;
- hard-negative memory.

The thesis must demonstrate that the control-facing problem formulation, asymmetric objective, unified policy, and measured safety benefit form a meaningful contribution.

### 8.2 Current gain is sequence-specific

The strongest improvement is concentrated in one May re-entry sequence.

The June crossing and occlusion sequences show neutral behaviour.

### 8.3 Tracker dependence is unresolved

The DeepSORT result shows that TIM-MARS can be unsafe when its assumptions do not match the base tracker.

The final method must either:

- work safely across supported trackers;
- use tracker-specific calibrated presets;
- or clearly limit its claim to the validated tracker configuration.

### 8.4 Configuration is not frozen

Current defaults and runners use incompatible values:

- appearance conservative margin: 0.25, 0.15, 0.10, and 0.05;
- hard-negative rejection margin: 0.08 and 0.03;
- replay default preset: `legacy`;
- ROS runtime defaults: balanced conservative settings.

Until one canonical configuration is frozen, results cannot be assumed to describe the same algorithm.

### 8.5 Paper, code, and runner equivalence is not established

The paper describes a clean ordered algorithm.

The implementation contains several parallel decision paths, including rank-aware reacquisition, short-gap protection, absence recovery, candidate belief, and conservative rejection inside acceptance.

The final thesis must prove that:

- the written algorithm;
- the implementation;
- the launcher configuration;
- and the evaluated replay

all represent the same method.

### 8.6 Appearance evidence is fragile

Current limitations include:

- latest-image rather than exact timestamp synchronization;
- appearance cache indexed only by tracker ID;
- stale cached embeddings;
- no strong crop-quality validation;
- possible positive-memory drift;
- possible hard-negative contamination.

### 8.7 Evaluation remains partly ID-dependent

The primary evaluator depends on tracker IDs matching manual annotations.

The bbox evaluator is spatial, but still uses annotated tracker IDs to locate the reference target box in `/tracks`.

A genuinely identity-independent reference is still required for robust full-pipeline reruns.

## 9. Non-claims

TIM-MARS does not claim to:

- recover a person when no correct candidate exists;
- solve arbitrary long absences;
- distinguish identical-looking people in all conditions;
- improve every tracker;
- improve generic MOT performance;
- eliminate all wrong-target publication;
- provide formal safety guarantees;
- generalise beyond evaluated people, scenes, and hardware.

## 10. Evidence required for the final thesis claim

Before freezing the thesis contribution, complete:

1. one canonical implementation and configuration;
2. paper-code-runner equivalence verification;
3. correction of the May result inconsistency;
4. investigation of the unsafe DeepSORT result;
5. geometry-only and appearance ablations;
6. hard-negative ablation;
7. recovery-confirmation ablation;
8. multiple identities and sequences;
9. identity-independent spatial evaluation;
10. parameter sensitivity analysis;
11. runtime and onboard resource measurements;
12. explicit failure-case analysis.

## 11. Target contribution statement

A defensible final contribution statement is:

> This thesis introduces TIM-MARS, a lightweight selected-target identity validation layer for RGB-only UAV person following. TIM-MARS operates above an existing detector, tracker, and target selector, and combines trusted temporal memory, geometric candidate plausibility, pretrained person appearance evidence, distractor-aware comparison, and conservative publication. Its objective is not generic multi-object tracking accuracy, but reducing unsafe controller-facing wrong-target output under recoverable tracker identity instability.
