# Live coordinate and image-time contract

Contract version: `tim_mars_source_pixels_resize_v1`

This contract is authoritative for the current live pipeline. Historical bags
that predate the versioned header remain historical evidence and must not be
silently reinterpreted as current-contract output.

## Coordinate transform

The detector input uses an anisotropic direct resize from source dimensions
`(Ws, Hs)` to inference dimensions `(Wi, Hi)`. There is no padding:

- `scale_x = Wi / Ws`
- `scale_y = Hi / Hs`
- `pad_x = pad_y = 0`
- source to inference: `(xi, yi) = (xs * scale_x, ys * scale_y)`
- inference to source: `(xs, ys) = (xi / scale_x, yi / scale_y)`

The shared implementation is `ImageTransform` in
`thesis_bringup.perception.preprocessing`. Coordinates are clipped to the
inclusive source or inference image edges after mapping.

All public `/detections`, `/tracks`, `/target`, and
`/target_memory_mars` boxes use source-image pixel coordinates. Detector boxes
are inverted to the source frame before publication. Tracker adapters therefore
never mix square inference coordinates with source-image crops. Dashboard and
saved-overlay consumers normalize or draw these source-pixel boxes directly;
they must not apply another letterbox inverse.

Each `/detections` header carries the contract, processing frame number, source
and inference dimensions, scale, and padding. Example:

`tim_mars_source_pixels_resize_v1;frame=17;source=640x480;inference=640x640;scale=1,1.33333333;pad=0,0`

The same header is propagated by `/tracks` and target messages. `/timing`
continues to carry the exact source timestamp and source dimensions.
The live launcher also passes those source dimensions into TIM geometry and the
control reference node; their normalization must never fall back to the square
inference dimensions.

## Causal image selection

Appearance crops use the latest valid image whose header timestamp is less than
or equal to the tracker timestamp. Future images are never eligible.

- Missing or zero timestamps: discard the image or skip appearance extraction.
- Future-only buffer: skip appearance extraction.
- Stale image: skip appearance extraction when age exceeds the configured
  `max_image_age_ms` (250 ms in the DeepSORT live profile).
- Duplicate image timestamp: the final received image replaces the earlier one.
- Out-of-order/non-monotonic arrival: insert by timestamp, then select by causal
  order rather than arrival order.
- Bounded history: retain the newest 64 timestamps in the live profile.

TIM-MARS and DeepSORT both follow this latest-at-or-before rule. This prevents a
future or merely latest-arrived camera frame from supplying identity evidence
for an older tracker update.

## Verification

Synthetic tests cover 640x480 to 640x640, a non-4:3 source, edge clipping,
round trips within one pixel, source-frame detection publication, dashboard
normalization, delayed/out-of-order selection, duplicates, missing timestamps,
future-only buffers, staleness, and bounded history.

Recorded detector/tracker/TIM/dashboard visual alignment remains required before
Issue #53 can close and before flight-readiness Issue #50 can proceed.
