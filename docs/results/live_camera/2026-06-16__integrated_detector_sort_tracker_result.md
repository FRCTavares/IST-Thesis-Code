# Integrated detector plus SORT tracker result

Date: 2026-06-16

## Runtime stack

    perception_camera_node
    -> /detections
    -> tracker_node with SORT backend
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

    /tracks approximately 29.94 to 30.00 Hz after warm-up

Detector timing sample:

    e2e_det_ms approximately 10.77 ms
    loop_ms approximately 10.83 ms
    infer_ms approximately 6.94 ms
    pub_dt_ms approximately 33.51 ms

Tracker timing sample:

    track_ms approximately 0.28 ms

CPU and thermal:

    perception_camera_node CPU approximately 69.5 percent
    tracker_node CPU approximately 8.0 percent
    temperature approximately 58.7 C
    throttled = 0x0

## Important finding

Without native numeric thread limits, the SORT tracker process consumed about 280 percent CPU despite track_ms being below 1 ms. With the thread limits enabled, tracker CPU dropped to about 8 percent while preserving 30 Hz /tracks output.

## Conclusion

The integrated detector plus SORT tracker path is real-time safe at 30 Hz. Native numeric thread limits must be included in the final live launch environment to avoid OpenBLAS/OpenMP oversubscription on the Raspberry Pi 5.
