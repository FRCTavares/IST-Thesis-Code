# VisDrone Person MOT Export

- Source root: `datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val`
- Output root: `datasets/processed/visdrone2019-mot/person_val_mot`
- Sequences: 7
- Total images: 2846
- Total person rows: 49848
- Total person IDs: 333

## Per-sequence export

| Sequence | Images | Size | Person rows | Person IDs | Tiny h<20 | Small h<40 | Occ 0 | Occ 1 | Occ 2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uav0000086_00000_v | 464 | 1344x756 | 21983 | 78 | 147 | 4855 | 13076 | 7248 | 1659 |
| uav0000117_02622_v | 349 | 2720x1530 | 9321 | 104 | 147 | 676 | 4391 | 4702 | 228 |
| uav0000137_00458_v | 233 | 2688x1512 | 9299 | 81 | 7 | 68 | 1846 | 7416 | 37 |
| uav0000182_00000_v | 363 | 1344x756 | 1175 | 24 | 2 | 710 | 616 | 554 | 5 |
| uav0000268_05773_v | 978 | 3840x2160 | 1984 | 6 | 0 | 1430 | 569 | 1270 | 145 |
| uav0000305_00000_v | 184 | 1904x1071 | 603 | 6 | 0 | 603 | 558 | 45 | 0 |
| uav0000339_00001_v | 275 | 1904x1071 | 5483 | 34 | 0 | 1500 | 1814 | 3397 | 272 |

## Generated roots

- Ground truth: `datasets/processed/visdrone2019-mot/person_val_mot/gt`
- Perfect predictions: `datasets/processed/visdrone2019-mot/person_val_mot/predictions/perfect`
- Summary CSV: `datasets/processed/visdrone2019-mot/person_val_mot/export_summary.csv`
