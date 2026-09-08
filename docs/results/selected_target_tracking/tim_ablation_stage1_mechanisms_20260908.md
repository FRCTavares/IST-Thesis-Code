# TIM-MARS Stage-1 AB-06 / AB-09 / AB-10 Development Ablation

Date: 8 September 2026.

This is development-only evidence. H01/H02/H03 were not captured, inspected or
used. The historical prospective split and comparison freezes remain unchanged.

## Control neutrality

The AB-06/AB-09/AB-10 development controls, with all new controls disabled,
were replayed on Seq03. The candidate-stream digest matched the expected frozen
candidate stream and the generated semantic digest exactly matched the retained
selected Seq03 digest:

    307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca

This establishes default-off neutrality for the new ablation plumbing.

## Opportunity scan

| Sequence | Conservative final rejects | Best hard-negative rejects | Any hard-negative candidate rejects | Final hard-negative rejects |
| --- | ---: | ---: | ---: | ---: |
| May | 0 | 0 | 199 | 0 |
| Seq01 | 0 | 0 | 662 | 0 |
| Seq03 | 0 | 46 | 633 | 0 |
| Seq04 | 0 | 73 | 611 | 0 |

## AB-06 — conservative final appearance filter

The selected executions contain no final `appearance_conservative_reject`
across May, Seq01, Seq03 or Seq04. Explicitly disabling only this final filter
on Seq03 also reproduces the selected semantic digest exactly.

**Classification: INACTIVE on the available development evidence.**

This classification is deliberately scoped to the permitted development set;
it does not claim that the filter can never fire on unseen conditions.

## AB-09 — hard-negative memory

Hard-negative memory is diagnostically active. The selected executions contain
46 Seq03 frames and
73 Seq04 frames where the
best candidate has `hard_negative_reject=true`. May and Seq01 have no such
best-candidate event. No selected development sequence has a final rejection
owned by `hard_negative_reject`.

Explicit AB-09 replays were therefore run on the two opportunity-bearing
sequences.

| Sequence | Correct selected / AB-09 (s) | Wrong selected / AB-09 (s) | LOST selected / AB-09 (s) |
| --- | ---: | ---: | ---: |
| Seq03 | 24.600414 / 24.600414 | 0.000000 / 0.000000 | 59.166384 / 59.166384 |
| Seq04 | 48.766241 / 48.766241 | 0.000000 / 0.000000 | 23.733801 / 23.733801 |

Seq03 preserves the physical-v2 outcome, state counts, reason counts and
appearance workload. Seq04 also preserves the complete physical-v2 outcome,
state counts and appearance workload. Its only aggregate policy difference is
six frames whose redundant rejection attribution moves from
`global_identity_recovery_reject` to
`protected_gallery_reacquisition_reject`.

**Classification: REDUNDANT on the available development evidence for
controller-facing behavior and appearance compute workload, while
diagnostically active.**

## AB-10 — positive-support same-ID hijack rejection

On Seq03, disabling only the missing/insufficient-positive-support part of the
same-ID hijack rejection changes the physical-v2 result from:

- correct authority: 24.600414 s to
  24.899310 s;
- wrong-person authority: 0.000000 s to
  1.099923 s;
- LOST/suppressed authority: 59.166384 s to
  57.767564 s.

The change gains 0.298896 s of correct authority but introduces
1.099923 s of wrong-person authority. This fails the asymmetric
safety criterion.

It also adds 26 backend/forced-fresh frames and 25 positive-memory-update
frames, demonstrating that the unsafe acceptance changes subsequent policy and
appearance workload rather than merely a diagnostic label.

**Classification: ESSENTIAL for the observed Seq03 safety behavior.**

## Stage-1 implication

Together with the 7 September AB-11/AB-18 decomposition:

- forced fresh same-ID challenges remain responsible for the selected
  candidate's observed development delta;
- the later general same-ID negative veto is redundant;
- the conservative final appearance filter is inactive on the available
  development evidence;
- hard-negative memory is diagnostically active but redundant for
  controller-facing behavior and appearance workload on the available
  development evidence;
- the positive-support same-ID hijack rejection is safety-essential on Seq03.

These are development classifications only. H01/H02/H03 remain untouched and
the historical prospective freeze is unchanged.

Exact replay commands, repository state, configuration/model hashes, candidate
and semantic digests, resolved-runtime fingerprints, full physical-v2 report
summaries, workload counters and deltas are retained in the companion JSON.
