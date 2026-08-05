# P1.11 Event and Recovery Metrics

## Purpose

Issue #26 extends the shared selected-target evaluator with event-level, recovery, status-occupancy and memory-lifecycle metrics. It does not change TIM-MARS runtime policy or its canonical parameters.

## Evidence

- Implementation commit: `b50f914aa2e7b985b0283e706f0e577779b4254e`
- Evidence directory: `reports/p026_event_recovery_b50f914a_2026_08_05`
- Canonical input: P018 hard-negative-lifecycle replay set
- Timebase: message header
- Sampling interval: `0.05 s`
- Maximum output age: `0.9 s`
- Stable recovery requirement: `0.25 s`
- Headerless status mapping: nearest header-bearing selected-target anchor
- Determinism: identical outputs across a complete second run
- Evidence hashes: all stored files verified
- Regression validation: `81 passed`

## Canonical results

| Sequence | Raw wrong (s) | TIM wrong (s) | Raw lost (s) | TIM lost (s) | Raw wrong bursts | TIM wrong bursts | Recovery attempts | Correct candidate suppressed (s) | Memory contamination events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| May hard reentry | 7.927 | 0.100 | 21.490 | 5.087 | 6 | 1 | 18 | 2.867 | 0 |
| June Seq01 clean | 0.000 | 0.000 | 66.790 | 13.590 | 0 | 0 | 0 | 0.000 | 0 |
| June Seq03 crossing | 0.100 | 0.950 | 63.027 | 15.379 | 1 | 6 | 84 | 4.816 | 9 |
| June Seq04 occlusion | 0.450 | 0.250 | 19.683 | 17.479 | 2 | 1 | 102 | 4.676 | 4 |

## TIM state occupancy

| Sequence | LOCKED | UNCERTAIN | LOST | REACQUIRED |
|---|---:|---:|---:|---:|
| May hard reentry | 0.925 | 0.027 | 0.041 | 0.007 |
| June Seq01 clean | 1.000 | 0.000 | 0.000 | 0.000 |
| June Seq03 crossing | 0.839 | 0.051 | 0.099 | 0.011 |
| June Seq04 occlusion | 0.592 | 0.032 | 0.372 | 0.004 |

## Findings

The clean Seq01 sequence remained entirely in `LOCKED`, with no wrong-target output, recovery attempts, suppression or memory contamination.

The May hard-reentry sequence reduced wrong-target output from `7.927 s` in the raw selected target to `0.100 s` in TIM-MARS. The memory-contamination count remained zero.

Seq03 crossing was the most identity-ambiguous sequence. TIM-MARS limited wrong-target output to `0.950 s`, but produced six short wrong-target bursts, 84 candidate attempts, `4.816 s` of correct-candidate suppression and nine memory-contamination events.

Seq04 occlusion produced `0.250 s` of TIM wrong-target output. Its 102 recovery attempts and `4.676 s` of correct-candidate suppression reflect prolonged ambiguity and absence handling. Four memory-contamination events were reported.

These results support the safety interpretation that TIM-MARS often converts sustained raw wrong-target output into LOST or suppressed output. The event metrics also show the cost of this safety policy: repeated candidate attempts, suppression and longer LOST occupancy in difficult scenes.

Memory-contamination events are evaluator classifications of memory updates associated with an incorrect identity. They do not alone prove persistent memory corruption or a later wrong-target publication.

## Semantic guarantees

- Correct, wrong-target, lost, target-absent and stale conditions remain separate.
- Raw selected-target and TIM output streams are reported independently.
- Sequence termination before recovery is reported as censored rather than as successful or failed recovery.
- Missing legacy status fields remain explicitly unavailable and are not inferred.
- Wrong-target output remains the principal safety failure; LOST and suppression remain distinct conservative outcomes.

## Promotion boundary

This is canonical development evidence using May and June sequences. September held-out evidence remains reserved for Issue #27 and must not be used to tune these metrics.
