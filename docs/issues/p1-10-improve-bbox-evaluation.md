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
specific bag being annotated), the known 640x480 capture resolution
already used and cross-checked by the completed #26/#30/#31 evidence over
these same sequences, and an explicit statement that the frame is
interpreted as plain source-image pixels (no letterbox padding, matching
the anisotropic-resize contract's own geometry even though this bag
predates the header that would say so explicitly).

## G. Physical target state

Each sample carries exactly one `identity_state`:

| State | Bbox required? | Meaning |
|---|---|---|
| `present_scored` | `target_bbox_xyxy` required | Physically visible; the annotator is confident this bbox is unambiguously the selected person, with no realistic risk of confusion with anyone else at this instant. Safe for automatic single-box geometric identity scoring (section J). |
| `present_ambiguous` | `target_bbox_xyxy` required | Physically visible, but this instant is judged a genuine identity-confusion risk (crossing, heavy occlusion boundary, near-duplicate distractor). `distractor_bboxes_xyxy` *should* be populated when feasible (section J/section H). Automatic geometry alone must never resolve this state; see section J for the exact rule. |
| `present_reference_unavailable` | none allowed | Physically visible in principle, but no reliable bbox can be drawn (near-total occlusion, motion blur, or any case where the annotator cannot commit to a specific box). Unscored, not zero-IoU, not absent. |
| `absent` | none allowed | Not physically present in the source frame. Not a localisation failure; excluded from the localisation-scored denominator entirely. |

`present_ambiguous` exists specifically to satisfy the non-negotiable
rule from this issue: **a wrong physical person must never become
"correct" merely because its bbox geometrically overlaps the reference.**
It is the schema's mechanism for a human to say "do not trust a single
IoU threshold here" independently of what the evaluator later computes --
see section J.

Explicitly, per this issue's constraint:

```
absent != unscored (present_reference_unavailable)
unscored != lost output (an evaluator/output-side concept, not this schema)
lost output != wrong person (also output-side, not this schema)
```

`distractor_bboxes_xyxy` (list of `[x1,y1,x2,y2]`, same format/bounds
rules as `target_bbox_xyxy`, may be empty) is optional on every state but
only meaningful on `present_ambiguous` and `present_scored`; it must be
empty/omitted on `present_reference_unavailable` and `absent`. Each
distractor box represents one other physically distinct visible person at
that instant -- never a tracker ID, never the target itself.

No partial/heavy occlusion sub-taxonomy is added beyond
`present_ambiguous` vs `present_reference_unavailable`: the two questions
that matter operationally are already separated ("can I draw a
trustworthy box at all" vs "could that box be confused with someone
else"), and multiplying occlusion categories further is not required by
the four canonical sequences audited.

## H. Occlusion bbox policy

When a valid box is drawn (`present_scored` or `present_ambiguous`), it
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
  preceding sample in the array have `identity_state == "present_scored"`.
  The validator rejects `true` on the first sample (no predecessor), and
  rejects it whenever either endpoint is not `present_scored` --
  concretely enforcing every one of:
  - no interpolation through `absent`;
  - no interpolation through `present_reference_unavailable`;
  - no interpolation across a `present_ambiguous` boundary;
  - no interpolation across a discontinuous re-entry unless the
    annotator explicitly re-asserts `present_scored` on both sides *and*
    sets the flag -- a hard cut the annotator does not want bridged is
    handled simply by leaving the flag `false`, which is also the
    default an annotator gets by doing nothing.
  When `true`, the evaluator (later milestone) may linearly interpolate
  `target_bbox_xyxy` between the two keyframes for output timestamps that
  fall strictly between them. Interpolation must never be extrapolated
  past the last keyframe or before the first.
- An interpolated reference must never be produced outside
  `[0, source_width] x [0, source_height]`; because both endpoints are
  already bounds-validated and linear interpolation of two in-bounds
  boxes is itself always in-bounds, this is a property of the
  interpolation rule rather than a separate runtime check.

## J. Identity correctness versus localisation correctness

Two strictly separate stages. Stage B never feeds back into Stage A.

**Stage A -- physical identity outcome** (per output sample, joined to
the nearest applicable physical-reference keyframe/interpolated span):

1. Reference state `absent` -> not identity-scored against a bbox at all
   (handled by the existing absence/output-during-absence accounting,
   unaffected by this contract).
2. Reference state `present_reference_unavailable` -> sample is
   **unscored** for identity, regardless of what the output published.
3. Reference state `present_scored` (exact or validly interpolated) with
   **no distractor boxes** recorded for that sample: output is
   identity-correct iff
   `bbox_iou(output_bbox, target_bbox) >= identity_iou_threshold`.
   This single-threshold rule is safe here specifically *because* the
   annotator already asserted, by choosing `present_scored`, that there
   was no realistic confusion risk at this instant -- the human judgment
   call is what licenses using a bare threshold, not the geometry alone.
4. Reference state `present_ambiguous`, **or** `present_scored` with one
   or more `distractor_bboxes_xyxy` recorded: output is identity-correct
   iff **both**
   (a) `bbox_iou(output_bbox, target_bbox) >= identity_iou_threshold`,
   **and**
   (b) for every distractor box `d`,
   `bbox_iou(output_bbox, target_bbox) > bbox_iou(output_bbox, d)`.
   This is the same best-match/margin principle already proven in
   `external_target_initialization.match_frame` (`best_iou`/`second_iou`/
   `margin`), generalised from anonymous tracker candidates to named
   physical-reference boxes. If (a) holds but (b) fails for some
   distractor, the output is identity-**wrong** (it matches a distractor
   at least as well as the target) -- not "correct because IoU was high."
5. `present_ambiguous` with **no** distractor boxes recorded: **unscored**
   for identity. The annotator's ambiguity flag alone withholds an
   automatic verdict even when no distractor geometry is available to
   adjudicate it -- this is the concrete mechanism that prevents "high
   IoU with the target reference" from ever being used, by itself, as a
   sufficient identity oracle during a genuinely contested moment.

**Stage B -- localisation quality** (computed only for samples Stage A
returned identity-correct on): `bbox_iou(output_bbox, target_bbox)` and
centre error (section M) against the target box. This is the *same*
target-IoU value that may already have been computed inside Stage A step
3; it is reported as a distinct field because it answers a different
question (how good is the match, given identity is already established),
and the causal direction is strictly one-way: identity gates localisation
reporting, localisation numbers never redefine or override the identity
verdict.

`identity_iou_threshold` (Stage A) and the localisation IoU/centre-error
*reporting* thresholds (Stage B, e.g. for a "good localisation" summary
bucket) are documented here as **conceptually independent knobs**; their
exact numeric values are evaluator-calibration work for the next
milestone, not frozen by this schema. As a continuity anchor, the
existing bbox evaluator's defaults (`iou_threshold=0.5`,
`centre_distance_threshold=0.5`) are a reasonable starting point to
revisit then, not a value this document binds.

## K. Localisation scoring subset

A sample contributes to the localisation-scored duration/count iff **all**
of the following hold:

1. the selected physical target's reference state is `present_scored` or
   `present_ambiguous` for that sample (exactly or via valid
   interpolation);
2. a valid `target_bbox_xyxy` is available (exact or interpolated);
3. a controller-facing output bbox exists and is valid (non-zero ID,
   finite, positive width/height) at that sample;
4. Stage A (section J) classified that sample identity-correct.

Any sample failing (1)-(3) falls into `reference_unscored_duration_s` or
`target_absent_duration_s`/`lost_duration_s` per section N, never into the
localisation numerator or denominator. A sample failing only (4) (a
confirmed wrong-person or ambiguous-and-unresolved output) contributes to
`wrong_target_duration_s`, never to localisation statistics -- geometry
computed on a wrong-person sample is not "worse localisation", it does
not exist as a localisation sample at all.

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

- `correct_target_duration_s` -- Stage A identity-correct.
- `wrong_target_duration_s` -- Stage A identity-wrong (output exists but
  fails Stage A: distractor match, or fails the plain threshold with no
  distractor evidence to save it).
- `lost_duration_s` -- reference available/scorable (`present_scored` or
  resolvable `present_ambiguous`) but no valid output published.
- `target_absent_duration_s` -- reference state `absent`.
- `reference_unscored_duration_s` -- reference state
  `present_reference_unavailable`, or `present_ambiguous` with no
  distractor evidence (section J step 5), regardless of what the output
  did.

`localisation_scored_duration_s` is **conditional, not a sixth disjoint
bucket**: it is the portion of `correct_target_duration_s` that also
satisfies section K's four conditions (in practice, all of
`correct_target_duration_s` by construction, since Stage A correctness
already implies (1)-(4) -- it is named separately only so a future report
can state the localisation-statistics denominator explicitly rather than
leaving it implicit).

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
future, flag-gated work (implementation plan step 4 in the accepted
audit), introduced only after this contract and its validator are
reviewed and accepted.

## This milestone's scope

Implemented: this document, plus `tools/analysis/physical_target_reference.py`
(schema dataclasses + deterministic load/validate/serialize) and its
focused tests, plus a template artifact. **Not** implemented: the drawing
UI, the evaluator refactor, any real sequence annotation, any replay run,
any TIM-MARS configuration change, any modification to existing
evaluators or annotation files.
