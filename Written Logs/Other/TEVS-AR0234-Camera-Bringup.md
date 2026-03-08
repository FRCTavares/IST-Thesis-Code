# TEVS-AR0234 CSI Camera Bring-Up on Raspberry Pi 5

## 1. Objective

- Bring up the TEVS-AR0234 CSI camera on Raspberry Pi 5 running Ubuntu 24.04.
- Verify the sensor is detected, the CSI pipeline initialises, and frames can be captured through V4L2.
- Establish a reliable procedure to initialise the camera after boot.

---

## 2. Platform

- **Hardware:** Raspberry Pi 5
- **Camera:** e-con Systems TEVS-AR0234
- **Interface:** CSI-2
- **OS:** Ubuntu 24.04
- **Kernel:** 6.8.x
- **Capture stack:** V4L2 + Media Controller (RP1-CFE pipeline)

---

## 3. System Configuration

- Camera auto-detection disabled.
- TEVS device tree overlay manually enabled.
- Camera connected to CSI CAM1 port.

**Configuration file modified:** `/boot/firmware/config.txt`

**Purpose:** Force loading of the TEVS camera driver and disable conflicting auto-detection.

---

## 4. Driver Initialisation

After boot the kernel detects:
- TEVS sensor on I2C
- CSI receiver (RP1-CFE)
- Media controller graph
- Video capture nodes

Important confirmation messages appear in `dmesg` indicating:
- TEVS driver initialised
- Sensor chip ID detected
- CSI capture node registered

---

## 5. Device Nodes Created

The following nodes appear after successful initialisation:

**Video nodes:**
- `/dev/video0`
- `/dev/video1`
- `/dev/video2`
- `/dev/video3`
- `/dev/video4` …

**Subdevices:**
- `/dev/v4l-subdev0`
- `/dev/v4l-subdev1`
- `/dev/v4l-subdev2`

These represent:
- Sensor
- CSI receiver
- ISP pipeline
- Capture channels

---

## 6. Media Pipeline Architecture

The Raspberry Pi 5 camera pipeline uses the Media Controller framework.

**Sensor pipeline:**

```
TEVS-AR0234 sensor
        ↓
CSI-2 receiver (rp1-cfe)
        ↓
CSI capture channel
        ↓
V4L2 video node
        ↓
system memory
```

**Primary capture node:** `/dev/video0`

---

## 7. Media Graph Inspection

The media controller graph confirms the following connections:

- Sensor → CSI receiver
- CSI receiver → capture channel
- Capture channel → `/dev/video0`

The critical link is:

> CSI output pad → CSI capture channel

This link must be enabled before frames can be streamed.

---

## 8. Camera Pipeline Initialisation

After boot the camera pipeline requires manual configuration.

**Steps performed:**
1. Configure sensor output format.
2. Configure CSI receiver input format.
3. Configure CSI receiver output format.
4. Enable CSI capture link.
5. Configure `/dev/video0` capture format.

**All components set to:**
- Resolution: 640 × 480
- Format: UYVY (YUV422)

---

## 9. Capture Verification

A test capture was performed using the V4L2 streaming interface.

**Test configuration:**
- Resolution: 640 × 480
- Format: UYVY
- Frames captured: 10

**Output:**
- Raw frame file successfully written
- File size ≈ 5.9 MB

This confirms the camera is streaming frames correctly.

---

## 10. Validation

Successful results confirm:
- Sensor detection working
- TEVS driver functioning
- CSI pipeline correctly configured
- Media controller graph operational
- `/dev/video0` capture working
- Raw frames successfully captured

The full sensor → CSI → memory pipeline is operational.

---

## 11. Achievements

This work completed the camera hardware bring-up phase.

**Key outcomes:**
- TEVS-AR0234 camera operational on Raspberry Pi 5
- Kernel driver validated on Ubuntu 24.04
- CSI capture pipeline understood and documented
- Repeatable camera initialisation procedure established

---

## 12. Troubleshooting: Stream Start Issues

### Problems Identified

After system reboot, the camera pipeline required reconfiguration and several issues were discovered:

**Issue 1: Trigger Mode**
- Symptom: `VIDIOC_STREAMON returned -1 (Invalid argument)`
- Cause: Sensor set to "Sync to Trigger Mode" (1) instead of continuous streaming
- Solution: `v4l2-ctl -d /dev/v4l-subdev2 --set-ctrl=trigger_mode=0`

**Issue 2: Colorspace Mismatch**
- Symptom: Kernel log shows "Format mismatch! Failed to start media pipeline: -22"
- Cause: Sensor outputs full-range sRGB but CSI receiver expected limited-range
- Solution: Configure entire pipeline with explicit colorspace parameters

**Issue 3: Sensor Not Streaming**
- Symptom: STREAMON succeeds but no frames received, exposure value reads 0
- Cause: Camera cable not fully seated in CSI port
- Solution: Power off, disconnect and firmly reconnect cable to CAM1 port, power on
- Status: **RESOLVED** - Camera now streams frames correctly

### Initialization Script

Created `/tools/camera/init_camera.sh` to configure the complete pipeline:

```bash
# 1. Configure sensor output with full colorspace
media-ctl -d /dev/media1 -V "'tevs 11-0048':0 [fmt:UYVY8_1X16/640x480 field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range]"

# 2. Configure CSI receiver input
media-ctl -d /dev/media1 -V "'csi2':0 [fmt:UYVY8_1X16/640x480 field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range]"

# 3. Configure CSI receiver output
media-ctl -d /dev/media1 -V "'csi2':4 [fmt:UYVY8_1X16/640x480 field:none colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range]"

# 4. Configure video0 capture format
v4l2-ctl -d /dev/video0 --set-fmt-video=width=640,height=480,pixelformat=UYVY

# 5. Set sensor controls
v4l2-ctl -d /dev/v4l-subdev2 --set-ctrl=trigger_mode=0
v4l2-ctl -d /dev/v4l-subdev2 --set-ctrl=exposure_mode=1
```

### Diagnostic Steps

1. **Verify devices exist:**
   ```bash
   ls /dev/video* /dev/v4l-subdev*
   ```

2. **Check media pipeline:**
   ```bash
   media-ctl -d /dev/media1 -p
   ```

3. **Verify sensor detection:**
   ```bash
   sudo dmesg | grep tevs
   # Should show: "tevs 11-0048: Chip ID: 0x0A56"
   ```

4. **Check trigger mode:**
   ```bash
   v4l2-ctl -d /dev/v4l-subdev2 --get-ctrl=trigger_mode
   # Should return: trigger_mode: 0 (Disabled)
   ```

5. **Test capture:**
   ```bash
   timeout 5 v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-to=/tmp/test.raw
   ```

### Recommended Recovery Procedure

If camera stops working after reboot:

1. Reboot to reset sensor hardware state
2. Run `init_camera.sh` to configure pipeline
3. Verify with `python3 test_cam_debug.py`
4. Check kernel logs: `sudo dmesg | grep -i "csi\|tevs\|cfe"`

---

## 13. Successful Camera Operation

### Resolution

After reboot and cable reconnection, the camera now captures frames successfully:

**Test Results:**
- First frame captured in ~60ms
- Image: 640×480 BGR (converted from UYVY)
- File size: ~94KB JPEG
- Pipeline fully operational

### Working Procedure

1. **After reboot, run initialization:**
   ```bash
   cd /home/francisco/Desktop/Thesis-Code/tools/camera
   bash init_camera.sh
   ```

2. **Capture test frame:**
   ```bash
   python3 test_cam_debug.py
   ```

3. **Expected output:**
   ```
   Opening /dev/video0 with V4L2...
   Camera opened: True
   Format: 640.0x480.0 @ -1.0 FPS, FOURCC: UYVY
   Attempting to read frame (timeout 5s)...
   Read returned after 0.06s: ret=True
   Success! Frame shape: (480, 640, 3), dtype: uint8
   Saved to frame.jpg
   Done
   ```

### Known Limitations

**Pipeline Must Be Reconfigured After Each Reboot:**
- The media controller pipeline doesn't persist across reboots
- Run `init_camera.sh` after every system boot
- Consider adding to system startup scripts if needed

**Capture Format:**
- Sensor outputs UYVY (YUV422)
- OpenCV automatically converts to BGR for processing
- Direct UYVY access possible via V4L2 if needed for performance

---

## 14. Next Steps

- Implement ROS 2 camera node with continuous capture
- Add automatic pipeline initialization to ROS launch file
- Benchmark sustained frame rate and latency
- Integrate live camera stream into perception pipeline
- Replace MP4 input in inference client with CSI frames
