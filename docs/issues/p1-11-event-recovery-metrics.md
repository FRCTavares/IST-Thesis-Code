# P1.11 Event and Recovery Metrics

GitHub Issue: #26
Branch: `issue-26-event-recovery-metrics`
Baseline: `feda884463664a677aedfd228b3c3ee945c0adea`

## Objective

Extend the authoritative selected-target evaluator introduced by Issue #24 with deterministic event, burst, transition and recovery-episode metrics.

This work is evaluation-only. It must not change TIM-MARS runtime policy, thresholds, canonical configuration, tracker behaviour or controller-facing publication.

## Existing authority

`tools/analysis/tim_evaluation.py` remains the single authority for:

- annotation parsing and validation;
- image-header or bag time origins;
- selected-target output validity;
- latest-preceding freshness;
- half-open annotation boundaries;
- exact interval-slice integration;
- correct, wrong-target, lost, absent and stale classifications.

New evaluators must import and reuse these semantics.

## Canonical event vocabulary

Use the repository annotation values:

- `clean_visible`
- `target_absent`
- `reentry`
- `occlusion_ambiguity`
- `id_switch_fragmentation`
- `other`

Do not invent replacement names in report outputs.

## Required metrics

### Existing duration metrics

Retain per stream and per event type:

- correct-target duration and ratio;
- wrong-target duration and ratio;
- lost-target duration and ratio;
- target-not-visible duration;
- target-absent-but-output duration;
- stale-output duration.

### New event and burst metrics

Add:

- wrong-target burst count;
- each wrong-target burst start, end and duration;
- longest wrong-target burst;
- wrong-handover count;
- recovery-attempt count;
- correct-candidate-suppressed duration;
- target-absent-but-output episodes;
- TIM-MARS state occupancy;
- memory-event counts.

### Recovery episodes

Each recovery episode must record:

- stream;
- bag or sequence identifier;
- annotation event type;
- disturbance start and end;
- first eligible recovery time;
- first correct output time;
- first stable correct output time;
- first-correct latency;
- stable-correct latency;
- success, failure or censored result;
- wrong-target duration before recovery;
- lost duration before recovery;
- target track ID before disturbance;
- target track ID after recovery;
- same-ID or new-ID recovery;
- TIM state transitions when status data exists.

Stable recovery must use a documented persistence rule and must not be inferred from one correct sample.

## Scientific rules

- Wrong target and lost output are never merged.
- Sequence end without stable recovery is censored, not successful.
- Target absence is not ordinary tracking failure.
- Tracker fragmentation is distinct from physical exit and re-entry.
- Missing annotations remain unscored.
- Positive-duration annotation overlap remains invalid.
- Events must not be double-counted across overlapping definitions.
- Raw `/target` and TIM `/target_memory_mars` remain separate.
- The annotated-ID oracle and spatial oracle remain separate.
- State or memory metrics unavailable in an older status payload must be emitted as unavailable, not guessed.

## Status-payload availability

All four canonical development bags contain `/target_memory_mars/status`.

May and June Seq01 contain an older payload with:

- state;
- control mode;
- target track ID;
- visible;
- reacquired;
- reason;
- frame ID;
- candidate score lists.

June Seq03 and Seq04 additionally contain:

- candidate track ID;
- publication suppression reason;
- positive-memory update fields;
- hard-negative memory size;
- hard-negative lifecycle events;
- risk flags;
- trusted-gallery and protected-anchor diagnostics;
- source track timestamps.

Schema-version and field-availability reporting is therefore mandatory.

## Proposed implementation shape

Prefer:

- shared episode and classification helpers in `tools/analysis/tim_evaluation.py`;
- one dedicated CLI such as `evaluate_tim_event_recovery.py`;
- versioned deterministic JSON as the complete report;
- deterministic CSV tables for event, burst, recovery and state rows;
- concise Markdown summary;
- focused unit tests using synthetic timelines;
- canonical four-sequence evidence.

## Required edge-case tests

Cover:

- no events;
- no output messages;
- exact half-open boundaries;
- zero-duration annotations;
- stale outputs;
- duplicate timestamps;
- non-monotonic timestamps;
- one-frame correctness that fails stable recovery;
- wrong output before recovery;
- repeated loss and recovery;
- recovery after tracker-ID change;
- same tracker ID on the wrong person;
- target absent until sequence end;
- missing status topic;
- older status schema;
- missing status fields;
- empty hard-negative events;
- multiple lifecycle events in one payload;
- final censored recovery episode.

## Implementation progress

### Slice 1 — authoritative classification and contiguous episodes

Added shared, evaluation-only primitives for:

- one classification per exact authoritative interval slice;
- explicit correct, wrong, lost, target-absent and no-selection categories;
- retained freshness provenance;
- maximal contiguous episodes without crossing gaps, bags or event types;
- wrong-target episodes that retain all selected IDs for later handover analysis.

This slice does not alter existing evaluators or runtime behaviour.

### Slice 2 — wrong bursts, handovers and absent-output episodes

Added deterministic aggregate metrics for:

- wrong-target burst count, total duration and longest duration;
- non-zero selected-ID handovers inside each wrong-target burst;
- target-absent-but-output episode count, total duration and longest duration;
- strict separation between wrong-target and target-absence metrics;
- boundaries that do not cross gaps, bags or annotation event types.

This slice remains evaluation-only and introduces no runtime-policy changes.

### Slice 3 — physical-absence recovery episodes

Added recovery episodes for an annotated physical target absence followed by
an adjacent visible interval.

The evaluation contract is:

- disturbance start and end are the annotated target-absence boundaries;
- recovery becomes eligible at the start of the next adjacent visible interval;
- first-correct latency is measured from that eligible time;
- stable recovery requires at least `0.25 s` of contiguous correct output;
- the reported stable-output time is the start of the first qualifying run;
- wrong and lost durations before stable recovery remain separate;
- a new physical absence before stable recovery is a failure;
- sequence end without stable recovery is censored;
- an absence with no subsequent visible interval is censored;
- same-ID and new-ID recovery are reported separately.

The persistence threshold is an evaluation parameter and is independent of the
TIM-MARS runtime confirmation configuration.

### Slice 4 — schema-aware status parsing and state occupancy

Added evaluation-only support for:

- tolerant parsing of JSON status payloads;
- explicit field availability for old and current status schemas;
- invalid-payload accounting without silently fabricating values;
- latest-status half-open state occupancy;
- deterministic duplicate-timestamp replacement;
- explicit unavailable output when no usable status data exists.

Current-only fields such as candidate ID, publication suppression, positive
memory updates and hard-negative lifecycle events remain unavailable when
absent from older payloads.

## Evidence boundary

Canonical development evidence may use May, June Seq01, Seq03 and Seq04.

September held-out sequences from Issue #27 must not be used for tuning or promotion in this issue.
