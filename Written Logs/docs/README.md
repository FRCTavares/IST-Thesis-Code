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

## Document Roles

- [planning/thesis_plan.md](planning/thesis_plan.md): top-level thesis scope, deliverables, and evaluation framing.
- [control/control_interface.md](control/control_interface.md): frozen perception-to-control contract and MAVROS-facing control assumptions.
- [control/first_outdoor_control_gate.md](control/first_outdoor_control_gate.md): pass/fail gate for supervised outdoor control tests.
- [research/novelty_plan.md](research/novelty_plan.md): frozen novelty hierarchy and implementation sequence.
- [research/embedding_decision_note.md](research/embedding_decision_note.md): concise novelty rationale and research decision snapshot.
- [research/literature_reading_matrix.md](research/literature_reading_matrix.md): paper extraction matrix feeding implementation choices.

## Frozen Novelty Hierarchy

- Contribution A: main algorithmic novelty (target-specific appearance memory)
- Contribution C: main systems novelty (identity-confidence-aware control validity)
- Contribution B: stretch-only robustness extension (tiny-target selective refine)

## Naming Rules (To Avoid Confusion)

- Use `Contribution A/B/C` only for thesis contributions defined in novelty docs.
- Use `Option O1/O2/O3` for appearance design alternatives in research review:
  - O1: lightweight ReID branch
  - O2: detector-integrated appearance features
  - O3: target-only appearance memory

## Maintenance Rules

- Keep control safety constraints synchronized across:
  - [control/control_interface.md](control/control_interface.md)
  - [control/first_outdoor_control_gate.md](control/first_outdoor_control_gate.md)
- Keep novelty hierarchy synchronized across:
  - [research/novelty_plan.md](research/novelty_plan.md)
  - [research/embedding_decision_note.md](research/embedding_decision_note.md)
  - [research/literature_reading_matrix.md](research/literature_reading_matrix.md)
