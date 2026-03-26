# Literature Reading Matrix: Appearance and Tracking for Onboard Micro-UAV

Date: 2026-03-26
Owner: Thesis literature workstream

## Purpose

Use this matrix to extract only decision-critical information from each paper and convert reading into implementation choices.

Primary decision question:

Which appearance integration design is most defensible and feasible for onboard target-relative following under strict latency and compute limits?

Naming convention for this file:

- `Option O1/O2/O3` = appearance design alternatives
- `Contribution A/B/C` = thesis contribution hierarchy

## How to Use This File

1. Add one row per paper.
2. Fill all mandatory columns.
3. Keep notes factual and short.
4. Mark unknown fields explicitly as unknown.
5. Update final design recommendation after every 3 to 5 papers.

## Mandatory Extraction Fields

| Paper ID | Tracker/Paper Name | Year | Task Context | Where Appearance Enters | Descriptor Dim | Appearance Usage Policy | Matching Metric | Association Pipeline | Control-Coupling Signal | Trigger Policy Detail | Reported Gains | Reported Failure Modes | Compute Cost Signal | Embedded Feasibility (1-5) | Integration Risk (1-5) | Relevance to This Thesis (1-5) | Design Option Mapping (O1/O2/O3) | Contribution Relevance (A/C/B) | Notes |
|---|---|---|---|---|---:|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|
| P01 | DeepSORT-style baseline | TBD | MOT | TBD | TBD | TBD | TBD | motion + IoU + appearance | weak/none | always-on or near always-on | TBD | TBD | TBD | TBD | TBD | TBD | O1 | A | |
| P02 | BoT-SORT family | TBD | MOT | TBD | TBD | TBD | TBD | motion + IoU + appearance fusion | weak/none | ambiguity-biased | TBD | TBD | TBD | TBD | TBD | TBD | O1 | A | |
| P03 | LITE-style efficient appearance integration | TBD | MOT | TBD | TBD | TBD | TBD | integrated feature + association | weak/none | efficiency-focused | TBD | TBD | TBD | TBD | TBD | TBD | O2 | A | |
| P04 | UAV/ReID paper 1 | TBD | UAV tracking/ReID | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | O1 or O3 | A or C | |
| P05 | UAV/ReID paper 2 | TBD | UAV tracking/ReID | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | O1 or O3 | A or C | |

## Scoring Guidance

Embedded Feasibility (1-5):

- 1: clearly not feasible on current onboard stack
- 3: feasible with substantial optimization and tradeoffs
- 5: directly feasible with low risk

Integration Risk (1-5):

- 1: low code and dependency risk
- 3: moderate refactor and tuning required
- 5: high risk due to architecture/toolchain constraints

Relevance to This Thesis (1-5):

- 1: weak overlap with selected-target control objective
- 3: partial overlap
- 5: strong overlap with lock continuity and reacquisition objective

Design option mapping:

- O1: lightweight ReID branch
- O2: detector-integrated appearance features
- O3: target-only appearance memory

Contribution relevance mapping:

- A: target-specific appearance memory (main algorithmic novelty)
- C: identity-confidence-aware control validity policy (main systems novelty)
- B: selective tiny-target refine (stretch)

## Implementation Extraction Addendum (For Coding Readiness)

After each paper row, add a short implementation note block:

- Integration point in this repository
- Required new data structures
- Expected runtime overhead location
- New metrics required to validate claim
- Failure conditions to test

Template:

### Implementation Note — [Paper ID]

- Integration point:
- Data structures:
- Runtime overhead location:
- Validation metrics:
- Failure conditions:
- Directly reusable ideas:
- Not suitable ideas:

## Thesis Decision Snapshot (Update Weekly)

Current best option:

- [ ] Option O1 (lightweight ReID branch)
- [ ] Option O2 (detector-integrated features)
- [ ] Option O3 (target-only appearance memory)

Rationale summary:

-

Open risks before implementation:

-

Minimum evidence required before coding starts:

- [ ] At least 5 core papers filled in matrix
- [ ] At least 2 UAV-specific constraints references reviewed
- [ ] Estimated overhead budget documented for selected option
- [ ] Evaluation plan frozen for ID switches, reacquisition, lock continuity, and latency impact

## Selected Novelty Package (Current)

- Primary: Contribution A + Contribution C
- Secondary: event-triggered appearance use and quality-gated memory updates

Frozen hierarchy note:

- Contribution A and Contribution C are primary.
- Contribution B is stretch-only.

Evidence expected from matrix:

- confirm where prior work ends (association quality only)
- identify the literature gap for control-coupled identity validity
- justify embedded runtime choices for ambiguity-only usage

## Final Selection Memo Stub

When ready, write a short decision memo here:

- Selected option:
- Why this option is best for onboard control-coupled tracking:
- Why alternatives were rejected for now:
- Planned implementation scope for first coding pass:
- Success criteria for first milestone:
