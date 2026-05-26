# Novelty Plan: Target Identity Memory with Lightweight Latent Target State

Date: 2026-05-06  
Owner: Thesis development  
Working title: **Latency-Bounded Selected-Target Perception for RGB-Only Micro-UAV Following**

---

## 1. Thesis Objective

Develop a latency-bounded onboard RGB-only perception system that allows a micro-UAV to follow one selected person under embedded compute constraints.

The UAV may use Pixhawk GPS/IMU for vehicle state and pilot-supervised control, but target detection, identity maintenance, uncertainty handling, and reacquisition are handled using onboard RGB perception.

The system should not expose raw tracker IDs directly to control. It should expose a validated selected-target state with explicit confidence, freshness, and control-validity flags.

---

## 2. Core Problem

This is not generic multi-object tracking.

Generic MOT:

> Maintain all visible identities as consistently as possible.

This thesis:

> Maintain one selected person as a reliable control target under detector noise, occlusion, ID switches, small target size, and bounded onboard latency.

The controller does not need every person to be tracked perfectly. It needs the selected target to be represented as a stable and safe control reference.

Therefore, the central problem is:

> How can noisy detector and tracker outputs be converted into a stable, control-valid selected-target state on Raspberry Pi 5 + Hailo-class hardware?

---

## 3. Current Evidence and Motivation

Current system evidence:

- Hailo enables fast onboard person detection.
- Simple trackers work well when detections are clean.
- Real detections create missed frames, localisation jitter, ID switches, and fragmentation.
- Larger detectors improve recall but can violate the onboard latency budget.
- Deep appearance trackers are heavier and are not ideal as always-on modules for a micro-UAV.

Conclusion:

> The main problem is temporal instability under detector-limited, latency-bounded conditions, not detection accuracy alone.

This motivates a lightweight temporal memory layer above the tracker.

---

## 4. Primary Novelty

### Target Identity Memory with Lightweight Latent Target State

The proposed contribution is a selected-target memory layer placed above detector and tracker outputs.

It maintains the selected person as a compact temporal state using:

- geometry: bbox position, IoU, centre distance
- motion: predicted target location and velocity
- scale: bbox height, area, relative size consistency
- detector evidence: confidence and visibility
- temporal evidence: age, last seen, missing-frame count
- optional latent appearance: compact learned target descriptor
- uncertainty: ambiguity and control-validity state

This layer is called:

> **Target Identity Memory (TIM)**

The improved version introduces:

> **Lightweight Latent Target State**

This does not model the entire UAV world. It models only the selected target.

---

## 5. Key Thesis Distinction

The work should not be framed as a full latent world model.

Full latent world model:

```text
UAV video + actions + instructions
    -> global latent world state
    -> future waypoints or actions
```

This thesis:

```text
detections + tracks + selected target history
    -> target identity memory
    -> validated target state for control
```

The proposed latent component is target-centric, lightweight, and event-aware.

It is not designed to understand the whole scene. It is designed to answer:

> Is this candidate still the selected person, and is it safe to use for control?

---

## 6. System-Level Positioning

Baseline tracking-by-detection pipeline:

```text
RGB camera
    -> Hailo person detector
    -> online tracker
    -> raw tracks
```

Proposed selected-target pipeline:

```text
RGB camera
    -> Hailo person detector
    -> online tracker
    -> Target Identity Memory
    -> control-valid target state
    -> MAVROS control reference
```

The important interface is not `/tracks` alone. The important interface is `/target`, containing a validated target state.

---

## 7. Target Memory State

For the selected target, maintain:

```text
m_t = {
    target_id,
    bbox,
    bbox_cx,
    bbox_cy,
    bbox_h,
    bbox_area,
    velocity,
    predicted_bbox,
    score,
    visual_latent,
    uncertainty,
    last_seen,
    missing_count,
    state,
    control_valid
}
```

Where:

```text
visual_latent = E(crop_t)
```

`E(.)` is a lightweight encoder applied to the selected target crop or to selected candidate crops when needed.

The latent vector should be small:

```text
visual_latent dimension: 8D to 32D
```

Preferred first implementation target:

```text
16D latent descriptor
```

---

## 8. TIM State Machine

TIM maintains explicit states:

```text
NO_TARGET
LOCKED
UNCERTAIN
LOST
REACQUIRED
```

### State meanings

| State | Meaning | Control behaviour |
|---|---|---|
| NO_TARGET | No selected target exists | No target-following command |
| LOCKED | Target evidence is strong and unambiguous | Normal control |
| UNCERTAIN | Target evidence is weak or ambiguous | Slow control or yaw-only control |
| LOST | Target is not reliable enough for control | Hover or hold attitude |
| REACQUIRED | Candidate target has been recovered after loss | Confirm before normal control |

### Priority rule

```text
operator command > target memory > tracker ID
```

Operator actions always override automatic reacquisition.

---

## 9. Core Matching Score

For each candidate track or detection `j`, compute a target-consistency score:

```text
S_j =
    w_iou    S_iou(j)
  + w_dist   S_dist(j)
  + w_scale  S_scale(j)
  + w_conf   S_conf(j)
  + w_latent S_latent(j)
  - w_amb    S_amb(j)
```

Where:

- `S_iou`: overlap with predicted target box
- `S_dist`: centre distance consistency
- `S_scale`: bbox height or area consistency
- `S_conf`: detector or track confidence
- `S_latent`: similarity between candidate latent and target memory latent
- `S_amb`: ambiguity penalty when multiple candidates are plausible

Accept candidate:

```text
j* = argmax_j S_j
```

Only accept if:

```text
S_j* >= tau_accept
```

and ambiguity is low:

```text
S_j* - S_second >= tau_margin
```

If the score is acceptable but the margin is small, enter `UNCERTAIN` rather than `LOCKED`.

---

## 10. Deterministic TIM-V0

TIM-V0 is the first implementation and should not depend on learned latent features.

Inputs:

- tracker output bbox
- confidence
- track age
- last seen
- predicted bbox
- geometric consistency

Cues:

- IoU
- centre distance
- scale similarity
- confidence
- missing-frame count
- ambiguity penalty

Purpose:

- provide a safe baseline
- prove that selected-target memory improves over raw tracker ID usage
- establish state machine, thresholds, logging, and metrics

Expected benefit:

- fewer target switches
- smoother target validity
- safer control transitions
- better short-gap handling

TIM-V0 is required before implementing latent memory.

---

## 11. Latent TIM-V1

TIM-V1 adds a lightweight learned latent target descriptor.

### Core idea

Instead of relying only on geometry and tracker ID, TIM stores a compact visual representation of the selected target:

```text
target crop -> tiny encoder -> latent descriptor z_t
```

The memory is updated only when the target is reliable:

```text
update latent memory only in LOCKED state
```

Do not update the latent memory in:

```text
UNCERTAIN
LOST
REACQUIRED confirmation period
```

This prevents model drift after occlusion or identity confusion.

### Candidate use cases

Use latent matching mainly when:

- two candidates have similar geometric score
- tracker ID changes unexpectedly
- the target disappears and reappears
- target is temporarily occluded
- people cross paths
- detector confidence is low but motion prediction remains plausible

This avoids full DeepSORT-style always-on re-identification.

---

## 12. Possible Latent Encoder Designs

### Option A: Handcrafted-first embedding baseline

Before training a CNN, use a very cheap baseline:

- colour histogram in target crop
- aspect ratio and scale features
- simple texture or gradient statistics

Purpose:

- establish whether appearance helps at all
- create a non-learned comparison point
- reduce implementation risk

### Option B: Tiny learned crop encoder

A small CNN encodes the selected target crop into a compact descriptor.

Input:

```text
64x32 or 96x48 RGB target crop
```

Output:

```text
8D to 32D L2-normalised descriptor
```

Training options:

- contrastive learning on tracklets
- positive pairs from same ground-truth identity across nearby frames
- negative pairs from different people in the same or nearby frames
- optional augmentation with blur, brightness, scale changes, and crop jitter

Loss options:

```text
contrastive loss
triplet loss
supervised identity classification + descriptor extraction
```

Preferred simple first option:

```text
supervised or pseudo-supervised contrastive training on VisDrone-style tracklets
```

### Option C: Temporal latent predictor

A more advanced extension predicts the next target latent:

```text
z_{t+1} = f(z_t, motion_t, bbox_t)
```

This should be treated as a stretch goal only.

The core thesis does not require a full temporal latent predictor. It only requires a useful target descriptor and memory update policy.

---

## 13. Relationship to ROI Re-Detection

The original idea was:

```text
target is small or uncertain
    -> crop predicted region
    -> resize crop
    -> rerun detector
    -> recover target bbox
```

This remains useful, but it should not be the primary novelty.

In the improved plan, ROI re-detection becomes TIM-V2:

```text
TIM uncertainty high
or target predicted small
or detector confidence falling
or target close to LOST
    -> trigger selective ROI re-detection
```

The novelty is not simply cropping. The novelty is using target memory and uncertainty to decide when extra computation is justified.

---

## 14. Selective ROI Re-Detection TIM-V2

### Trigger conditions

Trigger ROI refinement when one or more conditions are true:

- selected target bbox height below threshold, for example `< 20 px`
- target confidence below threshold
- TIM state is `UNCERTAIN`
- target has been missing for `N` frames but predicted location remains plausible
- ambiguity score is high
- candidate score is close to threshold

### Method

```text
predict target region
    -> crop ROI around predicted bbox
    -> expand crop by safety margin
    -> resize to detector input
    -> run detector or refine head
    -> map detections back to full image coordinates
    -> update TIM candidate scoring
```

### Bounded compute policy

ROI refinement must be bounded:

```text
max ROI calls per second
max consecutive ROI calls
skip ROI if detector queue is under pressure
skip ROI if latency p95 exceeds budget
```

### Metrics

Report:

- refine trigger rate
- added latency
- recovered targets after missed full-frame detection
- small-person recall by bbox height bin
- target lock duration with and without ROI refinement

---

## 15. Control Validity Policy

The controller should consume target validity, not raw tracks.

Suggested policy:

```text
LOCKED
    -> normal yaw + forward + optional lateral control

UNCERTAIN
    -> reduced-gain control, yaw-only control, or hold forward velocity

LOST
    -> hover or hold attitude

REACQUIRED
    -> confirm for K frames before normal control

NO_TARGET
    -> no target-following command
```

Control should use:

```text
ex = cx - 0.5
ey = cy - 0.5
range_proxy = bbox_height or bbox_area
control_valid
state
confidence
last_seen
```

The thesis should emphasise that the perception layer produces a safe control interface, not just detections.

---

## 16. Difference from DeepSORT and Standard ReID Trackers

DeepSORT-style approach:

- maintain appearance for all tracks
- run ReID frequently
- optimise generic MOT identity consistency
- can be too heavy for the target embedded setup

Proposed TIM approach:

- maintain memory for one selected target
- use appearance only when useful
- update memory only when target is reliable
- expose explicit control-validity states
- prioritise bounded latency over global MOT score
- optimise selected-target continuity, not all-object identity

This difference is central to the novelty.

---

## 17. Compute Split

Hailo:

- full-frame detector
- optional ROI detector if supported and bounded

Raspberry Pi 5 CPU:

- tracker
- TIM state machine
- candidate scoring
- uncertainty logic
- latent memory update if encoder is cheap enough
- control validity policy
- logging and metrics

Possible future deployment:

- move latent encoder to Hailo only if CPU overhead becomes too high

---

## 18. Research Questions

### RQ1: Selected-target stability

Does TIM reduce selected-target ID switches compared with raw tracker ID following?

### RQ2: Control-valid continuity

Does TIM increase the time during which the target is valid for control?

### RQ3: Reacquisition

Does TIM reduce time-to-reacquire after short occlusion or detector dropout?

### RQ4: Latent appearance contribution

Does a lightweight latent target descriptor improve ambiguous association without breaking the latency budget?

### RQ5: Selective refinement

Does TIM-triggered ROI re-detection improve small-target recovery more efficiently than always increasing full-frame detector resolution?

### RQ6: Latency boundedness

Can the complete system maintain required FPS and p95 latency while adding TIM, latent matching, and selective refinement?

---

## 19. Evaluation Metrics

### Selected-target identity metrics

- selected-target ID switches
- wrong-lock events
- identity recovery success rate
- ambiguity events resolved correctly

### Continuity metrics

- lock duration
- valid target time percentage
- number of LOST transitions
- fragmentation of selected-target state
- LOCKED / UNCERTAIN / LOST / REACQUIRED time distribution

### Reacquisition metrics

- time-to-reacquire after occlusion
- reacquisition success rate
- false reacquisition rate
- frames until confirmation after REACQUIRED

### Detection and tracking metrics

- person precision and recall
- recall by bbox height bin
- IDF1
- ID switches
- fragmentation

### Control-relevant metrics

- image-space centre error mean and variance
- target bbox height or area stability
- command smoothness
- unsafe command suppression during target loss
- percentage of time with valid target reference

### System metrics

- FPS
- end-to-end latency mean, p50, p95, p99
- TIM compute overhead
- latent encoder overhead
- ROI trigger rate
- ROI added latency
- queue pressure and dropped-frame behaviour

---

## 20. Implementation Roadmap

### Phase 1: Baseline preservation

Goal:

- preserve current detector + tracker live stack
- ensure repeatable logging and timing analysis

Deliverables:

- stable live runs
- baseline bags
- baseline timing report
- baseline tracker behaviour report

### Phase 2: TIM-V0 deterministic memory

Goal:

- implement selected-target memory without learning

Deliverables:

- `target_memory.py`
- `target_memory_node.py`
- state machine
- candidate scoring
- target validity output
- synthetic tests
- live dashboard visibility

### Phase 3: TIM-V0 evaluation

Goal:

- prove memory improves over raw tracker ID following

Deliverables:

- selected-target switch metrics
- lock duration metrics
- reacquisition metrics
- latency overhead report

### Phase 4: TIM-V1 latent target memory

Goal:

- add lightweight target appearance descriptor

Deliverables:

- crop extraction pipeline
- tiny encoder or handcrafted descriptor baseline
- latent update policy
- ambiguity-triggered latent matching
- overhead analysis

### Phase 5: TIM-V1 evaluation

Goal:

- prove latent memory helps in ambiguous scenarios

Deliverables:

- crossing-person tests
- occlusion tests
- identity-switch comparisons
- ablation: TIM-V0 vs TIM-V1

### Phase 6: TIM-V2 selective ROI re-detection

Goal:

- improve small/far target recovery under bounded compute

Deliverables:

- ROI trigger logic
- ROI detector/refine path
- full-image coordinate remapping
- ablation: no ROI vs ROI
- small-person recall analysis

### Phase 7: Control coupling and flight validation

Goal:

- validate perception output as a control reference

Deliverables:

- control-valid target state
- pilot-supervised flight logs
- image error analysis
- latency and continuity results
- final thesis figures and tables

---

## 21. Implementation Files

Suggested files:

```text
docs/design/selected_target_memory.md
docs/design/latent_target_memory.md
docs/design/roi_refine_policy.md

ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py
ros2_ws/src/thesis_bringup/thesis_bringup/target_memory_node.py
ros2_ws/src/thesis_bringup/thesis_bringup/latent_target_encoder.py
ros2_ws/src/thesis_bringup/thesis_bringup/roi_refine.py

tools/analysis/evaluate_selected_target_memory.py
tools/analysis/evaluate_reacquisition.py
tools/analysis/evaluate_target_lock.py

tests/test_target_memory_synthetic.py
tests/test_target_state_machine.py
tests/test_latent_update_policy.py
tests/test_roi_refine_mapping.py
```

---

## 22. ROS Interfaces

### Input topics

```text
/detections
/tracks
/timing
/camera/fps
```

### Output topics

```text
/target
/timing_target
/target_memory/debug
/target_memory/state
```

### Target output should include

```text
target_track_id
target_bbox_cx
target_bbox_cy
target_bbox_w
target_bbox_h
target_score
target_visible
target_state
control_valid
reacquired
last_seen_ms
uncertainty
candidate_margin
```

---

## 23. Minimum Proof Required

The thesis should show at least five clear results:

1. Raw tracker ID following fails in selected-target scenarios.
2. TIM-V0 improves selected-target continuity and reduces unsafe target switching.
3. TIM-V1 latent target memory improves ambiguous association or reacquisition cases.
4. TIM-V2 selective ROI re-detection improves small/far target recovery when triggered by uncertainty.
5. The full system remains latency-bounded on the target onboard hardware.

Without result 5, the contribution is not suitable for the micro-UAV setting.

---

## 24. Risk Management

### Risk 1: Latent encoder is too heavy

Mitigation:

- use only selected target crop
- trigger only during ambiguity
- start with handcrafted descriptor baseline
- keep descriptor dimension small
- move encoder to Hailo only if necessary

### Risk 2: Latent memory drifts to the wrong person

Mitigation:

- update only in LOCKED state
- freeze in UNCERTAIN and LOST
- require multi-frame confirmation after reacquisition
- use ambiguity margin threshold

### Risk 3: ROI refinement adds unstable latency

Mitigation:

- hard trigger budget
- skip under queue pressure
- report p95 and p99 latency
- compare against no-ROI baseline

### Risk 4: Not enough labelled flight data

Mitigation:

- use synthetic controlled tests
- annotate small selected subsets
- use VisDrone-style offline evaluation
- focus on selected-target events, not exhaustive full-scene MOT annotation

### Risk 5: Contribution becomes too broad

Mitigation:

- do not claim full UAV world modelling
- focus on selected target memory
- evaluate target continuity and control validity
- keep latent module lightweight and task-specific

---

## 25. Final Thesis Positioning

The final contribution should be framed as:

> A latency-bounded selected-target perception layer for RGB-only micro-UAV following. The system converts noisy detector and tracker outputs into a stable, control-valid target state using deterministic temporal memory, lightweight latent target appearance, and uncertainty-triggered ROI refinement.

This is not a generic MOT system and not a full latent world model.

It is a practical embedded perception method for maintaining one selected person as a safe control target under real onboard constraints.
