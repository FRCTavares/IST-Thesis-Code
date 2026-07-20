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

The promoted cross-tracker evidence uses:

- canonical TIM-MARS configuration SHA-256
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`;
- MARS model SHA-256
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`;
- clean replay commit
  `1b7dc4002c19e5235703913826e174df1025f1d0`;
- replay metadata schema `3` and resolved-runtime schema `2`;
- image-header-time evaluation with a `0.05 s` step and safety tolerance.

### 6.1 Canonical hard-reentry tracker matrix

| Tracker | Raw C/W/L | TIM-MARS C/W/L | Wrong delta | Absence-output delta | Safety verdict |
|---|---:|---:|---:|---:|---|
| ByteTrack | 0.514 / 0.000 / 0.486 | 0.920 / 0.010 / 0.069 | +0.700 s | +0.000 s | Reject |
| SORT | 0.442 / 0.000 / 0.558 | 0.786 / 0.080 / 0.134 | +5.300 s | +0.150 s | Reject |
| OC-SORT | 0.509 / 0.000 / 0.491 | 0.936 / 0.000 / 0.064 | +0.000 s | +0.200 s | Reject |
| DeepSORT | 0.366 / 0.001 / 0.633 | 0.755 / 0.225 / 0.020 | +15.203 s | +0.000 s | Reject |

The canonical report is:

- `reports/p004_tim_matrix_1b7dc400_2026_07_20/`.

Within-tracker raw-versus-TIM comparisons are valid. Absolute cross-tracker ranking is qualified because each tracker autonomously selected its own physical target.

All four tracker pairings failed promotion with the single canonical preset. Motion-only trackers were not automatically safe, and DeepSORT showed the largest wrong-target increase.

### 6.2 Required OC-SORT crossing and occlusion sequences

| Sequence | Raw C/W/L | OC-SORT + TIM-MARS C/W/L | Correct delta | Wrong delta | Lost delta |
|---|---:|---:|---:|---:|---:|
| Seq03 crossing ambiguity | 0.340 / 0.001 / 0.659 | 0.850 / 0.015 / 0.135 | +48.831 s | +1.350 s | -50.181 s |
| Seq04 occlusion/no-exit | 0.644 / 0.002 / 0.354 | 0.702 / 0.003 / 0.295 | +3.297 s | +0.050 s | -3.347 s |

The repeated deterministic report is:

- `reports/p004_ocsort_tim_1b7dc400_2026_07_20/`.

Seq03 substantially improves availability but exceeds the wrong-target safety tolerance. Seq04 lies exactly at the one-step wrong-target tolerance boundary. Neither sequence increases target-absence valid output.

Both sequence repetitions match in semantic output, authoritative evaluation, configuration and model fingerprints, runtime contract, and clean repository provenance. Corrected event-level aggregates match the authoritative evaluator within `0.004 s`.

Earlier sequence-specific ByteTrack and exploratory multi-tracker results remain useful as historical evidence, but they do not override these promoted canonical safety decisions.

## 7. Claim currently supported

The evidence supports the following bounded claim:

> TIM-MARS is a lightweight selected-target validation layer that can improve correct-target availability in some recoverable tracker-instability cases. Its message-level architecture can be paired with different trackers, but safety is tracker-, sequence-, and configuration-dependent. The current canonical preset is not safety-portable across the evaluated tracker pairings and is not promoted as a universal cross-tracker preset.

The evidence therefore separates two claims:

- interface modularity is established;
- universal safety portability is rejected.

The evidence does not support:

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

### 8.2 Availability gains remain sequence-specific

TIM-MARS can produce large correct-target and LOST-duration improvements, including on OC-SORT Seq03.

Those gains are not sufficient for promotion when wrong-target output also increases. Seq03 improves correct duration by `48.831 s` but adds `1.350 s` of wrong-target output.

The final evaluation must therefore preserve the asymmetric objective: wrong-target degradation blocks promotion even when continuity and aggregate correctness improve.

### 8.3 Architectural modularity does not establish safety portability

TIM-MARS accepts a tracker-independent message contract, but the behaviour of its geometry, continuity, appearance, and recovery logic depends on the candidate trajectories produced by the base tracker.

The canonical P0.4 clean-freeze evidence rejects one-preset portability:

- ByteTrack increases wrong-target output by `0.700 s`;
- SORT increases wrong-target output by `5.300 s` and target-absence valid output by `0.150 s`;
- OC-SORT increases target-absence valid output by `0.200 s` on hard re-entry and wrong-target output by `1.350 s` on Seq03;
- DeepSORT increases wrong-target output by `15.203 s`.

This is not only an appearance-association conflict: the motion-only trackers also show unsafe degradation with the same preset.

The safe thesis boundary is therefore:

- TIM-MARS is modular at the software interface;
- every tracker and configuration pairing requires calibration and held-out safety evaluation;
- only pairings that satisfy the asymmetric wrong-target criterion may be promoted;
- appearance-based association trackers remain outside the current safe layering claim;
- results for DeepSORT must not be generalised to untested StrongSORT, BoT-SORT, or Deep-OC-SORT combinations.

### 8.4 A canonical evidence configuration is frozen, not universal

The P0.4 clean tracker matrix and repeated OC-SORT sequence evidence use one recorded canonical configuration with SHA-256:

- `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`.

This establishes reproducibility for those experiments. It does not establish that the preset is a universal runtime default or is safe for another tracker, sequence, detector, or operating domain.

Tracker-specific calibration remains necessary, and any replacement preset must pass the same held-out wrong-target and target-absence safety criteria.

### 8.5 Current thesis text must follow the current implementation and evidence

The obsolete paper is not an authoritative description of the current
TIM-MARS algorithm and must not constrain implementation or evaluation values.

The repository source of truth is:

- the current TIM-MARS implementation;
- `tim_mars_canonical.yaml`;
- deterministic replay metadata and resolved-runtime fingerprints;
- the promoted clean P0.4 evidence catalogue and reports.

No current thesis source is tracked in this repository. When the final thesis
methodology and result tables are written, they must be derived from these
current sources rather than forced to reproduce the obsolete paper.

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

Before freezing the complete thesis contribution, complete:

1. one final canonical implementation and runtime configuration;
2. final thesis methodology and result tables derived from the canonical implementation and promoted evidence;
3. the remaining annotation and evidence-chain consolidation;
4. geometry-only and appearance ablations;
5. hard-negative ablation;
6. recovery-confirmation ablation;
7. broader identities and held-out sequences;
8. identity-independent spatial evaluation;
9. parameter sensitivity analysis;
10. runtime and onboard resource measurements;
11. explicit failure-case analysis.

The P0.4 clean evidence freeze is complete. It establishes interface modularity, rejects the single-preset safety-portability claim, and defines tracker-specific validation as a design boundary.

## 11. Target contribution statement

A defensible contribution statement is:

> This thesis introduces TIM-MARS, a lightweight selected-target identity validation layer for RGB-only UAV person following. TIM-MARS operates above an existing detector, tracker, and target selector, and combines trusted temporal memory, geometric candidate plausibility, pretrained person appearance evidence, distractor-aware comparison, and conservative publication. Its objective is not generic multi-object tracking accuracy, but reducing unsafe controller-facing wrong-target output under recoverable tracker identity instability.

The layer is modular at the tracker-output interface, but safety is not portable by default. Scientific and deployment claims must remain limited to tracker, configuration, and sequence combinations that pass the asymmetric wrong-target and target-absence criteria.
