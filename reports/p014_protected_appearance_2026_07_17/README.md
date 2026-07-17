# P1.4 Protected and Adaptive Appearance Memory

Date: 17 July 2026

## Decision

The protected/adaptive appearance-memory implementation passed the deterministic
safety and repeatability gates and was promoted to the canonical TIM-MARS
configuration.

Accepted settings:

- `appearance_protected_memory_enabled: true`
- `appearance_trusted_gallery_max_entries: 4`
- `appearance_gallery_min_anchor_similarity: 0.75`
- `appearance_trusted_lock_frames_before_update: 2`
- `hard_negative_max_positive_similarity: 1.01`

The hard-negative positive-similarity exclusion remains disabled above the
cosine-similarity range. Provenance-bearing hard-negative memory is implemented,
but no exclusion threshold was promoted without separate replay evidence.

## Memory architecture

The implementation separates:

- an immutable operator-selection anchor;
- a bounded trusted multi-pose gallery;
- an adaptive recent prototype;
- a provenance-aware hard-negative gallery.

Risky ID-switch and long-gap authorization uses protected anchor or trusted
gallery evidence. Adaptive similarity cannot independently authorize a new
lineage after adaptation to that lineage.

Gallery-supported authorization also requires:

- a memory-eligible crop;
- a non-ambiguous candidate;
- no unresolved hard-negative rejection;
- immutable-anchor similarity of at least `0.75`.

Positive memory is not updated on the first accepted ID-switch frame. Updates
require stable trusted `LOCKED` operation and are blocked during uncertainty,
loss, unconfirmed reacquisition, ambiguity, hard-negative conflict, and
memory-ineligible crop conditions.

## Canonical A/B results

| Sequence | Correct baseline [s] | Correct P1.4 [s] | Wrong baseline [s] | Wrong P1.4 [s] | Lost baseline [s] | Lost P1.4 [s] | Absent output baseline [s] | Absent output P1.4 [s] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| May | 64.750 | 63.380 | 0.000 | 0.000 | 2.950 | 4.320 | 0.000 | 0.000 |
| Seq01 | 122.340 | 122.340 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Seq03 | 61.236 | 65.395 | 27.538 | 12.284 | 6.953 | 18.048 | 0.000 | 0.000 |
| Seq04 | 42.897 | 40.343 | 1.358 | 0.000 | 12.567 | 16.479 | 0.762 | 0.000 |

Aggregate deltas:

- correct-target duration: `+0.235 s`;
- wrong-target duration: `-16.612 s`;
- lost-target duration: `+16.377 s`;
- target-absent output duration: `-0.762 s`.

No evaluated sequence increased wrong-target or target-absent publication.
The accepted result is safer but more conservative.

## Loss attribution

At the evaluator's 50 ms resolution, added correct-target loss was:

- `2.900 s` in ID-switch situations;
- `1.904 s` in same-ID long gaps;
- `1.050 s` in same-ID short gaps.

The dominant added abstention occurred during the risky transitions that the
protected-memory design is intended to govern.

## Deterministic repeatability

Three corrected Seq04 runs each produced:

- 1547 target messages;
- 1547 status messages;
- `40.343 s` correct output;
- `0.000 s` wrong output;
- `16.479 s` lost output;
- `0.000 s` target-absent output.

Shared semantic SHA-256 values:

- target stream:
  `16dffb2fa6462bb25cb1ef6a071d9809332fba669ef9f62c48525068d78fd6f7`;
- status stream:
  `00d6e3d2375a31b08accd566b2bcc73d723de3f3c655e3aeb81c85c134e8bcf0`.

## Configuration provenance

The exact replay profile and the promoted canonical YAML contain identical
parameter values. Their file hashes differ only because the replay profile
retains an obsolete pre-promotion comment for exact provenance.

- accepted replay-profile SHA-256:
  `9028966c4efb98a03ebdec00f237df411e398cccbd9b8e32ecfd5ddae4718007`;
- promoted canonical SHA-256:
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`;
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`.

Evidence paths:

- replay bags:
  `bags/replay/p014_protected_memory_2026_07_17/protected_anchor075/`;
- exact replay profile:
  `tim_mars_replay_profile.yaml`;
- promoted canonical snapshot:
  `tim_mars_canonical_config.yaml`;
- A/B comparison:
  `canonical_comparison.tsv`;
- repeatability report:
  `seq04_repeatability.txt`;
- loss attribution:
  `loss_attribution.txt`.

## Claim boundary

The result supports safer selected-target publication on the four evaluated
ByteTrack sequences. It does not establish generalisation to arbitrary people,
trackers, environments, long absences, or visually identical identities.
