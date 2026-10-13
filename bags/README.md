# bags/

Last reviewed: 2026-10-13

## Purpose

Local ROS 2 recordings made by the live stack: field/flight evidence, source
footage, and replay output. Bag data is **not tracked** by Git; only this README
is committed.

## Contents

| Folder | Written by | Role |
| --- | --- | --- |
| `live_camera/` | `start_live_stack.sh` (normal, `--field-record`) | Pipeline recordings and retained field runs: `<RUN_ID>__video[__<TAG>]/` |
| `source_video/` | `--source-record*` | Source-first raw recording root |
| `datasets/` | `--record-dataset` | Dataset-style recordings (raw imagery + telemetry) |
| `mavros/` | `--record-mavros` | Synchronized Pixhawk/MAVROS telemetry |
| `source/` | operators | Curated source, held-out and official-flight recordings kept for reference |
| `reference/` | operators | Known-good reference bags |
| `ground/` | operators | Ground-validation recordings |
| `replay/` | replay tools | Generated replay output; disposable |

## Rules

- Recordings are precious: never delete or overwrite a field run, a source
  recording or anything under `source/` without the owner's say-so. Failed and
  aborted runs are kept too.
- `replay/` is generated and can be removed once nothing depends on it.
- Recording stops when free space drops below `RECORDING_MIN_FREE_GIB`
  (`tools/lib/live_defaults.sh`); check `df -h` before a field day.
- Back up a field run off the Pi right after it (see
  [../docs/flight/field_day_runbook.md](../docs/flight/field_day_runbook.md)).
- Naming: `YYYY-MM-DD__HH-MM-SS__source__<campaign>__<seq>__<scenario>__<stream>`
  for source recordings; keep historic names unchanged.

## See also

- [../docs/OPERATIONS.md](../docs/OPERATIONS.md) - recording flags
- [../docs/flight/retained_evidence_package.md](../docs/flight/retained_evidence_package.md) - what a field run must contain
