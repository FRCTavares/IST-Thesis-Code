# Output freshness contract

Contract version: `tim_mars_output_freshness_v1`

This contract prevents a previously valid target from remaining authoritative
only because it is the latest value available. It is shared by live control,
TIM-MARS status, dashboard diagnostics, recordings, and the authoritative
offline target evaluators.

## Canonical rule

The frozen live profile uses a maximum output age of **0.90 seconds** and a
future-timestamp tolerance of **0.05 seconds**. The maximum is configurable, but
every recorded run and evaluation report must store the selected value.

Freshness is evaluated against the source observation timestamp, not only the
time at which a local subscriber received the message. Live control additionally
requires the local receive age to be within the same maximum.

| Condition | Classification | Consumer behavior |
|---|---|---|
| source and receive ages are within the inclusive maximum | `fresh` | output may be consumed |
| no positive source timestamp | `invalid_source` | fail closed |
| source is beyond future tolerance | `future_source` | fail closed |
| receive time is beyond future tolerance | `future_receive` | fail closed |
| source timestamp is older than the preceding callback | `non_monotonic_source` | fail closed |
| source timestamp duplicates the preceding live callback | `duplicate_source` | fail closed |
| source age exceeds the maximum | `stale_source` | fail closed / classify lost |
| receive age exceeds the maximum | `stale_receive` | fail closed |

Offline latest-preceding sampling intentionally permits a duplicate held value
until its source age exceeds the maximum. Once stale, all ID, event-type, and
bbox evaluators classify it as lost and add its interval to
`stale_output_duration_s` (or `stale_output_s`). Duplicate bag records at the
same timestamp use the later record; non-monotonic timestamp records are
discarded rather than allowed to refresh output.

## Live propagation

- The tracker copies the source timestamp from timing context. If the separate
  `/timing` callback arrives after `/detections`, it deterministically falls back
  to the detection header, which represents the same source image.
- TIM-MARS copies the tracker frame/source context into `TargetState` and adds
  the contract, classification, source age, and configured maximum to
  `/target_memory_mars/status`.
- The dashboard already transports that status JSON unchanged.
- `control_ref_node` checks source age and local receive age independently and
  immediately publishes zero for every non-fresh classification. Replayed old
  messages therefore cannot regain authority by arriving recently.
- `flight_metadata.txt` records the contract, maximum age, and enabled source/
  receive gates. The `/target_memory_mars/status` topic records the per-frame
  result.

The source timestamp and the comparison clock must share a ROS clock domain.
An invalid or non-comparable timestamp fails closed; it is never silently
replaced with subscriber arrival time.
