# Literature Reading Matrix: Tiny-Person Robustness for Onboard Micro-UAV

Date: 2026-03-26
Owner: Thesis literature workstream

## Purpose

Use this matrix to convert literature into implementation decisions for supervisor-aligned thesis priorities.

Primary decision question:

Which detector/tracker improvements are most defensible and feasible for improving robustness to small and distant people onboard under tight latency constraints, and where can appearance support help as a secondary mechanism?

## Route and Contribution Labels

- Full-Scene ReID Baseline: comparator baseline
- Detector-Feature Reuse Path: high-risk research reference only
- Target-Memory Appearance Path: secondary support module
- Contribution A: primary algorithmic novelty (tiny-person-aware detector/tracker improvement)
- Contribution B: secondary identity robustness module
- Contribution C: primary systems novelty (control-safe, latency-bounded integration)

## How to Use This File

1. Add one row per paper.
2. Fill all mandatory columns.
3. Keep notes factual and concise.
4. Mark unknown fields explicitly as unknown.
5. Update decision snapshot after each 3 to 5 papers.

## Mandatory Extraction Fields

| Paper ID | Method/Paper Name | Year | Task Context | Tiny-Person Behaviour | Far-Target Behaviour | Recall by Size Signal | Association Strategy | Appearance Role | Trigger Policy | Embedded Runtime Cost Signal | Latency Impact Signal | Control Relevance | Selected-Target Continuity Relevance | Embedded Feasibility (1-5) | Integration Risk (1-5) | Thesis Relevance (1-5) | Route Mapping | Contribution Mapping | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|
| P01 | DeepSORT-style baseline | TBD | MOT | TBD | TBD | TBD | motion + IoU + appearance | always-on appearance | near always-on | TBD | TBD | weak | medium | TBD | TBD | TBD | Full-Scene ReID Baseline | B | comparator reference |
| P02 | BoT-SORT family | TBD | MOT | TBD | TBD | TBD | motion + IoU + appearance fusion | ambiguity-biased appearance | partial trigger | TBD | TBD | weak | medium | TBD | TBD | TBD | Full-Scene ReID Baseline | B | comparator reference |
| P03 | LITE-style efficient integration | TBD | MOT | TBD | TBD | TBD | integrated features + association | detector feature reuse | efficiency-focused | TBD | TBD | weak | medium | TBD | TBD | TBD | Detector-Feature Reuse Path | B | high-risk reference |
| P04 | UAV small-object tracking paper | TBD | UAV tracking | TBD | TBD | TBD | TBD | none or limited | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | detector/tracker primary path | A | primary direction evidence |
| P05 | UAV identity robustness paper | TBD | UAV tracking/ReID | TBD | TBD | TBD | TBD | target-only appearance support | ambiguity/reacquisition | TBD | TBD | medium | high | TBD | TBD | TBD | Target-Memory Appearance Path | B/C | secondary support evidence |

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
- 5: strong overlap with tiny/far selected-target robustness and control-coupled operation

## Implementation Extraction Addendum

After each row, add a short note:

- integration point in this repository
- data structures needed
- expected overhead location
- validation metrics
- failure conditions

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

Current primary direction:

- [x] Contribution A first: tiny-person-aware detector/tracker improvement
- [x] Contribution C in parallel for safe latency-bounded control integration
- [ ] Contribution B expansion only after A and C are stable

Appearance route status:

- [ ] Full-Scene ReID Baseline used only as comparator
- [ ] Detector-Feature Reuse Path tracked as high-risk reference
- [ ] Target-Memory Appearance Path used as secondary module

Minimum evidence required before coding freeze:

- [ ] at least 5 decision-grade rows completed
- [ ] at least 2 rows focused on small/far person robustness
- [ ] latency impact estimates documented for shortlisted methods
- [ ] control relevance noted for shortlisted methods

## Evidence Appendix: Direction Mapping

Rows that support Contribution A as primary direction:

- [ ] List row IDs:

Rows that justify keeping Full-Scene ReID Baseline as comparator:

- [ ] List row IDs:

Rows that justify keeping Detector-Feature Reuse Path as high risk:

- [ ] List row IDs:

Rows that support Target-Memory Appearance Path as secondary module:

- [ ] List row IDs:

## Final Selection Memo Stub

When ready, write a short decision memo:

- Primary detector/tracker direction selected:
- Why this direction is best for small/far selected-target robustness:
- How Contribution C integration is preserved:
- Where appearance support is useful and bounded:
- Why rejected paths stay comparator/reference only:
