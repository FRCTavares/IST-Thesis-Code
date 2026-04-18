#!/usr/bin/env bash
set -euo pipefail
HAILO_EXAMPLES_DIR="${HAILO_EXAMPLES_DIR:-/root/thesis_deprecated/hailo-rpi5-examples}"
if [[ ! -d "$HAILO_EXAMPLES_DIR" && -d /root/hailo-rpi5-examples ]]; then
	HAILO_EXAMPLES_DIR=/root/hailo-rpi5-examples
fi
VENV="$HAILO_EXAMPLES_DIR/venv_hailo_rpi_examples"

export PYTHONPATH="$HAILO_EXAMPLES_DIR:${PYTHONPATH:-}"
DETECTION_ENTRY=/root/thesis_deprecated/infer_service/detection_zmq.py
if [[ ! -f "$DETECTION_ENTRY" ]]; then
	echo "[error] missing detection entrypoint: $DETECTION_ENTRY" >&2
	exit 1
fi

exec "$VENV/bin/python" "$DETECTION_ENTRY"
