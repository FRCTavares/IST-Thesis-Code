# Integrated detector plus DeepSORT tracker runtime check

Date: 2026-06-16

## Runtime stack

    perception_camera_node
    -> /detections
    -> tracker_node with DeepSORT backend
    -> /tracks

The tracker was launched with native numeric thread limits:

    OPENBLAS_NUM_THREADS=1
    OMP_NUM_THREADS=1
    MKL_NUM_THREADS=1
    NUMEXPR_NUM_THREADS=1
    VECLIB_MAXIMUM_THREADS=1
    BLIS_NUM_THREADS=1

## Important limitation

This was not a full DeepSORT appearance test.

Topic inspection showed:

    /camera/image_raw Publisher count: 0
    /camera/image_raw Subscription count: 1

The integrated perception node currently publishes /detections and /timing only. Therefore the DeepSORT tracker was running without a live image publisher for appearance crops.

## Runtime measurement

Detection rate:

    /detections approximately 30.00 Hz

Track rate:

    /tracks approximately 30.00 Hz

Tracker timing sample:

    track_ms approximately 0.04 ms

CPU and thermal:

    perception_camera_node CPU approximately 76.2 percent
    tracker_node CPU approximately 16.3 percent
    temperature approximately 59.3 C
    throttled = 0x0

## Conclusion

The integrated detector plus DeepSORT tracker process remains runtime-safe at 30 Hz, but this measurement does not validate real DeepSORT-MARS appearance performance. A fair DeepSORT test requires either a camera image publisher or direct internal frame access for appearance embedding extraction.
