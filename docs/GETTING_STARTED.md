# Getting started

Last reviewed: 2026-10-13

## Purpose

Take a Raspberry Pi 5 + Hailo-8 from a fresh Ubuntu install (or a fresh clone on
the existing Pi) to a built workspace that can run the live stack.

## Target hardware and software

| Item | Requirement |
| --- | --- |
| Computer | Raspberry Pi 5 with the Hailo-8 AI accelerator (PCIe) |
| OS / ROS | Ubuntu 24.04, ROS 2 Jazzy, Python 3.12 |
| Camera | CSI camera (TEVS) exposed as `/dev/video0` |
| Flight controller | Pixhawk 6X over Ethernet via MAVROS (field work only) |
| Models | `models/hef/yolov8s.hef` (detector) and `models/reid/mars-small128.pb` (re-ID) are tracked in Git |

The Mac is an editing host only. Nothing that needs ROS, the camera or Hailo
runs there.

## 1. Clone and install dependencies

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

sudo apt install python3-pytest python3-matplotlib ffmpeg zstd v4l-utils \
  ros-jazzy-mavros ros-jazzy-mavros-extras ros-jazzy-rosbag2-storage-mcap
```

MAVROS also needs its GeographicLib geoid dataset; install it with the script
shipped by the installed MAVROS package before any flight work.

## 2. Hailo-8 runtime

The Hailo PCIe driver, HailoRT and its Python binding are platform-specific and
are installed outside this repository.

- Python binding into the project venv: `tools/setup/install_host_hailo_bindings.sh`.
- Check the device: `hailortcli scan` must list the Hailo-8, and `/dev/hailo0`
  must exist.
- If the driver disappears after a kernel update, follow
  [docs/debug/HAILO_RECOVERY.md](debug/HAILO_RECOVERY.md).

Do not substitute detector or re-ID models, and do not enable stub inference, to
get a check to pass. The launcher fails fast when Hailo is unavailable.

## 3. Camera

The integrated camera path opens the CSI camera directly. If `/dev/video0` is
missing or `v4l2-ctl` hangs, follow
[docs/debug/LIVE_STACK_CAMERA_RECOVERY.md](debug/LIVE_STACK_CAMERA_RECOVERY.md).
`tools/camera/probe_camera_modes.sh` checks the practical output rate of each
V4L2 mode.

## 4. Build

```bash
./tools/thesis_build.sh                                   # whole workspace
./tools/thesis_build.sh --packages-select thesis_bringup  # one package
direnv allow                    # loads .envrc: ROS overlays, thesis_env, ROS_DOMAIN_ID=42
```

Without direnv, source the overlays yourself:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
source thesis_env/bin/activate
export ROS_DOMAIN_ID=42
```

`build/`, `install/` and `log/` under `ros2_ws/` are generated and git-ignored.

## 5. Check the environment

The checker imports the required libraries, checks ROS entry points, model
hashes and command availability. It starts no ROS node, camera or controller.

```bash
python tools/setup/check_delivery_environment.py --profile live
python tools/setup/check_delivery_environment.py --profile field    # adds MAVROS
python -m pip check
```

| Profile | Covers |
| --- | --- |
| `offline` | Bag readers, NumPy, SciPy, OpenCV, YAML, Matplotlib, ffmpeg, zstd, a built workspace |
| `live` | `offline` plus TensorFlow (MARS encoder), HailoRT binding, v4l2-ctl, websockets |
| `field` | `live` plus MAVROS and its service messages |

A pass means the software is present, not that the hardware or flight stack has
been accepted. SciPy must be installed: without it the tracker falls back to a
greedy assignment and results differ.

## 6. Run the tests

```bash
python3 -m pytest -q -p no:cacheprovider tools/tests
cd ros2_ws && colcon test && colcon test-result --verbose
```

## 7. First run

Continue with [OPERATIONS.md](OPERATIONS.md).

## Optional: dashboard

The browser dashboard lives in `FRCTavares/IST-Thesis-UI`. Clone it next to this
repository (`~/Desktop/IST-Thesis-UI`) and follow its own instructions; then
`./tools/start_ui_stack.sh` delegates to its launcher. Headless operation does
not need it. Network exposure rules are in
[docs/live/dashboard_trust_boundary.md](live/dashboard_trust_boundary.md).
