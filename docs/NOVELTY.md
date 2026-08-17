# TIM-MARS Research Position and Novelty Contract

## 1. Purpose

This file defines what TIM-MARS is intended to contribute, what the current evidence supports, and what must still be demonstrated before making the final thesis claim.

TIM-MARS is a control-facing selected-target identity validation layer for RGB-only UAV person following.

## Frozen research-question structure

### Main research question

> Can a fully onboard RGB selected-person-following architecture combine computationally lightweight multi-object tracking with post-tracker identity validation to improve correct-target continuity and reduce controller-facing wrong-target publication during occlusions, crossings, temporary absences, re-entry, and tracker identity instability on a small UAV?

### Algorithmic subquestion

> Can TIM-MARS, as a post-tracker selected-target identity-memory layer, improve correct-target continuity while reducing controller-facing wrong-target publication relative to the raw selected-target stream?

### Embedded-deployment subquestion

> Can Hailo acceleration be extended from detection to appearance-embedding inference so that detection, lightweight tracking, appearance-supported identity validation, and controller-facing perception run fully onboard a Raspberry Pi 5 without external inference while meeting the required throughput, latency, thermal, power, and safety constraints?

The canonical operational definitions, evidence dependencies, and claim exclusions are maintained in `docs/research_question.md`.

The algorithmic and embedded-system contributions must be evaluated separately. The dedicated Hailo appearance-offload work under Issue #44 is complete, but current development results do not close the held-out, end-to-end runtime, thermal, power, comparison, or final-claim obligations.

It is not:

- a detector;
- a multi-object tracker;
- a new person ReID network;
- a formal safety guarantee;
- a solution to arbitrary long-term person re-identification.

## 2. Research problem

A multi-object tracker may continue producing plausible tracks while assigning the selected person the wrong identity after:

- crossings;
- occlusion;
- track fragmentation;
- tracker-ID changes;
- disappearance and re-entry;
- interaction with distractors.

For generic tracking, this is an association error.

For UAV person following, a valid-looking wrong target may produce a command toward the wrong person.

The selected-target objective is therefore asymmetric:

1. minimise wrong-target publication;
2. retain correct-target publication;
3. accept temporary loss when identity evidence is insufficient.

The central controller-facing design principle is:

> A temporarily lost target is preferable to a confidently published wrong target.

A conceptual control-oriented loss is:

    J = C_wrong T_wrong + C_lost T_lost + C_switch N_switch

subject to:

    C_wrong > C_lost

This expresses the asymmetric controller-facing cost ordering. It is not a formal safety proof, and the coefficients must not be presented as universal constants unless experimentally justified.

## 3. Research gap

The thesis does not claim novelty from the mere combination of object
detection, multi-object tracking, person ReID, geometric consistency, temporal
memory, state machines, or appearance comparison. Those mechanisms are
established, and recent work on target-person tracking and robot person-following
already addresses designated-person persistence, occlusion, disappearance,
reappearance, and appearance-supported re-identification.

The narrower problem is the **authority gap** between generic multi-object
association and controller-facing target authority for one operator-selected
physical person.

A tracker maintains candidate trajectories and temporary association labels.
For selected-person UAV following, however, a plausible tracker output is not
by itself sufficient evidence that the same physical person originally
selected by the operator should retain controller-facing target authority.

The research gap investigated here is therefore whether a resource-constrained
UAV architecture can:

1. keep generic multi-object association computationally practical;
2. treat tracker identity as evidence rather than controller-facing target
   authority;
3. maintain persistent evidence about one selected physical person across
   tracker-ID instability;
4. deliberately abstain from publication when identity evidence is
   insufficient;
5. recover controller-facing authority only after bounded confirmation; and
6. achieve a useful wrong-target–availability–compute trade-off fully
   onboard.

This framing must be positioned against target-person tracking,
person-following, MOT-plus-ReID, appearance-aware trackers, and embedded UAV
perception systems. The thesis does not claim that these neighbouring research
problems are new.

## 4. Intended contribution

The intended contribution is a **controller-facing selected-person
identity-validation architecture**, not a new detector, tracker, or ReID
network.

Its central design decision is to decouple generic association continuity
from physical-target publication authority: the tracker estimates candidate
trajectories and temporary identities, while TIM-MARS separately decides
whether one candidate may represent the operator-selected physical person to
the downstream controller.

### 4.1 Association is evidence, not authority

TIM-MARS operates after person detection, multi-object tracking, and raw target
selection.

The tracker proposes candidate observations and temporary identities. TIM-MARS
independently determines whether a candidate is sufficiently supported as the
operator-selected physical person for controller-facing publication.

A tracker ID may contribute evidence, but it does not automatically obtain or
retain controller authority.

### 4.2 Persistent physical-target evidence

TIM-MARS maintains trusted evidence about the selected person across
recoverable tracker instability.

The implemented evidence may include:

- trusted tracker-lineage information;
- target geometry and quality;
- temporal state and continuity;
- positive selected-person appearance evidence;
- distractor or hard-negative appearance evidence.

These mechanisms are implementation components. The novelty claim is not that
any one of them is individually new, but how they support the authority
decision for one selected physical person.

### 4.3 Conservative abstention and bounded recovery

TIM-MARS is permitted to suppress output even when the detector or tracker
provides a plausible candidate.

This is deliberate. Under the thesis objective, temporary loss of target
authority is preferable to publishing a distractor when identity evidence is
insufficient.

Recovery is therefore not simply the first plausible reassociation. Candidate
authority must be re-established according to the implemented evidence and
confirmation policy.

Issue #74 extends this same authority principle into the state-aware
controller-facing following and bounded visual-recovery path. That work must
not create an alternative source of selected-person identity authority.

### 4.4 Asymmetric controller-facing evaluation

The evaluation separates:

- correct-target publication;
- wrong-target publication;
- lost or intentionally suppressed output;
- target-absent-but-output behaviour;
- reacquisition and recovery delay;
- unsafe handovers and wrong-target bursts;
- event-specific failure and recovery behaviour.

This differs from treating generic MOT accuracy as sufficient evidence for a
person-following controller.

The terminology is safety-oriented but not a formal safety claim. Here,
*safety* refers specifically to controller-facing wrong-person risk and its
trade-off with temporary target unavailability.

### 4.5 Embedded selected-person architecture

The intended deployment pairs TIM-MARS with a computationally practical,
appearance-free tracker and performs appearance reasoning selectively at the
selected-person validation layer.

The dedicated Hailo appearance-offload implementation and validation under
Issue #44 are complete.

The remaining embedded-systems hypothesis is:

> A lightweight tracker paired with selective selected-person validation can
> provide a competitive or preferable controller-facing
> wrong-target–availability–compute operating point relative to integrated
> appearance-aware tracking.

This is still a hypothesis, not a supported final result. Issue #58 owns the
controlled tracker comparison, and Issue #32 owns the final end-to-end
latency, invocation, resource, thermal, power, and sustained-operation
characterisation.

## 5. Minimal defensible final algorithm

The final algorithmic claim should contain only mechanisms that survive the
remaining controlled evaluation and final implementation freeze.

The core authority structure is:

1. one persistent trusted selected-person memory;
2. geometric candidate plausibility;
3. positive appearance evidence;
4. distractor-aware appearance comparison where retained by evidence;
5. temporal confirmation for recovery;
6. one final controller-authority decision;
7. conservative state transition and publication; and
8. trusted-only memory adaptation.

Motion evidence under Issue #21 and higher-resolution appearance evidence
under Issue #64 are additions only if they improve the supported
wrong-target–availability trade-off without creating unacceptable complexity
or new failure modes.

Parallel recovery paths or experimental policies that do not survive the final
evaluation must not remain part of the thesis contribution.

## 6. Evidence status

Exact numeric results, hashes, configuration fingerprints, and
evidence-version relationships do not belong in this novelty contract.

Their authorities are:

- `docs/results/`;
- `docs/algorithm/tim_mars_evidence_versions.md`;
- frozen experiment and split contracts under `docs/data/`;
- exact GitHub issue closure evidence where applicable.

This document records only the scientific interpretation and claim boundary.

### 6.1 Evidence already established

The repository already contains development evidence showing that:

- TIM-MARS can substantially change the controller-facing
  correct/wrong/lost operating point relative to the paired raw selected-target
  stream;
- appearance evidence is necessary in evaluated difficult cases where geometry
  or persistence alone can authorise the wrong lineage;
- software-interface modularity does not imply one-preset safety portability
  across trackers;
- some availability improvements can be unacceptable when they also increase
  wrong-target publication;
- event/recovery metrics and promoted development ablations exist;
- broader-sequence evaluation has been completed;
- parameter-sensitivity evaluation has been completed;
- the dedicated Hailo appearance-offload work under Issue #44 has been
  completed.

These are development and implementation findings. They do not by themselves
close the final prospective held-out or full embedded-deployment claims.

### 6.2 Evidence still required before the final claim

The remaining scientific gates are:

- **Issue #25** -- strengthen identity-independent bounding-box evaluation;
- **Issue #64** -- determine whether higher-resolution source imagery
  materially improves selected-person appearance evidence;
- **Issue #21** -- retain motion evidence only if controlled evaluation shows
  a useful contribution;
- **Issue #58** -- compare the intended lightweight-tracker-plus-TIM-MARS
  architecture with integrated appearance-aware tracking;
- **Issue #74** -- complete and validate the state-aware controller-facing
  architecture without weakening TIM-MARS identity authority;
- **Issue #32** -- complete end-to-end onboard runtime, resource, thermal,
  power, invocation, and sustained-operation characterisation;
- **Issue #27** -- capture, freeze, and evaluate the prospective H01--H03
  held-out sequences without leakage;
- **Issue #39** -- freeze the final thesis contribution only after the
  preceding evidence is available.

Thesis method, limitations, figures, and final prose under Issues #40--#42 must
then describe the implementation and evidence that actually survives these
gates.

## 7. Claim currently supported

The current evidence supports a bounded claim:

> TIM-MARS implements a separate controller-facing selected-person
> identity-validation decision above an existing tracking pipeline. Development
> evidence shows that this additional authority layer can materially alter
> correct-target availability and wrong-target publication under recoverable
> tracker identity instability, while also showing that its behaviour is
> tracker-, sequence-, and configuration-dependent.

Two conclusions are already important:

- modularity at the tracker-output interface is established;
- universal one-preset safety portability is not established and has been
  rejected by development evidence.

The evidence does **not** yet support a final claim that TIM-MARS generalises
across unseen people and scenarios, nor that the complete
lightweight-tracker-plus-TIM-MARS architecture is computationally preferable
to integrated appearance-aware tracking.

## 8. Novelty risks and scientific limitations

### 8.1 Individual mechanisms are established

Geometry, tracker continuity, cosine similarity, person ReID, temporal
confirmation, state machines, and distractor memories are not individually
claimed as novel.

The thesis contribution must therefore be defended at the level of the
controller-authority formulation, asymmetric objective, architecture,
decision policy, and measured system trade-offs.

### 8.2 Abstention creates a real safety–availability trade-off

Reducing wrong-person publication by suppressing uncertain output can reduce
target availability.

Conversely, aggressively recovering continuity can increase wrong-target
authority.

Results must therefore report both dimensions. An availability improvement is
not automatically a successful result when wrong-target publication worsens.

### 8.3 Interface modularity is not behavioural portability

TIM-MARS can consume a common tracker-output contract, but its decisions depend
on the candidate trajectories produced by the upstream detector and tracker.

Every promoted tracker/configuration pairing therefore requires its own
evidence. Results from one tracker must not be generalized to untested
trackers.

### 8.4 Selected-person evidence has perceptual limits

Appearance evidence can become unreliable under poor crops, limited
resolution, viewpoint change, occlusion, visually similar clothing, or
insufficient observations.

Issue #64 specifically tests whether better source resolution improves this
evidence. The thesis must retain only limitations that remain true after that
work is complete.

No appearance method used here establishes biometric identity.

### 8.5 Evaluation authority must become more identity-independent

Development evaluation includes tracker-ID-dependent annotation paths and
complementary spatial evaluation.

Issue #25 exists because the final thesis should rely as little as practical
on the same tracker identity labels whose instability TIM-MARS is designed to
handle.

The final claim must state exactly which oracle and annotation contract support
each result.

### 8.6 Embedded-cost superiority remains unproven

The intended architecture is motivated partly by selective appearance
reasoning rather than continuous appearance association for every candidate.

That does not establish a computational advantage.

Issue #58 and Issue #32 must jointly measure the relevant
wrong-target–availability–compute trade-off using comparable workloads and
clearly separated runtime/resource measurements.

### 8.7 Formal flight safety is outside scope

TIM-MARS can reduce or suppress controller-facing wrong-person target
publication, but it does not formally verify aircraft safety.

The thesis does not claim certified functional safety, collision avoidance,
formal controller stability, or elimination of all unsafe commands.

## 9. Non-claims

TIM-MARS does not claim to:

- invent generic target-person tracking;
- invent person ReID or appearance embeddings;
- replace the multi-object tracker;
- improve generic MOT metrics in every setting;
- recover a target when no correct candidate exists;
- solve arbitrary long-term person re-identification;
- distinguish identical-looking people in every condition;
- eliminate all wrong-target publication;
- provide universal tracker portability;
- provide formal flight-safety guarantees;
- generalise beyond the evaluated evidence;
- outperform all appearance-aware trackers;
- be computationally cheaper than integrated appearance-aware tracking before
  Issues #58 and #32 provide the required evidence.

## 10. Final claim gates

### Completed or already promoted

The final thesis may build on the repository's existing:

- event and recovery evaluation framework;
- development component-ablation evidence;
- broader-sequence evaluation;
- parameter-sensitivity study;
- evidence-version and provenance contracts;
- Hailo appearance-offload implementation and validation from Issue #44;
- existing controller-authority, coordinate, freshness, and live-system
  validation evidence.

Exact values and version boundaries must be taken from the promoted evidence
documents rather than copied into this novelty contract.

### Still open

Before Issue #39 freezes the contribution, the thesis still requires the
remaining evidence owned by:

1. Issue #25;
2. Issue #64;
3. Issue #21, if motion evidence is retained;
4. Issue #58;
5. Issue #74;
6. Issue #32;
7. Issue #27.

A completed item must not remain described as future work merely because it
appeared in an older planning version of this document.

## 11. Target contribution statement

The target contribution statement is:

> This thesis introduces TIM-MARS, a controller-facing selected-person
> identity-validation layer for RGB-only UAV person following. Rather than
> treating a tracker identity as sufficient controller-facing target authority,
> TIM-MARS decouples generic multi-object association from the decision to
> publish one operator-selected physical person to the downstream controller.
> It maintains trusted selected-person evidence across recoverable tracker
> identity instability and combines temporal continuity, geometric
> plausibility, pretrained appearance evidence, distractor evidence, and
> conservative confirmation to either
> authorise a candidate or abstain from publication when identity evidence is
> insufficient.

The associated algorithmic evaluation uses an asymmetric controller-facing
objective in which wrong-person publication is reported separately from
temporary target unavailability, together with recovery and failure behaviour.

The embedded contribution evaluates whether selective identity reasoning above
a computationally practical tracker can operate fully onboard and provide a
useful wrong-target–availability–compute operating point relative to
integrated appearance-aware tracking.

The first paragraph describes the intended architectural contribution. The
second describes the evaluation contribution. The third remains provisional
until Issues #58 and #32 provide the required comparative and embedded-system
evidence.

Final wording must be frozen only under Issue #39 after the prospective
held-out evidence and remaining embedded-system results are available.
