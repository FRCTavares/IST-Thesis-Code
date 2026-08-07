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
