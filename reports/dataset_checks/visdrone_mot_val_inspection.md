# VisDrone2019-MOT Val Inspection

- Dataset root: `datasets/external/visdrone2019-mot/extracted/VisDrone2019-MOT-val`
- Sequences: 7
- Total images: 2846
- All person instances, class 1/2: 50312
- Valid person instances, class 1/2: 49848
- Valid person track IDs, class 1/2: 333

## Class counts

| Class ID | Name | Count |
|---:|---|---:|
| 0 | ignored-region | 3994 |
| 1 | pedestrian | 32404 |
| 2 | people | 17908 |
| 3 | bicycle | 6022 |
| 4 | car | 31821 |
| 5 | van | 6842 |
| 6 | truck | 1359 |
| 7 | tricycle | 3769 |
| 8 | awning-tricycle | 1718 |
| 9 | bus | 264 |
| 10 | motor | 12025 |
| 11 | others | 1 |

## Per-sequence summary

| Sequence | Images | Valid person rows | Valid person IDs | Tiny h<20 | Small h<40 | Occ 0 | Occ 1 | Occ 2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| uav0000086_00000_v | 464 | 21983 | 78 | 147 | 4855 | 13076 | 7248 | 1659 |
| uav0000117_02622_v | 349 | 9321 | 104 | 147 | 676 | 4391 | 4702 | 228 |
| uav0000137_00458_v | 233 | 9299 | 81 | 7 | 68 | 1846 | 7416 | 37 |
| uav0000182_00000_v | 363 | 1175 | 24 | 2 | 710 | 616 | 554 | 5 |
| uav0000268_05773_v | 978 | 1984 | 6 | 0 | 1430 | 569 | 1270 | 145 |
| uav0000305_00000_v | 184 | 603 | 6 | 0 | 603 | 558 | 45 | 0 |
| uav0000339_00001_v | 275 | 5483 | 34 | 0 | 1500 | 1814 | 3397 | 272 |

## Generated files

- `datasets/processed/visdrone2019-mot/val_manifest.csv`
- `datasets/processed/visdrone2019-mot/val_summary.json`
