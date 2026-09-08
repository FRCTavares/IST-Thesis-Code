# TIM-MARS prospective held-out freeze (Stage-7) — Issue #27 — 8 September 2026

**This is the prospective freeze.** It is constructed and merged **before any
H01/H02/H03 source is captured, listed, opened, hashed, replayed, annotated,
evaluated or inspected.** No held-out outcome information exists or was used.

Machine-readable authority:
`docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`
(`freeze_id: tim_mars_prospective_freeze_2026_09_08`).

## Why a new freeze

The 5 September `tim_mars_split_v3` / `tim_mars_final_comparison_v2` prospective
freeze bound algorithm commit
`2476991d262f7f388930aece0d731745f20dc1b3` with canonical TIM-MARS SHA-256
`0f2ac3fc…`. The reviewed Stage-1 mechanism-ablation campaign then selected one
behaviour-affecting promotion — **AB-16 source-aware adaptive positive-memory
updates** (`appearance_prevent_repeated_source_adaptive_update: true`) — merged
as PR #101 at `79f11b631688889bf5ffbeb3c16ef543a53f9973`. Because the canonical
configuration changed **before** any held-out capture or outcome access, an
explicitly versioned new prospective freeze is required. This is a protocol
update, not post-test tuning. The previous freezes (v1/v2/v3, comparison
v1/v2) are retained byte-unchanged as historical provenance.

## Frozen algorithm

| Item | Value |
| --- | --- |
| Algorithm authority commit | `79f11b631688889bf5ffbeb3c16ef543a53f9973` (PR #101 merge) |
| Base Stage-1 merge | `d3edbcc537b92f5ef66771911015e620fc7467d2` |
| Canonical config | `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml` |
| Canonical config SHA-256 | `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c` |
| Detector | YOLOv8s — `models/hef/yolov8s.hef` (`69540ff8…`, 11 284 359 B), 640×640 inference, direct-Hailo |
| Appearance model | MARS-small128 — `models/reid/mars-small128.pb` (`e96f3cc0…`, 11 244 410 B) |
| Canonical tracker | ByteTrack — `ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml` (`e0e5c7c8…`) |
| Selected-target authority | TIM-MARS |
| Pinned numerical environment | `docs/results/selected_target_tracking/tim_pinned_replay_env_20260908.sh` (`24f8c09f…`) |

Critical canonical TIM-MARS settings (verified live):
`min_confirm_frames_after_reacquire: 1`, `appearance_weight: 0.12`,
`same_id_fresh_challenge_enabled: true`,
`same_id_challenge_available_images_only: true`,
`appearance_gallery_consensus_recovery_enabled: false`,
`appearance_prevent_repeated_source_adaptive_update: true`.

**AB-14, AB-15 and AB-19 are not promoted. No threshold was tuned.** The final
algorithm is the selected TIM-MARS development baseline plus production AB-16
only; every other retained mechanism (forced fresh same-ID appearance
challenge, available-image challenge handling, AB-10 same-ID positive-support
rejection, global and rank-aware reacquisition, short-gap same-ID priority,
short-gap new-ID suppression, protected anchor, trusted gallery, adaptive
positive representation, appearance-weighted ranking, hard-negative memory and
its lifecycle, update-based candidate persistence, generic post-reacquisition
confirmation) is unchanged.

## Frozen contracts

| Contract | New version | Supersedes |
| --- | --- | --- |
| Split | `docs/data/splits/tim_mars_split_v4.json` (`tim_mars_split_v4_2026_09_08`) | `tim_mars_split_v3_2026_09_05` |
| Architecture comparison | `docs/data/splits/tim_mars_final_comparison_v3.json` (`tim_mars_final_comparison_v3_2026_09_08`) | `tim_mars_final_comparison_v2_2026_09_05` |
| Held-out execution plan | `docs/flight/P027_HELDOUT_EXECUTION_PLAN_v2.md` | `docs/flight/P027_HELDOUT_EXECUTION_PLAN.md` (retained unchanged) |

`validate_tim_evaluation_split.py` now defaults to the v4 split; bare
invocations, the capture helper and `reproduce_tim_mars.py` follow.

## Split contract

- **Development / historical (tuning-permitted):** `dev_may_hard_reentry`,
  `dev_june_seq01`, `dev_june_seq03_ocsort`, `dev_june_seq04_ocsort` — carried
  forward unchanged from v3, all `ready`, all hashes re-verified.
- **Legacy validation (diagnostic only, no tuning, no held-out claim):**
  `legacy_june_seq02`.
- **Prospective held-out (future / unobserved):** `heldout_h01_exit_reentry`,
  `heldout_h02_crossing`, `heldout_h03_occlusion_distractor` — all
  `reserved_pending_capture`, `files: []`, no outcome values.

H01/H02/H03 cannot be used for parameter selection. No
algorithm/configuration/model/evaluator tuning is permitted after the first
held-out access. Development sequences remain development evidence.

## Held-out scenario contract (predeclared, unchanged)

The physical scenario roles were already specified before this freeze and are
preserved verbatim:

| Id | Challenge | Operator sheet |
| --- | --- | --- |
| `heldout_h01_exit_reentry` | selected target exits fully, remains absent ≈5–8 s (distractor visible during part of the absence), then re-enters amid tracker-ID churn; ≥10 s retained after re-entry | `docs/flight/P027_H01_EXIT_REENTRY.md` |
| `heldout_h02_crossing` | close target/distractor crossing with sustained overlap/near-overlap; two close crossings; clear separation between and after; ≥10 s after the final separation | `docs/flight/P027_H02_CROSSING.md` |
| `heldout_h03_occlusion_distractor` | partial then full visual occlusion while the target remains physically present, a distractor visible near the target's last location, then the same target revealed; ≥10 s after the reveal | `docs/flight/P027_H03_OCCLUSION_DISTRACTOR.md` |

Target-selection/bootstrap for every architecture uses the frozen
`physical_reference_v2` annotation at the predetermined initial-selection
instant only (`initial_target_bootstrap` in the comparison contract). Capture
start/end criteria, valid-capture criteria, annotation procedure and evaluator
procedure are in `P027_HELDOUT_EXECUTION_PLAN_v2.md` and
`docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md`.

**Recapture is allowed only for prospectively-defined technical invalidity**
(corrupted/unfinalized recording, missing `/camera/image_raw` or
`/detections`, unusable imagery, or objective failure to execute the
predeclared physical scenario). **A failed algorithmic performance result is
never grounds for recapture.**

## Primary held-out metric contract

Authority: `tim_physical_target_bbox_v2` via
`tools/analysis/evaluate_physical_target_bbox_v2.py` (frozen; `DEFAULT_STEP_S =
0.05`, `DEFAULT_MAX_OUTPUT_AGE_S = 0.9`). Primary identity buckets:
`correct_target_output_duration_s`, `wrong_person_output_duration_s`,
`identity_unresolved_duration_s`, `lost_or_suppressed_duration_s`; additional
required buckets: `target_absent_duration_s`,
`target_absent_with_output_duration_s`, `reference_unavailable_duration_s`,
`reference_gap_duration_s`. All buckets must reconcile against the full
evaluation window.

**Target-presence accounting (per sequence).**
`physical_target_present_duration_s` = the sum of the four primary identity
buckets (reference-covered, physically-scored target-present time);
`physical_target_absent_duration_s` = `target_absent_duration_s`;
`total_scored_duration_s` = `total_evaluated_duration_s`; percent of scored
time target-present is reported.

**While the physical target is present:** correct-target authority duration and
percentage, wrong-person authority duration and percentage, LOST/suppressed
duration and percentage, identity-unresolved duration — all as a percentage of
`physical_target_present_duration_s`.

**While the physical target is absent:** false-publication / authority-leakage
duration (`target_absent_with_output_duration_s`) and its percentage of
`target_absent_duration_s` (reported only when the sequence has non-zero
target-absent time), and safe-clear/LOST duration.

**Reacquisition (descriptive secondary analysis, derived from frozen
artifacts — no new evaluator).** A valid disappearance/return event is a
maximal `absent` run in the frozen physical-v2 reference bounded on both sides
by `present_scored`; the return instant is the first `present_scored` sample
after it. A successful reacquisition is correct-target authority held again at
or after the return instant and before the window end. Reacquisition latency is
`(first correct-authority sample at/after return) − (return instant)`, reported
per valid event. Events with no correct authority before the window end are
reported as **right-censored** (latency `≥ window_end − return_instant`), never
assigned a finite value and excluded from any summary-latency figure. Success
rate = successful / valid events. A summary latency is reported only over
non-censored successful events, always alongside the censored count.

**Identity safety.** Wrong-person authority duration and target-absence leakage
duration are always reported explicitly per sequence. Wrong-person intervals
(maximal `wrong_person` runs) and identity-switch events (`correct_target` →
`wrong_person` with no intervening `lost_or_suppressed` sample) are reported
where the reference supports it. Any non-zero wrong-person or absence-leakage
duration is an explicit finding.

### Development percentage characterisation (descriptive only)

The identical presence-conditioned percentages (`% correct / % wrong / %
suppressed while target present`; `% leakage while target absent`) may later be
computed for `dev_may_hard_reentry`, `dev_june_seq01`, `dev_june_seq03_ocsort`
and `dev_june_seq04_ocsort` from their existing frozen physical-v2 references
(hashed in the manifest) using the same derivation and **no change to
evaluator classification semantics**. This must not be used to retune the
algorithm and adds no new optimisation or acceptance threshold.
`dev_june_seq03_ocsort` has zero physical target-absent duration, so its
leakage percentage is *not applicable*.

## Architecture comparison contract

`tim_mars_final_comparison_v3.json` extends v2 with only the AB-16-driven
canonical-config hash/size (`0f2ac3fc…`/4842 → `b0a98334…`/5727) and the frozen
algorithm commit (`2476991d…` → `79f11b63…`). The four primary architecture
arms, the common YOLOv8s detector evidence rule, the common MARS appearance
model, the `physical_reference_v2` bootstrap rule, the physical-v2 evaluator
and its buckets, and `source_code_freeze.required_unchanged_paths` are
otherwise **unchanged**.

| Arm id | Label | Selected-target authority | Notes |
| --- | --- | --- | --- |
| `bytetrack_raw` | ByteTrack raw | none (raw tracker baseline) | lower reference; identity buckets computed with the same evaluator |
| `target_reid_090` | Simple Target-ReID 0.90 | fixed 0.90 MARS cosine, stateless | development-only negative arm |
| `bytetrack_tim_mars` | ByteTrack + canonical TIM-MARS | **TIM-MARS** | the final algorithm; canonical config `b0a98334…` |
| `deepsort_raw` | DeepSORT raw | none (raw tracker baseline) | lower reference |

No architecture is added, removed or retuned. The prospective comparison
extends the Issue #58 development matrix; it does not rerun or replace it.

## Success / failure interpretation

No quantitative pass/fail threshold exists in the historical Issue #27
methodology and none is fabricated here. Safety principle:
**correct target > LOST/HOVER > wrong target.** Wrong-person authority and
target-absence leakage are always reported explicitly and are never
compensated by higher correct-target availability. LOST/HOVER is an acceptable
safe outcome under ambiguity or absence. **No post-held-out parameter
adjustment may be used to improve a failed result. An unfavourable held-out
result remains valid thesis evidence.** Seq03's controller behaviour is
unchanged by AB-16 and Seq03 has zero target-absent duration; AB-16 is not
intended to change Seq03 availability, and the absence of a Seq03 improvement
is not a failure.

## Post-freeze lock rule

Once this freeze is merged, **the first access or capture of any of
H01/H02/H03 locks** the algorithm, production configuration, tracker
configuration, models, evaluator definitions, split, architecture arms,
primary metrics and annotation interpretation. No outcome-driven change to any
of these is permitted afterward. A serious software correctness bug discovered
after held-out access must be documented; it may **not** be silently patched
and re-run as though still prospective, and any corrected evaluation must be
clearly identified as post-freeze / post-access evidence. A behaviour-affecting
change motivated by held-out outcomes contaminates the accessed recordings —
they must leave the final held-out set and a further explicitly versioned
prospective split is required.

## Runtime provenance required from every held-out run

Source commit (`= 79f11b63…`, clean tree), canonical/tracker/detector/MARS
hashes, pinned-environment hash and effective values, split-v4 sequence id,
source-bag path and SHA-256, candidate-stream SHA-256 and match flag,
architecture-arm id, `repeated_source_adaptive_update` resolution
(`requested_production_policy=true`, `development_ablation_control=false`,
`activation_source='production_config'` for the final TIM-MARS arm), output
paths and semantic digest, evaluator file hashes, physical-v2 reference path
and SHA-256, resolved-runtime schema version. Full list in the manifest.

## Protected historical files — byte-unchanged

`tim_mars_split_v3.json`, `tim_mars_split_v2.json`, `tim_mars_split_v1.json`,
`tim_mars_final_comparison_v2.json`, `tim_mars_final_comparison_v1.json`,
`docs/flight/P027_HELDOUT_EXECUTION_PLAN.md`.

## Release state

`final_ready = 0/3`. Issue #27 remains **OPEN**. No held-out capture or
evaluation has occurred. **H01/H02/H03 were not accessed.**
