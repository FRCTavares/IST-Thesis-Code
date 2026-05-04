# Docs Index

Last updated: 2026-03-26

This folder contains the active thesis planning and control-validation reference documents.

## Canonical Order (Read First)

1. [planning/thesis_plan.md](planning/thesis_plan.md)
2. [control/control_interface.md](control/control_interface.md)
3. [control/first_outdoor_control_gate.md](control/first_outdoor_control_gate.md)
4. [research/novelty_plan.md](research/novelty_plan.md)
5. [research/embedding_decision_note.md](research/embedding_decision_note.md)
6. [research/literature_reading_matrix.md](research/literature_reading_matrix.md)
7. [research/contradiction_log.md](research/contradiction_log.md)
8. [research/claim_to_evidence.md](research/claim_to_evidence.md)
9. [research/open_decisions_for_supervisor.md](research/open_decisions_for_supervisor.md)

## Document Roles

- [planning/thesis_plan.md](planning/thesis_plan.md): top-level thesis scope, deliverables, and evaluation framing.
- [control/control_interface.md](control/control_interface.md): frozen perception-to-control contract and MAVROS-facing control assumptions.
- [control/first_outdoor_control_gate.md](control/first_outdoor_control_gate.md): pass/fail gate for supervised outdoor control tests.
- [research/novelty_plan.md](research/novelty_plan.md): frozen novelty hierarchy and implementation sequence.
- [research/embedding_decision_note.md](research/embedding_decision_note.md): secondary design note for appearance integration routes.
- [research/literature_reading_matrix.md](research/literature_reading_matrix.md): paper extraction matrix for tiny/far robustness and embedded feasibility decisions.
- [research/contradiction_log.md](research/contradiction_log.md): replacement wording for legacy novelty phrasing.
- [research/claim_to_evidence.md](research/claim_to_evidence.md): major claim mapping to required evidence and metrics.
- [research/open_decisions_for_supervisor.md](research/open_decisions_for_supervisor.md): unresolved supervisory decisions and required confirmations.

## Frozen Novelty Hierarchy

- Contribution A: main algorithmic novelty (tiny-person-aware detector/tracker improvement)
- Contribution C: main systems novelty (control-safe, latency-bounded integration)
- Contribution B: secondary identity robustness module (target-specific appearance support)

## Naming Rules (To Avoid Confusion)

- Use `Contribution A/B/C` only for thesis contributions defined in novelty docs.
- Use the frozen appearance route names in active docs:
  - Full-Scene ReID Baseline
  - Detector-Feature Reuse Path
  - Target-Memory Appearance Path

## Maintenance Rules

- Keep control safety constraints synchronized across:
  - [control/control_interface.md](control/control_interface.md)
  - [control/first_outdoor_control_gate.md](control/first_outdoor_control_gate.md)
- Keep novelty hierarchy synchronized across:
  - [research/novelty_plan.md](research/novelty_plan.md)
  - [research/embedding_decision_note.md](research/embedding_decision_note.md)
  - [research/literature_reading_matrix.md](research/literature_reading_matrix.md)
  - [research/contradiction_log.md](research/contradiction_log.md)
  - [research/claim_to_evidence.md](research/claim_to_evidence.md)
  - [research/open_decisions_for_supervisor.md](research/open_decisions_for_supervisor.md)
