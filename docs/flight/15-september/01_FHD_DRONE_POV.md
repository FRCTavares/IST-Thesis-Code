# Flight 1 — FHD Representative Drone-POV Capture

DEVELOPMENT / NON-HELD-OUT.

Pilot manually flies the aircraft. The thesis controller is OFF.

Do not reproduce H01/H02/H03.

## 1. Camera check

Run:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u

    ls -l /dev/video0

    v4l2-ctl -d /dev/video0 --list-formats-ext | \
        rg 'UYVY|1920x1080'

    pgrep -af '[s]tart_live_stack|[p]erception_camera_node|[r]os2 bag record|[m]avros_node' || true

No thesis process may own the camera.

## 2. Prepare output

Run:

    OUT_DIR="$PWD/bags/development/fhd_appearance"
    mkdir -p "$OUT_DIR"
    df -h "$OUT_DIR"

    TEST="fhd_drone_pov_15sep"

## 3. Start recording

Run:

    STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
    OUT="$OUT_DIR/${STAMP}_${TEST}_1920x1080_mjpeg.mkv"
    LOG="$OUT_DIR/${STAMP}_${TEST}_ffmpeg.log"

    echo "Recording to: $OUT"
    echo "Press q to stop recording."

    ffmpeg -hide_banner -n \
        -use_wallclock_as_timestamps 1 \
        -f v4l2 \
        -input_format uyvy422 \
        -video_size 1920x1080 \
        -i /dev/video0 \
        -an \
        -c:v mjpeg \
        -q:v 2 \
        -threads 4 \
        -fps_mode passthrough \
        "$OUT" \
        2> >(tee "$LOG" >&2)

## 4. Flight

Record about 60–90 s.

Get:

- FAR target — highest priority
- medium distance
- near distance
- front view
- side / oblique views
- rear view
- normal walking
- turns
- useful viewpoint change from the moving UAV

Pilot uses conservative manual flight only.

## 5. Stop

In FFmpeg press:

    q

## 6. Verify immediately

Run:

    ls -lh "$OUT"

    ffprobe -v error \
        -count_frames \
        -select_streams v:0 \
        -show_entries stream=codec_name,width,height,pix_fmt,nb_read_frames \
        -show_entries format=duration,size \
        -of default=noprint_wrappers=1 \
        "$OUT"

    ffmpeg -v error \
        -i "$OUT" \
        -f null - \
        2>&1

Required:

    codec_name=mjpeg
    width=1920
    height=1080

The decode command must finish successfully.

Keep the original FHD master unchanged.

## Next

Open:

    less docs/flight/15-september/02_H01_EXIT_REENTRY.md
