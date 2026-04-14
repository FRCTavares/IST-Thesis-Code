#!/usr/bin/env python3
"""
TEVS Camera Capture Tool
Handles initialization and capture with configurable resolution
"""
import cv2
import sys
import argparse
import subprocess
import signal
from pathlib import Path

# Global flag for graceful shutdown
should_stop = False
original_sigint = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully during recording"""
    global should_stop
    if not should_stop:
        print("\n\nStopping recording...")
        should_stop = True
    else:
        print("\nForce quit...")
        sys.exit(1)

def init_camera_pipeline(width=1920, height=1080):
    """Initialize the TEVS camera media pipeline"""
    print(f"Initializing camera pipeline ({width}x{height})...")
    
    MEDIA_DEV = "/dev/media0"  # Camera is on media0, not media1
    SENSOR_DEV = "/dev/v4l-subdev2"
    VIDEO_DEV = "/dev/video0"
    FMT = "UYVY8_1X16"
    COLORSPACE = "colorspace:srgb xfer:srgb ycbcr:601 quantization:full-range"
    
    commands = [
        ("Configure sensor", f"media-ctl -d {MEDIA_DEV} -V \"'tevs 11-0048':0 [fmt:{FMT}/{width}x{height} field:none {COLORSPACE}]\""),
        ("Configure CSI input", f"media-ctl -d {MEDIA_DEV} -V \"'csi2':0 [fmt:{FMT}/{width}x{height} field:none {COLORSPACE}]\""),
        ("Configure CSI output", f"media-ctl -d {MEDIA_DEV} -V \"'csi2':4 [fmt:{FMT}/{width}x{height} field:none {COLORSPACE}]\""),
        ("Enable link", f"media-ctl -d {MEDIA_DEV} -l \"'csi2':4 -> 'rp1-cfe-csi2_ch0':0 [1]\""),
        ("Configure video0", f"v4l2-ctl -d {VIDEO_DEV} --set-fmt-video=width={width},height={height},pixelformat=UYVY"),
        ("Set trigger mode", f"v4l2-ctl -d {SENSOR_DEV} --set-ctrl=trigger_mode=0"),
        ("Set exposure mode", f"v4l2-ctl -d {SENSOR_DEV} --set-ctrl=exposure_mode=1"),
    ]
    
    for description, cmd in commands:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            if result.returncode != 0:
                # Only warn, don't fail - sensor controls may timeout but still work
                if "set-ctrl" in cmd:
                    print(f"  Note: {description} may have issues (continuing anyway)")
                else:
                    print(f"  Warning: {description} failed (rc={result.returncode})")
        except subprocess.TimeoutExpired:
            if "set-ctrl" in cmd:
                print(f"  Note: {description} timed out (continuing anyway)")
            else:
                print(f"\n✗ ERROR: {description} timed out")
                print("  The camera may be in a bad state. Try:")
                print("    1. Unplug and replug the camera cable")
                print("    2. sudo reboot")
                raise
    
    print("✓ Camera initialized")

def capture_frames(output_path, num_frames=1, width=640, height=480, show_preview=False):
    """Capture frames from camera"""
    
    # Reset stop flag
    global should_stop, original_sigint
    should_stop = False
    
    # Initialize pipeline first
    try:
        init_camera_pipeline(width, height)
    except KeyboardInterrupt:
        print("\n\nInitialization cancelled.")
        return False
    
    print(f"Opening camera...")
    cap = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)
    
    if not cap.isOpened():
        print("ERROR: Failed to open camera")
        return False
    
    # Set format
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('U', 'Y', 'V', 'Y'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    
    # Verify actual format
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera format: {actual_w}x{actual_h}")
    
    if num_frames == 1:
        # Single frame capture
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(str(output_path), frame)
            print(f"✓ Frame saved to {output_path}")
            success = True
        else:
            print("✗ Failed to capture frame")
            success = False
    else:
        # Multiple frames or video
        if output_path.suffix in ['.mp4', '.avi', '.mkv', '.mov']:
            # Video recording
            # Choose codec based on format
            if output_path.suffix == '.avi':
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # Motion JPEG (more compatible)
            else:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MPEG-4
            
            # Measure actual FPS by capturing a few test frames
            print("Measuring camera framerate...")
            import time
            test_start = time.time()
            test_frames = 0
            for _ in range(30):
                ret, _ = cap.read()
                if ret:
                    test_frames += 1
            test_elapsed = time.time() - test_start
            
            if test_frames > 0:
                actual_fps = test_frames / test_elapsed
                fps = int(actual_fps)
                print(f"Detected camera FPS: {actual_fps:.1f}, using {fps} for encoding")
            else:
                fps = 30
                print(f"Could not measure FPS, using default: {fps}")
            
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (actual_w, actual_h))
            
            if not out.isOpened():
                print(f"ERROR: Could not open video writer for {output_path}")
                cap.release()
                return False
            
            print(f"Recording video to {output_path}")
            print(f"Format: {output_path.suffix}, FPS: {fps}, Resolution: {actual_w}x{actual_h}")
            
            if num_frames > 0:
                print(f"Recording {num_frames} frames (press Ctrl+C to stop early)...")
            else:
                print(f"Recording continuous (press Ctrl+C to stop)...")
            
            # Enable Ctrl+C handler for recording
            original_sigint = signal.signal(signal.SIGINT, signal_handler)
            
            frame_count = 0
            consecutive_failures = 0
            max_failures = 5
            
            while True:
                if should_stop or (num_frames > 0 and frame_count >= num_frames):
                    break
                
                # Check for too many consecutive failures
                if consecutive_failures >= max_failures:
                    print(f"\n✗ Too many consecutive frame failures ({max_failures}). Stopping.")
                    break
                    
                ret, frame = cap.read()
                if ret:
                    out.write(frame)
                    frame_count += 1
                    consecutive_failures = 0  # Reset on success
                    if frame_count % 30 == 0:
                        print(f"  Recorded {frame_count} frames...")
                else:
                    consecutive_failures += 1
                    print(f"  Warning: Frame read failed ({consecutive_failures}/{max_failures})")
            
            # Restore original signal handler
            if original_sigint:
                signal.signal(signal.SIGINT, original_sigint)
            
            out.release()
            print(f"✓ Video saved: {frame_count} frames to {output_path}")
            success = True
        else:
            # Multiple image files
            print(f"Capturing {num_frames} frames...")
            for i in range(num_frames):
                ret, frame = cap.read()
                if ret:
                    filename = output_path.parent / f"{output_path.stem}_{i:04d}{output_path.suffix}"
                    cv2.imwrite(str(filename), frame)
                    if (i + 1) % 10 == 0:
                        print(f"  Frame {i+1}/{num_frames}")
                else:
                    print(f"  Warning: Frame {i+1} failed")
            print(f"✓ {num_frames} frames saved")
            success = True
    
    cap.release()
    return success

def main():
    parser = argparse.ArgumentParser(
        description='TEVS Camera Capture Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Capture single frame (640x480)
  %(prog)s -o photo.jpg             # Capture to specific file
  %(prog)s -r 1920x1080             # Capture at 1920x1080
  %(prog)s -n 30 -o video.mp4       # Record 30 frames to MP4
  %(prog)s -n 0 -o video.mp4        # Record continuous (Ctrl+C to stop)
  %(prog)s -n 30 -o video.avi       # Record 30 frames to AVI (MJPEG)
  %(prog)s -n 100 -o frames.jpg     # Capture 100 images (frames_0000.jpg, ...)

Video formats: .mp4, .avi, .mkv, .mov
Image formats: .jpg, .png, .bmp
        """
    )
    
    parser.add_argument('-o', '--output', default='capture.jpg',
                        help='Output file path (default: capture.jpg)')
    parser.add_argument('-n', '--num-frames', type=int, default=1,
                        help='Number of frames to capture. Use 0 for continuous (default: 1)')
    parser.add_argument('-r', '--resolution', default='640x480',
                        help='Resolution WIDTHxHEIGHT (default: 640x480)')
    parser.add_argument('--init-only', action='store_true',
                        help='Only initialize pipeline, don\'t capture')
    
    args = parser.parse_args()
    
    # Parse resolution
    try:
        width, height = map(int, args.resolution.split('x'))
    except:
        print(f"ERROR: Invalid resolution format '{args.resolution}'. Use WIDTHxHEIGHT (e.g., 1920x1080)")
        return 1
    
    # Init only mode
    if args.init_only:
        init_camera_pipeline(width, height)
        return 0
    
    # Capture
    output_path = Path(args.output)
    success = capture_frames(output_path, args.num_frames, width, height)
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
