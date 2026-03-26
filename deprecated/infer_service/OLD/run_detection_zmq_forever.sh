#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[forever] Starting detection loop..."
i=0
while true; do
  i=$((i+1))
  echo "[forever] Run #${i} $(date -Iseconds)"
  ./run_detection_zmq.sh || true
  echo "[forever] Pipeline exited (EOS or error). Restarting in 1s..."
  sleep 1
done
