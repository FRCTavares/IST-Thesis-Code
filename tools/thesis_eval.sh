#!/usr/bin/env bash
set -euo pipefail

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$THESIS_ROOT"

cmd="${1:-help}"

usage() {
  cat <<'EOF'
Usage:
  ./tools/thesis_eval.sh official-tim-vs-raw
  ./tools/thesis_eval.sh visual-validation-header-time
  ./tools/thesis_eval.sh target-correctness BAG ANNOTATIONS OUT_DIR [evaluator options]

Commands:
  official-tim-vs-raw
      Run the official hard-reentry raw-vs-TIM-MARS selected-target evaluation.

  visual-validation-header-time
      Render the official header-time raw-vs-TIM-MARS validation videos.

  target-correctness BAG ANNOTATIONS OUT_DIR
      Run the selected-target correctness evaluator on one bag.

Outputs:
  reports/official_tim_vs_raw_header_time_2026-06-17/
EOF
}

run_target_correctness() {
  local bag="$1"
  local ann="$2"
  local out="$3"
  shift 3

  python3 tools/analysis/evaluate_tim_target_correctness.py \
    "$bag" \
    --annotations "$ann" \
    --out-dir "$out" \
    "$@"
}

run_official_tim_vs_raw() {
  local out_root="reports/official_tim_vs_raw_header_time_2026-06-17"
  local base="artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1"

  mkdir -p "$out_root"

  run_target_correctness \
    "${base}__tracker_bytetrack__tim_off__target_1__r2" \
    "docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv" \
    "$out_root/bytetrack_raw" \
    --timebase header

  run_target_correctness \
    "${base}__tracker_bytetrack__tim_mars__target_1__r4" \
    "docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv" \
    "$out_root/bytetrack_tim_mars" \
    --timebase header

  run_target_correctness \
    "${base}__tracker_ocsort__tim_off__target_1" \
    "docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv" \
    "$out_root/ocsort_raw" \
    --timebase header

  run_target_correctness \
    "${base}__tracker_ocsort__tim_mars__target_1__r1" \
    "docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv" \
    "$out_root/ocsort_tim_mars" \
    --timebase header

  run_target_correctness \
    "${base}__tracker_deepsort__tim_off__target_1" \
    "docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv" \
    "$out_root/deepsort_raw" \
    --timebase header

  run_target_correctness \
    "${base}__tracker_deepsort__tim_mars__target_1" \
    "docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv" \
    "$out_root/deepsort_tim_mars" \
    --timebase header

  python3 - <<'PY'
from pathlib import Path
import csv

out_root = Path("reports/official_tim_vs_raw_header_time_2026-06-17")

cases = [
    ("ByteTrack", "Raw", "bytetrack_raw", "raw_target"),
    ("ByteTrack", "TIM-MARS", "bytetrack_tim_mars", "tim_target_memory"),
    ("OCSORT", "Raw", "ocsort_raw", "raw_target"),
    ("OCSORT", "TIM-MARS", "ocsort_tim_mars", "tim_target_memory"),
    ("DeepSORT-MARS", "Raw", "deepsort_raw", "raw_target"),
    ("DeepSORT-MARS", "TIM-MARS", "deepsort_tim_mars", "tim_target_memory"),
]

rows = []

for tracker, method, folder, preferred_stream in cases:
    path = out_root / folder / "summary.csv"
    with path.open(newline="") as f:
        data = list(csv.DictReader(f))

    streams = {r["stream"] for r in data}
    stream = preferred_stream

    if stream not in streams:
        if method == "Raw":
            candidates = [x for x in streams if "raw" in x]
        else:
            candidates = [x for x in streams if "tim" in x or "memory" in x]
        if not candidates:
            raise SystemExit(f"[error] no usable stream in {path}: {sorted(streams)}")
        stream = sorted(candidates)[0]

    r = next(x for x in data if x["stream"] == stream)

    rows.append({
        "tracker": tracker,
        "method": method,
        "stream": stream,
        "correct_s": float(r["correct_target_duration_s"]),
        "wrong_s": float(r["wrong_target_duration_s"]),
        "lost_s": float(r["lost_target_duration_s"]),
        "correct_ratio": float(r["correct_target_ratio"]),
        "wrong_ratio": float(r["wrong_target_ratio"]),
        "lost_ratio": float(r["lost_target_ratio"]),
        "wrong_reduction_vs_raw_s": "",
        "lost_reduction_vs_raw_s": "",
        "correct_gain_vs_raw_s": "",
    })

for tracker in sorted({r["tracker"] for r in rows}):
    raw = next(r for r in rows if r["tracker"] == tracker and r["method"] == "Raw")
    tim = next((r for r in rows if r["tracker"] == tracker and r["method"] == "TIM-MARS"), None)
    if tim:
        tim["wrong_reduction_vs_raw_s"] = raw["wrong_s"] - tim["wrong_s"]
        tim["lost_reduction_vs_raw_s"] = raw["lost_s"] - tim["lost_s"]
        tim["correct_gain_vs_raw_s"] = tim["correct_s"] - raw["correct_s"]

out_csv = out_root / "official_tim_vs_raw_summary.csv"
fields = [
    "tracker", "method", "stream",
    "correct_s", "wrong_s", "lost_s",
    "correct_ratio", "wrong_ratio", "lost_ratio",
    "wrong_reduction_vs_raw_s",
    "lost_reduction_vs_raw_s",
    "correct_gain_vs_raw_s",
]

with out_csv.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

def fmt(v):
    if v == "":
        return ""
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)

widths = {k: len(k) for k in fields}
for r in rows:
    for k in fields:
        widths[k] = max(widths[k], len(fmt(r[k])))

lines = []
header = " ".join(k.ljust(widths[k]) for k in fields)
lines.append(header)
lines.append(" ".join("-" * widths[k] for k in fields))
for r in rows:
    lines.append(" ".join(fmt(r[k]).ljust(widths[k]) for k in fields))

text = "\n".join(lines)
(out_root / "official_tim_vs_raw_summary.txt").write_text(text + "\n")

print()
print("=== FINAL OFFICIAL SUMMARY ===")
print(text)
print()
print(f"Wrote: {out_csv}")
print(f"Wrote: {out_root / 'official_tim_vs_raw_summary.txt'}")
PY
}

case "$cmd" in
  official-tim-vs-raw)
    run_official_tim_vs_raw
    ;;

  target-correctness)
    if [[ $# -lt 4 ]]; then
      usage
      exit 2
    fi
    run_target_correctness "$2" "$3" "$4" "${@:5}"
    ;;

  help|-h|--help)
    usage
    ;;

  visual-validation-header-time)
    python3 tools/visualization/video.py tim-header-all
    ;;

  *)
    echo "[error] unknown thesis_eval command: $cmd"
    usage
    exit 2
    ;;
esac
