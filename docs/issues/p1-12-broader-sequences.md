# P1.12 Broader Sequences

GitHub Issue: #30
Branch: `issue-30-broader-sequences`
Baseline: `f1f02ebb8742e69bf6a1a5e416da2061b8efb1c4`

## Objective

Create a small, frozen and reproducible broader benchmark for TIM-MARS selected-target evaluation.

The benchmark extends the four internal ROS 2 development sequences with a manageable subset of external pedestrian-tracking sequences while preserving the distinction between:

- selected-target identity-memory behaviour;
- detector and tracker candidate availability;
- controller-facing wrong-target safety;
- in-domain UAV evidence;
- external stress-test evidence.

This issue is evaluation-only. It must not change the canonical TIM-MARS policy, thresholds, tracker configuration or controller-facing publication contract.

TIM-MARS is not another multi-object tracker. The tracker supplies candidate
boxes and temporary tracker identities. TIM-MARS must preserve the physical
person selected during the initialization frames, reject unsafe substitutions,
and recover that same person when the tracker identity changes or disappears.

## Research boundary

External datasets provide broader pedestrian-tracking stress tests.

They do not replace:

- Raspberry Pi 5 evidence;
- Hailo evidence;
- ROS 2 integration evidence;
- UAV-motion evidence;
- September held-out evidence owned by Issue #27;
- runtime, thermal and power evidence owned by Issue #32.

The benchmark must not be described as final held-out validation.

## Planned benchmark composition

The intended frozen benchmark contains approximately:

- four MOT17 sequences;
- four to six DanceTrack sequences;
- four VisDrone-MOT sequences;
- the four existing ROS 2 sequences.

The exact sequence names, target identities and frame ranges remain unfrozen until adapter compatibility and selection-policy checks are complete.

## Evaluation modes

### Oracle-candidate mode

Oracle-candidate mode uses dataset ground-truth person boxes and identities as the candidate stream.

Its purpose is to isolate TIM-MARS identity-memory and recovery behaviour from detector and tracker failures.

It must report candidate availability explicitly and must not be labelled as end-to-end tracking performance.

### Detector–ByteTrack–TIM-MARS mode

The end-to-end mode uses:

1. dataset image frame;
2. the selected detector path;
3. ByteTrack;
4. deterministic raw target initialization;
5. TIM-MARS;
6. controller-facing selected-target evaluation.

Failures must be attributable where possible to:

- detector miss;
- tracker fragmentation;
- tracker association error;
- correct candidate absent;
- TIM-MARS suppression;
- TIM-MARS wrong-target publication;
- stale output;
- physical target absence.

The two modes must remain separately labelled in reports.

## Dataset-neutral annotation contract

Every imported object annotation must preserve:

- dataset name;
- sequence name;
- split;
- original frame number;
- normalized zero-based frame index;
- derived timestamp;
- source frame rate;
- original identity;
- class;
- confidence when defined;
- visibility when defined;
- truncation when defined;
- ignored-region status;
- source image width and height;
- bbox in original source-image coordinates;
- source annotation row provenance.

The canonical internal bbox representation is:

- `xyxy`;
- floating-point;
- source-image pixels;
- left/top inclusive;
- right/bottom geometric edges;
- width computed as `x2 - x1`;
- height computed as `y2 - y1`;
- clipped to `[0, width]` and `[0, height]`.

Dataset adapters must explicitly document any source convention that differs.

## Frame and time contract

Each sequence manifest must record:

- source frame numbering convention;
- selected first and last source frame;
- corresponding normalized zero-based frame indices;
- frame rate;
- timestamp rule.

The default timestamp rule is:

`timestamp_s = normalized_frame_index / frame_rate`

No dropped-frame correction may be inferred unless the source dataset documents it.

## Target-selection policy

Target selection must be deterministic and frozen before final evaluation.

The selected target is the physical person chosen during an explicit
initialization frame or initialization window. This initial choice defines the
identity that TIM-MARS must preserve for the remainder of the evaluated range.

The benchmark must record separately:

- the dataset identity of the physical target;
- the initialization frame or window;
- the deterministic initialization rule;
- the tracker identity associated with the target at initialization;
- later tracker-identity changes corresponding to the same physical person.

A later tracker ID must not become the selected target merely because it has a
larger box, higher score or stronger visibility. Tracker IDs are candidate
identifiers, not the permanent definition of the person being followed.

A retained target should normally satisfy:

- sufficient visible duration;
- a clean initialization interval;
- at least one relevant challenge event;
- meaningful candidate competition;
- usable ground-truth boxes;
- no dependence on final TIM-MARS outcome.

Permitted deterministic selection inputs include:

- target visible duration;
- initialization visibility;
- bbox size;
- occlusion or visibility metadata;
- identity competition;
- documented sequence challenge categories.

TIM-MARS performance must not be used to select the target.

After initialization, evaluation must distinguish:

- correct publication of the initialized physical person;
- recovery of that person under a new tracker identity;
- safe suppression when identity is uncertain;
- wrong publication of a distractor;
- stale publication after the tracker identity has transferred to another
  person;
- loss caused by candidate absence rather than a TIM-MARS decision.

Every exclusion must record a reason.

## Sequence roles

Each sequence must be labelled as one of:

- `integration_check`;
- `development_evidence`;
- `external_stress_test`;
- `future_held_out`.

External benchmark sequences under Issue #30 must not use `future_held_out`.

## Event categories

The manifest may assign one or more of:

- `clean_tracking`;
- `candidate_loss`;
- `identity_confusion`;
- `tracker_fragmentation`;
- `short_occlusion`;
- `long_occlusion`;
- `physical_absence`;
- `reentry`;
- `crowd_crossing`;
- `similar_clothing`;
- `partial_crop`;
- `small_target`;
- `illumination_change`;
- `camera_motion`;
- `appearance_separation`;
- `appearance_ambiguity`.

These categories describe why a sequence was selected. Final event-level evaluation still depends on explicit frame or time annotations.

## Coordinate dependency

The current live contract is `tim_mars_source_pixels_resize_v1`.

External dataset adapters must produce original source-image coordinates and must not apply the live 640x640 inference resize unless running the end-to-end detector path.

The current bbox evaluator is not a physical identity-independent oracle because it locates the reference box through an annotated tracker ID.

Issue #30 therefore requires a dataset-ground-truth spatial reference path before external full-pipeline bbox claims are made.

## Storage layout

Large datasets and generated outputs remain local and ignored.

Expected local paths:

- original datasets: `data/datasets/external/<dataset>/`;
- normalized metadata: `data/datasets/processed/<dataset>/`;
- generated reports: `artifacts/reports/p030_broader_sequences/`;
- generated logs: `ros2_ws/log/p030_broader_sequences/`.

Tracked files contain only:

- contracts;
- manifests;
- small normalized annotations when appropriate;
- hashes;
- exact commands;
- aggregate interpretation;
- evidence references.

Datasets, extracted full frame copies and large generated outputs must not be committed.

## Provenance requirements

Each frozen sequence entry must record:

- official source;
- dataset version or release;
- download archive or source-file SHA-256 where practical;
- sequence-relative source path;
- sequence metadata;
- selected target identity;
- frame range;
- target-selection reason;
- exclusions;
- supported evaluation modes;
- dataset-adapter version;
- repository commit;
- canonical TIM-MARS configuration hash;
- detector and tracker configuration hashes for end-to-end runs.

## Determinism requirements

The final benchmark must guarantee:

- stable manifest ordering;
- stable annotation ordering;
- deterministic frame and timestamp conversion;
- deterministic target initialization;
- deterministic ByteTrack ID reset per sequence;
- deterministic report ordering;
- repeated aggregate output equality;
- explicit unavailable values rather than guessed fields.

## Initial implementation order

1. Freeze schemas and contracts.
2. Implement dataset-neutral records.
3. Implement MOTChallenge-compatible parsing.
4. Implement VisDrone-MOT parsing.
5. Add adapter fixture tests.
6. Add deterministic target-selection analysis.
7. Freeze selected sequence identities and frame ranges.
8. Implement oracle-candidate execution.
9. Implement detector–ByteTrack–TIM-MARS execution.
10. Reuse the shared selected-target evaluator.
11. Produce deterministic per-sequence and aggregate reports.
12. Document findings and limitations.

## Non-goals

This issue does not:

- tune canonical TIM-MARS thresholds;
- create a new detector;
- replace ByteTrack;
- implement generic MOT benchmark leaderboards;
- evaluate every sequence in each dataset;
- use Issue #27 held-out recordings;
- claim universal tracker portability;
- commit external datasets;
- replace UAV-specific evidence.

## First milestone completion criteria

The protocol milestone is complete when:

- this implementation plan is tracked;
- the benchmark manifest schema is tracked;
- the initial unfrozen manifest is tracked;
- coordinate and time conventions are explicit;
- target-selection rules are explicit;
- storage and evidence boundaries are explicit;
- `docs/TODO_LIST.md` marks Issue #30 in progress;
- JSON validation passes;
- `git diff --check` passes.

No dataset download or benchmark result is required for this milestone.

## Implementation progress

### Slice 1 — dataset-neutral records and annotation parsing

Added an evaluation-only normalization layer for:

- MOTChallenge-compatible annotations;
- VisDrone-MOT annotations;
- one-based or zero-based source frame numbering;
- deterministic zero-based frame indices and timestamps;
- source top-left `xywh` to geometric-edge source-pixel `xyxy`;
- clipping to `[0, width]` and `[0, height]`;
- source row and line-number provenance;
- retained source image dimensions, frame rate and index base per record;
- explicit inclusion and exclusion reasons;
- retained VisDrone class, truncation and occlusion semantics;
- deterministic ordering and rejection of repeated frame–identity pairs;
- finite-value and integral-frame validation.

The parser preserves class `1` (`pedestrian`) and class `2` (`people`) as
distinct source labels. It does not silently merge or erase the distinction.

This slice uses synthetic fixtures only. No external dataset was downloaded,
selected, frozen or evaluated.

The normalized records represent tracker candidates and physical
dataset identities. They do not define a tracker benchmark objective.

### Slice 2 — frozen-target initialization mapping

The physical dataset identity is frozen before TIM-MARS outcome review.
Initialization then maps that physical target to one tracker candidate using:

- the target ground-truth box;
- a bounded initialization window;
- unique best-IoU matching;
- a minimum IoU;
- a minimum best-versus-second margin;
- consecutive-frame confirmation.

The largest person in the scene is not automatically substituted for the
frozen benchmark target. The confirmed tracker identity is fixed as the raw
initial target, reselection is disabled, and later tracker-ID changes do not
redefine the physical person being evaluated.

This slice uses synthetic observations only. No external dataset was
downloaded, selected, frozen or evaluated.
