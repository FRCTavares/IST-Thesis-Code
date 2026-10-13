# TIM-MARS

Last reviewed: 2026-10-13

Onboard selected-person tracking and following on a **Raspberry Pi 5 + Hailo-8**
with an RGB-only camera, built for a micro aerial robot (MAV) with a
Pixhawk flight controller.

**TIM-MARS** (Target Identity Memory with MARS appearance consistency) is the
selected-target identity layer. It sits between an appearance-free tracker and
the flight controller and is the only source of target authority the controller
accepts: *a wrong target is worse than a lost target*, so when identity evidence
is insufficient it publishes nothing instead of a likely distractor.

## What runs on the Pi

```
camera --> perception (YOLOv8s on Hailo-8) --> tracker (ByteTrack) --> raw /target
       --> TIM-MARS (target_memory_mars_node) --> /target_memory_mars
       --> control_ref_node --> /control_ref/cmd_vel (+ optional MAVROS mirror)
```

- **Platform:** Raspberry Pi 5, Hailo-8, Ubuntu 24.04, ROS 2 Jazzy,
  `ROS_DOMAIN_ID=42`.
- **Detector:** YOLOv8s compiled for Hailo-8, in-process HailoRT inference.
- **Tracker:** ByteTrack by default; SORT, OC-SORT and DeepSORT are selectable.
- **Controller input:** `/target_memory_mars` only. Raw `/target` never drives
  the aircraft.
- **Dashboard:** a separate repository, `FRCTavares/IST-Thesis-UI`.

## Start here

| I want to... | Read |
| --- | --- |
| Set up a new Pi / build the workspace | [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) |
| Run, record and stop the live stack | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Understand how the pieces fit together | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Fix a camera, Hailo or network problem | [docs/debug/](docs/debug/README.md) |
| Run a field / flight day | [docs/flight/](docs/flight/README.md) |
| Look up a tool or script | [tools/README.md](tools/README.md) |
| Understand the TIM-MARS algorithm | [docs/algorithm/](docs/algorithm/README.md) |

## Quick start (on the Pi)

```bash
cd ~/Desktop/Thesis-Code
direnv allow                      # ROS overlays, thesis_env, ROS_DOMAIN_ID=42
./tools/thesis_build.sh           # build ros2_ws
./tools/start_live_stack.sh --help
./tools/start_live_stack.sh --res vga          # camera + perception + tracker + TIM-MARS + control
```

At the `live-stack>` prompt: `ids` lists tracker IDs, `target <id>` selects the
person to follow, `stop` shuts everything down cleanly.

## Repository layout

| Path | Owns |
| --- | --- |
| `ros2_ws/` | The ROS 2 implementation: `thesis_msgs`, `thesis_tracker`, `thesis_bringup`. `src/` is tracked; `build/`, `install/`, `log/` are generated. |
| `tools/` | Build, live-stack launcher, host/network management, flight preflight and evidence verification, setup helpers, timing analysis, and their tests. |
| `models/` | Hailo `.hef` detector graphs and the MARS re-identification model, with provenance notes. |
| `docs/` | Setup, operations, architecture, algorithm contracts, field procedures, recovery runbooks. |
| `bags/` | Local ROS bag recordings (not tracked). Only `bags/README.md` is committed. |

Local and git-ignored: `thesis_env/` (project Python venv), `bags/` contents,
`ros2_ws/{build,install,log}`, `analysis_out/`.

## Tests

```bash
source /opt/ros/jazzy/setup.bash && source ros2_ws/install/setup.bash
python3 -m pytest -q -p no:cacheprovider tools/tests          # tooling and launcher contracts
cd ros2_ws && colcon test && colcon test-result --verbose      # ROS packages
```

## History and research material

This project began as a master's thesis at IST. The thesis analysis tooling,
experiment reports, annotation workflows and research documentation were removed
from this tree to keep it focused on operating the system. They remain in Git
history: tag `archive/thesis-final-20261013` is the last commit that contains
them.

## Licence

MIT, see [LICENSE](LICENSE). Source headers credit Francisco Tavares.
