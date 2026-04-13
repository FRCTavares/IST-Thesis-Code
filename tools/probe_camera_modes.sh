#!/usr/bin/env bash
set -euo pipefail

# Probe practical camera stream rates per mode via v4l2-ctl.
# Intended for quick post-reboot diagnostics on Pi camera pipelines.

DEVICE="/dev/video0"
STREAM_COUNT=180
MMAP_BUFFERS=4
TIMEOUT_S=25

MODES=(
  "1280x720:UYVY"
  "960x540:UYVY"
  "640x480:UYVY"
  "1280x720:YUYV"
  "960x540:YUYV"
  "640x480:YUYV"
)

usage() {
  cat <<'EOF'
Usage: tools/probe_camera_modes.sh [options]

Options:
  --device <path>             Video device path (default: /dev/video0)
  --count <N>                 Frames to stream per mode (default: 180)
  --mmap <N>                  v4l2 mmap buffers (default: 4)
  --timeout-s <N>             Per-mode timeout seconds (default: 25)
  --mode <WxH:FOURCC>         Add/override a test mode (can repeat)
  -h, --help                  Show this help

Examples:
  tools/probe_camera_modes.sh
  tools/probe_camera_modes.sh --device /dev/video24 --count 120
  tools/probe_camera_modes.sh --mode 1280x720:UYVY --mode 640x480:UYVY
EOF
}

CUSTOM_MODES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --device)
      DEVICE="$2"
      shift 2
      ;;
    --count)
      STREAM_COUNT="$2"
      shift 2
      ;;
    --mmap)
      MMAP_BUFFERS="$2"
      shift 2
      ;;
    --timeout-s)
      TIMEOUT_S="$2"
      shift 2
      ;;
    --mode)
      CUSTOM_MODES+=("$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] Unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ ${#CUSTOM_MODES[@]} -gt 0 ]]; then
  MODES=("${CUSTOM_MODES[@]}")
fi

if ! command -v v4l2-ctl >/dev/null 2>&1; then
  echo "[error] v4l2-ctl not found in PATH"
  exit 2
fi

if [[ ! -e "$DEVICE" ]]; then
  echo "[error] Device not found: $DEVICE"
  exit 2
fi

stuck="$(ps -eo stat=,cmd= | awk '/camera_capture_node/ && $1 ~ /^D/ {print}')"
if [[ -n "$stuck" ]]; then
  echo "[error] Detected stuck camera process in D state. Reboot before probing modes."
  echo "$stuck"
  exit 3
fi

echo "[info] probing device: $DEVICE"
echo "[info] stream_count=$STREAM_COUNT mmap=$MMAP_BUFFERS timeout_s=$TIMEOUT_S"

printf "%-14s %-8s %-8s %-10s %-s\n" "mode" "status" "fps" "elapsed_s" "note"
printf "%-14s %-8s %-8s %-10s %-s\n" "--------------" "--------" "--------" "----------" "-------------------------"

for entry in "${MODES[@]}"; do
  mode="${entry%%:*}"
  fourcc="${entry##*:}"
  width="${mode%x*}"
  height="${mode#*x}"

  if [[ -z "$width" || -z "$height" || -z "$fourcc" ]]; then
    printf "%-14s %-8s %-8s %-10s %-s\n" "$entry" "invalid" "-" "-" "bad mode format"
    continue
  fi

  cmd=(
    v4l2-ctl -d "$DEVICE"
    --set-fmt-video="width=${width},height=${height},pixelformat=${fourcc}"
    --stream-mmap="$MMAP_BUFFERS"
    --stream-count="$STREAM_COUNT"
    --stream-to=/dev/null
  )

  start_ts="$(date +%s.%N)"
  set +e
  out="$(timeout "$TIMEOUT_S" "${cmd[@]}" 2>&1)"
  rc=$?
  set -e
  end_ts="$(date +%s.%N)"

  elapsed="$(awk -v s="$start_ts" -v e="$end_ts" 'BEGIN {printf "%.2f", (e - s)}')"

  fps="$(printf '%s\n' "$out" | awk '/fps/ {for (i=1; i<=NF; i++) if ($i=="fps") print $(i-1)}' | tail -n 1)"
  if [[ -z "$fps" ]]; then
    fps="-"
  fi

  note="ok"
  status="ok"
  if [[ $rc -ne 0 ]]; then
    status="fail"
    if [[ $rc -eq 124 ]]; then
      note="timeout"
    else
      err_line="$(printf '%s\n' "$out" | tail -n 1 | tr -d '\r')"
      note="${err_line:-rc=$rc}"
    fi
  fi

  printf "%-14s %-8s %-8s %-10s %-s\n" "${mode}:${fourcc}" "$status" "$fps" "$elapsed" "$note"
done

echo "[info] probe complete"
