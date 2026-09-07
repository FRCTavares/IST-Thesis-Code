# TIM-MARS same-ID resilience and correct-target availability

Development investigation, 7 September 2026. The protocol was committed as
`4520a688` before the first candidate comparison. The explicit fourth-candidate
amendment was committed as `b55df250` after diagnosing the strict challenge's
image-availability failure and before evaluating that final candidate. Original
negative results are retained. No detector, tracker, model or similarity
threshold was changed.

## Scope and reproducibility

Work took place in `/home/francisco/Desktop/Thesis-Code` on `fcstpi`, on branch
`tim-mars-same-id-hijack-resilience-20260907`, created from clean main
`7ea81b079d556896ec766fef2df3af618acb423d`. The separate Issue #58 / PR #99 branch
remains at `fafa968de77ab66844bf50eb6428d102b2e22425`.

The baseline canonical SHA-256 is
`0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`.
MARS-small128 remains
`e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`.
Existing #89/#90 evidence and both frozen prospective contract files are
unchanged. H01/H02/H03 were not captured, inspected, fabricated or used.

`tools/experiments/run_tim_resilience_development.py` reuses the exact commands,
source streams, dimensions, selected IDs and stream digests from the four
retained `p090_{may,seq01,seq03,seq04}_global_1c159a4e_2026_09_05` replay metadata
files. It changes only the development configuration and output destination.
Detection/tracker evidence is not regenerated. Each physical-v2 reference is
checked against its retained SHA before evaluation. The original physical-v2
evaluator, reference interpolation, output-age contract and attribution rule
remain unchanged. This is a TIM study, not a rerun or alteration of the frozen
architecture comparison.

New bags are under `bags/replay/tim_resilience_*_20260907`; generated reports
are under `reports/tim_resilience_20260907`; runtime logs are under
`ros2_ws/log/tim_resilience_*.log`. Retained compact evidence accompanies this
report. Frame-level joins are produced by
`tools/analysis/analyse_tim_resilience_evidence.py`. Its frame counts are
diagnostics and must not replace evaluator duration accounting.

## Root cause and exact Seq03 trace

The initial global recovery is correct: probation at 44.299462659 s and LOCKED
at 44.333037381 s. The detailed trace also contains a short interruption from
44.601125325 to 44.699664622 s, triggered by appearance 0.778 below 0.780, before
the later handover. Thus the post-recovery period is useful but not literally
uninterrupted authority.

All three wrong-authority observations use ID 9, candidate list `[13,9,10]`,
LOCKED state, `accepted_candidate`, no ambiguity, and a qualifying ID-13
challenger. Positive support is cached `trusted_gallery` similarity 1.0;
protected-anchor similarity is 0.560493443; negative similarity is 0.681705236;
positive-minus-negative margin is 0.318294764; negative rejection is false.

| Frame | Time s | Cache age ms | Geometry | Target IoU | Distractor IoU | Authority |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1078 | 46.699661380 | 132.954463 | 0.780544 | 0.564780 | 0.639897 | wrong person |
| 1079 | 46.733074750 | 166.367833 | 0.879466 | 0.387404 | 0.844842 | wrong person |
| 1080 | 46.799565472 | 232.858555 | 0.917582 | 0.292160 | 0.942964 | wrong person |
| 1081 | 46.833010805 | 0 | 0.956690 | 0.251276 | 0.961133 | suppressed |

At frame 1081 fresh positive similarity is 0.649897456 (adaptive prototype),
negative similarity 0.913337052 and margin -0.263439596. The existing gate
immediately emits `same_id_hijack_reject: challenger=13 hard_negative ...`,
transitions to UNCERTAIN and removes controller authority. No second rejection
observation is required. The three intervals sum to 0.133349425 s.

The cached source is frame 1075 at 46.566706917 s. Its fresh positive similarity
was 0.841075659; it was accepted and admitted to the trusted gallery. Subsequent
comparisons against that same stored feature return 1.0. This is repeated old
evidence, not independent identity verification. Appearance is evaluated on
the wrong frames, but `appearance_used=false`: same-ID geometry is not treated
as ranking ambiguity. The separate hijack check nevertheless evaluates the
cached positive/negative evidence and allows continuity.

The images at all event frames are contemporaneous (image age 0 ms), crops
are encoding-eligible, and each image is new. The exact skip reason is
`cached_interval`: the 250 ms interval prevents inference, rather than image
availability, crop rejection or the same-image guard. Fresh appearance at
46.566706917 s was positive; no fresh feature was obtained between that frame
and the rejection at 46.833010805 s.

Cache frame generation remains 1 and track generation 2. Lookup validates
age <=750 ms and matching generations. The configured spatial gates apply in
lifecycle reconciliation against the previous tracker bbox; cache lookup
does not compare the current box against `source_bbox`. Consecutive centre
distances are 0.016914, 0.006345 and 0.003544; consecutive area ratios are
0.814650, 0.873560 and 0.968420, all safely within the existing gates.
Source-to-current centre distances are 0.014576, 0.020879 and 0.024398, with
area ratios 0.769485, 0.672191 and 0.650963. Even adding source-box checks with
the unchanged 0.25/0.25 thresholds would not catch this event. Source IoU falls
from 0.630681 to 0.428507, which exposes how a small image-normalized movement
can matter for a small person crop.

`hard_negative_confirm_observations=2` controls admission of a distractor
prototype from pending to committed memory. It does not delay rejection.
At frame 1078 a committed ID-11-derived entry already has six observations,
last updated at frame 1056, with age 22 frames. Cached observations can count
toward memory acquisition; the parameter does not mean two fresh images.

`same_id_accept_relief=0.08` lowers the LOCKED geometry threshold from 0.52 to
0.44. Every wrong-frame geometry score exceeds even 0.52, so relief is not
decisive here and does not alter the 0.78 identity threshold. Enabling same-ID
hijack protection also exempts LOCKED same-ID proposals from the later general
negative gate: negative rejection relies on the earlier qualifying-challenger
check. This is a broader weakness when no challenger exists, but it is not the
cause of delay in this event because ID 13 already qualifies and the negative
flag remains false until fresh inference.

Publication is transactional with respect to the evidence available: rejection
precedes acceptance and positive-memory mutation. A ROS target message still
exists for a suppressed update; the canonical zero-ID/visibility contract
removes authority. This is not an extra post-rejection publication delay.

## Memory and broader failure class

Protected anchor content remains immutable. Positive memory is updated after
recovery, including repeated cached adaptive updates at the three wrong-box
frames. Their source features are physically target-derived; no fresh
distractor feature is admitted to positive memory during those three updates.
The geometric reference does follow the wrong box until rejection. The audit
therefore distinguishes wrong geometric continuity and reinforcement of stale
target appearance from fresh distractor-feature contamination.

The mechanism generalizes beyond ID 9: tracker identity may survive a physical
handover; gradual bbox movement preserves lifecycle generations; cached
positive evidence can become self-matching gallery evidence; same-ID ranking
ambiguity is suppressed; negative veto can depend on another track being
present. Longer visual gaps and absent/merged challenger tracks can extend the
unobservable interval. None of these observations justifies changing the
global reacquisition threshold.

A separate baseline Seq04 diagnostic flags eight adaptive update observations
using the cached crop from frame 979: its source box overlaps a distractor
slightly more than the target (0.714497 versus 0.676397). Current boxes at those
updates are target-attributed and no wrong authority is measured. This is a
source-crop contamination concern under overlap, not proof that the embedding
contains only the distractor. It is reported rather than hidden.

## False rejection and candidate rationale

The baseline audit finds 863 suppressed Seq03 observations containing a
physically correct candidate while the proposal reports protected-gallery
rejection. Many have >=0.78 gallery similarity but poor original-anchor
agreement. Similar examples occur in May and Seq04. This identifies a possible
availability bottleneck, but high gallery similarity alone is not proof that
the original gate is unnecessary.

The candidates are:

- `challenge`: fresh selected-candidate challenges under the existing nearby
  challenger predicate; interval bypass only for that candidate; failure to
  obtain fresh evidence suppresses authority; committed negative evidence
  cannot be bypassed solely by same-ID continuity.
- `gallery_consensus`: two distinct trusted gallery entries must each meet
  the unchanged 0.78 threshold to replace weak original-anchor agreement at
  recovery. Crop, ambiguity, competing-person margin and negative gates stay.
- `combined`: the two mechanisms together.
- `available_image_challenge`: the documented fourth-candidate amendment;
  fresh challenges when a new usable image exists, ordinary cached identity
  gates when no such image exists, and suppression for actual encoding/backend
  failure. It does not label a reused feature fresh or extend cache TTL.

The strict challenge removes the known Seq03 exposure partly by rejecting
earlier: at 45.666486936 s fresh similarity is 0.761 below 0.780, followed by
anchor rejection and LOST. It is incorrect to describe this as detecting the
handover exactly at 46.699661 s. Correct-duration deltas account for the cost.

Gallery consensus exposes a real safety failure: on Seq03, wrong ID-6 recovery
at 25.232779837 s has gallery support 0.832762 but anchor similarity 0.444538.
The ensuing history contains 96 wrong-authority diagnostic frames and 86
positive-memory updates whose source crops are wrong-person-attributed.
Redundant gallery entries are correlated; two of them do not provide an
independent protected identity guarantee. The combined candidate also admits
wrong Seq04 recoveries at 26.666927650 and 27.033436946 s, despite its continuity
challenge mechanism. These recovery-policy relaxations are not promotable.

## Results and decision

Recommendation: **PROMOTE `available_image_challenge` for development review**.
The canonical configuration has not been changed. Adoption and a new
prospective freeze require review before H01/H02/H03 capture.

The [complete comparison](tim_resilience_development_20260907/comparison.md)
contains all 20 sequence/configuration cells and aggregate totals. The
[machine-readable summary](tim_resilience_development_20260907/summary.json)
retains every requested duration, normalized percentage, publication correctness,
state/rejection count, workload counter, hash and repeatability result.
Percentages below use target-present evaluable time, excluding absence and
reference gaps.

| Sequence | Configuration | Correct s | Correct % | Wrong s | Lost s |
| --- | --- | ---: | ---: | ---: | ---: |
| May | baseline | 62.594003990 | 92.233 | 0.033394241 | 5.237511543 |
| May | selected | 62.796329712 | 92.531 | 0.033394241 | 5.035185821 |
| Seq01 | baseline | 61.200516816 | 100.000 | 0 | 0 |
| Seq01 | selected | 61.200516816 | 100.000 | 0 | 0 |
| Seq03 | baseline | 25.067443244 | 29.925 | 0.133349425 | 58.566005114 |
| Seq03 | selected | 24.600414282 | 29.368 | 0 | 59.166383501 |
| Seq04 | baseline | 43.469299585 | 59.958 | 0 | 29.030742187 |
| Seq04 | selected | 48.766241082 | 67.264 | 0 | 23.733800690 |

Across 285.332266145 s of target-present evaluable time, correct authority
increases from 192.331263635 s (67.406069%) to 197.363501892 s (69.169710%).
Wrong authority decreases from 0.166743666 s (0.058438%) to 0.033394241 s
(0.011704%). LOST decreases from 92.834258844 s (32.535493%) to 87.935370012 s
(30.818586%). Identity-unresolved duration is zero. Publication correctness
increases from 99.913379% to 99.983083%.

All configurations have zero reference-unavailable duration and zero output
during target absence. Seq04 contains 13.900030159 s absence, giving 0%
absence output; this percentage is undefined for the other three sequences.
Reference gaps remain 0 s in May/Seq01, 0.100453371 s in Seq03 and
0.100883795 s in Seq04. These intervals are not counted as avoidable LOST.

### Safety and availability selection

The selected candidate passes the per-sequence safety gates: no increase in
wrong authority, no new absence output, no new wrong-source positive-memory
update pattern in the retained frame audit, and deterministic outputs. May's
existing 0.033394241 s error remains; this is not a zero-error system.

The aggregate change is Pareto-improving: +5.032238257 s correct authority,
-0.133349425 s wrong authority and unchanged absence behavior. Per-sequence
analysis is more qualified. May gains 0.202325722 s correct authority, Seq01
is unchanged, and Seq04 gains 5.296941497 s. Seq03 is a genuine safety versus
availability tradeoff: eliminating its wrong interval costs 0.467028962 s
correct authority, with LOST increasing by 0.600378387 s. It still retains
2.067728018 s correct authority above the pre-#90 result. Its 29.368% correct
availability remains poor and is not presented as a solved crossing problem.

The strict challenge is availability-dominated by the selected candidate:
the same safety results, but 30.342656724 s less correct authority on May.
Gallery consensus and the combined candidate increase availability but fail
the per-sequence safety gates. They are safety-inferior, inadmissible tradeoffs,
not mathematically dominated on both duration axes. Their negative results
are retained rather than retuned. Raising the global threshold is unrelated
to the observed continuity failure; globally shortening the compute interval
would spend work outside the identified risk condition. Existing spatial
cache thresholds would still admit the wrong-interval boxes even if evaluated
against the original source crop, so that change alone cannot explain a fix.

### Appearance workload and onboard service time

| Sequence | Calls baseline / selected | Embeddings baseline / selected | Selected embeddings/s | Frames encoding %, baseline / selected | Forced calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| May | 185 / 248 | 374 / 416 | 6.153 | 19.474 / 26.105 | 84 |
| Seq01 | 224 / 232 | 868 / 876 | 14.314 | 14.737 / 15.263 | 8 |
| Seq03 | 302 / 354 | 844 / 896 | 10.684 | 15.640 / 18.333 | 52 |
| Seq04 | 313 / 1150 | 1387 / 2224 | 25.711 | 15.291 / 56.180 | 837 |

Total embeddings increase from 3473 to 4412 (+27.0%); calls increase from
1024 to 1984. Forced calls encode only the challenged selected candidate.
The 981 forced calls are not identical to the net call increase because
same-image guards can replace subsequent normal opportunities. Selected
embeddings per invocation are 1.677, 3.776, 2.531 and 1.934 respectively.
Selected cache hits are 1375/4844/4000/5320, misses 986/184/526/1371 and
expirations 11/0/15/43. Lookup invalidations are zero; lifecycle pruning is
separate and this does not imply that lifecycle resets never occur. Full
baseline and candidate counters are retained in the summary.

A sequential Pi service-time probe on Seq04, the largest workload increase,
repeats the same deterministic decisions with timing instrumentation only.
Appearance service time increases from 18.001 s to 32.816 s across an
86.501 s source timeline; total TIM processing service time increases from
20.825 s to 35.892 s. Forced single-crop inference has median 17.131 ms,
95th percentile 18.446 ms and maximum 25.580 ms. Overall TIM frame-processing
95th percentile changes from 62.256 ms to 62.782 ms. Both runs include a
roughly 0.47 s cold-start maximum. Exact distributions and semantic equality
are in [service_profile.json](tim_resilience_development_20260907/service_profile.json).

This is a material event-dependent compute increase, especially Seq04
(+60.3% embeddings), not a free safety improvement. The service-time fractions
are not CPU-utilization estimates or live end-to-end latency measurements.
They support feasibility, not sustained real-time certification; full
contention, thermal, detector/control scheduling and deployment characterization
remain with Issue #32.

### Verification and retained evidence

All 20 baseline/candidate cells repeat with identical semantic outputs and
identical source candidate-stream digests. Four further baseline controls on
the final implementation match the initial baseline, establishing that the
default-off additions preserve canonical behavior. Together these are 44
main replays; the two service probes also match their reference outputs.
Scientific source evidence was reused, not regenerated.

The final package and related replay/tool test gate passes with 505 tests,
one skip and 15 dependency warnings. The later tooling-only gate
passes 47 tests. Focused new tests cover physical handover under a stable ID,
cached continuity, fresh ambiguity challenges, committed hard-negative veto,
correct post-recovery continuation, unavailable images versus actual backend
failure, cache expiry, gallery recovery risks and default-off behavior.
The provenance tests also check cumulative versus consecutive box movement,
capture/replay clock alignment and target-present normalization. The normal
`tools/thesis_build.sh --packages-select thesis_bringup` build passes.

Retained review files:

- [Source provenance](tim_resilience_development_20260907/source_provenance.json): exact four source paths, source/reference hashes and replay metadata.
- [Seq03 frame evidence](tim_resilience_development_20260907/seq03_event.json): frames 1075--1082, all candidates, state, geometry, appearance source/age, crop provenance and physical attribution.
- [Frame audits](tim_resilience_development_20260907/frame_audits.json): all 20 cells, transitions, false-rejection categories and memory-update checks.
- [Selected development configuration](tim_resilience_development_20260907/available_image_challenge.yaml): SHA-256 `a8c8092199f6ad7659ef00226e77b3181b72c9e2fb89bb0e8e2c86c91a43cd5c`.

Reproduction uses `tools/experiments/run_tim_resilience_development.py`
with `--candidate NAME --repeat 1` and `--repeat 2`, followed by
`--summarize`. Repeat 3 is the final baseline control. The runner refuses to
overwrite existing runs; its destinations are study-specific, so reproduction
requires those derived destinations to be absent in a separate working copy
with the same retained source evidence. Do not delete the retained study to rerun it.
`--retain` exports only a complete, repeated, source-verified study with
matching service probes. Detailed frame reconstruction uses
`tools/analysis/analyse_tim_resilience_evidence.py`; service instrumentation
uses `tools/experiments/profile_tim_resilience_service.py`. These reuse the
existing deterministic replay and physical-v2 evaluator.

### Scientific limits and next freeze

H01/H02/H03 were not captured, inspected or used. All results are development
results, including the protocol-amended fourth candidate. No held-out
generalization claim follows from this selection. Correlated gallery evidence,
gradual drift below geometric gates, absence of a qualifying challenger and
handover during image gaps remain limitations. The available-image policy
retains bounded cached evidence in those gaps; it cannot infer unobserved
identity changes. The original anchor protection remains necessary on this
evidence. No detector, ReID model, global recovery threshold or cache TTL was
changed.

The canonical YAML remains at SHA-256
`0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`.
All experimental switches default off; the selected configuration enables
only the challenge and available-image behavior, not gallery consensus.
Historical #89/#90 reports, algorithm freeze
`2476991d262f7f388930aece0d731745f20dc1b3`, split v3 and final-comparison v2
remain unchanged. They do not describe the selected candidate if adopted.

Before final capture, review this development result, adopt the selected
configuration if approved, then record a new prospective algorithm commit
and canonical configuration hash with new split/comparison versions (for
example split v4 and comparison v3). Preserve the old files and reserved
H01/H02/H03 membership; do not weaken gates. No such freeze is created here.
Issue #58 / PR #99 and its branch are unchanged; any later runner/contract
version alignment is separate work. Final held-out capture must wait for
that reviewed prospective authority.
