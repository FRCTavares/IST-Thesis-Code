# Live Stack Camera Recovery Guide

## Scope

This document captures known camera bring-up incidents where live stack startup fails before inference because the TEVS/RPi CSI camera path is unhealthy.

This guide applies to the integrated camera live stack because camera failure happens before inference starts.

Use this guide when:

- live stack starts, but no `/camera/dashboard` stream appears
- media graph appears incomplete
- `/dev/video0` or `/dev/v4l-subdev*` is missing
- `media-ctl` shows `rp1-cfe` with only `csi2` and `pisp-fe`
- camera tools such as `v4l2-ctl` block or enter uninterruptible `D` state

Related operator docs:

- `RUNBOOK.md` for routine startup commands
- `HAILO_RECOVERY.md` for Hailo/AI HAT driver recovery
- `README.md` for path selection

---

## Pre-launch Gate

Run before starting the live stack after any reboot, kernel update, crash, CSI cable change, or camera incident:

```bash
uname -r
modinfo tevs | head || true
lsmod | rg '^tevs' || echo 'tevs not loaded'
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
v4l2-ctl --list-devices

for m in /dev/media*; do
  echo "===== $m ====="
  media-ctl -d "$m" -p | rg -i "tevs|rp1-cfe|csi2|pisp-fe|csi2_ch0|entity|video|ENABLED" | head -160
done

journalctl -k -b --no-pager | rg -i "tevs|rp1-cfe|pca953x|i2c|stream|timeout|fail|error" | tail -n 120
```

Gate to proceed:

- `/dev/v4l-subdev*` exists
- `v4l2-ctl --list-devices` shows `rp1-cfe` with `/dev/video0...`
- a media graph contains a TEVS entity, for example `tevs 10-0048`
- `csi2` is linked to TEVS
- the capture node `/dev/video0` exists

Important:

- Do not assume `rp1-cfe` is always `/dev/media0`.
- After reboot, media indexes can change. Inspect all `/dev/media*` devices.

---

## Incident Summary

### April 2026 Incident

Date range:

- Initial incident: 2026-04-08
- Resolution path completed: 2026-04-09
- Follow-up regression captured: 2026-04-14

Observed sequence:

1. Inference readiness failed first due to Hailo module mismatch.
2. After Hailo recovery, camera still failed.
3. Camera node exited because selected media graph exposed no camera video nodes.

Root causes:

1. Hailo module mismatch after kernel update.
2. TEVS camera driver missing for the current kernel.
3. Follow-up failure where topology was present but stream path was unhealthy.

### May 2026 Kernel 6.8.0-1053 Follow-up

Observed after reboot/update:

```text
uname -r -> 6.8.0-1053-raspi
modinfo tevs -> Module tevs not found
/dev/v4l-subdev* -> missing
v4l2-ctl --list-devices -> no /dev/video0
media graph -> rp1-cfe only had csi2 + pisp-fe, no TEVS entity
```

Root cause:

- Kernel updated to `6.8.0-1053-raspi`.
- TEVS out-of-tree module was not built/installed for the new kernel.
- Kernel headers were initially missing.

Recovery:

```bash
sudo apt update
sudo apt install -y linux-headers-$(uname -r)

cd /home/francisco/tevs-oot
make clean
make -j$(nproc)

sudo mkdir -p /lib/modules/$(uname -r)/extra
sudo cp /home/francisco/tevs-oot/tevs.ko /lib/modules/$(uname -r)/extra/tevs.ko
sudo depmod -a

sudo modprobe -r tevs 2>/dev/null || true
sudo modprobe tevs
```

Final healthy state:

```text
/dev/v4l-subdev0..2 exist
rp1-cfe exposes /dev/video0..7
media graph includes tevs 10-0048
csi2 -> rp1-cfe-csi2_ch0 link enabled
```

---

## Typical Failure Signatures

Launcher/log symptoms:

- timeout waiting for `/camera/dashboard`
- camera node alive but no `/camera/dashboard`
- camera node logs stop after TEVS entity detection
- selected media device exposes no camera video nodes
- `VIDIOC_STREAMON returned -1 (Invalid argument)`
- `VIDIOC_S_EXT_CTRLS: failed: Connection timed out`
- `VIDIOC_S_EXT_CTRLS: failed: Unknown error 220`

System symptoms:

- `ls -l /dev/v4l-subdev*` returns none
- `/dev/video0` missing
- media graph contains `rp1-cfe` with only `csi2` and `pisp-fe`
- `pispbe` and `rpivid` nodes exist, but no active TEVS capture path
- `v4l2-ctl` or camera tools stuck in `D` state

Kernel hints:

- `rp1-cfe ... found subdevice ... tevs@48`, but media graph still incomplete
- `rp1-cfe ... csi2_ch0 node link is not enabled`
- `rp1-cfe ... stream on failed in subdev`
- `i2c_designware ... timeout`
- `tevs ... failed to read from register: ret=-110`
- `pca953x` probe or power warnings on bad boots

---

## Recovery Procedure

### Step 1: Stop stale camera processes

```bash
cd "$THESIS_ROOT"

pkill -INT -f 'start_live_stack.sh|perception_camera_node|ros2 launch thesis_bringup camera_bringup.launch.py' || true
sleep 3
pkill -TERM -f 'start_live_stack.sh|perception_camera_node|ros2 launch thesis_bringup camera_bringup.launch.py' || true
sleep 3
pkill -KILL -f 'start_live_stack.sh|perception_camera_node|ros2 launch thesis_bringup camera_bringup.launch.py' || true

ps -eo pid,stat,cmd | rg 'start_live_stack|perception_camera_node|camera_bringup|v4l2|media-ctl' || true
```

If any process is in `D` state, userspace cannot kill it. Reboot immediately:

```bash
sudo reboot
```

### Step 2: Check module and graph

```bash
uname -r
modinfo tevs | head || true
lsmod | rg '^tevs' || echo 'tevs not loaded'
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
v4l2-ctl --list-devices

for m in /dev/media*; do
  echo "===== $m ====="
  media-ctl -d "$m" -p | rg -i "tevs|rp1-cfe|csi2|pisp-fe|csi2_ch0|entity|video|ENABLED" | head -160
done
```

### Step 3: Rebuild TEVS for current kernel if missing

If `modinfo tevs` fails or `/dev/v4l-subdev*` is missing:

```bash
ls -ld /lib/modules/$(uname -r)/build || echo missing-headers
```

If headers are missing:

```bash
sudo apt update
sudo apt install -y linux-headers-$(uname -r)
```

Then rebuild:

```bash
cd /home/francisco/tevs-oot
make clean
make -j$(nproc)

sudo mkdir -p /lib/modules/$(uname -r)/extra
sudo cp /home/francisco/tevs-oot/tevs.ko /lib/modules/$(uname -r)/extra/tevs.ko
sudo depmod -a

sudo modprobe -r tevs 2>/dev/null || true
sudo modprobe tevs

modinfo tevs | head
lsmod | rg '^tevs' || echo 'tevs not loaded'
```

### Step 4: Enable capture link if graph is present but link is disabled

First find which media device is `rp1-cfe`:

```bash
v4l2-ctl --list-devices
```

Then inspect it, replacing `/dev/media0` with the actual `rp1-cfe` media device if needed:

```bash
media-ctl -d /dev/media0 -p | rg -i 'tevs|csi2_ch0|ENABLED|device node'
```

If the capture link is disabled:

```bash
media-ctl -d /dev/media0 -l '"csi2":4 -> "rp1-cfe-csi2_ch0":0 [1]'
```

Verify:

```bash
media-ctl -d /dev/media0 -p | rg -i 'tevs|csi2_ch0|ENABLED|device node'
```

### Step 5: Use direct stream probes sparingly

Direct stream probes can wedge the camera path. Use them only when necessary and only after graph health is confirmed.

Conservative probe:

```bash
v4l2-ctl -d /dev/video0 \
  --set-fmt-video=width=640,height=480,pixelformat=UYVY \
  --stream-mmap=4 \
  --stream-count=30 \
  --stream-to=/dev/null \
  --stream-poll
```

If this hangs or creates a `D`-state process, reboot. Do not keep retrying.

### Step 6: Start live stack conservatively

After module and graph are healthy:

```bash
cd "$THESIS_ROOT"

./tools/start_live_stack.sh \
  --record \
  --tag camera_recovery_smoke_01
```

After the default stack works, optionally test higher-load options such as `--res hd` or `--dash 30`.

---

## Expected Healthy State

A successful recovery should show:

- `modinfo tevs` works for current kernel
- `tevs` appears in `lsmod`
- `/dev/v4l-subdev*` exists
- `v4l2-ctl --list-devices` shows `rp1-cfe` with `/dev/video0...`
- media topology includes TEVS sensor entity and enabled CSI link
- `start_live_stack.sh` starts camera and publishes `/camera/dashboard`
- `/camera/dashboard` and `/camera/fps` publish during live stack

---

## ROS-Level Debugging

Check graph:

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"

ros2 node list | rg 'camera|perception|tracker|target_memory'
ros2 topic list | rg '/camera/dashboard|/camera/fps|/camera/capture_fps'
ros2 topic info -v /camera/dashboard
```

For this ROS 2 setup, use simple `hz` commands:

```bash
ros2 topic hz /camera/dashboard
```

Do not use `--qos-reliability` with `ros2 topic hz` unless confirmed supported by the local CLI version.

Inspect logs:

```bash
cd "$THESIS_ROOT"

ls -1 ros2_ws/log/live_stack/latest
tail -n 160 ros2_ws/log/live_stack/latest/camera.log
journalctl -k -b --no-pager | rg -i 'tevs|rp1-cfe|i2c|timeout|stream|failed|error' | tail -120
```

---

## Prevention

After every kernel update or reboot:

```bash
uname -r
modinfo tevs | head || true
lsmod | rg '^tevs' || echo 'tevs not loaded'
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
v4l2-ctl --list-devices
```

If `modinfo tevs` fails, rebuild TEVS before launching the stack.

Keep overlay and physical connector aligned:

- For current setup with camera cable on J3: `dtoverlay=tevs-rpi22,cam0`
- Keep `camera_auto_detect=0`
- If the cable moves between J3/J4, update `cam0/cam1` and reboot.

Avoid active stream probes by default. The launcher already avoids aggressive probing unless explicitly requested.

---

## Fast Triage Checklist

```bash
uname -r
modinfo tevs | head || true
lsmod | rg '^tevs' || echo 'tevs not loaded'
ls -l /dev/v4l-subdev* 2>/dev/null || echo no-subdev
v4l2-ctl --list-devices
for m in /dev/media*; do echo "===== $m ====="; media-ctl -d "$m" -p | rg -i 'tevs|rp1-cfe|csi2|csi2_ch0|ENABLED|video' | head -120; done
journalctl -k -b --no-pager | rg -i 'tevs|rp1-cfe|pca953x|i2c|stream|timeout|fail|error' | tail -120
ps -eo pid,stat,cmd | rg 'perception_camera_node|v4l2|media-ctl' || true
```

Decision logic:

- `tevs` module missing for current kernel: install headers and rebuild TEVS.
- TEVS loaded but graph incomplete: inspect overlay/CSI path and kernel logs.
- Graph complete but stream path fails: enable capture link and retry once.
- `v4l2-ctl` or camera process in `D` state: reboot.
- Camera is healthy but `/detections` is missing: switch to `HAILO_RECOVERY.md`.

---

## Related Files

- `/home/francisco/tevs-oot`
- `tools/start_live_stack.sh`
- `tools/lib/live_camera.sh`
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_camera_node.py`
- `ros2_ws/log/live_stack/latest/camera.log`
- `HAILO_RECOVERY.md`
