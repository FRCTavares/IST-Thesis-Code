# Integrated detector plus OCSORT tracker result

Date: 2026-06-16

## Runtime stack

    perception_camera_node
    -> /detections
    -> tracker_node with OCSORT backend
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

    /tracks approximately 30.00 Hz

Tracker timing sample:

    track_ms approximately 0.93 ms

CPU and thermal:

    perception_camera_node CPU approximately 73.2 percent
    tracker_node CPU approximately 11.9 percent
    temperature approximately 58.2 C
    throttled = 0x0

## Conclusion

The integrated detector plus OCSORT tracker path is real-time safe at 30 Hz when native numeric thread limits are applied.
