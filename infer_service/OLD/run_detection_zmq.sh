#!/usr/bin/env bash
set -euo pipefail
VENV=/root/hailo-rpi5-examples/venv_hailo_rpi_examples

export PYTHONPATH="/root/hailo-rpi5-examples:${PYTHONPATH:-}"
exec "$VENV/bin/python" /root/thesis_service/detection_zmq.py
