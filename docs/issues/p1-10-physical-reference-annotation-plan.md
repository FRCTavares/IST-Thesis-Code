# P1.10 Physical-reference annotation workload plan (Milestone 4A)

GitHub Issue: #25
Branch: `issue-25-improve-bbox-evaluation`
Companion to: `docs/issues/p1-10-improve-bbox-evaluation.md` (frozen `tim_physical_target_bbox_v1` contract, Milestones 1-3)

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
  at a time, not as a single composite contact sheet.
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
   document's section F states "the known 640x480 capture resolution
   already used and cross-checked by the completed #26/#30/#31 evidence
   over these same sequences" for the May bag specifically. Direct
   inspection of the first `/camera/image_raw` message in the actual May bag
   (this milestone) shows `640x640`. June's three bags are genuinely
   640x480. This does not block anything -- the UI already reads
   `source_width`/`source_height` from the decoded frame's natural pixel
   dimensions rather than from typed-in or assumed values (Milestone 3,
   section R), so a real annotation session would record the correct value
   regardless. It is flagged here because section F's prose is a factual
   claim that is now known to be wrong for May and should be corrected in a
   small follow-up **when Milestone 4B or later touches that section** --
   not in this milestone, per the instruction not to reopen M1-M3 semantics
   without a blocking defect, and this is not blocking.
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
bag's own timebase and are used as-is in Section D.1 below.
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
fine.

### E.1 May hard re-entry (67.86 s, target = `black_shirt_person`)

A second person (`distractor_track_ids=2` in the legacy CSV, present in
nearly every row) is visible near the target through most of the sequence,
which is why most of this sequence is `distractors_complete` rather than
`target_only`, despite being labelled "clean" in the tracker CSV's own
`event_type` column -- a direct instance of "tracker evidence and physical
evidence disagree, physical evidence wins" (Section 6 of the brief). Only
the first ~24.8 s, where the two people are clearly separated at both
sampled instants (t=0, t≈17.4 s), is treated as safely `target_only`.

| Region | start_s | end_s | dur (s) | Regime | Interp? | Distractors? | Reason |
|---|---:|---:|---:|---|---|---|---|
| R1 | 0.00 | 24.77 | 24.77 | TARGET_ONLY_INTERPOLATABLE | yes | no | Two people clearly separated at both sampled instants (t=0, t≈17.4s); CSV `clean_visible`. |
| E1 | 24.77 | 25.47 | 0.70 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV `occlusion_ambiguity`. |
| R2 | 25.47 | 29.37 | 3.90 | DISTRACTORS_COMPLETE | no | yes | Companion still nearby (distractor_track_ids=2 continuous); conservative call. |
| E2 | 29.37 | 30.18 | 0.81 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV `occlusion_ambiguity`. |
| R3 | 30.18 | 33.93 | 3.75 | DISTRACTORS_COMPLETE | no | yes | Same as R2. |
| E3 | 33.93 | 36.27 | 2.34 | DISTRACTORS_COMPLETE (transition, hard re-entry) | no | yes | CSV `occlusion_ambiguity` spanning the tracker ID-switch instant (35.8s DeepSORT / 50.2s ByteTrack -- different per tracker, itself evidence the switch is a tracker artifact, not a physical event); visual sample at t≈34s shows the two people directly adjacent. |
| R4 | 36.27 | 40.03 | 3.76 | DISTRACTORS_COMPLETE | no | yes | Same as R2. |
| E4 | 40.03 | 41.50 | 1.47 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV `occlusion_ambiguity`. |
| R5 | 41.50 | 49.64 | 8.14 | DISTRACTORS_COMPLETE | no | yes | Visual sample at t≈48.7s shows both people close/adjacent, distinguishable but near. |
| E5 | 49.64 | 51.23 | 1.59 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV occlusion window + ByteTrack tracker handover (physical target continuous per the CSV's own 2026-07-27 visual-review note). |
| R6 | 51.23 | 55.07 | 3.84 | DISTRACTORS_COMPLETE | no | yes | Same as R2. |
| E6 | 55.07 | 56.03 | 0.96 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV `occlusion_ambiguity`. |
| R7 | 56.03 | 58.16 | 2.13 | DISTRACTORS_COMPLETE | no | yes | Same as R2. |
| E7 | 58.16 | 58.93 | 0.77 | DISTRACTORS_COMPLETE (transition) | no | yes | CSV `occlusion_ambiguity`. |
| R8 | 58.93 | 67.70 | 8.77 | DISTRACTORS_COMPLETE | no | yes | Visual sample at t≈66.9s shows up to 4 people visible (2 main + 2 distant). |

### E.2 June Seq01 -- clean four-person (61.20 s, target = `black_shirt_person`, proposed)

All 7 sampled instants (t = 0, 8.1, 20.3, 30.5, 44.7, 54.7, 60.8 s), spread
across the entire duration, show 4 people well separated across the court
with the proposed target clearly distinguishable every time. No crossing or
occlusion observed at any sampled instant.

| Region | start_s | end_s | dur (s) | Regime | Interp? | Distractors? | Reason |
|---|---:|---:|---:|---|---|---|---|
| R1 | 0.00 | 61.20 | 61.20 | TARGET_ONLY_INTERPOLATABLE | yes | no | 7 samples spanning the full duration all show clear separation; matches the scenario's own "clean_four_person" name and the legacy CSV's single `clean_visible` label. |

This is the only region in any of the four sequences confidently classified
as `target_only` for its entire span. Because it is based on 7 discrete
samples rather than exhaustive review, a small number of extra spot-check
keyframes are still budgeted in Section F as a safety margin, not because
any specific event was observed.

### E.3 June Seq03 -- crossing ambiguity (83.87 s, target = `black_shirt_person`, proposed)

Genuinely different character across the duration: starts separated, builds
into a sustained multi-person cluster by the second half, matching the
scenario's own name.

| Region | start_s | end_s | dur (s) | Regime | Interp? | Distractors? | Reason |
|---|---:|---:|---:|---|---|---|---|
| R1 | 0 | 20 | 20 | TARGET_ONLY_INTERPOLATABLE | yes | no | t=0, t≈17.4s: target alone/dominant, other people at the frame edge, not plausibly confusable. |
| R2 | 20 | 45 | 25 | DISTRACTORS_COMPLETE | no | yes | t≈34.8s: target and a second person directly adjacent/overlapping -- a genuine crossing. CSV independently confirms an `occlusion_ambiguity`/`id_switch_fragmentation` cluster in this scenario type. |
| R3 | 45 | 60 | 15 | DISTRACTORS_COMPLETE | no | yes | t≈52.1s: all 4 people visible simultaneously, moderate but real proximity. |
| R4 | 60 | 83.87 | 23.87 | DISTRACTORS_COMPLETE (denser) | no | yes | t≈69.5s, t≈82.5s: all 4 people tightly clustered in the centre circle at both instants -- sustained, not momentary. |

### E.4 June Seq04 -- occlusion, no exit (86.50 s, target = `black_shirt_person`, proposed)

The densest of the four sequences: even the opening instant shows 5 people
already loosely clustered (not spread out the way Seq01 is), and the
cluster becomes near-total by the midpoint.

| Region | start_s | end_s | dur (s) | Regime | Interp? | Distractors? | Reason |
|---|---:|---:|---:|---|---|---|---|
| R1 | 0 | 15 | 15 | TARGET_ONLY_INTERPOLATABLE | yes | no | Matches the legacy CSV's own `clean_visible` label for its opening portion; target individually distinguishable at t=0 despite 5 people being in frame. |
| R2 | 15 | 35 | 20 | DISTRACTORS_COMPLETE | no | yes | t≈17.4s, t≈34.7s: cluster persists; conservative call given persistent multi-person proximity even though the (non-time-joinable) legacy CSV calls this whole span `clean_visible`. |
| R3 | 35 | 60 | 25 | DISTRACTORS_COMPLETE + anticipated absence/unavailable episodes | no | yes | t≈52.1s: heaviest cluster of all four sequences, near-total overlap of 5 people. The legacy CSV (different bag, not time-joinable, Section C.2) records two genuine `target_absent` tracker windows in this same scenario type; annotator should specifically check whether the target becomes genuinely `absent` or `present_reference_unavailable` for any sub-interval here -- **not confirmed by this milestone's sampling, flagged for verification at real-annotation time.** |
| R4 | 60 | 75 | 15 | DISTRACTORS_COMPLETE | no | yes | t≈69.5s: spreading out again, but a closer foreground bystander adds a 5th/6th plausible person. |
| R5 | 75 | 86.50 | 11.50 | DISTRACTORS_COMPLETE (denser) | no | yes | t≈86.9s: clustered tightly again near the end. |

## F. Workload estimate

Method: manual target boxes = ceil(region duration / spacing) in
`TARGET_ONLY_INTERPOLATABLE` regions (0 distractor boxes, interpolation
fills the gaps); manual target **and** distractor boxes per sample in
`DISTRACTORS_COMPLETE` regions (no interpolation credit). "Conservative
upper bound" halves the spacing used in the expected case (i.e. assumes a
more cautious annotator or a harder-than-sampled interior); state-only
`absent`/`reference_unavailable` samples are boundary pairs, unaffected by
spacing.

| Sequence | Frames | Duration | Expected target boxes | Expected distractor boxes | State-only samples | **Expected total actions** | **Conservative upper bound** |
|---|---:|---:|---:|---:|---:|---:|---:|
| May hard re-entry | 974 | 67.9 s | 75 | 50 | 0 | **125** | ~230 |
| June Seq01 | 1520 | 61.2 s | 61 | 0 | 0 | **61** | ~120 |
| June Seq03 | 1931 | 83.9 s | 116 | 96 | 0 | **212** | ~420 |
| June Seq04 | 2047 | 86.5 s | 128 | 113 | 4 | **245** | ~490 |
| **Total** | **6472** | **299.5 s** | **380** | **259** | **4** | **~643** | **~1260** |

For scale: 643 expected manual actions against 6472 total source frames is
roughly **10%** of frames getting any manual treatment at all (roughly
**19%** even in the conservative case) -- solidly in the "low hundreds, not
thousands" band this milestone asked to confirm, not remotely close to one
box per frame for any sequence.

## G. Answers to the specific workload questions

- **Is interpolation doing most of the workload reduction?** Yes, and
  decisively: if every one of the 6472 source frames needed a manual target
  box (the naive alternative), the total would be an order of magnitude
  higher than the ~380 target boxes this plan proposes across all four
  sequences combined -- a ~94% reduction on the target side alone, entirely
  from sparse keyframing plus `interpolate_from_previous`, before counting
  the `distractors_complete` regions where interpolation is legitimately
  disallowed by the frozen schema.
- **Is any sequence unexpectedly expensive?** No. Seq04 (245 expected / ~490
  conservative) and Seq03 (212 / ~420) are the two most expensive, and both
  are expensive for the reason their own names advertise --
  "occlusion_no_exit" and "crossing_ambiguity" are literally descriptions of
  sustained multi-person proximity, confirmed independently by both visual
  inspection and (qualitatively) their legacy CSVs. Seq01 ("clean") is the
  cheapest, also exactly as its name would suggest. Nothing here surprised
  the plan.

## H. UI recommendation

**Worth one small follow-up before real annotation, not urgent enough to
block starting it.** At ~643 expected manual samples (up to ~1260 in the
conservative case) spread across four separate sessions, the current UI
(mouse-driven frame stepping via the existing slider, one box drawn and
saved at a time) is functionally sufficient -- nothing in this plan requires
a UI change to be *possible*. But the dominant remaining friction at this
volume is timeline navigation, not box-drawing itself: an annotator working
through ~15-50 keyframes per region, region after region, will spend a
disproportionate share of time locating the *next* intended keyframe on the
slider.

Recommended, if a small pre-annotation follow-up is approved:
- **keyboard next/previous-frame stepping** -- the single highest-value,
  lowest-risk addition given the above.
- **jump forward/back by N frames** -- secondary, same justification.

Explicitly **not** recommended for now: "copy previous human bbox as
editable draft." Section 11's constraint (previous HUMAN annotation only,
never auto-saved, never carrying tracker/detector geometry, never silent
across frames) is achievable, but in every `DISTRACTORS_COMPLETE` region in
this plan -- which is most of the expensive part of the workload -- people
are actively moving relative to each other, so a copied previous box would
usually need to be redrawn anyway rather than lightly nudged; the feature's
main payoff would land in `TARGET_ONLY_INTERPOLATABLE` regions, which are
already the cheapest part of the workload. Revisit only if real annotation
turns out slower than this plan expects.

No UI code is changed in this milestone.

## I. What this milestone does not do

No real physical-reference JSON was created. No sample was saved through
the annotation UI. No evaluator, schema, validator, or annotation UI code
was modified. No TIM-MARS configuration or runtime file was touched. No
existing tracker-ID annotation CSV was modified. The region boundaries in
Section E are a planning estimate from a bounded number of sampled frames,
not an exhaustive per-frame review -- real annotation will refine, and may
locally contradict, the exact seconds above; the regime classifications and
overall workload order-of-magnitude are expected to hold.
