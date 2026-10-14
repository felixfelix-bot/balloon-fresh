# SOFTWARE PREPARE LIST — build before the flights

**Date:** 2026-10-14 · operator instruction: implement as **independently tested
libraries** that compose into one deployment, and add the link layers.

**Principle:** each item is a module with its own unit tests, no dependency on
the others. A flight build picks the modules it needs. A flight that cannot log
its experiment is a wasted flight — so the logging modules are the priority.

## Link layers (operator-added)

| # | Library | Purpose | Notes |
|---|---|---|---|
| L1 | **FLRC (SX1280)** | Primary base↔balloon link, range & speed experiments | existing work; keep the toolchain |
| L2 | **LoRaWAN** | Long-range fallback + experiment channel once FLRC is out of range | needs a LoRaWAN stack (e.g. LMIC-style) on LR2021; regional params, duty-cycle limits, join/OTAA, uplink payload ≤ 51–242 B depending on DR |
| L3 | **MeshCore** | Mesh transport on LR2021 | operator-requested |
| L4 | **Meshtastic** | Mesh transport on LR2021 | operator-requested; shares LR2021 driver with L3 |

**Design consequence:** L2–L4 all want the LR2021 radio. The radio driver must
be a **shared abstraction** with per-protocol schedulers, or they fight over the
SPI bus and the TCXO. Build the LR2021 driver once (L0) and put L1–L4 on top.

## Logging & survival (the experiment enablers)

| # | Library | Purpose | Pass criterion |
|---|---|---|---|
| S1 | **telemetry schema** | one struct + serializer covering NTC_SENSE, SCAP_ADC, F33_VSENSE, HUB_PV_MID1/P/N, GPS (fix/sats/alt/vdop), link stats (RSSI/SNR), uptime, reset-cause, experiment-mode | round-trip encode/decode property test; versioned |
| S2 | **store-and-forward ring** | littlefs ring buffer in flash; survives reboots and brownout at any write point | power-cut torture test: kill at random offsets, assert no corrupt record and no lost prior record |
| S3 | **reset-cause + brownout log** | persist esp_reset_reason() + a boot counter across reboots | E-CS3/E-CS4 hinge on this; assert monotonically increasing boot ids |
| S4 | **GPS config** | apply **airborne <1 g** dynamic platform model + airborne CoCom config at boot | read-back the UBX config and assert it stuck |

## Housekeeping modules

| # | Library | Purpose | Pass criterion |
|---|---|---|---|
| H1 | **energy-budgeted duty scheduler** | priority: telemetry > cold-start logging > link stats; enforces the flight duty-cycle table from E-CS5 | schedule honours budget in a simulated sun/night profile |
| H2 | **experiment-mode framework** | enable/disable an experiment from the ground, with its own telemetry slot | a disabled experiment costs zero energy |

## Test discipline (per the project's standing rules)

- TDD: RED test observed failing before the implementation.
- Each library: unit tests + at least one **counter-test** that proves the test
  can fail (the pattern used in `services/jlc-quote/src/pcba.test.ts`).
- No library may claim a capability it has not exercised on hardware or a
  recorded fixture.
- Firmware builds must pass `pio run` for the ESP32-S3 target before merge.

## Deliverable order (dependency-sorted)

1. **S1** schema (everything else speaks it) → 2. **S3** reset-cause →
3. **S2** ring store → 4. **H1** scheduler → 5. **S4** GPS config →
6. **H2** experiment framework → 7. **L0** LR2021 driver → 8. **L2** LoRaWAN →
9. **L3/L4** MeshCore + Meshtastic on L0.

Items 1–6 are flight-blocking (no data otherwise); 7–9 are the fallback channel
and can land after the first flight if needed, but L2 (LoRaWAN) is required for
the cold-start experiment to report back.
