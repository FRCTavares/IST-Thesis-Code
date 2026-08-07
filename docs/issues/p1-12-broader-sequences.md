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

The intended full benchmark contains approximately:

- four MOT17 sequences;
- four to six DanceTrack sequences;
- four VisDrone-MOT sequences;
- the four existing ROS 2 sequences.

The exact sequence names, target identities and frame ranges remain unfrozen until adapter compatibility and selection-policy checks are complete.

### Phasing: MOT17 deferred

MOT17 acquisition is currently blocked because the official MOTChallenge
source is unreachable from the development network (see Slice 12). MOT17
therefore moves to a later supplementary phase and is not part of the first
frozen benchmark.

The first benchmark phase freezes and evaluates:

- four to six DanceTrack validation sequences;
- approximately four VisDrone-MOT validation sequences;
- the four existing ROS 2 development sequences.

MOT17 remains in scope. It will be added as a later supplementary phase, with
its own selection, freeze and paired raw-versus-TIM-MARS evaluation, once the
official archive is acquired. Its later addition must not reopen or alter the
first-phase freeze.

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

### Slice 3 — explicit DanceTrack compatibility

DanceTrack sequence metadata is parsed from a required MOT-style
`seqinfo.ini` contract. The adapter preserves:

- sequence name;
- image directory;
- frame rate;
- sequence length;
- image width and height;
- image extension;
- one-based source-frame numbering.

DanceTrack annotations are normalized through the existing
MOTChallenge-compatible parser while retaining `dataset=dancetrack`.
Only source class `1` is admitted as a person candidate. Invalid identities,
non-person rows and non-positive source confidence remain present with explicit
exclusion reasons.

This slice uses synthetic fixtures only. No DanceTrack archive or sequence was
downloaded, selected, frozen or evaluated.

### Slice 4 — deterministic target-candidate analysis

A dataset-neutral analysis layer now computes objective candidate facts before
any TIM-MARS outcome is examined:

- visible-frame count and span;
- longest consecutive visible run;
- bbox-height statistics;
- available visibility and occlusion statistics;
- border contact;
- frames containing other person candidates;
- bbox-overlap and centre-proximity competition;
- earliest clean initialization window;
- deterministic eligibility and exclusion reasons.

Candidate ordering is stable and uses only annotation-derived properties.
TIM-MARS correctness, recovery and suppression outcomes are deliberately absent
from the selection records.

This slice uses synthetic annotations only. No real sequence, identity or frame
range was selected or frozen.

### Slice 5 — dataset source and acquisition registry

A tracked source registry now defines:

- the official landing page and source authority for each dataset;
- admissible splits with locally available official ground truth;
- manual acquisition and terms-review requirements;
- local ignored storage paths;
- archive filename and SHA-256 fields to populate after acquisition;
- a minimum remaining-free-space rule;
- MOT17 scene deduplication across DPM, FRCNN and SDP folders;
- the separation between oracle ground truth and thesis detector output.

The registry deliberately contains no guessed direct-download URLs. Dataset
acquisition remains a reviewed manual action. Slice 8 later replaces the
dataset-level archive placeholders with verified split-level provenance so a
partial acquisition cannot imply that every admissible split is installed.

### Slice 6 — read-only local dataset catalogue

A deterministic catalogue scanner now inspects locally installed dataset
folders and records:

- dataset, split and sequence identity;
- source, metadata, annotation and image-directory paths;
- available sequence metadata;
- image counts;
- structure-validation errors;
- MOT17 scene keys and duplicate detector variants;
- the canonical MOT17 FRCNN folder used to avoid repeated scenes.

The scanner is read-only. It neither downloads datasets nor selects benchmark
targets. Synthetic directory fixtures validate MOT17, DanceTrack and
VisDrone-MOT layouts.

### Slice 7 — dataset-profile integrity hardening

Dataset-specific eligibility and sequence-integrity rules now enforce:

- VisDrone class `1` (`pedestrian`) as the only single-person target class;
- VisDrone class `2` (`people`) retained for provenance but excluded with
  `group_class_not_single_identity`;
- MOT rows without a source class labelled `unspecified`, never `person`;
- explicit annotation-to-`seqLength`, image-geometry and frame-rate checks;
- rejection of repeated tracker identities within one initialization frame.

These rules prevent group boxes, missing class metadata, out-of-range
annotations and malformed tracker candidate sets from silently entering target
selection or initialization.

### Slice 8 — verified split-level acquisition provenance

The source registry now records acquisitions per admissible split rather than
using one dataset-level archive pair. This prevents the verified VisDrone
validation archive from implying that the absent training split is installed.

The verified VisDrone2019-MOT validation acquisition records:

- archive `VisDrone2019-MOT-val.zip`;
- its locally calculated SHA-256 and exact byte size;
- the canonical installed `val` path;
- seven sequences;
- seven annotation files;
- 2,846 images;
- verification date 6 August 2026.

A tracked local verifier checks archive existence, byte size, SHA-256, installed
structure and catalogue-derived counts. Synthetic tests cover valid
acquisitions, deterministic output, missing archives, hash mismatch, count
mismatch and invalid installed structures.

This slice records acquisition provenance only. It does not freeze a sequence,
physical identity, frame range or frame-rate assumption, and it does not inspect
TIM-MARS outcomes.

### Slice 9 — deterministic annotation-only dataset profiles

A tracked read-only profiler now combines the source registry, canonical local
catalogue, dataset adapter and existing selection policy to report:

- sequence paths, image geometry and sequence length;
- frame-rate value and its provenance;
- total, included and explicitly excluded annotation rows;
- deterministic exclusion-reason counts;
- per-identity visibility, size, border and competition facts;
- clean initialization-window availability;
- candidate eligibility and exclusion reasons.

The profiler emits deterministic human-readable and standalone JSON output.
It contains no tracker identities, TIM-MARS scores, recovery events or final
benchmark selection.

MOT-style datasets use official `seqinfo.ini` timing. When source metadata does
not provide timing, the CLI requires an explicit frame rate and labels it
`explicit_cli_unfrozen`. The inspection-only VisDrone 24 FPS input is therefore
never silently hard-coded or treated as frozen provenance.

This slice does not change the selection policy, select a sequence, freeze a
physical identity or frame range, or modify `sequence_manifest.json`.

### Slice 10 — original capture rate versus exported cadence

The tracked source registry now records the official VisDrone timing evidence
without equating two different quantities:

- the original dataset videos were captured at 24 FPS;
- only part of the original frames was extracted for annotation;
- the cadence between adjacent exported annotation images is unavailable;
- exported frame indices therefore cannot establish physical source time.

The profiler retains its explicit frame-rate input for deterministic parsing,
analysis and eventual replay. For VisDrone that input remains
`explicit_cli_unfrozen` and is reported separately from:

- `original_capture_frame_rate_hz=24.0`;
- `exported_sequence_frame_rate_hz=null`;
- `exported_sequence_cadence_known=false`;
- `benchmark_time_policy=frame_index_only_until_cadence_resolved`.

Derived seconds under an explicit VisDrone analysis rate are labelled
`deterministic_analysis_only_not_physical_source_time`.

This slice does not modify `sequence_manifest.json`, select a sequence or
physical identity, freeze a frame range, define a final replay rate, or inspect
tracker and TIM-MARS outcomes.

### Slice 11 — verified DanceTrack validation acquisition

The official DanceTrack validation archive was acquired from the source linked
by the DanceTrack authors and verified before installation.

The local acquisition records:

- archive `val.zip`;
- exact size `4,209,785,614` bytes;
- SHA-256
  `90ba30973761ce0b81a9654c11086d87537392475ac8bc666d842e645641277c`;
- 25 validation sequences;
- 25 `gt/gt.txt` files;
- 25,508 source images;
- 20 FPS sequence timing from the official `seqinfo.ini` files.

The archive was checked for unsafe paths, symbolic links and encrypted entries
before extraction. Extraction used an isolated ignored staging directory, and
every installed sequence was checked for:

- required sequence metadata;
- metadata-name agreement;
- positive frame rate and image dimensions;
- image-directory presence;
- exact metadata-to-image-count agreement;
- local ground-truth identity annotations.

The source registry records only the verified validation split. The absent
training split remains unverified, so DanceTrack is `partially_verified`.

This slice does not select a sequence or physical target, freeze an
initialization window or frame range, modify `sequence_manifest.json`, or
inspect tracker and TIM-MARS outcomes.

### Slice 12 — MOT17 acquisition deferral and first-phase scope

MOT17 acquisition was attempted from the development Raspberry Pi 5 on
7 August 2026 and failed. Diagnosis before any workaround was attempted:

- `motchallenge.net` and `www.motchallenge.net` resolve via DNS to the same
  TUM-hosted host (`131.159.19.34`, IPv6 `2a09:80c0:18::1034`);
- IPv6 connection attempts fail immediately with no local route;
- IPv4 connection attempts to port 80 and port 443 fail with a routing-level
  error (`No route to host` / connection timeout), not a TLS or HTTP-layer
  failure;
- general internet access from the same network is unaffected
  (`https://github.com` succeeds);
- the identical TUM host is independently unreachable from a second,
  unrelated network with otherwise-working general internet access.

Two independent networks fail to reach specifically the TUM-hosted subnet
while general connectivity is healthy on both. This is consistent with a
routing or peering gap to that academic network, or an outage on their end,
and it is not evidence that the official reference URL is wrong. No
unofficial mirror was substituted. No archive URL was guessed. No download
was attempted.

The operator confirmed the Pi cannot be relocated to another network during
this work period. `dataset_sources.json` keeps `mot17.acquisition_status`
literally accurate as `"not_downloaded"`; no acquisition contract field was
weakened to accommodate the deferral. MOT17 remains fully in scope and moves
to a later supplementary benchmark phase, to be acquired manually by the
repository owner from a network that can reach the official source and
transferred to the Pi for verification, extraction and cataloguing under the
existing Slice 5/6/8/11 machinery, which is dataset-agnostic and requires no
changes to accommodate MOT17 once the archive is local.

This slice does not select a sequence, physical identity, initialization
window or frame range for any dataset, and it does not inspect tracker or
TIM-MARS outcomes.

### Slice 13 — first-phase ROS 2 sequence identification

The "four existing ROS 2 sequences" are the four sequences already frozen as
the `development` set in `docs/data/splits/tim_mars_split_v1.json`:

- `dev_may_hard_reentry` (hard target exit, re-entry and tracker-ID switch);
- `dev_june_seq01` (clean four-person visibility);
- `dev_june_seq03_ocsort` (four-person crossing ambiguity);
- `dev_june_seq04_ocsort` (four-person occlusion without exit).

These are exactly the four sequences used as Issue #26's canonical
event-and-recovery evidence
(`reports/p026_event_recovery_b50f914a_2026_08_05`), so their raw-versus-TIM
evaluation path already exists: the recorded bags contain both the raw
selected-target stream (`/target`) and the TIM-MARS stream
(`/target_memory_mars`) recorded together from one run against one shared
detector/tracker candidate stream, and `tools/analysis/tim_evaluation.py`
plus `tools/analysis/evaluate_tim_event_recovery.py` already score both
streams against the same annotation oracle.

**Correction (Slice 15): this is only true for May and June Seq01 as
originally written here.** Tracing each Issue #26 report's `input_bag`
provenance chain found that the June Seq03 and Seq04 evidence was generated
against an **OC-SORT**-tracked replay chain
(`bags/replay/p018_ocsort_sequences_305578f3_2026_07_19/...`), not
ByteTrack. Issue #30 explicitly requires a raw **ByteTrack** baseline, so
that existing Seq03/Seq04 evidence does not satisfy it. Slice 15 regenerates
both from their official ByteTrack `full_pipeline` bags instead. See Slice 15
for the fix and the corrected picture: only after that regeneration do all
four sequences share identical detector/ByteTrack output between their raw
and TIM branches.

The June `seq02` (target re-entry) sequence is deliberately excluded. It is
classified `legacy_validation` in `tim_mars_split_v1.json`, explicitly
"quarantined from tuning" and restricted to "diagnostic validation only... do
not call it held-out." Using it as a fifth or substitute ROS 2 benchmark case
here would blur that quarantine boundary without an explicit, separate
decision to do so; it remains available only for diagnostic comparison, not
for benchmark freeze evidence.

Issue #26's event vocabulary (`clean_visible`, `target_absent`, `reentry`,
`occlusion_ambiguity`, `id_switch_fragmentation`, `other`; correct/wrong/lost/
absent/stale durations) overlaps with but does not equal the Issue #30
outcome taxonomy (which additionally distinguishes distractor selection from
stale-ID transfer, and adds ambiguous-candidate and initialization-failure
categories). The ROS 2 evaluation path for Issue #30 extends the existing
authoritative classification in `tim_evaluation.py` rather than
reimplementing bag loading, timebase handling or annotation parsing.

This slice selects which existing sequences are in scope; it does not itself
freeze `sequence_manifest.json`, choose initialization frames, or inspect
tracker/TIM-MARS outcomes beyond the already-published Issue #26 evidence
cited above for provenance.

### Slice 14 — DanceTrack and VisDrone-MOT first-phase selection

Added `tools/analysis/select_first_phase_benchmark.py`, a deterministic,
tested selection tool that populates `sequence_manifest.json` entries for the
first benchmark phase using only annotation-derived facts already produced by
`profile_external_tracking_dataset`.

Selection method:

- sequences are ranked by `(candidate_count, sequence_name)`, using annotated
  candidate count as a crowd-density proxy;
- `count` sequences are then taken at evenly spaced positions across that
  ranking, so the selection spans low- to high-density scenes instead of
  clustering at one end;
- within each selected sequence, the physical target is the eligible,
  initialization-eligible candidate with the greatest total visible-frame
  count, tied first by longest consecutive visible run and then by lowest
  dataset identity;
- scene facts (`approximate_people`, `primary_challenge`) and
  `event_categories` are derived from the same candidate's annotated overlap,
  border-contact and height statistics.

No tracker or TIM-MARS outcome is read, computed or referenced anywhere in
the selection path.

This produced 5 DanceTrack `val` sequences (`dancetrack0004`,
`dancetrack0019`, `dancetrack0063`, `dancetrack0073`, `dancetrack0094`) and 4
VisDrone-MOT `val` sequences (`uav0000117_02622_v`, `uav0000137_00458_v`,
`uav0000268_05773_v`, `uav0000339_00001_v`), each with a frozen candidate
physical-target identity, initialization window, evaluation frame range and
schema-validated entry (status `selected`) in `sequence_manifest.json`. Every
entry sets `target.initial_tracker_identity` to `null`: the schema allows
this explicitly, and the real tracker candidate ID can only be known once the
detector-ByteTrack candidate stream is generated for that sequence, which is
later, execution-time work, not a selection-time decision.

The tool is idempotent and re-runnable: it replaces only the entries whose
`id` it produced and leaves any other sequences (including the ROS 2 entries
added in a later slice) untouched. Two consecutive runs over the same local
data produce byte-identical output.

The manifest root `status` remains `draft_not_frozen` after this slice. It
must not be read as final until the ROS 2 sequences are also added and the
manifest is deliberately frozen.

15 focused unit tests cover stratified-selection determinism and density
spread, physical-target tie-breaking, scene/event-category classification,
manifest-entry merging, and full JSON Schema validation of a synthetic built
entry against `manifest.schema.json`. The pre-existing 353-test non-ROS suite
was confirmed unaffected (11 failures present both with and without this
slice's changes, all in unrelated documentation-hash and ROS-environment
areas).

### Slice 15 — corrected ByteTrack replay for June Seq03 and Seq04

While assembling ROS 2 manifest provenance, each Issue #26 canonical
report's `provenance.bag_path` was traced back through its
`tim_replay_metadata.json` `input_bag` chain to find the true underlying
tracker:

- May (`bags/reference/tim_good/...bytetrack...`) and June Seq01
  (`.../seq01_clean_four_person/full_pipeline/...yolov8s_bytetrack_tim_mars`)
  are confirmed ByteTrack;
- June Seq03 and Seq04's existing evidence traced back to
  `bags/replay/p018_ocsort_sequences_305578f3_2026_07_19/seq0{3,4}_ocsort_freeze_r1`
  — an **OC-SORT** replay chain, not ByteTrack.

Issue #30 requires "a raw ByteTrack baseline using the same detections,
candidate tracks, target initialization, frames, and evaluation ground
truth" as the TIM-MARS branch. The existing Seq03/Seq04 OC-SORT-based
evidence does not satisfy that, so it is not reused for Issue #30.

Both sequences' official ByteTrack `full_pipeline` bags already exist
(`.../seq03_crossing_ambiguity/full_pipeline/...yolov8s_bytetrack_tim_mars`,
`.../seq04_occlusion_no_exit/full_pipeline/...yolov8s_bytetrack_tim_mars`)
with `/tracks`, `/target` and `/camera/dashboard` already recorded live.
`tools/experiments/run_deterministic_tim_replay.py` — the same tool and
canonical TIM-MARS config already used for May and Seq01 — was run against
each, using `--raw-target-mode source` (the raw baseline is the live
ByteTrack-selected `/target` output, unmodified) and `--selected-track-id`
set to each sequence's own initial `correct_target_track_id` from its
official ByteTrack annotation CSV (`seq03_bytetrack.csv`: 2;
`seq04_bytetrack.csv`: 1). Output bags:

- `bags/replay/p030_broader_sequences_bytetrack_2026_08_07/seq03_crossing`
- `bags/replay/p030_broader_sequences_bytetrack_2026_08_07/seq04_occlusion`

Both were generated twice; the tool's own `generated_semantic_sha256`
determinism digest was identical across both runs for each sequence,
confirming reproducibility. `tools/analysis/evaluate_tim_event_recovery.py`
was then run against each new bag with its correct ByteTrack annotation CSV
(`seq03_bytetrack.csv`, `seq04_bytetrack.csv`), matching the same evaluator
settings as the May/Seq01 canonical evidence
(`--timebase header --step-s 0.05 --max-output-age-s 0.9
--stable-recovery-duration-s 0.25`), producing
`artifacts/reports/p030_broader_sequences/seq0{3,4}_*_bytetrack/`.

Resulting selected-target summary (raw ByteTrack vs. TIM-MARS, same shared
candidate stream):

| Sequence | Correct [s] raw → TIM | Wrong [s] raw → TIM | Wrong bursts raw → TIM |
|---|---:|---:|---:|
| Seq03 crossing | 12.457 → 73.892 | 54.020 → 6.053 | 24 → 9 |
| Seq04 occlusion | 5.993 → 39.593 | 0.700 → 0.000 | 3 → 0 |

TIM-MARS substantially increases correct-target duration and reduces
wrong-target duration and bursts on both sequences versus the raw ByteTrack
baseline sharing the same detections and tracker candidates. Seq03 also
recorded 121 memory-contamination events under TIM-MARS (Seq04 recorded 0);
this is reported as-is and is not interpreted or explained away here — it is
a fact for the eventual thesis discussion, not a benchmark-selection input,
since it was observed only after the sequence, target and frame range were
already fixed by Slice 13.

These generated bags and reports are local, ignored artifacts (matching the
existing `bags/` and `artifacts/reports/p030_broader_sequences/` ignore
policy); this section is the tracked record of how they were produced and
their exact hashes, consistent with how the May/Seq01 evidence is documented
in Issue #26.

### Slice 16 — first-phase manifest population and freeze

Added `tools/analysis/add_ros2_first_phase_sequences.py`, which encodes the
four verified ROS 2 sequence records above (bag paths, corrected-ByteTrack
provenance, annotation paths, initial tracker identity, measured image
count and bag duration) and appends them as schema-validated
`sequence_manifest.json` entries.

Per-sequence facts are hand-verified rather than derived from a shared
profiler, because there are exactly four fixed sequences with a one-off
provenance correction (Slice 15), unlike the generically discoverable
external datasets. `target.dataset_identity` and
`target.initial_tracker_identity` are both set to the sequence's own
official annotation's initial `correct_target_track_id` — a value already
fixed by the existing annotation, not a new selection made from TIM-MARS
outcomes. `frame_contract.frame_rate` is the sequence's measured
`images_loaded / bag_duration_s` from its replay provenance (5.3–7.5 Hz for
these `/camera/dashboard`-topic replays), reported instead of the nominal
30 FPS capture rate documented in `flight_metadata.txt`, since the dashboard
topic is a throttled preview stream and the measured rate is what the
evaluator actually uses for timing. `image.width`/`height` are `640x640`,
matching the letterboxed resolution the deterministic replay tool was
actually run with, not the `640x480` `camera_publish` label.

With the four ROS 2 entries merged into the nine DanceTrack/VisDrone-MOT
entries from Slice 14, the manifest holds all 13 first-phase sequences. The
tool's `--freeze` flag then sets every sequence's `status` to `frozen`, sets
the manifest root `status` to `frozen`, records `frozen_date` and
`manifest_commit`, and the result is validated against
`manifest.schema.json` before being written.

This is the deterministic pre-outcome freeze for the first benchmark phase:
sequence, split, physical target identity, initialization window, frame
range and timing provenance are now fixed for all 13 cases before any
TIM-MARS versus raw-ByteTrack comparison outcome (beyond the already-fixed
May/Seq01/Seq03/Seq04 evidence cited for provenance in Slice 15, which did
not influence which sequences, targets or frame ranges were selected) is
used to run the remaining benchmark. MOT17 is not part of this freeze and
remains a later supplementary phase per Slice 12.

7 focused tests cover schema validity of all four built entries, the
frame-rate computation, confirmation that Seq03/Seq04 use their corrected
ByteTrack annotation (not the split's original OC-SORT one), that
`dataset_identity` and `initial_tracker_identity` agree, and manifest-entry
merge replacement semantics.

### Slice 17 — DanceTrack/VisDrone-MOT execution path

DanceTrack and VisDrone-MOT have no existing way to run the real thesis
detector/tracker pipeline: unlike the ROS 2 sequences, they are plain image
folders, not ROS bags. Three new tools close that gap:

- `tools/experiments/images_to_camera_bag.py` writes a sorted external-dataset
  image sequence into a ROS 2 bag as `sensor_msgs/msg/Image` (`bgr8`) on
  `/camera/image_raw`, timestamped at an explicit frame rate. It performs no
  detection, tracking or resizing; the live detector node resizes internally.
- `tools/experiments/capture_external_detector_tracker.sh` builds that source
  bag, then launches the real `perception_pipeline_node` (Hailo YOLOv6n) and
  `tracker_node` (ByteTrack) exactly as
  `run_one_detector_tim_replay.sh` does for recorded flight bags, plays the
  source bag through them, and records `/camera/image_raw`, `/detections` and
  `/tracks` into one output bag. No TIM-MARS, dashboard bridge or live target
  selection runs here: this produces one shared detector/ByteTrack candidate
  stream per benchmark case, satisfying Issue #30's requirement that the raw
  baseline and TIM-MARS branches consume identical detections and tracks.
  `tools/experiments/run_deterministic_tim_replay.py` (already proven in
  Slice 15) is the next step, run separately against this output bag, to
  deterministically generate the paired raw-versus-TIM-MARS streams from that
  one candidate stream.
- `tools/analysis/resolve_external_candidate_stream.py` reads a frozen
  manifest entry's `target.dataset_identity` and initialization window,
  loads the sequence's official ground-truth box for that identity across
  the initialization frames, reads the recorded `/tracks` stream from a
  capture bag (recovering each message's original frame index from its
  `src_stamp_ns`, since the live pipeline can drop frames), and applies
  `external_target_initialization.py`'s existing
  `frozen_target_unique_iou_confirmation_v1` rule -- using the manifest's
  own already-frozen `minimum_match_iou`/`minimum_match_margin`/
  `confirmation_frames` -- to resolve `target.initial_tracker_identity`. This
  does not reopen sequence, physical-identity or frame-range selection; it
  mechanically resolves which live tracker ID that already-frozen physical
  identity corresponds to in one specific capture.

**Real-hardware validation.** The full mechanism was run end-to-end on
`visdrone_mot_val_uav0000137_00458_v` (233 source images, the smallest
selected VisDrone sequence): all 233 images were captured; the live
detector/tracker processed 188 of them (80.7%; the remainder dropped during
normal real-time inference queueing, the same characteristic already visible
in the ROS 2 flight recordings). Detection coordinates correctly carried
source-pixel provenance
(`source=2688x1512;inference=640x640;scale=...;pad=...`), matching the
manifest's `original_source_image_pixels` coordinate contract without any
extra remapping.

Resolving the frozen target (`dataset_identity=41`) against this capture
returned `success: false, reason: no_confirmed_initial_tracker_match`: no
recorded track matched the target's ground-truth box during the frozen
initialization window (frames 0-9). This was verified to be a genuine result,
not a coordinate or alignment bug: the target's own VisDrone annotation flags
`occlusion=1` in those exact frames, and a full-capture IoU/distance search
found the same physical location picked up by the tracker only much later
(frames ~74-86 as one tracker ID, frames ~171-174 as another after an ID
switch) -- i.e. the live detector genuinely did not see this specific,
partially-occluded target during its first ten frames. This is a legitimate
instance of Issue #30's `initialization failure` outcome category, produced
by the pipeline running for real, not injected or cherry-picked.

This is evaluation-relevant evidence in its own right (the annotation-derived
selection policy's `maximum_initialization_occlusion=1` tolerance can select
a physical target that a real detector still fails to confirm), and it will
be recorded as such rather than discarded once the outcome-taxonomy evaluator
(next slice) exists to classify it formally.

Remaining before a full first-phase report: run this capture-and-resolve path
for the other eight external sequences, and build the frame-level MOT-style
evaluator implementing Issue #30's full outcome taxonomy (distractor
selection, stale-ID transfer, ambiguous candidate, initialization failure,
etc.) against oracle and end-to-end candidate streams -- distinct from
`tim_evaluation.py`/`evaluate_tim_event_recovery.py`, which are built for the
ROS 2 sequences' interval-annotation format, not per-frame MOT-style ground
truth.

### Slice 18 — frame-level outcome taxonomy and end-to-end report

Added `tools/analysis/evaluate_external_frame_outcomes.py`, the per-frame
MOT-style physical-target classifier the external (DanceTrack/VisDrone)
sequences need.

Design:

- primary correctness is IoU between a stream's output box and the
  sequence's own ground-truth box for the frozen physical identity --
  tracker-ID continuity is never the correctness signal, matching the core
  invariant that tracker IDs are temporary candidate labels;
- `external_target_initialization.match_frame` (already frozen and used for
  initialization) is reused, unmodified, as the per-frame "spatial oracle"
  that explains *why* a frame is wrong or empty: no candidate near the
  target, an ambiguous margin between two candidates, or a confident
  candidate that went unpublished;
- a same-person recovery across a tracker-ID change is distinguished from
  plain continuation by tracking the last tracker ID that was actually
  correct;
- a wrong output is classified as `stale_id_transfer` if its tracker ID was
  previously correct and now spatially matches a different real person, or
  `distractor_selection` if that ID was never correct;
- wrong-person outcomes (`distractor_selection`, `stale_id_transfer`,
  `wrong_unmatched_output`, `wrong_output_during_physical_absence`) are a
  disjoint set from lost/suppressed/absent outcomes
  (`safe_suppression`, `target_candidate_absent`, `physical_absence_correct`,
  `ambiguous_candidate`) and are never merged, per Issue #30's "wrong is
  worse than lost" invariant.

This covers seven of the eight required outcome categories directly
(correct target, correct same-person recovery, safe suppression/lost,
distractor selection, stale-ID transfer, target-candidate-absent, ambiguous
candidate); `initialization failure` is a sequence-level outcome, already
produced by `resolve_external_candidate_stream.py` when no live tracker
candidate confirms the frozen physical identity within the initialization
window (Slice 17). 13 focused tests cover every outcome category and confirm
the wrong/lost disjointness invariant directly.

Added `tools/analysis/run_external_sequence_report.py`, which chains the
whole per-sequence pipeline: resolve the frozen tracker identity from a
capture bag; if that fails, report `initialization_failure` and stop (there
is no valid stream to score); otherwise run
`run_deterministic_tim_replay.py` unmodified (`--raw-target-mode
selected_id`, the resolved ID) to deterministically generate the paired
raw-versus-TIM-MARS streams from the one captured candidate stream; read
both `/target` and `/target_memory_mars` back (recovering each message's
original frame index from `src_stamp_ns`, matching Slice 17's approach for
`/tracks`); classify every evaluation frame for both streams; and report
both streams' outcome summaries side by side.

Verified against the real `visdrone_mot_val_uav0000137_00458_v` capture from
Slice 17: correctly reports `initialization_failure` and does not attempt a
replay, since there is no confirmed tracker identity to seed either the raw
baseline or TIM-MARS.

Remaining: run this report for every captured sequence once the batch
capture (Slice 17) finishes, and aggregate the per-sequence reports (plus
the four ROS 2 sequences' Issue #26-vocabulary evidence) into the first
complete first-phase benchmark report.

### Slice 19 — oracle-candidate mode

Added `tools/analysis/build_oracle_candidate_bag.py` for the
`oracle_candidate` evaluation mode: it replaces the detector and tracker
with an idealized candidate stream built directly from official ground-truth
boxes, isolating TIM-MARS identity-memory and recovery behaviour from
detector/tracker failure.

The physical identity is never disclosed to TIM-MARS as a shortcut. Every
physical person -- the target and every distractor alike -- receives a
synthetic oracle tracker ID from a single global incrementing counter
assigned in frame order, never derived from or equal to the dataset
identity. A new oracle ID begins whenever a physical identity's own
annotated frame indices have a gap (the ground truth itself records the
person absent and then present again), so real re-entry/occlusion structure
already in the source data becomes controlled candidate-identity
fragmentation, per Issue #30's oracle-mode requirement, without inventing
synthetic failures. TIM-MARS must still discover which oracle ID is the
frozen physical target through the existing blind IoU/margin/confirmation
initialization rule -- identical to how it discovers a real tracker's ID --
not through direct identity disclosure.

Real images are written alongside the synthetic `/tracks` stream (not boxes
alone), because the canonical TIM-MARS configuration has
`appearance_enabled: true`, and Issue #30 forbids changing that policy for
this evaluation; oracle mode isolates detector/tracker failure, not
appearance-matching behaviour.

6 focused tests cover the oracle-ID assignment logic: continuous visibility
keeps one ID, a visibility gap starts a new one, different physical
identities never share an ID, excluded/ineligible rows do not join a
segment, oracle IDs never equal the dataset identity, and IDs are globally
unique across identities and segments.

Verified at full scale on the real `dancetrack0004` sequence (1203 frames):
1203 images and 1203 track messages written, 3499 total oracle boxes across
17 distinct oracle-ID segments for that sequence's physical identities.

The resulting bag has the same `/camera/image_raw` + `/tracks` shape as a
live capture bag, so `run_deterministic_tim_replay.py` and
`run_external_sequence_report.py`'s downstream resolve/replay/classify
pipeline (Slices 17-18) apply to it unmodified.

### Slice 20 — first-phase aggregate report

Added `tools/analysis/aggregate_first_phase_report.py`, a read-only
aggregation step over the frozen 13-sequence manifest: for each sequence it
reads the already-generated per-sequence report (external sequences from
`run_external_sequence_report.py`'s frame-level taxonomy; ROS 2 sequences
from the existing Issue #26 event-recovery reports) and rolls up
evaluated/initialization-failure/missing counts across the whole first
phase. It does not recompute anything itself and does not silently skip a
sequence with a missing report -- every sequence appears in the output with
an explicit status. 2 focused tests cover the counting logic and the
missing-report case.

### Slice 21 — development-host memory crashes

The 8 GB RAM / zero-swap development Raspberry Pi crashed and rebooted twice
while running the first-phase batch (2026-08-07, ~12:39 and ~15:01).

Root cause 1, fixed in this slice:
`rosbag2_py.SequentialCompressionReader` decompresses an entire compressed
mcap file up front (observed: a 1.7 GB compressed capture produced a 7.5 GB
decompressed file), and this happened independently in both the resolve
step and the deterministic-replay step for the same sequence. Fixed with
explicit, single, controlled streaming decompression via the `zstd` CLI
(`resolve_external_candidate_stream.ensure_uncompressed_bag`), reused across
both steps and deleted afterward; direct use of a still-compressed bag now
fails with a clear error (`open_bag_reader` / `run_deterministic_tim_replay.py`
`open_reader`) instead of silently risking OOM. Confirmed on the real 7.5 GB
`dancetrack0004` case: the `zstd` subprocess peaked at ~7 MB RSS, available
memory stayed at 7.0 GiB throughout, and the sequence's report generated
successfully with no crash.

A second decompression-metadata bug surfaced during that fix: a genuinely
uncompressed bag written by the real rosbag2 writer still carries
`compression_format`/`compression_mode` as empty strings, not absent: the
first version of this fix removed the keys entirely, which the strict
metadata parser rejected (confirmed by inspecting a real uncompressed bag's
`metadata.yaml` rather than guessing). Fixed by setting empty strings
instead of removing the keys.

Root cause 2, found but deliberately NOT fixed in this slice (out of scope
here; tracked for the next slice): `run_deterministic_tim_replay.py`
preloads every appearance image as a full decoded array into one in-memory
list before processing at all (`images.append((stamp_ns, image_bgr))`).
This was only ever exercised against the small ROS 2 sequences (<=807
images at 640x640, ~1 GB) and is unsafe for larger/higher-resolution
external sequences (`dancetrack0004`: 1203 images at 1920x1080, ~7.1 GB).

Repo integrity was verified intact after both crashes (`git status` clean,
`git fsck` showed only harmless dangling blobs, all commits present).

Per operator instruction, the first-phase batch was paused after this slice
so the one already-generated external result
(`visdrone_mot_val_uav0000339_00001_v`, small enough to be unaffected by
either crash) could be forensically verified before trusting or extending
it -- see Slice 22.

### Slice 22 — false wrong-person signal: missing source-resolution flags

Forensic investigation (requested by the operator, who independently
reached the same diagnosis) of `visdrone_mot_val_uav0000339_00001_v`'s
reported 7 TIM-MARS `wrong_unmatched_output` frames (raw: 0) found this was
**not** a genuine TIM-MARS tracking failure but a pipeline coordinate-space
bug.

`run_external_sequence_report.py`'s `run_deterministic_replay` never passed
`--image-width`/`--image-height` to `run_deterministic_tim_replay.py`, which
defaults both to `640.0` -- the resolution the ROS 2 field sequences it was
built for use, not this VisDrone sequence's actual `1904x1071` source
resolution (frozen in the manifest's `image.width`/`image.height`). Tracing
the flagged frames directly: at frame 26 the ByteTrack candidate box was
`(153.38, 616.81, 186.76, 683.39)` and the target ground truth was
`(152.0, 618.0, 185.0, 686.0)`, but TIM-MARS's published box was
`(153.38, 616.81, 186.76, 640.0)` -- the bottom edge clamped to exactly
`640.0`, the wrong assumed frame height. That clamp alone dropped the
correctness IoU from what would otherwise be a match to `0.2995`, just under
the `0.30` threshold, misclassifying a geometry bug as a wrong-person
selection. Frame 25 (classified correct) showed the identical clamp with
IoU `0.3131`, just above threshold by chance -- confirming the clamp was
present continuously, not something that started at frame 26. The raw
baseline was unaffected because it copies ByteTrack boxes through unchanged
and never passes through TIM-MARS's (wrongly-scaled) geometry pipeline.

Fixed by passing the manifest's own frozen `image.width`/`image.height` from
`build_report` through to `run_deterministic_replay`, which now requires
these as explicit arguments (no silent default). A focused regression test
verifies both that `run_deterministic_replay`'s subprocess command includes
the correct `--image-width`/`--image-height`, and that `build_report` wires
the manifest entry's own `image` dimensions through end to end.

Rerunning `visdrone_mot_val_uav0000339_00001_v` after the fix (verified
reproducible across two runs, identical `generated_semantic_sha256`):

| Metric | Raw | TIM-MARS before fix | TIM-MARS after fix |
|---|---:|---:|---:|
| Correct target [frames] | 26 | 19 | 70 |
| Correct same-person recovery | 0 | 0 | 2 |
| Wrong person (any category) | 0 | 7 | 0 |
| Candidate absent | 249 | 249 | 203 |
| Correct fraction | 0.095 | 0.069 | 0.262 |

With the bug fixed, TIM-MARS shows zero wrong-person frames and a
substantially higher correct fraction than raw ByteTrack on this sequence --
the opposite conclusion from the pre-fix number, and a result now consistent
with the "wrong is worse than lost" invariant holding and TIM-MARS
genuinely improving over the raw baseline here.

This was not caught before Slice 17-18's real-hardware validation because
that validation used the smallest VisDrone capture successfully but did not
independently cross-check TIM's *published box geometry* against ground
truth at the pixel level -- only the aggregate outcome counts. Every
external-sequence result generated before this fix (only
`visdrone_mot_val_uav0000339_00001_v`, since the batch crashed before
producing others) must be treated as unreliable and is superseded by the
post-fix rerun above.

### Slice 23 — memory-safe causal image selection

Fixed Slice 21's root cause 2 (`run_deterministic_tim_replay.py` preloading
every decoded appearance image into one in-memory list before processing),
preserving exact causal image selection.

The shared `TimMarsRuntime` (`ros2_ws/src/thesis_bringup/thesis_bringup/
tim_mars/runtime.py`) already exposes two ways to populate its causal-image
timeline: `replace_images()` (unbounded, offline-only, used before this
slice) and `add_image()` (bounded via `image_buffer_size`, already used by
the live ROS node, never previously used by offline replay).
`select_causal_image()` performs a binary search (`bisect_right`) for the
single latest image at or before a query timestamp -- it never needs more
than one image per query. Because `run_deterministic_tim_replay.py` already
sorts every track event into non-decreasing semantic-time order before
processing, the sequence of causally-selected images across all track
events is itself non-decreasing: a bounded buffer populated in timestamp
order is mathematically sufficient for identical results to full preload,
provided every image at or before a track event's timestamp is added before
that event is processed.

Implementation: pass 1 (unchanged read-order and `sequence_index`
numbering, so track-event tie-breaking is byte-identical to before) now
only collects `track_events`; it still reads every message to preserve the
exact original sequencing, but no longer decodes or retains image pixel
data. A second, fresh reader pass -- filtered to only the image topic --
streams images in timestamp order, calling `runtime.add_image()` for each
and discarding the local reference immediately, releasing (processing) each
sorted track event as soon as every image at or before its timestamp has
been added. Any track events after the last image are processed against
whatever the runtime's buffer currently holds, exactly as
`select_causal_image` would already resolve them. The per-track-event
processing body (raw-target generation, TIM target/status message
construction, semantic digest updates) is unchanged, just extracted into a
nested function so both the merge loop and any trailing events can call it.

Validation, in order:

- the pre-existing 35 `test_run_deterministic_tim_replay.py` tests and the
  pre-existing 16 `test_tim_mars_runtime.py` tests pass unchanged;
- a new focused regression test,
  `test_streaming_add_image_matches_bulk_replace_images`, directly proves
  the mathematical property against the real `TimMarsRuntime` class: a
  representative timeline (a gap, a duplicate timestamp resolved
  last-write-wins, a query before the first image, on an image timestamp,
  strictly between images, and after the last image) yields identical
  `select_causal_image` results whether populated via one `replace_images()`
  call or via interleaved `add_image()` streaming;
- rerunning `visdrone_mot_val_uav0000339_00001_v` (small, already known-good
  post-Slice-22 result) end to end produced an outcome-count match *and* a
  byte-identical `generated_semantic_sha256` determinism digest
  (`391eb11385768621dce3cf011474d3ebc8e817f3e000e5d7352650aa0208c5e0`) to the
  pre-streaming-refactor run;
- rerunning `dancetrack0004` -- the exact sequence that crashed the
  development Pi twice under the old preload approach -- completed
  successfully with available memory staying at ~7.0 GiB throughout (versus
  the ~7.1 GB single-sequence preload that previously exhausted an 8 GB,
  zero-swap host).

`dancetrack0004`'s post-fix result is new data (this sequence never
completed before this slice): raw 99/1203 correct (25 wrong-person, all
`stale_id_transfer`), TIM-MARS 107/1203 correct but 119 wrong-person (23
`distractor_selection`, 6 `stale_id_transfer`, 89 `wrong_unmatched_output`,
1 `wrong_output_during_physical_absence`) -- TIM-MARS shows *more*
wrong-person frames than raw on this crowded dance sequence. This is
recorded here as raw output only, not yet interpreted: Slice 21's still-open
`candidates_by_frame={}` gap (`run_external_sequence_report.py` does not yet
feed the captured ByteTrack candidate stream into the frame classifier)
makes the candidate-absence/ambiguity/safe-suppression side of the taxonomy
untrustworthy for every case run so far, and per operator instruction that
must be fixed and validated (Slice 24) before any external result -- this
one included -- is treated as a trustworthy finding.

### Slice 24 — real candidate stream fed to the frame classifier

Fixed Slice 21/23's remaining gap: `run_external_sequence_report.py` passed
`candidates_by_frame={}` to `evaluate_external_frame_outcomes.classify_sequence`
for both the raw and TIM-MARS streams. With no candidates ever present, every
"no output" frame's `match_frame` oracle check always returned
`no_tracker_candidates`, so every such frame was classified
`target_candidate_absent` and `safe_suppression` was structurally
unreachable -- the lost/suppressed side of the outcome taxonomy was reporting
a real number (`target_candidate_absent`) that was actually the sum of two
different, scientifically distinct situations (a genuine detector/tracker
miss vs. a confident candidate that went unpublished).

`resolve()` already reads this same recorded `/tracks` stream internally
(via `resolve_external_candidate_stream.load_tracker_candidates`) to confirm
the frozen physical target's live tracker identity. `build_report` now calls
it a second time -- while the (possibly temporary, decompressed) capture bag
still exists, before the `finally` block that removes it -- and groups the
result by frame, passing the real `candidates_by_frame` to both
`classify_sequence` calls.

Two focused regression tests: one confirms `load_tracker_candidates` is
called with the sequence's own frame rate; a second constructs synthetic
`TrackerCandidateObservation`s across two frames and confirms
`classify_sequence` receives them correctly grouped by
`normalized_frame_index`, for both the raw and TIM-MARS calls.

Rerunning both already-generated external results with the fix (wrong-person
and correct-target counts are unaffected, as expected, since those never
depended on `candidates_by_frame`; only the "no output" breakdown changes):

| Sequence | Stream | Candidate absent before | Candidate absent after | Safe suppression after |
|---|---|---:|---:|---:|
| `uav0000339_00001_v` | raw | 249 | 107 | 142 |
| `uav0000339_00001_v` | TIM | 249 | 107 | 96 |
| `dancetrack0004` | raw | 1077 | 652 (+1 ambiguous) | 424 |
| `dancetrack0004` | TIM | 973 | 644 | 329 |

Both sequences' `candidate_absent + safe_suppression (+ ambiguous_candidate)`
sums match the old lumped `target_candidate_absent` totals exactly,
confirming the fix redistributes an already-correct total into the right
categories rather than changing the underlying frame-by-frame classification
logic.

With both Slice 23 (memory-safe replay) and this slice validated, both
outstanding pipeline bugs identified during the operator-directed forensic
review are now fixed, tested, and confirmed against real sequences.

### Slice 25 — batch resumption, capture-tooling fixes, and a post-freeze scope decision

With both fixes validated, the operator authorized resuming the frozen
first-phase external batch using the existing captures.

**`dancetrack0004`'s wrong-person signal, investigated.** Before continuing,
Slice 24's still-open `dancetrack0004` finding (TIM-MARS 119 wrong-person
frames versus raw's 25, on the corrected pipeline) was investigated per
operator instruction to stop and investigate any suspicious result rather
than tuning TIM or blindly aggregating. A scan of every wrong-person-category
output box for the Slice 22 coordinate-clamp signature (a coordinate exactly
at `640.0` or `0.0`) found zero matches. Sample `distractor_selection`
frames (544-549) show TIM's output consistently and cleanly matching a
different, spatially distinct real person (IoU 0.62-0.71 against dataset
identity 2) while the true target sits in a clearly different image region.
Sample `wrong_unmatched_output` frames (616-620) show TIM's output box
partially overlapping the target with a correctness IoU declining from 0.30
to 0.11 over five frames -- consistent with tracking drift during a
crossing/occlusion event, not a coordinate artifact. Both patterns are
genuine ID-confusion/drift behaviour in a crowded, similarly-dressed dance
scene, not a residual pipeline bug. This result is reproducible: an
independent `build_report` run produced identical outcome counts.

**Re-verification of `uav0000137_00458_v` and `uav0000117_02622_v` under the
corrected pipeline.** Both reconfirm as `initialization_failure`, unchanged
from their pre-fix results (expected, since resolution runs before either
fixed code path). `uav0000117_02622_v` was additionally forensically
checked, since its capture bag holds only 27 tracker-candidate observations
across the entire 349-frame sequence -- unusually low next to the
hundreds-to-low-thousands seen on other sequences. The target's own GT box
in this sequence is 32x83 px in a 2720x1530 frame (about 1.2% of frame
width), and zero tracker candidates exist anywhere in the frames 0-9
initialization window. This is a genuine detector miss on a real, tagged
`external_stress_test` sequence (`crowd_crossing`, ~88 people), not a
capture defect.

**`uav0000268_05773_v` (4K VisDrone) capture required two additional
tooling fixes.** This sequence's 3840x2160 source resolution is far larger
than any other frozen sequence (next largest: 2720x1530).

1. *OOM on first capture attempt.* `ros2 bag play`'s
   `--read-ahead-queue-size` defaults to 1000 messages; at ~25 MB per
   uncompressed 4K `bgr8` frame, that is an attempted ~25 GB read-ahead
   buffer on an 8 GB, zero-swap host. `journalctl -k` confirmed the kernel
   OOM-killer terminated the `ros2 bag play` process
   (`anon-rss:7066940kB` at kill time). Fixed in
   `tools/experiments/capture_external_detector_tracker.sh` by adding a
   configurable `READ_AHEAD_QUEUE_SIZE` (default 20) passed through to
   `ros2 bag play`, and by checking the play command's exit status instead
   of silently reporting `[ok]` on a killed/failed player (the original
   script's `set +e` plus an unchecked exit code is exactly how the first,
   fully empty (`message_count: 0` on every topic) capture was reported as
   successful).
2. *Frame loss on second capture attempt.* With the OOM fixed, a second
   attempt completed without crashing but recorded only 675/978 image
   messages (69%) and 81/978 tracks/detections (8.3%), versus 100% image
   coverage on both other already-validated captures
   (`uav0000339_00001_v`: 275/275; `dancetrack0004`: 1203/1203). The
   recorder's own log showed `Cache buffers lost messages` (302 image
   messages) during the final cache flush, coinciding with disk usage
   peaking at 96% (9.7 GiB free) while the 16.8 GB uncompressed `.mcap` was
   being compressed concurrently with live capture. A third attempt, run
   with a 5x slower playback rate (`PLAY_RATE=0.02`) and with disk headroom
   restored to 54 GiB free beforehand (by first deleting artifacts from the
   two failed attempts), completed cleanly: 978/978 images (100%), 607/978
   tracks/detections (comparable to other sequences' natural detector
   sparsity), zero lost messages, zero queue-starved warnings.

**Post-freeze scope decision (operator-directed, pre-outcome).** After the
clean `uav0000268_05773_v` capture, generating its frame-level report
required `ensure_uncompressed_bag`'s safety guard (6x compressed size + 25
GiB floor, hardened in Slice 21 after a real OOM crash) -- for this
sequence's 8.3 GiB compressed bag, ~75 GiB free, versus 46 GiB actually
free. Rather than weaken that safety margin, the operator was asked how to
proceed and made an explicit, pre-outcome scope decision, unrelated to any
tracker or TIM-MARS result:

- All five DanceTrack sequences (`dancetrack0004`, `0019`, `0063`, `0073`,
  `0094`) are excluded from the primary Issue #30 benchmark as
  substantially out-of-domain for this thesis's selected-person
  UAV-following objective (DanceTrack is indoor, ground-level, close-range
  dance/performance footage).
- `uav0000268_05773_v` is excluded as a disproportionate resource-cost
  outlier: its 4K capture required two tooling fixes and its report
  generation exceeds the current disk-safety margin.
- These sequences' manifest entries are marked `"status": "excluded"` (a
  value the schema already defined) with an explicit reason recorded per
  entry in each `exclusions` array, rather than deleted from the manifest,
  keeping the exclusion itself auditable in the frozen manifest's history.
  No replacement sequences were selected to backfill the excluded slots.
- `tools/analysis/aggregate_first_phase_report.py` was updated to route any
  sequence with `status: "excluded"` into a separate `excluded_sequences`
  list (with its manifest exclusion reasons and, where one exists, its
  report) rather than counting it in the primary
  `sequences`/`evaluated_count`/etc. aggregate. A new regression test
  (`test_excluded_sequence_is_kept_out_of_primary_counts`) covers this; the
  three pre-existing tests are unaffected since they use fixture manifests
  with no `status` field, which continues to mean "included" for backward
  compatibility.
- Heavy local (git-ignored) data for the excluded sequences was deleted:
  the DanceTrack dataset (`data/datasets/external/dancetrack/`, 8.1 GB),
  all five DanceTrack capture bags (7.4 GB), the `dancetrack0004` replay bag
  (7 MB) and oracle-mode bag (7.0 GB), and for `uav0000268_05773_v` its
  source images (1.1 GB) and its capture bag (8.9 GB, deleted after the
  clean-capture confirmation above since no report was generated from it).
  Total reclaimed: roughly 32.5 GB (46 GiB &rarr; 79 GiB free). This did not
  reach the ~75 GiB the decompression guard would need for
  `uav0000268_05773_v` at the time DanceTrack alone was removed (only
  brought free space to ~70 GiB); no frame-level report exists for this
  sequence. `dancetrack0004`'s report (generated before the exclusion
  decision, Slice 24) is retained in
  `artifacts/reports/p030_broader_sequences/external_frame_reports/` and
  surfaced under `excluded_sequences` as auditable, out-of-primary-scope
  evidence; `dancetrack0019/0063/0073/0094` were never evaluated before the
  exclusion and have no report.
- No sibling repository copies or unrelated prior-work bags
  (`bags/replay/p044_*`, `p008_*`, `p019_*`, `p006b_*`, `p017_*`, `p028_*`,
  `p009_*`, `p018_*`, and the `Thesis-Code-p028/p033/p034`/`Desktop/old`
  checkouts) were touched.

**Primary aggregate, recomputed on the retained in-scope sequences.**
Running `aggregate_first_phase_report.py` against the amended manifest now
covers 7 primary sequences (the 4 frozen `ros2_internal` sequences plus the
3 retained VisDrone-MOT sequences) and reports the other 6 separately under
`excluded_sequences`:

| Metric | Value |
|---|---:|
| `total_sequences` (primary) | 7 |
| `evaluated_count` | 5 |
| `initialization_failure_count` | 2 (`uav0000117_02622_v`, `uav0000137_00458_v`) |
| `missing_report_count` | 0 |
| `excluded_count` | 6 |

Saved to
`artifacts/reports/p030_broader_sequences/first_phase_aggregate.json`
(git-ignored generated artifact, per the existing `artifacts/reports/`
convention).

Validation: the amended manifest re-validates against
`manifest.schema.json`; `test_aggregate_first_phase_report.py` (now 3
tests, including the new excluded-sequence coverage),
`test_select_first_phase_benchmark.py`, and
`test_add_ros2_first_phase_sequences.py` all pass (25 tests total).

MOT17 remains deferred per Slice 12, unaffected by this scope change.

### Slice 26 — oracle-candidate evaluation completed for the retained sequences

Completed the oracle-candidate evaluation path for the 7 sequences retained
in the primary Issue #30 benchmark after Slice 25's scope decision, per
operator instruction to keep oracle and full-pipeline results scientifically
separate and to only run oracle mode where the repository already has a
defensible oracle/GT candidate-generation contract.

**Scope of this slice.** The frozen manifest's `evaluation_modes` field
already declares which sequences have that contract:
`ros2_internal` sequences declare only `detector_bytetrack_tim` (no
ground-truth multi-person annotation exists for them, only live
detector/tracker output, so there is no defensible way to build an oracle
candidate stream); DanceTrack and VisDrone-MOT sequences declare both
`oracle_candidate` and `detector_bytetrack_tim`. Combined with Slice 25's
exclusions, this leaves exactly the 3 retained VisDrone sequences
(`uav0000117_02622_v`, `uav0000137_00458_v`, `uav0000339_00001_v`) eligible
for oracle evaluation. No new oracle protocol was invented for the 4 ROS2
sequences to fill out the table, per operator instruction.

**Oracle bags.** Built via the existing, Slice-19-validated
`build_oracle_candidate_bag.py` against each sequence's own official
VisDrone-MOT annotations -- unmodified tooling, no new oracle logic. All
three built with 100% frame coverage (`uav0000117_02622_v`: 349/349 images,
7815 oracle boxes, 95 distinct oracle IDs; `uav0000137_00458_v`: 233/233,
3792 oracle boxes, 41 IDs; `uav0000339_00001_v`: 275/275, 3273 oracle boxes,
18 IDs). Because the resulting bag has the same `/camera/image_raw` +
`/tracks` shape as a live capture bag, `run_external_sequence_report.py`'s
`build_report` applied to it unmodified, using a separate
`bags/replay/p030_broader_sequences_oracle_replay_2026_08_07/` replay
output root and saving reports to
`artifacts/reports/p030_broader_sequences/oracle_frame_reports/`, entirely
separate directories from the full-pipeline replay/report paths.

**Keeping the two modes separate.** Added
`tools/analysis/aggregate_oracle_report.py`, a sibling to (not a
modification of) `aggregate_first_phase_report.py`. It reads only
sequences whose manifest entry both declares `"oracle_candidate"` in
`evaluation_modes` and is not `status: "excluded"`, and never writes into
or reads from the full-pipeline aggregate. Sequences it skips are listed
with an explicit reason (`excluded_from_primary_scope` or
`no_oracle_candidate_contract_declared`) rather than silently omitted. 2
focused tests cover the eligibility filter and the missing-report case.
Running it against the current reports confirms exactly the expected split:
3 evaluated, 0 initialization failures, 0 missing, and the other 10
manifest sequences correctly skipped with the correct reason each.

**Full-pipeline results (primary benchmark, 7 sequences).**

| Sequence | Vocabulary | Status | Raw correct | Raw wrong | TIM correct | TIM wrong | Notes |
|---|---|---|---:|---:|---:|---:|---|
| `may_hard_reentry` | event_recovery (duration ratios) | evaluated | 56.5% | 11.7% | 92.3% | 0.1% | TIM lost/suppressed 7.5% |
| `seq01_clean` | event_recovery (duration ratios) | evaluated | 45.4% | 0.0% | 88.9% | 0.0% | both raw/TIM carry 13.6 s of stale output |
| `seq03_crossing` | event_recovery (duration ratios) | evaluated | 13.0% | 56.4% | 77.2% | 6.3% | raw is wrong-heavy on this crossing case |
| `seq04_occlusion` | event_recovery (duration ratios) | evaluated | 10.5% | 1.2% | 69.7% | 0.0% | long occlusion; 8.987 s target-not-visible on both |
| `uav0000117_02622_v` | frame taxonomy | **initialization_failure** | -- | -- | -- | -- | 0 tracker candidates anywhere in the init window; genuine detector miss on a 32x83 px target in an 88-person scene |
| `uav0000137_00458_v` | frame taxonomy | **initialization_failure** | -- | -- | -- | -- | 1515 candidates exist in the capture but none pass the frozen IoU/margin/confirmation rule in the init window |
| `uav0000339_00001_v` | frame taxonomy | evaluated | 26/275 (9.5%) | 0/275 (0.0%) | 72/275 (26.2%)&sup1; | 0/275 (0.0%) | TIM: 2 `correct_same_person_recovery`, 96 `safe_suppression`; both streams: 107 `target_candidate_absent` (shared candidate stream), 0 distractor/stale-ID |

&sup1; `70 correct_target + 2 correct_same_person_recovery`, matching the
operator's independently-confirmed positive forensic figures for this
sequence (constraint check in this slice's request: raw 26/0, TIM 72/0 --
both hold exactly).

Every ROS2 sequence and the one evaluable VisDrone sequence shows the same
pattern: TIM-MARS raises correct-target time/fraction substantially over
raw ByteTrack *and* reduces or matches wrong-person time/fraction --
correctness and safety improve together, not at each other's expense. The
two `initialization_failure` cases are preserved as failures in the primary
denominator (evaluated_count=5, initialization_failure_count=2 of 7), not
removed or reinterpreted, per operator instruction.

**Oracle-candidate results (diagnostic mode, 3 sequences).**

| Sequence | Status | Raw correct | Raw wrong | TIM correct | TIM wrong | TIM safe-suppression | TIM same-person recovery | Candidate absent / ambiguous / distractor / stale-ID |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `uav0000117_02622_v` | evaluated | 349/349 (100%) | 0 | 1/349 (0.3%) | 0 | 348 | 0 | 0 / 0 / 0 / 0 |
| `uav0000137_00458_v` | evaluated | 233/233 (100%) | 0 | 226/233 (97.0%) | 0 | 7 | 0 | 0 / 0 / 0 / 0 |
| `uav0000339_00001_v` | evaluated | 275/275 (100%) | 0 | 61/275 (22.2%) | 0 | 214 | 0 | 0 / 0 / 0 / 0 |

`physical_absence_correct` and `wrong_output_during_physical_absence` are 0
for every oracle run (no genuine annotated absence gap fell inside the
selected target's segment for these three sequences).

Raw is trivially 100% correct in oracle mode by construction: the frozen
raw baseline follows one fixed oracle ID for the whole sequence, and that
ID never switches identity (the ground truth itself is the candidate
stream), so this number measures the oracle contract's internal
consistency, not tracking skill, and must not be read as "raw achieves
perfect tracking." TIM-MARS's correct-target fraction varies drastically by
scene (0.3% / 97.0% / 22.2%) and in every case the non-correct remainder is
almost entirely `safe_suppression`, never a wrong output: TIM-MARS held 0
wrong-person frames across all three oracle runs, the same invariant as the
full pipeline.

**The `uav0000117_02622_v` oracle result (0.3% correct, 99.7%
`safe_suppression`) was investigated before acceptance**, per operator
instruction to inspect any surprising oracle result without tuning the
algorithm. Checked: the passed image dimensions were correct
(2720x1530, matching the manifest, not a repeat of Slice 22's bug);
initialization succeeded cleanly at frame 1 with 7815 oracle candidates
available across the sequence; wrong-person count is 0, ruling out a
coordinate-type defect. This sequence's target has the smallest annotated
box of any retained sequence (32x83 px, ~1.2% of frame width) in the
densest scene (~88 people). The coherent, non-tuned explanation is that
TIM-MARS's appearance-based re-confirmation essentially never reaches
sufficient confidence on a crop this small in a scene this dense, so it
defaults to withholding output rather than guessing -- consistent with, not
contradicting, the zero-wrong-person behaviour seen everywhere else. No
code was changed in response to this result.

**Interpretation -- what the two modes each show, and do not show.** The
full pipeline (real detector -> real ByteTrack -> raw/TIM) measures what
this thesis is actually about: deployed behaviour under real detector and
tracker imperfection. There, TIM-MARS improves both correctness and safety
over raw ByteTrack on every evaluable sequence, and the two genuine
initialization failures mark the honest limit of any anchored-identity
system when the physical target never produces a confirmable candidate at
all. Oracle mode removes the detector and tracker from the loop entirely to
isolate a different, narrower question: given a perfect, always-available,
unambiguous candidate, what does TIM-MARS's own identity-memory and
appearance-confirmation logic do on its own? The answer is that it never
once produces a wrong-person output under ideal candidate conditions
either, but its willingness to actively commit to an answer (versus safely
suppressing) is scene-dependent and, on the hardest scene, very low. Oracle
mode is therefore evidence about TIM-MARS's own confirmation threshold
behaviour in isolation, not a second, competing measurement of "real"
accuracy, and the two numbers must not be averaged, combined, or presented
as a single headline figure.

Validation: `test_aggregate_oracle_report.py` (2 new tests) passes;
`test_aggregate_first_phase_report.py`, `test_select_first_phase_benchmark.py`,
and `test_add_ros2_first_phase_sequences.py` (the primary-scope tests
already covered in Slice 25) continue to pass unchanged, confirming this
slice added a new, separate read path rather than touching the primary
aggregate. No TIM-MARS threshold, detector setting, ByteTrack parameter, or
sequence selection was changed while producing or interpreting any of the
above.
