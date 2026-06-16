# Integrated detector plus ByteTrack tracker result

Date: 2026-06-16

## Runtime stack

    perception_camera_node
    -> /detections
    -> tracker_node with ByteTrack backend
    -> /tracks

The tracker was launched with native numeric thread limits:

    OPENBLAS_NUM_THREADS=1
    OMP_NUM_THREADS=1
    MKL_NUM_THREADS=1
    NUMEXPR_NUM_THREADS=1
    VECLIB_MAXIMUM_THREADS=1
    BLIS_NUM_THREADS=1

## Clean measurement

Detection rate:

    /detections approximately 30.00 Hz

Track rate:

    /tracks approximately 29.99 to 30.00 Hz

Tracker timing sample:

    track_ms approximately 0.60 ms

CPU and thermal:

    perception_camera_node CPU approximately 74.9 percent
    tracker_node CPU approximately 10.5 percent
    temperature approximately 57.6 C
    throttled = 0x0

## Conclusion

The integrated detector plus ByteTrack tracker path is real-time safe at 30 Hz when native numeric thread limits are applied.
