# P0.24 unattended Pi host-recovery validation

Date: 22 July 2026

Issue: [#51](https://github.com/FRCTavares/IST-Thesis-Code/issues/51)

## Status

Implementation and all software-controlled host tests pass. The external
Tailnet and storage-safe physical power-restoration gates also pass. Issue #51
remains open pending the independent power/watchdog mitigation, exact approved
AERONEXT fallback-profile provisioning/validation, and the physical
AERONEXT/Pixhawk mode check.

## Safety boundary

The deployment enables only NetworkManager, Tailscale, the SSH socket, UFW, and
the host-health timer. It does not enable or start ROS, MAVROS, perception,
tracking, TIM, control, arming, recording, or any aircraft-facing service.
Tailscale is required only in unattended mode. Pixhawk mode prefers
`ISR Aero.Next GCS` on `wlan0` and may fall back to one explicitly configured
approved AERONEXT local-router profile when ISR cannot be activated. It reserves
`eth0` for `pixhawk-apm` and keeps Tailscale stopped.

## Audited baseline

- Ubuntu 24.04.4 LTS
- kernel `6.8.0-1060-raspi`
- systemd 255 (`255.4-1ubuntu8.16`)
- Tailscale 1.98.4
- NetworkManager-managed `wlan0`, saved profile set to autoconnect indefinitely
- `tailscaled.service` enabled and active
- `ssh.socket` enabled and active
- Raspberry Pi hardware watchdog available at `/dev/watchdog0`
- ext4 root filesystem: 229 GiB total, 46% used before implementation
- repository bags: 26 GiB; ROS logs: 75 MiB
- no failed systemd units
- no thesis, MAVROS, or control service enabled at boot

Initial gaps:

- hardware watchdog present but not fed by systemd;
- journal used 2.1 GiB with no explicit cap;
- Tailscale/SSH restart delays were 100 ms with small default start limits;
- UFW was inactive while SSH listened on all IPv4/IPv6 interfaces;
- no conservative host-health timer or recorder free-space refusal gate.

The Tailscale node was online, but its key expiry was
`2026-08-23T10:49:07Z`. An unattended interval that crosses that date requires
an admin-console expiry change or renewal before departure.

## Implemented repository contract

- `tools/host/thesis_host_health.py`
  - checks NetworkManager, default route, Tailscale, SSH, and free storage;
  - acts only after consecutive failures and a recovery cooldown;
  - reconnects only the configured NetworkManager interface;
  - restarts Tailscale only when the underlying network is healthy;
  - restarts only `ssh.socket` when SSH is unavailable;
  - emits redacted JSON and never logs credentials or Tailscale peer data.
  - in Pixhawk mode, accepts only the configured field Wi-Fi profiles,
    with `ISR Aero.Next GCS` first priority and an optional approved AERONEXT
    local-router fallback; it requires the active field profile's default route
    through `wlan0` and stops rather than restarts Tailscale.
- `tools/host/set_pi_network_mode.sh`
  - switches explicitly between `unattended` and `pixhawk` modes;
  - tries `ISR Aero.Next GCS` first, then the explicitly configured approved
    AERONEXT local-router fallback if required, and proves one approved field
    Wi-Fi profile is active before persisting field mode or stopping Tailscale;
  - activates `pixhawk-apm` with IPv4/IPv6 default routes disabled;
  - fails before changing mode if either required NetworkManager profile is
    absent or AERONEXT cannot connect.
- `tools/host/install_unattended_host_recovery.sh`
  - validates and backs up system files before installation;
  - installs the host-only systemd, watchdog, journal, and firewall contract;
  - never enables an aircraft-facing service.
- `tools/host/systemd/`
  - two-minute persistent health timer;
  - Tailscale 10-second restart with bounded start limits;
  - SSH 5-second restart with bounded start limits;
  - 30-second hardware-watchdog feed and 10-minute shutdown watchdog;
  - persistent journal capped at 1 GiB and 30 days.
- `tools/lib/live_storage.sh`
  - refuses video or dataset recording below 20 GiB free;
  - does not delete or rotate any bag.
- `docs/debug/UNATTENDED_PI_OPERATION.md`
  - complete pre-departure, remote-operation, recovery, power, failure, and
    rollback runbook.

Installed-system backup:

Latest: `/var/backups/thesis-host-recovery/20260722T174731Z`

## Automated validation

```text
focused host/network tests: 11 passed
complete tools suite in sourced ROS environment: 79 passed
bash syntax: passed
Python byte compilation: passed
systemd-analyze verify: passed
installer dry-run: passed
git diff --check: passed
```

The simulated disk-pressure test reported `disk_ok=false`, and the live recorder
guard returned 1 with `recording refused` below the 20 GiB threshold. No real
disk space was consumed.

## Installed service validation

After installation:

- NetworkManager, `tailscaled.service`, `ssh.socket`, and
  `thesis-host-health.timer` were enabled and active;
- the health service completed with status 0 and all checks healthy;
- Tailscale restart policy: `Restart=always`, `RestartSec=10s`, 10 starts per
  five-minute limit window;
- SSH restart policy: `Restart=on-failure`, `RestartSec=5s`, 10 starts per
  five-minute limit window;
- journald storage fell from 2.1 GiB to approximately 1.0 GiB;
- UFW became active with default-deny inbound, Tailnet service access only on
  `tailscale0`, UDP 41641 allowed on `wlan0` for direct Tailscale transport, and
  Pixhawk MAVLink UDP 14550 allowed only on `eth0`;
- a new key-based SSH connection through the Tailscale address passed after the
  firewall change;
- `tailscale serve status` reported no public serve configuration;
- no thesis or aircraft service appeared in enabled system service units.

## Controlled recovery tests

### Tailscale process termination

- action: killed only the `tailscaled.service` main process with SIGKILL;
- observed: systemd recorded exit at 18:10:36 and scheduled restart at 18:10:47;
- recovery: `NRestarts=1`, backend `Running`, node online, SSH reachable;
- result: PASS.

### SSH listener termination

- action: killed only the `ssh.service` main listener with SIGKILL;
- observed: exit at 18:11:58 and scheduled restart at 18:12:03;
- recovery: `NRestarts=1`, `ssh.socket` and `ssh.service` active, a new key-based
  SSH connection passed;
- result: PASS.

### Normal reboot and watchdog activation

- pre-reboot epoch: `1784740360`;
- first successful Tailscale SSH epoch: `1784740407`;
- remote recovery time: 47 seconds;
- NetworkManager, Tailscale, SSH socket, and health timer all active after boot;
- systemd reported `RuntimeWatchdogUSec=30s` and
  `RebootWatchdogUSec=10min`;
- boot journal confirmed systemd was feeding the Broadcom BCM2835 watchdog with
  a 30-second timeout;
- previous-boot journal remained readable;
- result: PASS.

### Wi-Fi device loss

- safety: a three-minute independent reconnect fallback was scheduled first;
- action: disconnected `wlan0` through NetworkManager;
- test thresholds: one failure and 60-second cooldown, restored afterward to
  three failures and 900 seconds;
- health action: `network_reconnect=0`, followed by `tailscale_restart=0` while
  the overlay network recovered;
- Tailscale SSH reachable again after 28 seconds;
- independent fallback cancelled;
- result: PASS.

### Default internet-route loss

- safety: a three-minute independent route fallback was scheduled first;
- action: removed only the default route through `wlan0`;
- health action: `network_reconnect=0`;
- DHCP default route restored after 42 seconds and Tailscale returned to
  `Running`;
- production thresholds restored and fallback cancelled;
- result: PASS.

### Health-check service failure

- action: replaced only the installed monitor payload with an invalid temporary
  payload under a trap-protected backup;
- injected invocation: failed with status 1 as expected;
- payload restored immediately, failed state reset, next invocation status 0;
- final service result: success;
- result: PASS.

### Pixhawk field-mode policy dry-run

- installed mode before test: `unattended`, home Wi-Fi active, Tailscale active;
- non-mutating invocation: Pixhawk mode, one-failure threshold, dry-run;
- observed: the home Wi-Fi profile was rejected (`expected_wifi_active=false`)
  even though the interface and a default route were present;
- selected recovery actions: recovery toward the configured preferred
  field Wi-Fi profile and `tailscale_stop`; no action was executed in the
  dry-run. The current software now supports ordered ISR-first recovery with
  an explicitly configured approved AERONEXT fallback;
- live-stack field and source paths now invoke the fail-closed mode switch
  instead of activating `pixhawk-apm` directly;
- result: SOFTWARE POLICY PASS; physical link/profile check remains open.

### 31 August 2026 spontaneous data-plane outage and automatic recovery

A genuine home-network data-plane interruption occurred while the Pi remained
configured in `unattended` mode on `netplan-wlan0-Wi-Fi MC`.

- At 19:41 WEST, the host-health check still observed the expected active
  NetworkManager profile, installed default route, active SSH, and running
  Tailscale, but the configured gateway `192.168.1.1` was no longer reachable.
  This was recorded as the first consecutive network failure.
- At 19:43 WEST, the gateway remained unreachable and Tailscale had also become
  offline, while `wlan0` was still nominally configured.
- At 19:45 WEST, the third consecutive network failure triggered exactly one
  bounded `network_reconnect` action.
- NetworkManager deliberately deactivated and reactivated the same
  `netplan-wlan0-Wi-Fi MC` profile. During that transition the Pi temporarily
  lost its LAN/default-route data path.
- At 19:45:48 WEST, DHCP restored `192.168.1.110` and the default route through
  `192.168.1.1`.
- Tailscale rebound to `wlan0`, re-established its control/DERP connectivity,
  and log upload recovered by 19:46:12 WEST.
- The next host-health invocation at 19:47 reported healthy gateway, network,
  SSH, and Tailscale state with all failure counters reset to zero.
- A fresh SSH connection to the Pi's Tailscale address `100.69.42.62` succeeded
  again from the operator Mac at approximately 20:03 WEST.
- The installed host mode remained `unattended`; `tailscaled.service` remained
  enabled/active and no Pixhawk field-mode transition occurred.

Result: PASS. This is retained real-failure evidence that the July data-plane
repair detects a nominally configured but unusable Wi-Fi path and performs one
bounded reconnect that restores both LAN and Tailscale reachability.

This same-home-network Tailscale reconnection does not replace the still-open
requirement for a fresh Tailnet SSH test from a genuinely external network.

### 31 August 2026 external Tailnet SSH and firewall cleanup

The temporary LAN-only SSH exception used during Issue #51 recovery testing was
removed after first proving that the active operator shell was using Tailscale:

- the active shell was
  `100.105.37.101 -> 100.69.42.62:22`, confirming Mac-to-Pi Tailnet transport;
- the exact temporary UFW rule
  `22/tcp on wlan0 ALLOW IN 192.168.1.213`
  (`temporary P051 LAN SSH test`) was uniquely identified and removed;
- UFW remained active with default-deny inbound, Tailnet service access on
  `tailscale0`, Tailscale UDP 41641 on `wlan0`, and Pixhawk MAVLink UDP 14550
  restricted to `eth0`;
- the existing Tailnet SSH session survived the firewall change;
- a fresh second SSH session to `100.69.42.62` succeeded afterward, proving that
  access did not depend on the removed LAN exception.

A genuinely external Tailnet SSH test was then performed with the Raspberry Pi
left on the home network and the operator Mac moved to a separate phone-hotspot
network:

- Mac host: `Franciscos-Mac.local`, Darwin;
- Mac hotspot IPv4: `172.20.10.3`;
- Mac default gateway: `172.20.10.1`;
- the Mac was therefore outside the Pi's `192.168.1.0/24` home LAN;
- a fresh SSH connection from the Mac to the Pi Tailscale address
  `100.69.42.62` succeeded;
- the Pi reported
  `SSH_CONNECTION=100.105.37.101 59081 100.69.42.62 22`;
- the Pi remained on `netplan-wlan0-Wi-Fi MC` with physical address
  `192.168.1.110` and default gateway `192.168.1.1`;
- the Pi's Tailscale peer state showed the external Mac reachable directly via
  `148.69.202.51:20044`.

Result: PASS. Fresh SSH through the Tailnet works while the operator computer is
on a genuinely separate external network, and no direct LAN SSH firewall
exception is required.

### 31 August 2026 storage-safe physical power restoration

A storage-safe complete physical power-removal/restoration test was performed
while the Pi was in `unattended` mode and no thesis live stack, ROS bag
recording, MAVROS process, or aircraft-facing control process was running.

Pre-power evidence was retained under
`ros2_ws/log/p051_power_cycle_20260831_221616/`.

Before shutdown:

- Git commit:
  `fd3e23167b8603cfa457ca055a37e0f297c31e6a`;
- boot ID:
  `7d547b68-11ad-49e1-8e00-266273014d15`;
- root filesystem: `/dev/mmcblk0p2`, ext4, read-write;
- approximately 73 GiB remained free;
- NetworkManager, `tailscaled.service`, `ssh.socket`, and
  `thesis-host-health.timer` were enabled and active;
- host mode was `unattended`;
- the storage-safe shutdown was requested at 22:16:17 WEST after `sync`.

The previous-boot journal confirms an orderly shutdown:

- systemd reached `umount.target`, `shutdown.target`, `final.target`, and
  `poweroff.target`;
- `systemd-poweroff.service` completed successfully;
- at 22:16:21 WEST, `systemd-shutdown` recorded
  `Syncing filesystems and block devices`;
- the journal then stopped normally.

After the Pi had fully shut down, input power was physically removed, left
disconnected for at least 15 seconds, and restored once. No local interaction
was performed after restoration.

Post-restoration evidence:

- new boot ID:
  `98eeee9a-b2a2-45c1-baa8-156a308e4c38`;
- recorded OS boot start: 22:17:35 WEST;
- the repository commit and clean state were preserved;
- host mode remained `unattended`;
- NetworkManager, `tailscaled.service`, `ssh.socket`, and
  `thesis-host-health.timer` automatically returned enabled and active;
- `wlan0` recovered the home profile and default route through
  `192.168.1.1`;
- Tailscale recovered address `100.69.42.62`;
- from the operator Mac on the separate phone-hotspot network, both Tailnet
  reachability and TCP/22 were already available at the first observation at
  22:20:28 WEST;
- a fresh external SSH session passed with
  `SSH_CONNECTION=100.105.37.101 59804 100.69.42.62 22`;
- the root ext4 filesystem was mounted read-write with no detected current-boot
  filesystem or I/O errors;
- no failed systemd units were present.

The exact physical power-restoration timestamp was not instrumented, so an exact
power-on-to-remote-reachability latency is not claimed. Remote access was
confirmed no later than 22:20:28 WEST, which is 173 seconds after the recorded
OS boot start.

The post-restoration watchdog audit also confirmed that systemd is actively
using `/dev/watchdog0`: `RuntimeWatchdogUSec=30s`,
`RebootWatchdogUSec=10min`, and `wdctl` reported the Broadcom BCM2835 watchdog
with a 30-second timeout and active keep-alive. This verifies the configured
watchdog is live, but it does not replace the still-open destructive-watchdog or
independent-power-mitigation acceptance gate.

Result: PASS. The Pi returned from a storage-safe complete physical power cycle
to an externally reachable unattended state without local intervention.

## Diagnostics and cleanliness

- recent previous-boot journal is available;
- journal growth is bounded to 1 GiB/30 days with 10 GiB kept free;
- root free space remained approximately 120 GiB;
- repository-root `log/`, `hailort.log`, and `.pytest_cache` were removed or
  absent after validation;
- no credentials, SSH keys, Wi-Fi secrets, Tailscale keys, or Tailscale state
  were added to the repository.

## Remaining physical/external gates

Do not close Issue #51 until all of these are recorded:

1. [RESOLVED 31 Aug 2026] storage-safe poweroff, complete physical power
   removal, restoration, and automatic Tailscale/SSH recovery passed. The boot
   ID changed, the ext4 root returned read-write without detected I/O errors,
   unattended services restored automatically, and fresh external Tailnet SSH
   succeeded;
2. [RESOLVED 31 Aug 2026] a fresh Tailscale SSH connection passed while the
   operator Mac was on a phone-hotspot network (`172.20.10.3`, gateway
   `172.20.10.1`) and the Pi remained on the home LAN (`192.168.1.110`,
   gateway `192.168.1.1`). The Pi observed the SSH source as the Mac Tailnet
   address `100.105.37.101`;
3. confirmation that a tested smart plug or UPS is available, or a locally
   supervised destructive watchdog-recovery test with the runbook safeguards;
4. [RESOLVED 31 Aug 2026] live Tailscale status reports the node online with
   key expiry `2027-02-21T12:59:51Z`, covering the remaining thesis interval;
5. with the Pixhawk connected to `eth0`, locally confirm `pixhawk-apm` is active,
   the approved field Wi-Fi selected on `wlan0` has the default route, ISR was
   preferred when available, and `tailscaled.service` is disabled/inactive.

## 25 July 2026 data-plane recovery repair validation

A real unattended failure demonstrated that NetworkManager connection state and
an installed default route were insufficient evidence of usable connectivity.
The powered Raspberry Pi became unreachable through LAN and Tailscale while the
old monitor continued to report the network as healthy.

The repaired unattended monitor now:

- records the active default gateway;
- performs one bounded ICMP probe through the configured interface;
- records configuration health separately as `network_config_ok`;
- requires gateway reachability for unattended `network_ok`;
- reconnects `wlan0` after three consecutive network failures;
- restarts NetworkManager after six consecutive failures using an independent
  cooldown;
- restarts Tailscale only when the underlying network is reachable;
- never automatically reboots the host or starts ROS, MAVROS, control,
  perception, arming, or any aircraft-facing process.

Installed-system validation on 25 July 2026 proved:

1. **Healthy baseline**
   - `wlan0` active at `192.168.1.110`;
   - default gateway `192.168.1.1` reachable;
   - NetworkManager, SSH, Tailscale, and the health timer active.

2. **Tailscale-only failure**
   - three consecutive Tailscale failures were recorded;
   - the third failure executed `tailscale_restart` with return code `0`;
   - Tailscale returned to `Running` and online state;
   - network and SSH remained healthy.

3. **Unreachable gateway with nominal NetworkManager state**
   - NetworkManager continued to report the expected Wi-Fi connection;
   - the default route remained installed;
   - the gateway probe correctly reported `gateway_reachable=false`;
   - `network_config_ok=true` and `network_ok=false` were recorded;
   - the third consecutive failure executed `network_reconnect` with return
     code `0`;
   - NetworkManager escalation did not occur during the three-failure test.

4. **Persistent gateway failure**
   - the third failure executed `network_reconnect` with return code `0`;
   - failures four and five produced no additional premature action;
   - the sixth failure executed `network_manager_restart` with return code `0`;
   - the gateway and default route recovered;
   - SSH remained or became active;
   - Tailscale returned online;
   - the production timer was restored;
   - the temporary firewall rule was removed.

5. **Isolation and deployment**
   - tests used isolated state directories under `/tmp`;
   - production counters remained unchanged;
   - the repository and `/usr/local/libexec/` monitor checksums matched;
   - 15 focused tests passed;
   - the production timer continued producing healthy snapshots.

The software repair is therefore complete. Issue #51 remains open only for the
deferred physical and external validation planned for September 2026.
