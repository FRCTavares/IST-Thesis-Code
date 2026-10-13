# tools/setup

Last reviewed: 2026-10-05

## Purpose

Set up a fresh Ubuntu 24.04 / ROS 2 Jazzy host and inspect the dependencies for
live operation, offline analysis and historical research reproduction. The Mac
checkout is an editing/delivery source; it does not supply ROS or Pi hardware.

## Core installation

Follow the root README: install ROS 2 Jazzy, source its setup, run rosdep against
`ros2_ws/src`, create `thesis_env` with system site packages, install
`requirements-mars.txt` and build with `tools/thesis_build.sh`. Install direnv
if using `.envrc`; alternatively activate the venv and source the ROS overlays
explicitly. Python 3.12 is the retained Pi environment.

ROS package manifests now declare NumPy, SciPy and OpenCV for the tracker,
and YAML, rosbag2 Python and ROS message introspection for runtime/replay.
TensorFlow is required by the CPU MARS encoder used by TIM-MARS and DeepSORT;
merely installing pytest does not prepare that encoder. SciPy supplies the
Hungarian assignment path; its absence causes a greedy fallback and therefore
cannot be ignored when reproducing tracker results.

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source thesis_env/bin/activate
python -m pip check
python tools/setup/check_delivery_environment.py --profile offline
python tools/setup/check_delivery_environment.py --profile live
python tools/setup/check_delivery_environment.py --profile field
```

The checker imports required libraries, checks ROS entrypoints, tracked model
hashes and command availability. It starts no ROS node, recorder, camera,
controller, installer or network connection. A pass reports software
availability, not hardware operation or field acceptance.

## Profiles and external prerequisites

| Profile | Required components | External inputs |
| --- | --- | --- |
| Offline | ROS bag readers/message introspection, NumPy, SciPy, OpenCV, YAML, Matplotlib, ffmpeg, zstd and a built thesis workspace | The exact source bags, video and annotation packages named by the selected run manifest. These are not stored in Git. |
| Live | ROS runtime/messages, NumPy, SciPy, OpenCV, YAML, websockets, TensorFlow, HailoRT Python binding, v4l2-ctl, ffmpeg and retained model files | Raspberry Pi 5, compatible Hailo-8 driver/runtime and the declared camera. Follow preflight before use. |
| Field | Live profile plus MAVROS and its service messages | Pixhawk, validated field network, RC/pilot, declared event/log procedure; Code #50/#32 acceptance is separate. |
| Frozen campaign | Complete retained research checkouts, the campaign-specific model/configuration hashes and recorded Python package versions | Cached detections/source images, per-frame annotations and retained run manifests. Use the research-source handoff below. |

For live camera/Hailo installation use the platform-specific recovery notes
under `docs/debug/`. Direct inference uses HailoRT; the retained experimental
GStreamer/TAPPAS path additionally needs GI/GStreamer plugins and its compatible
TAPPAS runtime. Do not substitute detector/re-ID models or enable stub inference
to satisfy a delivery check. `ros-jazzy-mavros` and `ros-jazzy-mavros-extras`
provide field support. MAVROS also needs its GeographicLib geoid dataset;
use the dataset installation procedure shipped with the installed MAVROS
package before operation. Host-network helpers require NetworkManager/nmcli
and the Ubuntu systemd/iproute2 utilities; installation/recovery procedures
are in `tools/host/README.md`. The FCU/network settings remain in the field
runbook.

The optional browser UI is owned by `FRCTavares/IST-Thesis-UI`; this repository
only delegates to its launcher. Clone/install that repository separately and
follow its own lockfile and build instructions. Core headless operation and
saved-output analysis do not bundle a web frontend.

## Research-source handoff

Current delivery headers change file hashes. Frozen experiment gates deliberately
reject the current headered checkout when their source/config bytes differ.
Do not refresh frozen hashes or weaken these checks. Historical reproduction
uses complete pinned source revisions and verified modified-file overlays;
see `docs/delivery_source_manifest_20261004.json` and
`docs/archive/delivery_sources_20261004/README.md`.

Complete retained source/model snapshots are also available under
`docs/archive/delivery_sources_20261005/`; their preparation guide lists the
remaining Git history, data and environment requirements.

The 116-file provenance archive alone is not a runnable checkout. Model paths,
source bags, cached detections and datasets in old manifests are external
prerequisites. Research reproduction is not included in normal live startup and
must not be presented as an original flight. No new experiment is required for
this setup audit.

## Maintained helpers

| Tool | Purpose |
| --- | --- |
| `check_delivery_environment.py` | Inspect the chosen software profile and model hashes without starting the runtime. |
| `requirements-mars.txt` | Install the CPU MARS encoder dependency; not a complete frozen environment lock. |
| `install_host_hailo_bindings.sh` | Install compatible Hailo Python wheels into a selected venv. |
| `setup_local_tappas_runtime.sh` | Prepare the retained local TAPPAS tree without installing into system paths. |

Installation helpers may download/install packages and are operator setup aids.
The dependency checker does not perform those actions. Do not repair or upgrade
the retained research environment during an evidence replay.

## Observed Pi environment consistency

The 5 October software/model check passes for the retained live profile.
`pip check` also reports an OpenCV 4.12.0.88 / NumPy 1.26.4 metadata conflict
and missing `cffi` for the unrelated installed PyNaCl package. Those warnings
are retained in the delivery audit. The frozen Pi environment was not upgraded
or repaired. For a fresh installation use a separate environment and resolve
its dependencies before operation; do not call the recorded package versions
a validated clean-install lock.
