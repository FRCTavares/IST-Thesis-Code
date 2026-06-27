# Hailo Recovery Guide

## Scope

This document captures Hailo AI HAT / Hailo PCI recovery procedures for the thesis live stack.

Use this guide when:

- `perception_camera_node` exits before publishing `/detections`
- `/detections` has subscribers but no publisher
- `hailortcli scan` reports no Hailo devices
- `/dev/hailo0` is missing
- `perception_camera.log` contains `HAILO_OUT_OF_PHYSICAL_DEVICES`
- the kernel was updated and `hailo_pci` is no longer available

Related operator docs:

- `RUNBOOK.md` for routine startup commands
- `LIVE_STACK_CAMERA_RECOVERY.md` for TEVS/camera bring-up
- `tools/start_live_stack.sh` for live-stack orchestration

---

## Pre-launch Gate

Run this before starting the live stack after any reboot, kernel update, crash, or driver recovery:

```bash
uname -r
ls -l /dev/hailo* 2>/dev/null || echo "no /dev/hailo device"
lsmod | rg '^hailo_pci' || echo 'hailo_pci not loaded'
modinfo hailo_pci | head || true
hailortcli scan
dkms status | grep -i hailo || true
find /lib/modules/$(uname -r) -name 'hailo_pci.ko*'
```

Healthy gate:

- `/dev/hailo0` exists
- `hailo_pci` is loaded
- `hailortcli scan` lists one Hailo device
- `dkms status` shows `hailo_pci` installed for the current `uname -r`

If any of those fail, fix Hailo before launching the live stack.

---

## Typical Failure Signatures

### 1. Hailo physical device unavailable

`ros2_ws/log/live_stack/latest/perception_camera.log`:

```text
[HailoRT] [error] CHECK failed - Failed to create vdevice. there are not enough free devices. requested: 1, found: 0
HAILO_OUT_OF_PHYSICAL_DEVICES(74)
hailo_platform.pyhailort.pyhailort.HailoRTException: libhailort failed with error: 74
```

Interpretation:

- Hailo device is missing, occupied, or the driver/runtime is wedged.
- If `/dev/hailo0` exists, another process may hold it.
- If `/dev/hailo0` is missing, the PCI driver is not loaded or not installed for the running kernel.

### 2. Driver missing after kernel update

```bash
sudo modprobe hailo_pci
```

returns:

```text
modprobe: FATAL: Module hailo_pci not found in directory /lib/modules/<kernel>
```

Interpretation:

- The running kernel changed.
- The DKMS module was not built for the new kernel.
- Install matching headers and rebuild DKMS.

### 3. No Hailo device visible

```bash
hailortcli scan
```

returns:

```text
Hailo devices not found
```

Interpretation:

- `/dev/hailo0` is probably missing.
- `hailo_pci` may not be loaded.
- Kernel module may be missing for the current kernel.

---

## Incident Summary: 2026-05-05 Kernel 6.8.0-1053

After reboot/update, the system was running:

```text
6.8.0-1053-raspi
```

Observed symptoms:

```text
/dev/hailo0 missing
hailortcli scan: Hailo devices not found
modprobe hailo_pci: Module hailo_pci not found in directory /lib/modules/6.8.0-1053-raspi
```

Existing modules were found only for older kernels:

```text
/lib/modules/6.8.0-1050-raspi/updates/dkms/hailo_pci.ko.zst
/lib/modules/6.8.0-1052-raspi/updates/dkms/hailo_pci.ko.zst
```

DKMS status initially showed:

```text
hailo_pci/4.23.0, 6.8.0-1052-raspi, aarch64: installed
```

Root cause:

- Kernel updated to `6.8.0-1053-raspi`.
- `hailo_pci` DKMS module was not installed for that kernel.
- Kernel headers were initially missing.

Recovery:

```bash
sudo apt update
sudo apt install -y linux-headers-$(uname -r)
```

This installed:

```text
linux-raspi-headers-6.8.0-1053
linux-headers-6.8.0-1053-raspi
```

DKMS then auto-built Hailo for the current kernel:

```text
hailo_pci/4.23.0, 6.8.0-1053-raspi, aarch64: installed
```

Final verification:

```text
/dev/hailo0 exists
hailortcli scan -> Device: 0000:01:00.0
```

---

## Recovery Procedure

### Step 1: Stop stale Hailo users

```bash
cd "$THESIS_ROOT"

pkill -f 'perception_camera_node|perception_pipeline_node|hailo|ros2 bag record' || true
```

Check containers:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

If a Hailo/container inference service is still running:

```bash
docker stop $(docker ps -q --filter "name=hailo") 2>/dev/null || true
```

### Step 2: Check device ownership

```bash
ls -l /dev/hailo* 2>/dev/null || echo "no /dev/hailo device"
sudo fuser -v /dev/hailo0 2>/dev/null || echo "no process using /dev/hailo0"
```

If a process holds the device:

```bash
sudo fuser -k /dev/hailo0
```

Then retry:

```bash
hailortcli scan
```

### Step 3: Check whether the driver exists for the current kernel

```bash
uname -r
modinfo hailo_pci | head || true
find /lib/modules/$(uname -r) -name 'hailo_pci.ko*'
dkms status | grep -i hailo || true
```

If `modinfo hailo_pci` fails or no module exists for the current kernel, continue to Step 4.

### Step 4: Install matching kernel headers

```bash
ls -ld /lib/modules/$(uname -r)/build || echo "missing headers"
```

If missing:

```bash
sudo apt update
sudo apt install -y linux-headers-$(uname -r)
```

If the package is unavailable, do not force-copy old modules. Either install the correct Raspberry Pi kernel headers or boot an older kernel where the module already exists.

### Step 5: Build/install Hailo DKMS for the current kernel

```bash
sudo dkms build hailo_pci/4.23.0 -k "$(uname -r)"
sudo dkms install hailo_pci/4.23.0 -k "$(uname -r)"
```

Verify:

```bash
dkms status | grep -i hailo
find /lib/modules/$(uname -r) -name 'hailo_pci.ko*'
```

Expected:

```text
hailo_pci/4.23.0, <current-kernel>, aarch64: installed
/lib/modules/<current-kernel>/updates/dkms/hailo_pci.ko.zst
```

### Step 6: Load the driver

```bash
sudo modprobe hailo_pci

ls -l /dev/hailo* 2>/dev/null || echo "no /dev/hailo device"
hailortcli scan
```

Expected:

```text
/dev/hailo0
Hailo Devices:
[-] Device: 0000:01:00.0
```

### Step 7: Start live stack

```bash
cd "$THESIS_ROOT"
./tools/start_live_stack.sh 
```

For a recordable smoke test:

```bash
./tools/start_live_stack.sh \
  --record \
  --tag hailo_recovery_smoke_01
```

---

## Debugging ROS Symptoms

### Check whether perception started

```bash
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"

ros2 node list | rg 'camera|perception|tracker|target_memory'
ros2 topic list | rg '/camera/dashboard|/detections|/tracks|/timing'
ros2 topic info -v /detections
```

Healthy perception:

```text
/perception_camera_node exists
/detections Publisher count: 1
/tracks receives messages
```

Broken Hailo/perception:

```text
/perception_camera_node missing
/detections Publisher count: 0
```

### Inspect logs

```bash
cd "$THESIS_ROOT"

tail -n 160 ros2_ws/log/live_stack/latest/perception_camera.log

grep -R "ERROR\|Traceback\|Exception\|Hailo\|hef\|failed\|No such file" -n \
  ros2_ws/log/live_stack/latest/perception_camera.log
```

---

## Fast Triage Checklist

Run these first during future Hailo incidents:

```bash
uname -r
ls -l /dev/hailo* 2>/dev/null || echo "no /dev/hailo device"
lsmod | rg '^hailo_pci' || echo 'hailo_pci not loaded'
modinfo hailo_pci | head || true
hailortcli scan
dkms status | grep -i hailo || true
find /lib/modules/$(uname -r) -name 'hailo_pci.ko*'
sudo fuser -v /dev/hailo0 2>/dev/null || true
```

Decision logic:

- `/dev/hailo0` exists but Hailo is busy: kill stale process using `/dev/hailo0`.
- `/dev/hailo0` missing and `modprobe hailo_pci` fails: install headers and rebuild DKMS.
- DKMS installed but `hailortcli scan` still fails: reload `hailo_pci`, check PCI visibility, or reboot.
- Hailo works but `/detections` missing: inspect the live-stack camera/perception logs for HEF/runtime errors.

---

## Prevention

After any kernel update:

```bash
uname -r
ls -ld /lib/modules/$(uname -r)/build || echo missing-headers
dkms status | grep -i hailo
modinfo hailo_pci | head || true
hailortcli scan
```

If headers or DKMS are missing, fix before starting the live stack.

Avoid copying Hailo modules from older kernels unless you explicitly verify compatibility. Prefer DKMS rebuilds against the running kernel.

---

## Related Files and Commands

- `/usr/src/hailo_pci-4.23.0/`
- `/home/francisco/hailort-drivers/`
- `tools/setup/install_host_hailo_bindings.sh`
- `tools/start_live_stack.sh`
- `ros2_ws/log/live_stack/latest/perception_camera.log`

Useful commands:

```bash
hailortcli scan
dkms status | grep -i hailo
sudo modprobe hailo_pci
sudo fuser -v /dev/hailo0
```
