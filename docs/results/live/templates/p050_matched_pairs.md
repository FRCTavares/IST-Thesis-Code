# #50 three-flight physical comparison — PENDING_PHYSICAL_EVIDENCE

Source: exact B-C-B RUN_ID/TAG bags, native Pixhawk DataFlash, reviewed
physical-person video annotation and visual-to-MCAP alignment. Analysis commit:
PENDING_PHYSICAL_EVIDENCE. The comparison is descriptive; do not populate from
TIM-MARS LOCKED state alone. Keep every attempt in the attempt inventory.

## Flight-level integrity

| Attempt RUN_ID / TAG | Flight role | Condition | Runtime package / DataFlash / annotation | Eligibility or rejection reason | Wrong-person non-zero [s] | Stale/invalid non-zero [s] | Recovery translation [s] | Unsafe motion / saturation / takeover |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| PENDING_PHYSICAL_EVIDENCE | Baseline A | baseline | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | N/A | PENDING_PHYSICAL_EVIDENCE |
| PENDING_PHYSICAL_EVIDENCE | Candidate | candidate | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE |
| PENDING_PHYSICAL_EVIDENCE | Baseline B | baseline | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | N/A | PENDING_PHYSICAL_EVIDENCE |

## All attempts and integrity

PENDING_PHYSICAL_EVIDENCE — list commissioning, ground, failed, aborted,
right-censored and ineligible RUN_ID/TAG attempts, exact source paths/hashes and
reasons. Do not silently replace attempts.

## Opportunity event evidence

For each O1/O2/O3 in each flight, record the exact
`run_logs/operator_events.jsonl` path/hash, matching start/end records and UTC
plus monotonic timestamps, scenario, 10.0 s horizon, operator outcome and any
note. Record physical loss/return annotations with their source and uncertainty
separately. The event markers do not establish reacquisition time.

## Opportunity-triplet outcomes

| Opportunity | Predeclared loss | Baseline A return [s] / censor | Candidate return [s] / censor | Baseline B return [s] / censor | Triplet eligible? | Candidate vs both baselines | Safety / attribution note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| O1 | right loss | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE |
| O2 | left loss | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE |
| O3 | distractor crossing + loss | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE | PENDING_PHYSICAL_EVIDENCE |

## Final controller decision

- Eligible opportunity triplets: PENDING_PHYSICAL_EVIDENCE.
- Candidate earlier than both baselines in: PENDING_PHYSICAL_EVIDENCE.
- Remaining opportunity no-worse condition: PENDING_PHYSICAL_EVIDENCE.
- Wrong-person/stale-invalid non-zero and recovery translation: PENDING_PHYSICAL_EVIDENCE.
- Unsafe motion, saturation and takeover comparison: PENDING_PHYSICAL_EVIDENCE.
- Retained policy and exact reason: PENDING_PHYSICAL_EVIDENCE.
- Physical-person/time-alignment uncertainty: PENDING_PHYSICAL_EVIDENCE.
- Limit: three opportunities inside each flight are repeated descriptive observations, not independent flight replicates; this comparison does not establish statistical superiority or formal safety.
