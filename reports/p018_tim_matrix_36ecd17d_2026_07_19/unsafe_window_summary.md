# P0.18 Unsafe-Window Diagnostic

- Evaluator step: `0.05 s`
- Diagnostic SHA-256: `da5d01c86f2a2910e7d34079b7465fa79ad1b423f0ad0c1558fd19b589550f3d`

Only unsafe segments present in TIM but not in the matching raw stream are listed below.

## bytetrack

- `wrong` from `50.636` to `50.836 s` (`0.200 s`): output ID `42`, expected `1`, event `id_switch_fragmentation`.
- `wrong` from `58.035` to `58.535 s` (`0.500 s`): output ID `1`, expected `61`, event `id_switch_fragmentation`.

## sort

- `wrong` from `25.200` to `25.250 s` (`0.050 s`): output ID `2`, expected `1`, event `clean_visible`.
- `wrong` from `34.800` to `34.850 s` (`0.050 s`): output ID `85`, expected `98`, event `clean_visible`.
- `wrong` from `35.699` to `40.799 s` (`5.100 s`): output ID `98`, expected `109`, event `clean_visible`.
- `wrong` from `50.734` to `50.834 s` (`0.100 s`): output ID `109`, expected `158`, event `clean_visible`.
- `absent_output` from `55.631` to `55.781 s` (`0.150 s`): output ID `158`, expected `None`, event `target_absent`.

## ocsort

- `absent_output` from `58.330` to `58.530 s` (`0.200 s`): output ID `1`, expected `None`, event `target_absent`.

## deepsort

- `wrong` from `35.128` to `50.331 s` (`15.203 s`): output ID `58`, expected `2`, event `clean_visible`.
