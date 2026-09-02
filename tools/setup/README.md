# Setup Tools

This folder contains host/runtime setup helpers for the thesis perception stack.

These scripts are operational setup aids. They should be used carefully because
they may download packages, install Python wheels, or modify local runtime
folders.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `install_host_hailo_bindings.sh` | Support workflow | Installs host-side Hailo Python bindings into a selected virtualenv when compatible wheels are available. |
| `setup_local_tappas_runtime.sh` | Support workflow | Prepares a local non-root TAPPAS runtime tree for single-process perception mode. |

## Usage policy

Prefer documented environment variables and explicit paths when running setup
scripts. Do not run them during evaluation unless the runtime environment
actually needs repair or recreation.

For normal replay/evaluation work, these scripts should not be needed.

## Field UI firewall

`setup_field_ui_firewall.sh` is the one-time host setup helper for the field
operator interface. It installs inbound UFW rules for TCP 5173, 8080, 8090, and
8765 on `wlan0`, plus TCP 22 on `wlan0` restricted to the approved field
operator subnet. The default SSH source is `192.168.8.0/24`, the retained
`ISR Aero.Next GCS` subnet. It does not create public SSH exposure or router
port forwarding. A different explicitly approved field subnet may be supplied
with `FIELD_OPERATOR_SSH_CIDR`.

Run it during Pi preparation, not as part of normal field startup:

    cd ~/Desktop/Thesis-Code || exit 1
    tools/setup/setup_field_ui_firewall.sh

Normal field operation uses the stable top-level
`tools/start_field_ui.sh` entrypoint.
