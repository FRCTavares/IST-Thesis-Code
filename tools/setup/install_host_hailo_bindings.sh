#!/usr/bin/env bash
set -euo pipefail

# Installs host-side Hailo Python bindings into a target virtualenv when a
# matching wheel exists for that virtualenv Python ABI.

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV_PATH="${VENV_PATH:-$THESIS_ROOT/.venv}"
BASE_URL="${BASE_URL:-https://dev-public.hailo.ai/2025_07}"
HAILORT_VERSION="${HAILORT_VERSION:-4.23.0}"
TAPPAS_CORE_VERSION="${TAPPAS_CORE_VERSION:-5.1.0}"
HAILO_EXAMPLES_DIR="${HAILO_EXAMPLES_DIR:-$THESIS_ROOT/deprecated/hailo-rpi5-examples}"
if [[ ! -d "$HAILO_EXAMPLES_DIR" && -d "$THESIS_ROOT/hailo-rpi5-examples" ]]; then
    HAILO_EXAMPLES_DIR="$THESIS_ROOT/hailo-rpi5-examples"
fi
DOWNLOAD_DIR="${DOWNLOAD_DIR:-$HAILO_EXAMPLES_DIR/hailo_temp_resources}"
HAILORT_WHEEL_SRC="${HAILORT_WHEEL_SRC:-}"
TAPPAS_WHEEL_SRC="${TAPPAS_WHEEL_SRC:-}"
SKIP_SYSTEM_CHECK=0
INSTALL_TAPPAS_WHEEL=1

print_usage() {
    cat <<'EOF'
Usage: install_host_hailo_bindings.sh [options]

Options:
  --venv-path <path>             Target virtualenv (default: $THESIS_ROOT/.venv)
    --base-url <url>               Hailo artifacts base URL (default: https://dev-public.hailo.ai/2025_07)
    --hailort-version <ver>        HailoRT wheel version (default: 4.23.0)
    --tappas-core-version <ver>    TAPPAS core wheel version (default: 5.1.0)
  --download-dir <path>          Download directory (default: hailo_temp_resources)
    --hailort-wheel <path-or-url>  Use explicit HailoRT wheel file (local path or URL)
    --tappas-wheel <path-or-url>   Use explicit TAPPAS wheel file (local path or URL)
    --skip-tappas-wheel            Skip TAPPAS Python wheel install
    --skip-system-check            Skip host shared-library checks
  -h, --help                     Show help

Environment overrides:
    VENV_PATH, BASE_URL, HAILORT_VERSION, TAPPAS_CORE_VERSION, HAILO_EXAMPLES_DIR, DOWNLOAD_DIR,
    HAILORT_WHEEL_SRC, TAPPAS_WHEEL_SRC

Recommended pair for Hailo-8 on Ubuntu 24.04:
    HAILORT_VERSION=4.23.0
    TAPPAS_CORE_VERSION=5.1.0
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --venv-path)
            VENV_PATH="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --hailort-version)
            HAILORT_VERSION="$2"
            shift 2
            ;;
        --tappas-core-version)
            TAPPAS_CORE_VERSION="$2"
            shift 2
            ;;
        --download-dir)
            DOWNLOAD_DIR="$2"
            shift 2
            ;;
        --hailort-wheel)
            HAILORT_WHEEL_SRC="$2"
            shift 2
            ;;
        --tappas-wheel)
            TAPPAS_WHEEL_SRC="$2"
            shift 2
            ;;
        --skip-tappas-wheel)
            INSTALL_TAPPAS_WHEEL=0
            shift
            ;;
        --skip-system-check)
            SKIP_SYSTEM_CHECK=1
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

if [[ ! -x "$VENV_PATH/bin/python" ]]; then
    echo "[error] virtualenv python not found at: $VENV_PATH/bin/python"
    echo "[hint] create it first, for example: python3 -m venv $VENV_PATH"
    exit 1
fi

mkdir -p "$DOWNLOAD_DIR"

PY_INFO="$($VENV_PATH/bin/python - <<'PY'
import platform
import sys
arch_map = {
    'x86_64': 'linux_x86_64',
    'aarch64': 'linux_aarch64',
}
major, minor = sys.version_info[:2]
py_tag = f"cp{major}{minor}-cp{major}{minor}"
arch = arch_map.get(platform.machine(), platform.machine())
print(py_tag)
print(arch)
print(f"{major}.{minor}")
PY
)"

PY_TAG="$(echo "$PY_INFO" | sed -n '1p')"
ARCH_TAG="$(echo "$PY_INFO" | sed -n '2p')"
PY_VERSION="$(echo "$PY_INFO" | sed -n '3p')"

HAILORT_WHEEL="hailort-${HAILORT_VERSION}-${PY_TAG}-${ARCH_TAG}.whl"
HAILORT_URL="${BASE_URL}/${HAILORT_WHEEL}"
TAPPAS_CANDIDATES=(
    "hailo_tappas_core_python_binding-${TAPPAS_CORE_VERSION}-${PY_TAG}-${ARCH_TAG}.whl"
    "hailo_tappas_core_python_binding-${TAPPAS_CORE_VERSION}-py3-none-any.whl"
    "tappas_core_python_binding-${TAPPAS_CORE_VERSION}-${PY_TAG}-${ARCH_TAG}.whl"
    "tappas_core_python_binding-${TAPPAS_CORE_VERSION}-py3-none-any.whl"
)
HAILORT_LOCAL_PATH="$DOWNLOAD_DIR/$HAILORT_WHEEL"
TAPPAS_LOCAL_PATH=""

has_library() {
    local lib_name="$1"
    if ldconfig -p 2>/dev/null | grep -q "$lib_name"; then
        return 0
    fi
    return 1
}

echo "[info] target venv: $VENV_PATH"
echo "[info] python: $PY_VERSION"
echo "[info] wheel tag: $PY_TAG ($ARCH_TAG)"
echo "[info] default hailort url: $HAILORT_URL"
if [[ "$SKIP_SYSTEM_CHECK" -eq 0 ]]; then
    if has_library "libhailort.so"; then
        echo "[ok] host library detected: libhailort.so"
    else
        echo "[warn] host library missing: libhailort.so"
    fi

    if has_library "libgsthailometa.so"; then
        echo "[ok] host library detected: libgsthailometa.so"
    else
        echo "[warn] host library missing: libgsthailometa.so"
        echo "[hint] install matching deb packages (hailort + hailo-tappas-core) before running single-process mode"
        echo "[hint] no-root fallback: ./tools/setup/setup_local_tappas_runtime.sh"
    fi
fi

fetch_artifact() {
    local src="$1"
    local dst="$2"

    if [[ -z "${src:-}" ]]; then
        echo "[error] empty artifact source"
        return 1
    fi

    if [[ -f "$src" ]]; then
        cp -f "$src" "$dst"
        return 0
    fi

    if [[ "$src" =~ ^https?:// ]]; then
        wget -q "$src" -O "$dst"
        return 0
    fi

    echo "[error] artifact source is neither an existing file nor URL: $src"
    return 1
}

echo "[step] resolving wheel sources"
if [[ -n "${HAILORT_WHEEL_SRC:-}" ]]; then
    HAILORT_WHEEL="$(basename "$HAILORT_WHEEL_SRC")"
    HAILORT_LOCAL_PATH="$DOWNLOAD_DIR/$HAILORT_WHEEL"
    echo "[info] using explicit hailort wheel source: $HAILORT_WHEEL_SRC"
    fetch_artifact "$HAILORT_WHEEL_SRC" "$HAILORT_LOCAL_PATH"
else
    if ! wget --spider -q "$HAILORT_URL"; then
        echo "[error] no matching HailoRT wheel found for this Python ABI"
        echo "[error] missing URL: $HAILORT_URL"
        echo "[hint] this usually means upstream does not publish this Python tag yet"
        echo "[hint] pass --hailort-wheel <path-or-url> if you received a wheel directly"
        exit 2
    fi
    wget -q "$HAILORT_URL" -O "$HAILORT_LOCAL_PATH"
fi

if [[ "$INSTALL_TAPPAS_WHEEL" -eq 1 ]]; then
    if [[ -n "${TAPPAS_WHEEL_SRC:-}" ]]; then
        TAPPAS_WHEEL="$(basename "$TAPPAS_WHEEL_SRC")"
        TAPPAS_LOCAL_PATH="$DOWNLOAD_DIR/$TAPPAS_WHEEL"
        echo "[info] using explicit tappas wheel source: $TAPPAS_WHEEL_SRC"
        fetch_artifact "$TAPPAS_WHEEL_SRC" "$TAPPAS_LOCAL_PATH"
    else
        found_tappas=0
        for tappas_wheel in "${TAPPAS_CANDIDATES[@]}"; do
            tappas_url="${BASE_URL}/${tappas_wheel}"
            if wget --spider -q "$tappas_url"; then
                TAPPAS_LOCAL_PATH="$DOWNLOAD_DIR/$tappas_wheel"
                echo "[info] selected tappas wheel url: $tappas_url"
                wget -q "$tappas_url" -O "$TAPPAS_LOCAL_PATH"
                found_tappas=1
                break
            fi
        done

        if [[ "$found_tappas" -ne 1 ]]; then
            echo "[error] no default TAPPAS wheel URL matched known naming conventions"
            echo "[hint] pass --tappas-wheel <path-or-url> if you received a wheel directly"
            echo "[hint] or re-run with --skip-tappas-wheel if you only need hailo import"
            echo "[hint] attempted candidates:"
            for tappas_wheel in "${TAPPAS_CANDIDATES[@]}"; do
                echo "       ${BASE_URL}/${tappas_wheel}"
            done
            exit 3
        fi
    fi
else
    echo "[info] skipping TAPPAS Python wheel install by request"
fi

echo "[step] installing wheels into $VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/python" -m pip install "$HAILORT_LOCAL_PATH"
if [[ "$INSTALL_TAPPAS_WHEEL" -eq 1 ]]; then
    "$VENV_PATH/bin/python" -m pip install "$TAPPAS_LOCAL_PATH"
fi

echo "[step] verifying import"
"$VENV_PATH/bin/python" - <<'PY'
import importlib
import hailo

print("hailo import ok", hailo.__file__)

try:
    hp = importlib.import_module("hailo_platform")
    print("hailo_platform import ok", hp.__file__)
except Exception as exc:
    print("hailo_platform import warning", exc)
PY

echo "[done] host Hailo bindings installed"
