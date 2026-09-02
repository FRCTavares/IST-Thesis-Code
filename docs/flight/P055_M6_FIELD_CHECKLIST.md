# Issue #55 — M6 Final Field Checklist

Use this only for the final approved-network validation.

## Before starting

Use either:
- a local Pi terminal; or
- direct LAN SSH from the Mac to the Pi's `wlan0` IPv4 address while both are
  connected to the approved ISR/AERONEXT Wi-Fi, but only if the current Pi
  firewall permits direct SSH on that WLAN.

Do not use a Tailscale `100.x.x.x` address or depend on Tailscale for the SSH
session. If direct WLAN SSH is blocked by the current firewall, use a local Pi
terminal instead; do not weaken the field firewall just to complete M6.

Keep:
- Pixhawk Ethernet connected on `pixhawk-apm`;
- no default route on Pixhawk Ethernet;
- Mac and iPhone available on the approved Wi-Fi.

Preferred Wi-Fi:
1. `ISR Aero.Next GCS`
2. approved AERONEXT local/GCS network only if ISR is unavailable

## 1. Join the approved Wi-Fi

Check:

    nmcli -t -f NAME,DEVICE connection show --active
    ip -4 addr show wlan0
    ip route

PASS:
- wlan0 is on `ISR Aero.Next GCS` or approved AERONEXT fallback;
- wlan0 has an IPv4 address;
- Pixhawk Ethernet remains present;
- Pixhawk Ethernet has no default route.

## 2. Verify SSH path, then disable Tailscale

If using SSH from the Mac, first check:

    echo "$SSH_CONNECTION"

PASS before disabling Tailscale, if using SSH:
- a fresh Mac -> Pi SSH connection over the Pi's `wlan0` IPv4 address succeeds;
- the Pi/server address in `SSH_CONNECTION` is that `wlan0` IPv4 address;
- the session is not using a Tailscale `100.x.x.x` address.

If that fresh direct-WLAN SSH connection does not work, switch to a local Pi
terminal before disabling Tailscale.

Then disable Tailscale:

    sudo systemctl disable --now tailscaled

Check:

    systemctl is-active tailscaled
    ip link show tailscale0 2>/dev/null || true

PASS:
- `tailscaled` is inactive;
- no active `tailscale0` interface is being used;
- if using direct WLAN SSH, the Mac-to-Pi SSH session still works after
  Tailscale is stopped.

## 3. Start the field UI

    cd ~/Desktop/Thesis-Code || exit 1
    tools/start_field_ui.sh --no-control

Do NOT use either bench override.

PASS when the terminal prints:

    FIELD UI READY

Note the printed iPhone URL:

    http://<PI_WLAN_IP>:5173

## 4. Test from iPhone

Connect the iPhone to the SAME approved GCS Wi-Fi.

Open the printed URL in Safari.

Confirm:
- camera video is live;
- numbered cyan `#ID` person overlay is visible;
- health shows NOMINAL or otherwise truthful status.

Then:

1. press SELECT on a visible person;
2. confirm `TIM TARGET #N`;
3. confirm `TIM CONFIRMED`;
4. confirm TIM state `LOCKED`;
5. confirm REF matches the selected/current TIM track;
6. press CLEAR TARGET;
7. confirm `NO_TARGET`;
8. confirm the green TIM target box disappears;
9. confirm the normal cyan `#ID` remains.

PASS:
- SELECT -> LOCKED works;
- CLEAR -> NO_TARGET works;
- no stale target overlay remains.

## 5. Stop

Press Ctrl-C once in the Pi terminal.

Wait for:

    [field-ui] stopped

Then check:

    ss -lntp | rg ':5173|:8080|:8090|:8765' || true
    pgrep -af 'start_field_ui|http.server 5173|dashboard_bridge|target_memory_mars|web_video_server' || true

PASS:
- ports 5173, 8080, 8090, 8765 are free;
- no field-UI/live-stack processes remain.

## 6. Evidence to remember

For M6 closure, record:

- exact SSID used;
- Pi wlan0 IPv4 address;
- confirmation that Tailscale was inactive;
- if SSH was used, confirmation that it was direct Mac -> Pi WLAN SSH and
  remained usable with Tailscale stopped;
- iPhone opened the Pi WLAN URL directly;
- SELECT -> LOCKED -> CLEAR -> NO_TARGET passed;
- shutdown cleanup passed.

Do not run another A/B/C performance test.

If all sections pass, M6 field validation is PASS.
