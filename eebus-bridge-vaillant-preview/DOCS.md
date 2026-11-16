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

## Preview 0.18.1 — signed heating-triggered SPINE discovery

- Candidate source commit: `be6bf5b48303ea3d2fa3437ef6c0a65e6a9bc6a0`.
- Pinned and verified OCI image: `ghcr.io/meneomic/eebus-bridge@sha256:c52fcc0615408ef5fe00da7f0fd0ae3653b60f28f848434e3b6ba397cec6e2e8`.
- Functional difference from Preview 0.18.0: when `debug_events: true`, the
  device's remote SPINE entities, features, function permissions and use cases
  are logged on **CRHT, MRHSF, MRT, MOT and MDT** events as well as MPC events.
  Previously the only discovery hook was MPC, which Vaillant ecoTEC does not
  advertise. No new control commands are sent to the heating system.
- The previously validated watchdog behavior is unchanged.
- Home Assistant integration remains at API version 0.18.0; **0.18.1 is the
  version of the separate experimental add-on only**.

### Safe in-place update after the existing preview is stable

1. Keep the old independent add-on `aa6fc4a7_eebus_bridge` installed but
   stopped, with its autostart off. Keep the verified backup `fc0c9905`
   (and the QNAP copy). Prefer a new partial Home Assistant backup containing
   the currently running Preview before updating it.
2. Refresh the custom app repository in Home Assistant. Confirm an update to
   **EEBUS Bridge Vaillant Preview 0.18.1** is offered. Do not update the
   unpatched original add-on by mistake.
3. Set `debug_events: true` and `ship_log: false`, then update only the Preview
   app. An app update may restart the bridge; a brief SHIP reconnect is expected.
4. Confirm the local SKI remains `…173DA7` and the remote SKI `…7604ED`.
   Wait for new CRHT/MRT/MOT callbacks, then collect:

   ```bash
   ha apps logs e9c1c275_eebus_bridge_vaillant_preview | grep -F '[DISCOVERY]'
   ```

5. Disable `debug_events` after collecting. Recheck `DEVICE_READINESS_READY`,
   `monitoring=unsupported`, `room_heating=available`,
   `recovery.attempts=0` and a running gRPC device stream.
6. If the new version cannot connect, stop the Preview immediately and
   restart the original add-on. Do not re-pair Vaillant. A Supervisor backup
   of Preview 0.18.0 offers an additional in-place rollback path.

Never publish raw full SHIP traces, certificates or private keys.
