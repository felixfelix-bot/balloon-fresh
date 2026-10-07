# ADR index — canonical number → filename map

**This file is GENERATED.** Do not hand-edit it: run
`python3 scripts/gen_adr_index.py` after adding or removing an ADR.

## The numbering rule (binding)

- A new ADR takes its number from `scripts/adr_next_number.py`, which
  prints the next free number at or above **044** and exits
  non-zero if its target path already exists. Do not pick a number by hand.
- **044 and above are reserved for sequential allocation.**
  Numbers 001–043 are historical.
- **Do not rename or renumber an existing ADR file again.** References to them exist
  outside `docs/adr/` (code, coordination docs, branch names, external links)
  and a rename silently breaks them. The one authorised exception was the
  **2026-10-07 duplicate-number fix** (branch `adr/renumber-collisions`): where two
  or more files shared a number, the live record kept it and the displaced
  historical records moved into the **100 range**, which is outside the sequential
  allocation band so it can never race it. That displacement is done; treat the
  100-range numbers as permanent. Any *new* collision is a defect to report,
  never to fix by another rename.
- Where a collision cannot be resolved from evidence (a file's own Status
  header, or a supersede pointer inside a committed record), this index says
  `UNRESOLVED - needs an operator decision`. It never guesses.

Generated from `docs/adr/`: **71** distinct
numbers, **71** numbered files, **1** non-conforming filenames.

## Collisions

None.

## Number → files

| # | file | title | own Status |
|---|---|---|---|
| 001 | `001-esp32-c3-as-mcu.md` | ESP32-C3 als Mikrocontroller | Akzeptiert |
| 002 | `002-lr2021-as-rf-chip.md` | Semtech LR2021 als LoRa-Transceiver (Gen 4) | Akzeptiert |
| 003 | `003-dual-track-hardware.md` | Dual-Track Hardware-Design (Dev + Flight) | Akzeptiert |
| 004 | `004-3d-yagi-antenna-structure.md` | 3D Yagi-Antennen-Struktur (4 Wings + Hub) | Akzeptiert |
| 005 | `005-sky66112-fem.md` | SKY66112-11 als Front-End-Module (PA + LNA) | Akzeptiert |
| 006 | `006-supercapacitor-power.md` | Supercapacitor-Stromversorgung (Solar + Supercaps) | Akzeptiert |
| 007 | `007-adaptive-protocol.md` | Adaptive Protokoll-Strategie (LoRa/FLRC/Sub-GHz) | Akzeptiert |
| 008 | `008-telemetry-protocol.md` | Telemetrie-Paketformat | Akzeptiert |
| 009 | `009-antenna-strategy-v1-v2.md` | V1 Omnidirectional Antennas with V2 Directional Upgrade Path | Accepted |
| 010 | `010-adaptive-tx-power.md` | Adaptive TX Power and Modulation per TDMA Slot | Accepted |
| 011 | `011-first-flight-strategy.md` | First Flight Strategy — Single Balloon, Helium, Minimal Variant | Accepted |
| 012 | `012-mesh-networking-strategy.md` | Mesh Networking Strategy — FIPS + MeshCore + TollGate + Nostr | Accepted |
| 013 | `013-cluster-aware-stratorelay.md` | Cluster-Aware Stratorelay for MeshCore | Proposed |
| 014 | `014-bent-pipe-fpga-bridging.md` | Bent-Pipe FPGA/RP2040 Bridging for Multi-Balloon Mesh | Proposed |
| 015 | `015-three-board-hardware-strategy.md` | Three-Board Hardware Strategy | Proposed |
| 016 | `016-fips-implementation-keep-cpp-microfips.md` | FIPS Implementation — Keep C++ microfips | Accepted |
| 017 | `017-phase-sync-via-reference-clocks.md` | Phase Synchronization via Independent Reference Clocks | Accepted |
| 018 | `018-multi-mode-range-characterization.md` | Multi-Mode Range Characterization Protocol | Accepted |
| 019 | `019-gps-synchronized-mode-switching.md` | GPS-Synchronized Time-Division Mode Switching | Accepted |
| 020 | `020-deprecate-radiolib-adopt-raw-lr2021-spi.md` | Deprecate RadioLib LR2021 Driver — Adopt Raw 2-Byte Opcode Protocol | Accepted |
| 021 | `021-absolute-utc-phase-sync.md` | Absolute UTC Phase Synchronization — No Boot-Time GPS Gate | Accepted |
| 022 | `022-mandatory-test-coverage.md` | Mandatory Full Test Coverage for Walk Test Firmware | Accepted |
| 023 | `023-tx-autonomy-and-mode-sync.md` | TX Full Autonomy and TX/RX Mode Synchronization | Accepted |
| 024 | `024-extract-only-source-repository-policy.md` | Extract-Only Source Repository Policy | ACCEPTED |
| 025 | `025-shared-hardware-flock-mutex.md` | Shared Hardware Access — Mandatory flock Mutex for ESP32-C3 + LR2021 | ACCEPTED |
| 026 | `026-dual-mcu-radio-architecture.md` | Dual MCU Radio Architecture — RP2040 Radio Processor + ESP32-C3 Application | ACCEPTED |
| 027 | `027-blossom-on-ip-layer.md` | Blossom Server Stacks on IP Layer — Not Raw Mesh Datagram | ACCEPTED |
| 028 | `028-schematic-first-three-variants.md` | Schematic-First PCB Design with Three MCU Variants | Proposed |
| 029 | `029-dual-band-flight-board.md` | v9 tri-band flight board (ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S) | Proposed |
| 030 | `030-deterministic-zero-inference-pcb-pipeline.md` | Deterministic, zero-inference PCB placement and routing | Proposed |
| 031 | `031-board-bring-up-isolation-and-staged-population.md` | Board bring-up isolation, testability, and staged population | Accepted |
| 032 | `032-simulation-evidence-ltspice-openems.md` | Simulation evidence for PCB design (LTspice + openEMS + stackup impedance) | Accepted |
| 033 | `033-giftwrap-single-construction-path.md` | Gift-wrap construction has one canonical primitive | Proposed |
| 034 | `034-radio-band-split-433-tx-2g4-rx.md` | v9 radio band split: 433 MHz TX / 2.4 GHz RX on two separate chips | Proposed |
| 035 | `035-tdm-radio-schedule.md` | TDM radio schedule: dedicated ranging windows, one transmitter at a time | Proposed |
| 036 | `036-energy-policy-burst-storage-daylight-only-tx.md` | Energy policy: burst-sized storage, daylight-only TX | Proposed |
| 037 | `037-mcu-s3-no-fem.md` | v9 MCU = ESP32-S3; SKY66112 front-end module omitted from v9 | Proposed |
| 038 | `038-wifi-bt-disabled.md` | v9 ESP32-S3: Wi-Fi/BT is never enabled, external antenna path left unpopulated | Proposed |
| 039 | `039-licence-exempt-433-design-point.md` | Licence-Exempt 433 MHz Design Point | Proposed |
| 040 | `040-v9-radio-site-optionality.md` | v9 dual radio-site optionality: one LP-or-HP variant site plus one LP-only site | Proposed |
| 041 | `041-rf-frontend-licence-exempt.md` | v9 RF front end under the ≤ 10 mW licence-exempt regime: gain on the ground, F33 internal LNA in circuit, no balloon FEM | Proposed |
| 042 | `042-thermal-drift-strategy.md` | Thermal / frequency-drift strategy for the balloon radio | Proposed |
| 043 | `043-cold-qualification-heating.md` | Cold Qualification — Heating Rejected, Below-Rated Parts Gated | Accepted |
| 044 | `044-v9-power-rails.md` | v9 power rails: the F33 5 V rail (resolves ADR-029 item O5) | Proposed |
| 045 | `045-antenna-solder-access.md` | Antenna solder-access constraint (hand-soldered RF parts must be reachable from outside the module body) | Proposed. The *decision* this ADR records is the operator's standing |
| 046 | `046-wing-board-interface.md` | Wing-board interface: tab/socket geometry, 4-wire pinout, wing outline, order shape | Proposed |
| 047 | `047-v9-power-provisioning.md` | v9 F33 power provisioning: over-provisioning the 5 V PA rail for the module's maximum draw | Proposed |
| 048 | `048-v9-hub-wing-interfaces.md` | v9 hub-side wing interfaces: four socket land sets at 90° | Proposed |
| 049 | `049-wing-architecture.md` | Wing architecture: cell class, structure, orientation and protection | Proposed |
| 050 | `050-mppt-charge-path.md` | Charge-path converter between the solar array and the supercap bank | Proposed |
| 051 | `051-hub-array-and-cut-topology.md` | Hub-mounted solar array as an INDEPENDENT string: the wing cut topology and the cut-sense provision | Proposed |
| 052 | `052-cell-mounting-end-only.md` | Bare cells are mounted END-ONLY: no adhesive bond, no bonded-and-vented carrier | Proposed |
| 053 | `053-per-cell-bypass-diodes.md` | Per-cell / per-group bypass Schottky diodes: a cracked or shaded cell costs one cell, not the whole series string | Proposed |
| 054 | `054-array-topology-final.md` | Array topology, final: the 12-cell series string is RETAINED, the hub-side per-interface bypass diode is MANDATORY, per-cell bypass is REJECTED, and the bypass-diode mechanism is CORRECTED | Proposed |
| 055 | `055-hub-geometry-final.md` | Hub geometry, final: the array plane is HORIZONTAL (flat, no tilt, zero ripple), the area is a DUTY CHOICE, the board is 0.4 mm, the hub is ≈103 mm square, and the cells go on the UPPER face under a raised attachment standoff | Proposed |
| 056 | `056-thermal-and-frequency-drift.md` | Thermal and frequency drift: no oscillator heater, TCXO where a radio needs one, and GPS 1PPS discipline as the zero-mass/zero-watt provision | Proposed |
| 057 | `057-flrc-drift-strategy.md` | FLRC drift strategy: FLRC's offset tolerance is band-independent in Hz, so the 2.4 GHz uplink is the exposure, the degradation ladder must not slow the FLRC rate, and the ranked mitigations | Proposed |
| 058 | `058-onboard-temp-compensation.md` | On-board temperature-sensor-based drift compensation: the LR2021's XOSC-adjacent sensor as the primary instrument, a per-unit calibration curve, GPS 1PPS verification, and an MS5611 cross-check | Proposed |
| 059 | `059-ntc-temp-compensation-provision.md` | LR2021 on-chip NTC temperature compensation: the provision, the TCXO-vs-NTC mutual exclusion, the thermal-coupling siting rule, and the module pin-breakout blocker | Proposed |
| 060 | `060-sx1280-drift-strategy.md` | SX1280 drift strategy: the retained 2.4 GHz ranging radio, whether its ranging role needs drift control at all, and the ranked provisions | Proposed |
| 100 | `100-tollgate-over-fips-mesh-udp.md` | TollGate Payment Messages Transport Over FIPS Mesh UDP | ACCEPTED |
| 101 | `101-lr2021-only-ban-sx1280.md` | REVISED — LR2021 SPI Protocol Clarification | SUPERSEDED by ADR-020 |
| 102 | `102-version-tagging-policy.md` | Version Tagging Policy — Tag on Progress Without Regressions | Accepted |
| 103 | `103-tx-autonomy-requirement.md` | TX Board Must Operate Fully Autonomously | Superseded |
| 104 | `104-tx-rx-sync-invariant.md` | TX-RX Synchronization Invariant — Same 56-Phase Sweep | Accepted |
| 105 | `105-reproducible-build-flash-test.md` | Reproducible Build, Flash, and Test via Make Targets + pytest | Accepted |
| 106 | `106-e-hash-relay-transport-layer.md` | 106-e-hash-relay-transport-layer | Proposed |
| 107 | `107-three-variant-pcb-design.md` | Three-Variant PCB Design (C3, S3, C3+RP2040) | Proposed |
| 108 | `108-f33-sx1280-pin-plan.md` | V9 D2b(b) — LoRa2021F33 + SX1280 pin plan | proposed implementation baseline, pending schematic ERC and module-datasheet |
| 109 | `109-firmware-output-harmonization.md` | Firmware Output Harmonization | APPROVED |
| 110 | `110-tollgate-over-lr2021.md` | TollGate Balloon Uses LR2021 Radio as Data Link | Proposed |
| ≥044 | *(reserved)* | next free: `scripts/adr_next_number.py` → 061 | — |

## Non-conforming filenames (not `NNN-description.md`)

These are listed so they are not mistaken for free numbers. They are NOT
renamed by this script (see the rule). Note that `110-tollgate-over-lr2021.md`
effectively competes for number **001** with `001-esp32-c3-as-mcu.md`; it is
recorded here rather than silently renumbered, and that pair also needs an
operator decision.

- `adr-e-hash-relay-DECISIONS.md` — ADR: E-Hash Relay Transport — LOCKED DECISIONS LOG (own Status: UNKNOWN)

