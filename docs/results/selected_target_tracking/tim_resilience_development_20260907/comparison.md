# Complete development comparison

Durations use the unchanged physical-v2 evaluator. Percentages use target-present evaluable time.

| Sequence | Candidate | Correct s | Correct % | Wrong s | Wrong % | Lost s | Lost % | Absent-output s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| may | baseline | 62.594004 | 92.233 | 0.033394 | 0.049 | 5.237512 | 7.718 | 0.000000 |
| may | challenge | 32.453673 | 47.821 | 0.033394 | 0.049 | 35.377843 | 52.130 | 0.000000 |
| may | gallery_consensus | 62.594004 | 92.233 | 0.033394 | 0.049 | 5.237512 | 7.718 | 0.000000 |
| may | combined | 32.453673 | 47.821 | 0.033394 | 0.049 | 35.377843 | 52.130 | 0.000000 |
| may | available_image_challenge | 62.796330 | 92.531 | 0.033394 | 0.049 | 5.035186 | 7.419 | 0.000000 |
| seq01 | baseline | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 | 0.000000 |
| seq01 | challenge | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 | 0.000000 |
| seq01 | gallery_consensus | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 | 0.000000 |
| seq01 | combined | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 | 0.000000 |
| seq01 | available_image_challenge | 61.200517 | 100.000 | 0.000000 | 0.000 | 0.000000 | 0.000 | 0.000000 |
| seq03 | baseline | 25.067443 | 29.925 | 0.133349 | 0.159 | 58.566005 | 69.916 | 0.000000 |
| seq03 | challenge | 24.600414 | 29.368 | 0.000000 | 0.000 | 59.166384 | 70.632 | 0.000000 |
| seq03 | gallery_consensus | 68.532987 | 81.814 | 3.767221 | 4.497 | 11.466590 | 13.689 | 0.000000 |
| seq03 | combined | 69.867360 | 83.407 | 0.133762 | 0.160 | 13.765677 | 16.433 | 0.000000 |
| seq03 | available_image_challenge | 24.600414 | 29.368 | 0.000000 | 0.000 | 59.166384 | 70.632 | 0.000000 |
| seq04 | baseline | 43.469300 | 59.958 | 0.000000 | 0.000 | 29.030742 | 40.042 | 0.000000 |
| seq04 | challenge | 48.766241 | 67.264 | 0.000000 | 0.000 | 23.733801 | 32.736 | 0.000000 |
| seq04 | gallery_consensus | 46.503111 | 64.142 | 0.000000 | 0.000 | 25.996931 | 35.858 | 0.000000 |
| seq04 | combined | 51.299976 | 70.759 | 0.066783 | 0.092 | 21.133282 | 29.149 | 0.000000 |
| seq04 | available_image_challenge | 48.766241 | 67.264 | 0.000000 | 0.000 | 23.733801 | 32.736 | 0.000000 |

Every cell has zero identity-unresolved and reference-unavailable duration.
Reference gaps are 0 s (May/Seq01), 0.100453371 s (Seq03), and 0.100883795 s (Seq04).
Target absence is 13.900030159 s in Seq04 and zero elsewhere; absence-output percentage is 0% in Seq04 and undefined elsewhere.
All remaining buckets, publication correctness, state/rejection counts and cache/workload counters are retained in summary.json.

## Aggregate target-present accounting

| Candidate | Present s | Correct s | Correct % | Wrong s | Wrong % | Unresolved s | Lost s | Lost % | Publication correctness % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 285.332266 | 192.331264 | 67.406 | 0.166744 | 0.058 | 0.000000 | 92.834259 | 32.535 | 99.913379 |
| challenge | 285.332266 | 167.020845 | 58.536 | 0.033394 | 0.012 | 0.000000 | 118.278027 | 41.453 | 99.980010 |
| gallery_consensus | 285.332266 | 238.830619 | 83.703 | 3.800615 | 1.332 | 0.000000 | 42.701032 | 14.965 | 98.433584 |
| combined | 285.332266 | 214.821526 | 75.288 | 0.233939 | 0.082 | 0.000000 | 70.276802 | 24.630 | 99.891219 |
| available_image_challenge | 285.332266 | 197.363502 | 69.170 | 0.033394 | 0.012 | 0.000000 | 87.935370 | 30.819 | 99.983083 |
