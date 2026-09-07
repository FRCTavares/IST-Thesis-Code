# TIM-MARS static algorithm audit and ablation design

Date: 7 September 2026

Status: development design; no held-out evidence accessed.

## Static complexity census

The complete read-only census found:

- 120 scoped configuration/interface fields;
- 114 ROS parameter declarations;
- 89 fields explicitly present in the canonical YAML;
- 56 active canonical algorithmic fields;
- 58 active algorithmic fields in the selected available-image resilience candidate;
- 44 active configured numerical policy fields;
- seven additional active hard-coded numerical policy sites;
- approximately 20 active canonical conceptual mechanisms, or 21 with the
  selected fresh-challenge mechanism.

These counts describe the reachable software policy surface, not independent
statistical degrees of freedom. The apparent hundred-plus-field complexity
also includes operational bounds, disabled experiments, diagnostics and legacy
interfaces. Nevertheless, the active policy surface is sufficiently large to
require mechanism-level ablation before another final TIM freeze.

## Principal static findings

The audit found that publication state, evidence eligibility and recovery are
strongly coupled.

A rejected proposal can move LOCKED to UNCERTAIN and eventually LOST.
UNCERTAIN/LOST scoring excludes adaptive positive support. LOCKED-only fresh
identity challenges stop on subsequent frames. Authoritative selected bbox
geometry advances only on accepted authority. Global geometry-bypass recovery
requires LOST and its separate entry conditions.

This is not an unconditional causal failure on every sequence, but together
with the retained Seq03 shadow evidence it creates a concrete self-inflicted
LOST hypothesis.

Additional findings include:

- the selected `same_id_fresh_challenge_enabled` behavior bundles fresh
  scheduling with removal of a general same-ID committed-negative exemption;
- `rank_aware_confirm_frames=1` is currently dominated by the general recovery
  persistence requirement;
- repeated cached appearance can advance several counters or memory updates
  without requiring a distinct source image;
- over-age committed hard negatives remain scoreable until a qualifying
  accepted transaction performs retirement;
- the conservative appearance filter has a reachable non-monotonic activation
  boundary because weak unused appearance can avoid a filter that stronger
  used appearance activates;
- proposal routing can terminate after an earlier route/proposal rejection
  without evaluating every later alternative;
- dataclass defaults, ROS defaults and canonical configuration are not
  interchangeable reproduction authorities.

## Stage-1 ablation menu

The selected available-image candidate is the primary development reference.
Canonical TIM remains a separate reference.

Independent Stage-1 interventions:

- AB-01: remove appearance contribution to ranking only.
- AB-04: disable short-gap same-ID priority.
- AB-05: disable short-gap new-ID suppression.
- AB-06: disable the conservative final appearance filter while retaining
  global-recovery margin checks.
- AB-07: remove trusted-gallery storage from clean initialization.
- AB-08: remove adaptive positive representation and its updates while
  preserving anchor/gallery behavior.
- AB-09: disable hard-negative memory.
- AB-10: remove only the challenger-gated positive-support hijack rejection
  while retaining negative rejection.
- AB-11: disable forced fresh challenge scheduling only while retaining the
  universal committed-negative veto.
- AB-12: disable global reacquisition.
- AB-13: disable rank-aware reacquisition.
- AB-14: remove the extra general recovery-confirmation observation.
- AB-15: retire over-age hard negatives before candidate scoring rather than
  only through trusted acceptance.
- AB-16: prevent repeated-source adaptive EMA reinforcement only.
- AB-18: restore the canonical general same-ID negative exemption while
  retaining fresh challenge scheduling and the earlier challenger-specific
  negative check.
- AB-19: require distinct source-image evidence to advance persistence while
  retaining the required observation count and all safety gates.

The previous AB-02 geometry-ranking proposal was removed because it did not
define a coherent independent intervention. The previous AB-03 same-ID
privilege group is retained only as a reduced-architecture dependency block.
The previous AB-17 publication/lineage-state coupling question is moved to a
later coherent R3 architecture comparison.

## Execution order

1. Establish exact development-control provenance and source-evidence
   attribution.
2. Execute AB-11 and AB-18 first to separate the currently bundled fresh
   scheduling and universal same-ID negative-veto effects.
3. Evaluate AB-09, AB-10 and AB-06 to resolve the principal identity-safety and
   suppression mechanisms.
4. Evaluate AB-08 and AB-07 independently. Run AB-16 only if adaptive memory
   remains relevant.
5. Evaluate recovery/persistence mechanisms AB-12, AB-13, AB-04, AB-05,
   AB-14 and conditionally AB-19.
6. Evaluate AB-15 only if negative memory remains useful and over-age veto
   opportunities exist.
7. Evaluate AB-01 independently after the principal safety architecture is
   understood.
8. Assemble reduced architectures only after individual ablation results.

The Stage-1 design is implementation-ready. A later continuity-aware R3 design
requires prospectively defined lineage motion/time bounds based only on the
permitted development sequences.

## Evaluation constraints

Use only May hard re-entry, Seq01 clean, Seq03 crossing and Seq04
occlusion/absence. Preserve source candidate-stream hashes, source/reference
hashes, exact resolved configuration, MARS model provenance and the unchanged
physical-v2 evaluator.

Primary interpretation remains safety-first without collapsing the result into
one weighted scalar:

correct target > LOST/HOVER > wrong target.

A reduced mechanism is not acceptable if it creates new wrong-person authority,
target-absence leakage or credible wrong-source memory contamination merely to
increase correct-target duration.

H01/H02/H03 remain reserved pending capture and were not inspected. Historical
split/comparison freezes remain unchanged.
