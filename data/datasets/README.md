# Datasets

Large datasets are not committed to Git.

## VisDrone2019-MOT

Official split currently used:
- `VisDrone2019-MOT-val`

Local layout:
- `data/datasets/external/visdrone2019-mot/raw/`: official downloaded zip files
- `data/datasets/external/visdrone2019-mot/extracted/`: extracted official dataset files
- `data/datasets/processed/visdrone2019-mot/`: generated manifests, summaries, caches, and converted formats

Current purpose:
- detector/tracker benchmarking
- selected-target continuity evaluation
- small-person and occlusion analysis
