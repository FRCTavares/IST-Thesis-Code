# TIM-V1A - Colour Target Memory Design

Date: 2026-05-09  
Status: design before implementation

## 1. Goal

TIM-V1A adds a lightweight colour appearance cue to TIM-V0.

The goal is to improve selected-target reacquisition and ambiguity handling when geometry alone is weak.

TIM-V1A is not a full ReID tracker and not a DeepSORT replacement. It is a target-only memory cue used selectively.

---

## 2. Motivation

TIM-V0 uses:

- IoU
- centre distance
- scale similarity
- confidence
- same-ID bonus
- ambiguity penalty

This is fast and interpretable, but it can fail when:

- the target disappears for too long
- the target reappears far from the remembered position
- the tracker assigns a new ID
- geometry score is below the lost-state threshold
- two candidates are geometrically ambiguous

TIM-V1A adds colour memory before attempting a learned embedding.

---

## 3. Feature

Initial feature:

- HSV histogram
- upper/lower body split
- L2 normalisation
- cosine similarity

Proposed bins:

- H bins: 16
- S bins: 8
- V channel ignored initially
- 2 body regions: upper and lower

Feature size:

- 16 x 8 x 2 = 256 dimensions

Reason:

- no training needed
- fast on CPU
- interpretable
- useful baseline before learned embeddings

---

## 4. Inputs

TIM-V1A needs:

- current RGB image
- candidate track boxes
- selected target memory
- current TIM state
- current geometric TIM-V0 candidate scores

Crop source:

- current image frame
- candidate bbox from /tracks

Crop rules:

- clip bbox to image boundaries
- reject invalid boxes
- reject crops below minimum height
- avoid memory update from tiny or low-confidence crops

Initial minimum bbox height:

- 30 px

---

## 5. Similarity

Use cosine similarity:

S_app = dot(z_memory, z_candidate)

Assumption:

- z_memory and z_candidate are L2-normalised

Interpretation:

- high value means similar colour appearance
- low value means different colour appearance

---

## 6. Score Integration

TIM-V0 score:

S_v0 = geometry + confidence + same-ID bonus - ambiguity penalty

TIM-V1A score:

S_v1a = S_v0 + w_app S_app

Initial policy:

- appearance is only used when useful
- appearance must not override extremely poor geometry by itself
- log when appearance changes candidate selection or acceptance

Suggested initial values:

- w_app = 0.10 to 0.20
- appearance trigger margin = 0.10 around geometric threshold

---

## 7. Trigger Policy

Compute appearance when:

- TIM state is UNCERTAIN
- TIM state is LOST
- candidate ID differs from remembered target ID
- candidate score is near acceptance threshold
- ambiguity is detected
- TIM is LOCKED and memory can be safely updated

Do not compute appearance for every track in every frame unless profiling shows the cost is negligible.

---

## 8. Memory Update Policy

NO_TARGET:

- no appearance memory

LOCKED:

- update memory slowly
- update only if match is strong and unambiguous

UNCERTAIN:

- use memory for matching
- do not update memory

LOST:

- use memory for reacquisition
- do not update memory

REACQUIRED:

- wait for stable confirmation before updating again

Update equation:

z_memory = normalise((1 - alpha) z_memory + alpha z_candidate)

Suggested alpha:

- 0.10

Most important rule:

- never update memory from weak or ambiguous candidates

---

## 9. Diagnostics

Expose or log later:

- appearance_used
- appearance_score
- appearance_memory_quality
- appearance_update_reason
- appearance_compute_ms
- candidate_count_encoded

These are needed to prove that TIM-V1A is latency-bounded.

---

## 10. Evaluation

Compare:

- raw /target
- TIM-V0
- TIM-V1A

Metrics:

- correct target duration
- wrong target duration
- lost duration
- safe invalid duration
- reacquisition time
- reacquired cases
- appearance trigger rate
- TIM latency p50, p95, p99

Useful bags:

- field_reentry_01
- field_distractor_static_01
- field_crossing_01
- field_occlusion_01
- field_far_target_01

---

## 11. Latency Budget

Target:

- TIM-V1A p95 overhead <= 2 ms

Stretch:

- TIM-V1A p95 overhead <= 1 ms

Reason:

- TIM-V0 is already well below 1 ms p95 in tested bags
- TIM-V1A must not break onboard real-time behaviour

---

## 12. Implementation Plan

Step 1:

- implement standalone crop and HSV feature utility

Step 2:

- test feature extraction on frames from recorded bags

Step 3:

- add appearance memory to TIM without changing decisions

Step 4:

- log appearance score only

Step 5:

- enable appearance-assisted scoring behind a flag

Step 6:

- compare TIM-V0 and TIM-V1A on annotated field bags

---

## 13. Thesis Positioning

TIM-V1A is a training-free appearance-memory baseline.

Its value is not that HSV histograms are novel.

Its value is that it creates a controlled intermediate step between:

- TIM-V0 geometry-only memory
- TIM-V1B learned target embedding

This keeps the development interpretable and measurable.
