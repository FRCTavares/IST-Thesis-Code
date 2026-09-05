# Issue #90 — Long-gap global appearance reacquisition

## Status

Development-only validation completed on 5 September 2026. Long-gap global
protected-identity recovery is promoted to the canonical TIM-MARS configuration.

No H01--H03 held-out outcome was inspected during implementation, development
evaluation, forensic analysis, or promotion.

## Controlled comparison

For each development sequence, baseline and treatment used the same frozen
ByteTrack candidate stream.

The only algorithmic policy difference was:

- baseline: `global_reacquisition_enabled: false`
- treatment: `global_reacquisition_enabled: true`

All appearance thresholds, identity thresholds, persistence settings, tracker
settings, and timing settings remained unchanged.

The development treatment configuration SHA-256 was
`286779f7a95a279ed4d4b27ba8f20a4fcfaa781cf32e4c175364960c1e04e7f5`.

The final promoted canonical configuration SHA-256 is
`0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`. Its semantic policy matches the tested treatment; its file
hash differs because the canonical YAML promotion comment was also updated.

Global recovery begins after 9 missed frames, immediately after the retained
8-frame short-gap grace window. The global absolute appearance threshold remains
0.78. No threshold tuning was performed.

## Development physical-v2 results

| Sequence | Correct baseline (s) | Correct global (s) | Delta correct (s) | Wrong baseline (s) | Wrong global (s) | Delta wrong (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| May hard re-entry | 62.594003990 | 62.594003990 | +0.000000000 | 0.033394241 | 0.033394241 | +0.000000000 |
| Seq01 clean | 61.200516816 | 61.200516816 | +0.000000000 | 0.000000000 | 0.000000000 | +0.000000000 |
| Seq03 crossing | 22.532686264 | 25.067443244 | +2.534756980 | 0.000000000 | 0.133349425 | +0.133349425 |
| Seq04 occlusion/no-exit | 35.068442774 | 43.469299585 | +8.400856811 | 0.000000000 | 0.000000000 | +0.000000000 |

Seq03 lost/suppressed duration decreased by 2.668106405 s.

Seq04 lost/suppressed duration decreased by 8.400856811 s. Its
13.900030159 s physical target-absence interval retained zero controller-facing
output in both baseline and treatment.

## Global-recovery provenance

The treatment path was directly exercised:

- May hard re-entry: 105 global proposal rows and 309 candidate evaluations;
- Seq01 clean: no global proposal was required;
- Seq03 crossing: 4547 global proposal rows and 16231 candidate evaluations;
- Seq04 occlusion/no-exit: 3612 global proposal rows and 15080 candidate
  evaluations, with repeated successful global locks across tracker-ID changes.

## Seq03 forensic audit

The complete additional wrong-person exposure was 0.133349425 s and belonged to
tracker ID 9 between approximately 46.699661 s and 46.833011 s.

The sequence of events was:

- global recovery entered probation for ID 9 at 44.299463 s;
- ID 9 was accepted and LOCKED at 44.333037 s;
- the recovered output remained useful for roughly 2.37 s;
- at 46.699661 s the tracker box began overlapping an annotated distractor more
  strongly than the selected physical target;
- across the wrong-person interval, target IoU fell from approximately 0.565 to
  0.292 while best-distractor IoU increased from approximately 0.640 to 0.943;
- at 46.833011 s TIM detected a same-ID hijack through hard-negative evidence
  and transitioned from LOCKED to UNCERTAIN.

The additional wrong-person interval is therefore attributed to brief tracker
continuity drift after a successful global identity recovery, not to an
incorrect initial global identity acceptance. The baseline avoided the exposure
because it remained LOST.

This event does not justify changing the 0.78 global appearance threshold.

## Promotion decision

Development evidence supports promotion:

- May hard re-entry: no controller-facing regression;
- Seq01 clean: no controller-facing regression;
- Seq03: increased correct-target availability, with one 0.133349425 s
  post-reacquisition tracker-drift interval that TIM detected and suppressed;
- Seq04: substantial correct-target availability gain with no wrong-person
  output and no output during true target absence;
- protected-memory and comparison-versus-memory-update semantics remain
  unchanged;
- H01--H03 remain untouched.

These are development results only. Prospective held-out evaluation remains
owned by Issue #27.
