# Novelty Plan: Selected-Target Perception for RGB-Only Micro-UAV Following

Date: 2026-05-04  
Owner: Thesis development

---

## 1. Thesis Objective

Develop a latency-bounded onboard RGB-only perception system that allows a micro-UAV to follow one selected person under embedded compute constraints.

The UAV may use Pixhawk GPS/IMU for state estimation and pilot-supervised control, but target detection, identity maintenance, and reacquisition are handled using onboard RGB perception.

---

## 2. Core Problem

This is not generic multi-object tracking.

Generic MOT:
> Maintain all identities.

This thesis:
> Maintain one selected person as a reliable control target under noise, occlusion, and latency.

The controller must follow a **validated target state**, not a raw tracker ID.

---

## 3. Current Evidence

- Hailo enables fast onboard detection.
- Tracker works well with clean detections.
- Real detections cause:
  - missed frames
  - ID switches
  - fragmentation
- Larger models improve accuracy but break latency.

**Conclusion:**
> The problem is temporal instability, not just accuracy.

---

## 4. Primary Novelty: Selected-Target Memory

A lightweight layer above tracker outputs that maintains one selected target.

### Behaviour

- initialise from operator-selected track
- maintain memory using:
  - IoU
  - motion
  - scale
  - confidence
- handle short detection gaps
- recover from ID switches

### States

- NO_TARGET
- LOCKED
- UNCERTAIN
- LOST
- REACQUIRED

### Priority

```
operator command > memory > tracker ID
```

---

## 5. Core Matching Score

For each candidate track j:

S_j = w_iou S_iou + w_dist S_dist + w_scale S_scale + w_conf S_conf - w_amb S_amb

Select:

j* = argmax_j S_j

Accept only if above threshold and not ambiguous.

---

## 6. Selective ROI Re-Detection

When target is small or uncertain:

```
predict target region
→ crop ROI
→ resize to detector input
→ re-run detector
→ map back
```

### Triggers

- small bbox
- low confidence
- missing detection
- UNCERTAIN / LOST

### Benefit

- improves small/far detection
- bounded computation

---

## 7. Optional Appearance Support

Used only when needed:

- ambiguity
- ID switch
- reacquisition

Avoid full DeepSORT-style always-on ReID.

### Policy

- update only when LOCKED
- freeze when UNCERTAIN or LOST

---

## 8. Control Validity Policy

```
LOCKED     → normal control
UNCERTAIN  → slow / yaw only
LOST       → hover
REACQUIRED → confirm
NO_TARGET  → no control
```

Goal: prevent unsafe commands.

---

## 9. Difference from DeepSORT

- single target, not all objects
- operator-driven selection
- event-triggered appearance
- explicit control validity
- latency bounded

---

## 10. Compute Split

Hailo:
- detection

Raspberry Pi:
- tracking
- target memory
- ROI logic
- control validity
- logging

---

## 11. Operating Envelope

Designed for:

- short-term continuity
- outdoor supervised tests
- one selected person

Fails in:

- long disappearance
- identical people crossing
- severe blur
- detector never recovers

---

## 12. Research Questions

RQ1: reduce target switches?  
RQ2: improve lock duration?  
RQ3: improve small/far detection?  
RQ4: improve reacquisition?  
RQ5: improve control safety?

---

## 13. Implementation Roadmap

### Phase 1
Baseline detector + tracker

### Phase 2
Selected-target memory

### Phase 3
Control validity

### Phase 4
ROI re-detection

### Phase 5
Appearance support

---

## 14. Implementation Files

- docs/design/selected_target_memory.md
- target_memory.py
- target_memory_node.py
- test_target_memory_synthetic.py
- evaluate_selected_target_memory.py

---

## 15. Metrics

Identity:
- switches
- wrong locks

Continuity:
- lock duration
- lost time

Reacquisition:
- time to recover

System:
- FPS
- latency p50/p95/p99

---

## 16. Minimum Proof

Must show:

1. tracker fails alone  
2. memory improves stability  
3. ROI improves small targets  
4. control remains safe  
5. latency remains bounded  

---

## 17. Final Positioning

This is not a new detector or tracker.

It is a layer that converts noisy detection + tracking into a stable, control-valid target for UAV following.
