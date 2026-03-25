# TEVS Camera Tool

Single tool for camera initialization and capture with configurable resolution.

## Documentation sync (2026-03-25)

This utility is independent from the dashboard bridge/web video path fixes made on 2026-03-25.
No command or behavior changes were required here.

## Usage

### Basic capture (640x480):
```bash
./camera.py
```

### Capture with specific resolution:
```bash
./camera.py -r 1920x1080 -o photo.jpg
```

### Record video (30 frames):
```bash
./camera.py -n 30 -o video.mp4
```

### Continuous recording (stop with Ctrl+C):
```bash
./camera.py -n 0 -o video.mp4
# Press Ctrl+C when done recording
```

### Record as AVI (MJPEG codec - more compatible):
```bash
./camera.py -n 0 -o video.avi
```

### Capture multiple images:
```bash
./camera.py -n 100 -o frames.jpg
# Creates: frames_0000.jpg, frames_0001.jpg, ...
```

### Initialize pipeline only (no capture):
```bash
./camera.py --init-only -r 1920x1080
```

## Supported Formats

**Video:** `.mp4`, `.avi`, `.mkv`, `.mov`
- **MP4**: Uses MP4V codec (standard)
- **AVI**: Uses MJPEG codec (more compatible, larger files)

**Images:** `.jpg`, `.png`, `.bmp`

## Common Resolutions

- `640x480` (VGA)
- `1280x720` (HD)
- `1920x1080` (Full HD)

## Options

```
-o, --output PATH          Output file path (default: capture.jpg)
-n, --num-frames N         Number of frames. Use 0 for continuous (default: 1)
-r, --resolution WxH       Resolution (default: 640x480)
--init-only                Only initialize pipeline, don't capture
```

## Stopping Recording

Press **Ctrl+C** to stop recording at any time. The video file will be saved with all frames captured up to that point.

## After Reboot

The camera pipeline must be initialized after each reboot. This happens automatically when you run `camera.py`.

To test the camera is working:
```bash
./camera.py -o test.jpg
```
