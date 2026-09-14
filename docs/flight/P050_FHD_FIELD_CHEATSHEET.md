# FHD Appearance Test — Field Cheat Sheet

**DEVELOPMENT / NON-HELD-OUT ONLY. NEVER H01/H02/H03.**

Held-out capture remains 640x480 under the existing prospective freeze.
Changing its acquisition format requires a **new freeze before any held-out
access**.

## 1. Camera-only preparation

Direct `/dev/video0` MJPEG capture needs a free camera and enough disk space.
It does not intrinsically need a Pixhawk, MAVROS, controller, GCS field
networking, or aircraft-motion authority.

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    ls -l /dev/video0
    v4l2-ctl -d /dev/video0 --list-formats-ext | rg 'UYVY|1920x1080'

    pgrep -af '[s]tart_live_stack|[p]erception_camera_node|[r]os2 bag record|[m]avros_node' || true

No other process may own the camera. Confirm the device offers
1920x1080 UYVY422 before capture.

    OUT_DIR="$PWD/bags/development/fhd_appearance"
    mkdir -p "$OUT_DIR"
    df -h "$OUT_DIR"

The validated smoke used about **87 MiB in 8 s**. Budget roughly
**0.9–1.0 GiB for 90 s**, plus working space; stop if free space is
insufficient.

## 2. Record the native FHD master

Choose a test name:

    TEST="fhd_appearance_01"

Then:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u

    STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
    OUT="$OUT_DIR/${STAMP}_${TEST}_1920x1080_mjpeg.mkv"
    LOG="$OUT_DIR/${STAMP}_${TEST}_ffmpeg.log"

    echo "Recording to: $OUT"
    echo "Press q to stop recording."

    # -n refuses a timestamp/name collision; it changes no capture settings.
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

Stop FFmpeg by pressing:

    q

## 3. Development scene

Record approximately 60–90 seconds.

Use only a development/rehearsal person.

Include:

- far distance
- medium distance
- near distance
- front view
- rear view
- side views
- normal walking and turns

The FAR section is especially important because the purpose is to determine
whether FHD provides better appearance crops.

Do not reproduce H01/H02/H03.

## 4. Verify the master immediately

The `$OUT` variable remains available in the same terminal.

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

Expected:

    codec_name=mjpeg
    width=1920
    height=1080

Check that the frame count and duration are plausible for the actual wall
capture time (roughly 30 frames/s in the validated 8 s smoke: 261 decoded
frames, 7.986 s container duration). The decode-to-null command must finish
successfully without frame corruption. The smoke showed non-monotonic DTS
warnings from the source/container timestamps; those warnings alone did not
show frame-sequence corruption. Keep the original master unchanged.

## 5. Held-out freeze check

    cd ~/Desktop/Thesis-Code || exit 1

    python3 tools/analysis/validate_tim_evaluation_split.py \
        docs/data/splits/tim_mars_split_v4.json \
        --verify-hashes

Expected:

    final_ready=0/3

H01/H02/H03 must remain untouched.

## 6. Matched FHD-to-HD comparison

Do NOT record a separate HD experiment.

Keep the FHD master unchanged.

Later:

1. extract the exact FHD frames;
2. create the HD frames by resizing those exact frames;
3. use identical frame indices for both variants;
4. annotate/evaluate the matched FHD and HD sequences.

Use the **same downstream appearance evaluator** on both matched frame
sets. This holds physical scene, person, pose, motion, distance, viewpoint,
lighting and frame timing fixed, so resolution is the intended comparison.
Never make a second independent HD performance.

## 7. Optional aircraft/flight context

If a separate development objective actually requires the UAV to fly during
this capture, use the normal #50 field gate and qualified pilot procedures in
`docs/flight/README.md`. The pilot alone controls aircraft motion. Those
aircraft/Pixhawk/network steps apply to the flight activity, not to
camera-only FHD recording.
