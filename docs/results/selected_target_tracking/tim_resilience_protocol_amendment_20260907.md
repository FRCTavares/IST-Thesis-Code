# Fourth candidate: available-image identity challenges

This amendment is recorded after the complete first comparison of the three
original candidates and before implementation/evaluation of the fourth.
It does not replace the original protocol or erase negative results.

The strict challenge candidate removes Seq03 wrong authority but loses
30.140331 s correct authority on May. The frame audit identifies 187
`same_id_fresh_challenge_reject` decisions: 140 `cached_same_image` and 47
`stale_image`. Repeated LOCKED -> UNCERTAIN -> REACQUIRED transitions explain
the regression. The May source has only 360 images for 950 tracker messages;
requesting another embedding cannot manufacture a new visual observation.

## Final candidate definition

`available_image_challenge` retains the challenge candidate's existing risk
predicate, selected-candidate interval bypass and unconditional committed
negative veto. It changes only the response when no new usable image exists:
for `cached_same_image`, `stale_image` or `no_image`, retain the original cache
attachment and existing identity safety gates rather than introducing a new
freshness-failure rejection. Cache TTL, generation, current crop restrictions,
same-ID identity threshold and hard-negative rejection are unchanged.

A new usable image still triggers fresh inference. Backend failure, invalid
image geometry, or an ineligible/failed crop still fails the challenge closed.
No cached feature becomes "fresh" merely because the image is unavailable.
The policy is opportunistic in visual sampling, not a stronger observability
claim: a handover occurring during an image gap remains an explicit limitation.

Hypothesis: the availability loss is caused by confusing a new tracker update
with a new appearance observation. Respecting the existing image sampling
contract should preserve the dense-image Seq03 safety benefit and remove much
of May's artificial recovery churn. This is falsified if wrong authority or
absence output increases, if correct authority still regresses materially, or
if memory safety degrades. The same four-sequence safety/availability/runtime
gates and repeated deterministic evaluations apply without modification.

This is the fourth and final candidate. No threshold sweep or gallery-policy
refinement will follow. Gallery consensus and the combined candidate remain
rejected unless their already recorded safety regressions can be explained as
an evidence-processing error; they will not be retuned to fit the sequences.

Canonical configuration, historical evidence, frozen split and prospective
comparison contract remain untouched. H01/H02/H03 remain inaccessible to this
development study. Any promotion remains subject to development review and a
new prospective freeze before final capture.
