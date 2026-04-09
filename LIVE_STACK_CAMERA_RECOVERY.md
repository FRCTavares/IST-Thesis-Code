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

2. TEVS camera driver missing for current kernel (primary camera blocker)
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

2. ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py
- improved media-device resolution to avoid false fallback onto pispbe-only nodes
- fail-fast when selected media graph exposes no video nodes

## Related Files

- live_stack_incident_2026-04-08.txt
- tools/start_live_stack.sh
- ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py
