# EEBUS Bridge — Vaillant Preview (EXPERIMENTAL)

This is a second, independent Supervisor app, built from our signed fork candidate.
The original installed app `aa6fc4a7_eebus_bridge` is NOT replaced and MUST
remain installed throughout testing. The preview app cannot share its `/data`.

## Safety / prerequisites

- Tested only on Home Assistant OS amd64, Vaillant ecoTEC / VR 940f.
- **Keep the original EEBUS app installed** for immediate rollback.
- Tested backup: `fc0c9905` (unprotected, present on local and QNAP;
  three identity files confirmed). Do not disclose it or store it in git.
- The preview app maps the `/backup` directory **read-only**. It can read all
  backups, so install only after reviewing and verifying the signed image.
- The preview does not generate any serial or certificate. If import fails,
  the app aborts without starting EEBUS.
- A single active bridge at a time: SHIP 4712 and gRPC 50051.
- **No automation or Home Assistant installation is performed by CI.**
- Confirm the signed candidate image is available to Home Assistant before
  installing. The Dockerfile pins a digest, not a mutable tag.

## Dry-run installation preparation (does not start the preview)

1. In Settings > Apps > Install app > ⋮ > Repositories add:
   `https://github.com/meneomic/eebus-ha-bridge-v940f#feat/vaillant-rc-preview`.
   A branch suffix is supported by Supervisor.
2. Select **EEBUS Bridge Vaillant Preview**, NOT the unchanged upstream
   `EEBUS Bridge` package that also appears in this repository.
3. Install but do **not** start it until the original has been stopped.
4. Under its configuration, enter only the *backup slug* in
   `migration_backup_slug`; do not paste any private keys into options:
   `fc0c9905`.
5. Keep `debug_events=false` / `ship_log=false` at initial start.

## Controlled cutover (only after preview image build and restore reviewed)

1. Check the original bridge's current status, and copy recent logs for baseline.
2. Stop the **original** with
   `ha apps stop aa6fc4a7_eebus_bridge`.
3. Start the **preview** using its exact slug shown by `ha apps list` or in
   the app UI. Do not assume a repository ID.
4. On first start, the preview extracts `data/serial`, `data/certs/cert.pem`,
   and `data/certs/key.pem` directly from the **local unprotected**
   `/backup/fc0c9905.tar` to its own private `/data`. It neither
   displays nor copies them to `/share`.
5. Confirm original local SKI matches (redacted suffix `...173DA7`),
   that the existing gRPC EEBUS integration reconnects, and that room
   temperature, outdoor temperature, and room-heating setpoint are available.
6. Let the preview run beyond 20 minutes: the watchdog should not enter
   `stage=stale` when the remote advertises `room_heating=available`
   and `monitoring=unsupported`.

## Immediate rollback

1. Stop the **preview** using the slug from its own app page or `ha apps list`.
2. Start the unchanged original:
   `ha apps start aa6fc4a7_eebus_bridge`.
3. Confirm `ha apps info aa6fc4a7_eebus_bridge` shows `state: started`,
   then validate EEBUS room-heating values in HA.
4. Never delete the original app or its private `/data`; do not re-pair
   Vaillant to troubleshoot before checking the logs.

The backed-up identity is sufficient for a restoration attempt, but an exact
SKI match and successful reconnection must be verified on live hardware.
