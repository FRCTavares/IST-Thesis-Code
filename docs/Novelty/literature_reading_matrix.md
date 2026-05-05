# Literature Reading Matrix: Selected-Target Perception for RGB-Only Micro-UAV Following

Date: 2026-05-04
Owner: Thesis literature workstream

## Table of Contents

- [Purpose](#purpose)
- [How to Use This File](#how-to-use-this-file)
- [Mandatory Extraction Fields](#mandatory-extraction-fields)
- [Scoring Guidance](#scoring-guidance)
- [Implementation Note — Paper ID](#implementation-note--paper-id)

## Purpose

Use this matrix to convert literature into implementation decisions for the current thesis direction.

Primary decision question:

Which methods help maintain one selected person as a reliable UAV-following target under onboard RGB-only latency constraints?

The focus is not generic MOT alone. The key question is whether a method helps selected-target continuity, reacquisition, small/far target robustness, and control-validity decisions.

## Route and Contribution Labels

Primary routes:

- Selected-Target Memory Layer: main selected-target identity and validity mechanism
- Selective ROI Re-Detection: small/far target recovery mechanism
- Control Validity Policy: perception-to-control safety mechanism

Secondary routes:

- Target-Only Appearance Support: event-triggered appearance for ambiguity and reacquisition
- Full-Scene ReID Baseline: comparator baseline only
- Detector-Feature Reuse Path: high-risk reference only
- Full New Detector Path: not first priority, research reference only

Contribution labels:

- Contribution A: selected-target memory and identity continuity
- Contribution B: selective ROI re-detection for small/far targets
- Contribution C: control-validity states and safe perception-to-control integration
- Contribution D: target-only appearance support

## How to Use This File

1. Add one row per paper.
2. Fill all mandatory columns.
3. Keep notes factual and concise.
4. Mark unknown fields explicitly as unknown.
5. After every 3 to 5 papers, update the decision snapshot.

## Mandatory Extraction Fields

| Paper ID | Method/Paper Name | Year | Task Context | Selected-Target Relevance | Small/Far Target Relevance | Detector Failure Handling | Reacquisition Handling | Association Strategy | Appearance Role | ROI / Local Re-Detection | Trigger Policy | Embedded Runtime Cost Signal | Latency Impact Signal | Control Relevance | Failure Modes | Embedded Feasibility (1-5) | Integration Risk (1-5) | Thesis Relevance (1-5) | Route Mapping | Contribution Mapping | Notes |
|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|
| P01 | SORT | 2016 | MOT | medium | weak | weak | weak | Kalman + IoU | none | none | none | low | low | weak | detector-dependent, ID switches | 5 | 1 | 4 | tracker baseline | A | fast baseline; useful to show detector dependency |
| P02 | ByteTrack | 2022 | MOT | high | medium | medium | medium | high-score + low-score detection association | none | none | detection score thresholds | low-medium | low-medium | medium | requires access to low-score boxes | 4 | 2 | 5 | tracker baseline | A | important baseline for detector-limited tracking |
| P03 | OC-SORT | 2023 | MOT | high | medium | medium | medium | observation-centric motion association | none | none | motion/association thresholds | low-medium | low-medium | medium | still detector-dependent | 4 | 2 | 5 | tracker baseline | A | strong motion baseline |
| P04 | DeepSORT | 2017 | MOT/ReID | medium | weak | medium | medium | motion + IoU + appearance | always-on full-scene appearance | none | near always-on | high | high | weak-medium | too heavy if used continuously | 2 | 3 | 3 | Full-Scene ReID Baseline | D | comparator; not main solution |
| P05 | BoT-SORT | 2022 | MOT/ReID | medium | medium | medium | medium | motion + IoU + appearance + camera motion | full-scene or broad appearance | none | partial | medium-high | medium-high | weak-medium | complexity and appearance cost | 2 | 4 | 3 | Full-Scene ReID Baseline | D | useful comparison for modern MOT |
| P06 | UAV target following with YOLO + MOT | TBD | UAV following | high | medium | TBD | TBD | detector + tracker | varies | usually none | varies | TBD | TBD | high | may assume larger compute or simpler scenarios | TBD | TBD | 5 | UAV baseline | A/C | close related work; must distinguish selected-target validity layer |
| P07 | Monocular long-term target following | TBD | UAV/robot following | high | medium | medium | high | target-specific tracking | target-specific | possible search/recovery | loss/recovery triggers | TBD | TBD | high | may not match micro-UAV constraints | TBD | TBD | 5 | selected-target recovery | A/C | useful for reacquisition framing |
| P08 | Target-specific appearance memory paper | TBD | Robot/person following | high | weak-medium | medium | high | target memory + appearance | target-only appearance | none | ambiguity/loss | medium | medium | high | appearance unreliable for tiny crops | TBD | TBD | 5 | Target-Only Appearance Support | D | useful for event-triggered appearance |
| P09 | Small-object / tiny-person detector paper | TBD | Detection | medium | high | medium | weak | detection improvement | none | possible | size/confidence | varies | varies | medium | may be too slow or not Hailo-ready | TBD | TBD | 4 | detector reference | B | use for ROI re-detection ideas |
| P10 | ROI / crop-based detection paper | TBD | Detection/tracking | high | high | high | medium-high | local re-detection | optional | yes | uncertainty/size/loss | medium | event-dependent | high | crop may miss target if prediction is bad | TBD | TBD | 5 | Selective ROI Re-Detection | B | directly relevant to selective local resolution |

## Scoring Guidance

Embedded Feasibility (1-5):

- 1: not feasible on current onboard stack
- 3: feasible with significant optimisation
- 5: directly feasible with low risk

Integration Risk (1-5):

- 1: low integration risk
- 3: moderate refactor and tuning effort
- 5: high risk due to architecture/toolchain constraints

Thesis Relevance (1-5):

- 1: weak overlap with thesis objective
- 3: partial overlap
- 5: strong overlap with selected-target robustness, small/far target recovery, and control-valid operation

## What to Extract From Each Paper

For each paper, answer:

1. Does it help maintain one selected target, or only improve global MOT?
2. Does it address missed detections or only association after detection?
3. Does it help when the target is small or far?
4. Does it support reacquisition?
5. Is appearance always-on or event-triggered?
6. Could it run on Raspberry Pi 5 + Hailo under the latency budget?
7. Does it provide a control-valid target state, or only tracking metrics?
8. What exact part could be reused in this repository?

## Implementation Extraction Addendum

After each row, add a short note:

### Implementation Note — [Paper ID]

- Integration point:
- Data structures needed:
- Runtime overhead location:
- Validation metrics:
- Failure conditions:
- Directly reusable ideas:
- Not suitable ideas:

## Current Thesis Decision Snapshot

Current primary direction:

- [x] Selected-target memory first
- [x] Control-validity states in parallel
- [x] Selective ROI re-detection as small/far target extension
- [ ] Target-only appearance only after the basic memory layer works
- [ ] Full-scene ReID only as comparator

Current baseline direction:

- [x] Detector + tracker baseline
- [x] ByteTrack and OC-SORT as main tracker baselines
- [x] DeepSORT/BoT-SORT as literature and possible comparator, not main implementation path

Detector direction:

- [x] Use Hailo to keep detector latency low
- [x] Use Raspberry Pi CPU for target memory, tracking logic, logging, and control logic
- [ ] Do not start by designing a full detector from scratch
- [x] Investigate selective ROI re-detection for small/uncertain selected targets

## Minimum Evidence Required Before Coding Freeze

- [ ] at least 5 decision-grade rows completed
- [ ] at least 2 rows focused on selected-target identity continuity
- [ ] at least 2 rows focused on small/far target or ROI-based recovery
- [ ] at least 1 row comparing against full-scene appearance tracking
- [ ] latency impact estimates documented for shortlisted methods
- [ ] control relevance documented for shortlisted methods

## Evidence Appendix: Direction Mapping

Rows that support Selected-Target Memory as primary direction:

- [ ] List row IDs:

Rows that support Selective ROI Re-Detection:

- [ ] List row IDs:

Rows that support Control Validity Policy:

- [ ] List row IDs:

Rows that justify keeping Full-Scene ReID as comparator:

- [ ] List row IDs:

Rows that support Target-Only Appearance as secondary support:

- [ ] List row IDs:

Rows that suggest a full new detector may be useful later:

- [ ] List row IDs:

## Final Selection Memo Stub

When ready, write a short decision memo:

- Primary selected-target method selected:
- Why this method is better than raw tracker ID following:
- How it handles short detector failures:
- How it fails safely when the detector cannot recover the target:
- How selective ROI re-detection is triggered:
- Why this is different from DeepSORT or full-scene ReID:
- How control-validity states are preserved:
- Runtime and latency impact:
- Rejected paths and why they remain comparator/reference only: