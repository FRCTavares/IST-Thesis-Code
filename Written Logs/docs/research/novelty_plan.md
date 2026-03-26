# Novelty Plan: Deep Research and Real Implementation

Date: 2026-03-26
Owner: Thesis development

## 1. Supervisor Objective (Frozen)

Develop a computationally efficient, autonomous onboard perception system for a micro aerial robot that can detect, identify, and track objects in real time using onboard vision and low-power embedded compute.

The thesis must combine:

- state-of-the-art computer vision and deep learning methods
- robust onboard control and estimation integration
- reliable operation in real-world, cluttered, dynamic conditions

This novelty plan translates that objective into publishable and implementable work.

## 2. What Counts as Real Novelty in This Thesis

Novelty should not be only adding another model. It should create new technical knowledge for this exact setting:

- micro-UAV
- strict onboard compute budget
- control-coupled tracking objective
- real-world clutter and occlusions

The strongest novelty for this thesis is to design methods that are aware of both identity reliability and control safety under latency constraints.

## 3. Proposed Novel Contributions

## Contribution A (Primary)

Control-aware target-specific appearance memory for reacquisition.

Core idea:

- maintain appearance memory only for the selected target
- update memory only in high-confidence windows
- invoke appearance matching only when motion and IoU are ambiguous
- output identity confidence that can gate control aggressiveness

Why this is novel for this thesis:

- most MOT systems optimize global tracking quality
- this thesis optimizes single-target lock continuity for closed-loop control
- appearance is triggered adaptively, not always-on, reducing onboard cost

Expected benefit:

- lower ID switches on selected target
- faster and safer reacquisition after short occlusions
- bounded compute overhead compared with per-detection ReID
- clear fit to selected-target following instead of full-scene MOT optimization

## Contribution B (Stretch Robustness Extension)

Ambiguity-triggered selective refine for tiny targets.

Core idea:

- trigger a lightweight refine pass only when target size/confidence indicates high risk
- local ROI refinement around predicted target state
- skip refine in normal high-confidence frames

Why this is novel for this thesis:

- compute is spent conditionally based on target risk, not uniformly
- aligns with low-power edge constraints and control-critical tracking continuity

Expected benefit:

- improved recall of small/far targets
- lower lock drop probability at distance
- controlled latency increase through trigger budgeting

## Contribution C (Primary Systems Novelty)

Identity-confidence-aware control validity policy.

Core idea:

- combine target freshness, geometric validity, and identity confidence into one control validity score
- use score to enforce graded control behavior:
  - valid and confident: normal bounded control
  - uncertain identity: conservative gains and tighter saturation
  - invalid or stale: safe zero/hold

Why this matters:

- ties perception uncertainty directly to control safety
- makes the control chain thesis-defensible beyond pure perception metrics

Why this is primary (not secondary):

- this is what makes the thesis read as robotics/control rather than MOT-only tracking
- it turns identity uncertainty into explicit safety-aware control logic

## Supporting Mechanisms (Recommended)

### S1 — Event-triggered appearance extraction/use

Core idea:

- do not run appearance logic every frame
- trigger only when ambiguity/risk indicators are active (crossings, close candidates, recent loss, confidence drop)

Why include it:

- strong embedded efficiency story
- aligned with low-power runtime constraints

### S2 — View-quality-aware memory updates

Core idea:

- update target memory only when view quality is acceptable (size, confidence, border distance, blur proxy, no active ambiguity)

Why include it:

- prevents memory poisoning from poor visual evidence
- practical for outdoor UAV conditions

### S3 — Tiny-target gated identity policy (optional)

Core idea:

- when target is too small, down-weight appearance cues
- pause memory updates when identity evidence is weak

Why include it:

- explicitly handles known UAV failure modes for appearance reliability

## 4. Deep Research Work Package

For each candidate method or paper family, extract only decision-critical fields:

- where appearance enters pipeline
- descriptor dimension
- always-on vs ambiguity-only use
- matching metric
- compute overhead profile
- robustness pattern (occlusion, crossings, re-entry)
- feasibility on embedded onboard stack

Priority reading families:

- DeepSORT-style appearance-assisted online association
- BoT-SORT-style motion + appearance fusion
- efficient integrated appearance pipelines such as LITE-style approaches
- UAV-specific ReID limitations and domain-shift behavior

Output artifact:

- one comparative matrix with implementation risk and expected gain

## 5. Real Coding Roadmap (Frozen Order)

## Phase 1: Control Closure and MAVROS Closure

Deliverables:

- frozen control contract and frame semantics
- completed ground validation campaign
- GO / NO-GO gate decision process ready

Acceptance:

- control path is stable and safety behavior is verified for stale/lost target cases

## Phase 2: Instrumentation for Novelty Experiments

Deliverables:

- add explicit identity and reacquisition events to logs
- add lock continuity and reacquisition timers
- add confidence/state transition traces for control validity analysis

Acceptance:

- metrics are automatically produced from bag analysis

## Phase 3: Contribution A Implementation (Target-Specific Appearance Memory)

Implementation tasks:

- add compact embedding extractor path
- add target-memory bank with conservative update policy
- add ambiguity detector (motion/IoU conflict zone)
- add appearance-assisted reassociation only in ambiguity windows

Acceptance:

- measurable ID switch reduction on target of interest
- no unacceptable latency regression against baseline

Engineering constraints:

- fixed compute budget and bounded per-frame runtime
- no unbounded queue growth

## Phase 4: Contribution C Integration (Identity-Confidence-Aware Control Validity)

Implementation tasks:

- compute control validity from freshness + geometry + identity confidence
- map validity to control mode tiers
- enforce safe fallback rules and saturation limits
- add hysteresis to avoid confidence-threshold oscillation bursts

Acceptance:

- stale/lost/uncertain conditions produce expected safe behavior
- no unsafe command bursts across mode transitions

## Phase 5 (Optional): Contribution B Implementation (Selective Tiny-Target Refine)

Implementation tasks:

- define trigger conditions from target size/confidence/tracker risk
- run ROI refine path only on trigger
- fuse refined result into tracker update
- add trigger-rate and latency accounting

Acceptance:

- improved tiny-target lock continuity or reacquisition
- trigger budget stays within defined ceiling

## 6. Evaluation Design

## Metrics (Novelty-Critical)

Identity and tracking:

- ID switches on selected target
- reacquisition time after controlled occlusion
- lock continuity duration

Small-target robustness:

- target recall by size bins
- lock retention for far/tiny target segments
- refine trigger precision and duty cycle

System and control:

- end-to-end latency p50, p95, p99
- frame cadence stability
- invalid-to-safe command transition time
- command saturation frequency and burst behavior

## Comparative Experiments

Mandatory comparisons:

1. baseline tracker without appearance/refine
2. baseline + Contribution A
3. baseline + Contribution A + Contribution C
4. baseline + Contribution A + Contribution C + Contribution B (optional stretch)

For each comparison:

- report accuracy gain
- report latency/compute cost
- report control-safety side effects

## 7. Thesis Claims You Can Defend

If executed successfully, the thesis can claim:

1. a control-aware appearance strategy that improves target lock robustness under embedded constraints
2. an integrated perception-to-control validity policy that improves safety behavior under uncertainty
3. ambiguity-triggered appearance usage reduces identity cost while preserving embedded runtime
4. selective tiny-target refine can provide additional robustness when included as stretch

These claims are stronger than generic tracker benchmarking because they are tied to onboard control outcomes.

## 8. Risk Register and Mitigations

Risk 1: appearance overhead too high

- mitigation: ambiguity-only invocation and compact descriptor size

Risk 2: weak transfer of appearance cues in outdoor UAV views

- mitigation: conservative memory updates and fallback to motion/IoU baseline

Risk 3: selective refine increases latency tail

- mitigation: strict trigger budget and runtime watchdog

Risk 4: perception-confidence coupling causes control oscillation

- mitigation: hysteresis and mode-transition damping in control validity tiers

## 9. Next 3-Block Execution Plan

Block 1 (control closure)

- finish frozen control contract and GO/NO-GO gate
- complete ground safety validation cases

Block 2 (novelty instrumentation)

- implement identity/reacquisition/confidence transition instrumentation
- freeze experiment metrics and analysis pipeline

Block 3 (novelty implementation core)

- implement Contribution A with full instrumentation
- run first baseline-versus-A experiment set

Block 4 (systems novelty integration)

- implement Contribution C confidence-aware control tiers
- validate conservative/normal/hold behavior and hysteresis

Block 5 (optional stretch)

- implement Contribution B (or lighter quality-gated support only)
- run extended comparison matrix if time allows

## 10. Priority Ranking (Frozen)

Primary novelty (must deliver):

1. Contribution A: control-aware target-specific appearance memory
2. Contribution C: identity-confidence-aware control validity policy

Secondary novelty (deliver if on-track):

1. S1 event-triggered appearance use
2. S2 view-quality-aware memory updates

Stretch novelty (only with time margin):

1. control-driven reacquisition window
2. multi-timescale target memory
3. Contribution B selective tiny-target refine
4. tiny-target gated identity handling as a separate module

## 11. Best Thesis Package

Recommended coherent package:

- Novelty A (main algorithmic novelty): control-aware target-specific appearance memory
- Novelty C (main systems novelty): identity-confidence-aware control validity policy
- Optional enhancement: event-triggered appearance activation

This package is strong because it is:

- small enough to finish
- tightly tied to one selected target
- control-relevant rather than MOT-score-only
- feasible under onboard runtime constraints

Strong thesis story (freeze wording intent):

- standard trackers optimize scene-wide association quality
- this thesis proposes a lightweight selected-target identity mechanism and couples identity confidence to control validity so uncertain reassociation does not propagate overconfident or unsafe control actions

## 12. Defensible Thesis Claims

If results support them, use claim language similar to:

1. A lightweight target-specific appearance memory improves selected-target lock continuity and reacquisition under ambiguous association.
2. Ambiguity-triggered appearance usage reduces the cost of classic appearance-assisted tracking in embedded onboard operation.
3. Propagating identity confidence into control validity improves safety behavior in the perception-to-control chain.

Note:

- claim 3 is a proposed systems contribution derived from a literature gap; it should be presented as your method, not as a direct copy of prior tracker literature.

## 12.1 Success Criteria to Freeze Now

For Contribution A:

- fewer selected-target ID switches
- faster reacquisition after short occlusion
- longer lock continuity
- acceptable latency increase

For Contribution C:

- identity uncertainty causes safer control behavior
- stale/lost transitions are clean and deterministic
- no command bursts during confidence transitions
- control remains responsive when identity confidence is strong

For combined A + C package:

- better selected-target persistence without breaking onboard runtime constraints

## 13. Out-of-Scope / High-Risk Paths

Avoid in this thesis scope:

- full new tracker from scratch
- end-to-end transformer tracking redesign
- always-on ReID for all detections
- detector-integrated feature extraction as first implementation target
- large-model retraining-heavy paths

## 14. Final Recommendation

Freeze this hierarchy and avoid reopening novelty scope daily:

- A is the main algorithmic novelty
- C is the main systems novelty
- B is stretch-only if core A + C is stable

Why this sequencing is best:

- A gives the clearest identity and reacquisition novelty with realistic onboard feasibility
- C turns perception novelty into control-safety novelty, strengthening thesis defensibility
- S1/S2 improve efficiency and robustness without exploding implementation scope
