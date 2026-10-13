#!/usr/bin/env bash
# Thesis-Code
# Purpose: Verify the retained bag, visual recording and evidence package for
# a named field run.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

set +u

RUN_ID="${1:-}"
TAG="${2:-}"
MODE="${3:-}"
SCOPE="${4:-}"

if [[ -z "$RUN_ID" || -z "$TAG" ]]; then
    echo "Usage: $0 RUN_ID TAG [--control-trial|--ground-qualification] [--disarmed-runtime-characterization|--ground-qualification]"
    exit 2
fi

printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"

if [[ ! -d "$BAG" ]]; then
    echo "FAIL: exact bag missing: $BAG"
    exit 1
fi

RC=0

ARGS=(
    --bag-dir "$BAG"
    --run-id "$RUN_ID"
    --field-record
    --expect-visual
    --expect-operator-events
)

GROUND_QUALIFICATION=0

if [[ "$MODE" == "--control-trial" ]]; then
    ARGS+=(--control-trial)
elif [[ "$MODE" == "--ground-qualification" ]]; then
    GROUND_QUALIFICATION=1
elif [[ -n "$MODE" ]]; then
    echo "FAIL: unsupported verification mode: $MODE"
    exit 2
fi

if [[ "$SCOPE" == "--disarmed-runtime-characterization" ]]; then
    if [[ "$MODE" != "--control-trial" ]]; then
        echo "FAIL: disarmed runtime characterization requires --control-trial"
        exit 2
    fi
    ARGS+=(--disarmed-runtime-characterization)
elif [[ "$SCOPE" == "--ground-qualification" ]]; then
    if [[ "$MODE" != "--control-trial" ]]; then
        echo "FAIL: ground qualification in argument 4 requires --control-trial"
        exit 2
    fi
    GROUND_QUALIFICATION=1
elif [[ -n "$SCOPE" ]]; then
    echo "FAIL: unsupported verification scope: $SCOPE"
    exit 2
fi

if [[ "$GROUND_QUALIFICATION" -eq 1 ]]; then
    case "$TAG" in
        ground_compute_vga|ground_process_loss_vga)
            ARGS+=(--runtime-only)
            ;;
        *)
            echo "FAIL: --ground-qualification is restricted to ground_compute_vga or ground_process_loss_vga"
            exit 2
            ;;
    esac
fi

case "$TAG" in
    bcb_baseline_a|bcb_candidate|bcb_baseline_b)
        if [[ "$MODE" != "--control-trial" ]]; then
            echo "FAIL: final B-C-B tag requires --control-trial"
            exit 2
        fi
        ARGS+=(--expect-bcb-opportunities "$TAG")
        ;;
esac

python3 tools/live/verify_evidence_package.py "${ARGS[@]}" || RC=1
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG" || RC=1
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json" || RC=1

if [[ "$MODE" == "--control-trial" ]]; then
    python3 tools/analysis/summarize_control_diagnostics.py \
        "$BAG" \
        --out "$BAG/control_diagnostics_summary.json" || RC=1
fi

echo "BAG=$BAG"

if [[ "$RC" -eq 0 ]]; then
    echo "PASS: retained run checks"
else
    echo "FAIL: retained run checks; KEEP THE RUN"
fi

exit "$RC"
