#!/usr/bin/env bash
set -euo pipefail

# Prepare a local, non-root TAPPAS runtime tree for single-process perception mode.
# This script extracts a known public hailo-tappas-core package and adds .so.5
# compatibility symlinks required by newer Python bindings.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BASE_URL="${BASE_URL:-http://dev-public.hailo.ai/2025_01}"
TAPPAS_VERSION="${TAPPAS_VERSION:-3.31.0}"
OUTPUT_DIR="${OUTPUT_DIR:-$THESIS_ROOT/infer_service/opt/tappas_runtime_3_31}"
FORCE=0

print_usage() {
    cat <<'EOF'
Usage: setup_local_tappas_runtime.sh [options]

Options:
  --output-dir <path>        Extraction root (default: infer_service/opt/tappas_runtime_3_31)
  --base-url <url>           Artifact base URL (default: http://dev-public.hailo.ai/2025_01)
  --tappas-version <ver>     Package version (default: 3.31.0)
  --force                    Re-extract even if output already exists
  -h, --help                 Show help

Environment overrides:
  THESIS_ROOT, BASE_URL, TAPPAS_VERSION, OUTPUT_DIR
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --tappas-version)
            TAPPAS_VERSION="$2"
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "[error] unknown argument: $1"
            print_usage
            exit 1
            ;;
    esac
done

if ! command -v wget >/dev/null 2>&1; then
    echo "[error] wget is required"
    exit 1
fi
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "[error] dpkg-deb is required"
    exit 1
fi

DEB_NAME="hailo-tappas-core_${TAPPAS_VERSION}_arm64.deb"
DEB_URL="${BASE_URL}/${DEB_NAME}"
CACHE_DIR="${OUTPUT_DIR}/.cache"
DEB_PATH="${CACHE_DIR}/${DEB_NAME}"

mkdir -p "$CACHE_DIR"

if ! wget --spider -q "$DEB_URL"; then
    echo "[error] unable to reach package URL: $DEB_URL"
    echo "[hint] check version/base URL or use a package from Hailo Developer Zone"
    exit 2
fi

if [[ ! -f "$DEB_PATH" ]] || [[ "$FORCE" -eq 1 ]]; then
    echo "[step] downloading $DEB_NAME"
    wget -q "$DEB_URL" -O "$DEB_PATH"
else
    echo "[info] using cached package: $DEB_PATH"
fi

if [[ -d "$OUTPUT_DIR/usr" ]] && [[ "$FORCE" -ne 1 ]]; then
    echo "[info] runtime already exists at: $OUTPUT_DIR"
    echo "[hint] re-run with --force to refresh"
else
    echo "[step] extracting runtime to $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR/usr"
    dpkg-deb -x "$DEB_PATH" "$OUTPUT_DIR"
fi

LIB_DIR="$OUTPUT_DIR/usr/lib/aarch64-linux-gnu"
if [[ ! -d "$LIB_DIR" ]]; then
    echo "[error] expected library directory missing after extraction: $LIB_DIR"
    exit 3
fi

ln -sfn libgsthailometa.so.3.31.0 "$LIB_DIR/libgsthailometa.so.5"
ln -sfn libhailo_tracker.so.3.31.0 "$LIB_DIR/libhailo_tracker.so.5"
ln -sfn libhailo_gst_image.so.3.31.0 "$LIB_DIR/libhailo_gst_image.so.5"
ln -sfn libhailo_cv_singleton.so.3.31.0 "$LIB_DIR/libhailo_cv_singleton.so.5"

echo "[done] local TAPPAS runtime prepared"
echo "[info] runtime root: $OUTPUT_DIR"
echo "[info] next: run ./tools/start_live_stack.sh --perception-mode single-process"
