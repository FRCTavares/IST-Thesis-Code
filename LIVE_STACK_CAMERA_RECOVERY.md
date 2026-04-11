# Live Stack Camera Recovery Guide

## Scope

This document captures the April 2026 incident where live stack startup failed due to camera bring-up issues after a crash/reboot cycle.

Use this guide when:

- inference service can run, but camera does not publish /camera/image_raw
- media graph appears incomplete
- /dev/video0 or /dev/v4l-subdev* is missing

## Incident Summary

Date range:

- Initial incident: 2026-04-08
- Resolution path completed: 2026-04-09

Observed sequence:

1. Inference readiness failed first (port 5556 timeout) due to Hailo module mismatch.
2. After Hailo recovery, camera still failed.
3. Camera node exited because selected media graph exposed no camera video nodes.

## Final Root Cause

Two separate root causes existed:

1. Hailo module mismatch (fixed first)

- Kernel moved to 6.8.0-1051-raspi.
- Hailo module initially existed only for older kernel.

1. TEVS camera driver missing for current kernel (primary camera blocker)

- Running kernel: 6.8.0-1051-raspi.
- tevs.ko existed for 6.8.0-1048 and 6.8.0-1050, but not 6.8.0-1051.
- Overlay declared TEVS node, but no driver binding occurred.
- Result:
  - no /dev/v4l-subdev*
  - no TEVS sensor entities in media topology
  - camera node failed before publishing /camera/image_raw

## Typical Failure Signatures

Launcher/log symptoms:

- timeout waiting for /camera/image_raw
- camera_capture_node traceback showing configured /dev/video0 missing
- selected media device exposes no video nodes

System symptoms:

- ls -l /dev/v4l-subdev* returns none
- media-ctl output contains rp1-cfe csi2 + pisp-fe only
- pispbe/rpivid nodes exist, but no active TEVS capture path

Possible kernel hints:

- rp1-cfe found subdevice tevs@48 in logs, but media graph still incomplete
- occasional pca953x probe errors on bad boots

## Recovery Procedure (Confirmed Working)

Prerequisites:

- current kernel headers installed
- local TEVS out-of-tree source available at /home/francisco/tevs-oot

Step 1: Build module for current kernel

```bash
cd /home/francisco/tevs-oot
make clean
make -j$(nproc)
```

Step 2: Install module into current kernel module tree

```bash
sudo mkdir -p /lib/modules/$(uname -r)/extra
sudo cp /home/francisco/tevs-oot/tevs.ko /lib/modules/$(uname -r)/extra/tevs.ko
sudo depmod -a
```

Step 3: Reload and verify module

```bash
sudo modprobe -r tevs 2>/dev/null || true
sudo modprobe tevs
lsmod | rg '^tevs' || echo 'tevs not loaded'
```

Step 4: Verify camera graph and devices

```bash
uname -r
ls -l /dev/v4l-subdev*
media-ctl -d /dev/media0 -p
media-ctl -d /dev/media1 -p
v4l2-ctl --list-devices
```

Step 5: Start live stack

```bash
cd /home/francisco/Desktop/Thesis-Code
./tools/start_live_stack.sh
```

## Expected Healthy State

A successful recovery should show:

- /dev/v4l-subdev* exists
- media topology includes TEVS sensor entities and capture path
- start_live_stack passes camera readiness check
- /camera/image_raw publishes

## Persistent Prevention (So It Does Not Recur)

Use this section after any reboot, kernel update, or CSI cable move.

### 1) Keep overlay port aligned with physical connector

For the current setup where the camera cable is on J3:

- set `dtoverlay=tevs-rpi22,cam0`
- keep `camera_auto_detect=0`

If the cable is moved again between J3/J4, update cam0/cam1 to match the physical port and reboot.

### 2) Reboot-health validation before launching stack

Run this quick check after every reboot and before `start_live_stack`:

```bash
uname -r
modinfo tevs || true
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
v4l2-ctl --list-devices
media-ctl -d /dev/media0 -p
journalctl -k -b --no-pager | rg -i "tevs|rp1-cfe|pca953x|i2c|fail|error" | tail -n 120
```

Gate to proceed:

- `/dev/v4l-subdev*` exists
- `v4l2-ctl --list-devices` shows `rp1-cfe` with `/dev/video0...`
- `media-ctl -d /dev/media0 -p` includes TEVS entity linked into `csi2`

If any gate fails, do not start the stack yet; fix camera bring-up first.

### 3) Keep runtime resilient defaults (already applied)

`tools/start_live_stack.sh` defaults were tuned to reduce startup and runtime regressions:

- `infer-queue-size=1` (fresh-frame behavior)
- `infer-workers=2`
- `infer-timeout-ms=300`
- `infer-retries=0` (avoid long retry stalls)
- `control-stale-timeout-s=0.80`

These defaults improve robustness against transient inference jitter that previously caused repeated stale-target drops.

### 4) Camera node robustness that should remain enabled

In `camera_capture_node.py`:

- media device auto-detection prefers CSI graphs over pispbe-only graphs
- sensor entity auto-detection handles bus re-enumeration (e.g., `tevs 10-0048` vs `tevs 11-0048`)
- media init reconciles to detected sensor resolution when requested format is not truly applied

This avoids the "node alive but no `/camera/image_raw` frames" state after reboot/re-enumeration.

### 5) Fast restart sequence when stack was previously healthy

```bash
cd /home/francisco/Desktop/Thesis-Code
./tools/start_live_stack.sh
```

If startup prints camera timeout again, collect these immediately:

```bash
latest=$(ls -1dt ros2_ws/log/live_stack/2026-* | head -n1)
tail -n 200 "$latest/camera.log"
tail -n 200 "$latest/inference.log"
```

## Fast Triage Checklist

Run these first during any future camera incident:

```bash
uname -r
modinfo tevs || true
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
media-ctl -d /dev/media0 -p
v4l2-ctl --list-devices
journalctl -k -b --no-pager | rg -i "tevs|rp1-cfe|pca953x|i2c|fail|error"
```

Decision logic:

- If tevs module missing for current kernel: rebuild/install tevs first.
- If tevs loaded but graph still incomplete: inspect kernel logs and CSI/overlay path.
- If graph is complete but no frames: inspect camera node launch parameters and runtime logs.

## Safety Guardrails

To reduce lockout risk:

- Avoid risky remote edits to boot kernel/initramfs lines in /boot/firmware/config.txt as first response.
- Prefer rebuilding and loading the required module for the current kernel.
- Only change boot config with local physical fallback available.

## Code Hardening Added During Incident

1. tools/start_live_stack.sh

- added camera fatal-log detection and clearer startup diagnostics
- added preflight media graph auto-detection and actionable hints

1. ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py

- improved media-device resolution to avoid false fallback onto pispbe-only nodes
- fail-fast when selected media graph exposes no video nodes

## Related Files

- live_stack_incident_2026-04-08.txt
- tools/start_live_stack.sh
- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py
