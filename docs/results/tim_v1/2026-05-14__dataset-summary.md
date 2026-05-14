# TIM-V1 Dataset Recording Summary - 2026-05-14

Recorded full raw dataset bags using `--record-dataset`.

## Valid raw bags

All listed bags contain `/camera/image_raw`, `/detections`, `/tracks`, `/target`, `/target_memory`, `/target_memory/status`, and timing topics.

| Bag | Duration | Raw frames | Use |
|---|---:|---:|---|
| `tim_v1_clean_single_target_raw` | 139.4 s | 1702 | single-target sanity check |
| `tim_v1_two_person_no_crossing_raw` | 51.8 s | 658 | not useful, target was not selected |
| `tim_v1_simple_crossing_raw` | 62.5 s | 873 | controlled crossing |
| `tim_v1_long_occlusion_raw` | 59.5 s | 837 | occlusion/reacquisition |
| `tim_v1_hard_reentry_id_switch_raw` | 67.9 s | 974 | hard re-entry/id-switch case |
| `tim_v1_mixed_stress_raw` | 69.9 s | 925 | mixed stress/diagnostic bag |

## Initial analysis notes

### Clean single target

After selection, TIM and raw target were both fully valid. Useful as a sanity and latency check.

### Two-person no crossing

TIM never left `NO_TARGET`; target was not selected. Not useful for TIM evaluation unless replayed/annotated differently.

### Simple crossing

Raw valid duration after selection: 35.300 / 45.835 s.  
TIM valid duration after selection: 45.665 / 45.665 s.  
Reacquired events: 2.  
Appearance used: 2 rows.

### Long occlusion

Raw valid duration after selection: 12.376 / 40.990 s.  
TIM valid duration after selection: 40.986 / 40.986 s.  
Reacquired events: 2.  
Appearance used: 2 rows.

### Hard re-entry / ID switch

Raw valid duration after selection: 33.656 / 46.206 s.  
TIM valid duration after selection: 45.790 / 46.092 s.  
Reacquired events: 5.  
Appearance used: 8 rows.

### Mixed stress

Raw valid duration after selection: 31.083 / 61.690 s.  
TIM valid duration after selection: 55.732 / 61.502 s.  
UNCERTAIN rows: 63.  
LOST rows: 31.  
REACQUIRED rows: 43.  
Appearance used: 28 rows.  
This is useful as a stress/diagnostic bag, but not as a clean controlled scenario.
## Offline replay validation: two-person no-crossing
The original `tim_v1_two_person_no_crossing_raw` bag did not contain a live target selection. It was replayed using only clean input topics (`/camera/image_raw` and `/detections`), then target ID 1 was selected during replay and a new eval bag was recorded:

- `artifacts/bags/eval/tim_v1_two_person_no_crossing_clean_replay_id1`

Result:

- Raw valid duration after selection: 115.395 / 115.395 s
- TIM valid duration after selection: 115.395 / 115.395 s
- TIM state sequence: `NO_TARGET -> LOCKED`
- Reacquisition events: 0
- TIM latency p95: 1.0675 ms
- TIM latency p99: 1.3623 ms
- Appearance enabled: yes
- Valid appearance rows: 291 / 590
- Appearance-used rows: 0

Interpretation:

This confirms that offline raw-only replay with manual target selection works. It also provides a clean two-person no-crossing stability baseline: TIM remains stable in the presence of a distractor, and appearance is not used because no ambiguous association occurred.
