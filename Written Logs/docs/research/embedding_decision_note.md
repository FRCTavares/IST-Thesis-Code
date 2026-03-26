# Embedding Research Decision Note

Date: 2026-03-26
Scope: research-first with direct implementation targeting

## Thesis Question

Can a lightweight target-specific appearance embedding reduce ID switches and improve reacquisition without violating latency constraints?

## Intended Use of Appearance

Appearance is secondary, not primary:

- first use motion and IoU gates
- invoke appearance only when association is ambiguous
- prioritize target-lock and reacquisition outcomes over full-scene MOT elegance

## Candidate Designs

Naming convention for this file:

- `Option O1/O2/O3` = appearance design alternatives
- `Contribution A/B/C` = thesis contribution hierarchy (defined in novelty plan)

### Option O1 — Lightweight ReID Branch (Classic)

Design:

- per-detection 8D to 32D embedding descriptor
- association uses motion gate + IoU gate + cosine distance
- appearance used only on ambiguity

Pros:

- easy to explain and benchmark
- strong literature alignment

Risks:

- added per-detection compute overhead

### Option O2 — Detector-Integrated Appearance Features

Design:

- reuse detector features for appearance cue
- avoid standalone ReID model pass

Pros:

- potentially lower incremental overhead

Risks:

- implementation risk on current onboard/Hailo stack
- feature access and integration complexity

### Option O3 — Target-Only Appearance Memory

Design:

- maintain compact appearance memory only for selected target
- conservative memory update while confidence is high
- use appearance for reacquisition/ambiguity resolution only

Pros:

- best alignment with target-following control objective
- likely best compute tradeoff on Pi 5

Risks:

- less direct comparability to generic MOT pipelines

## Current Recommendation

Research Option O3 first, then compare to Option O1 baseline in thesis analysis.

Rationale:

- objective is stable target-relative following of one chosen person
- target lock and reacquisition matter more than global MOT ranking
- computational risk is lower than full per-detection appearance cues

## Right Novelty Shape (Frozen)

The novelty is not "adding embeddings".

The novelty is how appearance is used in a control-coupled embedded system:

- target-specific memory instead of full-scene appearance tracking
- ambiguity-only/event-triggered usage instead of always-on usage
- identity confidence propagated into control validity behavior

## Priority Ranking

Primary novelty:

1. target-specific appearance memory
2. identity-confidence-aware control policy

Secondary novelty:

1. event-triggered appearance extraction/use
2. view-quality-aware memory updates

Stretch novelty:

1. control-driven reacquisition window
2. multi-timescale memory
3. tiny-target gated identity handling

## Best Thesis Package

- Main algorithmic novelty: control-aware target-specific appearance memory
- Main systems novelty: identity-confidence-aware control validity policy
- Optional efficiency enhancement: event-triggered appearance activation

Contribution hierarchy (frozen):

- Contribution A: main algorithmic novelty
- Contribution C: main systems novelty
- Contribution B: stretch-only extension

## High-Risk Paths to Avoid

- full new tracker from scratch
- always-on ReID for all detections
- detector-integrated feature extraction as first implementation target
- retraining-heavy large-model path as primary strategy

## Literature Extraction Template

For each paper/tracker family, extract:

- where appearance enters the pipeline
- descriptor dimension
- always-on vs ambiguity-only usage
- matching metric (cosine, L2, etc.)
- compute cost and runtime implications
- main robustness gains (occlusion, crossings, re-entry)
- realism for onboard deployment

## Short Reading Queue

- DeepSORT-style online appearance-assisted tracking
- BoT-SORT motion + appearance fusion
- LITE-style efficient integrated appearance extraction
- one to two UAV-focused ReID constraints papers

## Decision Deliverable for This Block

Produce a 1-page design selection memo containing:

- selected option and why
- integration point in current tracker/selector path
- expected latency risk
- evaluation metrics for thesis (ID switches, reacquisition time, lock continuity, latency impact)
