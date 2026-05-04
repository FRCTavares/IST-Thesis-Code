# Novelty Plan: Selected-Target Perception for RGB-Only Micro-UAV Following

Date: 2026-05-04
Owner: Thesis development

## Table of Contents

- [Thesis Objective](#1-thesis-objective)
- [Core Problem](#2-core-problem)
- [Selected-Target Memory Layer](#4-primary-novelty-selected-target-memory-layer)
- [Selective ROI Re-Detection](#5-smallfar-target-extension-selective-roi-re-detection)
- [Control Validity Policy](#7-control-safe-perception-integration)


## 1. Thesis Objective

Develop a latency-bounded onboard RGB-only perception system that allows a micro-UAV to follow one selected person under embedded compute constraints.

The UAV may use Pixhawk GPS/IMU for vehicle state estimation and pilot-supervised control, but target detection, identity maintenance, and reacquisition are handled using onboard RGB perception.

## 2. Core Problem

The thesis is not generic multi-object tracking.

Generic MOT asks:

> Can all identities be maintained across the video?

This thesis asks:

> Can one selected person be maintained as a reliable control target when detections are noisy, intermittent, small, or temporarily lost?

The controller should not blindly follow a raw tracker ID. It should follow a selected-target state with explicit confidence and validity.

## 3. Current Evidence

Current results show:

- Hailo makes onboard detection feasible at low latency.
- The Raspberry Pi CPU can then focus on tracking, target consistency, logging, and control logic.
- Tracker-only performance is much stronger with clean detections.
- Real detector outputs cause missed detections, fragmented tracks, and ID switches.
- Larger detectors can improve perception, but often increase latency too much for strict onboard control.

Therefore, the main contribution should not be only:

> use YOLO + tracker on UAV

The contribution should be:

> convert noisy detector-tracker outputs into a control-valid selected-target representation under onboard latency constraints.

## 4. Primary Novelty: Selected-Target Memory Layer

## Contribution A: Selected-Target Memory

Core idea:

Add a lightweight layer above the detector and tracker that maintains the selected person as a persistent target state instead of directly trusting the raw tracker ID.

The layer should:

- initialise from an operator-selected track
- maintain a target memory using motion, bbox overlap, scale, and confidence
- handle short detection gaps
- recover through tracker ID changes when evidence is consistent
- output clear states such as:
  - NO_TARGET
  - LOCKED
  - UNCERTAIN
  - LOST
  - REACQUIRED

This is target-specific, not full-scene MOT.

Operator commands have priority:

```text
operator command > selected-target memory > raw tracker ID

If the operator selects another detected person, the current memory is reset and initialised from the new target.

5. Small/Far Target Extension: Selective ROI Re-Detection
Contribution B: Selective Target Re-Detection

Core idea:

When the selected target becomes small, uncertain, or close to being lost, spend extra computation only around the predicted target region.

Instead of increasing full-frame resolution, the system should:

predict likely target region
-> crop ROI around that region
-> resize ROI to detector input size
-> run detector again on the crop
-> map detection back to full image
-> update selected-target memory

Expected benefit:

improve detection of small/far selected targets
reduce lock drops when the target is near the detector limit
keep latency bounded by avoiding full-frame high-resolution inference

Trigger conditions:

target bbox height below threshold
confidence drops
target predicted but not detected
selected-target state becomes UNCERTAIN or LOST
target close to image edge
tracker close to losing target

This is a safer detector-side contribution than immediately designing a full detector from scratch.

6. Optional Identity Support: Target-Only Appearance
Contribution C: Event-Triggered Appearance Support

Appearance is not the main starting point.

Core idea:

Use appearance only for the selected target and only when needed.

Use cases:

ambiguous association
tracker ID switch
short occlusion
reacquisition after loss
two nearby candidate people

Avoid:

full-scene ReID every frame
DeepSORT-style always-on appearance for all objects

Possible descriptors:

colour histogram baseline
small crop descriptor
compact learned embedding
Hailo-deployed embedding only if needed

Update policy:

update only when LOCKED and high confidence
freeze during UNCERTAIN
freeze during LOST
avoid updates from tiny, blurry, clipped, or low-confidence crops
7. Control-Safe Perception Integration
Contribution D: Control Validity Policy

Control should use the selected-target state, not raw detections or raw tracker IDs.

Basic policy:

`LOCKED`     -> normal target-relative command
`UNCERTAIN`  -> slow down / yaw-only / hold
`LOST`       -> hover or constrained search
`REACQUIRED` -> confirm before full control resumes
`NO_TARGET`  -> no following command

This is not a new controller contribution. It is perception-aware control validity.

Expected benefit:

avoid aggressive commands during identity uncertainty
avoid following the wrong person after an ID switch
make failure modes explicit and safe
8. Difference from DeepSORT

DeepSORT improves global MOT by using appearance features for all tracked objects.

This thesis is different because it focuses on:

one selected target, not all identities
explicit operator target selection
control-validity states
event-triggered recovery logic
bounded onboard latency
selective computation only when the selected target is at risk

The goal is not to beat DeepSORT as a generic MOT method.

The goal is to produce a reliable selected-target representation for micro-UAV following.

9. Research Questions

RQ1:
Can a selected-target memory layer reduce target switches compared with raw tracker ID following?

RQ2:
Can selected-target memory improve lock duration and short-term reacquisition under detector flicker?

RQ3:
Can selective ROI re-detection improve small/far target continuity without full-frame high-resolution inference?

RQ4:
Can target-only appearance, used only during ambiguity or reacquisition, improve identity stability with limited overhead?

RQ5:
Can explicit target-validity states make pilot-supervised target-relative control safer under uncertain perception?

10. Implementation Roadmap
Phase 1: Baseline Stability

Deliverables:

live yolov6n + ByteTrack or OC-SORT baseline
verified low-score detection handling for ByteTrack
live logging of detections, tracks, target state, timing

Acceptance:

stable live perception and tracking at acceptable FPS
no unbounded queue growth
timing messages and bag analysis working
Phase 2: Selected-Target Memory V0

Deliverables:

design document
pure Python implementation
synthetic validation tests
offline tests on bags

Minimum functions:

bbox_iou
centre_distance
scale_similarity
score_candidate
update_memory
state transition logic

Acceptance:

fewer selected-target switches in simple ID-change cases
short detection gaps handled without wrong-target jumps
negligible runtime overhead
Phase 3: Control Validity Integration

Deliverables:

target state published to control path
control validity policy
safe behaviour for UNCERTAIN, LOST, and NO_TARGET

Acceptance:

no aggressive commands when target state is invalid or uncertain
deterministic state transitions
Phase 4: Selective ROI Re-Detection

Deliverables:

ROI prediction from selected-target memory
crop, resize, re-detect, remap pipeline
trigger policy
latency measurement

Acceptance:

improved continuity for small/far target cases
trigger rate and latency overhead reported
p95/p99 latency remains acceptable
Phase 5: Target-Only Appearance Support

Deliverables:

simple appearance baseline
event-triggered appearance matching
quality-gated memory updates

Acceptance:

improved ambiguity or reacquisition behaviour
overhead remains bounded
failure cases reported honestly
11. Evaluation Metrics

Selected-target identity:

selected-target switches
wrong-target lock count
false reacquisition count
selected-target continuity

Continuity:

lock duration
lost duration
fragmentation
time in LOCKED / UNCERTAIN / LOST / REACQUIRED

Reacquisition:

time-to-reacquire
reacquisition success rate
false reacquisition rate

Small/far target robustness:

recall by bbox height bins
lock retention in small-target segments
ROI re-detection trigger rate
ROI re-detection success rate

Control relevance:

valid target time
stale target time
image centre error
commands published during invalid target states
control mode transitions

System:

FPS
end-to-end target latency mean/p50/p95/p99
inference latency mean/p50/p95/p99
tracker latency mean/p50/p95/p99
selected-target memory overhead mean/p50/p95/p99
ROI re-detection overhead mean/p50/p95/p99
12. Comparative Experiments

Mandatory comparisons:

detector + tracker baseline
detector + tracker + selected-target memory
detector + tracker + selected-target memory + control validity
detector + tracker + selected-target memory + selective ROI re-detection
detector + tracker + selected-target memory + target-only appearance
DeepSORT or appearance-based tracker as comparator if feasible

For each comparison:

report selected-target robustness
report runtime and latency cost
report control-relevance effects
report failure cases
13. Defensible Thesis Claims

Possible claims, if supported by results:

A selected-target memory layer improves control-target continuity compared with raw tracker ID following.
Explicit target-validity states reduce unsafe or unstable control behaviour during perception uncertainty.
Selective ROI re-detection improves small/far selected-target continuity while keeping computation bounded.
Target-only appearance support improves ambiguity and reacquisition cases with lower overhead than full-scene appearance tracking.

Do not claim:

universal UAV person following
full solution to long-term re-identification
detector failures are fully solved
generic MOT replacement
14. Risk Register

Risk 1: selected-target memory does not improve difficult cases

Mitigation:

focus claim on short detection gaps, ID switches, and bounded reacquisition
report failure cases honestly

Risk 2: detector misses are too long for memory to recover

Mitigation:

transition to LOST
require operator confirmation or constrained search
use selective ROI re-detection only while prediction is still meaningful

Risk 3: ROI re-detection increases latency too much

Mitigation:

event-trigger only
limit trigger rate
measure p95/p99 overhead
disable if latency budget is exceeded

Risk 4: appearance support adds cost without benefit

Mitigation:

keep target-only and event-triggered
compare against no-appearance baseline
use simple descriptor first

Risk 5: control reacts to uncertain identity

Mitigation:

explicit validity states
hysteresis
conservative control in UNCERTAIN and LOST
15. Priority Ranking

Primary:

Selected-target memory layer
Control-validity states
Selective ROI re-detection for small/far selected target

Secondary:

Target-only appearance support
Full-scene ReID baseline as comparator only

Not primary:

full new detector from scratch
always-on ReID
generic MOT improvement without control relevance
16. Final Positioning

This thesis does not propose a generic replacement for modern MOT.

It proposes a selected-target perception layer that converts noisy detector-tracker outputs into a control-valid target representation for RGB-only micro-UAV following under onboard latency constraints.

The strongest package is:

Hailo detector
-> ByteTrack / OC-SORT
-> selected-target memory
-> control-validity states
-> selective ROI re-detection when target is small or uncertain
-> optional target-only appearance for ambiguity