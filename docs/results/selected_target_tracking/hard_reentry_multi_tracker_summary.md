# Canonical TIM-MARS selected-target evidence

## Evidence status

This is the active thesis-facing summary for the clean P0.4 canonical evidence
freeze.

Canonical compact reports:

- `reports/p004_tim_matrix_1b7dc400_2026_07_20/`
- `reports/p004_ocsort_tim_1b7dc400_2026_07_20/`

Clean replay commit:

- `1b7dc4002c19e5235703913826e174df1025f1d0`

Canonical fingerprints:

- TIM-MARS configuration:
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`
- MARS model:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`

Every clean replay records metadata schema `3`, resolved-runtime schema `2`,
the exact command, source bag manifest, selected tracker ID, repository commit
and state, effective runtime values and their sources, and SHA-256 sidecars.

## Canonical hard-reentry tracker matrix

| Tracker | Raw C/W/L | TIM-MARS C/W/L | Wrong delta | Absence-output delta | Verdict |
|---|---:|---:|---:|---:|---|
| ByteTrack | 0.514 / 0.000 / 0.486 | 0.920 / 0.010 / 0.069 | +0.700 s | +0.000 s | Reject |
| SORT | 0.442 / 0.000 / 0.558 | 0.786 / 0.080 / 0.134 | +5.300 s | +0.150 s | Reject |
| OC-SORT | 0.509 / 0.000 / 0.491 | 0.936 / 0.000 / 0.064 | +0.000 s | +0.200 s | Reject |
| DeepSORT | 0.366 / 0.001 / 0.633 | 0.755 / 0.225 / 0.020 | +15.203 s | +0.000 s | Reject |

Within-tracker raw-versus-TIM comparisons are valid. Absolute cross-tracker
ranking is not claimed because each tracker autonomously selected its own
physical target.

## Required OC-SORT sequences

| Sequence | Raw C/W/L | TIM-MARS C/W/L | Correct delta | Wrong delta | Lost delta |
|---|---:|---:|---:|---:|---:|
| Seq03 crossing ambiguity | 0.340 / 0.001 / 0.659 | 0.850 / 0.015 / 0.135 | +48.831 s | +1.350 s | -50.181 s |
| Seq04 occlusion/no-exit | 0.644 / 0.002 / 0.354 | 0.702 / 0.003 / 0.295 | +3.297 s | +0.050 s | -3.347 s |

Both repetitions match in generated semantic messages, topic counts,
authoritative aggregate evaluation, event-level evaluation, and effective
runtime after output-path normalisation.

## Scientific conclusion

TIM-MARS is modular at the tracker-output interface, but the current canonical
preset is not safety-portable across the evaluated trackers and sequences.

Correct-target availability can improve substantially, but any wrong-target or
target-absence degradation above the one-step `0.05 s` tolerance blocks safety
promotion.

## Annotation lineage

Hard-reentry matrix:

- `docs/data/annotations/may_hard_reentry/bytetrack_f17cdf80_autonomous.csv`
- `docs/data/annotations/may_hard_reentry/sort_f17cdf80_autonomous.csv`
- `docs/data/annotations/may_hard_reentry/ocsort_f17cdf80_autonomous.csv`
- `docs/data/annotations/may_hard_reentry/deepsort_f17cdf80_autonomous.csv`

OC-SORT sequence pair:

- `docs/data/annotations/june_hard_sequences/seq03_ocsort_305578f3.csv`
- `docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv`

## Digest-schema migration

The older promoted evidence stored semantic-digest schema `v1`. The clean P0.4
freeze stores schema `v2`. The literal digest strings are therefore not directly
comparable.

Recomputing both old and new bags under `v2` produced identical aggregate
digests and identical per-message records for all eight replay cases.

## Thesis-source status

This repository contains no tracked `.tex` or `.bib` thesis source. The old
paper and `reports/paper_final_tables_2026_07_04/final_result_tables.md` are
obsolete and are not authoritative evidence.

The current implementation, canonical configuration, deterministic runner
provenance, evidence catalogue, and promoted P0.4 reports are the source of
truth. Any final thesis methodology or result table must be written from those
current sources rather than reproducing obsolete paper values.

## Limitations

- The evidence is sequence- and tracker-specific.
- Manual annotations are tracker-ID-specific.
- The four-tracker matrix does not support absolute cross-tracker ranking.
- The canonical preset is frozen for reproducibility, not claimed as universal.
