# Pi handover: access, network and ownership

Last reviewed: 2026-10-15

## Purpose

Everything a new maintainer needs to reach and take ownership of the Raspberry
Pi 5, written for the case where the previous maintainer's Tailscale network is
no longer available. No password, key or token is stored in this repository;
where one is needed this document says how to obtain or replace it.

## The machine

| Item | Value |
| --- | --- |
| Hostname | `fcstpi` |
| User | `francisco` (member of `sudo`, `docker`, `dialout`, `video`, `gpio`, `i2c`, `spi`) |
| OS | Ubuntu 24.04 LTS, Raspberry Pi 5, kernel `6.8.0-*-raspi` |
| Repository | `/home/francisco/Desktop/Thesis-Code` (branch `main`, remote `origin` on GitHub: `FRCTavares/IST-Thesis-Code`) |
| Dashboard repo | `/home/francisco/Desktop/IST-Thesis-UI` (`FRCTavares/IST-Thesis-UI`) |
| Python env | `thesis_env/` in the repository (loaded by `direnv`, see [GETTING_STARTED.md](GETTING_STARTED.md)) |
| Recordings | `bags/` in the repository, plus `~/flight_evidence_*`, `~/flight_recovery_*`, `~/flight_sheets_*`, `~/flight_state_*` |
| Hardware sources | `~/src/hardware` (Hailo PCIe driver, kernel and TEVS camera driver sources) and `~/src/vendor` |

## How to reach the Pi

The Pi has three network roles. Only the first depends on Tailscale.

1. **Remote, any network: Tailscale** (`ssh francisco@fcstpi`). This was the
   normal path and belongs to the previous maintainer's Tailscale account.
2. **Local field network: `ISR Aero.Next GCS`** Wi-Fi. Join it and use
   `ssh francisco@192.168.8.174`. This works without Tailscale.
   `tools/mac/thesis_field_connect.sh` checks the connection and opens the shell.
3. **Console:** HDMI + keyboard on the Pi, or a USB serial/Ethernet link. Always
   works and is the recovery path of last resort.

The Pi's other Wi-Fi addresses (for example on the IST/ISR campus network) are
DHCP and change. The installed firewall (`tools/host/install_unattended_host_recovery.sh`)
default-denies inbound traffic: SSH is allowed through `tailscale0` and on
`wlan0` **only from the GCS management subnet (`192.168.8.0/24`)**. Check the
live rules with `sudo ufw status verbose`.

### What changes when the Pi leaves the previous maintainer's Tailscale

- Remote SSH from outside the lab stops working until the Pi joins a new
  tailnet. On a campus or home Wi-Fi it will **not** be reachable by plain SSH
  because of the firewall rule above.
- Field work (GCS Wi-Fi, role 2) and console access are unaffected.
- `thesis-host-health.timer` keeps running; it only restarts Tailscale when the
  gateway is reachable, so it is harmless without a tailnet.

### Moving the Pi to your own Tailscale (recommended)

Do this once someone is physically at the Pi or connected over the GCS network:

```bash
sudo tailscale logout                    # leave the previous owner's tailnet
sudo tailscale up --hostname fcstpi      # prints a login URL: sign in with the new account
tailscale status
```

Then in the new tailnet's admin console disable key expiry for this node (the
last audited expiry was short; an expired key silently drops remote access) and
add whoever should be allowed in through the ACLs. Never commit an auth key or
the Tailscale state directory. Related procedures:
[debug/UNATTENDED_PI_OPERATION.md](debug/UNATTENDED_PI_OPERATION.md).

If you do not want Tailscale at all, either stay on the GCS network and the
console, or add a deliberate firewall rule for your own subnet (with a second
working session open): `sudo ufw allow in on wlan0 from <your-subnet>/24 to any port 22`.

## Accounts, keys and passwords

- **SSH keys:** `~/.ssh/authorized_keys` currently holds a single key, the
  previous maintainer's Mac. **Every new maintainer must add their own key**
  before the previous one is revoked, from a machine that can already log in
  or at the console:

  ```bash
  ssh-copy-id -i ~/.ssh/id_ed25519.pub francisco@192.168.8.174   # on the GCS network
  # or on the Pi itself: append the public key to ~/.ssh/authorized_keys
  ```

  Then remove the old key line from `~/.ssh/authorized_keys`.
- **sudo / account password:** held by the previous maintainer. Hand it over
  through a password manager, then change it with `passwd`. Without it only
  non-root work is possible (`sudo` is used for network modes, drivers and
  the firewall).
- **Wi-Fi credentials** live only in NetworkManager profiles on the Pi, never in
  this repository.
- **GitHub:** the clone uses the remote `origin`. New maintainers need access to
  `FRCTavares/IST-Thesis-Code` and should authenticate with their own key or
  token (`git remote -v`, `git config user.name/user.email`).
- Set `git config user.name` / `user.email` on the Pi to the person actually
  committing.

## Wi-Fi and network profiles (NetworkManager)

| Profile | Role |
| --- | --- |
| `ISR` | Normal campus Wi-Fi (autoconnect). |
| `ISR Aero.Next GCS` | **Field authority** profile. Never autoconnects; activated only by `sudo tools/host/set_pi_network_mode.sh pixhawk`. |
| `ISR Aero.Next GCS Rescue` | Low-priority management clone so SSH stays reachable on the GCS network. |
| `pixhawk-apm`, `pixhawk-px4` | Dedicated Ethernet profiles for the Pixhawk link (`192.168.144.x`). |
| `netplan-wlan0-Wi-Fi MC`, `Wired connection 1` | Other saved connections. |
| `FCT iPhone 15` | **Personal hotspot of the previous maintainer; delete it:** `sudo nmcli connection delete "FCT iPhone 15"`. |

Modes: `sudo tools/host/set_pi_network_mode.sh status|unattended|pixhawk`. Field
mode stops Tailscale by design. See the full contract in
[debug/UNATTENDED_PI_OPERATION.md](debug/UNATTENDED_PI_OPERATION.md).

## Services enabled on the Pi

`NetworkManager`, `ssh.socket`, `tailscaled` and `thesis-host-health.timer` start
at boot; the hardware watchdog is armed. **No ROS, MAVROS, perception or control
service starts by itself.** The live stack only runs when someone starts
`tools/start_live_stack.sh`. Check with:

```bash
systemctl is-enabled NetworkManager ssh.socket tailscaled thesis-host-health.timer
systemctl --failed --no-pager
```

## First-day checklist for a new maintainer

1. Get console or GCS-network access and the sudo password; log in.
2. Add your SSH key, remove the old one, change the password.
3. Move the Pi to your Tailscale (above) or decide on another remote path.
4. Delete the `FCT iPhone 15` profile; review `nmcli connection show`.
5. `cd ~/Desktop/Thesis-Code && git status && git pull`; set your git identity.
6. Run the checks in [GETTING_STARTED.md](GETTING_STARTED.md) section 5, then a
   ground run from [OPERATIONS.md](OPERATIONS.md).
7. Check storage (`df -h /`; recordings stop below `RECORDING_MIN_FREE_GIB`) and
   decide who backs up `bags/live_camera` and the `flight_*` folders.
8. Read [flight/field_day_runbook.md](flight/field_day_runbook.md) before any
   aircraft work; the pilot owns arming and takeover.

## Backups that exist outside the Pi

The previous maintainer kept the thesis research data, annotations, old
campaign runs and the research archive on a personal Mac; those are not
available to other maintainers through this repository. The research
*source* history is in Git: tag `archive/thesis-final-20261013`.
Final recordings on the Pi (`bags/source`, `bags/reference`, `bags/live_camera`,
`bags/source_video`) may exist **only** there, so copy them off the Pi before
reflashing or replacing the SD card.
