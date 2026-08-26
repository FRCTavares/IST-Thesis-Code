# P1.10 Physical-reference annotation workload plan (M4A-v2)

GitHub Issue: #25
Branch: `issue-25-bbox-evaluation-continuation-20260825`
Companion to: `docs/issues/p1-10-improve-bbox-evaluation.md` (frozen `tim_physical_target_bbox_v1` contract, Milestones 1-3)

## M3-v2 human browser acceptance (2026-08-25)

Francisco completed the pending six-item human acceptance checkpoint using the
live `Physical reference v2 (Issue #25)` workspace and the canonical June Seq01
raw curated-source bag `2026-06-19__12-48-17` (1520 frames). These results are
human-observed browser evidence; they are not substitutes for M4B physical-person
annotation.

1. **PASS -- explicit JSON reload after a rejected draft.** A valid scratch
   artifact was saved as sequence `m3_smoke_seq01_20260825`; after clearing
   `sequence_id`, changing the visible bbox draft, and receiving the expected
   backend save rejection, explicit Load-selected-JSON restored the saved
   metadata/sample and removed the rejected changed draft.
2. **PASS -- distractor correspondence after save/reload.** A
   `distractors_complete` sample assigned `phys_d001` and `phys_d002` to two
   distinct physical distractors. Reload preserved the same person
   correspondences and deterministic ordering.
3. **PASS -- reverse-direction drawing.** A target box drawn bottom-right to
   top-left was normalised around the intended person and remained correct
   after save/reload.
4. **PASS -- resize alignment.** Resizing the browser from a very narrow window
   to full width left target and distractor boxes visually aligned with the
   same physical people, with no observable source-pixel coordinate drift.
5. **PASS -- final-frame right-boundary anchor.** At source frame `1519 / 1519`,
   the UI reported `t_s = 61.201 s` and the valid right-boundary-anchor hint.
   Save/reload preserved samples at `0.000 s` and the exact final timestamp,
   including the final target bbox.
6. **PASS -- legacy editor independence.** After returning to the loader, the
   same source bag opened in `Annotation editor`; Tracker IDs, interval/CSV
   controls, and video playback remained functional independently of the v2
   physical-reference workspace.

### Non-blocking loader-navigation observation

During that session, `Change bag / annotation` appeared to do nothing once
from a loaded workspace; refreshing returned to the loader and allowed the
legacy-editor check above. A deterministic source audit found the button is
`type="button"` and directly calls `changeLoadedBag()`, which pauses playback,
hides all three loaded workspaces plus the summary/playback dock, removes the
`bagLoaded` body class that hides the loader, resets load progress, and scrolls
to the top. The corresponding CSS exposes the loader when that class is absent.
No conflicting handler or state transition was found, and the ended browser
state could not be reproduced deterministically on the Pi (no browser-automation
runtime is installed). Therefore this is recorded as an unconfirmed,
non-blocking observation, not a reproduced defect; no UI code was changed. If
it recurs, capture the browser console error and exact click/loading state
before considering a narrowly scoped fix.

## M4B Seq01 development history: assisted interpolation review (2026-08-25)

Francisco has started the canonical June Seq01 artifact at
`docs/data/physical_target_references/seq01_clean.json` with sequence ID
`june_seq01_clean`. It currently exists locally as an **untracked,
human-created in-progress artifact** and was deliberately not edited, staged, or
committed by the tooling work described here. Its two explicit
`present_scored` / `distractors_complete` endpoint anchors retain the target
plus `phys_d001`, `phys_d002`, and `phys_d003`; the final anchor claims
interpolation from the first.

That interpolation claim is not yet accepted as scientifically valid across
the whole 61.201 s span. The following annotation assistance was added so the
human can review it efficiently while preserving the frozen v2 contract:

- **Effective preview:** the backend validates the in-memory v2 artifact and
  batch-resolves every source-frame timestamp through the evaluator's actual
  `resolve_reference_interval` helper. Exact anchors are classified
  separately, including the final right boundary. The frontend only caches and
  paints the returned geometry; it contains no second interpolation
  implementation.
- **Playback display:** effective preview is enabled by default. Solid
  green/orange boxes are explicit accepted/draft geometry, dashed cyan boxes
  are interpolated effective reference, and dotted yellow boxes are unaccepted
  image-only proposals. Status text distinguishes `explicit_keyframe`,
  `interpolated`, `reference_gap`, `absent`, and
  `present_reference_unavailable` continuously while scrubbing or playing.
- **Geometry proposals:** a proposal is requested manually while paused and is
  propagated from the nearest explicit human anchor by sparse Lucas--Kanade
  optical flow with median translation. It is capped at 150 source frames,
  runs off the FastAPI event loop, retains the anchor's target role and exact
  `phys_dNNN` labels, and refuses insufficient visual evidence rather than
  guessing. It reads only cached source images and human anchor geometry: no
  detector, tracker ID, RAW/TIM selected target, or TIM-MARS output participates.
- **Review assistance:** proposal/effective disagreement is shown per physical
  person using IoU, centre displacement normalised by effective-reference
  height, and logarithmic width/height scale delta. The default 0.65 / 0.25 /
  0.25 thresholds only trigger `Possible interpolation drift -- review
  recommended`; they are annotation-tool parameters, never evaluation or
  TIM-MARS thresholds.
- **Explicit acceptance boundary:** generating or previewing a proposal changes
  neither samples nor disk. The human may copy it into an editable draft or
  explicitly accept it as an in-memory anchor. JSON still changes only after a
  separate explicit Save action through the authoritative v2 validator.

A deterministic read-only pilot against the real in-progress artifact resolved
0.000 s and 61.200516816 s as explicit anchors and 5, 15, 30, 45, and 55 s as
interpolated target-plus-three-distractor frames with the same
`phys_d001`--`phys_d003` correspondence. The artifact SHA-256 was identical
before and after. On the real cached source frames, an image-only proposal from
frame 0 to frame 107 (5.00004372 s) succeeded for target plus all three
distractors and likewise left the artifact unchanged. This proves tooling
operation only; it does **not** validate the long interpolation visually.

### Sequential propagation added after real nonlinear-motion review

During real M4B playback Francisco stopped near frame 190
(`t_s = 7.833641125 s`) because the dashed endpoint-linear boxes remained on
the legal evaluator path while the four people had followed nonlinear image
motion. This is not an evaluator defect; it demonstrates that the two endpoint
anchors are scientifically insufficient.

The assisted-review instrument now provides a second, strictly non-canonical
layer:

- `Generate/refresh sequence proposals` propagates each target / `phys_dNNN`
  geometry hypothesis frame by frame in both directions between compatible
  explicit human anchors. Sparse Lucas--Kanade feature displacement is computed
  independently inside each preceding bbox. A person's chain stops on
  insufficient visual evidence; no other person, tracker trajectory, drawing
  order, or detector identity can replace it.
- Each per-person proposal records tracked feature count/fraction, maximum LK
  residual over the propagated direction, boundary truncation, directional
  agreement and a deterministic `high` / `medium` / `review` / `ambiguous` /
  `lost` status. These labels are review categories, not probabilities.
- The server computes once in a background worker, exposes progress, and caches
  the complete result only in process/session memory. Scrubbing and playback
  then paint dotted yellow boxes without further optical-flow work.
- IoU, centre/ref-height and scale disagreement against the evaluator's cyan
  reference create flagged frames. Adjacent flags are grouped into review
  regions. `Previous review region` / `Next review region` jump to each
  region's worst frame.
- Adaptive anchor selection recursively finds the largest proposal-versus-
  piecewise-linear disagreement, proposes that frame as a virtual split, and
  repeats until thresholds, minimum spacing, or the 24-suggestion safety cap is
  reached. Suggested anchors are buttons for inspection, never samples.
- A pure anonymous-detection geometry matcher is available for a future source
  of person boxes. It accepts bbox coordinates only, can refine x/y/width/
  height when one candidate is clearly best, and returns `ambiguous` on a close
  tie. The Seq01 pilot does **not** use it because this curated-source session
  supplies no appropriate anonymous detector stream; no production detector,
  RAW/TIM selected target, tracker ID, or TIM-MARS decision enters propagation.

The read-only two-anchor Seq01 pilot produced 1,520 frame records in 152.2 s
after a 5.3 s bag-cache load (about 1.96 GB peak process RSS). At frame 190 it
retained `target`, `phys_d001`, `phys_d002`, and `phys_d003` and reported
proposal-versus-cyan IoUs of 0.341, 0.338, 0.248, and 0.431 respectively. The
current conservative thresholds group the continuously inadequate endpoint
span into one review region (frames 1--1518) and hit the 24-suggestion cap. One
suggestion is frame 188 / 7.767 s, directly covering the observed nonlinear
motion. A live browser check confirmed progress reporting, cached yellow-box
playback, suggestion navigation, and continuous updates from frame 190 to 207.
This is evidence that the tool exposes and prioritises the motion; it is **not**
human approval of any proposed geometry.

No bulk acceptance is offered for this pilot: every current suggestion is
`review`, so the conservative workflow exposes only single-frame Copy/Accept
operations. `Accept current proposal as in-memory anchor` is explicit; JSON is
still changed only by the separate `Save JSON` action. After an in-memory sample
changes, the sequence cache is invalidated and must be regenerated.

### Seq01 review workflow

1. Load the exact `12-48-17` source and `seq01_clean.json`; leave **Show
   effective v2 reference** enabled and click **Generate/refresh sequence
   proposals** once.
2. Inspect the suggested anchors, starting with 7.767 s, and use **Next review
   region** plus ordinary playback to compare the cyan evaluator geometry,
   dotted yellow proposal, and visible people. Treat all current suggestions as
   `review`, not approved geometry.
3. At each useful suggestion, verify target and every `phys_dNNN`. Use **Use
   current proposal as editable draft** when correction is needed, or **Accept
   current proposal as in-memory anchor** only after that complete human check.
   Check interpolation deliberately.
4. Regenerate the invalidated proposal cache after each accepted/corrected
   anchor; the adaptive suggestions should then re-evaluate the smaller spans.
   Stop and create a trusted human anchor/state boundary wherever correspondence
   is ambiguous or a person is lost.
5. Save JSON separately only after deliberate review, reload it through the v2
   loader, and continue. Accept honest gaps or explicit unavailable/absence
   boundaries where visual judgement cannot support geometry/correspondence.

## Preferred M4B frontend: exact-frame CVAT bridge (2026-08-26)

The endpoint-linear failure and the cost of maintaining a bespoke tracking
frontend motivate a workflow change: CVAT is now the preferred human
annotation/tracking interface, while Thesis-Code remains authoritative for
source provenance, scientific states, validation, and the frozen v2 artifact.

The interchange deliberately uses an **ordered lossless PNG sequence**, not an
encoded video. Filenames are zero-padded (`frame_000000.png` onward), task
sorting is lexicographical, and frame step is one. This avoids introducing a
codec/container decode path whose dropped, duplicated, or reordered frames
would need separate proof. A JSON and CSV manifest records every CVAT index,
source-frame index, positive ROS Image header timestamp (falling back to bag
record time only if absent), exact integer relative nanoseconds, source
dimensions, coordinate convention, evaluation window, bag metadata hash, and
extracting repository HEAD. Nominal FPS never supplies a timestamp.

Create one immutable/select annotation attribute named `physical_ref` on the
single `person` rectangle label. Seq01 values are `target`, `phys_d001`,
`phys_d002`, and `phys_d003`. CVAT numeric track IDs are transport details
and are discarded. The seed XML imports only the four human frame-zero boxes
and marks each track outside at frame one, avoiding a fabricated long endpoint
trajectory; the annotator deliberately resumes/tracks each identity.

Use rectangle **Track** mode. Correct keyframes when geometry drifts; use
`Outside` only when the same person is genuinely not visible, and `Occluded`
only after deliberate review. CVAT's ordinary rectangle interpolation or an
available AI/OpenCV tracker may propose motion, but the human must play through
and correct all four tracks. Optional hosted/enterprise SAM2 is not required
and polygon/mask output is outside this rectangle converter.

Export an ordered PNG task as **CVAT for images 1.1**, the representation
validated on completed Seq01. CVAT may expand track interpolation into one
`<image><box>` annotation per source frame. The converter maps each image ID
and zero-padded filename exactly through the manifest and reads identity only
from the box's stable `physical_ref`; numeric CVAT IDs and drawing order are
never identity. Native video-style CVAT 1.1 `<track>` exports remain a
supported alternate representation. Both paths require exact source-pixel
coordinates and reject missing/duplicate roles, role changes, unapproved
occlusion, unsupported labels/shapes/states, out-of-range boxes, incomplete
frame coverage, and any unproven coordinate transform. Exact source timestamps
come from `frame_manifest.json`, never nominal FPS, and human review remains
authoritative. State/context comes from the separate
`conversion_config.json`, because CVAT `outside`/`occluded` cannot
scientifically imply v2 `absent`, `present_reference_unavailable`, or a
reference gap. Seq01's generated sidecar records Francisco's sequence-specific
full-window `present_scored` / `distractors_complete` assertion; this must
not be copied to Seq02--Seq04 without fresh human evidence.

Conversion defaults to one explicit v2 sample per manifest frame (apart from
explicit sidecar reference gaps), with interpolation only between adjacent
compatible source frames. This preserves the human-reviewed CVAT trajectory
and avoids recreating nonlinear error through sparse endpoint simplification.
No adaptive simplification is performed.

Generated Seq01 package location (ignored by Git):

`data/datasets/processed/cvat/physical_reference/june_seq01_clean/`

Preparation:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
thesis_env/bin/python tools/analysis/cvat_physical_reference.py prepare \
  --bag bags/source/curated/2026-06-19__12-48-17__source__2026-06-19__official__seq01__clean_four_person__image_raw \
  --reference docs/data/physical_target_references/seq01_clean.json \
  --output-dir data/datasets/processed/cvat/physical_reference/june_seq01_clean
```

After returning the CVAT export to the package directory:

```bash
thesis_env/bin/python tools/analysis/cvat_physical_reference.py convert \
  --cvat-export data/datasets/processed/cvat/physical_reference/june_seq01_clean/cvat_export.zip \
  --manifest data/datasets/processed/cvat/physical_reference/june_seq01_clean/frame_manifest.json \
  --config data/datasets/processed/cvat/physical_reference/june_seq01_clean/conversion_config.json \
  --output data/datasets/processed/cvat/physical_reference/june_seq01_clean/seq01_clean_converted.json

thesis_env/bin/python tools/analysis/cvat_physical_reference.py validate \
  --reference data/datasets/processed/cvat/physical_reference/june_seq01_clean/seq01_clean_converted.json \
  --manifest data/datasets/processed/cvat/physical_reference/june_seq01_clean/frame_manifest.json
```

The converted artifact remains generated until Francisco inspects it in the
custom physical-reference workspace and deliberately promotes it. The existing
human `seq01_clean.json` is never an implicit output target.

### Seq01 M4B completion checkpoint (2026-08-26)

Francisco completed human review of the four physical-person tracks in the
ordered PNG CVAT task. The **CVAT for images 1.1** export contains 1,520 images
and exactly one `person` box for each of `target`, `phys_d001`,
`phys_d002`, and `phys_d003` on every frame. The exact-manifest conversion
and frozen-v2 validation both pass with 1,520 `present_scored` samples, zero
missing frames, complete four-role coverage, and the 61.200516816 s final
right-boundary anchor. The completed export SHA-256 is
`5df00afc58f993b5c07f4a1f06755cff1610ff5cbf1a02eb3fabee80a2c86529`;
the generated v2 SHA-256 is
`c0d7c2a3c7471cd9ae2d1a16868110e5f1f30320cf15c21f32ffef2d8d23833d`.
The superseded two-anchor canonical-path draft had SHA-256
`4bc30dea99bba4b5a3ecd93dea9306a8002b59e605135ac97a740fe5a7e5b249`.
No established physical-reference backup-file convention exists, so no ad-hoc
backup file was created. The validated full reference was promoted directly to
`docs/data/physical_target_references/seq01_clean.json`, with SHA-256
`c0d7c2a3c7471cd9ae2d1a16868110e5f1f30320cf15c21f32ffef2d8d23833d`.

June Seq01 M4B is complete. Global M4B remains incomplete until May, Seq03, and
Seq04 receive equivalent human annotation and validation. M5 must not begin
until all required real references and matching same-capture outputs exist.

## M4A-v2 re-plan (2026-08-25)

This section supersedes the v1 workload estimate below for execution planning.
The older sections remain as historical evidence of why v2 was required. No
new visual identity judgement was made in this re-plan: it uses the existing
10 August frame review, direct bag/topic/timestamp inspection, the frozen v2
contract, and existing event annotations only.

### Evidence-path correction

The four physical-reference sources remain the raw captures listed below, but
a reference is scientifically usable only against output regenerated from the
**same capture and timebase**. The current `tim_mars_split_v1` June output
bags cannot be paired directly with these references:

- May's promoted replay embeds the exact `11-03-26` raw-capture name and
  contains `/camera/image_raw`; its provenance is joinable.
- June Seq01's split entry is the independent `12-45-45` live capture,
  whereas the usable raw-image sequence is `12-48-17`.
- June Seq03/Seq04 split entries are image-less downstream replays whose
  preserved lineage points through now-missing OC-SORT replay inputs; the
  annotatable raw captures are `12-55-58` and `12-59-53`.
- The June live `full_pipeline` captures and the raw-image captures have
  different durations and were recorded independently. Scenario names are
  not a timebase join.

Therefore M5 must first regenerate full-pipeline outputs from the exact
annotated raw bag for each sequence and record that source relationship.
Applying a raw-bag reference to a different live capture is prohibited.

### Exact v2 evaluation windows

These are first-to-last `/camera/image_raw` message timestamps, which are
the UI-derived v2 horizons, not bag-level prose estimates.

| Sequence | Frames | Exact `evaluation_window` | Effective cadence | Dimensions |
|---|---:|---:|---:|---:|
| May hard re-entry | 974 | `[0.0, 67.866525700]` s | 14.337 fps | 640x640 |
| June Seq01 | 1520 | `[0.0, 61.200893630]` s | 24.820 fps | 640x480 |
| June Seq03 | 1931 | `[0.0, 83.866288839]` s | 23.013 fps | 640x480 |
| June Seq04 | 2047 | `[0.0, 86.501604967]` s | 23.653 fps | 640x480 |

Every artifact needs an anchor at the first source frame and may use the final
source frame as the legal right-boundary anchor. The final anchor contributes
no duration by itself.

### Final-semantics annotation policy

All four sequences remain conservatively `distractors_complete` wherever
the target is scored. v2 changes the workload because those samples may now
interpolate per physical person, but only when both endpoints have the exact
same `person_ref` set and the annotator judges every trajectory and
visible-extent box to be locally linear.

- Use about 1.0 s anchor spacing in calm, separated motion. Interpolate only
  after checking the whole span, not merely its endpoints.
- Add anchors at every entry, exit, correspondence change, abrupt motion or
  scale change, and occlusion/crossing onset and offset.
- Review difficult regions at about 0.25–0.5 s spacing. Split them into short
  interpolable spans only where the correspondence and geometry are genuinely
  unambiguous. Do not bridge overlaps, uncertain re-entry, or changing visible
  extent just to improve coverage.
- If one physical person disappears, omit that `person_ref`; the set change
  deliberately blocks interpolation. Mint a new `person_ref` after uncertain
  re-entry. Never use a tracker ID to settle correspondence.
- Use `absent` or `present_reference_unavailable` boundary samples only
  after direct human judgement. Existing tracker-ID absence rows are navigation
  hints, not physical-state truth.
- Accept honest `reference_gap_duration_s` where no legal interpolation or
  trustworthy state claim exists. The plan does not invent a coverage target;
  M5 must report the achieved fraction.

### Sequence plan and workload

The ranges count bbox drawings (target plus all plausible distractors), not
mouse clicks or native frames. They assume 1 s anchors in accepted calm spans
and 0.25–0.5 s review in the existing high-risk regions; they will move when
the annotator inspects every span. They are not a reuse of the old 1488-action
estimate.

| Sequence | Existing evidence and risk regions | Correspondence / state requirements | Approximate workload |
|---|---|---|---:|
| May hard re-entry | One prominent companion throughout; seven transferable ambiguity windows at 24.77–25.47, 29.37–30.18, 33.93–36.27, 40.03–41.50, 49.64–51.23, 55.07–56.03, and 58.16–58.93 s; occasional distant people near 17.4 and 66.9 s need checking. | Reuse one companion `person_ref` only while visually certain; split at any actual occlusion/correspondence change. Tracker handovers are not identity boundaries. | 70–90 keyframes; about 140–200 bbox drawings. |
| June Seq01 | Four people were simultaneously visible and separated throughout every prior sample; no crossing was observed. Lowest-risk interpolation pilot, but the physical target label still requires Francisco's confirmation. | Establish three distractor correspondences at the start and preserve them only by visual judgement. Check frame edges/entries before treating the set as constant. | 62–70 keyframes; about 248–280 bbox drawings. |
| June Seq03 | Two people approach during 0–20 s; crossing/overlap risk is concentrated around 20–45 s; all four are visible around 45–60 s; sustained central clustering occurs from about 60 s to the end. | Dense event anchors and short spans through approach/crossing; do not interpolate across overlapping boxes or uncertain correspondence. | 90–170 keyframes; about 330–680 bbox drawings. |
| June Seq04 | Tight multi-person cluster from the opening, heaviest overlap around 35–60 s, spreading around 60–75 s, and renewed clustering near the end; a possible fifth person and possible target absence/unavailability require direct review. | Highest correspondence churn risk. Use explicit state boundaries for genuine absence/unavailability; changed person sets must stop interpolation. | 110–220 keyframes; about 450–1100 bbox drawings, plus roughly 4–8 state-only boundary samples if the suspected episodes are confirmed. |
| **Total** | 299.435 s across 6472 source frames. | Identity-independent `phys_dNNN` correspondence only. | **332–550 keyframes; about 1168–2260 bbox drawings, plus confirmed state boundaries.** |

The upper end is still not a full-coverage guarantee. Under the v2 evaluator's
default 0.05 s grid, a non-interpolated exact keyframe supports only its own
grid interval. Full coverage of every difficult span without interpolation
would approach frame/grid-rate annotation and could exceed ten thousand bbox
drawings. That is not recommended: use legal short-span interpolation where
human judgement supports it and report the remaining reference gaps honestly.

### M4B entry and stopping rule

M3-v2 human browser acceptance and June Seq01 M4B are complete. The next
active M4B work is May, then Seq03 and Seq04, using the exact-frame CVAT bridge
and fresh sequence-specific semantic evidence. After each sequence, validate the JSON with the real
v2 loader and, once same-capture outputs exist, inspect the planned M5 report's
reference coverage before investing in the next sequence. Stop and reassess if
coverage is dominated by gaps or if correspondence cannot be maintained
without tracker-ID inference.

Global M4B remains incomplete human work. Seq01 now has a completed,
converted, validated generated v2 artifact, but it has not yet been promoted
over the existing local canonical-path draft; May, Seq03, and Seq04 remain
unannotated. M5 also remains incomplete and must not start until all required
real annotations and matching same-capture regenerated outputs exist.

## Corrective re-audit (2026-08-10)

The version of this plan first landed for Milestone 4A classified several
regions -- most notably all of June Seq01 -- as `target_only` on the basis
that the target was clearly identifiable and well separated from the other
people on screen. On review, that is the wrong test. The frozen contract's
`target_only` requires the annotator to assert that **no other visible
physical person could plausibly explain a controller-facing person bbox**,
not merely that the target is easy to recognise or that people are not
overlapping. A person-detector-driven controller can plausibly attach its
output to *any* clearly visible, reasonably sized person in frame, whether
or not they are near the target -- separation reduces the chance of a
*localisation* mix-up (two boxes overlapping), but it does nothing to rule
out a *detection/tracking* mix-up (the system latching onto the wrong
person entirely), which is exactly what `identity_context` exists to
capture.

Every region in the original version of Section E was re-examined against
this corrected test, using additional frame samples specifically targeted
at the previously-proposed `target_only` windows (Section A). The result:
**no region in any of the four sequences survives the corrected test.** At
every additional sampled instant, at least one other physically distinct,
clearly resolvable person was simultaneously visible in frame -- all four
sequences are now planned as `distractors_complete` throughout. Section E
below is the corrected region table; Section F is the corrected, larger
workload estimate that results. Interpolation is consequently not used
anywhere in this revised plan (Section F.1) -- there is no confirmed
`target_only` interval left for it to apply to.

## Purpose

This is a **planning** document, not an annotation artifact. It answers, for
each of the four canonical sequences: which timeline regions can safely use
sparse target-only keyframes plus linear interpolation, which regions need
dense manual treatment because more than one physical person is genuinely
competing for the controller-facing output, and roughly how many manual
drawing actions the annotator should expect. **No real physical-reference
JSON was created while producing this document**; all bag paths were
inspected read-only and all sample frames used for visual inspection were
written under `/tmp` on the annotation host, never under
`docs/data/physical_target_references/`.

## A. How this plan was built

- Exact canonical bag paths were resolved by cross-referencing
  `docs/data/catalogue/bag_inventory.md`, `docs/data/splits/tim_mars_split_v1.json`,
  and direct `metadata.yaml`/`flight_metadata.txt` inspection (Section B).
- Frame counts, durations, and `/camera/image_raw` pixel dimensions were read
  directly from each bag via `rosbag2_py` (never assumed from prose
  elsewhere in the repository -- Section B flags one place where an existing
  assumption turned out to be wrong).
- `coordinate_convention` was resolved for all four bags using the existing,
  already-tested `tim_ui_physical_reference.resolve_coordinate_convention`
  (Milestone 3 corrective follow-up), not re-derived by hand.
- Visual inspection used the existing annotation UI's `/frame.jpg` renderer
  (`clean=1&draw_raw=0&draw_tim=0&draw_reference=0`, i.e. plain source pixels
  with **no tracker/detector overlay baked in**, so the sampling below is not
  contaminated by the very tracker output Issue #25 exists to evaluate
  independently of). 6-7 frames spread across each sequence's full duration
  were fetched to `/tmp` on the annotation host and inspected directly, one
  at a time, not as a single composite contact sheet. The corrective
  re-audit above added further samples specifically inside the windows
  originally proposed as `target_only`, at finer granularity (every 2-5 s),
  to check specifically for the presence of any other visible person, not
  just for target separation.
- Existing tracker-ID annotation CSVs (`docs/data/annotations/`) were read
  for event timing, but never treated as physical ground truth -- Section C
  records, per sequence, whether that CSV's second-level timing is actually
  joinable to the raw bag chosen for physical annotation, which turned out
  to be true for only one of the four sequences (Section C.1).

## B. Canonical bag paths (verified, not assumed)

| Sequence | `source_bag_path` | `source_image_topic` | Frames | Duration | Cadence | Dimensions | Capture date |
|---|---|---|---|---|---|---|---|
| May hard re-entry | `bags/source/curated/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw` | `/camera/image_raw` | 974 | 67.86 s | ~14.4 fps | **640x640** | 2026-05-14 |
| June Seq01 (clean four-person) | `bags/source/curated/2026-06-19__12-48-17__source__2026-06-19__official__seq01__clean_four_person__image_raw` | `/camera/image_raw` | 1520 | 61.20 s | ~24.8 fps | 640x480 | 2026-06-19 |
| June Seq03 (crossing ambiguity) | `bags/source/curated/2026-06-19__12-55-58__source__2026-06-19__official__seq03__four_person_crossing_ambiguity__image_raw` | `/camera/image_raw` | 1931 | 83.87 s | ~23.0 fps | 640x480 | 2026-06-19 |
| June Seq04 (occlusion, no exit) | `bags/source/curated/2026-06-19__12-59-53__source__2026-06-19__official__seq04__four_person_occlusion_no_exit__image_raw` | `/camera/image_raw` | 2047 | 86.50 s | ~23.7 fps | 640x480 | 2026-06-19 |

`coordinate_convention` for all four: `source_pixels_historical_pre_p53`
(auto-resolved by the existing Milestone-3 resolver, date-based -- all four
predate Issue #53's 2026-07-22 contract closure). Same resolver, same
resolution path already exercised by the Milestone 3 test suite; not
re-implemented here.

**Two findings worth recording:**

1. **May's source frame is 640x640, not 640x480.** The frozen contract
   document's section F previously stated "the known 640x480 capture
   resolution already used and cross-checked by the completed #26/#30/#31
   evidence over these same sequences" for the May bag specifically. Direct
   inspection of the first `/camera/image_raw` message in the actual May bag
   (`sensor_msgs/msg/Image.width`/`.height`, via `rosbag2_py.SequentialReader`)
   shows `640x640`. June's three bags are genuinely 640x480 by the same
   direct check. **Corrected in `docs/issues/p1-10-improve-bbox-evaluation.md`
   section F as part of this corrective pass** (a per-sequence verified
   dimensions table replaces the old blanket claim): this is a factual
   provenance correction, not a schema or semantics change --
   `source_width`/`source_height` on every artifact were always read from
   the decoded frame's natural pixel dimensions (Milestone 3, section R),
   never from this prose, so no annotation behaviour changes as a result.
2. **June Seq01 has two candidate raw bags; only one shows the actual
   scenario.** `bag_inventory.md` lists two `raw_image_source` entries for
   Seq01: one at `12-38-13` (29.0 s, 759 frames) and one at `12-48-17`
   (61.2 s, 1520 frames). Direct visual inspection resolved this: the
   `12-38-13` bag's frames are plain ground/pavement with no people visible
   at any sampled instant (frame 0 and mid-sequence both show only ground --
   almost certainly a pre-flight/idle capture), while `12-48-17` clearly
   shows the four-person "clean_four_person" scenario at every sampled
   instant across its full duration. **`12-48-17` is the bag used
   throughout this plan and the table above; `12-38-13` is not a usable
   physical-reference source and should be left alone.** Seq03 and Seq04
   each have exactly one raw candidate in the inventory, no ambiguity there.

## C. Relationship to existing tracker-ID annotations

The existing interval CSVs under `docs/data/annotations/` were read for
event-timing guidance only, per section 6/7 of this milestone's brief. They
were **not** used as physical ground truth, and in three of the four cases
they are not even time-joinable to the raw bag chosen for physical
annotation:

### C.1 May -- CSV timing transfers directly (verified)

The split file's `dev_may_hard_reentry` replay bag filename
(`bags/reference/tim_good/2026-05-14__hard_reentry__bytetrack__tim_mars_v4_margin010__target_1/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_bytetrack__tim_mars__target_1__r2__...mcap`)
embeds the exact raw bag name used in Section B as its own prefix: it is a
tracker replay **of that same raw bag**, not an independent capture. Because
`t_s` in both the legacy CSV and the future physical reference is
bag-relative "seconds since first message," May's CSV event boundaries
(occlusion windows, the ID-switch instant) transfer directly onto the raw
bag's own timebase and are used as-is in Section E.1 below.
`deepsort_hard_reentry.csv`'s `target_label` column additionally records
`BLACK_SHIRT` for the physical target -- a real, repository-recorded
physical description, used as the proposed `selected_physical_target_label`
below (not invented).

### C.2 June Seq01/Seq03/Seq04 -- CSV timing does **not** transfer

Every June `full_pipeline` recording's `flight_metadata.txt` records
`perception_mode=integrated-camera` and an empty `dataset_bag_name` --
confirmed directly for all four June `full_pipeline` bags (Seq01, Seq02,
Seq03, Seq04), meaning every one of them is an independent **live** camera
capture, not a replay of any of the separately-recorded raw-only
`image_raw` bags used for physical annotation. Concretely:

- `seq01_bytetrack.csv`'s single row spans `0.0-122.34 s` against a bag
  (`...annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest`)
  that no longer exists on disk -- longer than the 61.2 s raw bag now
  available, confirming it is a different recording, not just a
  differently-processed view of the same one.
- `seq03_bytetrack.csv` and `seq04_bytetrack.csv` both reference the
  `12-57-48`/`13-01-36` `full_pipeline` bags directly, whose own duration
  (up to 95.7 s and at least 65.8 s respectively) again does not match the
  raw bags used here (83.87 s, 86.50 s).

These CSVs remain useful **qualitatively**: they confirm that
"crossing_ambiguity" and "occlusion_no_exit" are real, repeatedly-occurring
event types in these scenarios (multiple `occlusion_ambiguity`/
`id_switch_fragmentation` windows in Seq03; two genuine `target_absent`
tracker windows in Seq04), which is exactly the kind of region that
Section E below independently confirms through direct visual inspection of
the actual available raw bag. But their second-level timestamps are not
transplanted onto the region tables below -- those come from direct visual
sampling of the bags in Section B, per this milestone's explicit instruction
not to plan from CSV timestamps alone.

### C.3 Selected physical target label

| Sequence | `selected_physical_target_label` | Evidence |
|---|---|---|
| May | `black_shirt_person` | Repository-recorded: `deepsort_hard_reentry.csv`'s `target_label` column reads `BLACK_SHIRT` for every row. |
| Seq01 | `black_shirt_person` (**proposed, not repository-confirmed**) | No June CSV records a physical description (`CORRECT_TARGET` is generic). Visual inspection of all 7 sampled frames shows one consistent person in a black/dark t-shirt and light trousers, clearly distinguishable from the other three (lighter clothing) at every sampled instant. |
| Seq03 | `black_shirt_person` (**proposed, not repository-confirmed**) | Same visual basis as Seq01; same `june19_four_person_group_A` per the split file, so plausibly the same individual across the day, but this is an inference, not a repository fact. |
| Seq04 | `black_shirt_person` (**proposed, not repository-confirmed**) | Same visual basis as Seq01/Seq03. |

Per the instruction not to invent a label where evidence is ambiguous: the
three June proposals above are flagged explicitly as inspection-based
proposals, to be confirmed (or replaced) by the annotator at real
annotation time, not treated as frozen. May's label is the only one with
direct repository backing.

**Also worth noting for June sequences:** at several sampled instants (most
visibly in Seq04), a fifth person is visible who does not obviously belong
to the core four-person choreographed group (e.g. a bystander or crew
member near the court edge). Section G of the frozen contract requires
`distractors_complete` to box **every plausible competing physical person**,
not just the four "official" participants -- a visible fifth person counts
if a person-detector could plausibly attribute an output to them. The
workload estimate in Section F accounts for this by assuming a variable,
not fixed, distractor count per sample.

## D. Global annotation rules

Restating the frozen rules this plan operates under (no change to any of
them):

- `target_only`: asserts no other physical person could plausibly be
  confused with the controller-facing output at this instant.
  `distractor_bboxes_xyxy` must be empty. Used only where visual inspection
  directly supports it, never merely because a tracker ID looked stable.
- `distractors_complete`: asserts every plausible competing physical person
  visible at this instant has been boxed. Required whenever more than one
  person is genuinely close enough to be a candidate for the
  controller-facing output. `interpolate_from_previous` is illegal across or
  between `distractors_complete` samples (schema, section I) -- these must
  always be dense enough to stand on their own.
- `interpolate_from_previous = true`: legal only between two adjacent
  `present_scored`/`target_only` keyframes. Used inside
  `TARGET_ONLY_INTERPOLATABLE` regions only.
- `absent`: the target is not physically in frame. Boundary samples only
  (entry into absence, exit from absence) -- never filled with meaningless
  boxes.
- `present_reference_unavailable`: target is physically present but no
  trustworthy box can be drawn (near-total occlusion, motion blur). Boundary
  samples only, same as `absent`.
- Event anchors: every observed occlusion onset/offset, crossing
  onset/offset, re-entry instant, and abrupt motion/scale change gets a
  dedicated keyframe, in addition to whatever regular cadence already covers
  that instant -- never left to be implied purely by interpolation across a
  full keyframe interval.
- Tracker independence: `correct_target_track_id` and tracker-ID stability
  are navigation aids only. They never determine `identity_state`,
  `identity_context`, or which physical person is boxed. Section C.2 above
  is a direct, concrete instance of why this matters: three of the four
  sequences' own CSVs cannot even be time-joined to the bag being annotated,
  let alone trusted as ground truth.

**Keyframe-spacing convention used below** (not a fixed single interval,
per this milestone's brief):

- `TARGET_ONLY_INTERPOLATABLE`: 1.0 s baseline spacing (matches the
  suggested starting scale; motion in all four sequences is walking-pace,
  not running-pace, at every sampled instant).
- `DISTRACTORS_COMPLETE`: 0.5-1.0 s spacing depending on how dynamic the
  cluster is (denser where people are moving relative to each other, e.g.
  mid-crossing; sparser where a cluster is present but relatively static).
  No interpolation credit -- every sample in this regime is a fully manual
  target+distractors draw.
- Transition/event windows are folded into whichever regime's cadence
  already spans them (usually `DISTRACTORS_COMPLETE`) rather than counted a
  second time, except where a window is short enough (<1 s) that its own
  regular cadence would produce zero samples -- those get an explicit
  boundary pair instead.
- `absent` / `present_reference_unavailable`: 2 samples per episode (start,
  end), never densified.

## E. Per-sequence timeline regions

All region boundaries below come from direct visual inspection of the exact
bags in Section B (Section A's sampling method), except May's, which reuse
the CSV boundaries because Section C.1 established those transfer exactly.
Boundaries for the three June sequences are stated to the nearest sampled
instant and rounded to whole seconds for readability -- this is a workload
**plan**, not the annotation itself, so region edges will move a little once
an annotator works through every second directly; that is expected and
fine. Every region below is now `distractors_complete` -- see the
corrective re-audit note above -- with a stated **average distractor count
per sample**, since "one distractor box per sample" (the simplifying
assumption used in the original version of this plan) understated the
June sequences in particular, where all four people are typically
mutually visible at once.

### E.1 May hard re-entry (67.86 s, target = `black_shirt_person`)

A second person (`distractor_track_ids=2` in the legacy CSV, present in
nearly every row) is visible **immediately adjacent** to the target at
every sampled instant across the entire duration, including the opening
seconds -- re-audit samples at t=0, 3, 6, 9, 12, 15, 18, 21, 24 s (dense
sampling specifically inside the previously-proposed `target_only` window)
all show the two people standing side by side, both clearly resolvable and
equally prominent. There is no sub-interval in this sequence where the
target is not accompanied by at least one other clearly visible person.
Distractor count: 1 per sample throughout (the CSV's own
`distractor_track_ids` column records exactly one companion almost
everywhere; occasional distant third/fourth figures near the frame edge at
t≈17.4s and t≈66.9s are small and not consistently present, so are not
counted as a second guaranteed distractor, but a real annotator should
check them at those specific instants).

| Region | start_s | end_s | dur (s) | Regime | Avg distractors/sample | Reason |
|---|---:|---:|---:|---:|---|
| R1 | 0.00 | 24.77 | 24.77 | DISTRACTORS_COMPLETE | 1 | **Reclassified from TARGET_ONLY_INTERPOLATABLE.** Re-audit samples at t=0,3,6,9,12,15,18,21,24s all show the companion person immediately adjacent to the target, not merely "visible somewhere in frame" -- clearly a plausible alternative detection at every instant. |
| E1 | 24.77 | 25.47 | 0.70 | DISTRACTORS_COMPLETE (transition) | 1 | CSV `occlusion_ambiguity`. |
| R2 | 25.47 | 29.37 | 3.90 | DISTRACTORS_COMPLETE | 1 | Companion continuously nearby (distractor_track_ids=2). |
| E2 | 29.37 | 30.18 | 0.81 | DISTRACTORS_COMPLETE (transition) | 1 | CSV `occlusion_ambiguity`. |
| R3 | 30.18 | 33.93 | 3.75 | DISTRACTORS_COMPLETE | 1 | Same as R2. |
| E3 | 33.93 | 36.27 | 2.34 | DISTRACTORS_COMPLETE (transition, hard re-entry) | 1 | CSV `occlusion_ambiguity` spanning the tracker ID-switch instant (35.8s DeepSORT / 50.2s ByteTrack -- different per tracker, itself evidence the switch is a tracker artifact, not a physical event); visual sample at t≈34s shows the two people directly adjacent. |
| R4 | 36.27 | 40.03 | 3.76 | DISTRACTORS_COMPLETE | 1 | Same as R2. |
| E4 | 40.03 | 41.50 | 1.47 | DISTRACTORS_COMPLETE (transition) | 1 | CSV `occlusion_ambiguity`. |
| R5 | 41.50 | 49.64 | 8.14 | DISTRACTORS_COMPLETE | 1 | Visual sample at t≈48.7s shows both people close/adjacent. |
| E5 | 49.64 | 51.23 | 1.59 | DISTRACTORS_COMPLETE (transition) | 1 | CSV occlusion window + ByteTrack tracker handover (physical target continuous per the CSV's own 2026-07-27 visual-review note). |
| R6 | 51.23 | 55.07 | 3.84 | DISTRACTORS_COMPLETE | 1 | Same as R2. |
| E6 | 55.07 | 56.03 | 0.96 | DISTRACTORS_COMPLETE (transition) | 1 | CSV `occlusion_ambiguity`. |
| R7 | 56.03 | 58.16 | 2.13 | DISTRACTORS_COMPLETE | 1 | Same as R2. |
| E7 | 58.16 | 58.93 | 0.77 | DISTRACTORS_COMPLETE (transition) | 1 | CSV `occlusion_ambiguity`. |
| R8 | 58.93 | 67.70 | 8.77 | DISTRACTORS_COMPLETE | 1 | Visual sample at t≈66.9s shows up to 4 people visible (2 main + 2 distant); 1 counted as guaranteed, distant pair flagged for annotator check. |

### E.2 June Seq01 -- clean four-person (61.20 s, target = `black_shirt_person`, proposed)

**Reclassified in full.** The original version of this plan called this
entire sequence `target_only` because the 4 people are well spread across
the court and never cross paths. That is the wrong test: a fresh,
close look at all 7 original samples (t = 0, 8.1, 20.3, 30.5, 44.7, 54.7,
60.8 s) plus a further confirmation sample shows **all 4 people
simultaneously visible, individually resolvable, and reasonably sized** at
every single one of the 8 sampled instants spanning the full duration --
none of them is a background speck. Separation prevents a crossing/overlap
mix-up, but does not prevent a detector/controller from latching onto any
of the other 3 people instead of the target; that is exactly what
`distractors_complete` exists to cover. This is the sequence the milestone
brief specifically flagged as suspicious, and the closer look confirms the
suspicion was warranted.

| Region | start_s | end_s | dur (s) | Regime | Avg distractors/sample | Reason |
|---|---:|---:|---:|---:|---|
| R1 | 0.00 | 61.20 | 61.20 | DISTRACTORS_COMPLETE | 3 | **Reclassified from TARGET_ONLY_INTERPOLATABLE (entire region).** All 4 people simultaneously visible and individually resolvable at all 8 sampled instants across the full duration -- every other person is a plausible alternative detection throughout, not just during any single moment. |

No region in this sequence is `target_only`. This is the largest single
correction in this re-audit, both scientifically (this was the sequence
literally named "clean_four_person," and it is still not `target_only`)
and in workload terms (Section F).

### E.3 June Seq03 -- crossing ambiguity (83.87 s, target = `black_shirt_person`, proposed)

The originally-proposed 0-20s `target_only` opening did not survive
re-audit: dense re-sampling at t=0, 5, 10, 15, 20s shows two other people
already visible near the right edge of frame from the very first sampled
frame (t=0) onward, closing in on the target as the sequence progresses --
never absent, only more distant early on. Given the explicit instruction
to be conservative, and that these two people are part of the same
choreographed four-person scenario (not incidental background pedestrians)
and visibly converging rather than static, the opening is reclassified.

| Region | start_s | end_s | dur (s) | Regime | Avg distractors/sample | Reason |
|---|---:|---:|---:|---:|---|
| R1 | 0 | 20 | 20 | DISTRACTORS_COMPLETE | 2 | **Reclassified from TARGET_ONLY_INTERPOLATABLE.** Re-audit samples at t=0,5,10,15,20s all show 2 other people already visible near the frame edge, closing in over time -- not absent, just more distant early on; conservatively still a plausible alternative detection, not "reasonably irrelevant." |
| R2 | 20 | 45 | 25 | DISTRACTORS_COMPLETE | 3 | t≈34.8s: target and a second person directly adjacent/overlapping -- a genuine crossing; a 3rd/4th person also visible per the original sampling. CSV independently confirms an `occlusion_ambiguity`/`id_switch_fragmentation` cluster in this scenario type. |
| R3 | 45 | 60 | 15 | DISTRACTORS_COMPLETE | 3 | t≈52.1s: all 4 people visible simultaneously, moderate but real proximity. |
| R4 | 60 | 83.87 | 23.87 | DISTRACTORS_COMPLETE (denser) | 3 | t≈69.5s, t≈82.5s: all 4 people tightly clustered in the centre circle at both instants -- sustained, not momentary. |

### E.4 June Seq04 -- occlusion, no exit (86.50 s, target = `black_shirt_person`, proposed)

The originally-proposed 0-15s `target_only` opening also did not survive
re-audit: a fresh sample at t=2s (inside that window) shows **5 people
already tightly clustered together**, immediately adjacent to the target,
not spread out the way Seq01's opening is. The legacy CSV's own
`clean_visible` label for this span describes tracker behaviour (a track
was held without an ID switch), not physical isolation, and physical
evidence overrides it per the frozen rule.

| Region | start_s | end_s | dur (s) | Regime | Avg distractors/sample | Reason |
|---|---:|---:|---:|---:|---|
| R1 | 0 | 15 | 15 | DISTRACTORS_COMPLETE | 3 | **Reclassified from TARGET_ONLY_INTERPOLATABLE.** Re-audit sample at t=2s shows 5 people already tightly clustered, immediately adjacent to the target -- the legacy CSV's `clean_visible` label describes tracker-ID stability, not physical isolation. |
| R2 | 15 | 35 | 20 | DISTRACTORS_COMPLETE | 3 | t≈17.4s, t≈34.7s: cluster persists. |
| R3 | 35 | 60 | 25 | DISTRACTORS_COMPLETE + anticipated absence/unavailable episodes | 4 | t≈52.1s: heaviest cluster of all four sequences, near-total overlap of 5 people. The legacy CSV (different bag, not time-joinable, Section C.2) records two genuine `target_absent` tracker windows in this same scenario type; annotator should specifically check whether the target becomes genuinely `absent` or `present_reference_unavailable` for any sub-interval here -- **not confirmed by this milestone's sampling, flagged for verification at real-annotation time.** State-only samples (4, unchanged) remain budgeted for this. |
| R4 | 60 | 75 | 15 | DISTRACTORS_COMPLETE | 3 | t≈69.5s: spreading out again, but a closer foreground bystander adds a further plausible person. |
| R5 | 75 | 86.50 | 11.50 | DISTRACTORS_COMPLETE (denser) | 3 | t≈86.9s: clustered tightly again near the end. |

## F. Workload estimate

### F.1 Interpolation after the re-audit

**No region in any of the four sequences is used as `target_only` any
longer, so `interpolate_from_previous` is not used anywhere in this
revised plan.** There is consequently no boundary to "split" (Section 6 of
this corrective brief) -- there is no surviving `target_only` interval on
either side of a reclassified region to split in the first place. If real,
frame-by-frame annotation later confirms a genuinely isolated single-person
interval that this milestone's bounded sampling did not happen to catch
(none was confirmed by any sample taken, including the additional
re-audit sampling specifically aimed at finding one), `target_only` plus
interpolation could legitimately be used there, bounded by explicit event
anchors at its entry and exit -- but this plan does not assume one exists
pre-emptively, per the instruction not to artificially minimize the
workload.

### F.2 Method

Manual target and distractor boxes per sample = `ceil(region duration /
spacing)` x `(1 target + average distractors/sample)`, using the
per-region spacing and distractor-count columns in Section E (no
interpolation credit anywhere, per F.1). "Conservative upper bound" halves
the spacing used in the expected case (a more cautious annotator, or a
harder-than-sampled interior) while keeping the same distractor-count
assumptions. State-only `absent`/`reference_unavailable` samples are
boundary pairs, unaffected by spacing (Seq04 R3 only, unchanged at 4).

| Sequence | Frames | Duration | Expected target boxes | Expected distractor boxes | State-only samples | **Expected total actions** | **Conservative upper bound** |
|---|---:|---:|---:|---:|---:|---:|---:|
| May hard re-entry | 974 | 67.9 s | 75 | 75 | 0 | **150** | ~282 |
| June Seq01 | 1520 | 61.2 s | 82 | 246 | 0 | **328** | ~656 |
| June Seq03 | 1931 | 83.9 s | 116 | 328 | 0 | **444** | ~888 |
| June Seq04 | 2047 | 86.5 s | 128 | 434 | 4 | **566** | ~1128 |
| **Total** | **6472** | **299.5 s** | **401** | **1083** | **4** | **~1488** | **~2954** |

For scale: ~1488 expected manual actions against 6472 total source frames
is roughly **23%** of frames getting some manual treatment (roughly **46%**
in the conservative case). This is markedly higher than the original
version of this plan (~643 / ~1260), but it is important to be precise
about *why*: the number of manual **samples** (keyframes) barely changed --
401 target boxes now versus 380 before, a 5.5% increase -- because sparse
keyframing spacing (Section D) is essentially unchanged and still discards
92-95% of native frames per sequence (75/974 for May, 82/1520 for Seq01,
116/1931 for Seq03, 128/2047 for Seq04). What changed is that every one of
those samples now also carries its full distractor set (1083 distractor
boxes, versus 259 before) instead of the "0 distractors, interpolation
fills the gap" discount that `target_only` regions used to receive. The
workload roughly doubled not because sparse keyframing got less effective,
but because the reclassification removed a discount that should never have
applied in the first place.

## G. Answers to the specific workload questions

- **Is interpolation doing most of the workload reduction?** **No --
  interpolation contributes nothing now, because it is not used anywhere in
  this revised plan** (Section F.1). But that does not mean sparse
  keyframing stopped working: keyframe density is essentially unchanged
  from the original plan (401 target-box samples now versus 380 before,
  only +5.5%), and still discards 92-95% of native frames per sequence
  (Section F.2) -- sparse keyframing was, and remains, the dominant
  reduction mechanism throughout. What actually drove the ~2.3x increase in
  total actions is narrower and more specific than "less reduction overall":
  every sample now also carries its full distractor set, because the
  `target_only` regions that used to carry zero distractor cost did not
  survive the corrected test. Conflating "interpolation is no longer used"
  with "sparse sampling got less effective" would itself be an inaccurate
  reading of these numbers.
- **Is any sequence unexpectedly expensive?** No, and the ranking is
  unchanged: Seq04 (566 expected / ~1128 conservative) and Seq03 (444 /
  ~888) remain the two most expensive, for the same reason as before --
  "occlusion_no_exit" and "crossing_ambiguity" describe sustained
  multi-person proximity, now correctly reflected in *every* region of
  both sequences rather than just their second halves. Seq01 (328 / ~656)
  is no longer the cheapest sequence by a wide margin the way it looked in
  the original plan -- correcting its `target_only` misclassification was
  the single largest contributor to the overall increase -- though May
  (150 / ~282, single-companion for almost all of its duration) remains
  the least expensive of the four.

## H. UI recommendation (unchanged from the original plan, not acted on)

This section is carried over from the original Milestone 4A report,
unchanged in substance, and **not implemented in this corrective pass** --
the instruction for this pass was explicitly to freeze the corrected
workload first and decide on any UI follow-up afterward, separately. It is
retained here only for continuity; the higher, corrected workload estimate
in Section F if anything strengthens rather than weakens the case for it,
since there are now more distractor boxes to draw per sample across every
region, not fewer.

At ~1488 expected manual actions (up to ~2954 in the conservative case)
spread across four separate sessions, the current UI (mouse-driven frame
stepping via the existing slider, one box drawn and saved at a time) is
functionally sufficient -- nothing in this plan requires a UI change to be
*possible*. The dominant remaining friction at this volume is timeline
navigation, not box-drawing itself.

If a small pre-annotation follow-up is approved (a decision for after this
corrected plan is reviewed, not part of this pass):
- **keyboard next/previous-frame stepping** -- the single highest-value,
  lowest-risk candidate.
- **jump forward/back by N frames** -- secondary, same justification.

Still explicitly **not** recommended: "copy previous human bbox as
editable draft" -- not implemented, and per this pass's own instruction,
not to be added. With almost every region now `distractors_complete`,
people are moving relative to each other in essentially all of them, so a
copied previous box would usually need to be redrawn rather than lightly
nudged, further weakening the case for this specific feature versus the
original plan.

No UI code is changed in this milestone.

## I. What this milestone (and this corrective pass) does not do

No real physical-reference JSON was created. No sample was saved through
the annotation UI. No evaluator, schema, validator, or annotation UI code
was modified in either the original Milestone 4A pass or this corrective
re-audit -- the only code-adjacent change across both is the factual
provenance correction to `docs/issues/p1-10-improve-bbox-evaluation.md`
section F (Section B, finding 1), which does not alter any schema
semantics. No TIM-MARS configuration or runtime file was touched. No
existing tracker-ID annotation CSV was modified. No UI productivity
feature (Section H) was implemented. The region boundaries in Section E
are a planning estimate from a bounded number of sampled frames, not an
exhaustive per-frame review -- real annotation will refine, and may locally
contradict, the exact seconds above; after this corrective pass, the
`distractors_complete`-everywhere conclusion is expected to hold even if
individual region boundaries move.
