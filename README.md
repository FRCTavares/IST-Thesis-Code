# Thesis-Code

Last reviewed: 2026-10-05

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

## Retained configurations and source boundaries

The thesis retains ByteTrack + TIM-MARS and ByteTrack + TIM-MARS-G as two
configurations of one identity-memory architecture. This main checkout owns
the original live/flight stack. TIM-MARS-G and the expanded campaign backends
(including BoT-SORT) are preserved in separately pinned research-source
snapshots under `docs/archive/delivery_sources_20261005/`; they were replayed,
not flown. The source handoff lists exact revisions, overlays, models, external
data and Git-history requirements. Do not substitute a later trial variant or
use the current headered files as byte-exact historical evidence.

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
| `data/` | Local external datasets and processed research workspaces, including CVAT physical-reference packages and Issue #64 processed inputs. Generated contents remain local; see `data/README.md`. |

Local, git-ignored, not part of a clean checkout: `thesis_env/` (the
project-local Python venv, activated by `.envrc` when present). Generated
figures belong under `artifacts/figures/`; there is no root-level figure
workspace.

## Primary entrypoints

| Command | Purpose |
| --- | --- |
| `./tools/thesis_build.sh` | Build the ROS 2 workspace with repository-local colcon logs. |
| `./tools/start_live_stack.sh` | Start the live camera -> perception -> tracker -> TIM-MARS -> control/dashboard stack. Options: `--help`, `--help-advanced`. |
| `python3 tools/reproduce_tim_mars.py --set development` | Historical reproduction entrypoint: run from its pinned research checkout with the declared external data/environment. Current delivery headers intentionally fail byte-exact historical gates. |
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
- **Setup and recovery:** the Clean-checkout installation section below, then
  `docs/debug/`, `tools/setup/`, `tools/host/`
- **Documentation conventions:** `docs/design/README_STANDARD.md`

## Clean-checkout installation

Supported host: Ubuntu 24.04 with ROS 2 Jazzy.

```bash
git clone git@github.com:FRCTavares/IST-Thesis-Code.git "$HOME/Desktop/Thesis-Code"
cd "$HOME/Desktop/Thesis-Code" || exit 1

source /opt/ros/jazzy/setup.bash
sudo rosdep init 2>/dev/null || true
rosdep update
rosdep install --from-paths ros2_ws/src --ignore-src --rosdistro jazzy -r -y

python3 -m venv --system-site-packages thesis_env
thesis_env/bin/python -m pip install --upgrade pip
thesis_env/bin/python -m pip install -r tools/setup/requirements-mars.txt

# Tools, offline plotting/video export and field telemetry support:
sudo apt install python3-pytest python3-matplotlib ffmpeg zstd v4l-utils \
  ros-jazzy-mavros ros-jazzy-mavros-extras ros-jazzy-rosbag2-storage-mcap

# Select the profile actually needed; hardware checks only inspect availability.
thesis_env/bin/python tools/setup/check_delivery_environment.py --profile offline

./tools/thesis_build.sh
direnv allow          # loads .envrc: ROS overlays, thesis_env, ROS_DOMAIN_ID=42
```

Full dependencies, profile checks, external source/data requirements and the
separate historical reproduction packages are documented in
[delivery setup](tools/setup/README.md). The Mac is an editing host; Linux/ROS
checks do not establish Raspberry Pi hardware or flight acceptance.

The Hailo runtime is platform-specific (Raspberry Pi 5) and is installed
separately — see `tools/setup/`. The browser frontend is prepared in its own
repository: `cd ~/Desktop/IST-Thesis-UI && npm ci && npm run build`.

## Source documentation and delivery

Project source headers identify each file's purpose and credit **Francisco
Tavares**. The repository licence uses the full name Francisco Carreira Tavares.
Upstream notices remain attached to third-party templates and dependencies.

Run `python3 tools/analysis/check_source_headers.py` to check maintained source
coverage. Header conventions and immutable-artifact exclusions are documented in
[the source header standard](docs/design/SOURCE_HEADERS.md). The current delivery
review is recorded in [the delivery audit](docs/DELIVERY_READINESS_20261005.md).

## Rules

- The only tracked root files are `.envrc`, `.gitignore`, `LICENSE`,
  `README.md`. Every tracked root directory is a distinct architectural
  concern with its own README.
- Generated dataset contents under `data/`, generated contents under
  `artifacts/`, `thesis_env/`, and caches stay local and are never committed.
- `thesis_env/` is the project-local Python environment; recreate it with the
  Setup steps, never commit it.
- Paths pinned in
  `docs/results/selected_target_tracking/tim_mars_prospective_freeze_20260908.json`
  must not move before the H01–H03 held-out evaluation.
- Generated caches (`__pycache__/`, `.pytest_cache/`, `*.pyc`) are never
  committed; run `pytest` with `-p no:cacheprovider`.
