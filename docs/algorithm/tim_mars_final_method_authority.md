# TIM-MARS final method authority

Reviewed 18 September 2026. This is the implementation map for dissertation
Chapter 4. It describes the Stage-7 frozen algorithm, not a new experiment.
The algorithm authority is commit
`79f11b631688889bf5ffbeb3c16ef543a53f9973`; the canonical parameter
file is `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
(SHA-256 `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c`).
The immutable freeze is
`docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.{md,json}`.
Later repository HEADs are runtime/provenance identities, not a redefinition
of this algorithm. Verify the file hash before quoting these values.

## Problem and claim boundary

A detector and ByteTrack supply candidate person trajectories; an operator
selects one physical person through a visible track. TIM-MARS decides whether
subsequent tracker candidates carry enough evidence to expose that selected
identity to control. **Association != identity evidence != controller
authority.** Its asymmetric preference is correct selected-person authority,
then temporary suppression, then wrong-person authority. This is an
engineering objective, not a formal safety guarantee or calibrated
probability.

The contribution is the separate selected-person identity/authority
architecture, integration and evaluation. ReID, target memory, reacquisition,
hard negatives, abstention, distractor reasoning, selective appearance
extraction, and appearance-aware tracking are established mechanisms, not
individual novelty claims. The canonical tracker is ByteTrack; conclusions
are tracker-, scenario-, annotation- and configuration-specific. The method
does not estimate target velocity independently.

## Inputs and authority epoch

`target_memory_mars_node.py` wraps `runtime.py` and the ROS-free
`target_memory.py`. A `Track2DArray` supplies frame ID, source timestamp,
and tracks with ID, bbox and confidence. The node receives operator
selection/clear commands; the raw `/target` topic is only an operator
selection mirror, never the controller-facing output. A changed selection
increments `selection_generation`, cancels pending appearance work, clears
the previous memory/cache lifecycle, and publishes a zero target before the
new request can acquire authority. A pending ID must appear in the current
candidate set before selection. `auto_select_largest` defaults to false
and is for manual inspection, not final evaluation.

`runtime.py` chooses a causal image at or before the track timestamp. Fresh
encoding requires a usable image within 250 ms. The canonical request policy
is `all_candidates`; actual encoding can be rate-limited to one source every
250 ms and embeddings can be reused for at most 750 ms. A cached embedding
carries source frame/image time, embedded time, frame and track generation,
bbox and crop quality. Reuse requires continuous plausible ID, centre and
scale; absence, implausible jump, non-monotonic frame or invalid timestamp
invalidates the lineage. Encoding eligibility and positive-memory update
eligibility differ: a comparison crop can inform acceptance without
necessarily being safe to learn from. Crop quality uses width, height,
clipping, aspect, overlap and centre separation in appearance-image
coordinates. A feature's source metadata remains visible in diagnostics.

## Stored state and transitions

The core stores selected flag, last accepted tracker ID and bbox, quality,
consecutive missed updates, positive appearance and state. Additional state
holds protected positive memory, bounded hard-negative prototypes and pending
observations, candidate confirmation, appearance update cooldown, and tracker
frame/time lineage. Re-selection or clear starts a new authority epoch and
clears these memories.

| State | Operational meaning | Controller-valid? |
| --- | --- | --- |
| `NO_TARGET` | No operator-selected target; clear returns here. | No |
| `LOCKED` | Current candidate passed all acceptance gates and was committed. | Yes, subject to freshness |
| `UNCERTAIN` | One through six consecutive misses/rejections; last trusted geometry remains diagnostic only. | No |
| `LOST` | More than six consecutive misses/rejections. | No |
| `REACQUIRED` | A recovery proposal is awaiting confirmation; stored trusted state is not yet replaced. | No |

Each miss multiplies retained quality by 0.85 and increments the missed
update count. A passed recovery returns to `LOCKED` only after the required
observations. `REACQUIRED` is emitted as a probationary output; it is not a
controller-valid accepted target. State-to-mode suggestions are
`NO_CONTROL/NORMAL/YAW_ONLY/HOVER/CONFIRM`; only `NORMAL` is
`control_valid`. These mode names are diagnostics/intent and do not by
themselves establish physical FCU behaviour.

## Candidate evidence and scoring

For candidate `c` and the last accepted bbox `b`, let `I` be bbox IoU,
`d` centre displacement divided by image diagonal, `r` candidate/reference
area, `q` clipped tracker confidence, and `J` the same-ID indicator.
The canonical geometry score is

`G(c)=clip01[0.34 I + 0.26 exp(-0.5(d/0.18)^2) + 0.18 exp(-0.5(log(r)/0.55)^2) + 0.14 q + 0.08 J]`.

Zero-area scale similarity is zero. This compares with the last **accepted**
bbox, not a predicted velocity state. Candidates below confidence 0.10 are
discarded. `geometry_score` is the acceptance-threshold quantity.
`ranking_score` begins at `G`; when positive appearance is enabled,
available, geometry-permitted, requested by the policy, and at least 0.35
similar, it becomes `G + 0.12 A`, where `A` is clipped cosine similarity
to the effective positive reference. `total` is the clipped diagnostic
ranking value. Acceptance never substitutes the appearance bonus for the
geometry minimum.

Ordinary appearance comparison requires positive IoU or distance similarity
at least 0.25 **and** scale similarity at least 0.35. In `LOCKED`,
appearance affects ranking when base geometry is ambiguous; in
`UNCERTAIN/LOST/REACQUIRED` it is requested. Protected anchor and trusted
gallery similarities are recorded separately from the adaptive prototype.
For an ID switch or untrusted recovery, only protected support can authorize
identity. Hard-negative similarity and positive-minus-negative margin are
calculated independently of whether appearance was added to ranking.
For a non-same-ID rank leader, ranking separation below 0.07 is ambiguous;
same-ID continuity is exempt from that generic ambiguity test.

## Transactional acceptance and recovery

All short-gap, global, rank-aware and normal paths construct a proposal and
pass the same side-effect-free safety verdict before confirmation state and
trusted memory are committed. Rejection becomes an invisible miss. Pending
confirmation emits `REACQUIRED/CONFIRM` with `visible=false`; it cannot
update the accepted ID, bbox, positive memory or hard negatives. Candidate
preparation cannot bootstrap identity memory.

- Normal acceptance requires `G >= 0.52` while not LOST, or `G >= 0.60`
  in LOST; same ID receives 0.08 threshold relief. A same-ID `LOCKED`
  observation can continue without a new embedding, subject to the nearby
  hijack/fresh-challenge and negative gates. Returning from `UNCERTAIN` or
  `LOST` with the same ID requires an actual candidate embedding when
  appearance is enabled. A same-ID `REACQUIRED` confirmation can use the
  already accepted entry evidence.
- During the eight-frame short-gap grace, the old ID has priority if its
  `G >= 0.30`; an unsupported new ID is suppressed unless it passes the
  configured strong-evidence rule (0.70 general, 0.85 in group-crop risk).
  Same-ID continuity does not bypass the common acceptance gate.
- Rank-aware recovery operates in `UNCERTAIN/LOST`. Eligible candidates
  require `G >= 0.40`, distance similarity >= 0.10, appearance >= 0.05,
  and at least 0.03 appearance separation over the next enriched candidate.
  It can select a candidate below geometry rank zero, but the common
  appearance, hard-negative, ambiguity and confirmation gates still apply.
- After at least nine missed updates in LOST, global recovery is enabled
  only when protected positive identity memory exists. It ranks by protected
  similarity, checks the independent ID-switch threshold (0.78), requires
  appearance separation >= 0.05, and rejects hard-negative compatibility.
  This path explicitly bypasses obsolete local geometry; it still uses the
  common proposal gate and confirmation. Adaptive appearance alone cannot
  authorize it.
- A different ID needs independently supported appearance at least 0.78
  (the maximum of 0.78 ID-switch and 0.65 conservative minimum), subject to
  the protected-gallery/crop rules, and `allow_id_switch_recovery=true`.
  The optional ID-switch spatial gate is disabled in the canonical config.
  A confirmed hard negative rejects at similarity >= 0.80 when positive
  minus negative similarity < 0.03. The final conservative filter requires
  its configured similarity/margin where it applies; missing appearance is
  not universally rejected (`appearance_conservative_require_appearance=false`).
- A changed ID or recovery from `UNCERTAIN/LOST/REACQUIRED` requires
  `1 + min_confirm_frames_after_reacquire = 2` update observations.
  Rank-aware's configured one-frame requirement does not remove this
  generic two-observation requirement. Rejected proposals cannot advance
  confirmation. This is update-based persistence, not an independent
  source-image count requirement.

The first failed gate supplies the suppression reason. A nearby identity
challenge can require fresh appearance for a continuing same ID; the active
available-image policy does not fail solely because the current image cannot
be encoded. The same-ID hijack gate can still reject a likely distractor.
The exact predicate order is in `target_memory.py::_candidate_safety_reject_reason`;
do not summarize it as an unconditional same-ID privilege.

## Positive and negative memory transactions

Operator selection initializes the protected anchor only from an
update-eligible crop. If selection has no eligible appearance, a later
accepted, continuously supported operator-ID observation may bootstrap it;
loss of that pre-anchor operator lineage prevents delayed bootstrap.
The anchor remains fixed. After a trusted `LOCKED` streak of two updates,
accepted update-eligible, unambiguous and non-negative observations can update
the adaptive EMA (alpha 0.10) and admit distinct gallery entries (max four;
near-duplicates at similarity >= 0.98 are not appended). Recovery resets
lineage trust and does not immediately rewrite the protected identity.
The adaptive prototype supports routine continuity but cannot independently
authorize an ID switch or long-gap recovery.

The active AB-16 source guard suppresses a second adaptive EMA update from
the same source observation (image timestamp preferred; source frame is the
fallback). Missing provenance keeps the prior behaviour. It does not suppress
MARS inference, change alpha, or block trusted-gallery admission. Low-quality
or overlapping crops are comparison-only and cannot update positive memory.

Hard-negative learning happens **after** an accepted current-frame candidate
and only during uninterrupted trusted `LOCKED` same-ID continuity with an
eligible selected crop. A distractor must have a usable crop, geometry at
least 0.20, positive similarity at least 0.70 yet no more than 0.95 to
protected anchor/gallery, and two trusted observations before promotion.
The 0.95 exclusion protects target-like duplicate fragments. At most eight
committed prototypes are retained; merge alpha is 0.20. Entries retain
source/selected IDs, frame/time, bbox/crop and appearance provenance.
Pending observations are discarded when trusted continuity breaks, and a
newly accepted selected identity is reconciled out of negatives. Committed
entries remain full strength until expiry after age >247 tracker frames;
expiry is transacted during trusted acceptance, not pre-score retirement.

## Controller-facing publication and timing boundary

`TargetMemoryOutput.control_valid` is true only for `NORMAL` mode.
With the canonical `zero_id_when_not_visible=true`, the ROS conversion
publishes ID=0, zero geometry, score and quality for non-valid output on
`/target_memory_mars`; diagnostic status still exposes candidate,
suppression reason, state, scores and memory events on
`/target_memory_mars/status`. Output carries the track source stamp/frame.
The node reports source age, duplicate/future/stale classification using
`freshness_max_output_age_s=0.90` and future tolerance 0.05 s. The TIM node reports this classification but does not itself zero a
LOCKED target solely because the source stamp is stale. The downstream
control-reference node independently checks source and receive age and zeros
non-fresh commands. These timing gates are separate from identity scoring. A held target box in memory is never, by itself, controller
authority. See `output_freshness_contract.md` and the #50 physical gate
before making an FCU-response claim.

## Canonical parameters and computation boundary

All values below are from the canonical YAML, not `TargetMemoryConfig`
class defaults. Geometry weights and sigmas are in the scoring equation.
Algorithmic values: confidence floor 0.10; locked/lost thresholds 0.52/0.60;
same-ID relief 0.08; ambiguity 0.07; uncertain horizon 6 updates; recovery
confirmation 1 additional update; short-gap grace 8, minimum 0.30,
new-ID thresholds 0.70/0.85; ID-switch appearance 0.78; positive appearance
weight/minimum 0.12/0.35; adaptive alpha 0.10; trusted gallery max 4,
anchor agreement floor 0.75, trusted-lock streak 2; hard-negative max 8,
alpha 0.20, candidate minimum 0.70, confirmation 2, protected-positive
exclusion 0.95, rejection similarity/margin 0.80/0.03, geometry floor 0.20,
age 247 with `none_until_expiry`; conservative minimum/margin 0.65/0.05;
global LOST start 9; rank-aware geometry/distance/appearance/margin
0.40/0.10/0.05/0.03. The exact active booleans are in the YAML and the
sections above.

Runtime/transport values: causal image age <=250 ms; encode interval >=250
ms; cache TTL <=750 ms with centre-distance <=0.25 and scale-ratio >=0.25;
crop width >=12 px, height >=24 px, clipping <=0.10, aspect in
[0.20,1.00], memory overlap IoU <=0.10 and centre separation >=0.04;
MARS batch size 32; output age <=0.90 s and future tolerance 0.05 s.
Image dimensions, topics, selected ID and model path are launcher values.
The detector's 640x640 input and VGA-versus-HD source decision are outside
this frozen identity algorithm. For `N` candidate tracks, scalar scoring is
linear in `N` for bounded galleries/negative memory, followed by sorting
`O(N log N)`; crop overlap/quality checks and embedding extraction add
separate image/workload costs. No fixed FPS follows from this complexity;
#32 measures integrated mounted runtime after #64 and #50.

## Explicitly non-active development mechanisms

The canonical YAML disables candidate-belief recovery, absence-recovery
policy, ID-switch spatial gate, and protected-gallery consensus recovery.
AB-14 changed confirmation, AB-15 retired negatives before scoring, and
AB-19 altered development appearance behaviour; none was promoted at Stage-7.
Development-only ablation switches, old-ID distrust/handoff variants,
active appearance-first reselection, hold-last-on-reject, historical V4 risk
presets, and `geometry_winner` selective ReID experiments are not the final
algorithm. FHD is not the active source profile. Historical parameter values
in `tim_mars_evidence_versions.md` belong to their own evidence versions.

## Behaviour-to-test map

| Claimed behaviour | Focused test authority |
| --- | --- |
| Selection, same-ID continuity, miss states, clear and ambiguity | `test_target_memory_synthetic.py` |
| Selection epoch and immediate authority revocation | `test_tim_mars_selection_generation.py` |
| Canonical parameter loading and active/inactive switches | `test_tim_mars_ros_params.py` |
| ID-switch rejection and same-ID hijack | `test_target_memory_identity_lineage.py`, `test_target_memory_appearance.py` |
| Fresh same-ID challenge and available-image rule | `test_tim_identity_resilience.py` |
| Unified transactional gate and non-mutating rejection | `test_target_memory_transactional_gate.py` |
| Protected anchor, gallery and adaptive separation | `test_target_memory_protected_appearance.py` |
| Source-aware repeated adaptive-update suppression | `test_ab16_production_promotion.py` |
| Negative staging, trusted commit, reconciliation and expiry | `test_target_memory_hard_negative_transaction.py`, `test_hard_negative_lifecycle_provenance.py` |
| Target-fragment exclusion | `test_target_memory_hard_negative_fragment_safety.py` |
| Short-gap and rank-aware probation/confirmation | `test_target_memory_synthetic.py`, `test_target_memory_rank_aware_reacquisition.py` |
| Long-gap protected recovery, ambiguity, negatives and clear | `test_target_memory_global_reacquisition.py` |
| Causal image choice and stale image skip | `test_tim_mars_runtime.py` |
| Cache generation, absence, jumps and invalid timestamps | `test_appearance_cache_identity_safety.py` |
| Zero controller fields, diagnostic status and freshness classification | `test_tim_mars_ros_messages.py`, `test_target_memory_mars_node_static.py`, `test_freshness.py` |

These are deterministic method tests, not substitute physical controller
evidence. The held-out evidence contract is in the Stage-7 freeze; the final
architecture comparison is recorded as **post-access protocol-repair**
evidence in `docs/results/selected_target_tracking/p058_heldout_architecture_comparison_20260916.md`.
Its retained first run and repairs must remain visible in thesis results.
EOF'