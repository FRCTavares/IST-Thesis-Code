# Future Flights

Use:

    docs/flight/field_day_runbook.md

That file is the canonical flight-day command sheet.

## Remaining physical work

Complete in this order:

1. passive MAVROS + recorder ground gate
2. controller compute-only ground gate
3. restrained / props-off MAVROS command-path gate
4. RC takeover / PreArm / failsafe check
5. baseline closed-loop following
6. loss / reacquisition trial
7. distractor crossing trial
8. yaw-recovery candidate only if explicitly approved after baseline review

## Important

Do not add `--record-raw` to field flights.

Do not enable yaw recovery for the baseline.

H01/H02/H03 source captures are already complete and are not part of these flights.

Detailed evidence requirements:

    docs/flight/retained_evidence_package.md

Manual moving-platform TIM-MARS trial:

    docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md
