# Camera Tools

This folder contains camera probing and validation helpers.

These scripts are for hardware/runtime diagnostics. They are not part of the
final TIM-MARS evaluation metric pipeline.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `probe_camera_modes.sh` | Support workflow | Streams selected V4L2 modes briefly to check practical camera output rates. |

## Typical use

Run `probe_camera_modes.sh` after camera setup, reboot, driver changes, or
unexpected live-stack camera failures.

The script uses `v4l2-ctl`, so it should be run on the host where the camera is
attached.
