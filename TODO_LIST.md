# TIM-MARS Thesis Roadmap

## Purpose

This is the active repository-grounded roadmap for turning TIM-MARS into a coherent, reproducible, and defensible Master's thesis contribution.

Priority:

- P0: blocks trustworthy results or the final thesis claim;
- P1: major algorithmic or scientific work;
- P2: useful improvement;
- P3: optional future work.

## Current audit snapshot

Confirmed repository facts as of 14 July 2026:

- the failed six-file trusted-same-ID experiment was preserved as a diagnostic
  patch and reverted from the main working tree;
- the guarded diagnostic implementation remains isolated on branch
  `diagnostic/trusted-same-id-bypass-2026-07-14` and was not merged;
- the current canonical main implementation is identified by commit
  `73ed19dd` for the clean replay evidence and commit `3aa39572` after adding
  failure-characterization tests;
- `thesis_bringup` builds successfully and the focused TIM-MARS suite passes
  with `42 passed, 3 xfailed`;
- the three `xfail` tests are explicit unresolved safety specifications rather
  than accidental failing tests;
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

### P0.4 Freeze one canonical preset — DONE

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

Current behaviour uses the latest received image with current track boxes.

Tasks:

- [ ] Match tracks with the corresponding image timestamp or frame ID.
- [ ] Reject appearance extraction when alignment exceeds tolerance.
- [ ] Report actual image-track offset.
- [ ] Test delayed and dropped image conditions.

### P0.10 Make appearance caching identity-safe

Current cache key:

    tracker ID

Risks:

- ID reassignment;
- stale box;
- cached embedding attached to a different person.

Tasks:

- [ ] Include frame generation and bbox continuity.
- [ ] Invalidate on implausible box jumps.
- [ ] Invalidate when track lifecycle restarts.
- [ ] Report embedding age per candidate.
- [ ] Add an ID-reuse regression test.

### P1.3 Add crop-quality controls

Before encoding, measure:

- [ ] minimum pixel height and width;
- [ ] clipping fraction;
- [ ] aspect ratio;
- [ ] overlap with nearby people;
- [ ] centre distance to group members;
- [ ] optional blur or sharpness.

Do not update positive or negative memory from low-quality crops.

### P1.4 Separate protected and adaptive appearance memory

Implement and compare:

- immutable or very slow operator-selection anchor;
- bounded trusted multi-pose gallery;
- adaptive recent prototype;
- provenance-aware hard-negative gallery.

The May failure demonstrates that adaptive similarity can become self-confirming
after a wrong reacquisition. Increasing similarity to the adaptive prototype is
not independent evidence that the physical identity is correct.

Rules:

- [ ] preserve an operator-selected anchor independently of the adaptive memory;
- [ ] never replace the anchor merely because a newly reacquired ID reaches
  `LOCKED`;
- [ ] compare ID-switch and long-gap candidates against the protected anchor and
  trusted gallery;
- [ ] adaptive memory updates only after stable trusted lock;
- [ ] adaptive appearance similarity must never be treated as independent
  evidence once adaptive memory has already been updated from that identity;
- [ ] prevent circular reasoning where acceptance strengthens adaptive
  memory and strengthened adaptive memory later justifies the same identity;
- [ ] no positive update on the first accepted ID-switch frame;
- [ ] no update during `UNCERTAIN`, `LOST`, or unconfirmed `REACQUIRED`;
- [ ] no update during ambiguity or unresolved hard-negative conflict;
- [ ] no update with weak, clipped, blurred, tiny, overlapping, or stale crops;
- [ ] record which memory source supported every acceptance;
- [ ] add a regression where a wrong reacquisition becomes geometrically stable
  and must not overwrite the original identity anchor.

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
- [ ] Remove or implement `max_lost_frames`.

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

For ByteTrack, OC-SORT, and DeepSORT:

- [ ] use compatible annotations;
- [ ] use autonomous selected-target initialization;
- [ ] report raw and TIM output;
- [ ] report unsafe degradation;
- [ ] determine whether one preset is valid across trackers.

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

### P1.17 Create a single reproducibility command

The command should:

1. validate source bags and annotations;
2. build using `tools/thesis_build.sh`;
3. run the canonical replay matrix;
4. generate all evaluation outputs;
5. verify configuration fingerprints;
6. build the final thesis tables;
7. fail on inconsistent numbers.

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

Required:

- pipeline position;
- state machine;
- evidence and safety gate;
- trusted-memory update policy;
- wrong-versus-lost trade-off;
- ablation table;
- failure-case frames;
- runtime table.

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
2. [x] Revert the six-file trusted-same-ID experiment from the main working tree.
3. [x] Rebuild and rerun the canonical Seq01 and May baseline.
4. [x] Classify the unresolved safety regressions explicitly as `xfail`.
5. [x] Add characterization tests for:
   - unsafe first ID-switch acceptance;
   - wrong reacquisition becoming `LOCKED`;
   - positive-memory contamination after wrong reacquisition;
   - hard-negative insertion before acceptance and missing reconciliation.
6. [x] Extract the May status timeline and all candidate scores.
7. [x] Summarize 33 hard-negative-risk frames into seven lifecycle episodes.
8. [x] Demonstrate same-ID and cross-lineage hard-negative vetoes.

Next:

1. Move hard-negative updates out of `_prepare_update_candidates()` without
   changing any acceptance decision yet.
2. Introduce a post-decision hard-negative transaction that runs only after a
   trusted current-frame acceptance.
3. Add selected-negative reconciliation for operator selection and accepted
   lineage changes.
4. Add tests proving that:
   - proposal preparation is side-effect free;
   - a candidate cannot become a negative before its role is resolved;
   - a newly selected identity is removed or quarantined from negative memory;
   - `UNCERTAIN`, `LOST`, and `REACQUIRED` frames cannot add negatives;
   - a rejected candidate is not automatically considered a proven distractor.
5. Add negative provenance containing source track ID, insertion lineage,
   first and last frame, observation count, insertion reason, crop quality, and
   trust state.
6. Require repeated trusted observations before a prototype becomes a strong
   negative.
7. Audit every hard-negative insertion across Seq01 and May using the new
   provenance diagnostics.
8. Rerun the focused suite, canonical Seq01, and canonical May after each
   meaningful structural change.
9. Reject any change that improves one sequence by making the other unsafe.
10. Only after negative-memory mutation is transactional, refactor candidate
    policies to return proposals.
11. Route all proposal sources through one final transactional safety gate.
12. Introduce protected anchor memory and explicit trusted-lineage state.
13. Add diagnostics for proposal source, anchor support, adaptive similarity,
    crop quality, synchronization age, and negative provenance.
14. Extend validation to Seq03 crossing and Seq04 occlusion/absence.
15. Reproduce and diagnose the historical DeepSORT failure using preserved
    configuration and annotation-compatible memory replay.
16. Add evaluator freshness, shared semantics, and dedicated tests.
17. Fix live appearance wiring, image-track synchronization, cache safety, and
    crop-quality gating.
18. Run component ablations on tuning sequences.
19. Run held-out multi-tracker evaluation.
20. Freeze the final claim, implementation, paper pseudocode, and thesis results.
