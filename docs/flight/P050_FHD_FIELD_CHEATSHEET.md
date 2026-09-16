# FHD Appearance Test

Development / non-held-out only.

The representative FHD capture is complete.

## Retained master

File:

    bags/development/fhd_appearance/20260915T152745Z_fhd_drone_pov_15sep_1920x1080_mjpeg.mkv

Recorded 15 September 2026.

Verified properties:

- 1920x1080 MJPEG
- 2208 decoded frames
- 85.809 s
- approximately 25.73 fps
- 1,004,727,994 bytes
- full decode check passed
- Mac backup verified byte-for-byte

SHA-256:

    17c6e654903274afcc2b7e2479554bec99ae8fd08a516c14c290049bc81eee4e

Do not recapture this merely to obtain a different result.

## Remaining work

Use this same FHD master for the matched resolution comparison.

1. inspect representative target geometry;
2. extract the exact FHD frames;
3. derive the lower-resolution condition from those same frames;
4. use identical frame indices;
5. run the same downstream appearance evaluation on both;
6. compare native FHD against derived HD.

Do not record a separate HD sequence. That would introduce scene and timing differences.

## Held-out boundary

H01/H02/H03 remain separate 640x480 held-out sequences.

This FHD development experiment must not modify their frozen acquisition or evaluation contract.

## Active Issue #64 question

Determine whether native FHD provides a measurable appearance benefit for the representative distant/small-person drone viewpoint.

The capture itself does not answer that question. The matched evaluation still does.
