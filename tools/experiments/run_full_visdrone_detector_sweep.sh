#!/usr/bin/env bash
set -u

cd "${THESIS_ROOT:-$HOME/Desktop/Thesis-Code}"
source .venv/bin/activate

RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUT_BASE="reports/tracking/visdrone_full_detector_sweep_${RUN_ID}"
LOG="${OUT_BASE}/run.log"
SUMMARY="${OUT_BASE}/summary.csv"

mkdir -p "$OUT_BASE"

THRESHOLDS=("0.10" "0.15" "0.20" "0.25" "0.35")
TRACKERS="sort_live,ocsort_live,ocsort_benchmark,bytetrack_default"

echo "[info] run_id=$RUN_ID" | tee -a "$LOG"
echo "[info] out_base=$OUT_BASE" | tee -a "$LOG"
echo "[info] trackers=$TRACKERS" | tee -a "$LOG"
echo "[info] thresholds=${THRESHOLDS[*]}" | tee -a "$LOG"
echo "[info] models:" | tee -a "$LOG"
find models/hef -maxdepth 1 -type f -name "*.hef" | sort | tee -a "$LOG"

for HEF in $(find models/hef -maxdepth 1 -type f -name "*.hef" | sort); do
  MODEL="$(basename "$HEF" .hef)"

  for TH in "${THRESHOLDS[@]}"; do
    TH_TAG="${TH//./_}"
    OUT_ROOT="${OUT_BASE}/${MODEL}_th_${TH_TAG}"

    echo "" | tee -a "$LOG"
    echo "============================================================" | tee -a "$LOG"
    echo "[run] model=$MODEL hef=$HEF threshold=$TH" | tee -a "$LOG"
    echo "[run] out=$OUT_ROOT" | tee -a "$LOG"
    echo "============================================================" | tee -a "$LOG"

    python3 tools/experiments/run_visdrone_detector_tracker_matrix.py \
      --hef "$HEF" \
      --model-name "$MODEL" \
      --trackers "$TRACKERS" \
      --score-threshold "$TH" \
      --out-root "$OUT_ROOT" \
      2>&1 | tee -a "$LOG"

    STATUS="${PIPESTATUS[0]}"
    if [ "$STATUS" -ne 0 ]; then
      echo "[fail] model=$MODEL threshold=$TH status=$STATUS" | tee -a "$LOG"
    else
      echo "[ok] model=$MODEL threshold=$TH" | tee -a "$LOG"
    fi
  done
done

echo "[info] aggregating summary..." | tee -a "$LOG"

python3 - <<'PY'
from pathlib import Path
import csv
import re

out_base = sorted(Path("reports/tracking").glob("visdrone_full_detector_sweep_*"))[-1]
rows = []

for run_dir in sorted(out_base.iterdir()):
    if not run_dir.is_dir():
        continue

    m = re.match(r"(.+)_th_(\d+)_(\d+)$", run_dir.name)
    if not m:
        continue

    model = m.group(1)
    threshold = f"{m.group(2)}.{m.group(3)}"

    eval_dir = run_dir / "eval"
    det_csv = run_dir / "detector_runtime_summary.csv"
    tracker_csv = run_dir / "tracker_runtime_summary.csv"

    det_frames = det_raw = det_kept = 0
    det_infer_weighted_sum = 0.0
    det_infer_p95_max = 0.0

    if det_csv.exists():
        with det_csv.open(newline="") as f:
            for r in csv.DictReader(f):
                frames = int(r["frames"])
                det_frames += frames
                det_raw += int(r["raw_detections"])
                det_kept += int(r["kept_detections"])
                det_infer_weighted_sum += float(r["infer_ms_mean"]) * frames
                det_infer_p95_max = max(det_infer_p95_max, float(r["infer_ms_p95"]))

    tracker_runtime = {}
    if tracker_csv.exists():
        tmp = {}
        with tracker_csv.open(newline="") as f:
            for r in csv.DictReader(f):
                tracker = r["tracker"]
                tmp.setdefault(tracker, {"frames": 0, "sum": 0.0, "p95max": 0.0})
                frames = int(r["frames"])
                tmp[tracker]["frames"] += frames
                tmp[tracker]["sum"] += float(r["track_ms_mean"]) * frames
                tmp[tracker]["p95max"] = max(tmp[tracker]["p95max"], float(r["track_ms_p95"]))
        for tracker, v in tmp.items():
            tracker_runtime[tracker] = {
                "track_ms_mean_weighted": v["sum"] / v["frames"] if v["frames"] else 0.0,
                "track_ms_p95_max": v["p95max"],
            }

    if not eval_dir.exists():
        continue

    for summary_csv in sorted(eval_dir.glob("*/summary.csv")):
        tracker_name = summary_csv.parent.name
        if "__" in tracker_name:
            _, tracker = tracker_name.split("__", 1)
        else:
            tracker = tracker_name

        overall = None
        with summary_csv.open(newline="") as f:
            for r in csv.DictReader(f):
                if r["sequence"] == "OVERALL":
                    overall = r
                    break

        if overall is None:
            continue

        rt = tracker_runtime.get(tracker, {})
        rows.append({
            "model": model,
            "threshold": threshold,
            "tracker": tracker,
            "mota": overall["mota"],
            "idf1": overall["idf1"],
            "fp": overall["fp"],
            "fn": overall["fn"],
            "id_switches": overall["id_switches"],
            "fragments": overall["fragments"],
            "gt": overall["gt"],
            "pred": overall["pred"],
            "det_frames": det_frames,
            "det_raw": det_raw,
            "det_kept": det_kept,
            "infer_ms_mean_weighted": det_infer_weighted_sum / det_frames if det_frames else 0.0,
            "infer_ms_p95_max": det_infer_p95_max,
            "track_ms_mean_weighted": rt.get("track_ms_mean_weighted", 0.0),
            "track_ms_p95_max": rt.get("track_ms_p95_max", 0.0),
            "run_dir": str(run_dir),
        })

summary = out_base / "summary.csv"
if rows:
    with summary.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"[ok] wrote {summary}")

    ranked = sorted(rows, key=lambda r: float(r["idf1"]), reverse=True)[:20]
    print("\nTop 20 by IDF1:")
    for r in ranked:
        print(
            f"{r['model']} th={r['threshold']} {r['tracker']} "
            f"IDF1={100*float(r['idf1']):.2f}% "
            f"MOTA={100*float(r['mota']):.2f}% "
            f"IDSW={float(r['id_switches']):.0f} "
            f"FN={float(r['fn']):.0f} "
            f"FP={float(r['fp']):.0f}"
        )
else:
    print("[warn] no rows found")
PY

echo "[done] full sweep completed" | tee -a "$LOG"
echo "[done] summary: $SUMMARY" | tee -a "$LOG"
