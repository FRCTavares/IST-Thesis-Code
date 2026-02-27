# Runbook

Quick recipes for the four core operations.
All commands run from `$THESIS_ROOT/` unless noted.

---

## 1 — Record a raw bag

```bash
cd $THESIS_ROOT/bags/raw

ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker

# Immediately after Ctrl-C:
mv rosbag2_<auto-timestamp>  YYYY-MM-DD__slice__<tag>
# e.g.: mv rosbag2_2026-02-28-09_30_00  2026-02-28__slice__lab01
```

**Output:** `bags/raw/YYYY-MM-DD__slice__<tag>/`

---

## 2 — Run eval replay

Replays a raw detections bag through the tracker and records the result.

```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/2026-02-25__slice__primary \
  tracker:=sort
```

Override the date if re-running an old bag:
```bash
  run_date:=2026-02-27
```

**Output:** `bags/eval/YYYY-MM-DD__eval__<rawbag>__<tracker>/`

---

## 3 — Analyse timing

Reads `/timing` (and `/timing_tracker` if present) from a raw bag.

```bash
python3 tools/analyse_bag_timing.py \
  bags/raw/2026-02-25__slice__primary
```

**Outputs:**
- `reports/timing/<bag>__timing.md`
- `figures/timing/<bag>/` (PNG plots)

---

## 4 — Analyse tracking

Reads `/target` and `/timing_tracker` from an eval bag.

```bash
python3 tools/analyse_bag_tracking.py \
  bags/eval/2026-02-27__eval__2026-02-25__slice__primary__sort
```

Tag is auto-detected from the bag name; pass `--tag` to override.

**Outputs:**
- `reports/tracking/<evalbag>/summary.md`
- `reports/tracking/<evalbag>/target_lock_timeseries.png`
- `reports/tracking/<evalbag>/track_ms_cdf.png`
- `reports/tracking/<evalbag>/reacq_hist.png`

---

## Where outputs go

| Type | Location |
|---|---|
| Raw bags | `bags/raw/YYYY-MM-DD__slice__<tag>/` |
| Eval bags | `bags/eval/YYYY-MM-DD__eval__<rawbag>__<tracker>/` |
| Timing reports | `reports/timing/` |
| Tracking reports + plots | `reports/tracking/<evalbag>/` |
| Timing figures | `figures/timing/<bag>/` |
| Tracking figures | `figures/tracking/` |
| Comparison reports | `reports/compare/` |
