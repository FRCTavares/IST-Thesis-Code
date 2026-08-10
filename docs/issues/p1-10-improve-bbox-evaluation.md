# P1.10 Improve bbox evaluation

GitHub Issue: #25
Branch: `issue-25-improve-bbox-evaluation`
Baseline: `49744968a8c8189a83add20740c3f688a95fe21a` (main, Issue #54 merged)

## A. Purpose

The existing selected-target evaluators
(`tools/analysis/evaluate_tim_target_bbox_correctness.py`,
`tools/analysis/tim_evaluation.py` /
`tools/analysis/evaluate_tim_target_correctness.py`) locate their reference
bbox via

```
annotation says correct_target_track_id = N
          -> evaluator looks up track N in /tracks at time t
          -> that track's bbox becomes "the target"
```

`correct_target_track_id` is a tracker-assigned integer. Tracker IDs are
**temporary implementation labels**, not physical identities: two runs of
the same physical sequence through different tracker backends (or a
regenerated/reconfigured run of the same backend) assign different ID
numbers to the same person, and IDs can be reassigned to a *different*
physical person mid-run without the evaluator being able to tell. The
repository already carries direct evidence of the operational cost of
this: `docs/data/annotations/may_hard_reentry/` holds eight separate CSVs
for one physical scenario -- one per tracker backend -- because
`correct_target_track_id` differs per backend, and
`deepsort_hard_reentry.csv`'s own notes record a human manually
re-deriving "id=1 before 35.800s, id=69 after" by inspecting a visual UI.
`docs/results/selected_target_tracking/p028_component_ablation_development/README.md`
already documents this as a known limitation of a published result ("can
be conservative when the same physical person is fragmented into a new
tracker ID").

The corrected relation is

```
selected physical person (frozen at operator selection)
          -> independent physical-reference annotation (this contract)
          -> compared against controller-facing output, whatever tracker
             ID that output currently carries
```

The physical-reference annotation is defined once per source sequence and
is never re-derived when a tracker, its parameters, or its internal ID
numbering changes.

## B. Version

Contract name: **`tim_physical_target_bbox_v1`**. `schema_version: 1`
inside every artifact. The evaluator that will consume this (a later,
not-yet-implemented milestone) must record this string and version number
in its output, matching the existing `tim_mars_source_pixels_resize_v1`/
`tim_mars_split_v1` naming convention already used elsewhere in
`docs/data/` and `docs/algorithm/`.

## C. Source identity

Each physical-reference artifact is one JSON file, one per source
sequence, stored under `docs/data/physical_target_references/` (a new
sibling of `docs/data/annotations/`, added to `docs/data/README.md`).
JSON, not CSV, because the artifact is a provenance header plus a list of
structured per-keyframe records (bbox, state, optional distractor list) --
shaped like `docs/data/splits/tim_mars_split_v1.json`, not like the flat
interval CSVs.

**No file under `docs/data/annotations/` is modified, renamed, or
reinterpreted by this contract.** The existing tracker-specific CSVs
remain historical evidence in their original schema and location.

Top-level provenance fields (all required unless noted):

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | int | Must equal `1`. |
| `contract_version` | string | Must equal `"tim_physical_target_bbox_v1"`. |
| `sequence_id` | string | Matches the existing split/catalogue sequence identifiers where one exists (e.g. `dev_may_hard_reentry`, `dev_june_seq03`), for cross-reference -- not a requirement that a split entry exists yet. |
| `source_bag_name` | string | Bag directory name. |
| `source_bag_path` | string | Repo-relative path to the **raw-image/source** bag (e.g. the `raw_image_source`/`curated` bags identified in the audit), never a tracker-output replay bag. |
| `source_image_topic` | string | e.g. `/camera/image_raw`. |
| `source_width`, `source_height` | int > 0 | Source frame pixel dimensions. |
| `coordinate_convention` | enum: `source_pixels_p53_contract` \| `source_pixels_historical_pre_p53` | See section F. |
| `coordinate_convention_evidence` | string | Required when convention is the historical variant; must cite the concrete evidence (see F). |
| `selected_physical_target_label` | string | A human-assigned, non-numeric identity, e.g. `"black_shirt_person"`. **Never a tracker ID.** The validator rejects a value that parses as a bare integer (a structural proxy for "someone typed a track ID here"). |
| `annotator` | string | Free text. |
| `created_date` | string, `YYYY-MM-DD` | |
| `notes` | string, optional | |

## D. Timebase

`t_s` on every sample is defined **identically** to the existing
evaluators' bag-relative timebase: seconds elapsed since the first message
read from the bag by `rosbag2_py.SequentialReader`, i.e.
`(message_timestamp_ns - first_message_timestamp_ns) / 1e9`. This is the
same convention as `start_s`/`end_s` in the existing tracker-specific
interval CSVs, so the two artifact families stay time-joinable for manual
cross-checking without any conversion.

- `t_s` must be finite and `>= 0.0`.
- `samples` must be sorted by `t_s`, strictly increasing (no duplicate or
  non-monotonic timestamps -- rejected, not silently reordered).
- No wall-clock or header-time variant is supported in v1. A future
  version may add one; it would be a new `contract_version`, not a
  variant field on this one.
- Join to `/tracks` / selected-target output timebases, and any
  tolerance/interpolation *at evaluation time* (as opposed to the
  keyframe interpolation defined in section I, which is about deriving a
  reference between two annotated keyframes) is evaluator-refactor scope,
  not this schema's concern beyond guaranteeing a shared, unambiguous
  clock to join against.

## E. Bbox coordinate format

Bboxes are stored as `[x1, y1, x2, y2]` (xyxy), floating point, in
**source-image pixel coordinates** -- matching
`tools/analysis/external_target_initialization.py`'s `BBoxXYXY`/
`bbox_iou`, which the validator imports and reuses rather than
duplicating. This is a different serialized shape from the existing bbox
evaluator's `cx,cy,w,h` convention; a future evaluator converts as needed,
but the stored annotation format is unambiguous and singular -- v1 does
not support multiple representations.

- Origin `(0, 0)` at the top-left corner; `x` increases rightward, `y`
  increases downward (the OpenCV/image-array convention already used
  throughout `thesis_bringup.perception.preprocessing.ImageTransform` and
  `tools/bag_annotation_ui/tim_ui_drawing.py`).
- `x1, y1, x2, y2` all finite.
- Strictly positive area required: `x2 > x1` and `y2 > y1` (zero/negative
  width or height rejected).
- Bounds: `0 <= x1 < x2 <= source_width` and `0 <= y1 < y2 <= source_height`.
  Out-of-bounds boxes are **rejected**, not silently clipped -- if the
  real target extends past the visible frame edge, the correct annotation
  is `present_reference_unavailable` (section G), not a guessed/clipped
  box.

## F. Historical May/June coordinate provenance

Verified directly, not assumed: the May hard-reentry source bag
(`bags/source/curated/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw`,
captured 2026-05-14) contains `/camera/image_raw`
(`sensor_msgs/msg/Image`, 974 messages) and `/detections`
(`vision_msgs/msg/Detection2DArray`). Its first `/detections` message
carries `header.frame_id = 'frame_103'` -- **no**
`tim_mars_source_pixels_resize_v1;...` contract string. Issue #53's
contract closed 2026-07-22, more than two months after this capture:
**this bag is historical and predates the formal contract header**. The
June sequences (captured 2026-06-19, per
`docs/data/catalogue/bag_inventory.md`) also predate #53's closure and
must be treated the same way unless a per-sequence check on that specific
bag shows otherwise.

This contract does **not** fabricate a modern header into these bags.
`coordinate_convention` for both must be set to
`source_pixels_historical_pre_p53`, with `coordinate_convention_evidence`
recording: the direct header inspection above (or the equivalent for the
specific bag being annotated), the source frame's own actual pixel
dimensions as read directly from the bag being annotated, and an explicit
statement that the frame is interpreted as plain source-image pixels (no
letterbox padding, matching the anisotropic-resize contract's own geometry
even though this bag predates the header that would say so explicitly).

**Corrected 2026-08-10 (Issue #25 Milestone 4A):** an earlier version of
this section generalised a single "known 640x480 capture resolution...
cross-checked by the completed #26/#30/#31 evidence over these same
sequences" to both May and June without checking May's own bag directly.
Direct inspection of the first `/camera/image_raw` message
(`sensor_msgs/msg/Image.width`/`.height`) in each of the four canonical
raw source bags, via `rosbag2_py.SequentialReader`, establishes:

| Sequence | Verified `width x height` |
|---|---|
| May hard-reentry (`2026-05-14__11-03-26__...raw`) | **640 x 640** |
| June Seq01 (`...12-48-17__...seq01...image_raw`) | 640 x 480 |
| June Seq03 (`...12-55-58__...seq03...image_raw`) | 640 x 480 |
| June Seq04 (`...12-59-53__...seq04...image_raw`) | 640 x 480 |

The June figure was correct; the May figure was not -- May's own capture
was square, not 4:3. This does not change any schema semantics:
`source_width`/`source_height` on every artifact are, and always were,
read from the annotated frame's own decoded pixel dimensions (section C;
enforced in the UI per section R, "read directly from the decoded frame's
natural pixel dimensions, never typed by hand"), never from this
document's prose. The correction here is to the provenance narrative only,
so a reader of this section does not carry a wrong assumption about May
into a manual calculation or a hand-written artifact.

## G. Physical target state

**Corrected after review of the first version of this contract**, which
conflated two independent questions -- "does a trustworthy reference
bbox exist" and "how confident is the geometric identity match" -- into
one `identity_state` axis (`present_scored` vs `present_ambiguous`), and
let a Stage A IoU threshold decide identity, which silently turned poor
*localisation* into a *wrong-person*/unscored verdict. The corrected
schema separates these into two independent fields.

**Reference availability -- `identity_state`** (whether a trustworthy
`target_bbox_xyxy` exists at all):

| State | Bbox required? | Meaning |
|---|---|---|
| `present_scored` | `target_bbox_xyxy` required | Physically visible and a trustworthy reference bbox can be drawn. Says nothing about whether a nearby person could be confused with the output -- that is `identity_context`, below. |
| `present_reference_unavailable` | none allowed | Physically visible in principle, but no reliable bbox can be drawn (near-total occlusion, motion blur, or any case where the annotator cannot commit to a specific box). Unscored, not zero-IoU, not absent. |
| `absent` | none allowed | Not physically present in the source frame. Not a localisation failure; excluded from the localisation-scored denominator entirely. |

There is no separate `present_ambiguous` reference state in v1: it was
removed because its only job -- flagging a contested instant -- is now
carried, more precisely, by `identity_context`.

**Competitive context -- `identity_context`** (required on every
`present_scored` sample, forbidden otherwise): an explicit **completeness
assertion** about competing physical identities at this instant, never
inferred from whatever happens to be in `distractor_bboxes_xyxy`.

| Context | `distractor_bboxes_xyxy` | Meaning |
|---|---|---|
| `target_only` | must be empty | The annotator asserts **no other physical person could plausibly be confused with the controller-facing output** at this instant. Stage A then attributes *any* output to the target regardless of its IoU -- see section J. This is what lets a badly localised but genuinely target-attributed output reach Stage B instead of being misclassified. |
| `distractors_complete` | must contain at least one box | The annotator asserts **every plausible competing physical person visible at this instant has been boxed**. Stage A resolves identity by relative comparison against exactly these references -- see section J. |

An empty `distractor_bboxes_xyxy` can therefore only ever mean "asserted
`target_only`"; it can never mean "distractors were not annotated". The
validator enforces this structurally (`distractors_complete` requires
`>= 1` distractor box; `target_only` requires zero) -- see section 4.

Explicitly, per this issue's constraints:

```
absent != unscored (present_reference_unavailable)
unscored (present_reference_unavailable) != identity_unresolved (a Stage A
    attribution outcome, section J -- the reference existed and was
    usable, but geometry alone could not resolve who the output belongs to)
identity_unresolved != wrong_person (attribution to a different
    recorded physical person, never a synonym for "could not decide")
wrong_person != poor localisation of the correct person (section J/K)
```

`distractor_bboxes_xyxy` (list of `[x1,y1,x2,y2]`, same format/bounds
rules as `target_bbox_xyxy`) is only present on `present_scored` samples,
governed by `identity_context` above; it must be empty/omitted on
`present_reference_unavailable` and `absent`. Each distractor box
represents one other physically distinct visible person at that instant
-- never a tracker ID, never the target itself.

No partial/heavy occlusion sub-taxonomy is added: the two questions that
matter operationally are already separated (`identity_state`: can I draw
a trustworthy box at all; `identity_context`: could that box be confused
with someone else), and multiplying occlusion categories further is not
required by the four canonical sequences audited.

## H. Occlusion bbox policy

When a valid box is drawn (`present_scored`, any `identity_context`), it
encloses the **visible pixels of the person only** -- never an inferred
full-body extent under occlusion. This matches the convention already
implicit in the existing detector/tracker pipeline (Hailo person-detector
boxes are visible-extent boxes, not amodal/completion boxes), so the
physical reference stays comparable to what the system can actually be
expected to output. If visible extent is too fragmented or too small to
draw a box that is still recognisably "this person and not noise", use
`present_reference_unavailable` instead of forcing a box.

## I. Sampling / keyframes / interpolation

Physical references are **sparse keyframes**, not every source frame --
matching the existing interval-annotation convention's practicality, and
because per-frame annotation of four sequences is not required to satisfy
the issue. Every sample carries a required boolean field
`interpolate_from_previous`:

- `false` (the safe default -- must be stated explicitly, never implied):
  no reference exists between the previous sample and this one; an
  evaluator must not synthesise one.
- `true`: only legal when **both** this sample and the immediately
  preceding sample in the array have
  `identity_state == "present_scored"` **and**
  `identity_context == "target_only"`. The validator rejects `true` on
  the first sample (no predecessor), and rejects it whenever either
  endpoint fails that check -- concretely enforcing every one of:
  - no interpolation through `absent`;
  - no interpolation through `present_reference_unavailable`;
  - no interpolation across (or between) a `distractors_complete`
    instant, even if both surrounding keyframes are `present_scored` --
    distractor geometry cannot be safely linearly interpolated, and
    `distractors_complete` exists precisely to mark an instant that
    needs explicit, not synthesised, evidence;
  - no interpolation across a discontinuous re-entry unless the
    annotator explicitly re-asserts `present_scored`/`target_only` on
    both sides *and* sets the flag -- a hard cut the annotator does not
    want bridged is handled simply by leaving the flag `false`, which is
    also the default an annotator gets by doing nothing.
  When `true`, the evaluator (later milestone) may linearly interpolate
  `target_bbox_xyxy` between the two keyframes for output timestamps that
  fall strictly between them. Interpolation must never be extrapolated
  past the last keyframe or before the first.
- An interpolated reference must never be produced outside
  `[0, source_width] x [0, source_height]`; because both endpoints are
  already bounds-validated and linear interpolation of two in-bounds
  boxes is itself always in-bounds, this is a property of the
  interpolation rule rather than a separate runtime check.

## J. Identity attribution versus localisation quality

**Corrected after review.** The first version of this section made a
minimum target-IoU (`identity_iou_threshold`) a *prerequisite* for
Stage A identity correctness, even in the no-distractor case. That was
scientifically wrong: it meant a controller-facing output that genuinely
belonged to the selected physical person, but was badly localised (e.g.
target IoU 0.25 against a 0.5 threshold), would have been classified an
*identity* failure and its poor IoU excluded from Stage B -- both turning
poor localisation into a fabricated identity error, and biasing Stage B
upward by censoring exactly the worst-localised target-attributed
samples out of the statistics meant to measure localisation quality.

The corrected principle, frozen here:

> Stage A physical-identity attribution must not impose a minimum
> localisation-quality threshold that censors poor target localisation
> from Stage B. `wrong_person` requires evidence that the output is
> attributable to a *different* annotated physical person -- failure to
> obtain good overlap with the selected target alone is not evidence of
> wrong identity.

Two strictly separate stages, using the same `bbox_iou` primitive for
different purposes and never feeding Stage B's numbers back into Stage A:

- **Stage A resolves WHICH annotated physical reference the output
  belongs to** -- identity attribution, not quality.
- **Stage B measures HOW ACCURATELY a target-attributed output localises
  the target** -- computed only after, and never influencing, Stage A's
  verdict.

**Stage A outcomes** (`tools/analysis/physical_target_reference.py`):

| Outcome | Meaning |
|---|---|
| `identity_target` | The output is attributed to the selected physical person. Says nothing about localisation quality -- see Stage B. |
| `wrong_person` | The output is attributed to a *different*, specifically recorded physical person. Never used for poor target IoU, large centre error, a missing reference, an unresolved tie, no output, or target absence -- those are separate outcomes (section N). |
| `identity_unresolved` | A target reference existed and was usable, but geometry alone could not defensibly attribute the output to the target or to any specific distractor (a tie, including zero overlap with everyone). Not a synonym for `wrong_person`, and not a synonym for `present_reference_unavailable` (section G) -- the reference was available; only the *attribution* is unresolved. |

Reference-availability outcomes (`absent`, `present_reference_unavailable`,
no controller-facing output) are handled entirely upstream of Stage A,
by the caller inspecting `identity_state` and output validity directly --
`classify_identity_stage_a` is only invoked for a `present_scored`
sample that also has a valid controller-facing output to classify.

**Stage A algorithm**, per `identity_context` (section G):

1. **`target_only`** -- no plausible competing physical person was
   recorded for this instant. Any valid controller-facing output is
   attributed to the target: **always `identity_target`**, independent
   of `bbox_iou(output, target)`. There is no absolute IoU threshold
   anywhere in this branch, by construction (the function has no such
   parameter) -- a target-attributed output with IoU 0.02 and a
   target-attributed output with IoU 0.95 both return `identity_target`
   here; only Stage B distinguishes them.
2. **`distractors_complete`** -- attribution is the *relative* winner of
   `target_iou = bbox_iou(output, target)` versus
   `best_distractor_iou = max(bbox_iou(output, d) for d in distractors)`:
   - `target_iou` strictly greater (beyond a `1e-9` floating-point tie
     guard, not a scientific margin) -> `identity_target`, **regardless
     of the absolute value** -- a target that wins 0.08 to 0.02 is still
     the target, and its 0.08 IoU still reaches Stage B;
   - `best_distractor_iou` strictly greater -> `wrong_person`;
   - a tie (including the all-zero case, where the output overlaps
     nobody) -> `identity_unresolved`. This is the same best-match
     principle already proven in
     `external_target_initialization.match_frame`
     (`best_iou`/`second_iou`/`margin`), generalised from anonymous
     tracker candidates to named physical references, but used purely
     for *relative* attribution -- never gated by an absolute pass/fail
     value on either side.

This is the concrete mechanism that satisfies both halves of the
non-negotiable rule: (a) a wrong physical person cannot become "correct"
merely because it overlaps the target reference (the crossing test in
section 5 -- distractor beats target on relative comparison ->
`wrong_person`, no threshold involved); and (b) a badly localised but
genuinely target-attributed output cannot become a fabricated identity
failure (the `target_only` branch, and the `distractors_complete`
relative-win branch, both attribute low-IoU target outputs to the target
whenever the geometry genuinely still favours the target over every
recorded alternative).

**No absolute IoU threshold remains anywhere in `classify_identity_stage_a`.**
The only numeric constant is `_TIE_EPSILON = 1e-9`, a floating-point
equality guard, not a localisation-quality bar.

**Stage B -- localisation quality**, computed for every sample Stage A
returned `identity_target` on, **without exception and without any
further quality gate**: `bbox_iou(output_bbox, target_bbox)` and centre
error (section M) against the target box. A target-attributed sample
with IoU 0.02 contributes IoU 0.02 (and a correspondingly large centre
error) to Stage B's statistics; it is not filtered, clipped, or excluded.
This is what "Stage B measures how well the target-attributed output
localises the target" means concretely: the measurement is honest about
bad localisation instead of hiding it behind a manufactured identity
verdict.

A future evaluator may *additionally* report a binary "good localisation"
summary bucket (e.g. IoU >= 0.5) purely as a descriptive statistic over
the Stage B numbers -- that threshold, if used at all, is
Stage-B-internal, evaluator-calibration work for the next milestone, and
must never be allowed to influence which samples are *members* of the
Stage B population in the first place.

## K. Localisation scoring subset

A sample contributes to the localisation-scored duration/count iff **all**
of the following hold:

1. the selected physical target's reference state is `present_scored`
   for that sample (exactly or via valid interpolation);
2. a valid `target_bbox_xyxy` is available (exact or interpolated);
3. a controller-facing output bbox exists and is valid (non-zero ID,
   finite, positive width/height) at that sample;
4. Stage A (section J) attributed that sample `identity_target`.

Condition 4 is a **membership** test, not a **quality** test: it asks
only whether the output belongs to the target, never how well it
localises the target. A sample satisfying (1)-(4) enters Stage B with
whatever IoU/centre-error it actually has, including near-zero values --
see section J's Stage B paragraph. Any sample failing (1)-(3) falls into
`target_absent_duration_s`/`reference_unavailable_duration_s`/
`lost_duration_s` per section N, never into the localisation numerator or
denominator. A sample failing only (4) (`wrong_person` or
`identity_unresolved`) contributes to `wrong_target_duration_s` or
`identity_unresolved_duration_s` respectively, never to localisation
statistics -- geometry computed on a wrong-person or unresolved sample is
not "worse localisation", it does not exist as a localisation sample at
all.

## L. IoU

`IoU = intersection_area(output_bbox, target_bbox) / union_area(...)`,
computed via `external_target_initialization.bbox_iou` (xyxy, reused not
duplicated), range `[0, 1]`.

Aggregation, once the evaluator-refactor milestone implements reporting:
- **primary**: duration-weighted mean over the localisation-scored subset
  (matching the existing evaluator family's `dt`-weighted convention, so
  numbers remain comparable in kind to today's duration-based ratios);
- **secondary/diagnostic**: unweighted sample mean, median, and p90,
  reported alongside, not in place of, the duration-weighted primary.

A single binary "IoU >= threshold" pass/fail, as the current bbox
evaluator reports today, is not sufficient on its own going forward --
the numeric aggregate value must be reported, per the issue's explicit
requirement.

## M. Centre error

`centre_error_px = euclidean_distance(centre(output_bbox), centre(target_bbox))`
in raw source-image pixels, **and** the same distance normalised by the
target box's height:
`centre_error_norm = centre_error_px / target_bbox_height`
(matching the existing `centre_distance_ratio` convention already in
`evaluate_tim_target_bbox_correctness.py`, for continuity with thresholds
already in use elsewhere). Both are reported; neither replaces the other.
Same duration-weighted-primary / sample-mean-secondary aggregation as
section L.

## N. Explicit duration buckets

The future evaluator reports, at minimum, these **mutually exclusive**
totals covering the full evaluated span:

- `correct_target_duration_s` -- Stage A `identity_target`.
- `wrong_target_duration_s` -- Stage A `wrong_person`: the output is
  attributed to a *different*, specifically recorded physical person.
  Never populated by poor target IoU, large centre error, a missing
  reference, an unresolved tie, no output, or target absence.
- `identity_unresolved_duration_s` -- Stage A `identity_unresolved`: a
  target reference was available and an output existed, but geometry
  could not defensibly attribute it to the target or to any specific
  distractor (a tie, including zero overlap with everyone).
- `lost_duration_s` -- reference available/scorable (`present_scored`,
  either context) but no valid output published.
- `target_absent_duration_s` -- reference state `absent`.
- `reference_unavailable_duration_s` -- reference state
  `present_reference_unavailable`, regardless of what the output did.

Per the required distinction between the two reasons a sample can be
excluded from identity/localisation statistics:
`reference_unavailable_duration_s` means **no trustworthy reference bbox
existed to compare against at all** (an annotation-side gap);
`identity_unresolved_duration_s` means **a reference existed and a
comparison was attempted, but the geometry itself did not defensibly
resolve who the output belongs to** (an attribution-side indeterminacy).
Both are excluded from `correct_target_duration_s`/`wrong_target_duration_s`
and from Stage B's localisation statistics, but they are never merged
into one number -- a report may total them for a headline "unscored"
figure, but the per-reason breakdown must remain available.

`localisation_scored_duration_s` is **conditional, not a seventh disjoint
bucket**: it is the portion of `correct_target_duration_s` that also
satisfies section K's four conditions (in practice, all of
`correct_target_duration_s` by construction, since `identity_target`
already implies (1)-(4) -- it is named separately only so a future report
can state the localisation-statistics denominator explicitly rather than
leaving it implicit). It is **not** further filtered by IoU or
centre-error quality -- section J/K.

## O. Regenerated tracker-ID invariance (formal invariant)

Given two full-pipeline runs `R1`, `R2` over the same physical source
sequence, differing only in tracker backend, tracker parameters, or
regenerated internal ID numbering (not in the physical camera content),
the physical-reference annotation file for that sequence is used
**unmodified** for both. Applying the Stage A / Stage B procedure from
section J/K to `R1`'s and `R2`'s `/target` and `/target_memory_mars`
streams must be computable without editing the physical-reference file at
all. Any difference in scored outcomes between `R1` and `R2` must be
attributable only to genuine behavioural differences between the runs,
never to a need to re-map identity labels. This receives a focused
automated test in this milestone (constructing the same physical
reference against two synthetic "runs" using disjoint ID numbering and
asserting identical scoring).

## P. Legacy evaluators

`tools/analysis/evaluate_tim_target_bbox_correctness.py` and
`tools/analysis/tim_evaluation.py` /
`tools/analysis/evaluate_tim_target_correctness.py` are **not modified or
deleted by this milestone**. They remain documented, explicitly, as:

- legacy / historical;
- valid only when tracker IDs in a replay/live run match the annotation
  stream's `correct_target_track_id` values;
- **not** suitable for identity-independent, regenerated-tracker-ID
  evidence -- `evaluate_tim_target_correctness.py`'s own generated report
  already says as much ("For fresh tracker reruns where IDs may be
  renumbered, use bbox correctness or visual validation instead"), and
  this contract is the actual fix that statement was gesturing at.

A new, identity-independent evaluator path consuming this schema is
implemented in Milestone 2 (section Q), introduced alongside the legacy
evaluator rather than replacing it.

## Q. Milestone 2 -- evaluator implementation

Three new files, none of them modifying the legacy evaluator:

- `tools/analysis/physical_target_bbox_evaluation.py` -- the pure
  evaluation core: timebase join, Stage A/B, duration buckets,
  aggregation, report assembly. No bag I/O, so it is fully exercisable
  with synthetic data.
- `tools/analysis/evaluate_physical_target_bbox.py` -- the CLI/bag-reading
  wrapper. Its `--help` text and module docstring explicitly state it is
  **not** the legacy evaluator and does not use
  `correct_target_track_id`/`/tracks` lookups, and name
  `evaluate_tim_target_bbox_correctness.py` as the tracker-ID-dependent
  alternative, satisfying the "impossible to accidentally believe legacy
  evaluation is identity-independent" requirement.
- Focused tests in `tools/tests/test_physical_target_bbox_evaluation.py`
  (core, 26 tests) and `tools/tests/test_evaluate_physical_target_bbox.py`
  (CLI helpers + `--help` distinctiveness, 9 tests).

**Timebase join** (section D): physical-reference keyframes are resolved
at an arbitrary `t_s` as a step function (holding the enclosing
keyframe's `identity_state`/`identity_context`/`distractor_bboxes_xyxy`
constant across `[keyframe.t_s, next_keyframe.t_s)`), with
`target_bbox_xyxy` additionally linearly interpolated across that span
only when the successor keyframe's `interpolate_from_previous` is `true`
(itself only legal, per the schema validator, between two
`present_scored`/`target_only` keyframes). Time outside
`[samples[0].t_s, samples[-1].t_s)` is never evaluated. The
controller-facing output stream is sampled by latest-preceding-sample
with the existing shared freshness contract
(`thesis_bringup.freshness.classify_relative_freshness`,
`DEFAULT_MAX_OUTPUT_AGE_S`) -- the same primitive `tim_evaluation.py`
already uses, not a new validity definition.

**Evaluation state machine**, per fixed-step grid tick (default
`step_s=0.05`, matching `tim_evaluation.py`'s existing default):

1. `absent` -> `target_absent_duration_s`; additionally
   `target_absent_with_output_duration_s` when a valid output exists at
   that instant (the safety-relevant sub-condition from section 13 --
   never collapsed into ordinary localisation error).
2. `present_reference_unavailable` -> `reference_unavailable_duration_s`,
   unconditionally on output (section 14: an output existing during this
   period does not fabricate identity/localisation).
3. `present_scored` with no fresh/valid output ->
   `lost_or_suppressed_duration_s`.
4. `present_scored` with a fresh/valid output -> `classify_identity_stage_a`
   (imported, not reimplemented) decides `identity_target` ->
   `correct_target_output_duration_s` (+`localisation_scored_duration_s`,
   + Stage B numeric metrics, unconditionally, no quality gate),
   `wrong_person` -> `wrong_person_output_duration_s`, or
   `identity_unresolved` -> `identity_unresolved_duration_s`.

**Duration buckets**: the six outcomes above
(`correct_target_output_duration_s`, `wrong_person_output_duration_s`,
`identity_unresolved_duration_s`, `lost_or_suppressed_duration_s`,
`target_absent_duration_s`, `reference_unavailable_duration_s`) are
primary and mutually exclusive; `DurationBuckets.primary_total_s()` sums
them, and the evaluator asserts this equals
`total_evaluated_duration_s` within `1e-6`s (`reconciliation_ok`/
`reconciliation_residual_s`), reported in every output JSON.
`localisation_scored_duration_s` and
`target_absent_with_output_duration_s` are conditional subset metrics
(always `<=` their parent bucket) and are never added into the
reconciliation total a second time.

**Stage B formulas** (section L/M, unchanged from Milestone 1, now
executable): IoU via `external_target_initialization.bbox_iou` (reused,
not reimplemented). Centre error in pixels: Euclidean distance between
bbox centres. Centre error, normalised: divided by the **target**
(reference) bbox height specifically -- `centre_error_ref_h`, verified by
a dedicated test that the same formula gives a different, wrong answer if
divided by the output bbox's height instead. Aggregation: duration-weighted
mean (primary), plus min/max/median/p10/p90 (secondary/diagnostic),
computed only over `identity_target` samples -- no IoU/centre-error
threshold gates membership in this population.

**Report** (`build_report`): JSON containing schema/contract version,
evaluator name/mode, stream name, source bag identity/topic/dimensions,
coordinate convention (+evidence where historical), selected physical
target label, physical-reference path and SHA-256, repository commit and
dirty state (`None` if ungettable, never fabricated), all duration
buckets, full Stage B aggregate, and the reconciliation block. A Markdown
companion is written alongside for human review.

**Regenerated-tracker-ID invariance**: proven both at the Stage A level
(Milestone 1) and now end-to-end through the full join/bucket/aggregate
pipeline (`test_regenerated_tracker_id_invariance_end_to_end`) -- two
synthetic runs, identical geometry and timing, disjoint `track_id`
values, assert identical `DurationBuckets` and `LocalisationAggregate`.
A structural test additionally confirms the evaluation core's source
never references the legacy annotation's tracker-ID field, and that
`OutputSample.track_id` is not read by any of the join/classify
functions.

## R. Milestone 3 -- annotation UI

Adds a third `tools/bag_annotation_ui/static/tim_clean_ui.html` workspace
mode, "Physical reference (Issue #25)", alongside (not replacing) the
existing "Evaluation viewer" and "Annotation editor" modes. All new
frontend logic lives in a separate file,
`tools/bag_annotation_ui/static/tim_physical_reference_ui.js`, so the
existing 2400-line `tim_clean_ui.js` is touched only additively (two small
branches: one in `setLoadedWorkspaceVisible` to show/hide the new
workspace div, one in `updateFrame` to dispatch to the new mode's frame
renderer -- both feature-detected via `typeof window.X === "function"`,
so the legacy modes degrade to their exact original behaviour if the new
file is ever absent). The new mode reuses the existing bag-loading,
`/frame.jpg` rendering, and frame-stepping machinery (`loadedFrames`,
`loadedBag`, `frameTimesS`, `currentFrameIndex()`, `currentTimeS()`) --
no frame-navigation or source-image pipeline is duplicated.

**Backend**: `tools/bag_annotation_ui/tim_ui_physical_reference.py` is a
thin adapter, not a second schema implementation -- `load_physical_reference_for_ui`/
`save_physical_reference_for_ui` call `physical_target_reference.py`'s
`parse_physical_reference`/`validate_physical_reference`/
`write_physical_reference`/`serialize_physical_reference` directly. The
one new piece of logic is `normalize_rect` (reverse-drag normalisation,
zero-area rejection) -- a backend-side safety net applied to whatever
rectangle the frontend submits, on top of (not instead of) the schema
validator's own bounds checking. Three new routes in `tim_clean_ui.py`
(`/api/physical_reference/list`, `/load`, `/save`, plus a best-effort
`/image_topic_hint` for provenance display) mirror the existing
`/api/annotation/load`/`save` pattern exactly. **The backend validator is
authoritative**: `save_physical_reference_for_ui` never writes a file
before `validate_physical_reference` has accepted it, verified directly
against the running server (an artifact with a bare-integer physical
label was rejected with no file written, section 20 verification).

Also fixed as part of this milestone: `physical_target_reference.write_physical_reference`
did not create parent directories, which the schema's own frozen save
destination (`docs/data/physical_target_references/`, not yet existing in
the repository) requires. This is an additive robustness fix (`path.parent.mkdir(parents=True,
exist_ok=True)`), not a schema or scoring semantics change.

**Coordinate mapping** (section 5's core requirement): the canvas's
internal pixel buffer (`canvas.width`/`height`) is set to the loaded
frame's *natural* pixel dimensions the instant it loads
(`updatePhysicalRefFrame`), not a CSS-scaled size. A pointer event is
converted from CSS/display pixels to that buffer's pixel space via
`canvas.width / canvas.getBoundingClientRect().width` (and the `y`
equivalent) -- because the buffer already equals the source image size,
this single ratio *is* the entire display-to-source mapping, and it is
applied at every `pointerdown`/`pointermove`/`pointerup`, before any
box is stored. Saved boxes are therefore always source-image pixels;
raw CSS/canvas display coordinates are never saved, regardless of how
the browser renders the canvas element visually. `physicalRefNormalizeDrag`
handles reverse-drag direction (drag from any corner) and rejects
sub-1px boxes at the frontend, mirrored by the backend's `normalize_rect`.

**Bbox drawing interaction**: pointer-event-based (not legacy mouse
events), a draw-mode selector (Target / Distractor), live drag preview,
an explicit "Clear drawn box" action, and a distractor list with
per-item remove buttons. Target boxes render green, distractor boxes
orange, both labelled -- not colour-only.

**State/context controls**: `identity_state` (`present_scored` /
`present_reference_unavailable` / `absent` -- `present_ambiguous` is not
offered, matching its removal from the frozen schema) and
`identity_context` (`target_only` / `distractors_complete`, shown only
for `present_scored`) are plain `<select>` elements wired to enforce the
frozen rules client-side as *convenience*: switching to `target_only`
clears any drawn distractors; drawing a distractor while in
`target_only` is refused with a status message; drawing any box while
`identity_state != present_scored` is refused. None of this is
authoritative -- the backend validator re-checks everything
independently before any file is written.

**Interpolation**: a single `interpolate_from_previous` checkbox. The UI
does not attempt to pre-compute or grey out illegal transitions (that
would require the frontend to reimplement the validator's adjacency
logic); instead, an artifact with an illegal transition is rejected by
the backend validator at save time with the same error message the
Milestone 1 test suite already exercises, and no partial file is
written.

**Save/load**: the in-memory sample list is edited entirely client-side
(new/update/delete/edit actions on `physicalRefSamples`, kept sorted by
`t_s`) and only reaches the backend on explicit "Save JSON". Loading an
existing artifact re-populates both the sample list and the provenance
form fields. Saving to a path that already holds a different, valid
artifact overwrites it explicitly (there is no silent overwrite outside
this normal, deliberate save action -- the destination path is always
visible and editable in the form before the button is clicked).

**Provenance**: `source_width`/`source_height` are read directly from
the decoded frame's natural pixel dimensions (never typed by hand);
`source_bag_name`/`source_bag_path` are read from the already-loaded bag
path; `source_image_topic` is a best-effort hint from a new endpoint that
inspects the bag's topic list (preferring `/camera/image_raw`) purely for
display -- it never changes which frames `tim_ui_bag_cache.load_bag_cache`
serves, so the existing frame pipeline is untouched. `coordinate_convention`
supports `source_pixels_historical_pre_p53` with a required evidence
field (shown/hidden based on the selected convention), satisfying the
May/June historical-provenance requirement without fabricating a modern
header into old data.

**Tracker overlays**: a "show tracker overlays" checkbox toggles
`draw_tracks` on the existing `/frame.jpg` endpoint -- pixels baked into
the served JPEG for visual context only. They are never read back out of
the canvas or serialized; `physicalRefSamples` objects have no field that
could hold one, and a dedicated backend test walks every key in a saved
artifact asserting none contains the substring "track".

**Legacy UI**: `tools/bag_annotation_ui/tim_ui_annotations.py` (the CSV
schema/validator) is not modified at all. The existing tracker-ID
annotation editor and its `/api/annotation/load`/`save` routes were
verified against the live running server after this milestone's changes,
round-tripping a CSV exactly as before.

## This milestone's scope

Milestone 1 (frozen, corrected): this document (sections A-P) plus
`tools/analysis/physical_target_reference.py` (schema, validator, Stage A
classifier) and its 42 focused tests, plus a template artifact.

Milestone 2 (frozen, section Q): the executable evaluation core, CLI
wrapper, and 35 further focused tests, proven entirely against synthetic
data.

Milestone 3 (this update, section R): the annotation UI mode, its
backend adapter, and 17 further focused tests (94 total for Issue #25).
**Not** implemented: any real sequence annotation, any canonical
evaluation run, any TIM-MARS configuration change, any modification to
the legacy evaluators or existing tracker-ID annotation files.

## Revision note

This document's sections G and J were corrected after review of the
milestone's first version (commit `fcfbe0c5`), which let a minimum
target-IoU threshold gate Stage A identity correctness even with no
competing physical person recorded -- silently turning poor localisation
of the *correct* person into a fabricated identity failure, and biasing
any future Stage B statistics upward by excluding exactly the
worst-localised target-attributed samples. The corrected contract
(`identity_context`: `target_only` / `distractors_complete`, and a
threshold-free relative-comparison Stage A rule) is frozen here; see
sections G and J for the full corrected semantics and the reasoning.

## Milestone 3 corrective follow-up

A browser smoke test against the real May hard-reentry bag found that the
UI's `coordinate_convention` control defaulted to
`source_pixels_p53_contract` regardless of source, silently mis-labelling
a historical pre-#53 bag as modern unless the annotator remembered to
change it by hand. Fixed with a deterministic auto-resolver
(`tim_ui_physical_reference.resolve_coordinate_convention`): a bag whose
own directory name embeds a capture date before Issue #53's 2026-07-22
contract closure resolves to `source_pixels_historical_pre_p53` with
generated evidence text (a logical certainty from the date, not a guess);
a bag with a genuine `tim_mars_source_pixels_resize_v1` header match on
`/detections` resolves to `source_pixels_p53_contract`; anything else
resolves to nothing, and the UI leaves the control on an explicit
"unresolved, choose deliberately" placeholder that the backend validator
already rejects if left unchanged at save time. Verified live against the
real May bag path. Section E/F's frozen coordinate semantics themselves
are unchanged -- this only decides which of the two applies to a given
source, automatically where possible.

The same smoke test flagged the default output-path placeholder
(`.../ui_created/new_physical_reference.json`) as too easy to mistake for
a real destination during casual testing. The output-path default is now
under an explicitly named `_scratch/` example path, and
`physical_target_reference.parse_provenance` now additionally requires a
non-empty `sequence_id` (mirroring the existing
`selected_physical_target_label` non-empty check) -- a save with a
placeholder-empty identity is rejected before any file (or even the
output directory) is created, verified live.

`interpolate_from_previous`'s visible checkbox label is now "Interpolate
from previous keyframe"; the field name and schema are unchanged.
