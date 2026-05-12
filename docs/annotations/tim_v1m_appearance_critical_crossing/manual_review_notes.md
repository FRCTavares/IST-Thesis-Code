# Manual Review Notes - TIM-V1M Appearance-Critical Crossing

Bag:

artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

Reports:

reports/tim_v0/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing
reports/tim_v1_appearance/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

## Manual observations

- ID 1 is the selected person before the crossing/occlusion.
- ID 6 is the main distractor.
- Around 35.71-36.36 s, ID 6 completely occludes the selected target.
- ID 9 is the selected person after the first re-entry; it is the same person previously tracked as ID 1.
- Around 50.97-53.02 s, ID 6 again completely occludes the selected target.
- ID 10 is the selected person after the next re-entry; it is the same person previously tracked as IDs 1 and 9.
- From approximately 56.11 s onward, the selected person is clearly visible as ID 11 while the distractor remains ID 6.
- Therefore, the earlier assumption that 56.11-70.45 s was hidden/ambiguous was wrong. This interval is a visible-target interval, and accepting ID 6 there would be a wrong-target failure.

## Candidate-regime evidence from TIM status

Compressed best-candidate intervals after operator selection:

- 20.48-35.63 s: LOCKED, target ID 1, best ID 1.
- 35.71-36.31 s: UNCERTAIN/LOST, best ID 6.
- 36.36-50.97 s: LOST, best ID 9, appearance mean approximately 0.659 and max approximately 0.798.
- 51.02-53.01 s: LOST, best ID 6.
- 53.02-56.11 s: LOST/REACQUIRED, best candidate alternates between ID 10 and ID 6.
- 56.14-70.45 s: UNCERTAIN/LOST, best ID 6, but manual review shows the selected target is visible as ID 11.
- 70.55-72.72 s: LOST, best ID 11.

## Refined threshold sweep result

After refining the visibility annotation:

| accept_score_lost | correct ratio | wrong ratio | lost ratio | correct [s] | wrong [s] | lost [s] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.60 | 0.308 | 0.000 | 0.692 | 15.200 | 0.000 | 34.130 |
| 0.55 | 0.603 | 0.000 | 0.397 | 29.750 | 0.000 | 19.580 |
| 0.50 | 0.788 | 0.000 | 0.212 | 38.870 | 0.000 | 10.460 |
| 0.45 | 0.603 | 0.170 | 0.227 | 29.750 | 8.400 | 11.180 |

## Interpretation

This is an appearance-critical re-entry case and an acceptance-policy stress test.

TIM-V1 appearance was active and repeatedly selected plausible true-target candidates, especially ID 9 during 36.36-50.97 s. However, the default LOST-state acceptance threshold of 0.60 was too conservative to reacquire ID 9 early.

The later interval, 56.11-70.55 s, shows the opposite risk: the selected target is visible as ID 11 while the best candidate is often the distractor ID 6. This means permissive thresholds can create wrong-target output.

Representative rejected true-target candidates:

- t=36.355 s, best_track_id=9, best_total=0.560, best_appearance=0.451, threshold=0.600
- t=36.386 s, best_track_id=9, best_total=0.570, best_appearance=0.495, threshold=0.600

Representative risk interval:

- 56.11-70.55 s: target visible as ID 11, distractor ID 6 often appears as best candidate.

## Conclusion

This bag supports a careful threshold-tuning claim:

- accept_score_lost=0.60 is too conservative for hard true-target re-entry.
- accept_score_lost=0.50 gives the best result on this bag.
- accept_score_lost=0.45 is too permissive and introduces wrong-target duration.
- The live default should not be changed from this single bag alone.
