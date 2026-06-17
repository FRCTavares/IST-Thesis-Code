#!/usr/bin/env bash
set -euo pipefail

THESIS_ROOT="${THESIS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$THESIS_ROOT"

cmd="${1:-start}"

case "$cmd" in
  start)
    shift || true
    exec ./tools/start_live_stack.sh "$@"
    ;;

  record)
    shift || true
    tag="${1:-live}"
    shift || true
    exec ./tools/start_live_stack.sh --record --tag "$tag" "$@"
    ;;

  ui)
    shift || true
    exec ./tools/start_ui_stack.sh "$@"
    ;;

  help|-h|--help)
    cat <<'EOF'
Usage:
  ./tools/thesis_live.sh
  ./tools/thesis_live.sh start [live options]
  ./tools/thesis_live.sh record TAG [live options]
  ./tools/thesis_live.sh ui

Examples:
  ./tools/thesis_live.sh
  ./tools/thesis_live.sh record outdoor_01
  ./tools/thesis_live.sh record demo1 --dash 10
  ./tools/thesis_live.sh start --tracker sort --mem off
  ./tools/thesis_live.sh ui

Advanced live options:
  ./tools/start_live_stack.sh --help-advanced
EOF
    ;;

  *)
    echo "[error] unknown thesis_live command: $cmd"
    echo "Run: ./tools/thesis_live.sh help"
    exit 2
    ;;
esac
