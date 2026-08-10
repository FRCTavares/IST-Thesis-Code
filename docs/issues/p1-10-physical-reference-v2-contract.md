# P1.10 Physical reference v2 contract (M1-v2)

GitHub Issue: #25
Branch: `issue-25-improve-bbox-evaluation`
Supersedes, for future canonical annotation only: `docs/issues/p1-10-improve-bbox-evaluation.md` (sections C-N, the frozen `tim_physical_target_bbox_v1` contract, which remains unmodified and fully valid on its own terms)
Motivated by: `docs/issues/p1-10-physical-reference-annotation-plan.md` (the M4A corrective workload plan, which established that all four canonical sequences are `distractors_complete`-dominated) and the read-only M4A.2 audit (which established that v1's `distractors_complete` samples cannot interpolate and that v1's evaluator silently step-holds stale geometry between sparse keyframes, producing duration-weighted metrics that are not scientifically valid at the density M4A planned).

This document is the implementation authority for M1-v2 (this milestone: schema + validator), M2-v2 (a later milestone: evaluator resolution + duration accounting), and M3-v2 (a later milestone: UI). Nothing in this document is only a comment in code -- every rule below is enforced by `tools/analysis/physical_target_reference_v2.py` and proven by `tools/tests/test_physical_target_reference_v2.py`, or explicitly frozen here as a specification for M2-v2/M3-v2 to implement later, not before.

## A. Core scientific requirement (unchanged)

The reference relation is, and remains:

```
physical person -> physical bbox
```

never

```
tracker ID -> physical bbox
```

Regenerating ByteTrack/DeepSORT IDs, or any tracker's internal numbering, in the evaluated pipeline must leave a v2 physical-reference artifact and its evaluation results completely unchanged. No tracker ID, detector index, or list position appears anywhere in this contract as a source of physical identity.

## B. Schema identity

```
contract_version = "tim_physical_target_bbox_v2"
schema_version   = 2
```

Implemented in a new sibling module, `tools/analysis/physical_target_reference_v2.py`, never by modifying `tools/analysis/physical_target_reference.py`. The v1 module, its `SCHEMA_VERSION = 1` / `CONTRACT_VERSION = "tim_physical_target_bbox_v1"` constants, its parser, its validator, and its own 42 tests are unchanged by this milestone -- verified directly in Section K below, not assumed.

Stable, version-independent primitives are imported from v1, never duplicated: `BBoxXYXY`, `bbox_iou`, `classify_identity_stage_a`, `PhysicalReferenceValidationError`, the state/context constants (`STATE_PRESENT_SCORED`, `STATE_PRESENT_REFERENCE_UNAVAILABLE`, `STATE_ABSENT`, `ALL_STATES`, `STATES_REQUIRING_BBOX`, `STATES_FORBIDDING_BBOX`, `CONTEXT_TARGET_ONLY`, `CONTEXT_DISTRACTORS_COMPLETE`, `ALL_CONTEXTS`, `COORDINATE_CONVENTIONS`), and the internal bbox/finite-value/bare-tracker-ID helpers (`_parse_bbox`, `_require_finite`, `_validate_bbox_bounds`, `_looks_like_bare_tracker_id`). None of these concepts change meaning between v1 and v2 -- what changes is exclusively the distractor correspondence model (Section D) and the evaluation-horizon/gap semantics (Sections F/G), which are genuinely new.

No automatic v1 -> v2 migration. This is currently moot: zero real v1 physical-reference artifacts exist in `docs/data/physical_target_references/` (the directory itself does not exist). If it ever mattered, an automatic migration could not safely invent `person_ref` correspondence from a v1 artifact's flat, uncorrelated distractor list -- that is a semantic judgement only a human reviewing the original footage can make. Future canonical May/June physical-reference artifacts use v2 exclusively once the full v2 stack (M1-v2 through M3-v2) is implemented and reviewed; v1 remains a complete, tested, historically-valid implementation of the narrower (target-only-interpolation-only) contract, not something to be replaced in place.

## C. Target identity (unchanged from v1, deliberately not extended)

No parallel `target_ref` is introduced. There is exactly one target slot per artifact, already unambiguously identified by its unique field position (`target_bbox_xyxy`) and by the existing artifact-level `selected_physical_target_label` (unchanged validation: non-empty, not a bare tracker ID, reusing v1's `_looks_like_bare_tracker_id`). The correspondence problem this contract solves is specific to the multi-entry distractor collection, where list position alone cannot safely identify which physical person a box belongs to across samples; a single, uniquely-positioned field has no such ambiguity to resolve. Adding a target-side identifier would be complexity with no disambiguation benefit.

## D. Physical distractor correspondence

Each distractor entry carries an explicit, annotation-local physical-person identifier:

```json
{"person_ref": "phys_d001", "bbox_xyxy": [x1, y1, x2, y2]}
```

replacing v1's flat `distractor_bboxes_xyxy: [[x1,y1,x2,y2], ...]` with a v2 `distractors: [{...}, ...]` list of structured entries.

### D.1 Namespace (Amendment C)

Canonical, frozen format: `^phys_d[0-9]{3,}$` -- e.g. `phys_d001`, `phys_d002`, `phys_d123`. Rejected by construction: bare integers (`"7"`), tracker-shaped strings (`"T2"`, `"track_7"`), unprefixed ordinals (`"d1"`), and anything not matching the pattern exactly (case-sensitive, `phys_d` prefix mandatory, at least 3 digits). The prefix exists specifically so the identifier visibly belongs to the physical-annotation contract and cannot be casually confused with, or copy-pasted from, a tracker ID column.

### D.2 Scope

`person_ref` is scoped to **one physical-reference artifact / one source sequence**. It has no meaning compared across two different artifacts -- `"phys_d001"` in a May artifact and `"phys_d001"` in a June artifact refer to different, unrelated physical people (or none in particular); nothing in this contract or its future evaluator ever compares `person_ref` values across artifacts.

### D.3 Uniqueness

Within one sample, every distractor's `person_ref` must be unique -- the validator rejects a sample with the same `person_ref` appearing twice. Across different (non-adjacent) samples in the same artifact, the *same* `person_ref` reappearing is normal and expected: it is exactly how the annotator asserts "this is the same physical person I labelled earlier."

### D.4 Reuse is a semantic assertion, not a computationally verifiable fact

No schema can computationally prove that a human has not mapped `person_ref` to the wrong physical person -- this is a known, permanent trust boundary, not a gap to close later. It is exactly analogous to `identity_context = target_only` already being an annotator's explicit completeness assertion in v1, never an inference. State this plainly rather than implying false rigor: **the validator guarantees `person_ref` namespace and structure; it cannot and does not guarantee physical-identity truth.**

### D.5 Disappearance and re-entry

If a physical distractor leaves and later re-enters the frame:
- Reuse the same `person_ref` **only when the annotator is genuinely certain** it is the same physical person.
- Otherwise, **mint a new `person_ref`** -- this is the fail-closed default under uncertainty.

This choice affects only how a human reader interprets the artifact's continuity narrative. It has **zero effect on interpolation legality** either way: Section E's exact-set-match rule structurally blocks interpolation across any entry/exit/reappearance boundary regardless of whether the ID was reused or newly minted, because the person's `person_ref` is absent from at least one of the two adjacent samples' sets in both cases.

## E. v2 sample shape and state/context matrix

Replaces v1's `distractor_bboxes_xyxy` field with `distractors`; all other sample-level fields (`t_s`, `identity_state`, `identity_context`, `target_bbox_xyxy`, `interpolate_from_previous`, `notes`) are unchanged in name and meaning from v1.

| identity_state | identity_context | `target_bbox_xyxy` | `distractors` |
|---|---|---|---|
| `present_scored` + `target_only` | required, `= "target_only"` | required, valid in-bounds bbox | must be `[]` |
| `present_scored` + `distractors_complete` | required, `= "distractors_complete"` | required, valid in-bounds bbox | `>= 1` entry, each with a unique, namespace-valid `person_ref` and a valid in-bounds bbox |
| `present_reference_unavailable` | forbidden (`null`) | forbidden (`null`) | forbidden (`[]`) |
| `absent` | forbidden (`null`) | forbidden (`null`) | forbidden (`[]`) |

`present_ambiguous` is not resurrected -- unchanged from v1's own correction.

## F. Interpolation legality (validator-enforced in M1-v2; interpolation math itself is M2-v2)

A sample B with `interpolate_from_previous = true` asserts that the open interval between the previous sample A and B is safely covered by interpolation. M1-v2 enforces **legality** of this claim; it does not perform the interpolation itself (no lerp math exists in the schema/validator module -- that is M2-v2's job).

### F.1 `target_only` (unchanged from v1)

Legal iff A and B are both `present_scored` + `target_only`.

### F.2 `distractors_complete` (new)

Legal iff **all** of:
- A and B are both `present_scored` + `distractors_complete`;
- `{person_ref for d in A.distractors} == {person_ref for d in B.distractors}` -- **exact set equality**, list order never matters.

**Exact set match is the only scientifically defensible rule, not merely the preferred default.** A weaker rule (e.g. interpolating over the intersection and silently dropping non-matching entries) would let a future evaluator run Stage A mid-gap against an *incomplete* distractor set -- reintroducing, silently, exactly the kind of unaudited bias this whole contract exists to eliminate, just relocated from "tracker ID instability" (v1's original problem) to "silently dropped distractor" (a new one). Weaker rules are rejected outright, not merely deprioritised.

Any set mismatch (a `person_ref` added, removed, or replaced between A and B) makes interpolation illegal for the entire interval -- this uniformly and correctly handles entry, exit, and full occlusion of any single distractor (Section H) without any bespoke per-case logic, since all three collapse to "the set changed."

The validator **rejects** an artifact that claims `interpolate_from_previous = true` when these conditions are not met -- matching v1's own existing precedent of hard-rejecting illegal interpolation claims rather than silently downgrading them to `false`.

### F.3 Correspondence validity is not the same claim as geometric interpolation validity

The schema can verify *that* the same physical people are present at both endpoints. It cannot verify *that linear motion between two keyframes is a scientifically safe approximation of what actually happened in between* -- crossings, rapid acceleration, strong scale changes, and progressive occlusion can all make a geometrically legal interpolation a bad one. This is not a new trust boundary: v1's own doc already required the annotator to judge "target motion/scale reasonably smooth... no rapid non-linear motion" for `target_only` interpolation, purely by eye, never mechanically checked. v2 extends the same annotator-judgment boundary to per-distractor geometry; it does not remove it.

**Annotator guidance, frozen for M3-v2's later UI copy and for the annotation workflow generally:**

| Situation | Guidance |
|---|---|
| Calm multi-person motion, roughly linear paths | Interpolation-eligible at standard spacing |
| People approaching but not yet crossing | Still eligible per-person, provided no correspondence change |
| Crossings / overlapping boxes | Do not interpolate, even if the `person_ref` set technically matches -- densify keyframes through the event |
| Rapid acceleration / strong scale change | Same as crossings |
| Partial occlusion, honest visible-extent box still possible | Sample stays `present_scored`; avoid interpolating across a period of changing occlusion extent |
| Full occlusion of a distractor | Omit that `person_ref` from that keyframe's `distractors` list -- naturally forces a set mismatch, blocking interpolation across it (Section F.2) |
| Full occlusion of the target | Switch that keyframe to `present_reference_unavailable` (Section G) |
| Entry/exit | Section H |
| Image-edge truncation, no honest box possible | Same handling as full occlusion |
| Correspondence uncertain across a re-entry | Mint a new `person_ref` (Section D.5); never resolve uncertainty with a tracker ID |

## G. State-only propagation vs. geometry hold -- the distinction this whole contract exists to freeze

Two different things, conflated by v1's implementation even though its schema already implicitly separated them:

- **State-label propagation**: `absent` and `present_reference_unavailable` legitimately hold across an interval until the next transition -- e.g. "target was absent from t=49 to t=53" is a meaningful claim with no bbox attached, and Stage A/B are never invoked for either state (confirmed directly in v1's evaluator: both branches `continue` before reaching Stage A). This is **safe, unchanged, and still automatic in v2** -- there is no staleness risk here because no geometry is ever held, only a state label.
- **Geometry hold**: treating a bbox drawn at one instant as if it were still true, unchanged, at a later instant. This is **eliminated** as an automatic behaviour in v2 (Section H). It was v1's actual defect (proven directly against `resolve_reference_at` and `test_no_interpolation_flag_holds_previous_bbox_step_function` in the M4A.2 audit), and it does not survive into v2's default behaviour under any circumstance.

## H. Eliminating the silent `present_scored` step-hold (non-negotiable)

This is the load-bearing fix, and it is symmetric across both contexts: v1's defect is not `distractors_complete`-specific. v1 already silently held `target_only` geometry too, whenever `interpolate_from_previous = False` between two `target_only` keyframes -- legal in v1, explicitly sanctioned by its own doc ("a hard cut the annotator does not want bridged is handled simply by leaving the flag false"). M4A.2 did not surface this in practice only because no confirmed `target_only` interval survived that audit's re-classification of the four canonical sequences. The fix must be, and is, uniform.

**Frozen rule for M2-v2:** for any `t` strictly between two `present_scored` keyframes A and B where interpolation is not both claimed and legal (Section F), the resolved reference at `t` has **no trustworthy `target_bbox_xyxy` and no trustworthy distractor geometry**. An isolated `present_scored` keyframe does not, by itself, establish any positive-duration interval of valid geometry -- it is a point measurement, useful for artifact inspection, QA, exact-sample diagnostics, and as an interpolation endpoint, but it grants **zero duration** of Stage A/B credit on its own.

**No invented tolerance.** M2-v2 must not introduce a 50ms (or any other) support window around a keyframe, a nearest-keyframe rule, or a reference-freshness tolerance to manufacture non-zero coverage from an isolated point. The existing evaluation grid resolution (`step_s`, already a chosen parameter elsewhere in this codebase) is the only granularity concept involved, and only because duration-weighted metrics are computed on a discrete grid at all -- not because a new freshness concept is being introduced. Concretely: a grid tick's interval `[t, t+dt)` counts as covered by real geometry iff a sample's exact `t_s` falls inside `[t, t+dt)`, **or** the tick lies within a span covered by legal interpolation (Section F). Otherwise it is uncovered (Section I).

**Consequence, stated plainly so M4A-v2's later re-plan is not surprised by it:** without legal interpolation, a sequence of sparse keyframes alone yields only `keyframe_count x step_s` seconds of genuinely-scored duration -- everything else correctly falls to `reference_gap_duration_s` (Section J). Interpolation is therefore not optional cosmetic sugar in v2; it is the *only* mechanism by which sparse annotation produces any meaningful scored duration at all. This directly reframes the productivity question for M4A-v2: an annotator who never sets `interpolate_from_previous = true` gets almost no scored coverage no matter how many keyframes they draw.

## I. Explicit evaluation horizon (Amendment A)

v1 implicitly bounded evaluation to `[samples[0].t_s, samples[-1].t_s)` -- time before the first sample or after the last sample silently disappeared from every report. v2 makes the intended evaluation horizon an explicit, validated provenance field, independent of which timestamps happen to have keyframes:

```json
"evaluation_window": {"start_s": 0.0, "end_s": 67.9}
```

Placed inside `provenance` (alongside the other artifact-scope declarations, e.g. `source_width`/`source_height`), not as a third top-level sibling of `provenance`/`samples` -- it is a declarative fact about the artifact's intended scope, matching the pattern already established for the rest of provenance.

**Validation (M1-v2, enforced now):**
- `start_s` and `end_s` both required, finite;
- `start_s >= 0.0`;
- `end_s > start_s`;
- every sample's `t_s` must satisfy `evaluation_window.start_s <= t_s <= evaluation_window.end_s` -- see the corrected boundary note below. A sample outside this closed anchor domain is rejected at validation time, not silently ignored.

**Frozen for M2-v2 (not implemented in M1-v2):** the evaluator must reconcile the **full** declared `evaluation_window`, not merely `samples[0].t_s -> samples[-1].t_s`. Concretely:
- time strictly before `samples[0].t_s` or at/after `samples[-1].t_s` but still inside `[evaluation_window.start_s, evaluation_window.end_s)` must **not** silently vanish from the report the way it does in v1 today;
- an explicit `absent` or `present_reference_unavailable` state, if it is the first/last sample and extends to the window boundary, propagates through that boundary exactly as it would through any other interval (Section G);
- legally interpolated `present_scored` geometry provides valid reference wherever it applies;
- everything else uncovered by the above becomes `reference_gap_duration_s` (Section J) -- including any span between the window boundary and the nearest keyframe that carries no interval-propagating state.

**Corrected 2026-08-10 (discovered before M3-v2 UI work, before any UI code was written): the sample anchor domain and the evaluated duration domain are two related but distinct things, and the original text above conflated them.**

The *evaluated duration* domain remains, and must always remain, the half-open `[start_s, end_s)` -- no duration at or after `end_s` is ever fabricated, unchanged from the original text.

The *sample anchor* domain is the **closed** `[start_s, end_s]` -- a sample at exactly `t_s == end_s` is legal, specifically as a right-boundary interpolation anchor. This was found to be necessary, not optional, once the UI needed to derive `evaluation_window` deterministically from a loaded source-image timeline: the only deterministic value available is the final source frame's own relative timestamp (`frame_times_s[-1]`), and the original half-open sample rule (`t_s < end_s`, strict) would have made that exact instant impossible to annotate at all -- the last available source frame could never become a keyframe. The fix is not to invent a margin past the last frame (no `DEFAULT_STEP_S` addition, no estimated/median frame period, no epsilon, no manually-typed duration -- the evaluation grid's cadence and the source recording's horizon are separate concepts and must stay separate); it is to recognise that `end_s` itself, like any other timestamp, is a legitimate instant to place a keyframe at.

This does **not** grant the right-boundary anchor any positive duration by itself -- it remains a measure-zero point exactly like every other exact keyframe (Section H). Concretely, for two `present_scored` keyframes A (before `end_s`) and B (exactly at `end_s`):
- if `B.interpolate_from_previous = true` and correspondence is legal, the interpolated span `[A.t_s, end_s)` is fully covered -- the evaluation horizon's last instant of *duration* is included in coverage, even though the anchor point `end_s` itself contributes none;
- if `B.interpolate_from_previous = false` (or no such B exists at all), the tail up to `end_s` is `reference_gap_duration_s`, exactly as any other non-interpolated or absent stretch would be -- a non-interpolated final anchor never manufactures coverage after itself, because no evaluated interval ever starts at `t_s == end_s` (there is nothing left in `[start_s, end_s)` beyond it).

No change to M2-v2's evaluator code was required by this correction -- `physical_target_bbox_evaluation_v2.py`'s interval partitioning already treats `evaluation_window.end_s` as the final breakpoint and never evaluates a tick starting there, so a sample legally placed at `end_s` automatically satisfies "zero duration by itself" and "full coverage when legally interpolated into" without any special-casing. Only `physical_target_reference_v2.py`'s validator needed to change (`t_s > end_s` rejected, `t_s == end_s` accepted), a one-line correction. v1 semantics are entirely unaffected -- v1 has no `evaluation_window` concept at all.

## J. Frozen duration-bucket contract for M2-v2 (not implemented in M1-v2)

**Primary, mutually exclusive buckets:**

```
correct_target_output_duration_s      Stage A identity_target, valid reference only
wrong_person_output_duration_s        Stage A wrong_person, valid reference only
identity_unresolved_duration_s        Stage A tie, valid reference only
lost_or_suppressed_duration_s         valid reference, no fresh/valid output
target_absent_duration_s              state-propagated (Section G)
reference_unavailable_duration_s      state-propagated, explicit annotator assertion only (Section G)
reference_gap_duration_s              NEW -- valid anchors exist, no legal interpolation covers this instant (Section H)
```

`reference_gap_duration_s` is not a reuse of `reference_unavailable_duration_s` under a new name -- the two are semantically distinct claims and must never be merged: `reference_unavailable_duration_s` means "the annotator looked at this specific instant and explicitly asserted no trustworthy bbox exists"; `reference_gap_duration_s` means "the annotator had trustworthy anchors on both sides and made no claim about what happens in between." Collapsing them would hide that distinction from anyone reading a future report.

**Reconciliation (required, exact):**

```
sum(all seven primary buckets) == evaluation_window.end_s - evaluation_window.start_s
```

within the same numeric tolerance v1 already uses (`1e-6s`).

**Conditional subset metrics (never separately summed into the total):**

```
localisation_scored_duration_s        <= correct_target_output_duration_s
target_absent_with_output_duration_s  <= target_absent_duration_s
```

**Required transparency reporting concepts (not merely nice-to-have):**

```
reference_covered_duration_s     = correct_target_output_duration_s
                                  + wrong_person_output_duration_s
                                  + identity_unresolved_duration_s
                                  + lost_or_suppressed_duration_s
                                  -- i.e. duration where physical geometry was
                                     valid for Stage A/B evaluation (whether or
                                     not a fresh output existed at that instant)
reference_gap_duration_s         as above
reference_coverage_fraction      = reference_covered_duration_s
                                  / (evaluation_window.end_s - evaluation_window.start_s)
interpolated_reference_duration_s   subset of reference_covered_duration_s whose
                                     geometry came from legal interpolation rather
                                     than an exact keyframe instant (transparency
                                     metric, not a primary bucket)
```

These let a future report state plainly how much of a headline result rests on human anchors, how much on legal interpolation, and how much duration was honestly left uncovered -- exactly the transparency this whole M4A.2/M4A.3 chain was about.

## K. Stage A / Stage B freeze (unchanged, verified by direct code trace, not assumed)

**Stage A requires zero changes.** `classify_identity_stage_a` (`physical_target_reference.py`) takes `target_bbox_xyxy` and a flat sequence of distractor boxes; it never needs to know *which* physical person a box belongs to, only geometry, to compute `target_iou` vs. `max(distractor_ious)`. The v2 resolution layer (M2-v2) produces `(person_ref, bbox)` pairs, strips the `person_ref`, and calls this **exact same, unmodified, imported function** -- mirroring how v1 already reuses `bbox_iou` from `external_target_initialization.py` rather than reimplementing it. `classify_identity_stage_a` remains threshold-free WHO-classification; `wrong_person` still requires an actual recorded distractor with strictly higher relative IoU. No M1 bias is reintroduced.

**Stage B requires zero formula changes.** `bbox_iou`, `centre_error_px`, `centre_error_ref_h` operate on a resolved `target_bbox_xyxy` regardless of how it was resolved (exact keyframe vs. legally interpolated). The only new requirement, frozen for M2-v2: the evaluator's main loop must check for a Section H "gap" outcome **before** calling Stage A/B at all, routing gap ticks straight to `reference_gap_duration_s` instead. Poor or zero-IoU localisation of a correctly-attributed target still reaches Stage B unfiltered, exactly as in v1, now correctly scoped to only apply when the reference is genuinely valid (exact or legally interpolated) -- never a gap tick that v1 would have silently and wrongly scored.

## L. v1/v2 coexistence

- `physical_target_reference.py` and `physical_target_bbox_evaluation.py` are untouched by this milestone. v1's 42 existing tests remain fully meaningful.
- A v2 artifact (`schema_version = 2`) parsed by the v1 parser is rejected (v1's `parse_provenance` already hard-requires `schema_version == 1`). A v1 artifact (`schema_version = 1`) parsed by the v2 parser is rejected the same way in reverse (`physical_target_reference_v2.py`'s `parse_provenance` hard-requires `schema_version == 2`). Neither module ever silently accepts the other's artifacts -- both directions are proven by test (Section M).
- A future shared loader/dispatcher that peeks `schema_version` and routes to the correct parser, and a shared or version-aware CLI, are **M2-v2 concerns**, not implemented in this milestone.
- Every artifact's own `schema_version`/`contract_version` fields are always read from, and reported based on, its own declared values -- never inferred or guessed -- so "no v1 artifact is silently treated as v2" holds by construction once M2-v2's report assembly reads these fields the same way v1's `build_report` already does today.

## M. Test coverage (M1-v2)

`tools/tests/test_physical_target_reference_v2.py` proves, at minimum: contract/version identity; evaluation-window presence/validity/half-open-boundary enforcement; `person_ref` namespace acceptance and rejection (bare integers, tracker-shaped strings, unprefixed ordinals, empty, malformed digit count); per-sample `person_ref` uniqueness; malformed distractor entries; distractor bbox bounds; the full state/context matrix; interpolation legality for both `target_only` and `distractors_complete` (equal sets legal regardless of list order, added/removed `person_ref` illegal, context/state mismatches illegal); deterministic serialization (distractors always written in `person_ref` order, independent of input order); parse/serialize/parse round-trip determinism; write/load round-trip; v1/v2 mutual isolation in both directions; absence of any "track"-containing concept anywhere in a serialized v2 artifact; identity of `classify_identity_stage_a` as the literal same function object imported from v1 (not a redefinition); absence of any freshness/support-window/tolerance concept in the schema module itself (Section H's "no invented tolerance" rule, checked structurally even though the evaluator that would need such a thing does not exist yet); and presence of this contract document with the key frozen terms (`evaluation_window`, `reference_gap_duration_s`) it depends on.

## N. UI expectations for M3-v2 (frozen here, not implemented)

Additive to the existing M3 "Physical reference" UI mode, reusing its drawing/save machinery -- no identity-management application:

- Derive the list of `person_ref` labels already used anywhere in the current artifact client-side from the in-memory sample list -- no new backend state.
- On drawing a new distractor: a small control offering existing labels used so far in this artifact, plus an explicit "+ New physical distractor" action that mints the next `phys_dNNN` automatically (the annotator never types a `person_ref` by hand, and never sees or types a tracker ID).
- Reusing an existing label asserts "same physical person"; the annotator is responsible for that judgement (Section D.4).
- Render each distractor's `person_ref` visibly next to its box on the canvas, not only in a legend, to reduce mislabeling risk at the point of drawing.
- Removing a distractor from the *current* sample removes only that sample's entry -- the label remains available for future samples (true by construction, since samples are independent JSON entries; the UI must simply not scope its "known labels" list to only the current sample).
- Optional, non-authoritative convenience check mirroring the existing M3 pattern ("none of this is authoritative -- the backend validator re-checks everything"): warn client-side if `interpolate_from_previous` is checked but the current and previous samples' `person_ref` sets do not match.
- Explicitly out of scope: rename-across-artifact tooling, ID-merge tooling, any dedicated identity-management screen. A labelling mistake is fixed by editing the specific sample(s) directly, using the existing edit capability.

## O. What this milestone does not do

Does not implement `physical_target_bbox_evaluation_v2.py` or any interpolation/resolution math. Does not implement a loader dispatcher or a v2-aware CLI. Does not modify the annotation UI. Does not modify `physical_target_reference.py` or `physical_target_bbox_evaluation.py`. Does not create any real physical-reference artifact. Does not begin real canonical annotation. The earlier M4A/M4A.1/M4A.2 workload-planning documents remain historical evidence of why v2 became necessary and are not rewritten to pretend v1 was always sufficient.
