# Issue #55 — M6 Field Checklist

## Validation status

**M6 PASS — 2 September 2026.**

The final M6 evidence combines the previously completed real-iPhone UI
validation with the real Pixhawk-gated field-network validation retained in
`docs/results/live/p055_field_network_validation.md`.

This file remains the compact operator checklist for the validated field
network/UI path.

## Required invariant

`NO PIXHAWK -> NO AERONEXT GCS`

Field Wi-Fi is never a passive maintenance preference.

Approved order:

1. `ISR Aero.Next GCS`;
2. one explicitly configured approved AERONEXT fallback only if the primary
   cannot be activated.

Do not configure `ISR Aero.Next GCS-5G` merely because it is visible.

## 1. Start in unattended maintenance mode

Use a local Pi terminal for the field transition.

Check:

    sudo /usr/local/sbin/thesis-network-mode status
    nmcli -g GENERAL.CONNECTION device show wlan0
    systemctl is-active tailscaled
    nmcli -g connection.autoconnect connection show "ISR Aero.Next GCS"

PASS:

- mode is `unattended`;
- ordinary maintenance Wi-Fi is active;
- Tailscale may be active for maintenance;
- `ISR Aero.Next GCS` has `connection.autoconnect=no`.

Do not manually connect the GCS profile while the Pixhawk is absent.

## 2. Connect and verify the Pixhawk

Physically connect and power the Pixhawk Ethernet link.

Check:

    cat /sys/class/net/eth0/carrier
    nmcli -g GENERAL.CONNECTION device show eth0

PASS before field entry:

- physical carrier is `1`;
- field mode has not been entered automatically;
- `pixhawk-apm` need not yet be active while still unattended.

Carrier appearance is only a prerequisite. It is never an automatic field-mode
trigger.

## 3. Enter field mode explicitly

From the local Pi terminal:

    sudo /usr/local/sbin/thesis-network-mode pixhawk

Then check:

    sudo /usr/local/sbin/thesis-network-mode status
    nmcli -g GENERAL.CONNECTION device show wlan0
    nmcli -g GENERAL.CONNECTION device show eth0
    cat /sys/class/net/eth0/carrier
    systemctl is-active tailscaled
    ip route show default
    ip route show default dev eth0
    nmcli -g connection.autoconnect connection show "ISR Aero.Next GCS"

PASS:

- mode is `pixhawk`;
- Wi-Fi is `ISR Aero.Next GCS`, or the explicitly approved fallback if the
  primary genuinely cannot be activated;
- `pixhawk-apm` is active on the Pixhawk Ethernet interface;
- carrier is `1`;
- Pixhawk Ethernet owns no default route;
- the default route is through approved field Wi-Fi;
- Tailscale is inactive;
- field/GCS autoconnect remains `no`.

If any field-network contract fails, do not launch the UI.

## 4. Start the field UI

    cd ~/Desktop/Thesis-Code || exit 1
    tools/start_field_ui.sh --no-control

Do not use a bench override.

PASS when the terminal prints:

    FIELD UI READY

Open the printed `http://<PI_WLAN_IP>:5173` address from the iPhone connected to
the same approved GCS Wi-Fi.

## 5. Verify the operator surface

Confirm:

- camera video is live;
- numbered cyan `#ID` tracker overlays are aligned;
- SELECT on the intended person produces the matching TIM target;
- TIM reaches `LOCKED`;
- CLEAR TARGET returns to `NO_TARGET`;
- the authoritative target overlay disappears;
- the ordinary numbered tracker overlay remains;
- no stale target box remains.

The real-iPhone version of this sequence passed during M6.

## 6. Normal shutdown

Press Ctrl-C once in the field-UI terminal and wait for:

    [field-ui] stopped

Check:

    ss -lntp | rg ':5173|:8080|:8090|:8765' || true
    pgrep -af 'start_field_ui|http.server 5173|dashboard_bridge|target_memory_mars|web_video_server' || true

Then return the host to maintenance networking:

    sudo /usr/local/sbin/thesis-network-mode unattended

PASS:

- field-UI ports are free;
- no field-UI/live-stack processes remain;
- approved field Wi-Fi is inactive;
- mode is `unattended`;
- Tailscale is restored;
- ordinary maintenance Wi-Fi may reconnect according to its own autoconnect
  policy;
- field/GCS `connection.autoconnect` remains `no`.

## 7. Pixhawk disconnect while in field mode

If physical Pixhawk Ethernet carrier disappears during field mode, do not try
to preserve the GCS connection.

The validated host behavior is:

1. NetworkManager dispatcher detects Ethernet loss;
2. host exits to `unattended`;
3. approved field Wi-Fi is disconnected;
4. `pixhawk-apm` is relinquished;
5. Tailscale is restored;
6. ordinary maintenance Wi-Fi may recover;
7. carrier restoration alone does not re-enter field mode.

The final real physical-unplug test measured `8318 ms` from observed carrier
loss to the retained unattended-state observation and required no emergency
rollback.

## 8. Retained M6 evidence

Authoritative summary:

    docs/results/live/p055_field_network_validation.md

Raw logs:

    reports/p055_field_network_2026_09_02/

Do not repeat the A/B/C UI performance characterization for Issue #55.

M7 may begin only after the M6 closure commit is retained.
