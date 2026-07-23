# P0.17 wrong-target oracle audit

Date: 2026-07-23

## Reason for the audit

The first P0.17 closure described the final development row as having zero
physical wrong-target output. Visual review of the May comparison found a
counterexample around `41.30–41.33 s`: TIM-MARS publishes tracker ID `41` on
the striped-shirt distractor while the selected black-shirt target remains ID
`1`. At the same moment, the ID `1` tracker box expands across both people, so
the spatial evaluator accepts the distractor even though the annotated-ID
evaluator correctly reports it as wrong.

The zero-wrong-target claim is therefore withdrawn.

## Frozen replay identity

- Algorithm commit:
  `c5ba9d30997e47c7f555baee5257bc687698508a`
- Canonical configuration SHA-256:
  `e7620313be428cac4d2d1f5595dc48b1f6127a43c22f1b4149049beba1e207ff`
- MARS model SHA-256:
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- Replay root:
  `bags/replay/p028_component_ablation_c5ba9d30_2026-07-23/`
- Evaluation step: `0.05 s`
- Maximum output age: `0.90 s`
- Repository state recorded by every replay: clean

The replay metadata records each source bag manifest, annotation, selected
target, resolved runtime, exact command, configuration, model, commit, and
repository state.

## Wrong-target results

| Development sequence | Raw spatial [s] | Raw annotated-ID [s] | TIM spatial [s] | TIM annotated-ID [s] |
| --- | ---: | ---: | ---: | ---: |
| May hard re-entry | 4.429 | 7.927 | 0.000 | 0.100 |
| June Seq01 | 0.000 | 0.000 | 0.000 | 0.000 |
| June Seq03 OC-SORT | 0.000 | 0.100 | 0.000 | 0.950 |
| June Seq04 OC-SORT | 0.310 | 0.450 | 0.000 | 0.250 |
| **Aggregate** | **4.739** | **8.477** | **0.000** | **1.300** |

TIM-MARS improves wrong-target duration substantially relative to raw under
both oracles. It is not flawless. The two oracle totals are bounds with
different failure modes and must not be collapsed into one timeless result:

- spatial agreement is optimistic when the reference tracker bbox merges
  people;
- annotated-ID agreement is conservative when the same physical target is
  fragmented into a new tracker ID.

## Commands

For each sequence, the audit ran:

```bash
python3 tools/analysis/evaluate_tim_target_correctness.py \
  <final-row-bag> \
  --annotations <annotation.csv> \
  --out-dir /tmp/p028_oracle_audit/<sequence>/id \
  --step-s 0.05 \
  --max-output-age-s 0.9 \
  --timebase header

python3 tools/analysis/evaluate_tim_target_bbox_correctness.py \
  <final-row-bag> \
  --annotations <annotation.csv> \
  --out-dir /tmp/p028_oracle_audit/<sequence>/bbox \
  --max-output-age-s 0.9
```

The audited annotations are:

- `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- `docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq03_ocsort_305578f3.csv`
- `docs/data/annotations/june_hard_sequences/seq04_ocsort_305578f3.csv`

## Corrected claim boundary

The development evidence supports this claim:

> At the frozen P0.17 configuration, TIM-MARS reduced wrong-target duration
> relative to the raw selected-target stream under both the optimistic spatial
> oracle and the conservative annotated-ID oracle.

It does not support a zero-wrong-target, flawless, tracker-independent, or
held-out generalisation claim. H01–H03 remain required for the final thesis
claim.
