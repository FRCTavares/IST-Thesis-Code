# TIM-MARS Thesis Roadmap

## Purpose

This is the active repository-grounded roadmap for turning TIM-MARS into a coherent, reproducible, and defensible Master's thesis contribution.

Priority:

- P0: blocks trustworthy results or the final thesis claim;
- P1: major algorithmic or scientific work;
- P2: useful improvement;
- P3: optional future work.

## Current audit snapshot

Confirmed repository facts:

- focused TIM tests pass: 44 passed;
- the core implementation is modular, but `target_memory.py` remains 1069 lines;
- ROS declares 66 TIM-facing parameters;
- several experimental policies remain in the main decision path;
- live, replay, documentation, and ROS defaults are inconsistent;
- the May final result is internally inconsistent;
- TIM-MARS is neutral on two June sequences;
- TIM-MARS becomes unsafe in the promoted DeepSORT selected-ID result;
- evaluation scripts have no dedicated metric tests;
- documentation contains stale paths and obsolete configuration guidance.

## Phase 1 — Repair the evidence chain

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

### P0.2 Investigate the unsafe DeepSORT result

Current promoted audit:

- raw DeepSORT wrong ratio: 0.028;
- DeepSORT + TIM-MARS wrong ratio: 0.466.

Tasks:

- [ ] Confirm annotation compatibility.
- [ ] Confirm the selected-ID initialization.
- [ ] Confirm whether ByteTrack annotations were incorrectly applied.
- [ ] Inspect the visual output around the first wrong handover.
- [ ] Determine whether failure comes from:
  - geometry assumptions;
  - rank-aware recovery;
  - appearance memory;
  - tracker-ID semantics;
  - mirrored selection;
  - stale embeddings;
  - configuration mismatch.
- [ ] Remove any broad tracker-independent claim until resolved.
- [ ] Add a regression sequence if the failure is algorithmic.

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

### P0.4 Freeze one canonical preset

Current drift:

| Source | Appearance margin | Hard-negative margin |
|---|---:|---:|
| ROS defaults | 0.05 | 0.03 |
| clean replay conservative preset | 0.25 | 0.08 |
| alternate replay preset | 0.10 | 0.08 |
| memory replay | 0.15 | 0.08 |
| old design document | 0.25 | not canonical |

Tasks:

- [ ] Choose one candidate thesis preset.
- [ ] Store it in a versioned YAML file.
- [ ] Make live and all replay runners load that file.
- [ ] Remove `legacy` as the silent experiment default.
- [ ] Serialize the complete resolved config into every report.
- [ ] Add a configuration fingerprint to replay metadata.

### P0.5 Prove paper-code-runner equivalence

- [ ] Write the final algorithm as ordered pseudocode.
- [ ] Map each pseudocode step to one code function.
- [ ] Map each parameter to the canonical YAML.
- [ ] Confirm every evaluated replay used that implementation.
- [ ] Record the Git commit used by each final result.
- [ ] Add a test that loads the canonical configuration.
- [ ] Update the paper and thesis if implementation order differs.

### P0.6 Replace parallel acceptance paths with one safety gate

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

Tasks:

- [ ] Create one candidate-selection stage.
- [ ] Create one final candidate safety gate.
- [ ] Ensure all paths check:
  - ID-switch permission;
  - geometry;
  - ambiguity;
  - positive appearance;
  - appearance separation;
  - hard-negative risk;
  - temporal confirmation.
- [ ] Apply state transition only after the final gate.
- [ ] Apply memory updates only after trusted acceptance.

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

- immutable selection anchor;
- bounded trusted gallery;
- adaptive recent prototype;
- hard-negative gallery.

Rules:

- [ ] anchor is not overwritten after uncertain recovery;
- [ ] adaptive memory updates only after stable trusted lock;
- [ ] no update during ambiguity;
- [ ] no update with weak crop quality;
- [ ] no update under hard-negative risk.

### P1.5 Fix positive-memory bootstrap

Current bootstrap can occur during scoring when the same tracker ID has an embedding.

Tasks:

- [ ] bootstrap only after a trusted current-frame acceptance;
- [ ] require crop-quality validation;
- [ ] record bootstrap frame and evidence;
- [ ] test same-ID hijack before first embedding.

## Phase 4 — Repair hard-negative memory

### P0.11 Move hard-negative updates after trusted acceptance

Current update occurs during candidate preparation before the current frame is finally accepted.

Tasks:

- [ ] update hard negatives only after confirming the selected target in that frame;
- [ ] never update while the scene is ambiguous;
- [ ] never update during `UNCERTAIN`, `LOST`, or `REACQUIRED`.

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

Only pursue after the baseline is corrected and simplified:

- modern lightweight ReID replacement;
- part-based embeddings;
- multi-frame embedding aggregation;
- Bayesian identity belief;
- camera-motion compensation;
- learned candidate fusion;
- group split recovery;
- anchor drift adaptation.

These ideas must not enter the final algorithm without controlled ablation evidence.

## Immediate execution order

1. Resolve the May result inconsistency.
2. Audit the unsafe DeepSORT result.
3. Freeze one canonical YAML preset.
4. Fix live appearance wiring.
5. Add rank-aware bypass tests.
6. Add evaluator freshness and tests.
7. Unify the acceptance path.
8. Protect appearance and hard-negative updates.
9. Run ablations on tuning data.
10. Run held-out evaluation.
11. Freeze the claim.
12. Rewrite the thesis method and results.
