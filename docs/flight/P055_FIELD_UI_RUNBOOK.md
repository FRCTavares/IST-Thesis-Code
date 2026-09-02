# Issue #55 — iPhone Field UI Runbook

## Status

**FIELD UI WORKFLOW AND PIXHAWK-GATED FIELD NETWORK VALIDATED; ISSUE #55 M6 PASS.**

M7 old-frontend removal is now unblocked but is not part of this runbook validation.

This document owns the operator-facing browser/UI workflow for the Raspberry Pi
field system.

It does **not** replace the aircraft-control procedure owned by Issue #50.
Before retained aircraft operation, the exact controller/MAVROS launch command,
abort procedure, retained topics, and Pixhawk checks must be frozen in
[P050_FLIGHT_VALIDATION.md](P050_FLIGHT_VALIDATION.md).

The current #55 UI path has been validated with:

- Raspberry Pi 5;
- YOLOv8s direct/in-process Hailo inference;
- ByteTrack;
- TIM-MARS;
- iPhone Safari;
- direct local Wi-Fi access;
- no cloud or internet dependency;
- frontend/API/WebSocket/MJPEG bound to the Pi's active `wlan0` IPv4 address.

The browser is an operator interface only. TIM-MARS remains the physical-person
identity authority.

## 1. What the operator should see

The final field UI is intentionally small and phone-first.

Required information:

- live camera image;
- numbered tracker IDs;
- numeric target bootstrap selection;
- explicit SELECT action;
- explicit CLEAR TARGET action;
- TIM state;
- current TIM-associated tracker ID;
- backend/connection health;
- compact latency/cadence/temperature health.

Target selection semantics:

1. selecting tracker ID `#N` identifies the physical person currently
   represented by that tracker ID;
2. TIM-MARS then owns identity continuity;
3. the underlying tracker ID may change later;
4. the browser must display TIM's current association rather than treating the
   original tracker ID as permanent identity.

TIM state interpretation:

- `LOCKED`: TIM currently accepts the selected physical person;
- `REACQUIRED`: TIM has reacquired the same selected person;
- `UNCERTAIN`: identity evidence is insufficient for normal acceptance;
- `LOST`: TIM is suppressing the target rather than asserting an unsafe match;
- `NO_TARGET`: no target is selected.

Safety ordering remains:

correct selected person > LOST / hover / suppression > wrong person.

## 2. Network contract

Field operation is explicit and Pixhawk-gated.

The required invariant is:

`NO PIXHAWK -> NO AERONEXT GCS`

Approved field Wi-Fi priority:

1. `ISR Aero.Next GCS`;
2. one explicitly configured approved AERONEXT local-router/network fallback
   only if the primary cannot be activated.

The field router does not need internet access.

The host normally remains in `unattended` maintenance mode. Field/GCS profiles
are persisted with `connection.autoconnect=no` and must not be selected as
ordinary maintenance networks.

Physical Pixhawk Ethernet carrier is a prerequisite for field entry, but carrier
appearance never triggers field mode automatically.

Enter field networking only through:

    sudo /usr/local/sbin/thesis-network-mode pixhawk

A valid field state requires:

- approved field Wi-Fi active on `wlan0`;
- `pixhawk-apm` active on the dedicated Ethernet interface;
- physical Pixhawk carrier present;
- no default route through Pixhawk Ethernet;
- Tailscale disabled/inactive;
- field/GCS `connection.autoconnect=no`;
- no router port forwarding or public dashboard/API exposure.

Only after those gates pass should `tools/start_field_ui.sh --no-control` be
started.

If the Pixhawk Ethernet contract disappears while already in field mode, the
NetworkManager dispatcher fails closed to `unattended`: field Wi-Fi is dropped,
Pixhawk Ethernet is relinquished, and Tailscale is restored. The periodic
host-health monitor independently enforces the same contract as a slower
backstop.

Neither the dispatcher nor the health monitor automatically re-enters field
mode. A new explicit `pixhawk` command is required after carrier returns.

The final real physical-disconnect validation is retained in
`docs/results/live/p055_field_network_validation.md`.
## 3. One-time Pi firewall preparation

This normally needs to be done only once per Pi installation:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    tools/setup/setup_field_ui_firewall.sh

The helper allows these TCP services only on `wlan0`:

- `5173` — browser frontend;
- `8080` — MJPEG video;
- `8090` — dashboard HTTP API;
- `8765` — dashboard WebSocket.

It does not open LAN SSH.

Current UFW policy also contains the independently owned Pixhawk and unattended
host rules. Do not remove or broaden them from this runbook.

## 4. Before field use

Use a local Pi terminal for the field-network transition.

From the Pi:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat

Check repository state:

    git status --short

Confirm the maintenance state:

    sudo /usr/local/sbin/thesis-network-mode status
    nmcli -g GENERAL.CONNECTION device show wlan0
    systemctl is-active tailscaled
    nmcli -g connection.autoconnect connection show "ISR Aero.Next GCS"

Physically connect and power the Pixhawk, then verify:

    cat /sys/class/net/eth0/carrier

Carrier must be `1`.

Enter field networking explicitly:

    sudo /usr/local/sbin/thesis-network-mode pixhawk

Verify:

    sudo /usr/local/sbin/thesis-network-mode status
    nmcli -g GENERAL.CONNECTION device show wlan0
    nmcli -g GENERAL.CONNECTION device show eth0
    systemctl is-active tailscaled
    ip route show default
    ip route show default dev eth0

Required before launching the field UI:

- host mode `pixhawk`;
- ISR preferred whenever available;
- approved AERONEXT fallback only when explicitly configured and the primary
  cannot be activated;
- physical Pixhawk carrier present;
- `pixhawk-apm` active;
- no Pixhawk Ethernet default route;
- Tailscale inactive;
- field/GCS autoconnect still disabled.

Do not manually preserve the GCS connection if the Pixhawk link disappears.
The host is required to fail closed to unattended networking.

For actual aircraft work, also perform the Issue #50 control/MAVROS/abort
checks in `P050_FLIGHT_VALIDATION.md`.
## 5. Current validated UI-only launch command

The currently validated ground/UI command is:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    tools/start_field_ui.sh --no-control

This starts:

- camera + direct Hailo YOLOv8s perception;
- ByteTrack;
- TIM-MARS;
- dashboard bridge;
- MJPEG video server;
- browser frontend.

It deliberately does not start controller output.

**Do not substitute this UI-only command for the future Issue #50 retained
aircraft command.**

When #50 freezes the exact controller/MAVROS configuration, this runbook must
be updated so the operator has one authoritative aircraft-day command.

## 6. Expected launcher output

A successful launch prints:

    FIELD UI READY

    Network: <approved SSID>
    Pi:      <wlan0 IPv4>

    Open on iPhone:
      http://<wlan0 IPv4>:5173

    No internet connection is required.

Use the numeric IPv4 address printed by the launcher.

Do not depend on `fcstpi.local`, public DNS, Tailscale, a laptop proxy, or an
internet connection.

## 7. Open the UI on the iPhone

1. Connect the iPhone to the same approved Wi-Fi as the Pi.
2. Stay connected even if iOS reports that the Wi-Fi has no internet.
3. Open Safari.
4. Enter the exact URL printed by the Pi launcher.
5. Keep Safari foregrounded during active monitoring.

Example bench URL from the 1 September 2026 validation:

    http://192.168.1.110:5173

That address is an example only. Always use the address printed for the current
field network.

For prolonged test measurements, temporarily prevent iPhone Auto-Lock so Safari
does not suspend the WebSocket/MJPEG session.

## 8. Target selection

Before selecting:

- verify the correct physical person is clearly visible;
- identify the tracker number shown over that person;
- do not infer identity from detector confidence alone.

Then:

1. select the corresponding tracker ID;
2. press SELECT;
3. confirm the UI reports the command result;
4. confirm TIM transitions to the expected state;
5. verify the TIM-associated target corresponds to the intended physical
   person.

Tracker ID selection is only the bootstrap operation.

If tracker ID `#3` represents the intended person at selection time and TIM
later associates that same physical person with tracker ID `#12`, the UI should
show the new TIM association.

## 9. During operation

The operator should prioritize these signals:

1. camera / numbered tracker alignment;
2. TIM state;
3. TIM-associated current tracker ID;
4. target command result;
5. system health strip.

Normal expected field values are approximately:

- detector/tracker/TIM cadence around 15 Hz on the current YOLOv8s path;
- detector p95 latency well below the 120 ms timing-contract threshold;
- controller-facing validated-target latency well below the freshness limit;
- temperature comfortably below thermal warning limits.

Do not treat a green detector bounding box by itself as proof of target
identity.

TIM state is authoritative for target identity.

## 10. If TIM becomes UNCERTAIN or LOST

Do not manually reinterpret a detector/tracker box as the target.

TIM-MARS is designed to prefer suppression over wrong-person output.

If TIM reports `UNCERTAIN` or `LOST`:

- expect target publication/control behavior to follow the state-aware safety
  policy;
- do not assume the original tracker ID remains trustworthy;
- visually confirm the physical scene;
- use CLEAR TARGET if the operator intends to cancel target authority;
- reselect only according to the approved field procedure.

Issue #89 separately tracks the known wide-crop same-ID reacquisition defect.
Do not change its algorithmic thresholds during Issue #55 field-UI validation.

## 11. Stop the complete UI session

Use `Ctrl-C` in the terminal running `tools/start_field_ui.sh`.

The launcher owns cleanup of:

- the live-stack process;
- browser frontend;
- FIFO/control resources.

After shutdown, the field UI ports should be free:

    ss -lntp | rg ':5173|:8080|:8090|:8765' || true

Do not manually kill unrelated processes on the operator laptop.

## 12. Troubleshooting

### UI does not open on iPhone

Check that the Pi and iPhone are on the same Wi-Fi.

On the Pi:

    nmcli -t -f ACTIVE,SSID dev wifi
    ip -brief address show wlan0
    sudo ufw status numbered

Verify listeners:

    ss -lntp | rg ':5173|:8080|:8090|:8765'

Verify the UI/API locally:

    curl -fsS http://<PI_IP>:5173/ >/dev/null
    curl -fsS http://<PI_IP>:8090/api/models >/dev/null

Do not solve a field-access failure by opening SSH to the WLAN or exposing
services publicly.

### Safari disconnects after a short period

The 1 September bench validation showed that iOS/Safari may suspend all active
dashboard connections when the page/display is suspended.

The Pi services remained healthy.

Reopen Safari and keep it foregrounded. For controlled measurements, disable
Auto-Lock temporarily.

### Tailscale is active

Normal field launch must stop.

Do not bypass this check during aircraft operation.

Bench-only override variables exist for development and remote maintenance, but
they are not approved field-flight procedure.

## 13. Offline guarantee

The normal runtime path must not require:

- npm downloads;
- CDN resources;
- cloud APIs;
- public DNS;
- Tailscale;
- internet routing.

The Pi and iPhone only need local connectivity on the approved Wi-Fi.

Required frontend dependencies must already be installed before departure.

## 14. 1 September 2026 real-iPhone and performance evidence

Direct iPhone Safari access passed using the Pi's local WLAN address with no
laptop proxy or internet dependency.

The performance characterization used three active-TIM states:

- **State A** — canonical perception/tracker/TIM plus dashboard bridge, with
  browser frontend and MJPEG/web-video serving disabled;
- **State B** — normal UI services available, but with zero phone clients;
- **State C** — normal UI services with one continuously connected iPhone
  consuming WebSocket telemetry and MJPEG video.

All three measurements used the canonical YOLOv8s + ByteTrack + TIM-MARS path.
The retained State-A target crop was appearance-eligible
(`encoding_eligible=true`, `memory_update_eligible=true`) and TIM remained
`LOCKED` and visible before and after the 60-second timing window.

| metric | State A | State B | State C |
| --- | ---: | ---: | ---: |
| detector cadence | 14.704 Hz | 14.930 Hz | 14.282 Hz |
| tracker cadence | 14.887 Hz | 15.147 Hz | 14.532 Hz |
| TIM target cadence | 15.303 Hz | 15.264 Hz | 15.015 Hz |
| detector e2e p95 | 23.443 ms | 23.887 ms | 28.026 ms |
| tracker p95 | 4.911 ms | 4.674 ms | 5.294 ms |
| TIM processing p95 | 49.264 ms | 51.269 ms | 54.811 ms |
| validated-target e2e p95 | 73.574 ms | 75.227 ms | 80.910 ms |
| validated-target e2e p99 | 78.561 ms | 82.938 ms | 93.046 ms |

The infrastructure-only A-to-B change was negligible: validated-target p95
increased by 1.654 ms and TIM processing p95 by 2.005 ms, while target cadence
changed by only -0.040 Hz.

With an actively connected iPhone, B-to-C target cadence changed by -1.63%,
TIM processing p95 increased by 3.541 ms, validated-target p95 increased by
5.682 ms, and validated-target p99 increased by 10.108 ms.

Across the complete A-to-C comparison, TIM target cadence changed from
15.303 to 15.015 Hz (-1.88%), TIM processing p95 increased by 5.547 ms, and
validated-target p95 increased by 7.336 ms.

States B and C had zero detector, tracker, and TIM frame-ID gaps. State A had
zero detector and tracker gaps but one `/timing_target` gap event with an
estimated two missing frame IDs. State A nevertheless retained a 100/100 live
timing health score, remained cadence-consistent, and finished with TIM
`LOCKED`, visible, and using an appearance-eligible crop. This isolated
State-A gap is retained as a measurement caveat rather than hidden.

The active-phone continuity monitor observed WebSocket + MJPEG connectivity for
70/70 one-second samples.

Conclusion:

**the field UI has a measurable but non-material effect on the
controller-facing TIM-MARS pipeline. Keeping the UI services available without
a client produces negligible timing change; active iPhone viewing adds a small
latency cost while TIM output remains approximately 15 Hz and within the live
timing contract.**

Do not claim literal zero computational effect from the UI.

Evidence directories:

- `ros2_ws/log/ui_performance/2026-09-01_active_tim_state_a/`
- `ros2_ws/log/ui_performance/2026-09-01_active_tim_no_phone_b/`
- `ros2_ws/log/ui_performance/2026-09-01_active_tim_phone_c/`

## 15. 1 September 2026 final iPhone visual validation

The final manual browser gate passed on a real iPhone using direct local-WLAN
access to `192.168.1.110`.

Validated behavior:

- every current ByteTrack person candidate is rendered as a readable numbered
  `#ID` camera overlay;
- detector rectangles are suppressed where the same person is already
  represented by a tracker, avoiding duplicate person boxes;
- selecting a numbered tracker ID through the explicit `SELECT` action
  successfully bootstraps TIM-MARS;
- a confirmed selection is rendered as `TIM TARGET #N`, with the operator panel
  simultaneously reporting `TIM CONFIRMED`, `LOCKED`, the matching reference
  track ID, and `CONTROL NORMAL`;
- `CLEAR TARGET` returns TIM-MARS to `NO_TARGET`, clears the authoritative
  reference, and restores the current ordinary numbered ByteTrack candidate;
- an initially observed stale dashed target box after CLEAR was repaired by
  clearing and suppressing remembered target geometry whenever TIM state is
  `NO_TARGET`; live iPhone revalidation passed after the repair;
- portrait and landscape presentations both preserve target-box/video
  alignment through browser resize/orientation changes;
- the field launcher truthfully reported
  `Tailscale: active (bench override)` during the bench session rather than
  falsely reporting an inactive state;
- the browser remained connected directly over the Pi WLAN address without a
  laptop proxy.

The manual visual/identity-authority portion of M6 is therefore PASS.

This bench validation does not satisfy the separate final field-network gate
because it deliberately used both the unapproved-Wi-Fi and active-Tailscale
development overrides.

## 16. Frozen frontend packaging contract

The field frontend is packaged as a prebuilt static Vite artifact but does not
run the Vite development server in normal operation.

The frozen runtime contract is:

- build `IST-Thesis-UI/dist/` before deployment;
- serve that tree with Python's standard-library HTTP server through the
  UI-owned `tools/start_dashboard.sh`;
- bind the server to the approved WLAN address supplied by the field launcher;
- generate `dist/runtime-config.js` at launch for mode/API/WebSocket overrides;
- derive the normal API, WebSocket, and MJPEG hosts from the browser-visible Pi
  hostname, so a WLAN address change does not require rebuilding the frontend;
- require no Node, Vite, esbuild, npm invocation, `node_modules`, package
  download, CDN, DNS, or internet access during normal field runtime;
- retain `tools/start_dashboard.sh --dev` only for explicit frontend
  development.

A local alternate-port smoke test passed with the frontend owned by
`python3 -m http.server` and no Vite/esbuild runtime process.

The packaging contract was then validated end-to-end through the normal field
launcher on a real iPhone:

- port 5173 was owned by `python3 -m http.server`, serving the prebuilt
  `IST-Thesis-UI/dist/` tree;
- no Vite or esbuild process existed in the field runtime;
- `runtime-config.js` was served in backend mode;
- API, WebSocket, and MJPEG services were simultaneously bound to the Pi WLAN
  address;
- the iPhone completed the numbered-track -> SELECT -> TIM LOCKED -> CLEAR ->
  NO_TARGET operator smoke successfully;
- signalling the field launcher executed its cleanup trap, terminated the
  Python frontend and canonical live-stack children, released ports
  5173/8080/8090/8765, and left no process in the field launcher's process
  group.

The frontend-packaging M6 gate is therefore PASS. The retained frontend implementation reference is `e7329e01c70ee7da6d1581f1c20ad325e3fa26dd` (`01-09-26: simplify and freeze field dashboard`).

## 17. Remaining Issue #55 M6 closure gates

For the final offline field session, use the compact operator checklist:
`docs/flight/P055_M6_FIELD_CHECKLIST.md`.

Do not mark this runbook final until all of the following are resolved:

1. the final field network is tested on an approved ISR/AERONEXT network with
   Tailscale genuinely inactive;
2. the final M6 evidence ledger is reconciled with retained commit references.

After those gates pass, update this document and Issue #50 before retained
aircraft use.
