# Frozen TIM-MARS thesis research questions

Status: frozen on 24 July 2026

## Main research question

> Can a fully onboard RGB selected-person-following architecture combine computationally lightweight multi-object tracking with post-tracker identity validation to improve correct-target continuity and reduce controller-facing wrong-target publication during occlusions, crossings, temporary absences, re-entry, and tracker identity instability on a small UAV?

The main question joins two related but independently testable thesis
contributions:

1. a selected-target identity-memory contribution;
2. a fully onboard embedded-perception contribution.

The final thesis answer must report the evidence for each contribution
separately. Successful algorithmic evidence does not by itself prove onboard
feasibility, and successful onboard execution does not by itself prove
selected-target correctness.

## Algorithmic subquestion

> Can TIM-MARS, as a post-tracker selected-target identity-memory layer, improve correct-target continuity while reducing controller-facing wrong-target publication relative to the raw selected-target stream?

This subquestion evaluates whether an upper identity-validation layer can make
a computationally practical tracker more useful for selected-person following.

The intended benefit has two parts:

- increase or retain correct-target continuity;
- reduce controller-facing wrong-target publication.

Temporary lost or suppressed output is acceptable when identity evidence is
insufficient because publishing no target is safer than publishing a plausible
distractor.

## Embedded-deployment subquestion

> Can Hailo acceleration be extended from detection to appearance-embedding inference so that detection, lightweight tracking, appearance-supported identity validation, and controller-facing perception run fully onboard a Raspberry Pi 5 without external inference while meeting the required throughput, latency, thermal, power, and safety constraints?

This subquestion evaluates whether the complete perception and identity path
can operate on the aircraft without workstation, cloud, or ground-station
inference.

The intended architecture is:

1. RGB image capture onboard;
2. neural person detection accelerated by Hailo;
3. computationally lightweight multi-object tracking;
4. appearance-embedding inference accelerated by Hailo;
5. TIM-MARS selected-target identity validation;
6. controller-facing target publication;
7. ROS 2 and MAVROS integration on the onboard platform.

## Operational definitions

### Fully onboard

Fully onboard means that image capture, detection, tracking, appearance
embedding, selected-target validation, and controller-facing perception are
computed on hardware carried by the aircraft.

A ground station may display telemetry or video, but it must not perform
required detection, tracking, ReID, identity validation, or target-selection
inference.

### Computationally lightweight tracker

A computationally lightweight tracker is one selected for practical onboard
execution rather than maximum server-class multi-object tracking performance.

This phrase describes the architectural design target. It does not assert that
runtime, power, or thermal requirements have already been demonstrated.
Those measurements remain required under Issue #32.

### Post-tracker identity validation

TIM-MARS consumes candidates produced by an existing detector, tracker, and
raw target-selection path.

It is not:

- a detector;
- a replacement multi-object tracker;
- a new person ReID network;
- a generic MOT-accuracy method;
- a formal safety guarantee.

### Correct-target continuity

Correct-target continuity is the duration or proportion of valid
controller-facing output corresponding to the operator-selected physical
person.

It must be evaluated against the paired raw selected-target stream using the
same tracker, sequence, annotation, timebase, and configuration.

### Wrong-target publication

Wrong-target publication occurs when valid controller-facing output
corresponds to a person other than the operator-selected physical target.

Ground-truth annotations and evaluation oracles are used offline only. The
live system does not receive a reference identity or evaluation oracle.

### Recoverable identity instability

The evaluated failure modes include:

- short occlusion;
- ambiguous crossing;
- tracker-ID change;
- track fragmentation;
- temporary absence;
- re-entry;
- nearby distractors;
- selected-target handover risk.

Recoverable means that a plausible representation of the selected physical
person exists again. The thesis does not claim recovery when no correct
candidate exists.

### Hailo appearance offload

The target deployment extends Hailo use from detector inference to
appearance-embedding inference.

The Hailo appearance claim is not complete until Issue #44 demonstrates:

- model conversion and deployment;
- acceptable quantisation or embedding degradation;
- stable identity-ranking behaviour;
- detector and appearance scheduling on the accelerator;
- no unacceptable wrong-target regression.

## Evidence and dependency boundaries

### Current algorithmic evidence

The current development evidence supports only a narrow paired statement:
the frozen TIM-MARS configuration reduced wrong-target duration relative to
the paired raw selected-target stream under both retained offline evaluation
methods.

That evidence is:

- development-only;
- tracker-, sequence-, configuration-, annotation-, and oracle-specific;
- not flawless;
- not tracker-independent;
- not final held-out evidence.

### Final held-out evidence

Issue #27 owns the prospective H01-H03 held-out recordings and remains
schedule-blocked until September 2026.

The final answer to the algorithmic subquestion must not be frozen before the
held-out gate passes.

### Onboard runtime evidence

Issue #32 owns throughput, latency, CPU load, accelerator load, memory,
temperature, power, and sustained runtime evidence.

The words fully onboard and computationally lightweight do not remove the need
for those measurements.

### Hailo appearance evidence

Issue #44 owns selection of the appearance approach and promotion of the
selected model to Hailo.

Until Issue #44 closes, the thesis may describe Hailo appearance offload as a
research objective and implementation target, not a completed result.

### Final thesis claim

Issue #39 owns the final contribution statement after the held-out and
embedded-deployment evidence is complete.

## Literature-gap boundary

The intended literature gap is the combination of:

- fully onboard RGB selected-person following;
- a Raspberry Pi 5-class companion computer;
- Hailo-accelerated neural inference;
- a computationally lightweight tracker;
- appearance-supported selected-target identity recovery;
- controller-facing output without external inference.

The thesis must support this gap using a documented literature review.

It must use wording such as "to the best of our knowledge" unless the search
method justifies a stronger statement. It must not claim that no related
Raspberry Pi, Jetson, UAV-tracking, ReID, or edge-inference system exists.

## Claim exclusions

The frozen questions do not assert:

- zero wrong-target output;
- flawless recovery;
- universal tracker portability;
- recovery through arbitrary long absence;
- discrimination between identical-looking people in every condition;
- formal flight-safety guarantees;
- completed Hailo appearance inference;
- completed held-out generalisation;
- completed runtime, thermal, or power validation;
- superiority over all Jetson- or workstation-based systems.

## Final framing

The thesis investigates whether a resource-constrained onboard platform can
achieve useful selected-person following by combining:

- fast neural inference on a dedicated accelerator;
- a computationally practical tracker;
- conservative post-tracker identity memory.

The contribution is the complete architecture and its measured trade-offs,
not an unsupported claim that every lightweight tracker becomes reliable in
every environment.
