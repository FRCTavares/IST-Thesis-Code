# TIM-MARS Stage-1 recovery / short-gap / persistence / ranking ablations — 8 September 2026

Development-only evidence. **H01/H02/H03 were not accessed, captured or inspected.**
The Issue #27 frozen contracts (`tim_mars_split_v3.json`,
`tim_mars_final_comparison_v2.json`, `P027_HELDOUT_EXECUTION_PLAN.md`) are
untouched. No canonical behaviour is promoted.

Completes the remaining Stage-1 mechanism ablations after AB-11/AB-18,
AB-06/AB-09/AB-10 and the positive-memory block (AB-07/AB-08/AB-16).

## 0. Reproducibility contract

All runs in this document use the pinned numerical environment
`docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh`
(TF thread pins + `TF_DETERMINISTIC_OPS=1`; `TF_ENABLE_ONEDNN_OPTS=0` verified
non-operative). The comparison contract is **pinned selected baseline vs pinned
treatment**; a pinned treatment digest is never compared to a historical
uncontrolled-environment digest. Rationale and behavioural-equivalence proof:
`tim_pinned_replay_semantic_rebaseline_20260908.md`.

Pinned selected-development baselines (config
`available_image_challenge.yaml` SHA-256
`a8c8092199f6ad7659ef00226e77b3181b72c9e2fb89bb0e8e2c86c91a43cd5c`; model
`mars-small128.pb` SHA-256
`e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`):

| Seq | pinned baseline semantic SHA-256 | candidate-stream SHA-256 | physical-v2 correct / wrong / LOST / absent-with-output (s) |
| --- | --- | --- | --- |
| May   | `9eb017711275e98bbba6f6b35ea30b1be036aac730c222a9686dd8ef446fa63b` | `a85270138a46cb51888dc2656d3525647109647fa69886f39024e3ec9cab8d8d` | 62.796329712 / 0.033394241 / 5.035185821 / 0 |
| Seq01 | `7754d5717a587f5ee596f00a5aa2402e11386856b52b6a5d8f0ce7f84103dce2` | `1c9b90773a86c1dc5739d7af5617268a60f6c109086ac5354e1a14825a04ac2b` | 61.200516816 / 0 / 0 / 0 |
| Seq03 | `ca1f1826e2092a03c36b73015045d55c55dc232046b28871e769b85200079eaf` | `60e41fb14822af5a04b781ac08a6a75e7a05382a9bd55629a737a325512582db` | 24.600414282 / 0 / 59.166383501 / 0 |
| Seq04 | `d7da756a5220a06e35ada759c5a7a7cafbf678e5c7102d31b35028c996a4c5ca` | `9c514facb5cd946a02800885e8bacb9ea9fb0132d6ceab4c73e7f4a30ce3c3bf` | 48.766241082 / 0 / 23.733800690 / 0 |

A post-rebuild neutrality re-verification (after the AB-15/AB-19 source
additions) reproduced the Seq03 pinned baseline `ca1f1826…` exactly, confirming
every new development control is default-off neutral.

## 1. Implementation

All controls are runner-only and default-off. No canonical YAML, ROS parameter,
launch config, or `TargetIdentityMemory` constructor development exposure is
added beyond the existing pattern.

| Ablation | Runner flag | Mechanism | Kind |
| --- | --- | --- | --- |
| AB-12 | `--ablation-disable-global-reacquisition` | `memory.global_reacquisition_enabled = False` | existing `TargetMemoryConfig` switch |
| AB-13 | `--ablation-disable-rank-aware-reacquisition` | `memory.rank_aware_reacquisition_enabled = False` | existing `TargetMemoryConfig` switch |
| AB-04 | `--ablation-disable-short-gap-same-id-priority` | `memory.short_gap_same_id_priority_enabled = False` | existing `TargetMemoryConfig` switch |
| AB-05 | `--ablation-disable-short-gap-new-id-suppression` | `memory.short_gap_new_id_suppression_enabled = False` | existing `TargetMemoryConfig` switch |
| AB-14 | `--ablation-zero-min-confirm-frames-after-reacquire` | `memory.min_confirm_frames_after_reacquire = 0` | existing `TargetMemoryConfig` field |
| AB-01 | `--ablation-zero-appearance-ranking-contribution` | `memory.appearance_weight = 0.0` | existing `TargetMemoryConfig` field (see §4) |
| AB-15 | `--ablation-retire-overage-hard-negatives-pre-score` | pre-score `HardNegativeMemory.expire_committed(...)` in `update()` | new runtime dev-control |
| AB-19 | `--ablation-require-distinct-source-for-persistence` | `CandidatePersistenceTracker` does not advance on a repeated appearance source image | new runtime dev-control |

AB-12/13/04/05/14 and AB-01 need no rebuild (config-field overrides). AB-15/19
add default-off branches to `target_memory.py` / `reacquisition_policy.py` /
`runtime.py` and were built with `tools/thesis_build.sh --packages-select
thesis_bringup`.

Tests: `tools/tests/test_run_deterministic_tim_replay.py`,
`test_candidate_persistence_tracker.py` (AB-19 unit),
`test_tim_identity_resilience.py`, `test_hard_negative_lifecycle_provenance.py`,
`test_target_memory_global_reacquisition.py`,
`test_target_memory_rank_aware_reacquisition.py` — all pass; the existing
global- and rank-aware-reacquisition contract tests are preserved.

## 2. Opportunity scan (pinned selected baselines)

Proposal-source / reason counts from `/target_memory_mars/status`:

| Mechanism (proposal_source / reason) | May | Seq01 | Seq03 | Seq04 |
| --- | --: | --: | --: | --: |
| `global_identity_reacquisition` proposal frames (AB-12) | 34 | **0** | 1372 | 820 |
| `rank_aware_reacquisition` proposal frames (AB-13) | 4 | **0** | 4 | 15 |
| `short_gap_same_id` proposal frames (AB-04) | 22 | **0** | 8 | 37 |
| `short_gap_new_id_suppressed` frames (AB-05) | 17 | **0** | 4 | 7 |
| `recovery_persistence_pending` frames (AB-14) | 7 | **0** | 2 | 11 |
| over-age (>247f) committed hard-negative present (AB-15) | 0 | 0 | 616 | 34 |
| over-age entry AND best-candidate `hard_negative_reject` (AB-15) | 0 | 0 | 23 | 6 |
| repeated-source confirmation transitions (AB-19) | 5 of 7 | 0 | 0 of 2 | 0 of 10 |

Seq01 is LOCKED + NORMAL for all 1520 frames with zero recovery / short-gap /
persistence activity, so AB-12/13/04/05/14/15/19 are **NO-OPPORTUNITY on Seq01**
(confirmed under the pinned baseline contract). AB-12/AB-13 on Seq01 were also
run explicitly and reproduced the Seq01 pinned baseline semantic digest exactly.

## 3. Mandatory ablation results (independent, vs pinned selected baseline)

Every treatment: candidate-stream SHA-256 verified, physical-v2 reconciliation
ok (residual 0), **zero new wrong-person authority, zero new target-absence
leakage on every cell**.

### AB-12 — disable long-gap global identity reacquisition

| Seq | semantic == baseline | Δcorrect (s) | Δwrong (s) | Δabsence (s) | state Δ |
| --- | --- | --: | --: | --: | --- |
| May   | no (diagnostics only) | 0 | 0 | 0 | none |
| Seq01 | **yes** | 0 | 0 | 0 | none |
| Seq03 | no | **−2.067728018** | 0 | 0 | LOCKED −47, LOST +55, REACQUIRED −2, UNCERTAIN −6 |
| Seq04 | no | **−9.302666459** | 0 | 0 | LOCKED −215, LOST +234, REACQUIRED −2, UNCERTAIN −17 |

Interval detail: Seq03 loses two correct-authority windows (1.300 s at 44.3 s,
0.734 s at sequence end); Seq04 loses ~10.2 s across 6 windows and gains one
1.0 s window at 40.9 s (net −9.30 s). Zero ID-error intervals. With global
recovery disabled, rank-aware then normal selection attempt the same
candidates but are rejected more often
(`rank_aware_id_switch_recovery_reject`, `ambiguous_best_candidate`,
`best_below_threshold`); the lost authority converts entirely to LOST/HOVER.
Appearance backend calls fall 40 (Seq03) / 121 (Seq04).

**Classification: USEFUL — context-specific availability, essential on Seq03
(+2.07 s) and Seq04 (+9.30 s correct authority) at zero wrong-person or
ID-error cost on the available development evidence; redundant on May; inactive
on Seq01.** Reconfirms the Issue #90 promotion under the pinned contract.

### AB-13 — disable rank-aware reacquisition

May / Seq03 / Seq04: physical-v2 buckets, `TargetState` counts and proposal
routing to the controller-facing outcome are **identical**; only diagnostics
differ (Seq03: the 4 rank-aware proposals become 2 `normal_selection` +
2 `best_below_threshold`, same final output). Seq01 NO-OPPORTUNITY.

**Classification: REDUNDANT on the available development evidence for
controller-facing behaviour and appearance workload, while diagnostically
active. Dominated by global recovery and normal selection** (consistent with
the static audit's `rank_aware_confirm_frames=1` note).

### AB-04 — disable short-gap same-ID priority

May / Seq03 / Seq04: buckets + states identical. Seq03: the 8 `short_gap_same_id`
proposals become 6 `rank_aware_reacquisition` + 2 `normal_selection` with the
same final outcome.

**Classification: REDUNDANT on the available development evidence.**

### AB-05 — disable short-gap new-ID suppression

May / Seq03 / Seq04: buckets + states identical. Seq03: the 4
`short_gap_new_id_suppressed` rejections become 4
`rank_aware_id_switch_recovery_reject` — the candidates are still rejected, by a
downstream gate. No output is gained by removing the suppression.

**Classification: REDUNDANT on the available development evidence — the
suppressed candidates are rejected by downstream identity gates anyway.**

### AB-14 — `min_confirm_frames_after_reacquire = 0`

The general post-reacquisition confirmation requires
`1 + min_confirm_frames_after_reacquire = 2` observations; AB-14 makes it 1.

| Seq | Δcorrect (s) | Δwrong (s) | Δabsence (s) | interval detail |
| --- | --: | --: | --: | --- |
| May   | +0.617569768 | 0 | 0 | 7 reacquisitions publish ~1 frame sooner; 0 LOST, 0 ID-error |
| Seq03 | +0.066927370 | 0 | 0 | 2 single-frame gains |
| Seq04 | +0.295821426 | 0 | 0 | 10 single-frame gains + 0.133 s window; also two small −0.200 s losses (transient reacquire flicker the extra frame would have suppressed) |

**Classification: the extra general post-reacquisition confirmation observation
prevents ZERO wrong publications on the available development evidence — it only
adds ~0.07–0.62 s of suppression latency per sequence (and cleans up 0.2 s of
transient flicker on Seq04). It is a simplification candidate; the confirmation
frame is not doing wrong-person safety work on the permitted sequences.**
Development-only: a held-out sequence could still expose a wrong publication the
extra observation would have caught.

### AB-01 — remove appearance contribution to ranking only

`appearance_weight = 0` removes the single numerical term
`ranking_score += appearance_weight * appearance_score` in
`appearance_policy.score_with_appearance`; `appearance_raw`,
`appearance_similarity_passed`, `appearance_gate_passed`, `appearance_used`, the
appearance margin, the conservative filter, positive/protected memory and
hard-negative memory are all computed from separate quantities and stay active.

All four sequences: physical-v2 buckets, `TargetState` counts, proposal-source
counts, reason-prefix counts and appearance workload are **identical**; Seq01 is
even semantic-identical to the pinned baseline (on Seq01 `appearance_ambiguous_only`
keeps `use_appearance` false throughout, so the ranking term is never applied).

**Classification: the numerical appearance contribution to candidate ranking is
controller-facing INACTIVE / REDUNDANT on the available development evidence.**
Appearance's decisive influence on these sequences is entirely via its gates and
memory policy, not via its weighted addition to the ranking score.

## 4. AB-01 implementation note

`appearance_weight` is referenced at exactly one site
(`score_with_appearance`, the ranking-contribution multiplier); zeroing it is
therefore an exact, minimal realisation of "remove appearance contribution to
ranking only". The only second-order effect is that when
`appearance_used` is true the published `total` becomes `clamp01(geometry_score)`
rather than the unclamped base `total`; `geometry_score` is within [0, 1] for
these configurations so this is inert. This is **not** `appearance_enabled=false`.

## 5. Conditional ablations

### AB-15 — pre-score retirement of over-age committed hard negatives

Gate: hard-negative memory is diagnostically active (AB-09) and over-age veto
opportunity exists — Seq03 has committed entries up to **863** frames old (max
age 247), rejecting the best candidate on **23** frames; Seq04 has entries up to
**281** frames old rejecting the best candidate on **6** frames, **6** of which
the final controller-facing reason mentions hard-negative. May (max 110) and
Seq01 (max 247, not over) are **NO-OPPORTUNITY**.

Executed on Seq03 and Seq04.

| Seq | Δcorrect | Δwrong | Δabsence | states | TIM `/target` | detail |
| --- | --: | --: | --: | --- | --- | --- |
| Seq03 | 0 | 0 | 0 | none | **byte-identical** | pre-score expiry removes the over-age prototypes but no physical-v2 bucket, state or published target changes |
| Seq04 | 0 | 0 | 0 | none | **byte-identical** | 6 frames' rejection attribution moves `global_identity_recovery_reject` → `protected_gallery_reacquisition_reject`; identical suppressed output |

**Classification: INACTIVE on the available development evidence.** Over-age
committed hard negatives are diagnostically scoreable and do reject the best
candidate (Seq03 23 frames, Seq04 6 frames), but retiring them before scoring
changes zero physical-v2 buckets, zero `TargetState` counts and leaves the
published `/target` stream byte-identical — the candidate is suppressed by other
gates regardless. This extends AB-09: not only is hard-negative memory
controller-facing redundant on the permitted sequences, so is the timing of its
lifecycle expiry.

### AB-19 — require distinct source-image support for persistence

Gate: repeated-source confirmation opportunity exists — on May, 5 of 7
recovery confirmation transitions reuse the same cached MARS embedding (same
appearance source image, `pending_img_ts == accept_img_ts`) for candidate 1.
The pending→accept transition frame pair on Seq03/Seq04 uses distinct images,
but the multi-frame recovery confirmations there still partly ride on one
cached embedding (see results). Seq01 has zero confirmation activity —
**NO-OPPORTUNITY**. Executed on May, Seq03, Seq04.

| Seq | Δcorrect (s) | Δwrong (s) | Δabsence (s) | state Δ | interpretation |
| --- | --: | --: | --: | --- | --- |
| May   | **−2.754305096** | 0 | 0 | LOCKED −51, REACQUIRED +50, LOST +1 | 5 single-observation reacquisitions delayed until a fresh image; `recovery_persistence_pending` +50, positive-memory updates −47 |
| Seq03 | **−2.067728018** | 0 | 0 | LOCKED −47, LOST +47, REACQUIRED +6 | 2 recovery reacquisitions delayed |
| Seq04 | **−10.066900216** | 0 | 0 | LOCKED −227, LOST +160, REACQUIRED +108 | `recovery_persistence_pending` +108; large availability cost on the occlusion sequence |

Aggregate: **−14.888933330 s correct authority, 0 s new wrong-person, 0 s new
absence leakage.** All lost authority converts to suppressed (LOST/REACQUIRED).

**Classification: HARDENING candidate with a substantial availability cost and
no measured safety benefit on the available development evidence.** 2–10 s of
the selected candidate's reacquisition authority per sequence rests on
confirmation counting a single cached appearance observation more than once.
Enforcing distinct-source evidence removes that authority without removing any
wrong-person or absence-leakage authority. Read together with AB-14 (the
current general 2-frame confirmation prevents zero wrong publications on these
sequences and only adds latency), AB-19 is pure availability cost here. **Do
not adopt on development evidence; retain as a diagnostic.** A held-out
sequence could still expose a wrong reacquisition that distinct-source
confirmation would prevent.

## 6. Stage-1 classification summary

| Ablation | Mechanism | Classification (available development evidence) |
| --- | --- | --- |
| AB-12 | long-gap global identity reacquisition | **USEFUL** — availability-essential on Seq03 (+2.07 s) and Seq04 (+9.30 s correct), redundant on May, inactive on Seq01; zero wrong-person / ID-error cost |
| AB-13 | rank-aware reacquisition | **REDUNDANT** (controller-facing + workload), diagnostically active; dominated by global recovery + normal selection |
| AB-04 | short-gap same-ID priority | **REDUNDANT** — proposals re-route to rank-aware / normal with identical final output |
| AB-05 | short-gap new-ID suppression | **REDUNDANT** — suppressed candidates are rejected by downstream identity gates anyway |
| AB-14 | extra post-reacquisition confirmation frame | **REDUNDANT for wrong-person safety** — prevents zero wrong publications, only adds 0.07–0.62 s suppression latency per sequence; simplification candidate |
| AB-01 | numerical appearance contribution to ranking | **INACTIVE / REDUNDANT** — appearance's decisive influence is via its gates and memory policy, not its weighted ranking term; Seq01 semantic-identical |
| AB-15 | pre-score retirement of over-age hard negatives | **INACTIVE** — over-age negatives are scoreable and reject the best candidate but change no bucket / state / published target; extends AB-09 |
| AB-19 | distinct-source persistence requirement | **HARDENING with availability cost, no measured safety benefit** (−14.89 s aggregate correct authority, 0 s wrong / absence); diagnostic only — do not adopt on development evidence |

Safety ordering (correct target > LOST/HOVER > wrong target) is respected by
every result: no ablation created wrong-person authority, absence leakage or
credible memory contamination, and no reduction was accepted merely for
suppressing more output. Retained Stage-1 simplification candidates:
**AB-16** (repeated-source adaptive EMA), and now **AB-14** (post-reacquisition
confirmation frame). Retained mechanisms: protected anchor, trusted gallery,
adaptive representation (positive-memory block); global reacquisition (AB-12).

These are development classifications only. H01/H02/H03 remain untouched and
the historical prospective freeze is unchanged. No new prospective
algorithm/config/split/comparison freeze is authorised by this document.

## 7. Provenance

Per-cell provenance (`command`, config/model/candidate/semantic/resolved-runtime
SHA-256, treatment flags, value sources), physical-v2 reports, status scans and
`compare_vs_baseline.json` are retained under
`reports/tim_ablation_stage1_pinned_20260908/` with the machine-readable
`campaign_gathered.json`. Helper scripts:
`reports/tim_ablation_stage1_20260908/_helpers/`. Historical uncontrolled-env
mechanism-ablation evidence is unchanged.
