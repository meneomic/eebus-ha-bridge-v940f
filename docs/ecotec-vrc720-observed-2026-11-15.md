# Vaillant ecoTEC + sensoCOMFORT VRC 720 + VR 940f — baseline (2026-11-15)

> **Scope:** evidence from one Home Assistant EEBUS diagnostic export, a Go
> bridge log and screenshots of the Home Assistant entity registry supplied by
> the installation owner. These are observations, not a general Vaillant
> interoperability guarantee. This file intentionally excludes device SKIs,
> serial numbers, addresses and certificate material.

## Installed stack

- Home Assistant OS 18.4, Core 2026.11.1 (Proxmox VM).
- EEBUS Home Assistant integration 0.18.0 from volschin.
- Bridge is paired to the VR 940f over local SHIP/SPINE; HA integration uses
  loopback gRPC, port 50051, local push semantics.
- Boiler: Vaillant ecoTEC; controller: sensoCOMFORT VRC 720; heating zone Rdc.

## Confirmed via HA EEBUS diagnostics

| EEBUS field | Snapshot | Interpretation |
| --- | --- | --- |
| connection.connected | true | SHIP connection existed at capture time |
| connection.ski_registered | true | Remote identity registered |
| capabilities.room_heating | available | Heating control capability exposed |
| hvac.setpoint | 18.0 °C | Target exposed with writable=true |
| hvac.min/max/step | 5/30/0.5 °C | Advertised constraints, not a performed write test |
| hvac.system_function | auto | Modes auto/on/off; mode_writable=true |
| hvac.zone_label | Rdc | Room heating zone |
| room_temperature_c | 18.5 °C | Observed local measurement |
| outdoor_temperature_c | 6.5 °C | Observed local measurement |
| capabilities.dhw | unsupported | remote_not_advertised |
| capabilities.dhw_system_function | unsupported | remote_not_advertised |
| capabilities.monitoring | unsupported | remote_not_advertised |
| capabilities.lpc/ohpcf/failsafe/heartbeat | unsupported | Not advertised at capture time |
| flow_temperature_c, return_temperature_c | null | No usable value in this projection |
| dhw_temperature_c | null | No usable value in this projection |

Only the room heating capability was available at the diagnostic instant.
The existence of a generic HA entity for a feature **does not imply** that the
VR 940f exposes its backing function on this boiler.

The snapshot also showed a successful gRPC stream (no reconnects or dropped
events) but bridge readiness `DEVICE_READINESS_GRACE_PERIOD`, so the stability
of the session must be evaluated separately.

## Bridge log evidence

- 2026-11-15 10:59:18: monitoring recovery, stale, invalidate, reconnect,
  grace_period (attempt 1).
- 2026-11-15 11:01:48: same sequence (attempt 2).
- 2026-11-15 11:06:18: same sequence (attempt 3).
- `EEBUS debug_events=false` in the captured startup log.

These records indicate a stale-data recovery path, **not by themselves** proof
of a network disconnection or a failed authentication. The log does not contain
a complete `[DISCOVERY]` dump of the remote feature functions.

## Inventory comparison: myVAILLANT entity registry (cloud)

Names visible in screenshots (current state and reliability not established):

- `System Water Pressure`, `Trouble Codes`.
- `Current Flow Temperature`, `Flow Temperature Setpoint`,
  `Heating Curve`, `Min Flow Temperature Setpoint`.
- `Heating State`, `Heating Operating Mode`, `Desired Heating Temperature`.
- DHW `Setpoint`, `Boost`, `Operation Mode`.
- `Consumed Primary Energy Heating`,
  `Consumed Primary Energy Domestic Hot Water`,
  `Heat Generated Heating`, `Heat Generated Domestic Hot Water`.

These are **investigation targets**, not evidence that EEBUS provides them.
Cloud telemetry may originate from eBUS data that the VR 940f does not publish
over the external EEBUS interface.

## Implementation and validation order

1. **Keep the existing installed bridge** and its certificate/serial identity.
2. Inspect recovery behaviour and collect an EEBUS `[DISCOVERY]` dump *only*
   through a controlled approach that preserves the active add-on's `/data`
   identity. Do not install a second add-on on the same ports.
3. Run the offline `scripts/spine_inventory.py` parser on the redacted
   discovery log; compare its entries against the existing aroTHERM-specific
   `docs/vr940-function-inventory.md`.
4. Implement read-only Home Assistant entities only for confirmed usable
   source data. Test data freshness and units; keep unavailable sensors
   unavailable rather than inferring values.
5. Review writable functions and service calls separately. An advertised
   `w` permission is not permission to execute an untested heating command.
6. If boiler pressure, burner state, fault codes, or flow/return temperatures
   are not present in the full EEBUS discovery, evaluate a separate eBUS
   adapter/ebusd integration as a complementary source.

**Not performed:** actual setpoint write test, cloud-blocking test, raw
SPINE capture on this ecoTEC, custom add-on deployment, or control commands.
