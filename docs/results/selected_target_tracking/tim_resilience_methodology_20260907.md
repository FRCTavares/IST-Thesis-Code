# TIM-MARS identity resilience: development protocol

## Scope and provenance

Protocol recorded on 7 September 2026 before candidate outcome evaluation.
Base: `7ea81b079d556896ec766fef2df3af618acb423d` on
`tim-mars-same-id-hijack-resilience-20260907`.
Canonical configuration remains unchanged at SHA-256
`0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`.
The historical #89/#90 reports and prospective split/comparison contracts
remain unchanged. H01/H02/H03 are neither accessed nor captured.

## Diagnosis informing the experiment

The retained #90 Seq03 status and tracker messages identify frames 1078--1080
as the three wrong-person authority observations, from 46.699661380 s until
46.833010805 s. They reuse the embedding from frame 1075, 46.566706917 s,
at ages 132.954463, 166.367833 and 232.858555 ms. Images are contemporaneous;
the 250 ms compute interval, not crop eligibility or image availability,
prevents fresh inference. At frame 1081 fresh negative similarity 0.913337
and positive-minus-negative margin -0.263440 immediately suppress authority.
Negative memory was already committed from distractor ID 11; its observation
confirmation parameter controls memory acquisition, not rejection latency.

Cache lifecycle displacement/scale gates compare consecutive tracker boxes.
Lookup checks TTL and generations but does not compare the current bbox to
the cached source bbox. Gradual physical handover can therefore retain cached
positive support. Same-ID ambiguity is always false; the separate nearby
challenger gate accepts positive cached support. General negative rejection
also has a LOCKED same-ID exemption when that challenger gate does not fire.

The cached feature was admitted to trusted gallery at frame 1075 and matches
itself at similarity 1.0 thereafter. Repeated cached observations update the
adaptive prototype. This is repeated old evidence, not a fresh physical
identity check. The immutable anchor remains unchanged. A contamination
audit must distinguish stale target evidence reused on a wrong box from
admission of a fresh distractor feature.

False-rejection audit also finds 863 suppressed Seq03 candidate observations
physically attributed to the selected target under the existing physical-v2
Stage A rule while the proposal reports protected-gallery rejection. Many
have positive similarity >=0.78 but weak original-anchor similarity. These
are diagnostic frame counts, not availability durations or proof of safe
recovery. May and Seq04 show the same class less frequently.

## Predeclared candidates

1. `challenge`: use the existing same-ID nearby-challenger predicate to request
   a fresh selected-candidate appearance challenge before continuing authority.
   Bypass the normal interval for that candidate only. Preserve image-age,
   crop and same-image constraints; suppress challenged authority if current
   evidence cannot be obtained. A strong committed negative contradiction
   must not be bypassed solely because tracker ID remains constant. Other
   candidates retain the normal schedule. This is an event-conditioned
   workload, potentially expensive in sustained crowds; measure it explicitly.
2. `gallery_consensus`: permit gallery-supported recovery despite weak original
   anchor agreement only when at least two distinct trusted gallery exemplars
   each satisfy the unchanged independent identity threshold (0.78). Retain
   existing crop, ambiguity, competing-person margin, negative and transactional
   gates. Two exemplars are the minimum redundancy that removes single-exemplar
   authority, not a similarity threshold sweep. No memory trust gates relax.
3. `combined`: apply both mechanisms, with identical component definitions.

No detector, tracker, model, global similarity threshold, cache TTL or global
compute cadence changes. Experimental switches default off. The canonical
file stays untouched during evaluation. Do not add further candidates by
chasing outcome metrics.

## Falsification and promotion

Challenge is falsified as a practical improvement if fresh appearance does
not reduce handover exposure, creates new safety failures, loses substantial
correct authority, or imposes disproportionate inference load. Gallery
consensus is falsified if correlated/contaminated gallery support authorizes
wrong identities or does not improve correct authority. Combined behavior
must be measured rather than inferred from separate results.

Run the unchanged baseline twice and every candidate on all four exact
retained #90 source candidate streams: May hard re-entry, Seq01 clean,
Seq03 crossing, Seq04 occlusion/absence. Recover exact commands and candidate
digests from each `p090_*_global_1c159a4e_2026_09_05/tim_replay_metadata.json`.
Use the same physical-v2 references/evaluator; do not regenerate detection or
tracker evidence. Recheck repeatability for any proposed selection.

Report every duration bucket, target-present normalized percentages,
publication correctness, separate absence-output percentage and aggregate
target-present totals. Undefined denominators remain undefined. Per-sequence
safety gates precede aggregate availability: no increase in wrong authority,
no new absence output, no memory-contamination regression, deterministic
results. Among passing candidates strongly prefer increased correct authority
and reduced LOST, retaining #90 gains. Explicitly identify dominance and
safety/availability tradeoffs without a weighted scalar.

Record inference calls, embeddings, candidates/call, embeddings/s, fraction of
frames encoded, cache counters and forced challenge counts. Deterministic
replay measures work, not live latency. Add focused synthetic tests for same-ID
handover, cached drift, correct continuity, fresh/failed challenges, negative
contradictions, gallery consensus and recovery suppression. Use the package
build helper and pytest without cacheprovider.

Any promotion requires development review followed by a new prospective
algorithm freeze, split version and final-comparison contract before H01--H03
capture. Creating or releasing that new freeze is outside this investigation.
