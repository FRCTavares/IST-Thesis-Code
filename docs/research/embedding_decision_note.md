# Appearance Integration Decision Note (Secondary Thesis Design Note)

Date: 2026-03-26
Scope: appearance integration choices that support, but do not define, thesis novelty

## Thesis Context

Main thesis question:

How can an onboard RGB-only perception pipeline for a micro-UAV be improved to maintain robust selected-target tracking of small and distant people in real time under strict embedded compute and latency constraints?

This note is a secondary design note for appearance support routes.

## Role of Appearance in the Thesis

Appearance is secondary.

- use appearance only when it improves ambiguity resolution or reacquisition
- keep detector/tracker tiny-person robustness as the primary algorithmic axis
- do not present appearance integration as the main novelty

## Appearance Route Definitions (Frozen)

### Full-Scene ReID Baseline

Design:

- per-detection descriptor extraction for scene-wide association support
- compare motion/IoU and appearance cues during association

Role:

- comparator baseline for analysis

Risks:

- higher per-frame runtime overhead
- possible latency tail growth under crowded scenes

### Detector-Feature Reuse Path

Design:

- reuse detector-side features for lightweight appearance signals
- reduce dependence on a standalone ReID branch

Role:

- high-risk research reference only

Risks:

- integration complexity on current stack
- uncertain feature access and maintainability

### Target-Memory Appearance Path

Design:

- maintain compact appearance memory for the selected target only
- invoke matching in ambiguity or short-loss windows
- use conservative, quality-gated memory updates

Role:

- secondary support module after primary tiny-person work is stable

Risks:

- added system complexity if invoked too frequently
- limited benefit if tiny-person detector/tracker errors dominate

## Implementation Priority

1. first implementation priority is tiny-person detector/tracker robustness work
2. Target-Memory Appearance Path is optional/secondary support once the main tiny-target path is stable
3. Full-Scene ReID Baseline is a comparator
4. Detector-Feature Reuse Path is high-risk reference only

## Decision Guidance

Use appearance routes to answer secondary questions:

- does appearance support reduce selected-target ID switches in ambiguity windows?
- does it improve reacquisition without violating latency bounds?
- is added complexity justified after Contribution A and Contribution C evidence is strong?

## Evidence Requirements for Appearance Use

- explicit ambiguity/reacquisition event accounting
- incremental runtime and latency measurements
- lock continuity comparison with and without appearance support
- no unsafe control behaviour introduced by identity-confidence changes

## Frozen Wording Guardrail

This document must not be used as the thesis headline document. Primary novelty remains tiny-person-aware detector/tracker robustness plus control-safe, latency-bounded integration.
