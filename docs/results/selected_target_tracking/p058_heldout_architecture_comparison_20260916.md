# Issue #27 / #58 prospective held-out architecture closure

Date: 16 September 2026  
Evidence class: final held-out protocol-repair evidence under the unchanged
Stage-7 prospective authority

## Authority and claim boundary

- Split: `tim_mars_split_v4_2026_09_08`
- Comparison: `tim_mars_final_comparison_v3_2026_09_08`
- Algorithm authority: `79f11b631688889bf5ffbeb3c16ef543a53f9973`
- Canonical TIM-MARS SHA-256:
  `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c`
- Final evidence run:
  `reports/p058_final_architecture_comparison/p058_final_architecture_protocol_repair_v2_20260916_184554`
- Clean run commit: `dc4c5c39cfbe9911b63cb9757d01ca3de096f696`
- Result: 12/12 cells valid, zero bootstrap failures, zero other failures;
  all physical-v2 duration reconciliations pass.

No threshold, model, tracker parameter, TIM-MARS logic, bootstrap instant,
bootstrap frame budget, physical-v2 rule, or evaluation semantic was changed
after held-out access. The final run is labelled protocol-repair evidence and
must not be described as a new prospective freeze.

## Protected first run and protocol diagnosis

The first prospective run remains immutable at
`reports/p058_final_architecture_comparison/p058_final_architecture_20260916_172556`.
Its independent Mac backup contains the same 92 files with exact file-by-file
SHA-256 equality. It reported 6 valid cells and 6 bootstrap failures.

Two implementation defects prevented the frozen bootstrap method from being
executed as written:

1. The resolver read the first `present_scored` reference time but ignored it,
   starting its tracker-frame budget at the beginning of the bag. H02's target
   first becomes scored at `3.266311891 s`; the first run compared that box
   against tracker frame 0. Initial detection messages also precede the first
   source image on H01/H02 (two messages) and H03 (one message), so those
   pre-reference messages incorrectly consumed DeepSORT's budget.
2. After time alignment, H02 showed a DeepSORT track above the IoU threshold
   at aligned frames 0, 1, and the frozen frame 2. The resolver selected the
   earliest match at frame 0; the runner then rejected it because the frozen
   DeepSORT instant is exactly frame 2. The corrected resolver evaluates the
   exact required frame and uses the physical-reference box at that frame.

The retained pre-edit diagnoses are
`p058_heldout_bootstrap_forensics_20260916.md` and
`p058_deepsort_predetermined_instant_forensics_20260916.md`.
The intermediate alignment-only run remains immutable at
`reports/p058_final_architecture_comparison/p058_final_architecture_protocol_repair_20260916_181235`
(11 valid cells; H02 DeepSORT rejected by the second defect). Its 132-file Mac
backup and the final run's 140-file Mac backup both have exact file-by-file
SHA-256 equality with the Pi.

These were protocol implementation defects. They were not tracker failures,
scenario limitations, or grounds for outcome-driven retuning. DeepSORT's
unchanged `n_init=3`, frame-2 instant, and three-frame budget are retained.

## Final per-scenario results

Values are seconds of physical-v2 correct / wrong-person /
lost-or-suppressed authority while the target is present. Identity-unresolved
duration is `0` in every cell. The final column is output during explicit
physical target absence and is separate from wrong-person authority.

| Scenario | Architecture | Correct | Wrong | LOST | Absent with output |
| --- | --- | ---: | ---: | ---: | ---: |
| H01 exit/re-entry | ByteTrack raw | 4.533121531 | 3.833477614 | 31.266607781 | 1.200480990 |
| H01 exit/re-entry | Target-ReID 0.90 | 2.633099069 | 0.000000000 | 37.000107857 | 0.000000000 |
| H01 exit/re-entry | ByteTrack + TIM-MARS | 30.016216755 | 0.099977678 | 9.517012493 | 0.000000000 |
| H01 exit/re-entry | DeepSORT raw | 9.316574000 | 0.099977678 | 30.216655248 | 0.000000000 |
| H02 crossing | ByteTrack raw | 16.066702430 | 15.899951887 | 13.666725519 | 0.233353659 |
| H02 crossing | Target-ReID 0.90 | 0.100030561 | 0.000000000 | 45.533349275 | 0.066536805 |
| H02 crossing | ByteTrack + TIM-MARS | 11.700053330 | 0.000000000 | 33.933326506 | 0.233353659 |
| H02 crossing | DeepSORT raw | 13.666611696 | 0.000000000 | 31.966768140 | 0.233353659 |
| H03 occlusion/distractor | ByteTrack raw | 27.232552230 | 16.867387125 | 1.999696322 | 0.000000000 |
| H03 occlusion/distractor | Target-ReID 0.90 | 0.467069612 | 0.000000000 | 45.632566065 | 0.000000000 |
| H03 occlusion/distractor | ByteTrack + TIM-MARS | 20.932933131 | 0.000000000 | 25.166702546 | 0.000000000 |
| H03 occlusion/distractor | DeepSORT raw | 45.183591414 | 0.066686546 | 0.849357717 | 0.000000000 |

Target-present time is `131.366222439 s` across H01-H03. Explicit target
absence is `31.333332107 s`; reference-gap time is `0.199664078 s` and
reference-unavailable time is `0 s`. Descriptive sums across the three
different scenarios are:

| Architecture | Correct s (% present) | Wrong s (% present) | LOST s (% present) | Absent with output s (% absent) |
| --- | ---: | ---: | ---: | ---: |
| ByteTrack raw | 47.832376191 (36.411%) | 36.600816626 (27.862%) | 46.933029622 (35.727%) | 1.433834649 (4.576%) |
| Target-ReID 0.90 | 3.200199242 (2.436%) | 0 (0%) | 128.166023197 (97.564%) | 0.066536805 (0.212%) |
| ByteTrack + TIM-MARS | 62.649203216 (47.690%) | 0.099977678 (0.076%) | 68.617041545 (52.233%) | 0.233353659 (0.745%) |
| DeepSORT raw | 68.166777110 (51.891%) | 0.166664224 (0.127%) | 63.032781105 (47.982%) | 0.233353659 (0.745%) |

The aggregate is descriptive; H01, H02, and H03 remain separate scenario
tests and are not independent repetitions of one condition.

## Defensible conclusion

TIM-MARS substantially changes raw ByteTrack's controller-facing safety:
across the three scenarios, measured wrong-person authority falls from
`36.600816626 s` to `0.099977678 s`, while correct authority rises from
`47.832376191 s` to `62.649203216 s`. The fixed-template Target-ReID baseline
also suppresses wrong-person output, but its `3.200199242 s` correct authority
shows severe availability loss. TIM-MARS therefore demonstrates value beyond
both raw tracking and a conservative similarity-threshold baseline.

TIM-MARS does not establish universal superiority over integrated DeepSORT.
It provides much more correct authority on H01 re-entry (`30.016 s` versus
`9.317 s`) and avoids DeepSORT's H03 wrong-person interval, while DeepSORT
provides more correct authority on H02 and especially H03. Descriptively,
DeepSORT has `5.517573894 s` more correct authority across H01-H03 but
`0.066686546 s` more wrong-person authority; both have the same measured
`0.233353659 s` target-absence output. The result is a scenario-dependent
safety-availability trade-off.

The retained development cost evidence completes that trade-off: ByteTrack +
TIM-MARS used about 8.9% less architecture CPU than DeepSORT on the controlled
Pi workload, but about 19.9% more mean architecture RSS. Its validated selected
target path met the predeclared rate and p95 latency targets in 3/3 runs;
DeepSORT's retained measurement is tracker-stage only and must not be presented
as an equivalent controller-facing latency result.

The supported thesis claim is therefore limited: the lightweight tracker plus
TIM-MARS architecture is a viable safety-oriented alternative that sharply
reduces raw-tracker identity authority failures and preserves far more useful
authority than simple Target-ReID. The evidence supports complementary,
scenario-dependent advantages relative to DeepSORT, not general dominance.

## Integrity

Final-run top-level SHA-256:

- `manifest_lock.json`: `d40f4e47264578422cc3ddb546e7e3a4b647eb5911fdb8aa761cee5a58409dc5`
- `run_provenance.json`: `26f584f1201a0cdf3e7aa6b11d374809de844ea512ed2f409bc7803a8e0a9667`
- `comparison_by_architecture.json`: `44365aac4117e709b93f694c8370151e10dd2f4b9ab83ab2a764801397c5e4d7`
- `comparison_by_architecture.csv`: `9daf0375ebb2ec386fe03f395f0e96046d77466449ad21aff037be431f140098`
- `comparison_by_architecture.md`: `1ad44d5951e82adb4e34087b32d236632d2bc6047ca91e585e3224c11b7239ed`

The final run was produced with a clean repository and is independently
backed up and hash-verified. The first prospective run and both corrective
runs remain retained; none was overwritten.
