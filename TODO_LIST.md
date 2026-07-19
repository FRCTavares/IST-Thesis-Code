# TIM-MARS Thesis Roadmap

## Purpose

This is the active repository-grounded roadmap for turning TIM-MARS into a coherent, reproducible, and defensible Master's thesis contribution.

Priority:

- P0: blocks trustworthy results or the final thesis claim;
- P1: major algorithmic or scientific work;
- P2: useful improvement;
- P3: optional future work.

## Phase 0 — 5-day offline sprint -> live flight (Fri 17 Jul -> Wed 22 Jul)

**This is the active work order. Start at the top of Day 1 and do not skip the Day-1 gate.**

Premise: real drone bags can be replayed offline, so this week includes real
algorithm/perception experiments, not just readiness checks. Two rules hold the week
together:

- **Gate before A/B.** Controlled offline replay is now deterministic through
  the shared ROS-free runtime and complete-timeline runner. Three identical Seq04
  runs produced frame-level-identical target and status streams and exactly equal
  metrics. Algorithm A/B tests may now use this runner, but preservation on May,
  Seq01, and Seq03 remains required before the synchronization change is committed.
- **Offline-green != live-certified.** Replays use different image-age/cache/recompute
  values than the drone (F4), so the live appearance wiring (P0.8), the live config
  profile (F4), control-sign checks, and Pi thermals are live-only and reserved for
  the day before flight.

Everything below is flag-gated with the current path as default; wrong-target
increase blocks promotion; MARS stays default (no Hailo-ReID this week — needs x86
compile + int8 margin re-validation, no time to do safely).

### Day 1 (Fri 17) — GATE: make replay trustworthy
- [x] **P0.9 deterministic image-track sync for controlled offline evaluation** —
  preload the complete valid image timeline, process tracks in deterministic
  semantic-time order, and avoid ROS callback scheduling and wall-clock timing hacks.
- [x] Add frame-level diagnostics for track timestamp, selected image timestamp,
  image age, skip reason, candidate IDs, and proposal/publication reason.
- [x] Prove Seq04 repeatability across three runs:
  - 1547 target messages per run;
  - 1547 status messages per run;
  - identical target SHA-256 across all runs;
  - identical status SHA-256 across all runs;
  - exactly equal correctness summaries.
- [x] Rerun May, Seq01, and Seq03 on the matching canonical evidence bags:
  - May reference: correct 0.965, wrong 0.000, lost 0.035;
  - Seq01: correct 1.000, wrong 0.000, lost 0.000;
  - Seq03: correct 0.655, wrong 0.290, lost 0.054.
- [ ] Run complete verification and commit the deterministic synchronization change.

### Day 2 (Sat 18) — perception A/B on the now-trustworthy replay
- [ ] Detector: wire prebuilt **YOLOv8m / YOLO11m @640** (person class) as opt-in
  `--detector`, current HEF default. Verify `/detections` schema unchanged,
  `hz /detections` >= camera rate, recall better on a distant/occluded bag. Keep only
  if it wins; else fly current detector.
- [ ] Tracker A/B: **ByteTrack (anchor) vs OC-SORT** on crossing/occlusion bags, same
  frozen config. Add SORT if time. Single replay each is now valid post-P0.9.
- [ ] Record results into the P0.18 / Phase-10 tables. One variable per run.

### Day 3 (Sun 19) — ground dry-run + record
- [ ] **P0.8 fix live appearance wiring** (launcher must honour the resolved
  `--no-appearance`, not hardcode `appearance_enabled:=true`).
- [ ] Freeze the **live config profile** (F4): decide image-age/cache/recompute for
  flight, write it down, commit.
- [ ] Run the *exact* live command on the ground (`--record --record-mavros`), person
  walking/crossing/leaving frame. Confirm ~30 Hz on critical topics, ports up,
  dashboard/UI, sane TIM state transitions and `cmd_vel`. Watch **CPU + thermals**
  over a sustained run.

### Day 4 (Mon 20) — stabilize + control safety
- [ ] Repeat the ground dry-run until stable across 3 runs.
- [ ] **Control-sign checks** (README §7): center->vx=0/yaw=0, left->yaw<0,
  right->yaw>0, far->vx>0, near->vx<0, stale->0. Run the isolated test node.
- [ ] If feasible: tethered / low-hover test with a spotter before free flight.

### Day 5 (Tue 21) — freeze + flight checklist. NO CODE AFTER TODAY.
- [ ] Commit the live profile + any kept Day-2 swaps; clean tree
  (`git status --short --ignored`, no `log/` or `hailort.log`).
- [ ] Write flight-day checklist: camera preflight, port checks, arm, stop via the
  `pkill` line, explicit abort criteria (kill-to-manual on any wrong-target lock).
- [ ] Batteries charged; SD space for bags confirmed.

### Wed 22 — FLY
- [ ] Several short runs > one long run. Record everything (`--record --record-mavros`).
- [ ] The recorded UAV-motion bag is the prize: it is the held-out
  UAV-motion/small-person sequence your evaluation is missing (P1.12, NOVELTY
  §8.2/§10.8). Treat live metrics as qualitative + systems evidence only (F4) — not
  promoted numbers.

---

## Consolidation note (16 July 2026)

This file is now the single source of truth for what to do next. The actionable
roadmap from `TIM_COMPLETE_ALGORITHM_REVIEW.md` has been folded in here (findings
index + delivery calendar below); that file remains as the narrative reviewer
critique and no longer holds any to-do item not represented here. New onboard
pipeline priorities (detector, tracker pairing, ReID placement) are in **Phase 10**.

Integrity note: the onboard pipeline upgrades are mostly **deferred behind the
evidence-chain repair**. The near-term critical path is F2 closure + decision-logic
repair, not model swaps. The only near-term Phase-10 item is the tracker x TIM
matrix, which already lives on the critical path as P0.18.

### Algorithm-review findings -> owning task (quick index)

- **F1** appearance-crop coordinate-frame mismatch — RESOLVED 2026-07-15 (`f8ab0c0b`).
  Key result: the fix did **not** change reported numbers, so the ceiling is the
  decision logic and/or MARS-small128 separability, not crops. Owner: P0.8a.
- **F2** paper / canonical YAML / NOVELTY describe three algorithms — IN PROGRESS;
  infra landed (digest `11ae1b8f...29f8a3e`). Closure = F3 removal + paper/NOVELTY
  text reconciliation + commit causal-timestamp impl + **regenerate promoted table
  under the committed config**. Owner: P0.4 / P0.5 / P0.20.
- **F3** dead parameters published as method (`max_lost_frames`,
  `rank_aware_missing_ttl_frames`) — now a subtask blocking F2. Owner: P0.4 / P1.15.
- **F4** evaluated pipeline != live pipeline; tables came from an offline simulator
  whose node-equivalence is asserted, not shown. Owner: P0.5 + equivalence harness.
- **FM1** same-ID trust transfer (wrong lineage kept because tracker ID persists).
  Owner: P0.6 unified gate + P1.4 protected anchor.
- **FM2** far re-entry structurally unreachable from a stale last-seen box.
  Owner: P0.6 recovery mode + Phase 10 re-detection (deferred, paper-v2).
- **FM3** suppression / counter bookkeeping mis-attributes wrong vs lost.
  Owner: P0.9 sync + P1.1 counter merge.
- **§23 vNext** single transactional gate, 24-parameter set, scene-relative margin
  `m` — the end-state that P0.6 / P1.1 / P1.2 / P0.12 collectively build toward.

### Delivery calendar (deadline 2026-10-31)

Critical path, in order. Nothing downstream starts until the F2 regeneration lands.

1. **Now -> ~Jul 19 (close F2, no algorithm changes):** remove/deprecate dead
   params (F3); rewrite paper Table I + NOVELTY tables as projections of the frozen
   YAML; commit the causal-timestamp impl; **regenerate the promoted table under the
   committed canonical config**. Run the reason-attribution script over
   Seq01/May/Seq03 to see whether the unchanged post-F1 results are dominated by FM1,
   FM3, or FM2. Deterministic image-track sync (P0.9) gates a clean regeneration.
2. **~Jul 20 -> Aug 7 (refactor + regenerate):** Phase 2/3/4 deletions + counter
   split (P1.1) + seconds-based hysteresis + cache invalidation (P0.10), behind the
   ported tests; node/simulator equivalence harness (P0.5 / F4); regenerate the 3
   paper + 4 NOVELTY rows under the frozen config — these become the thesis's only
   quoted numbers; DeepSORT rerun with attribution (P0.2 -> NOVELTY §10.4).
3. **Aug 8 -> Aug 31 (evidence):** ablations (P0.17); sensitivity sweep over
   surviving thresholds incl. `m` (P1.13); event-level + target-absent-output +
   identity-independent spatial check (P1.10 / P1.11). Stretch only if on schedule:
   gallery + scene-relative margin + same-ID monitor as one change-set. **Do not
   start re-detection mode before Sep 1.**
4. **September (writing):** failure-analysis chapter from reason attribution;
   limitations state FM2 as structural scope, not tuning; optional risk-coverage
   figure; re-measure runtime table (P1.14) after lazy encoding.
5. **October:** buffer, freeze, provenance audit (every number -> a table row),
   deliver Oct 31. Nothing new after ~Oct 7.

Effort: the Jul-Aug plan is ~15-20 focused implement+replay days; all bag-replay,
no new flights required for the core story.

## Current audit snapshot

Confirmed repository facts as of 16 July 2026:

### 16 July causal timestamp and reproducibility update

- the causal timestamp-alignment implementation is currently uncommitted;
- current source changes include:
  - `target_memory_mars_node.py`;
  - `test_target_memory_mars_node_static.py`;
  - new `test_target_memory_mars_node_timestamps.py`;
  - new `tools/visualization/render_tim_comparison_video.py`;
- generated supervisor videos exist under
  `videos/tim_mars_supervisor_comparison/`;
- generated videos should not be committed unless large media is intentionally
  versioned;
- `thesis_bringup` builds successfully;
- current focused TIM-MARS validation passes with:
  - `80 passed, 4 xfailed`;
  - `12 passed` timestamp-focused tests;
  - `15 passed` appearance-attachment tests;
- Python compilation and `git diff --check` pass;
- the canonical parameter source remains:

      ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml

- the current canonical configuration SHA-256 is:

      11ae1b8f3cb589abcbcbfe4d7448b4d437ebed4ee71bf0878109a31c829f8a3e

- the source and installed canonical YAML copies match;
- the obsolete parameters `max_lost_frames` and
  `rank_aware_missing_ttl_frames` have no active code, installed-package, or
  canonical-YAML references;
- the previous appearance attachment used the newest callback-visible image;
- June `/tracks` messages arrive approximately 73-82 ms after image messages,
  so the former implementation could attach future-frame appearance evidence;
- the current causal implementation:
  - stores appearance images in timestamp order;
  - prefers the `/tracks` header timestamp;
  - falls back to `src_stamp_ns` only when the header is unavailable;
  - rejects images and tracks without trustworthy message timestamps;
  - selects only the latest image satisfying
    `image timestamp <= track timestamp`;
  - does not mix ROS message timestamps with monotonic process time;
- causal timestamp behavioural tests cover:
  - header-time priority;
  - source-time fallback;
  - missing-time rejection;
  - exact timestamp matching;
  - latest causal-image selection;
  - future-image rejection;
  - clock-domain isolation;
- original F2 canonical results at commit `06de21dd` were:

| Sequence | Correct | Wrong | Lost | Absent output |
|---|---:|---:|---:|---:|
| May | 0.417 | 0.535 | 0.049 | 0.000 s |
| Seq01 | 1.000 | 0.000 | 0.000 | 0.000 s |
| Seq03 | 0.721 | 0.225 | 0.054 | 0.000 s |
| Seq04 | 0.736 | 0.149 | 0.116 | 7.025 s |

- representative causal timestamp results were:

| Sequence | Correct | Wrong | Lost | Absent output |
|---|---:|---:|---:|---:|
| May | 0.955 | 0.011 | 0.034 | 0.000 s |
| Seq01 | 1.000 | 0.000 | 0.000 | 0.000 s |
| Seq03 | 0.653 | 0.292 | 0.054 | 0.000 s |
| Seq04 illustrative run | 0.776 | 0.078 | 0.146 | 5.637 s |

- May improves dramatically under causal image selection;
- Seq01 remains perfect;
- corrected Seq03 remains substantially better than raw ByteTrack but still
  contains unsafe wrong-target publication;
- the older Seq03 result may have benefited from future-frame appearance
  leakage and must not automatically be treated as more valid;
- the earlier causal ROS replay remained scheduler-dependent and produced
  materially different wrong/lost allocations across identical Seq04 runs;
- the deterministic complete-timeline runner removes callback-order dependence;
- three deterministic Seq04 runs produced:

| Run | Correct | Wrong | Lost | Absent output |
|---|---:|---:|---:|---:|
| r1 | 0.770 | 0.069 | 0.161 | 2.805 s |
| r2 | 0.770 | 0.069 | 0.161 | 2.805 s |
| r3 | 0.770 | 0.069 | 0.161 | 2.805 s |

- all three `/target_memory_mars` streams contain 1547 messages and share SHA-256
  `e63dc19fb5b18839c1c3b53edda642ee2a5b4f751a049238cc7de9b6b3b708f0`;
- all three status streams contain 1547 messages and share SHA-256
  `72559bc777aca76b7fa6f1e10f14d5aed798e590121e187899b805aeaf4d678a`;
- deterministic synchronization is therefore established for controlled offline
  replay;
- Seq04's 0.069 wrong ratio and 2.805 s target-absent output are now confirmed
  reproducible algorithmic safety failures;
- four raw-versus-TIM supervisor videos and H.264 copies were generated under:

      videos/tim_mars_supervisor_comparison/

- the Seq04 video is explicitly labelled as an illustrative nondeterministic
  replay.

### Previously confirmed structural findings

- the failed six-file trusted-same-ID experiment was preserved as a diagnostic
  patch and reverted from the main working tree;
- the guarded diagnostic implementation remains isolated on branch
  `diagnostic/trusted-same-id-bypass-2026-07-14` and was not merged;
- the current canonical main implementation is identified by commit
  `73ed19dd` for the clean replay evidence and commit `3aa39572` after adding
  failure-characterization tests;
- the earlier focused baseline passed with `42 passed, 3 xfailed`;
- the current expanded focused suite passes with `80 passed, 4 xfailed`;
- the four current `xfail` tests are explicit unresolved safety specifications
  rather than accidental failing tests;
- four additional characterization tests reproduce the current unsafe
  behaviours:
  - contradictory appearance can be ignored during a single-candidate ID
    switch;
  - a wrongly reacquired ID becomes `LOCKED` on the next same-ID frame;
  - the wrong locked lineage can update positive appearance memory;
  - a candidate can enter hard-negative memory before acceptance and remain
    there after becoming selected;
- clean canonical replay on commit `73ed19dd` reproduced:
  - Seq01 TIM-MARS: `1.000 / 0.000 / 0.000`;
  - May TIM-MARS: `0.944 / 0.015 / 0.041`;
- Seq03 ByteTrack annotations were found to describe the wrong physical target
  and were corrected in commit `3ff6164c`;
- the corrected Seq03 target lineage begins with tracker ID `2` and later uses
  IDs `8`, `12`, `17`, and `13`;
- appearance crops were confirmed to have a coordinate-frame defect:
  - candidate boxes were expressed in the stretched 640 x 640 inference frame;
  - June appearance images were native 640 x 480 `/camera/dashboard` frames;
  - MARS previously received the inference-frame boxes without vertical
    remapping;
- commit `f8ab0c0b` maps appearance crop boxes into the actual appearance-image
  dimensions before MARS encoding while preserving candidate geometry;
- focused validation after the mapping change passed:
  - 15 appearance-attachment tests;
  - 40 focused TIM-MARS tests;
  - Python compilation;
  - changed-line lint;
  - `thesis_bringup` build;
- the memory replay runner now automatically selects:
  - `/camera/dashboard` when present;
  - otherwise `/camera/image_raw`;
  - while preserving an explicit environment override;
- active mapped-appearance replay produced:
  - Seq01 TIM-MARS: `1.000 / 0.000 / 0.000`;
  - May TIM-MARS: `0.944 / 0.015 / 0.041`;
  - corrected Seq03 TIM-MARS: `0.650 / 0.288 / 0.062`;
- the corrected Seq03 result shows a major improvement over raw ByteTrack
  (`0.147 / 0.566 / 0.286`) but still contains substantial wrong-target
  publication and therefore remains a primary algorithmic failure case;
- both clean replays used canonical configuration SHA-256
  `5871bc351a78c252a22cfa7ee81f951658b031c35626150979c5ef844f97e4d1`;
- the replay metadata records the exact Git commit, command, source bag,
  annotation, canonical configuration, runtime overrides, and fingerprints;
- the repository was marked dirty during those replays only because
  `TODO_LIST.md` contained an unrelated unstaged roadmap edit;
- controlled diagnostics previously demonstrated that disabling
  `hard_negative_max_positive_similarity` degrades May catastrophically while
  Seq01 remains correct, so the threshold currently compensates for an
  upstream identity-integrity defect;
- the May hard-negative status timeline contains 950 status messages,
  2,785 candidate-score rows, 33 hard-negative-risk frames, and seven
  contiguous risk episodes;
- those seven episodes contain 11 direct hard-negative vetoes;
- at least one direct veto rejects uninterrupted same-ID continuity of the
  currently selected lineage;
- other episodes show candidate IDs `2`, `41`, and the returning original ID
  being treated as negative-like at different lineage stages;
- hard-negative memory is currently updated during candidate preparation,
  before final acceptance, and is not reconciled when a candidate later
  becomes selected;
- hard-negative entries contain appearance prototypes without source identity,
  insertion frame, observation count, trust, expiry, or selected-lineage
  reconciliation;
- therefore hard-negative contamination is now directly demonstrated rather
  than only hypothesized;
- same tracker ID, strong geometry, and high adaptive appearance are still not
  sufficient proof of physical-target continuity;
- positive appearance memory may adapt toward a wrongly accepted identity;
- candidate-generation policies still have parallel acceptance paths;
- `target_memory.py` remains too large and difficult to verify as one ordered
  algorithm;
- evaluation scripts still lack dedicated metric and freshness tests;
- documentation still contains stale paths and obsolete guidance.

## Phase 1 — Repair the evidence chain


### Engineering principle

A heuristic that prevents catastrophic failure must not be removed simply
because it appears ad hoc.

If removing a threshold causes catastrophic degradation, first determine
whether that threshold is compensating for an upstream algorithmic flaw.

Structural correctness has priority over threshold tuning.


### P0.1 Resolve the disputed May result — DONE

Resolved on 12 July 2026.

Findings:

- the old `0.728 / 0.118 / 0.154` raw result and `0.963 / 0.003 / 0.034` TIM result were generated before the annotation correction;
- commit `6a4ef843` moved the correct target-ID handover boundary from 48.800 s to 50.233 s;
- the canonical post-correction report gives:
  - raw ByteTrack: `0.708 / 0.138 / 0.154`;
  - ByteTrack + TIM-MARS: `0.943 / 0.024 / 0.034`;
- the pre-correction report is retained only for provenance.

Acceptance condition:

- [x] one source bag;
- [x] one current annotation file;
- [x] one canonical report;
- [x] one corrected set of quoted numbers;
- [x] obsolete values identified as pre-correction evidence.

### P0.2 Reproduce the historical unsafe DeepSORT result

Historical generated result:

- raw DeepSORT wrong ratio: 0.028;
- DeepSORT + TIM-MARS wrong ratio: 0.466.

Evidence status:

- the generated reports remain;
- the replay bag was deleted during the 9 July 2026 cleanup;
- preserved metadata confirms that the deleted bag contained `/tracks`, `/target`, `/target_memory_mars`, `/target_memory_mars/status`, and `/camera/image_raw`;
- the source DeepSORT bag still exists;
- the exact resolved TIM configuration was not preserved with the deleted replay.

Tasks:

- [x] Confirm that the historical replay bag was deleted.
- [x] Confirm that the source DeepSORT bag still exists.
- [x] Reclassify the result as historical and unresolved rather than final reproducible evidence.
- [ ] Record a canonical TIM configuration before rerunning.
- [ ] Regenerate the selected-ID memory replay from the surviving source bag.
- [ ] Preserve the new replay bag, status stream, resolved configuration, command, and Git commit.
- [ ] Confirm annotation compatibility.
- [ ] Confirm selected-ID initialization.
- [ ] Inspect the first wrong handover visually and through status reasons.
- [ ] Determine whether failure comes from:
  - geometry assumptions;
  - rank-aware recovery;
  - appearance memory;
  - tracker-ID semantics;
  - mirrored selection;
  - stale embeddings;
  - configuration mismatch.
- [ ] Add a regression sequence if the failure is algorithmic.
- [ ] Keep tracker-independent claims disabled until reproduction is complete.

### P0.3 Freeze the canonical evidence set

- [ ] Mark every promoted bag as:
  - autonomous;
  - annotation-driven diagnostic;
  - memory-only replay;
  - full-pipeline replay.
- [ ] Remove `valid_for_evaluation: true` from catalogue entries whose annotation compatibility is not proven.
- [ ] Clarify why Seq02 is non-final despite many catalogue entries.
- [ ] Record exact source lineage for every final row.
- [ ] Ensure generated and curated reports agree.

## Phase 2 — Establish one actual TIM-MARS algorithm

### P0.4 Freeze one canonical preset — CONFIGURATION DONE; CLEAN RESULT FREEZE PENDING

Completed on 12 July 2026.

Canonical source:

- `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`

Completed work:

- [x] Created one versioned canonical TIM-MARS YAML.
- [x] Verified every configured key is declared by the ROS node.
- [x] Installed the YAML through the `thesis_bringup` package.
- [x] Wired the live stack to the canonical YAML.
- [x] Wired clean replay to the canonical YAML.
- [x] Wired memory-only replay to the canonical YAML.
- [x] Wired detector replay to the canonical YAML.
- [x] Removed the active `MARS_TIM_PRESET` and silent `legacy` preset system.
- [x] Removed unsupported anchor-drift and group-split parameters from the active memory runner.
- [x] Restricted launcher overrides to runtime-specific parameters.
- [x] Verified the running ROS node loads representative canonical values.

Completed replay provenance work:

- [x] Serialize the canonical YAML into TIM experiment outputs.
- [x] Serialize all effective TIM runtime overrides separately.
- [x] Record canonical and resolved-runtime SHA-256 fingerprints.
- [x] Record the Git commit, repository state, runner, and exact command.

Remaining paper-code equivalence work belongs to P0.5.

Additional status as of 16 July 2026:

- [x] Designated the checked-in canonical YAML as the single parameter source
  of truth.
- [x] Confirmed all four causal replay cases used canonical SHA-256
  `11ae1b8f3cb589abcbcbfe4d7448b4d437ebed4ee71bf0878109a31c829f8a3e`.
- [x] Confirmed `max_lost_frames` and
  `rank_aware_missing_ttl_frames` are absent from active code and
  configuration.
- [x] Preserved bag, annotation, selected target, canonical hash, runtime hash,
  report, runner, and repository-state provenance.
- [x] Resolve deterministic image-track synchronization.
- [ ] Commit the causal timestamp and synchronization implementation.
- [ ] Regenerate the canonical matrix from a clean committed repository.
- [ ] Update `NOVELTY.md`, paper Table I, and promoted result tables only from
  clean committed reports.
- [ ] Treat current dirty-tree causal results as diagnostic evidence rather
  than final promoted evidence.

### P0.5 Prove paper-code-runner equivalence

- [ ] Write the final algorithm as ordered pseudocode.
- [ ] Map each pseudocode step to one code function.
- [ ] Map each parameter to the canonical YAML.
- [ ] Confirm every evaluated replay used that implementation.
- [ ] Record the Git commit used by each final result.
- [ ] Add a test that loads the canonical configuration.
- [ ] Update the paper and thesis if implementation order differs.

### P0.6 Replace parallel acceptance paths with one transactional safety gate

Current update order includes:

1. candidate preparation;
2. short-gap protection;
3. absence recovery;
4. rank-aware reacquisition;
5. score threshold;
6. ambiguity;
7. candidate belief;
8. ID-switch permission;
9. spatial gate;
10. hard-negative rejection;
11. `_accept()`;
12. conservative appearance rejection inside `_accept()`.

Current diagnostic evidence:

- rank-aware and other recovery policies can return through separate acceptance
  paths;
- moving an unqualified hard-negative veto into every acceptance path was unsafe
  because negative memory can be stale or contaminated;
- adding a strong same-ID bypass fixed Seq01 but protected a wrong lineage in
  May;
- `LOCKED` currently means that the latest candidate completed the state
  transition, not necessarily that it belongs to the operator-selected physical
  identity.

Tasks:

- [ ] Introduce a candidate proposal structure containing:
  - candidate and score;
  - proposal source;
  - previous and proposed tracker IDs;
  - same-ID or ID-switch classification;
  - required confirmation;
  - evidence availability;
  - memory-update eligibility;
  - diagnostic reason.
- [ ] Make short-gap, rank-aware, absence, and normal selection return proposals
  instead of calling `_accept()` directly.
- [ ] Create one final candidate safety gate.
- [ ] Ensure every proposal checks:
  - ID-switch permission;
  - geometry and motion plausibility;
  - ambiguity;
  - protected positive-anchor similarity;
  - adaptive appearance similarity;
  - current-frame distractor separation;
  - qualified hard-negative risk;
  - crop and synchronization quality;
  - temporal confirmation;
  - identity-lineage trust.
- [ ] Return `accepted`, `rejected`, or `pending` before mutating any state.
- [ ] Apply state transition only after final acceptance.
- [ ] Apply positive and negative memory updates only after trusted current-frame
  acceptance.
- [ ] Prevent a newly reacquired ID from automatically receiving the same trust
  privileges as an uninterrupted operator-selected lineage.
- [ ] Add tests proving that no proposal source bypasses the final gate.



### P0.6b Identify why structural safety heuristics are required

July 2026 diagnostics demonstrated that
`hard_negative_max_positive_similarity`
is currently preventing catastrophic May failures.

The objective is therefore **not** to tune or remove this threshold.
The objective is to identify the missing algorithmic invariant that makes
the threshold necessary, then eliminate that structural flaw.

A heuristic that cannot be removed without catastrophic degradation is
evidence of a missing invariant, not evidence that the heuristic itself is
wrong.

Completed diagnostic work:

- [x] Preserved and reverted the failed trusted-same-ID experiment.
- [x] Restored and reproduced the canonical Seq01 and May baseline.
- [x] Added explicit unresolved identity-safety specifications.
- [x] Added four tests characterizing the current unsafe behaviour.
- [x] Extracted the complete May status timeline with 950 status records.
- [x] Extracted 2,785 per-candidate score rows.
- [x] Grouped 33 hard-negative-risk frames into seven contiguous episodes.
- [x] Identified 11 direct hard-negative vetoes.
- [x] Demonstrated a direct same-ID hard-negative veto against the current
  selected lineage.
- [x] Demonstrated that the current selected identity can remain represented in
  hard-negative memory after a lineage transition.
- [x] Located hard-negative mutation before final acceptance in
  `_prepare_update_candidates()`.

Current structural conclusion:

- candidate scoring and proposal preparation currently mutate hard-negative
  memory before candidate identity has been resolved;
- a candidate may be inserted as a negative and later promoted to the selected
  lineage;
- no selected-negative reconciliation removes or invalidates that prototype;
- later same-ID, returning-ID, and rank-aware proposals can therefore be vetoed
  using contaminated evidence;
- this must be repaired before considering any broad same-ID bypass.

Remaining tasks:

- [ ] Audit every hard-negative insertion event across all canonical sequences,
  not only the seven May episodes.
- [ ] Document the independent evidence supporting every negative insertion.
- [ ] Separate "candidate rejected" from "candidate proven distractor".
- [ ] Require repeated trusted observations before committing a strong negative.
- [ ] Prove every hard-negative insertion has sufficient independent evidence.
- [ ] Move hard-negative mutation out of candidate preparation.
- [ ] Add selected-negative reconciliation after an accepted lineage change.
- [ ] Preserve the current safety threshold until the structural replacement is
  validated.
- [ ] Repeat Seq01 and May diagnostics after every structural change.

### P0.7 Fix rank-aware bypass risks

Add tests proving rank-aware recovery cannot bypass:

- [ ] `allow_id_switch_recovery=false`;
- [ ] hard-negative rejection;
- [ ] spatial rejection;
- [ ] ambiguity policy;
- [ ] required confirmation;
- [ ] canonical appearance constraints.

### P1.1 Simplify recovery confirmation

There are three nearly identical counters:

- candidate belief;
- absence recovery;
- rank-aware reacquisition.

Tasks:

- [ ] Replace with one candidate persistence tracker.
- [ ] Decide whether persistence is state-dependent.
- [ ] Use time-based confirmation or explicitly justify frame-based confirmation.
- [ ] Remove candidate belief if it has no demonstrated benefit.
- [ ] Remove absence recovery from the final path if it remains disabled.

### P1.2 Reduce `target_memory.py`

Target structure:

- candidate evidence preparation;
- candidate selection;
- unified safety gate;
- state transition;
- trusted memory update;
- output diagnostics.

Acceptance condition:

- algorithm flow can be understood without following multiple early-return branches;
- implementation matches thesis pseudocode;
- tests preserve behaviour.

## Phase 3 — Repair appearance integrity

### P0.8a Map appearance crops into the image coordinate frame — DONE

Completed on 15 July 2026 in commit `f8ab0c0b`.

Confirmed defect:

- tracker candidates use the stretched 640 x 640 inference coordinate frame;
- June appearance replay uses 640 x 480 `/camera/dashboard` images;
- MARS previously cropped the appearance image using unmapped inference-frame
  coordinates;
- this vertically displaced and distorted the physical crop region.

Completed work:

- [x] Added an explicit candidate-frame to appearance-image bbox mapping.
- [x] Applied independent horizontal and vertical scale factors.
- [x] Kept state-machine candidate geometry in the original inference frame.
- [x] Passed only mapped boxes to the MARS encoder.
- [x] Added identity-frame and 640 x 640 to 640 x 480 regression tests.
- [x] Added invalid-frame-geometry rejection.
- [x] Verified that active appearance features are generated during replay.
- [x] Made the replay runner select the available appearance topic
  automatically.
- [x] Reran Seq01, May, and corrected Seq03 with active mapped appearance.

Remaining implications:

- [ ] Apply equivalent coordinate-frame validation to the DeepSORT crop path.
- [ ] Add crop visualization or sampled crop export for direct visual checking.
- [ ] Do not reuse appearance thresholds obtained from geometrically invalid
  crops without a new controlled sensitivity analysis.

### P0.8 Fix live appearance wiring

`start_live_stack.sh` currently passes:

    appearance_enabled:=true

even though the CLI has `--no-appearance`.

Tasks:

- [ ] Pass the resolved appearance boolean.
- [ ] Add a launcher test.
- [ ] Remove obsolete HSV-only CLI options.
- [ ] Remove unused minimum-bbox-height options or connect them to MARS crop validation.

### P0.9 Synchronize image and track evidence

The previous runtime used the latest callback-visible image with current track
boxes. This allowed future-frame appearance leakage.

Completed:

- [x] Use image and track message timestamps rather than callback time.
- [x] Prefer the `/tracks` header timestamp.
- [x] Fall back to `src_stamp_ns` only when the header is unavailable.
- [x] Reject appearance attachment when no trustworthy track timestamp exists.
- [x] Discard appearance images with invalid header timestamps.
- [x] Store images in timestamp order.
- [x] Select only the latest image at or before the track timestamp.
- [x] Reject future images.
- [x] Preserve monotonic time only for local processing-latency measurement.
- [x] Add behavioural timestamp-selection tests.
- [x] Quantify image-track age distributions for May, Seq01, Seq03, and Seq04.
- [x] Demonstrate that the former implementation could use future-frame
  appearance evidence.
- [x] Rerun the four canonical cases under causal image selection.
- [x] Run three identical Seq04 repetitions.
- [x] Demonstrate material Seq04 replay nondeterminism.

Resolved replay blocker:

- the former ROS callback runner was scheduler-dependent because eligible images
  could reach the live buffer before or after the corresponding `/tracks` callback;
- the controlled offline runner now closes the evidence window by reading the full
  valid image timeline before processing tracks;
- three identical Seq04 runs produced frame-level-identical target and status
  streams;
- the remaining Seq04 wrong-target and target-absent publication are reproducible
  algorithmic failures rather than replay nondeterminism.

Tasks:

- [x] Add frame-level diagnostics for:
  - track timestamp;
  - selected image timestamp;
  - image age;
  - image sequence or identity;
  - appearance skip reason;
  - candidate IDs;
  - proposal and publication reason.
- [x] Identify the first divergent frame between two Seq04 repetitions.
- [x] Confirm whether divergent runs use different causal images or differ in
  whether an eligible image is available.
- [x] Extract tracker conversion, causal image selection, appearance attachment,
  and memory updates into a shared ROS-free runtime used by the ROS wrapper.
- [x] Introduce deterministic synchronization between image and track evidence for controlled offline evaluation by preloading the complete image timeline and processing tracks in deterministic semantic-time order.
- [x] Close the causal image-selection window in deterministic offline replay by reading the complete image timeline before processing any track message.
- [x] Define deterministic behaviour when no exact image timestamp exists: select the latest image timestamp not after the track timestamp and preserve the configured maximum-age rejection.
- [x] Avoid sleeps, wall-clock delays, ROS playback, and callback-scheduler dependence in the deterministic offline runner.
- [x] Preserve `appearance_max_image_age_ms` rejection through the shared appearance-attachment runtime.
- [x] Expose actual image-track offset in status diagnostics.
- [x] Add a deterministic ROS-free bag runner that:
  - reads the complete appearance-image and track timelines;
  - preloads valid timestamped images;
  - processes tracks by trustworthy timestamp, frame ID, original bag timestamp,
    and original sequence index;
  - writes deterministic `/target_memory_mars` and status streams;
  - streams original source messages in a second pass instead of retaining the
    complete serialized bag in memory.
- [x] Complete the first deterministic Seq04 smoke replay:
  - 467 appearance images loaded;
  - 1547 track messages processed;
  - 1547 TIM target and 1547 status messages written;
  - source evidence copied successfully;
  - peak resident memory approximately 1.24 GiB;
  - evaluator completed using header time.
- [x] Record the first deterministic Seq04 result as a synchronization baseline:
  - correct ratio 0.770;
  - wrong ratio 0.069;
  - lost ratio 0.161;
  - wrong-target duration 3.936 s;
  - target-absent output duration 2.805 s.
- [x] Establish that the 0.069 wrong ratio and 2.805 s absent-output duration
  are deterministic algorithmic safety issues rather than scheduler noise.
- [x] Test deterministic image-track correspondence:
  - image before track and latest-causal-image selection;
  - track before image and future-image rejection;
  - equal timestamps;
  - delayed but eligible causal image with exact offset diagnostics;
  - dropped or evicted images producing no causal image;
  - out-of-order image ingestion;
  - stale causal-image rejection through the full runtime;
  - invalid image and track timestamps.
- [x] Repeat Seq04 three times after synchronization.
- [x] Require stable frame-level output and metrics:
  - target stream count: 1547 in every run;
  - target stream SHA-256:
    `e63dc19fb5b18839c1c3b53edda642ee2a5b4f751a049238cc7de9b6b3b708f0`;
  - status stream count: 1547 in every run;
  - status stream SHA-256:
    `72559bc777aca76b7fa6f1e10f14d5aed798e590121e187899b805aeaf4d678a`;
  - TIM metrics in every run: correct 0.770, wrong 0.069, lost 0.161;
  - wrong-target duration in every run: 3.936 s;
  - target-absent output duration in every run: 2.805 s.
- [x] Rerun May, Seq01, and Seq03 to verify preservation.
- [ ] Commit only after deterministic repeatability passes.

### P0.10 Make appearance caching identity-safe

Status as of 17 July 2026: implementation, local verification, canonical
replay acceptance, final diff review, and GitHub Issue #12 closure complete.

The cache now binds every embedding to:

- tracker ID;
- tracker-instance generation;
- frame generation;
- source frame ID;
- source bounding box;
- embedding timestamp.

TIM-MARS derives lifecycle generations from the observed `/tracks` stream because
the recorded `Track2D` schema has no explicit lifecycle counter. Cache ownership
is invalidated after an observed track absence, a non-monotonic frame restart,
an invalid tracker timestamp, or an implausible centre or scale jump. The two
bbox-continuity limits are explicit canonical and ROS parameters.

Known limitation: an immediate same-ID reassignment with no observed absence and
a geometrically plausible bounding box cannot be proven from the current
`Track2DArray` evidence alone.

Verification completed:

- dedicated identity-safety contract: 8 passed;
- functional `thesis_bringup` suite: 106 passed, 4 expected xfails;
- deterministic replay-runner suite: 10 passed;
- `thesis_bringup` package build passed;
- Python compilation and `git diff --check` passed;
- no root `log/` or `hailort.log` runtime noise was created;
- package-wide ROS lint tests remain excluded because the repository already has
  broad unrelated flake8 and pep257 debt.

Canonical replay evidence:

- canonical configuration SHA-256:
  `149056bbad4895db658f9903d3ff30d8f6ac5238b3a99af5b76538e5472fcb40`;
- May remained `0.965 / 0.000 / 0.035` correct, wrong, and lost;
- Seq01 remained `1.000 / 0.000 / 0.000`;
- corrected Seq03 remained `0.655 / 0.290 / 0.054`;
- all three Seq04 runs remained `0.770 / 0.069 / 0.161`, with 3.936 s
  wrong-target duration and 2.805 s target-absent output;
- all three Seq04 target streams contain 1547 messages and share semantic
  SHA-256
  `e63dc19fb5b18839c1c3b53edda642ee2a5b4f751a049238cc7de9b6b3b708f0`;
- all three complete new status streams contain 1547 messages and share semantic
  SHA-256
  `64f137129e0d0c092f90f5534223da600a92a4b0e7c8ca0f6f3c618b47307789`;
- the target stream is identical to the clean pre-P0.10 baseline;
- the causal status audit passed: non-diagnostic changes were confined to frames
  260 and 261, where an observed absence invalidated one stale cached embedding;
- no target identity, state, reason, control mode, publication decision, or
  protected risk field changed during that invalidation event.

Evidence directories:

- `bags/replay/p010_identity_safe_2026_07_16/`;
- `reports/p010_identity_safe_2026_07_16/`.

Closure record:

- implementation commit `e5db8c3a` was pushed to `origin/main`;
- GitHub Issue #12 was closed as completed on 17 July 2026.

Tasks:

- [x] Include frame generation and bbox continuity.
- [x] Invalidate on implausible box jumps.
- [x] Invalidate when track lifecycle restarts.
- [x] Report embedding age per candidate.
- [x] Add an ID-reuse regression test.
- [x] Regenerate the canonical replay comparison and reject promotion if
  wrong-target publication increases.
- [x] Record the new canonical configuration SHA-256 after replay acceptance.

### P1.3 Add crop-quality controls

Status as of 17 July 2026: implementation, verification, canonical replay
acceptance, final diff review, and GitHub Issue #13 closure complete. The pure
crop-quality contract, unclipped geometry preservation, pre-encoding
filtering, sparse encoder alignment, cache-quality provenance, conservative
positive and negative memory gates, canonical and ROS parameter wiring,
deterministic-runner parity, and status diagnostics are implemented.

Replay investigation also exposed two unsafe recovery paths amplified by
reduced cache retention. Different-ID recovery now requires an embedding above
the dedicated appearance threshold, while same-ID geometry-only recovery is
permitted only during continuous `LOCKED` operation or confirmation of an
already evidence-backed `REACQUIRED` transition. Same-ID recovery from
`UNCERTAIN` or `LOST` requires current appearance evidence.

Canonical replay acceptance:

- May hard re-entry: `64.750 s` correct, `0.000 s` wrong, `2.950 s` lost, `0.000 s` target-absent output; deltas versus P0.10 are `-0.597 s` correct, `+0.000 s` wrong, `+0.597 s` lost, and `+0.000 s` target-absent output.
- Seq01: `122.340 s` correct, `0.000 s` wrong, `0.000 s` lost, `0.000 s` target-absent output; deltas versus P0.10 are `+0.000 s` correct, `+0.000 s` wrong, `+0.000 s` lost, and `+0.000 s` target-absent output.
- Seq03: `61.236 s` correct, `27.538 s` wrong, `6.953 s` lost, `0.000 s` target-absent output; deltas versus P0.10 are `-1.500 s` correct, `-0.249 s` wrong, `+1.749 s` lost, and `+0.000 s` target-absent output.
- Seq04: `42.897 s` correct, `1.358 s` wrong, `12.567 s` lost, `0.762 s` target-absent output; deltas versus P0.10 are `-0.854 s` correct, `-2.578 s` wrong, `+3.432 s` lost, and `-2.043 s` target-absent output.
- Seq04 was repeated independently with identical decoded target messages,
  decision-bearing status fields, and complete status payloads.
- The Seq03 audit found 11 wrong frames removed and four added. Two added
  frames extended an existing wrong-ID episode at an annotation boundary; two
  displaced a pre-existing wrong episode after longer conservative
  suppression. Total wrong duration still decreased by `0.249 s`.
- The accepted behavior is safety-positive but more conservative: wrong-target
  and target-absent publication do not increase on any canonical sequence, at
  the cost of additional lost-target duration on May, Seq03, and Seq04.
- Canonical configuration SHA-256:
  `6db6bed81506f7e5892b4983f541901976e68f1a7f2c0d5660c8e9dd3bd6601f`.
- Evidence:
  `bags/replay/p013_crop_quality_candidate_6db6bed8_2026_07_17/` and
  `reports/p013_crop_quality_candidate_6db6bed8_2026_07_17/`.

Before encoding, measure:

- [x] minimum pixel height and width;
- [x] clipping fraction;
- [x] aspect ratio;
- [x] overlap with nearby people;
- [x] centre distance to group members;
- [ ] optional blur or sharpness.

Sharpness remains deferred until a controlled measurement establishes a stable
threshold. It is not enabled through an arbitrary Laplacian-variance constant.

Do not update positive or negative memory from low-quality crops.

Diagnostic acceptance invariant:

- when appearance mode is enabled, a different tracker ID must not be accepted
  without an embedding or below the dedicated ID-switch appearance threshold;
- same-ID continuity may remain geometry-driven while operation is continuously
  `LOCKED`;
- same-ID confirmation may complete from `REACQUIRED` without a fresh embedding
  because entry to `REACQUIRED` has already passed the applicable evidence gates;
- after `UNCERTAIN` or `LOST`, even the same tracker ID requires an actual
  appearance embedding before acceptance;
- appearance-disabled operation preserves the existing geometry-only fallback;
- the May accepted-switch audit found wrong similarity `0.695` and correct
  similarities `0.852` and `0.893`; the canonical threshold `0.78` lies inside
  that observed separation and passed May, Seq01, Seq03, and Seq04 replay
  validation;
- remaining protected-versus-adaptive appearance-memory failures belong to
  P1.4 and must not be addressed by further P1.3 threshold tuning.

### P1.4 Separate protected and adaptive appearance memory — DONE

Status as of 17 July 2026: implementation, deterministic A/B safety
acceptance, Seq04 semantic repeatability, canonical promotion, and local
verification complete.

The positive-memory design now separates:

- an immutable operator-selection anchor;
- a bounded trusted multi-pose gallery;
- an adaptive recent prototype;
- a provenance-aware hard-negative gallery.

Risky ID-switch and long-gap candidates are authorized only by protected anchor
or trusted-gallery evidence. Adaptive similarity cannot independently authorize
a lineage after adapting to it. Gallery-only authorization additionally requires
an eligible crop, a non-ambiguous candidate, and immutable-anchor agreement of
at least `0.75`.

Completed rules:

- [x] Preserve an operator-selected anchor independently of adaptive memory.
- [x] Never replace the anchor merely because a reacquired ID reaches `LOCKED`.
- [x] Compare ID-switch and long-gap candidates against the protected anchor and
  trusted gallery.
- [x] Update adaptive memory only after stable trusted lock.
- [x] Prevent adaptive similarity from independently authorizing an adapted
  lineage.
- [x] Prevent circular acceptance and self-confirming adaptive updates.
- [x] Prevent positive updates on the first accepted ID-switch frame.
- [x] Prevent updates during `UNCERTAIN`, `LOST`, or unconfirmed `REACQUIRED`.
- [x] Prevent updates during ambiguity or unresolved hard-negative conflict.
- [x] Prevent updates from weak, clipped, tiny, overlapping, stale, or otherwise
  memory-ineligible crops.
- [x] Record the supporting memory source for every acceptance.
- [x] Add a regression proving that a stable wrong reacquisition cannot overwrite
  the original anchor.
- [x] Add bounded-gallery and hard-negative-provenance contracts.
- [x] Add a regression proving adaptive-only similarity cannot authorize an ID
  switch.
- [x] Add regressions for gallery anchor agreement, ambiguous candidates, and
  ineligible crops.
- [x] Wire the protected-memory configuration through ROS and canonical YAML.
- [x] Run baseline, initial protected, and corrected protected A/B replays.
- [x] Reject the initial protected candidate after Seq04 wrong-target and
  target-absent publication increased.
- [x] Promote only the independently anchored `0.75` gallery candidate.
- [x] Repeat corrected Seq04 three times with semantic target, semantic status,
  and metric identity.

Canonical replay acceptance:

- May: `63.380 s` correct, `0.000 s` wrong, `4.320 s` lost, and
  `0.000 s` target-absent output.
- Seq01: `122.340 s` correct, `0.000 s` wrong, `0.000 s` lost, and
  `0.000 s` target-absent output.
- Seq03: `65.395 s` correct, `12.284 s` wrong, `18.048 s` lost, and
  `0.000 s` target-absent output.
- Seq04: `40.343 s` correct, `0.000 s` wrong, `16.479 s` lost, and
  `0.000 s` target-absent output.
- No evaluated sequence increased wrong-target or target-absent publication.
- Aggregate deltas versus P1.3 are `+0.235 s` correct, `-16.612 s` wrong,
  `+16.377 s` lost, and `-0.762 s` target-absent output.
- The accepted behavior is safety-positive but more conservative.

Repeatability and provenance:

- all three corrected Seq04 runs contain 1547 targets and 1547 statuses;
- target semantic SHA-256:
  `16dffb2fa6462bb25cb1ef6a071d9809332fba669ef9f62c48525068d78fd6f7`;
- status semantic SHA-256:
  `00d6e3d2375a31b08accd566b2bcc73d723de3f3c655e3aeb81c85c134e8bcf0`;
- accepted replay-profile SHA-256:
  `9028966c4efb98a03ebdec00f237df411e398cccbd9b8e32ecfd5ddae4718007`;
- promoted canonical configuration SHA-256:
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`;
- replay and canonical YAML parameter values are semantically identical;
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`;
- replay evidence:
  `bags/replay/p014_protected_memory_2026_07_17/protected_anchor075/`;
- tracked evidence:
  `reports/p014_protected_appearance_2026_07_17/`.

Verification completed:

- non-linter `thesis_bringup` suite: 145 passed, 3 deselected, 3 expected
  xfails;
- deterministic replay-runner suite: 12 passed;
- Python compilation passed;
- `thesis_bringup` package build passed;
- `git diff --check` passed;
- no root `log/` or `hailort.log` runtime noise was created.

Closure record:

- implementation commit `a4c7b1e1` was pushed to
  `origin/main`;
- GitHub Issue #14 was closed as completed on 18 July 2026;
- closure evidence:
  `https://github.com/FRCTavares/IST-Thesis-Code/issues/14#issuecomment-5008378396`.

### P1.5 Fix positive-memory bootstrap

Current bootstrap can occur during scoring when the same tracker ID has an embedding.

Tasks:

- [ ] bootstrap only after a trusted current-frame acceptance;
- [ ] require crop-quality validation;
- [ ] record bootstrap frame and evidence;
- [ ] test same-ID hijack before first embedding.

## Phase 4 — Repair hard-negative memory

### P0.11 Move hard-negative updates after trusted acceptance

Current update occurs during candidate preparation before the current frame is
finally accepted. This ordering defect has now been reproduced in a dedicated
characterization test and observed in the May replay status timeline.

May diagnostic evidence:

- 33 hard-negative-risk frames;
- seven contiguous risk episodes;
- 11 direct hard-negative vetoes;
- selected/candidate transitions involving IDs `1`, `2`, and `41`;
- a direct veto where selected ID `2` and best candidate ID `2` are the same;
- a later direct veto where selected ID `41` rejects returning candidate ID `1`;
- repeated rank-aware vetoes after short-gap suppression has already moved TIM
  into `LOST`.

Current entries are appearance prototypes without enough provenance to
determine whether they remain trustworthy. The next implementation change must
be transactional rather than a threshold or bypass adjustment.

Required transaction order:

1. prepare immutable candidate evidence;
2. produce one candidate proposal;
3. validate the proposal through the final safety gate;
4. apply the accepted state transition;
5. reconcile negative memory with the accepted selected identity;
6. commit only independently proven distractors from a trusted current frame.

Tasks:

- [ ] update hard negatives only after confirming the selected target in the
  current frame;
- [ ] never update while the scene is ambiguous;
- [ ] never update during `UNCERTAIN`, `LOST`, or `REACQUIRED`;
- [ ] never create a hard negative solely because a candidate was rejected;
- [ ] require independent evidence that the candidate represents a different
  physical identity;
- [ ] distinguish 'candidate rejected' from 'candidate proven distractor';
- [ ] store source tracker ID, first and last frame, observation count, crop
  quality, geometry context, insertion reason, and trust level;
- [ ] require repeated observation before a distractor becomes a strong negative;
- [ ] remove or reconcile entries whose tracker ID later becomes selected;
- [ ] downweight or quarantine negatives that are extremely similar to a newly
  trusted positive anchor;
- [ ] expire stale negatives;
- [ ] expose negative provenance in status diagnostics;
- [ ] add tests for contamination, ID reuse, reselection, and negative-to-positive
  identity transitions.

### P1.6 Prevent target fragments becoming negatives

- [ ] reject negative candidates that may be duplicate target tracks;
- [ ] compare against anchor and recent target history;
- [ ] require repeated distractor observation;
- [ ] reject contaminated overlapping crops;
- [ ] store provenance and confidence.

### P1.7 Add hard-negative lifecycle

Each prototype should store:

- source track ID;
- first and last frame;
- observation count;
- crop quality;
- confidence;
- last geometry context.

Add:

- [ ] expiry;
- [ ] decay;
- [ ] duplicate merging;
- [ ] maximum age;
- [ ] visual diagnostics.

## Phase 5 — Correct the scoring model

### P0.12 Separate ranking from validation

Current geometry weights sum to 1.0 and appearance is added as a positive bonus before clipping.

Problems:

- score saturation;
- appearance can only increase total;
- thresholds change meaning when appearance is active;
- poor appearance may be treated like missing appearance.

Tasks:

- [ ] define a geometry ranking score;
- [ ] define independent identity gates;
- [ ] distinguish:
  - appearance available;
  - appearance evaluated;
  - similarity passed;
  - appearance used for ranking;
  - appearance accepted for publication.
- [ ] avoid using one boolean for all appearance semantics.

### P1.8 Rename misleading fields

- [ ] Rename `distance` to `position_similarity`.
- [ ] Store normalized raw centre distance separately.
- [ ] Replace `geometry_strength = max(...)` with a meaningful aggregate or separate cues.

### P1.9 Add motion evidence only if it helps

Documentation currently mentions motion consistency, but the implementation uses last-box geometry only.

Experiments:

- [ ] last-box baseline;
- [ ] constant-velocity centre prediction;
- [ ] predicted scale;
- [ ] uncertainty growth during absence;
- [ ] optional camera-motion compensation.

Do not claim motion consistency unless implemented and evaluated.

## Phase 6 — Make evaluation trustworthy

### P0.13 Add evaluator tests

Test:

- [ ] interval boundaries;
- [ ] annotation gaps and overlaps;
- [ ] zero-duration rows;
- [ ] missing messages;
- [ ] stale last output;
- [ ] target-not-visible intervals;
- [ ] different stream start times;
- [ ] bag versus header time;
- [ ] zero ID with non-zero bbox;
- [ ] non-zero ID with invalid bbox.

### P0.14 Add output freshness

The primary evaluator currently holds the latest preceding ID indefinitely.

Tasks:

- [ ] define a maximum output age;
- [ ] classify stale output as lost;
- [ ] record stale-output duration;
- [ ] use the same freshness rule in all evaluators.

### P0.15 Unify evaluator semantics

The main and event evaluators currently define validity differently.

Tasks:

- [ ] create a shared evaluation library;
- [ ] use one time origin;
- [ ] use one output-validity function;
- [ ] use one annotation parser;
- [ ] use one exact duration integrator.

### P1.10 Improve bbox evaluation

Current bbox evaluation still uses annotated tracker ID to locate the reference box.

Tasks:

- [ ] annotate the physical target bbox independently of tracker IDs;
- [ ] evaluate output bbox against that physical reference;
- [ ] report IoU and centre error;
- [ ] report unscored duration separately;
- [ ] support regenerated full-pipeline tracker IDs.

### P1.11 Add event and recovery metrics

Report:

- time to first correct reacquisition;
- wrong-target burst duration;
- number of wrong handovers;
- number of recovery attempts;
- correct candidate suppressed duration;
- target-absent-but-output duration;
- state occupancy;
- memory contamination events.

## Phase 7 — Scientific experiments

### P0.16 Freeze tuning and test data

- [ ] designate tuning sequences;
- [ ] designate final held-out sequences;
- [ ] do not tune thresholds on final test sequences;
- [ ] record people and clothing overlap between sets.

### P0.17 Run component ablations

Required rows:

1. raw tracker;
2. geometry-only TIM;
3. geometry plus positive appearance;
4. geometry plus appearance margin;
5. geometry plus hard negatives;
6. geometry plus persistence;
7. final simplified TIM-MARS.

### P0.18 Validate across trackers

Tracker-configuration prerequisite started on 18 July 2026:

- [x] remove backend-inert keys from the active tracker YAML files;
- [x] add a branch-aware regression test for tracker configuration consumption;
- [x] pass the focused tracker tests and package builds;
- [x] create a deterministic tracker-only freezing workflow before generating
  new raw-versus-TIM evidence:
  - [x] define original-source-order tracker processing and fixed-ID raw-target
    semantics;
  - [x] implement the initial ROS-free tracker-freezing runner and focused unit
    tests;
  - [x] verify changed-file lint, compilation, focused tests, and package builds;
  - [x] run repeated ByteTrack, OC-SORT, SORT, and DeepSORT smoke freezes:
    - [x] ByteTrack completed twice with autonomous initialization and matching
      generated topic counts;
    - [x] SORT completed twice with autonomous initialization and matching
      generated topic counts;
    - [x] OC-SORT completed twice with autonomous initialization and matching
      generated topic counts;
    - [x] DeepSORT completed twice with autonomous initialization, matching
      generated topic counts, and identical source-order image-age evidence;
  - [x] prove repeated semantic output identity and validate generated topic
    counts:
    - [x] ByteTrack matched across all 1,906 generated message fields, source
      bytes, topic counts, selection metadata, and normalized provenance;
    - [x] document that raw CDR and MCAP byte identity is not a determinism
      contract because non-semantic alignment padding can differ;
    - [x] validate matching canonical semantic digests for ByteTrack, SORT, and
      OC-SORT;
    - [x] validate the matching canonical semantic digest for DeepSORT;
  - [x] regenerate one fully hashed canonical bag per tracker from clean commit
    `f17cdf80` with empty repository-status provenance;
  - [x] validate or recreate tracker-specific annotations for the exact frozen
    outputs:
    - [x] create and structurally validate the ByteTrack autonomous-target
      annotation against the canonical `f17cdf80` freeze;
    - [x] create and validate the SORT autonomous-target annotation;
    - [x] visually confirm or recreate the OC-SORT autonomous-target annotation;
    - [x] create and validate the DeepSORT autonomous-target annotation.

- [x] produce deterministic TIM outputs with a persisted evidence contract:
  - [x] audit the deterministic TIM runner and select the image-header-time
    track-ID evaluator as the authoritative P0.18 evaluator;
  - [x] persist exact source, canonical-configuration, model, repository, and
    runtime provenance;
  - [x] persist a generated-message semantic digest over declared TIM target
    and status fields in target-then-status write order;
  - [x] add focused evidence-contract tests and pass verification;
  - [x] run a repeated ByteTrack smoke replay before generating the clean
    four-tracker matrix.
  - [x] generate and evaluate the clean four-tracker matrix from commit
    `36ecd17d` with fully hashed clean provenance;
  - [x] preserve the consolidated matrix report under
    `reports/p018_tim_matrix_36ecd17d_2026_07_19/`.

For ByteTrack, SORT, OC-SORT, and DeepSORT:

- [x] use compatible annotations;
- [x] use autonomous selected-target initialization;
- [x] report raw and TIM output;
- [x] report unsafe degradation;
- [x] determine whether one preset is valid across trackers.
  - Result: no. With a `0.05 s` one-step safety tolerance, unsafe
    degradation remained for all four trackers:
    - ByteTrack: `+0.700 s` wrong-target output;
    - SORT: `+5.300 s` wrong-target output and `+0.150 s`
      target-absence valid output;
    - OC-SORT: `+0.200 s` target-absence valid output;
    - DeepSORT: `+15.203 s` wrong-target output.
  - Interpretation: the one-preset motion-only modularity claim is not supported
    on this hard-reentry sequence. The DeepSORT result also supports keeping
    appearance-based association outside the current safe layering claim.

Issue #43 remains open for:

- [ ] run OC-SORT + TIM on the required crossing and occlusion sequences:
  - [x] freeze Seq03 twice with matching semantic output and stable autonomous
    selection of OC-SORT ID `1`;
  - [x] diagnose Seq04 one-message initialization selecting transient OC-SORT
    ID `3`, which produced only `2/1,589` valid raw-target messages;
  - [x] harden and verify autonomous initialization with a configurable
    consecutive-eligible-observation confirmation gate:
    - confirmation `2` preserved stable OC-SORT ID `1` on Seq03 with
      `827/2,336` valid raw-target messages;
    - confirmation `2` replaced transient Seq04 ID `3` with stable ID `1`,
      increasing valid raw-target messages from `2/1,589` to `902/1,589`;
    - [x] regenerate fully hashed, repeated clean evidence for both sequences
      from implementation commit `305578f3`:
      - Seq03 repetitions match semantic SHA-256
        `3d5a55d6b05d831b83f8770aeeead283b0096d7816dc9480d9d3ab48b971ab9a`;
      - Seq04 repetitions match semantic SHA-256
        `e6f6d8e438cf879fab8daf69a6b06a7a68570427450b81b62facb2f2aadac096`;
      - source manifests are fully hashed and repository provenance is clean;
    - [x] manually annotate and structurally validate canonical Seq03 OC-SORT
      identity intervals in
      `docs/data/annotations/june_hard_sequences/seq03_ocsort_305578f3.csv`
      (SHA-256 `12db619326e47ff138b4267cd19dc1f3296385a06e01f693e9c1e467876bf56a`);
    - [x] manually annotate and structurally validate canonical Seq04 OC-SORT
      identity intervals in
      `docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv`
      (SHA-256 `39cc630be6873c261de22a248ddeab1cbb723988e2513b1cc2ae24a8450fc1a1`):
      - the visible `48.882-49.019 s` tracker-dropout interval retains physical
        lineage ID `53` and is classified as `id_switch_fragmentation`;
    - [ ] run repeated TIM-MARS replays and header-time evaluation for Seq03
      and Seq04;
- [ ] update `NOVELTY.md` Section 8.3 and the thesis-facing modularity claim
  after this evidence commit exists;
- [ ] record the rejected single-preset claim and close Issue #43 only after
  the remaining OC-SORT evidence and claim updates are complete.

### P1.12 Add broader sequences

Include:

- clean multi-person tracking;
- repeated crossings;
- short occlusion;
- long occlusion;
- exit and re-entry;
- similar clothing;
- small distant people;
- partial crops;
- illumination change;
- UAV or camera motion.

### P1.13 Parameter sensitivity

At minimum vary:

- acceptance threshold;
- ambiguity margin;
- appearance minimum;
- appearance separation margin;
- hard-negative threshold;
- hard-negative margin;
- confirmation time.

Show safety-performance trade-offs, not only the best tuned result.

### P1.14 Runtime and onboard cost

Measure:

- TIM core latency;
- MARS extraction latency;
- cache hit rate;
- candidates encoded per second;
- complete pipeline FPS;
- p95 and p99 target latency;
- CPU;
- memory;
- temperature.

## Phase 8 — Documentation and repository repair

### P0.19 Update stale tooling documentation

`docs/design/tim_tooling_index.md` references missing paths:

- old core implementation path;
- old node path;
- missing generated report path.

Tasks:

- [ ] replace with `thesis_bringup/tim_mars/` paths;
- [ ] point to promoted current reports;
- [ ] remove obsolete HSV references;
- [ ] verify every documented path automatically.

### P0.20 Synchronize TIM documentation

Resolve conflicts across:

- `docs/algorithm/tim_mars_versions.md`;
- `docs/design/selected_target_memory.md`;
- `docs/design/tim_mars_design.md`;
- `docs/design/tim_evaluation_protocol.md`;
- module README;
- launch scripts;
- paper;
- thesis.

Specifically fix:

- appearance margin drift;
- hard-negative margin drift;
- motion claims;
- final algorithm components;
- final result numbers;
- tracker-independence claims.

### P1.15 Remove unsupported experimental runner parameters

`run_one_memory_tim_replay.sh` contains anchor-drift and group-split parameters not declared by the current TIM ROS interface.

Tasks:

- [ ] verify whether these belong to removed code;
- [ ] remove them from the active runner;
- [ ] or reintroduce them only as isolated experiments;
- [ ] never silently pass unsupported parameters.

### P1.16 Clean package metadata

Replace TODO values in:

- `thesis_bringup/setup.py`;
- `thesis_bringup/package.xml`.

### P1.16a Repair the `thesis_tracker` ROS lint harness

Known tooling issue confirmed again on 18 July 2026:

- `test_pep257.py` repeatedly hangs inside `pydocstyle.parser` and requires
  manual interruption;
- `test_flake8.py` can hang inside the flake8 multiprocessing worker pool;
- direct `flake8 --jobs=1` terminates, but reports broad historical package
  lint debt unrelated to the current tracker-configuration change;
- package-wide ament lint must therefore not be used as an unbounded gate for
  unrelated P0/P1 implementation work.

Tasks:

- [ ] reproduce both hangs with explicit timeouts and record tool versions;
- [ ] determine which paths make `ament_pep257` or `pydocstyle` stall;
- [ ] exclude generated, installed, cached, environment, and runtime paths;
- [ ] force serial flake8 execution in the maintained verification command;
- [ ] make all lint checks bounded so they fail rather than hang indefinitely;
- [ ] separate historical package lint debt from changed-file lint failures;
- [ ] document the focused lint command used for normal repository work;
- [ ] repair or replace the generated ROS lint tests once the cause is known.

Until resolved, verification should use focused tests, changed-file lint,
Python compilation, package builds, `git diff --check`, and repository-status
review. A manual `KeyboardInterrupt` from these known hanging lint wrappers is
not evidence of an implementation regression.

### P1.17 Create a single reproducibility command

The command should:

1. validate source bags and annotations;
2. build using `tools/thesis_build.sh`;
3. run the canonical replay matrix;
4. generate all evaluation outputs;
5. verify configuration fingerprints;
6. build the final thesis tables;
7. fail on inconsistent numbers.

### P2.1 Consolidate replay bags and define evidence retention policy

Tracked by
[GitHub Issue #49](https://github.com/FRCTavares/IST-Thesis-Code/issues/49).

Complete only after the active P0.18+ OC-SORT evidence workflow:

- [ ] inventory and classify replay, reference, review, and annotation-input bags;
- [ ] define canonical evidence and deterministic-repetition retention rules;
- [ ] protect all report, annotation, catalogue, and documentation dependencies;
- [ ] remove only verified obsolete smoke, failed, duplicate, and UI-generated runs;
- [ ] create stable annotation-input aliases and reduce default UI clutter;
- [ ] preserve a machine-readable cleanup manifest and report disk usage before
  and after cleanup.

## Phase 9 — Thesis writing

### P0.21 Freeze the research question

Proposed question:

> Can a lightweight selected-target identity validation layer reduce unsafe wrong-person publication in RGB-only UAV person following under recoverable tracker identity instability?

### P0.22 Freeze the claim only after final evaluation

The current claim must remain narrow until:

- May numbers are reconciled;
- DeepSORT failure is explained;
- broader held-out results exist;
- one canonical configuration is used.

### P1.18 Write the method from the final implementation

Include:

- problem formulation;
- asymmetric objective;
- candidate evidence;
- unified safety gate;
- state transition;
- trusted memory update;
- computational complexity.

### P1.19 Add explicit limitations

Discuss:

- missing candidates;
- long disappearance;
- identical clothing;
- small crops;
- tracker dependence;
- appearance domain gap;
- parameter calibration;
- lack of formal safety proof.

### P1.20 Build final figures

Preliminary qualitative material completed:

- [x] Generate four raw-versus-TIM side-by-side supervisor videos.
- [x] Generate H.264-compatible copies.
- [x] Show IDs, validity, timing offset, elapsed time, and summary metrics.
- [x] Mark Seq04 as illustrative and nondeterministic.

Required final material:

- [ ] pipeline-position figure;
- [ ] state-machine figure;
- [ ] evidence and transactional safety-gate figure;
- [ ] trusted-memory update-policy figure;
- [ ] wrong-versus-lost trade-off;
- [ ] ablation table;
- [ ] failure-case frames;
- [ ] runtime table;
- [ ] regenerate comparison videos from the final clean deterministic commit;
- [ ] ensure every displayed metric points to a promoted provenance record.

## Phase 10 — Onboard pipeline & model upgrades (detector / tracker pairing / ReID placement)

Scope: these refine existing items (P0.18 tracker validation, P1.14 runtime cost,
Deferred-experiments ReID/Hailo) and mostly sit **after** the evidence-chain repair.
Only the tracker x TIM matrix is near-term. Every model swap is conditional on
ablations (P0.17) showing the global embedding under occlusion is the actual
bottleneck — per the Deferred-experiments rule. Same safety contract as the rest of
this file: wrong-target increase blocks promotion; every new component is flag-gated
with the current path as default; **select on CPU/replay, promote only the winner
onboard.**

### P0.18+ Tracker pairing = the modularity claim (refines P0.18)

TIM is a validation layer above the tracker, so it pairs best with **motion-only**
trackers whose failure mode (ID switch under occlusion/crossing) is exactly what TIM
is built to catch.

- [ ] Add **SORT** to the raw-vs-TIM matrix (P0.18 currently lists ByteTrack,
  OC-SORT, DeepSORT). SORT is the barest cheap tracker — biggest expected raw->TIM
  delta, cleanest modularity ablation.
- [ ] Prioritize **OC-SORT + TIM** on the crossing/occlusion sequences. OC-SORT's
  observation-centric gap repair (ORU) + nonlinear handling (OCM) is SOTA on
  DanceTrack/MOT20 (Cao et al., CVPR 2023) and should give TIM cleaner continuity on
  exactly the sequences where the current table is neutral.
- [ ] Treat **DeepSORT / StrongSORT / BoT-SORT / Deep-OC-SORT** as out-of-scope for
  the safe claim: they already assert identity from appearance, which duplicates
  TIM's ReID work and can conflict with it. The historical DeepSORT unsafe result
  (P0.2: raw 0.028 -> TIM 0.466 wrong) is consistent with that conflict. Once P0.2
  reproduction confirms it, restate NOVELTY §8.3 as a scoped design boundary — "TIM
  validates motion-only trackers; it is not layered over appearance-based
  association" — rather than an open failure.

### P1.14+ ReID placement: select on CPU, then promote the winner to Hailo (refines P1.14 + Deferred ReID/Hailo items)

- [ ] **Measure first whether ReID even needs to leave the CPU.** TIM embeds only the
  selected target + a few distractors per frame (not every detection, unlike
  DeepSORT), so CPU load may already be tolerable — check `htop` / `hailortcli
  monitor` during a live run before committing to any migration.
- [ ] **Select on CPU/replay (fast iteration).** Behind the existing embedding seam,
  add OSNet / OSNet-AIN / small CLIP-ReID-distilled as flagged alternatives to
  MARS-small128 (identical crop preprocessing + output usage; MARS stays default).
  Compare on wrong/lost + reacq delay across all eval bags. Promote a candidate only
  if it lowers wrong-target with no wrong-target rise anywhere. Do NOT iterate
  candidate nets by compiling each to HEF — that is a slow x86 train->ONNX->compile
  loop; the CPU replay answers the quality question in an afternoon.
- [ ] **Promote only the winner to Hailo**, then re-validate:
  - [ ] **Quantization margin re-validation (critical — an F2 obligation, ties to
    P1.13).** Hailo runs int8; quantization shifts cosine similarities by amounts on
    the order of TIM's own gates (hard-neg 0.03-0.08, conservative 0.05-0.25). The
    frozen config is only valid for the precision it was frozen at — re-verify the
    thresholds hold on the int8 embedding and recalibrate `m`/margins against the
    quantized model if needed.
  - [ ] **NPU contention:** detector + ReID share one 26-TOPS Hailo-8 (HailoRT
    time-slices network groups with context-switch cost). Measure
    `ros2 topic hz /detections` before/after adding the ReID network; confirm
    detector FPS stays >= camera rate.
  - [ ] **Timing/sync:** confirm scheduler queuing does not reopen the causal
    image-track mismatch just closed in P0.9; keep the embedding matched to the
    correct causal frame.

### P2.x Detector (perception upgrade behind TIM — additive, low priority)

A missed detection forces TIM to LOST (safe, but hurts availability), so detector
recall is the perception lever most relevant to TIM. Not on the critical path; do
after the evidence chain is clean.

- [ ] Reality: the Hailo Dataflow Compiler is x86-only — custom person-only YOLO is a
  separate x86 task, not a Pi task. For now use a prebuilt Model Zoo HEF.
- [ ] Trial **YOLOv8m / YOLO11m @ 640** (person class) from the Hailo-8 Model Zoo as
  an opt-in `--detector` / config value, keeping the current HEF as default. Verify
  `/detections` schema unchanged, `hz /detections` >= camera rate, and better recall
  on a distant/occluded test bag.
- [ ] If small/distant recall is the limiter, test **higher input resolution
  (960/1280)** before a deeper backbone — resolution usually buys more small-object
  recall at similar Hailo cost.
- [ ] Optional: a **pose detector** (YOLOv8/YOLO11-pose, in the Model Zoo) to feed
  TIM cheap orientation + tighter crops — enables the orientation gate below.

### P3.x Orientation gating (stretch; needs pose keypoints)

- [ ] If pose keypoints are available, gate the appearance vote on target
  orientation so a front<->back flip down-weights appearance and leans on
  geometry/motion. Flag-gated, default off. Addresses the "inverted appearance"
  failure without heavy compute. Skip unless already producing keypoints.

## Deferred experiments

Only pursue after the baseline is corrected, memory integrity is protected, and
the unified gate is validated:

- modern lightweight ReID replacement;
- part-based or horizontal-stripe embeddings for partial occlusion;
- pose-guided visible-part comparison;
- multi-frame embedding galleries and aggregation;
- time-scaled reacquisition thresholds;
- uncertainty-growing spatial and motion gates;
- foveated high-resolution re-detection around the predicted target region;
- moving ReID inference onto Hailo;
- Bayesian identity belief;
- camera-motion compensation;
- learned candidate fusion;
- group split recovery;
- anchor drift adaptation.

The cheap prerequisites are crop-quality gating, image-track synchronization,
protected anchor memory, qualified relative distractor margins, and trustworthy
evaluation. Larger ReID or Hailo changes should be attempted only if controlled
ablations show that the remaining bottleneck is the global embedding under
occlusion.

These ideas must not enter the final algorithm without controlled ablation
evidence.

## Immediate execution order

Completed:

1. [x] Preserve the failed trusted-same-ID experiment as diagnostic evidence.
2. [x] Revert the six-file experiment from the main working tree.
3. [x] Restore and reproduce clean Seq01 and May evidence.
4. [x] Add unresolved identity-safety specifications.
5. [x] Add characterization tests for unsafe ID-switch acceptance, wrong
   reacquisition lock, positive-memory contamination, and pre-acceptance
   hard-negative insertion.
6. [x] Extract the May status timeline and candidate scores.
7. [x] Group May hard-negative-risk frames into lifecycle episodes.
8. [x] Demonstrate same-ID and cross-lineage hard-negative vetoes.
9. [x] Correct appearance-crop coordinate mapping.
10. [x] Add appearance-topic auto-detection to replay.
11. [x] Correct Seq03 annotations and selected target ID.
12. [x] Freeze one canonical YAML and provenance format.
13. [x] Identify future-frame appearance leakage.
14. [x] Implement causal message-time image selection.
15. [x] Add timestamp correspondence tests.
16. [x] Rerun May, Seq01, Seq03, and Seq04 under the causal implementation.
17. [x] Demonstrate material Seq04 nondeterminism across three identical
    replays.
18. [x] Generate four side-by-side supervisor videos and H.264 copies.

Next — finish deterministic evidence:

1. [x] Compare the former nondeterministic Seq04 repetitions and locate the first
   divergent output decision.
2. [x] Record timestamp, image, candidate, proposal, acceptance, and publication
   evidence at divergent frames.
3. [x] Confirm callback-dependent causal-image availability as the divergence
   source.
4. [x] Design deterministic synchronization without wall-clock sleeps.
5. [x] Close the causal image-selection window using the complete offline image
   timeline.
6. [x] Complete delayed, dropped, equal-timestamp, stale,
   future-image, invalid-timestamp, and out-of-order image tests.
7. [x] Repeat deterministic Seq04 three times.
8. [x] Require identical frame-level target/status output and stable metrics.
9. [x] Rerun May, Seq01, and Seq03 for preservation.
10. [x] Run compilation, focused tests, build, and `git diff --check`.
11. [ ] Commit the timestamp and synchronization implementation.
12. [ ] Regenerate the four-case canonical matrix from the clean commit.
13. [ ] Record clean provenance:
    - Git commit;
    - clean repository state;
    - source bag;
    - annotation;
    - selected target ID;
    - canonical config hash;
    - resolved runtime hash;
    - report.
14. [ ] Regenerate supervisor videos from the clean deterministic runs.
15. [ ] Update `NOVELTY.md`, paper Table I, and promoted result tables.

Then — structural algorithm repair:

16. [ ] Move hard-negative updates out of
    `_prepare_update_candidates()` without changing acceptance decisions.
17. [ ] Make candidate preparation side-effect free.
18. [ ] Introduce a post-decision hard-negative transaction.
19. [ ] Add selected-negative reconciliation.
20. [ ] Separate candidate rejection from proven-distractor evidence.
21. [ ] Add negative provenance and lifecycle information.
22. [ ] Require repeated trusted observations before strong-negative promotion.
23. [ ] Audit negative insertion across May, Seq01, Seq03, and Seq04.
24. [ ] Refactor recovery policies to return candidate proposals.
25. [ ] Route every proposal through one transactional safety gate.
26. [ ] Introduce protected anchor memory and explicit trusted-lineage state.
27. [ ] Add proposal, anchor, synchronization, crop-quality, and
    negative-provenance diagnostics.
28. [ ] Reproduce and diagnose the historical DeepSORT failure.
29. [ ] Add evaluator freshness, shared semantics, and dedicated tests.
30. [ ] Fix live appearance wiring, cache safety, and crop-quality gating.
31. [ ] Run component ablations on tuning sequences.
32. [ ] Run held-out multi-tracker evaluation.
33. [ ] Freeze the final implementation, claim, pseudocode, tables, figures, and
    thesis results.
