# TIM-MARS Stage-3 architecture decision — AB-16 production promotion — 8 September 2026

Development-only decision record. **H01/H02/H03 were not accessed, captured or
inspected.** The Issue #27 frozen contracts
(`docs/data/splits/tim_mars_split_v3.json`,
`docs/data/splits/tim_mars_final_comparison_v2.json`,
`docs/flight/P027_HELDOUT_EXECUTION_PLAN.md`) are untouched. **This is not the
Stage-7 prospective freeze**: no new prospective algorithm/configuration/split/
comparison freeze is created here, and none is authorised until the combined
AB-16 production regression is reviewed.

## 1. Inputs

- Stage-1 mechanism-ablation development checkpoint merged as PR #100 at
  `d3edbcc537b92f5ef66771911015e620fc7467d2`.
- Selected development baseline configuration:
  `docs/results/selected_target_tracking/tim_resilience_development_20260907/available_image_challenge.yaml`.
- Stage-1 evidence:
  `tim_ablation_stage1_2x2_20260907.{md,json}`,
  `tim_ablation_stage1_mechanisms_20260908.{md,json}`,
  `tim_ablation_stage1_positive_memory_20260908.{md,json}`,
  `tim_ablation_stage1_recovery_ranking_20260908.{md,json}`,
  `tim_pinned_replay_semantic_rebaseline_20260908.{md,json}`.

## 2. Decision

Promote exactly one Stage-1 mechanism: **AB-16 — source-aware adaptive
positive-memory updates.**

The selected development baseline remains the algorithm. The new canonical
configuration `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
materialises that baseline exactly and additionally enables AB-16:

| Parameter | Canonical value | Note |
| --- | --- | --- |
| `min_confirm_frames_after_reacquire` | `1` | unchanged; AB-14 **not** promoted |
| `same_id_fresh_challenge_enabled` | `true` | selected development baseline |
| `same_id_challenge_available_images_only` | `true` | selected development baseline |
| `appearance_gallery_consensus_recovery_enabled` | `false` | selected development baseline |
| `appearance_prevent_repeated_source_adaptive_update` | `true` | AB-16 production promotion |

The only value that differs between the previous canonical configuration and the
selected development baseline plus AB-16 is the three baseline challenge keys
(previously absent, resolving to their `false` defaults) and the new AB-16 key.
No numerical threshold was tuned.

## 3. AB-16 production invariant

An eligible adaptive positive-memory update that carries known source provenance
does **not** reinforce the adaptive prototype when that source is identical to
the last source successfully incorporated into the adaptive prototype.

- Source image timestamp is the preferred source identifier; the source frame
  identifier is the fallback.
- Missing source provenance preserves the existing adaptive-update behaviour.
- Last-source suppression only. `A → B → A` updates on all three transitions;
  there is no historical or global source de-duplication.
- Clearing identity memory resets the remembered adaptive source. Operator
  selection and delayed operator-anchor bootstrap initialise the remembered
  source together with the adaptive representation. Ordinary recovery does not
  start a new identity-memory session and does not reset source tracking.
- Trusted-gallery admission is independent of an adaptive-update skip.
- The EMA coefficient, crop eligibility and appearance inference scheduling are
  unchanged. No MARS inference saving is claimed or implemented; the effect is a
  redundant-reinforcement reduction of the adaptive EMA only.

Implementation: the tested Stage-1 `PositiveAppearanceMemory.update_trusted`
`prevent_repeated_adaptive_source` path is reused unchanged. At the
`TargetIdentityMemory` call site the effective suppression is
`cfg.appearance_prevent_repeated_source_adaptive_update` **or** the retained
development-only ablation control, so live and replay execution activate the
policy through canonical configuration without the development flag, and the
development flag still reproduces the historical experiments.

## 4. AB-14 rejection

AB-14 (`min_confirm_frames_after_reacquire = 0`) is **not** promoted. Its
development availability gain is small (0.618 / 0.067 / 0.296 s of correct
authority on May / Seq03 / Seq04, zero on Seq01, no new wrong-person authority
on the available development evidence) and removing the generic
post-reacquisition confirmation frame weakens a temporal safeguard whose value
cannot be assessed on development sequences alone. The safeguard is retained
until prospective evaluation.

## 5. Retained mechanisms (unchanged)

Forced fresh same-ID appearance challenge; available-image challenge behaviour;
AB-10 same-ID positive-support rejection; global appearance reacquisition;
protected anchor; trusted gallery; adaptive positive representation; rank-aware
reacquisition; short-gap same-ID priority; short-gap new-ID suppression;
appearance-weighted ranking; hard-negative memory and its existing lifecycle;
update-based candidate persistence; generic post-reacquisition confirmation.

AB-13, AB-04, AB-05, AB-01, AB-06, AB-09 are not adopted. AB-15 and AB-19 remain
diagnostics only and are not adopted; hard-negative evidence from AB-09 / AB-15
is not conflated with AB-10.

## 6. Intended regression contract

Before the Stage-7 prospective freeze, run the combined AB-16 production
configuration through deterministic replay for May, Seq01, Seq03 and Seq04 under
the pinned numerical environment
(`docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh`),
comparing against the pinned selected-development baselines recorded in
`tim_pinned_replay_semantic_rebaseline_20260908.md`. The expected outcome is:

- candidate-stream SHA-256 unchanged on every sequence;
- physical-v2 correct / wrong / LOST / absent-with-output buckets and
  `TargetState` counts unchanged relative to the pinned selected baseline;
- zero new wrong-person authority and zero new target-absence leakage on every
  sequence;
- reduced reported trusted adaptive-memory updates, consistent with the Stage-1
  AB-16 development finding, with no controller-facing regression.

`tim_mars_resolved_runtime.json` (schema 4) records, for every run, whether
repeated-source suppression was requested through production configuration,
through the development ablation control, or both, and the effective state.

## 7. Scope

Development-only architecture decision. No held-out sequence, prospective freeze
or evaluation semantics are affected. H01/H02/H03 remain reserved pending
capture and were not inspected.
