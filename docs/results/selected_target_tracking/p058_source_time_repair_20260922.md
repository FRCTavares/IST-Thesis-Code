# #58 source-time repair: old versus corrected physical-v2 metrics

Post-access evaluator correctness repair; the 16 September evidence and physical-v2 scoring core are unchanged.
Delta is corrected minus old. Times use seconds; IoU is a fraction and centre error is pixels.
The companion JSON retains full precision, report hashes, source origins and output-read statistics.

## heldout_h01_exit_reentry

Source origin: `1789486281308955860` ns from `header.stamp`.

| Architecture | Topic | Messages | src_stamp_ns | header.stamp | Bag record | Duplicate replaced | Non-monotonic skipped |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bytetrack_raw | /target | 1865 | 1865 | 0 | 0 | 0 | 0 |
| target_reid_090 | /target_reid | 1865 | 1865 | 0 | 0 | 0 | 0 |
| bytetrack_tim_mars | /target | 1865 | 1865 | 0 | 0 | 0 | 0 |
| bytetrack_tim_mars | /target_memory_mars | 1865 | 1865 | 0 | 0 | 0 | 0 |
| deepsort_raw | /target | 1865 | 1865 | 0 | 0 | 0 | 0 |

| Architecture | Metric | Old | Corrected | Delta |
| --- | --- | ---: | ---: | ---: |
| bytetrack_raw | correct_target_output_duration_s (s) | 4.533121531 | 4.566355193 | 0.033233662 |
| bytetrack_raw | wrong_person_output_duration_s (s) | 3.833477614 | 3.866438284 | 0.032960670 |
| bytetrack_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | lost_or_suppressed_duration_s (s) | 31.266607781 | 31.200413449 | -0.066194332 |
| bytetrack_raw | target_absent_duration_s (s) | 22.300219460 | 22.300219460 | 0.000000000 |
| bytetrack_raw | target_absent_with_output_duration_s (s) | 1.200480990 | 1.166724353 | -0.033756637 |
| bytetrack_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | reference_gap_duration_s (s) | 0.133013131 | 0.133013131 | 0.000000000 |
| bytetrack_raw | reference_gap_with_output_duration_s (s) | 0.033189254 | 0.033189254 | 0.000000000 |
| bytetrack_raw | iou_duration_weighted_mean (fraction) | 0.810649453 | 0.859508693 | 0.048859239 |
| bytetrack_raw | iou_median (fraction) | 0.809084946 | 0.880428626 | 0.071343681 |
| bytetrack_raw | centre_error_px_duration_weighted_mean (px) | 3.326769239 | 2.139034989 | -1.187734250 |
| bytetrack_raw | scored_duration_s (s) | 4.533121531 | 4.566355193 | 0.033233662 |
| bytetrack_raw | n_samples (count) | 215 | 218 | 3 |
| target_reid_090 | correct_target_output_duration_s (s) | 2.633099069 | 2.599837960 | -0.033261109 |
| target_reid_090 | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | lost_or_suppressed_duration_s (s) | 37.000107857 | 37.033368966 | 0.033261109 |
| target_reid_090 | target_absent_duration_s (s) | 22.300219460 | 22.300219460 | 0.000000000 |
| target_reid_090 | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | reference_gap_duration_s (s) | 0.133013131 | 0.133013131 | 0.000000000 |
| target_reid_090 | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | iou_duration_weighted_mean (fraction) | 0.735995145 | 0.858685156 | 0.122690011 |
| target_reid_090 | iou_median (fraction) | 0.766722432 | 0.865906883 | 0.099184451 |
| target_reid_090 | centre_error_px_duration_weighted_mean (px) | 5.538390749 | 2.078070828 | -3.460319921 |
| target_reid_090 | scored_duration_s (s) | 2.633099069 | 2.599837960 | -0.033261109 |
| target_reid_090 | n_samples (count) | 131 | 129 | -2 |
| bytetrack_tim_mars | correct_target_output_duration_s (s) | 30.016216755 | 30.299888246 | 0.283671491 |
| bytetrack_tim_mars | wrong_person_output_duration_s (s) | 0.099977678 | 0.000000000 | -0.099977678 |
| bytetrack_tim_mars | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | lost_or_suppressed_duration_s (s) | 9.517012493 | 9.333318680 | -0.183693813 |
| bytetrack_tim_mars | target_absent_duration_s (s) | 22.300219460 | 22.300219460 | 0.000000000 |
| bytetrack_tim_mars | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_duration_s (s) | 0.133013131 | 0.133013131 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | iou_duration_weighted_mean (fraction) | 0.742899501 | 0.835282492 | 0.092382991 |
| bytetrack_tim_mars | iou_median (fraction) | 0.754781974 | 0.845393216 | 0.090611243 |
| bytetrack_tim_mars | centre_error_px_duration_weighted_mean (px) | 6.063314944 | 2.894892364 | -3.168422580 |
| bytetrack_tim_mars | scored_duration_s (s) | 30.016216755 | 30.299888246 | 0.283671491 |
| bytetrack_tim_mars | n_samples (count) | 1477 | 1495 | 18 |
| deepsort_raw | correct_target_output_duration_s (s) | 9.316574000 | 9.433317301 | 0.116743301 |
| deepsort_raw | wrong_person_output_duration_s (s) | 0.099977678 | 0.000000000 | -0.099977678 |
| deepsort_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | lost_or_suppressed_duration_s (s) | 30.216655248 | 30.199889625 | -0.016765623 |
| deepsort_raw | target_absent_duration_s (s) | 22.300219460 | 22.300219460 | 0.000000000 |
| deepsort_raw | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | reference_gap_duration_s (s) | 0.133013131 | 0.133013131 | 0.000000000 |
| deepsort_raw | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | iou_duration_weighted_mean (fraction) | 0.747045645 | 0.833055264 | 0.086009620 |
| deepsort_raw | iou_median (fraction) | 0.756645669 | 0.837881534 | 0.081235865 |
| deepsort_raw | centre_error_px_duration_weighted_mean (px) | 4.427756595 | 2.274638146 | -2.153118449 |
| deepsort_raw | scored_duration_s (s) | 9.316574000 | 9.433317301 | 0.116743301 |
| deepsort_raw | n_samples (count) | 452 | 459 | 7 |

## heldout_h02_crossing

Source origin: `1789486544612758276` ns from `header.stamp`.

| Architecture | Topic | Messages | src_stamp_ns | header.stamp | Bag record | Duplicate replaced | Non-monotonic skipped |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bytetrack_raw | /target | 1544 | 1544 | 0 | 0 | 0 | 0 |
| target_reid_090 | /target_reid | 1544 | 1544 | 0 | 0 | 0 | 0 |
| bytetrack_tim_mars | /target_memory_mars | 1544 | 1544 | 0 | 0 | 0 | 0 |
| deepsort_raw | /target | 1544 | 1544 | 0 | 0 | 0 | 0 |

| Architecture | Metric | Old | Corrected | Delta |
| --- | --- | ---: | ---: | ---: |
| bytetrack_raw | correct_target_output_duration_s (s) | 16.066702430 | 16.233310777 | 0.166608347 |
| bytetrack_raw | wrong_person_output_duration_s (s) | 15.899951887 | 15.666769110 | -0.233182777 |
| bytetrack_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | lost_or_suppressed_duration_s (s) | 13.666725519 | 13.733299949 | 0.066574430 |
| bytetrack_raw | target_absent_duration_s (s) | 5.733018365 | 5.733018365 | 0.000000000 |
| bytetrack_raw | target_absent_with_output_duration_s (s) | 0.233353659 | 0.299976461 | 0.066622802 |
| bytetrack_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | reference_gap_duration_s (s) | 0.033327126 | 0.033327126 | 0.000000000 |
| bytetrack_raw | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | iou_duration_weighted_mean (fraction) | 0.768364007 | 0.804583830 | 0.036219823 |
| bytetrack_raw | iou_median (fraction) | 0.777890790 | 0.812304101 | 0.034413311 |
| bytetrack_raw | centre_error_px_duration_weighted_mean (px) | 5.253598462 | 4.084417563 | -1.169180899 |
| bytetrack_raw | scored_duration_s (s) | 16.066702430 | 16.233310777 | 0.166608347 |
| bytetrack_raw | n_samples (count) | 793 | 799 | 6 |
| target_reid_090 | correct_target_output_duration_s (s) | 0.100030561 | 0.100024042 | -0.000006519 |
| target_reid_090 | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | lost_or_suppressed_duration_s (s) | 45.533349275 | 45.533355794 | 0.000006519 |
| target_reid_090 | target_absent_duration_s (s) | 5.733018365 | 5.733018365 | 0.000000000 |
| target_reid_090 | target_absent_with_output_duration_s (s) | 0.066536805 | 0.066869644 | 0.000332839 |
| target_reid_090 | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | reference_gap_duration_s (s) | 0.033327126 | 0.033327126 | 0.000000000 |
| target_reid_090 | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | iou_duration_weighted_mean (fraction) | 0.642684958 | 0.645110023 | 0.002425065 |
| target_reid_090 | iou_median (fraction) | 0.637761599 | 0.637761599 | 0.000000000 |
| target_reid_090 | centre_error_px_duration_weighted_mean (px) | 9.389758778 | 10.346191484 | 0.956432706 |
| target_reid_090 | scored_duration_s (s) | 0.100030561 | 0.100024042 | -0.000006519 |
| target_reid_090 | n_samples (count) | 5 | 5 | 0 |
| bytetrack_tim_mars | correct_target_output_duration_s (s) | 11.700053330 | 11.633283986 | -0.066769344 |
| bytetrack_tim_mars | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | lost_or_suppressed_duration_s (s) | 33.933326506 | 34.000095850 | 0.066769344 |
| bytetrack_tim_mars | target_absent_duration_s (s) | 5.733018365 | 5.733018365 | 0.000000000 |
| bytetrack_tim_mars | target_absent_with_output_duration_s (s) | 0.233353659 | 0.299976461 | 0.066622802 |
| bytetrack_tim_mars | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_duration_s (s) | 0.033327126 | 0.033327126 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | iou_duration_weighted_mean (fraction) | 0.773036395 | 0.829303015 | 0.056266620 |
| bytetrack_tim_mars | iou_median (fraction) | 0.777890790 | 0.831397022 | 0.053506231 |
| bytetrack_tim_mars | centre_error_px_duration_weighted_mean (px) | 5.402760452 | 3.372876334 | -2.029884118 |
| bytetrack_tim_mars | scored_duration_s (s) | 11.700053330 | 11.633283986 | -0.066769344 |
| bytetrack_tim_mars | n_samples (count) | 575 | 571 | -4 |
| deepsort_raw | correct_target_output_duration_s (s) | 13.666611696 | 13.600045426 | -0.066566270 |
| deepsort_raw | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | lost_or_suppressed_duration_s (s) | 31.966768140 | 32.033334410 | 0.066566270 |
| deepsort_raw | target_absent_duration_s (s) | 5.733018365 | 5.733018365 | 0.000000000 |
| deepsort_raw | target_absent_with_output_duration_s (s) | 0.233353659 | 0.299976461 | 0.066622802 |
| deepsort_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | reference_gap_duration_s (s) | 0.033327126 | 0.033327126 | 0.000000000 |
| deepsort_raw | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | iou_duration_weighted_mean (fraction) | 0.780619189 | 0.821758516 | 0.041139328 |
| deepsort_raw | iou_median (fraction) | 0.787957374 | 0.831019749 | 0.043062375 |
| deepsort_raw | centre_error_px_duration_weighted_mean (px) | 4.742906391 | 3.335481224 | -1.407425167 |
| deepsort_raw | scored_duration_s (s) | 13.666611696 | 13.600045426 | -0.066566270 |
| deepsort_raw | n_samples (count) | 673 | 671 | -2 |

## heldout_h03_occlusion_distractor

Source origin: `1789487735873995680` ns from `header.stamp`.

| Architecture | Topic | Messages | src_stamp_ns | header.stamp | Bag record | Duplicate replaced | Non-monotonic skipped |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bytetrack_raw | /target | 1485 | 1485 | 0 | 0 | 0 | 0 |
| target_reid_090 | /target_reid | 1485 | 1485 | 0 | 0 | 0 | 0 |
| bytetrack_tim_mars | /target_memory_mars | 1485 | 1485 | 0 | 0 | 0 | 0 |
| deepsort_raw | /target | 1485 | 1485 | 0 | 0 | 0 | 0 |

| Architecture | Metric | Old | Corrected | Delta |
| --- | --- | ---: | ---: | ---: |
| bytetrack_raw | correct_target_output_duration_s (s) | 27.232552230 | 27.182607492 | -0.049944738 |
| bytetrack_raw | wrong_person_output_duration_s (s) | 16.867387125 | 16.783789008 | -0.083598117 |
| bytetrack_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | lost_or_suppressed_duration_s (s) | 1.999696322 | 2.133239177 | 0.133542855 |
| bytetrack_raw | target_absent_duration_s (s) | 3.300094282 | 3.300094282 | 0.000000000 |
| bytetrack_raw | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | reference_gap_duration_s (s) | 0.033323821 | 0.033323821 | 0.000000000 |
| bytetrack_raw | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_raw | iou_duration_weighted_mean (fraction) | 0.796029242 | 0.822484288 | 0.026455046 |
| bytetrack_raw | iou_median (fraction) | 0.813235058 | 0.837572432 | 0.024337374 |
| bytetrack_raw | centre_error_px_duration_weighted_mean (px) | 3.427353331 | 2.696779010 | -0.730574320 |
| bytetrack_raw | scored_duration_s (s) | 27.232552230 | 27.182607492 | -0.049944738 |
| bytetrack_raw | n_samples (count) | 1338 | 1336 | -2 |
| target_reid_090 | correct_target_output_duration_s (s) | 0.467069612 | 0.496025647 | 0.028956035 |
| target_reid_090 | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | lost_or_suppressed_duration_s (s) | 45.632566065 | 45.603610030 | -0.028956035 |
| target_reid_090 | target_absent_duration_s (s) | 3.300094282 | 3.300094282 | 0.000000000 |
| target_reid_090 | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | reference_gap_duration_s (s) | 0.033323821 | 0.033323821 | 0.000000000 |
| target_reid_090 | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| target_reid_090 | iou_duration_weighted_mean (fraction) | 0.900165596 | 0.921214115 | 0.021048519 |
| target_reid_090 | iou_median (fraction) | 0.929269126 | 0.938450450 | 0.009181324 |
| target_reid_090 | centre_error_px_duration_weighted_mean (px) | 1.358469942 | 0.933527540 | -0.424942403 |
| target_reid_090 | scored_duration_s (s) | 0.467069612 | 0.496025647 | 0.028956035 |
| target_reid_090 | n_samples (count) | 24 | 25 | 1 |
| bytetrack_tim_mars | correct_target_output_duration_s (s) | 20.932933131 | 20.866269431 | -0.066663700 |
| bytetrack_tim_mars | wrong_person_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | lost_or_suppressed_duration_s (s) | 25.166702546 | 25.233366246 | 0.066663700 |
| bytetrack_tim_mars | target_absent_duration_s (s) | 3.300094282 | 3.300094282 | 0.000000000 |
| bytetrack_tim_mars | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_duration_s (s) | 0.033323821 | 0.033323821 | 0.000000000 |
| bytetrack_tim_mars | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| bytetrack_tim_mars | iou_duration_weighted_mean (fraction) | 0.794696943 | 0.822497291 | 0.027800348 |
| bytetrack_tim_mars | iou_median (fraction) | 0.812827061 | 0.838169810 | 0.025342749 |
| bytetrack_tim_mars | centre_error_px_duration_weighted_mean (px) | 3.390634459 | 2.630154535 | -0.760479924 |
| bytetrack_tim_mars | scored_duration_s (s) | 20.932933131 | 20.866269431 | -0.066663700 |
| bytetrack_tim_mars | n_samples (count) | 1029 | 1026 | -3 |
| deepsort_raw | correct_target_output_duration_s (s) | 45.183591414 | 45.199796817 | 0.016205403 |
| deepsort_raw | wrong_person_output_duration_s (s) | 0.066686546 | 0.000000000 | -0.066686546 |
| deepsort_raw | identity_unresolved_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | lost_or_suppressed_duration_s (s) | 0.849357717 | 0.899838860 | 0.050481143 |
| deepsort_raw | target_absent_duration_s (s) | 3.300094282 | 3.300094282 | 0.000000000 |
| deepsort_raw | target_absent_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | reference_unavailable_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | reference_gap_duration_s (s) | 0.033323821 | 0.033323821 | 0.000000000 |
| deepsort_raw | reference_gap_with_output_duration_s (s) | 0.000000000 | 0.000000000 | 0.000000000 |
| deepsort_raw | iou_duration_weighted_mean (fraction) | 0.788016237 | 0.815775208 | 0.027758971 |
| deepsort_raw | iou_median (fraction) | 0.797860910 | 0.826186014 | 0.028325103 |
| deepsort_raw | centre_error_px_duration_weighted_mean (px) | 3.606350231 | 2.751151272 | -0.855198959 |
| deepsort_raw | scored_duration_s (s) | 45.183591414 | 45.199796817 | 0.016205403 |
| deepsort_raw | n_samples (count) | 2236 | 2236 | 0 |
