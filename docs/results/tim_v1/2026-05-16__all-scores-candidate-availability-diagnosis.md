# TIM All-Scores Candidate Availability Diagnosis

Bag:

2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Manual wrong-target intervals:

- 69.32-101.20 s
- 110.84-116.31 s

## Goal

Check whether the true selected target was available as a candidate during the wrong-target intervals.

This uses the new `all_scores` export from `/target_memory/status`.

## Wrong interval 1: 69.32-101.20 s

Manual interpretation:

- TIM followed distractor ID 1.
- Selected target was believed to become ID 96 and later ID 142.

All-score result:

- distractor ID 1 appeared in 246 rows.
- ID 1 median total score: 0.932.
- ID 1 median appearance score: 0.000.
- true target ID 96 appeared in only 1 row.
- true target ID 96 total score: 0.244.
- true target ID 142 did not appear as a candidate.

Interpretation:

TIM could not reliably switch to the true target in this interval because the true target was not available as a stable candidate. The persistent distractor ID 1 dominated the candidate set with very strong geometric score.

## Wrong interval 2: 110.84-116.31 s

Manual interpretation:

- TIM followed distractor ID 1.
- Selected target was believed to become ID 161.

All-score result:

- distractor ID 1 appeared in 31 rows.
- ID 1 median total score: 0.897.
- ID 1 median appearance score: 0.000.
- true target ID 161 appeared in only 3 rows.
- ID 161 median total score: 0.262.
- ID 161 median appearance score: 0.000.

Interpretation:

The true target was only briefly available and had very weak association score. The distractor remained the dominant candidate.

## Conclusion

The main failure in these intervals is not that appearance selected the wrong person. Appearance was rarely used and the true target was mostly absent or weak in the candidate set.

The main failure is candidate availability:

- the detector/tracker did not provide a stable candidate for the selected person,
- TIM therefore stayed with the persistent geometrically strong distractor.

This means that the next improvement should not only be stronger appearance matching. TIM needs a recovery mechanism when the selected target is visible to a human but missing or weak in the tracker output.

## Next improvement direction

The strongest next direction is selective target recovery:

- use raw detections in addition to confirmed tracks,
- keep short-lived low-confidence target hypotheses,
- trigger ROI re-detection/refinement around the predicted target region,
- or explicitly search for a target-like candidate when TIM suspects wrong lock.

This connects the TIM failure mode to the planned selective refine / target recovery component.
