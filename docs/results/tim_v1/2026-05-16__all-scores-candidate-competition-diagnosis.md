# TIM All-Scores Candidate Competition Diagnosis

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Manual wrong-target intervals:

- 69.32-101.20 s
- 110.84-116.31 s

## Goal

Check whether the true selected target was available as a candidate during wrong-target intervals and why it lost to the distractor.

## Wrong interval 1: 69.32-101.20 s

Manual interpretation:

- TIM followed distractor ID 1.
- True target changed from ID 1 to IDs 98 and 115.

All-score result:

| Candidate | Rows | Median total | Median appearance | Interpretation |
|---|---:|---:|---:|---|
| Distractor ID 1 | 246 | 0.932 | 0.000 | dominant wrong candidate |
| True target ID 98 | 82 | 0.501 | 0.000 | present, but lower score |
| True target ID 115 | 124 | 0.516 | 0.000 | present, but lower score |

Interpretation:

The true target was present as a candidate, but it had much lower total score than the distractor. The distractor won mainly because of strong geometric continuity. Appearance did not help because appearance similarity was zero for the true target candidates.

## Wrong interval 2: 110.84-116.31 s

Manual interpretation:

- TIM followed distractor ID 1.
- True target was ID 144 and later ID 163.

All-score result:

| Candidate | Rows | Median total | Median appearance | Interpretation |
|---|---:|---:|---:|---|
| Distractor ID 1 | 31 | 0.897 | 0.000 | dominant wrong candidate |
| True target ID 144 | 2 | 0.921 | 0.000 | briefly strong and rank 0 |
| True target ID 163 | 25 | 0.546 | 0.000 | present, but lower score |

Interpretation:

The true target was available, especially as ID 163, but its score remained lower than the distractor. ID 144 was briefly strong, but not persistent enough to maintain the correct target.

## Updated conclusion

The failure is not pure candidate absence. The true target is often present in the candidate set, but loses to a persistent distractor because the geometry score strongly favours the old/distractor ID.

The current appearance feature does not solve this because the measured appearance similarity for the true target candidates is mostly zero. Therefore, simply increasing the appearance weight is unlikely to solve the problem reliably.

## Next improvement direction

The next TIM improvement should use candidate-hypothesis competition:

- keep multiple plausible candidate hypotheses during close crossings,
- compare the current target ID against persistent alternative IDs,
- use appearance evidence over multiple frames rather than a single-frame bonus,
- enter UNCERTAIN instead of staying confidently LOCKED when another candidate is plausible but identity is ambiguous,
- switch only when the alternative has stable evidence.

This is a stronger and safer novelty direction than simply lowering thresholds or increasing appearance weight.
