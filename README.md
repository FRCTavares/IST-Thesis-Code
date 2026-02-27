# Thesis workspace

## Folder map

### Source (edited by hand)
| Path | Contents |
|---|---|
| `ros2_ws/src/` | ROS 2 packages (nodes, launch files, msgs) |
| `tools/` | Analysis scripts (`analyse_bag_timing.py`, `analyse_bag_tracking.py`) |
| `infer_service/` | ZMQ inference service scripts (run inside Docker) |
| `Written Logs/` | Weekly + daily logs, `useful_commands.md` |

### Data (generated — do not edit by hand)
| Path | Contents |
|---|---|
| `bags/raw/` | Raw recorded bags (detections, timing) |
| `bags/eval/` | Eval bags produced by `eval_replay.launch.py` (tracks, target, timing_tracker) |
| `bags/tmp/` | Scratch; safe to delete |

### Outputs (generated)
| Path | Contents |
|---|---|
| `reports/timing/` | Timing markdown reports from `analyse_bag_timing.py` |
| `reports/tracking/` | Tracking markdown reports + plots from `analyse_bag_tracking.py` |
| `reports/compare/` | Cross-tracker comparison reports |
| `figures/timing/` | Timing plots |
| `figures/tracking/` | Tracking plots (if separated from reports) |
| `figures/compare/` | Cross-tracker comparison plots |

---

## Naming conventions

### Raw bags — `bags/raw/`
```
YYYY-MM-DD__slice__<tag>
```
Example: `2026-02-26__slice__longrun`

Record with `-o` pointing directly to the final name, or rename immediately after stopping:
```bash
mv rosbag2_<auto-timestamp> YYYY-MM-DD__slice__<tag>
```

### Eval bags — `bags/eval/`
```
YYYY-MM-DD__eval__<rawbag>__<tracker>
```
Example: `2026-02-27__eval__2026-02-25__slice__primary__sort`

These are created automatically by `eval_replay.launch.py` — do not rename manually.

---

## Common commands

### Record a raw bag
```bash
cd $THESIS_ROOT/bags/raw
ros2 bag record --storage mcap \
  --topics /detections /timing /tracks /target /timing_tracker
# Then rename:
mv rosbag2_<timestamp> YYYY-MM-DD__slice__<tag>
```

### Run eval replay (records to `bags/eval/`)
```bash
ros2 launch thesis_bringup eval_replay.launch.py \
  bag:=$THESIS_ROOT/bags/raw/<YYYY-MM-DD__slice__tag> \
  tracker:=sort
```

### Analyse timing
```bash
python3 tools/analyse_bag_timing.py \
  $THESIS_ROOT/bags/raw/<YYYY-MM-DD__slice__tag>
# Output: reports/timing/<bag>__timing.md  +  figures/timing/<bag>/
```

### Analyse tracking
```bash
python3 tools/analyse_bag_tracking.py \
  $THESIS_ROOT/bags/eval/<YYYY-MM-DD__eval__rawbag__tracker>
# Output: reports/tracking/<evalbag>/summary.md  +  3 PNG plots
```

### Rebuild ROS 2 workspace
```bash
cd $THESIS_ROOT/ros2_ws
colcon build --packages-select thesis_bringup thesis_tracker thesis_interfaces
source install/setup.bash
```
