# Seq03 behavior-neutral shadow appearance probe

Date: 7 September 2026

This is development-only forensic evidence. It does not modify canonical
TIM-MARS behavior and it does not access H01/H02/H03.

## Purpose

The probe independently encoded tracker ID 9 on selected Seq03 frames
immediately before the normal TIM decision and compared that fresh embedding
against the actual pre-decision positive and committed hard-negative memory.

The shadow embedding was not supplied to the TIM appearance cache, protected
anchor, trusted gallery, adaptive prototype, hard-negative memory, state
transition logic, persistence logic or publication path.

## Behavior-neutrality gate

Reference replay generated semantic SHA-256:

    307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca

Shadow-probed replay generated semantic SHA-256:

    307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca

The semantic hashes are identical. All 14 requested probe frames were observed.

The retained machine-readable sidecar is:

    seq03_shadow_appearance_probe_20260907.json

## Fresh evidence after the first challenged rejection

Frame 1054 is still LOCKED before the decision. Fresh effective positive
similarity is 0.761, committed-negative similarity is 0.502 and the
positive-minus-negative margin is +0.259.

Frames 1055--1063 then provide fresh effective positive similarities from
0.793 to 0.887 while positive-minus-negative margins remain strongly positive,
from +0.241 to +0.275. The actual trajectory nevertheless progresses through
UNCERTAIN and then LOST.

The probe does not prove that all of these suppressed frames were safely
publishable. In particular, protected-anchor similarities remain weaker than
the recent gallery/adaptive support, and the real counterfactual trajectory
would change after any restored publication.

The evidence does establish that the later suppression cannot be explained
simply as absence of discriminative fresh MARS information.

## Physical handover region

Fresh evidence changes qualitatively at the physical tracker-ID handover:

- frame 1078: effective 0.731, negative 0.768, margin -0.037
- frame 1079: effective 0.648, negative 0.816, margin -0.168
- frame 1080: effective 0.650, negative 0.876, margin -0.227
- frame 1081: effective 0.687, negative 0.913, margin -0.226

The positive-minus-negative relationship therefore reverses around the real
identity transfer. This motivates mechanism-level review of how publication
state, continuity evidence, protected memory and negative evidence interact;
it does not justify replacing TIM with one margin threshold.

## Scientific consequence

A complete read-only static audit was subsequently performed before further
TIM redesign. It identified a plausible suppression feedback loop in which a
rejected observation can move the internal state away from LOCKED, exclude
adaptive appearance from authority scoring, stop LOCKED-only forced challenge
requests and freeze authoritative geometry, after which stricter recovery
rules apply.

That interaction is a development hypothesis to test through ablation. No new
canonical algorithm or prospective freeze is created by this forensic result.
