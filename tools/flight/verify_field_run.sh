#!/usr/bin/env bash
set +u

RUN_ID="${1:-}"
TAG="${2:-}"
MODE="${3:-}"

if [[ -z "$RUN_ID" || -z "$TAG" ]]; then
    echo "Usage: $0 RUN_ID TAG [--control-trial]"
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

if [[ "$MODE" == "--control-trial" ]]; then
    ARGS+=(--control-trial)
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
