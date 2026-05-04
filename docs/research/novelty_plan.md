# Novelty Plan: Supervisor-Aligned Thesis Direction

Date: 2026-03-26
Owner: Thesis development

## 1. Supervisor Objective (Frozen)

Develop a computationally efficient, autonomous onboard perception system for a micro aerial robot that can detect, identify, and track people in real time using RGB-only onboard vision and low-power embedded compute.

The thesis must combine:

- robust small and distant person perception under onboard constraints
- control-coupled integration with explicit safety behaviour
- reliable operation in cluttered outdoor conditions

## 2. What Counts as Real Novelty in This Thesis

Novelty is not adding appearance features on its own. It must generate new technical evidence for this setting:

- micro-UAV
- strict onboard compute and latency budget
- selected-target tracking objective
- small and far person failure modes in real scenes

The strongest novelty is improving detector/tracker robustness for tiny and distant people while preserving real-time embedded operation.

## 3. Contribution Hierarchy (Frozen)

## Contribution A (Primary Algorithmic Novelty)

Tiny-person-aware detector/tracker improvement for selected-target onboard perception.

Core idea:

- improve detection and association behaviour when the selected person is small or far
- use risk-aware triggers based on size, confidence, and track stability
- maintain selected-target continuity without breaking runtime limits

Expected benefit:

- better recall for small and distant people
- fewer lock drops in far-target segments
- stronger selected-target continuity under ambiguity

## Contribution B (Secondary Identity Robustness Module)

Target-specific appearance support for ambiguity resolution and reacquisition.

Core idea:

- use the Target-Memory Appearance Path only when motion/IoU cues are ambiguous or after short loss
- update appearance memory conservatively in high-quality views
- avoid always-on appearance processing

Role in thesis:

- supports Contribution A
- does not define the main thesis novelty

## Contribution C (Primary Systems Novelty)

Control-safe, latency-bounded perception-to-control integration.

Core idea:

- combine freshness, geometric validity, and identity confidence into control validity
- enforce graded control modes under uncertainty and loss
- keep transition behaviour deterministic and bounded

Expected benefit:

- safer behaviour during stale, uncertain, or lost-target conditions
- bounded command behaviour across mode transitions
- defensible systems contribution beyond tracker metrics alone

## 4. Appearance Route Roles (Frozen Naming)

- Target-Memory Appearance Path: secondary support mechanism for ambiguity and reacquisition
- Full-Scene ReID Baseline: comparator baseline
- Detector-Feature Reuse Path: high-risk research reference only

## 5. Deep Research Work Package

Primary decision question:

- which detector/tracker changes are most defensible for tiny and distant people under strict embedded latency limits, and where does appearance support add value without dominating scope?

For each candidate method or paper family, extract:

- tiny/small target behaviour
- far-target robustness pattern
- recall impact by target size
- runtime and latency impact
- control relevance and selected-target continuity relevance
- appearance support role, if any

Priority reading families:

- small-object-aware detector/tracker methods under edge constraints
- UAV RGB-only person perception robustness studies
- efficient association strategies for ambiguous target crossings
- DeepSORT/BoT-SORT/LITE-style appearance families as secondary references

## 6. Real Coding Roadmap (Frozen Order)

## Phase 1: Control Closure and MAVROS Closure

Deliverables:

- frozen control contract and frame semantics
- completed ground validation campaign
- GO / NO-GO gate decision process ready

Acceptance:

- control path stable, including stale/lost safe behaviour

## Phase 2: Instrumentation for Novelty Experiments

Deliverables:

- explicit tiny-target and far-target event logging
- lock continuity and reacquisition timers
- control-validity transition traces

Acceptance:

- metrics produced automatically from bag analysis

## Phase 3: Contribution A Implementation (Primary)

Implementation tasks:

- add tiny-person-aware detector/tracker improvements
- define risk triggers from size/confidence/track stability
- integrate selected-target continuity logic for small/far segments
- add latency guardrails and watchdog checks

Acceptance:

- measurable gains in small/far selected-target robustness
- no unacceptable runtime regression

## Phase 4: Contribution C Integration (Primary Systems)

Implementation tasks:

- compute control validity from freshness + geometry + identity confidence
- map validity to conservative/normal/hold control modes
- enforce transition hysteresis and saturation limits

Acceptance:

- deterministic safe behaviour under uncertain perception
- no unsafe command bursts during transitions

## Phase 5: Contribution B Integration (Secondary Support)

Implementation tasks:

- integrate Target-Memory Appearance Path for ambiguity and reacquisition windows
- keep updates quality-gated and event-triggered
- measure added cost and continuity gain

Acceptance:

- improved continuity/reacquisition in ambiguity windows
- added runtime cost remains bounded

## 7. Evaluation Design

## Metrics (Novelty-Critical)

Small/far target robustness:

- recall by size bins
- selected-target lock retention in far/tiny segments
- lock continuity duration

Identity continuity:

- ID switches on selected target
- reacquisition time after controlled occlusion
- ambiguity-window recovery rate

System and control:

- end-to-end latency p50, p95, p99
- frame cadence stability
- invalid-to-safe transition time
- command saturation frequency and burst behaviour

## Comparative Experiments

Mandatory comparisons:

1. baseline tracker without tiny-person-specific improvement
2. baseline + Contribution A
3. baseline + Contribution A + Contribution C
4. baseline + Contribution A + Contribution C + Contribution B (secondary module)
5. baseline + Full-Scene ReID Baseline (comparator where feasible)

For each comparison:

- report robustness gain
- report runtime and latency cost
- report control-safety side effects

## 8. Defensible Thesis Claims

If supported by results, claim language should reflect:

1. tiny-person-aware detector/tracker improvement increases selected-target robustness for small and distant people under embedded constraints
2. latency-bounded control-validity integration improves safety behaviour in uncertain perception conditions
3. target-specific appearance support improves ambiguity resolution and reacquisition as a secondary module

## 9. Risk Register and Mitigations

Risk 1: tiny-target robustness gain is weak

- mitigation: tighten risk triggers and tune size-bin-specific thresholds

Risk 2: latency tail grows after detector/tracker changes

- mitigation: strict trigger budget, queue discipline, and runtime watchdog

Risk 3: appearance support adds cost without clear gain

- mitigation: keep Contribution B event-triggered and quality-gated only

Risk 4: confidence coupling causes control oscillation

- mitigation: hysteresis and mode-transition damping in Contribution C policy

## 10. Priority Ranking (Frozen)

Primary novelty (must deliver):

1. Contribution A: tiny-person-aware detector/tracker improvement
2. Contribution C: control-safe, latency-bounded perception-to-control integration

Secondary novelty (deliver after core is stable):

1. Contribution B: target-specific appearance support for ambiguity and reacquisition
2. event-triggered and view-quality-gated appearance updates

## 11. Best Thesis Package

Recommended coherent package:

- main algorithmic novelty: Contribution A
- main systems novelty: Contribution C
- secondary support module: Contribution B via Target-Memory Appearance Path

This package is strong because it is:

- centred on small/far person robustness
- selected-target and control-coupled
- feasible under embedded runtime constraints

## 12. Final Recommendation

Freeze this hierarchy and avoid daily scope drift:

- Contribution A and Contribution C are primary
- Contribution B is secondary support
- Full-Scene ReID Baseline is comparator only
- Detector-Feature Reuse Path is research reference only

Supervisor-aligned freeze: the main thesis objective is to improve onboard detector/tracker robustness for small and distant people under embedded runtime constraints. Appearance-based mechanisms are supporting options, not the primary thesis contribution unless later supervisor guidance changes this priority.
