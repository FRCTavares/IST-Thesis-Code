# Official 4-person TIM-MARS field recordings - 2026-06-19

## Keep

### SEQ01 - clean four-person baseline
- Source raw: PASS, 61.20 s, 1520 images, 24.84 FPS
- Field live: PASS, 108.16 s
- Field MAVROS: weak, only /mavros/state recorded
- Status: usable

### SEQ02 - four-person target re-entry
- Source raw: missing
- Field live: PASS, 151.37 s
- Field MAVROS: PASS, 127.67 s
- Status: usable as live onboard evidence

### SEQ03 - four-person crossing ambiguity
- Source raw: usable, 83.87 s, 1931 images, 23.02 FPS
- Field live: PASS, 97.55 s
- Field MAVROS: PASS, 78.87 s
- Status: usable, important sequence

### SEQ04 - four-person occlusion without frame exit
- Source raw: usable, 86.50 s, 2047 images, 23.66 FPS
- Field live: PASS, 66.43 s
- Field MAVROS: usable but short, 44.83 s
- Status: usable

## Missing or skipped

### SEQ05 - similar clothing
- Missing
- Status: skipped

### SEQ06 - raw stable control
- Missing
- Status: skipped

## Notes

SEQ02 has no matching source raw bag, so it should be treated as live onboard evidence only.
SEQ03 and SEQ04 have source raw bags and can be used for offline replay.
SEQ01 is a good stable baseline.
