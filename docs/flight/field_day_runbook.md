# Field-Day Backup Index

Friday 25 September 2026. The **only canonical linear operator sheet** is
[README.md](README.md). Open it at the field; this short index does not replace
its network fallback, process-loss, pilot, event, matched-pair or evidence gates.

1. Confirm final Git SHA/clean tree, qualified pilot, spotter, hardware, site and storage.
2. Provision and physically validate the explicitly approved AERONEXT fallback;
   then enter Pixhawk field mode with the real FCU connected.
3. Run static preflight and the passive `--res vga --field-record --no-control`
   recorder gate.
4. Run compute-only signs/freshness and restrained BODY_NED command-path gates.
5. Kill the **exact** controller child during a recorded non-zero reference;
   require fail-closed FCU response and pilot takeover before flight.
6. Pilot go/no-go; first baseline flight; then predeclared three matched
   baseline/candidate pairs if safe.
7. Stop/finalize each run, verify exact MCAP/visual/operator package, archive
   human-selected DataFlash, document verdict and physical-person annotation.
8. Backup all attempts, including failures; return to unattended network mode.

#64 is closed with VGA 640x480 retained. Every #50 launch explicitly uses
`--res vga`. H01/H02/H03 are complete. Final #32 waits for the #50 physical
controller decision.
