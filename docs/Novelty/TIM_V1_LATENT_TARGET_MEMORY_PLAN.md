# TIM-V1 Plan: Lightweight Latent Target Memory

Date: 2026-05-06  
Project: RGB-only selected-target perception for micro-UAV following  
Status: Design plan before implementation

---

## 1. Objective

TIM-V1 extends TIM-V0 with a lightweight target-only latent appearance cue.

The goal is not to build a full UAV latent world model, a generic ReID tracker, or a DeepSORT replacement.

The goal is narrower:

> improve selected-target reacquisition and ambiguity handling when TIM-V0 geometry is weak.

TIM-V1 keeps the thesis focus:

> maintain one operator-selected person as a control-valid target under noisy detections, short occlusions, missed frames, and tracker ID reassignment.

---

## 2. Motivation from TIM-V0

TIM-V0 showed that a deterministic geometric memory layer can:

- run live onboard with negligible latency
- expose control-valid states
- recover from injected tracker ID reassignment
- provide interpretable failure modes

The main V0 limitation is geometric weakness after loss.

The threshold sweep showed:

| accept_score_lost | reacquired |
|---:|---:|
| 0.35 | 15/15 |
| 0.38 | 15/15 |
| 0.40 | 15/15 |
| 0.42 | 14/15 |
| 0.45 | 13/15 |
| 0.50 | 13/15 |
| 0.60 | 13/15 |

Interpretation:

- lower thresholds improve recovery
- higher thresholds are safer but reject weak candidates
- TIM-V1 should add an extra cue instead of simply lowering thresholds

Main question:

> can a lightweight latent target cue recover weak geometric cases without blindly accepting low-score matches?

---

## 3. Core Idea

TIM-V1 maintains a compact visual memory of the selected target.

Conceptual flow:

- selected target crop
- lightweight feature encoder
- compact latent vector `z_t`
- target memory `z_mem`
- candidate comparison during ambiguity or loss

Candidate matching then adds one extra term:

`S_j = S_V0 + w_lat S_lat`

where:

`S_lat = cosine_similarity(z_mem, z_j)`

The first implementation should use L2-normalised vectors and cosine similarity.

---

## 4. What TIM-V1 Is Not

TIM-V1 is not:

- a full latent world model
- a language-conditioned UAV navigation model
- a global multi-object ReID system
- a full DeepSORT-style always-on appearance tracker
- a detector retraining method
- a pixel-space reconstruction model
- a planner

The contribution remains:

> a latency-bounded selected-target perception layer for RGB-only micro-UAV following.

---

## 5. Pipeline Position

TIM-V1 stays above tracker outputs and before control-valid target publication.

Pipeline:

- `/camera/image_raw`
- `perception_pipeline_node`
- `/detections`
- `tracker_node`
- `/tracks`
- `target_memory_node`
- TIM-V0 geometric score
- TIM-V1 latent target score
- `/target_memory`
- `/target_memory/status`

The latent cue is internal to the target memory layer.

---

## 6. Inputs and Outputs

Inputs:

- current image frame or dashboard image
- candidate tracks from `/tracks`
- selected target memory
- current TIM state
- candidate bounding boxes

Internal target memory:

- `z_mem`: latent target memory
- `z_last`: most recent trusted latent vector
- `age`: frames since update
- `quality`: memory confidence

Candidate data:

- `z_j`: candidate latent vector
- `S_lat_j`: latent similarity to target memory

Diagnostics to expose later in `/target_memory/status`:

- `latent_score`
- `latent_used`
- `latent_memory_quality`
- `latent_update_reason`

---

## 7. Score Extension

TIM-V0 score:

`S_j = w_iou S_iou + w_dist S_dist + w_scale S_scale + w_conf S_conf + w_id S_id - w_amb S_amb`

TIM-V1 score:

`S_j = w_iou S_iou + w_dist S_dist + w_scale S_scale + w_conf S_conf + w_id S_id + w_lat S_lat - w_amb S_amb`

Initial rule:

- use latent score only when useful
- do not let latent score override very poor geometry alone
- log when latent score changes the selected candidate

---

## 8. Memory Update Policy

The update policy is critical.

### LOCKED

Use and update latent memory slowly.

Update form:

`z_mem <- (1 - alpha) z_mem + alpha z_j`

Suggested `alpha`:

- `0.05` to `0.20`

Update only if:

- candidate is accepted
- match is not ambiguous
- bbox is large enough
- confidence is acceptable
- TIM state is stable

### UNCERTAIN

Use latent memory for matching.

Do not update it.

Reason:

> avoid corrupting memory with a wrong candidate.

### LOST

Use latent memory for reacquisition.

Do not update it.

Reason:

> memory must stay anchored to the last trusted target.

### REACQUIRED

Do not immediately trust the new latent vector.

Only resume updates after confirmation over a few stable frames.

### NO_TARGET

No latent memory exists.

---

## 9. When to Run the Encoder

TIM-V1 must remain latency-bounded.

Do not run appearance for every object all the time.

Recommended trigger policy:

- update selected target feature when `LOCKED`
- compute candidate features when state is `UNCERTAIN`
- compute candidate features when state is `LOST`
- compute candidate features when geometric score is close to threshold
- compute candidate features when ambiguity is detected

This keeps TIM-V1 different from DeepSORT.

---

## 10. Feature Options

### V1-A: colour or texture feature baseline

Use:

- HSV histogram
- optional upper/lower body split
- L2 normalisation

Pros:

- no training
- very fast
- useful first baseline

Cons:

- weak under lighting changes
- weak for tiny targets
- not a learned latent embedding

### V1-B: tiny learned embedding

Use:

- target crop
- resize to `64x128` or `96x192`
- tiny CNN
- 8D or 16D vector

Pros:

- closer to latent target memory
- better thesis novelty
- still lightweight if designed carefully

Cons:

- needs training or adaptation
- must be measured carefully on Pi 5

Recommended path:

1. implement V1-A first
2. validate integration and timing
3. then attempt V1-B

---

## 11. Training Direction for Learned Embedding

The learned embedding does not need to solve global person ReID.

It only needs to answer:

> is this candidate visually consistent with the selected target memory?

Possible data:

- VisDrone MOT crops
- own recorded flight/court crops
- synthetic ID-switch pairs from tracks
- positive pairs from same identity
- negative pairs from nearby different people

Possible objectives:

- contrastive loss
- triplet loss
- binary same-target classifier
- supervised cosine embedding loss

Preferred first objective:

> binary same-target or contrastive crop-pair training

Target embedding size:

- `8D` or `16D`

---

## 12. Evaluation Protocol

Compare TIM-V1 against TIM-V0.

Use the same deterministic fault-injection batch:

- selected ID: `1`
- replacement ID: `3`
- same gap starts
- same gap durations

Metrics:

- reacquired cases
- validity gain
- reacquisition time
- wrong reacquisition rate, if annotated negatives exist
- added latency
- encoder trigger rate
- candidate crops encoded per second

Latency targets:

- TIM-V1 p95 overhead <= `2 ms`
- stretch target <= `1 ms`

---

## 13. Success Criteria

TIM-V1 is useful if it improves at least one of these without breaking latency:

1. recovers weak geometric cases rejected by TIM-V0
2. reduces ambiguous wrong matches
3. reduces LOST duration
4. improves reacquisition time
5. keeps p95 overhead within budget

Minimum useful result:

> TIM-V1 improves recovery in threshold-boundary cases while keeping p95 overhead below 2 ms.

---

## 14. Failure Modes

TIM-V1 can fail when:

- target crop is too small
- lighting changes strongly
- clothing colours are similar
- crop contains too much background
- detector box is unstable
- memory is updated with the wrong person
- encoder latency becomes too high

Most dangerous failure:

> memory corruption.

Therefore TIM-V1 must be conservative about memory updates.

---

## 15. Implementation Roadmap

Step 1: define feature API.

- `extract_target_feature(image, bbox) -> z`
- `compare_features(z_mem, z_candidate) -> S_lat`

Step 2: implement non-learned feature baseline.

- HSV histogram
- crop extraction
- feature memory
- status logging
- scoring integration
- latency accounting

Step 3: integrate into TIM.

Parameters:

- `use_latent`
- `w_lat`
- `latent_trigger_policy`
- `latent_update_alpha`
- `latent_min_bbox_height`

Step 4: evaluate.

Repeat:

- single fault injection
- batch fault injection
- threshold sweep
- latency analysis

Step 5: implement tiny learned embedding only after the baseline works.

---

## 16. Main Thesis Claim

Potential TIM-V1 claim:

> TIM-V1 adds a lightweight target-specific latent memory to a selected-target perception layer, improving reacquisition under weak geometric evidence while preserving bounded onboard latency.

This is stronger and more precise than claiming a full UAV latent world model.

---

## 17. Relation to Latent World Models

The supervisor email points to a broader research trend:

> compact predictive latent representations for UAV autonomy.

TIM-V1 borrows only the useful local idea:

> represent task-relevant visual state compactly in latent space.

But it applies it to a narrower and feasible problem:

> selected-target identity memory for micro-UAV following.

TIM-V1 is therefore not a latent world model.

It is a target-centric latent memory module.
