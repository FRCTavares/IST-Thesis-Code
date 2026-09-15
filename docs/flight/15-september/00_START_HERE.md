# 15 September 2026 — START HERE

Open this file first at the field.

## Today

Five manual / non-closed-loop captures:

1. `01_FHD_DRONE_POV.md`
2. `02_H01_EXIT_REENTRY.md`
3. `03_H02_CROSSING.md`
4. `04_H03_OCCLUSION.md`
5. `05_DYNAMIC_UAV_TIM_MARS.md`

The thesis controller is NOT authorised to fly the aircraft today.

The qualified pilot retains all aircraft-motion authority.

## One-time setup

Run:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    set +u

    git status --short

The output must be empty.

Verify the Stage-7 freeze:

    python3 tools/analysis/validate_tim_evaluation_split.py \
        docs/data/splits/tim_mars_split_v4.json \
        --verify-hashes

Before H01/H02/H03, the release state must still be:

    final_ready=0/3

Check storage and hardware:

    df -h /
    ls -l /dev/video0 /dev/media0 /dev/hailo0
    hailortcli scan

At least 40 GiB free is required before the held-out captures.

Check that no stale thesis recording process is running:

    pgrep -af '[s]tart_live_stack|[p]erception_camera_node|[r]os2 bag record|[m]avros_node|[c]ontrol_ref_node' || true

There must be no stale previous stack or recorder.

## Pilot preflight

Before any aircraft leaves the ground, the qualified pilot completes the
normal aircraft, RC, battery, area and regulatory safety checks.

Pilot judgement overrides every experimental choreography instruction.

## Execution order

Start with:

    less docs/flight/15-september/01_FHD_DRONE_POV.md

Then follow the numbered files in order.

## Held-out rule

H01/H02/H03 are prospective held-out captures.

Between H01, H02 and H03:

- bag integrity checks are allowed;
- physical-scene confirmation is allowed;
- source-image usability checks are allowed;
- physical-v2 annotation is allowed;
- tracker/TIM-MARS performance inspection is forbidden;
- architecture evaluation is forbidden;
- parameter/model/tracker changes are forbidden.

Do not repeat a held-out sequence because an algorithm performs badly.

## Closed-loop work

Do NOT run autonomous / closed-loop controller flights today from this queue.

Those are indexed in:

    docs/flight/future-flights/README.md
