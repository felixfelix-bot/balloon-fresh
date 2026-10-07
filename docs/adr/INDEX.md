# ADR index — canonical number → filename map

**This file is GENERATED.** Do not hand-edit it: run
`python3 scripts/gen_adr_index.py` after adding or removing an ADR.

## The numbering rule (binding)

- A new ADR takes its number from `scripts/adr_next_number.py`, which
  prints the next free number at or above **044** and exits
  non-zero if its target path already exists. Do not pick a number by hand.
- **044 and above are reserved for sequential allocation.**
  Numbers 001–043 are historical.
- **Never rename or renumber an existing ADR file.** References to them exist
  outside `docs/adr/` (code, coordination docs, branch names, external links)
  and a rename silently breaks them. A number used by two files is a
  *collision*: record it here, do not fix it by renaming.
- Where a collision cannot be resolved from evidence (a file's own Status
  header, or a supersede pointer inside a committed record), this index says
  `UNRESOLVED - needs an operator decision`. It never guesses.

Generated from `docs/adr/`: **44** distinct
numbers, **54** numbered files, **2** non-conforming filenames.

## Collisions

- **002 (2x)** — `002-lr2021-as-rf-chip.md`, `002-tollgate-over-fips-mesh-udp.md`
  - **LIVE:** `002-lr2021-as-rf-chip.md` (Status `Akzeptiert`) — the LR2021 chip selection. **SUPERSEDED:** none. The other file is an unrelated Accepted record (`002-tollgate-over-fips-mesh-udp.md`, transport layer), so no supersede chain joins them → `UNRESOLVED - needs an operator decision`.
- **017 (3x)** — `017-lr2021-only-ban-sx1280.md`, `017-phase-sync-via-reference-clocks.md`, `017-version-tagging-policy.md`
  - **LIVE:** `017-phase-sync-via-reference-clocks.md` and `017-version-tagging-policy.md` (both Status `Accepted`, unrelated topics). **SUPERSEDED:** `017-lr2021-only-ban-sx1280.md` — its own Status header reads `SUPERSEDED by ADR-020` (2026-07-23). Three unrelated records share 017 → `UNRESOLVED - needs an operator decision`.
- **018 (2x)** — `018-multi-mode-range-characterization.md`, `018-tx-autonomy-requirement.md`
  - **LIVE:** `018-multi-mode-range-characterization.md` (Status `Accepted (2026-07-22)`). **SUPERSEDED:** `018-tx-autonomy-requirement.md` — its own Status header reads `Superseded (partial) — 2026-07-27` and names no successor number, so the *number* is still not allocated → `UNRESOLVED - needs an operator decision`.
- **019 (2x)** — `019-gps-synchronized-mode-switching.md`, `019-tx-rx-sync-invariant.md`
  - **LIVE:** both — `019-gps-synchronized-mode-switching.md` (Status `Accepted (2026-07-22)`) and `019-tx-rx-sync-invariant.md` (Status `Accepted`). **SUPERSEDED:** none; they are unrelated topics with no supersede pointer between them → `UNRESOLVED - needs an operator decision`.
- **020 (2x)** — `020-deprecate-radiolib-adopt-raw-lr2021-spi.md`, `020-reproducible-build-flash-test.md`
  - **LIVE:** both — `020-deprecate-radiolib-adopt-raw-lr2021-spi.md` (Status `Accepted (2026-07-23)`, itself states it `Supersedes ADR-017`) and `020-reproducible-build-flash-test.md` (Status `Accepted`). **SUPERSEDED:** none (the 017 → 020 pointer is cross-number, it does not allocate 020) → `UNRESOLVED - needs an operator decision`.
- **025 (2x)** — `025-e-hash-relay-transport-layer.md`, `025-shared-hardware-flock-mutex.md`
  - **LIVE:** both — `025-shared-hardware-flock-mutex.md` (Status `ACCEPTED`) and `025-e-hash-relay-transport-layer.md` (Status `Proposed`). **SUPERSEDED:** none; unrelated topics, no supersede pointer → `UNRESOLVED - needs an operator decision`.
- **028 (2x)** — `028-schematic-first-three-variants.md`, `028-three-variant-pcb-design.md`
  - **LIVE:** `028-schematic-first-three-variants.md` — cited as the **accepted ADR-028** by `docs/coordination/PCB-MASTER-EXECUTION-PLAN.md` (lines 10 and 683) and committed later (`862c0c5`, 2026-08-05). **SUPERSEDED:** `028-three-variant-pcb-design.md` (`3356695`, same day, the earlier proposal); its own body says of the earlier script-generated workflow *"The schematic-first approach replaces this entirely."* Both documents cover the same subject (three MCU variants), so this collision IS resolvable. *(Files are NOT renamed — see the rule above.)*
- **029 (3x)** — `029-dual-band-flight-board.md`, `029-f33-sx1280-pin-plan.md`, `029-firmware-output-harmonization.md`
  - **LIVE:** `029-dual-band-flight-board.md` (Status `Proposed`) — the v9 design of record. **ANNEX (not a competing record):** `029-f33-sx1280-pin-plan.md`, which declares itself the pin plan for this ADR's D2b(b) and is named as such in ADR-029 §Rollout item 7. **UNRESOLVED:** `029-firmware-output-harmonization.md` (Status `APPROVED`) is an unrelated firmware record claiming the same number; ADR-029's own O7 flags it as unresolved → `UNRESOLVED - needs an operator decision`.

## Number → files

| # | file | title | own Status |
|---|---|---|---|
| 001 | `001-esp32-c3-as-mcu.md` | ESP32-C3 als Mikrocontroller | Akzeptiert |
| 002 **(COLLISION)** | `002-lr2021-as-rf-chip.md` | Semtech LR2021 als LoRa-Transceiver (Gen 4) | Akzeptiert |
| 002 **(COLLISION)** | `002-tollgate-over-fips-mesh-udp.md` | TollGate Payment Messages Transport Over FIPS Mesh UDP | ACCEPTED |
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
| 017 **(COLLISION)** | `017-lr2021-only-ban-sx1280.md` | REVISED — LR2021 SPI Protocol Clarification | SUPERSEDED by ADR-020 |
| 017 **(COLLISION)** | `017-phase-sync-via-reference-clocks.md` | Phase Synchronization via Independent Reference Clocks | Accepted |
| 017 **(COLLISION)** | `017-version-tagging-policy.md` | Version Tagging Policy — Tag on Progress Without Regressions | Accepted |
| 018 **(COLLISION)** | `018-multi-mode-range-characterization.md` | Multi-Mode Range Characterization Protocol | Accepted |
| 018 **(COLLISION)** | `018-tx-autonomy-requirement.md` | TX Board Must Operate Fully Autonomously | Superseded |
| 019 **(COLLISION)** | `019-gps-synchronized-mode-switching.md` | GPS-Synchronized Time-Division Mode Switching | Accepted |
| 019 **(COLLISION)** | `019-tx-rx-sync-invariant.md` | TX-RX Synchronization Invariant — Same 56-Phase Sweep | Accepted |
| 020 **(COLLISION)** | `020-deprecate-radiolib-adopt-raw-lr2021-spi.md` | Deprecate RadioLib LR2021 Driver — Adopt Raw 2-Byte Opcode Protocol | Accepted |
| 020 **(COLLISION)** | `020-reproducible-build-flash-test.md` | Reproducible Build, Flash, and Test via Make Targets + pytest | Accepted |
| 021 | `021-absolute-utc-phase-sync.md` | Absolute UTC Phase Synchronization — No Boot-Time GPS Gate | Accepted |
| 022 | `022-mandatory-test-coverage.md` | Mandatory Full Test Coverage for Walk Test Firmware | Accepted |
| 023 | `023-tx-autonomy-and-mode-sync.md` | TX Full Autonomy and TX/RX Mode Synchronization | Accepted |
| 024 | `024-extract-only-source-repository-policy.md` | Extract-Only Source Repository Policy | ACCEPTED |
| 025 **(COLLISION)** | `025-e-hash-relay-transport-layer.md` | 025-e-hash-relay-transport-layer | Proposed |
| 025 **(COLLISION)** | `025-shared-hardware-flock-mutex.md` | Shared Hardware Access — Mandatory flock Mutex for ESP32-C3 + LR2021 | ACCEPTED |
| 026 | `026-dual-mcu-radio-architecture.md` | Dual MCU Radio Architecture — RP2040 Radio Processor + ESP32-C3 Application | ACCEPTED |
| 027 | `027-blossom-on-ip-layer.md` | Blossom Server Stacks on IP Layer — Not Raw Mesh Datagram | ACCEPTED |
| 028 **(COLLISION)** | `028-schematic-first-three-variants.md` | Schematic-First PCB Design with Three MCU Variants | Proposed |
| 028 **(COLLISION)** | `028-three-variant-pcb-design.md` | Three-Variant PCB Design (C3, S3, C3+RP2040) | Proposed |
| 029 **(COLLISION)** | `029-dual-band-flight-board.md` | v9 tri-band flight board (ESP32-S3-WROOM-1U + LoRa2021F33-2G4 + SX1280 + MAX-M10S) | Proposed |
| 029 **(COLLISION)** | `029-f33-sx1280-pin-plan.md` | V9 D2b(b) — LoRa2021F33 + SX1280 pin plan | proposed implementation baseline, pending schematic ERC and module-datasheet |
| 029 **(COLLISION)** | `029-firmware-output-harmonization.md` | Firmware Output Harmonization | APPROVED |
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
| ≥044 | *(reserved)* | next free: `scripts/adr_next_number.py` → 045 | — |

## Non-conforming filenames (not `NNN-description.md`)

These are listed so they are not mistaken for free numbers. They are NOT
renamed by this script (see the rule). Note that `ADR-001-tollgate-over-lr2021.md`
effectively competes for number **001** with `001-esp32-c3-as-mcu.md`; it is
recorded here rather than silently renumbered, and that pair also needs an
operator decision.

- `ADR-001-tollgate-over-lr2021.md` — TollGate Balloon Uses LR2021 Radio as Data Link (own Status: Proposed)
- `adr-e-hash-relay-DECISIONS.md` — ADR: E-Hash Relay Transport — LOCKED DECISIONS LOG (own Status: UNKNOWN)

