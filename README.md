# Thesis-Code

Last reviewed: 2026-09-09

Onboard RGB-only selected-person tracking and following for a micro aerial
robot. The scientific core is **TIM-MARS**, a selected-target identity-memory
layer that sits between an appearance-free tracker and the flight controller
and is the only controller-facing target authority.

## System at a glance

- **Platform:** Raspberry Pi 5 + Hailo-8 for the full live stack; generic
  Linux for replay and offline analysis.
- **ROS 2:** Jazzy, `ROS_DOMAIN_ID=42`, workspace under `ros2_ws/`.
- **Detector:** YOLOv8s, direct in-process Hailo inference.
- **Tracker:** ByteTrack (canonical); SORT / OC-SORT / DeepSORT selectable.
- **Selected-target authority:** TIM-MARS (`target_memory_mars_node`).
- **Canonical path:** `perception_camera_node` -> `tracker_node` -> raw
  `/target` -> `target_memory_mars_node` -> `/target_memory_mars` ->
  `control_ref_node`. The controller consumes `/target_memory_mars` only;
  raw `/target` never drives control.
- **Frontend:** independently owned — `FRCTavares/IST-Thesis-UI`.

## Root layout

| Path | Owns |
| --- | --- |
| `ros2_ws/` | The ROS 2 implementation: `thesis_msgs`, `thesis_tracker`, `thesis_bringup`. `src/` is tracked; `build/`, `install/`, `log/` are local/generated. See `ros2_ws/README.md`. |
| `tools/` | Build, live-stack, evaluation-reproduction, analysis, annotation and host-recovery tooling. See `tools/README.md`. |
| `models/` | Detector `.hef` and ReID model binaries plus a per-file provenance inventory. See `models/README.md`. |
| `docs/` | Research contracts, frozen data definitions, procedures, reviewed result summaries, and the historical archive. Authority hierarchy: `docs/README.md`. |
| `bags/` | ROS bag data — protected source/flight recordings and disposable replay bags. Only `bags/README.md` is tracked; bag data and the retention policy live under `bags/README.md` and `docs/data/catalogue/`. |
| `reports/` | Locally generated analysis output, with a promotion path: a citable result exists here only as a reviewed evidence package force-added with provenance sidecars. Only `README.md` / `PROMOTED.md` and those packages are tracked. |
| `artifacts/` | Disposable, reproducible intermediate output (annotation/CVAT scratch, rendered media, run logs). `artifacts/README.md` is tracked; all generated contents are local and are never thesis authority. |
| `data/` | Imported external-benchmark datasets and locally processed frames, used only by the external-tracking comparison. Currently entirely local; a concise `data/README.md` will follow in a later folder pass. |

Local, git-ignored, not part of a clean checkout: `thesis_env/` (the
project-local Python venv, activated by `.envrc` when present). Legacy
generated `figures/` output is being consolidated into `artifacts/figures/`;
it is not an architectural root directory.

## Primary entrypoints

| Command | Purpose |
| --- | --- |
| `./tools/thesis_build.sh` | Build the ROS 2 workspace with repository-local colcon logs. |
| `./tools/start_live_stack.sh` | Start the live camera -> perception -> tracker -> TIM-MARS -> control/dashboard stack. Options: `--help`, `--help-advanced`. |
| `python3 tools/reproduce_tim_mars.py --set development` | Verify the frozen split and hashes, build, run the canonical evaluation matrix, and check provenance. |
| `./tools/start_ui_stack.sh` | Launch the external dashboard (`IST-Thesis-UI`). |

`tools/timing_contract.py` is the repository-wide schema-v4 timing contract,
imported as `tools.timing_contract`; it is not a CLI.

## Where to go

- **Build, live operation, and every tool:** `tools/README.md`
- **Experiments and replay:** `tools/experiments/README.md`
- **Evaluation and analysis:** `tools/analysis/README.md`,
  `docs/design/tim_tooling_index.md`
- **Field procedures:** `docs/flight/` (held-out capture, aircraft validation,
  high-resolution capture)
- **Results and evidence:** `docs/results/README.md`; claim boundaries in
  `docs/algorithm/tim_mars_evidence_versions.md`
- **Runtime metrics:** `docs/RUNTIME_METRICS.md`
- **Setup and recovery:** the Setup section below, then `docs/debug/`,
  `tools/setup/`, `tools/host/`
- **Documentation conventions:** `docs/design/README_STANDARD.md`

## Setup

Supported host: Ubuntu 24.04 with ROS 2 Jazzy.

```bash
git clone git@github.com:FRCTavares/IST-Thesis-Code.git "$HOME/Desktop/Thesis-Code"
cd "$HOME/Desktop/Thesis-Code" || exit 1

source /opt/ros/jazzy/setup.bash
sudo rosdep init 2>/dev/null || true
rosdep update
rosdep install --from-paths ros2_ws/src --ignore-src --rosdistro jazzy -r -y

python3 -m venv --system-site-packages thesis_env
thesis_env/bin/python -m pip install --upgrade pip pytest

./tools/thesis_build.sh
direnv allow          # loads .envrc: ROS overlays, thesis_env, ROS_DOMAIN_ID=42
```

The Hailo runtime is platform-specific (Raspberry Pi 5) and is installed
separately — see `tools/setup/`. The browser frontend is prepared in its own
repository: `cd ~/Desktop/IST-Thesis-UI && npm ci && npm run build`.

## Rules

- The only tracked root files are `.envrc`, `.gitignore`, `LICENSE`,
  `README.md`. Every tracked root directory is a distinct architectural
  concern with its own README.
- `data/`, `figures/`, `thesis_env/` and caches stay local and are never
  committed.
- `thesis_env/` is the project-local Python environment; recreate it with the
  Setup steps, never commit it.
- Paths pinned in
  `docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`
  must not move before the H01–H03 held-out evaluation.
- Generated caches (`__pycache__/`, `.pytest_cache/`, `*.pyc`) are never
  committed; run `pytest` with `-p no:cacheprovider`.
