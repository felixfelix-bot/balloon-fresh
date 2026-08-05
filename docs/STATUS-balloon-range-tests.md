# STATUS: balloon-range-tests

**Last Updated**: 2026-07-24 (session 4)
**Phase**: Adaptive sweep firmware built. All software done. Ready for outdoor test.

## Current State

### Bugs Fixed (all verified on hardware)
- RX FIFO race (commit 3dcddaf): GPIO IRQ poll replaces SPI poll. 8+ session bug dead.
- RSSI measurement (commit d85b5ea): LR2021 command 0x024B replaces SX1280 0x022A.
- PER calculation (commit 7a3d150): Multi-burst window handling via cumulative DEADBEEF tracking.
- Packet size mismatch (commit 7a3d150): rx-auto 144→127B matching TX.
- Noise floor measurement (commit 7a3d150): Auto at RX boot via RSSI_INST 0x020B.

### New: Adaptive Bitrate Sweep Firmware (commit 7b00ee2)
- GPS time module (gps_time.h/cpp): NMEA parser + PPS interrupt + millis() fallback
- Sweep scheduler (sweep_scheduler.h/cpp): 4-mode state machine, 12-min cycle
- TX sweep (flrc_range_tx_sweep.cpp): Auto-switches bitrate at window boundaries
- RX sweep (flrc_range_rx_sweep.cpp): Re-arms RX after each switch, full RSSI+PER preserved
- Works WITHOUT GPS (millis fallback). Auto-upgrades to UTC sync when GPS soldered.

### Cross-Track Learnings (from speed-tests, commit 80d9f1d)
- FLRC efficiency: 2600 kbps=23%, 325 kbps=60%. Lower bitrate = better throughput efficiency.
- LoRa bugs pre-solved: CR encoding (5 invalid), RSSI/SNR byte swap, BW codes (812kHz=0x0F).
- Runtime bitrate switching UNTESTED — #1 risk for sweep firmware.

### Total Firmware Envs: 14 (all compile clean)
- 9 original (tx-auto, raw-rx-127, rx-auto, 6x bitrate pairs)
- 3 new sweep (tx-sweep, rx-sweep, gps-time-test)
- 2 legacy (raw-rx, raw-rx-20mhz)

## Board Assignments

| Role | Serial | Notes |
|------|--------|-------|
| TX   | E663B035977F242D | F242D. Port swaps on reflash. |
| RX   | E663B035973B8332 | 8332. Port swaps on reflash. |

**ALWAYS verify by serial number. Acquire/release BOTH boards atomically.**

## Verified Performance (Indoor, ~30cm)

| Metric | Value | Notes |
|--------|-------|-------|
| Signal RSSI | -60 dBm | At 12.5 dBm TX power, PA enabled |
| Noise floor | -103 dBm | Measured at boot |
| SNR | 43 dB | Excellent link margin |
| PER | 0% | At 12.5 dBm, 2600 kbps, 127B |
| Throughput | 219 kbps | Continuous RX mode |
| TX rate | 1558 kbps | 500-pkt bursts, 0 timeouts |

## #1 RISK: Runtime Bitrate Switching

Our sweep firmware is the FIRST attempt at runtime FLRC bitrate changes on LR2021.
Speed-tests group avoided this entirely (used compile-time only).
Our approach switches between bursts (not during TX), so CDC death shouldn't apply.
BUT: radio may need full re-init of all registers, not just MOD_PARAMS.

**Verification needed before outdoor test**: Flash sweep firmware, confirm RSSI/PER
differs between bitrate windows at same distance. If identical → switch not working.

## Git State

- Branch: range-tests
- Latest: 80d9f1d (cross-track learnings + test_runner.py)
- All pushed to: ngit + GitHub (felixfelix-bot/balloon-fresh)
- Working tree: clean

## Discovery Sync Log

- **2026-07-30**: circuit-design — clearance-aware routing rewrite + DRC analysis tooling [PROTOCOL, TEST]. Informational. Relevant when custom PCBs arrive: F33 variant (2W PA, +33 dBm) will need separate range characterization vs dev boards. DRC-clean routing = can rule out PCB shorts as RF degradation cause. No action needed now — current boards are RP2040 dev boards.
- **2026-07-30**: balloon-hermes 47-finding batch. 2 actionable: (1) RP2040 SPI baseline 1760kbps at 10.40MHz — confirms SPI ceiling for sweep firmware. (2) 255B optimal payload — our 127B packets are fine for range testing (shorter = better PER at weak signal). 40+ ESP-IDF findings NOT applicable (RP2040 uses raw SPI, not lr2021_transport). No code changes needed.
- **2026-07-30**: circuit-design/hermes — V1+F33 full signal routing (SPI/UART/I2C/RF/PA), DRC tooling. Informational. Relevant when custom PCBs arrive: F33 PA variant needs separate range test. V1 SPI trace quality affects 20MHz signal integrity. No action needed now.
- **2026-07-31**: balloon-hermes — walk test logs + retry script [TEST]. ACTIONABLE for range-tests:
  (1) Walk test data from 2026-07-26/27: FLRC-2600 had 100% PER (TX fw="none" during FLRC phases — TX board not running FLRC firmware). LoRa SF12 received at RSSI -27 close range, GPS 3 sats fix. Lesson: verify BOTH boards run same mode before sweep.
  (2) retry-c3-acquire.sh pattern: poll board-lock status every 90s, acquire when free, then flash+test. Adapting for range-test board acquisition.
  (3) Walk test plots exist (RSSI/PER/throughput vs distance, log-scale). These are reference baseline for outdoor sweep comparison.

- **2026-08-01**: balloon-hermes — P1B.1-FIX: SPI TX debugging for raw FLRC transmission [SPI, RADIO, PROTOCOL]. Commit `822cdf0`. Impact: **NO DATA VALIDITY ISSUE** — the missing `SET_FLRC_PACKET_PARAMS (0x0249)` bug was in the ESP-IDF bench code (`mesh-stack/flrc-bench-espidf/main/esp32_raw_tx.cpp`). Our RP2040 firmware already has `0x0249` in 11+ files. ESP32-C3 bench firmware already has `0x0249` at line 247. Walk test data VALID. ACTIONABLE for technique adoption: TX debugging approach (GPIO CS toggle during RAWTX, FIFO WriteBuffer→ReadBuffer verification, BUSY pin low→high→low transition check, IRQ bit 0 TX-done polling) could improve outdoor sweep reliability — add TX verification to RP2040 firmware to detect silent TX failures.

## Discovery Sync — 2026-08-05 (4 findings from balloon-hermes)

- **GPIO10 collision fix (commit f926dc9)** — `CRITICAL` `ADOPTED`
  - **Assessment**: Adopted via cherry-pick into this track (commit 311913f). LR2021 NSS was on GPIO10 conflicting with the NeoPixel status LED on the same pin. The dual-drive caused an unreliable SPI bus — **previous RSSI data collected before this fix may have been affected by SPI CS contention** (intermittent corruption when LED drive fought NSS). LED now on GPIO18, FEM_TX now on GPIO19 (Kconfig default updated). Firmware `app_main.cpp` confirmed: `#define LED_GPIO 18` with move-comment; `FEM_TX_PIN` Kconfig default = 19.
  - **GPIO audit result**: Searched all `*.py`, `*.c`, `*.cpp`, `*.h` under `tracker/`, `data/`, `tools/` for stale GPIO10 (LED) and GPIO1 (old FEM_TX) references:
    - **Firmware**: ✅ Clean. `app_main.cpp` LED=GPIO18, FEM_TX=GPIO19. LR2021 NSS correctly stays on GPIO10.
    - **GPIO1 / FEM_TX**: ✅ Clean. All GPIO1 references are UART1_RX (GPS), not FEM_TX. No stale FEM_TX-on-GPIO1 found. FEM_TX_PIN is Kconfig-driven (default 19).
    - **STALE — schematic generators**: ⚠️ `tracker/hardware/hub_board/hub_schematic.py` and `hub_schematic_f33.py` still hardcode GPIO10 as the status LED (7 and 6 references respectively). These Python scripts generate KiCad schematics — **not runtime firmware**, so no RSSI impact, but any future board fabrication from these scripts would reintroduce the collision. Should be updated to GPIO18/GPIO19 when these scripts are next used.

- **FLRC fixes + board lock tooling (commit 0292aec)** — `PARTIALLY ADOPTED` `TEST` `TOOLING`
  - **Assessment**: Board lock tooling (hard device lock v3) already in use on this track via `balloon-board-lock.py` — no new adoption needed. FLRC byte alignment fix from earlier sync (commit 9b740aa) already noted in tollgate track's discovery log; our RP2040 firmware already had correct `0x0249` packet params. No additional action needed.

- **secp256k1 smoke test (commit 0829953)** — `INFORMATIONAL` `BUILD`
  - **Assessment**: secp256k1 (libsecp256k1 via nucula wallet submodule) now builds successfully in the tracker ESP-IDF firmware. Not directly relevant to range test methodology (RSSI/PER/distance sweeps). Noted for future: when unified firmware is used for range tests, Nostr identity derivation will be available. No range-test impact.

- **Mesh baseline build verified (commit 8aaa0bb)** — `INFORMATIONAL` `BUILD`
  - **Assessment**: Unified/mesh firmware builds clean on ESP32-S3. Relevant when the orchestrator approves board access for Phase 2 raw ping test — the raw ping methodology may use unified firmware instead of standalone sweep firmware. No action needed until board access is granted.

## Discovery Sync — 2026-08-05 (6 findings from balloon-hermes, batch 2)

- **Integration test plan Phases 2-4 (commit 2cbf7cd)** — `ACTIONABLE` `HARDWARE`
  - **TAGS**: INTEGRATION, HARDWARE-PREP, PCB-GPIO
  - **Assessment**: Phase 2 = two-board raw ping, NO RSSI/distance measurement. Phases 2-4 are benchtop functional validation only. Range-tests scope (outdoor sweeps) NOT covered in integration plan — our track defines separately.
  - **ACTION**: PCB GPIO fix items — must verify jumper wires match fixed pin table (LED=GPIO18, FEM_TX=GPIO19, NSS=GPIO10 exclusively) before any outdoor sweep. ACTIONABLE for hardware prep.

- **radio_task non-blocking loop (commit 4e7722c)** — `NOT APPLICABLE` `FUTURE`
  - **TAGS**: ARCHITECTURE, UNIFIED-FIRMWARE
  - **Assessment**: Cherry-pick CONFLICT — radio_task.cpp doesn't exist in range-tests branch (that's unified firmware only). Our standalone sweep firmware uses different architecture. NOT APPLICABLE to current range-tests code.
  - **ACTION**: Will be relevant when migrating to unified firmware. No action needed now.

- **Signature field in nostr_event_t (commit bc3bd5b)** — `INFORMATIONAL` `PROTOCOL`
  - **TAGS**: NOSTR, SIGNING
  - **Assessment**: Nostr event signing not part of RSSI/distance measurement methodology.
  - **ACTION**: No action needed.

- **Host-side relay pipeline test (commit 4e86174)** — `INFORMATIONAL` `TEST`
  - **TAGS**: RELAY, PROTOCOL-TEST
  - **Assessment**: No-hardware protocol test, not range methodology.
  - **ACTION**: No action needed.

- **SPI timing comparison status (commit b6c2146)** — `INFORMATIONAL` `SPEED-TESTS`
  - **TAGS**: SPI, TIMING, CROSS-TRACK
  - **Assessment**: C3 vs RP2040 SPI timing — relevant to speed-tests track. We already benchmarked SPI in our RP2040 comparison work.
  - **ACTION**: No action needed — already covered in our track.

- **Phase 6 SPI timing plan (commit 4d53713)** — `INFORMATIONAL` `SPEED-TESTS`
  - **TAGS**: SPI, LOGIC-ANALYZER, CROSS-TRACK
  - **Assessment**: Logic analyzer comparison — speed-tests scope.
  - **ACTION**: No action needed.

## Next Steps (Physical — Operator Required)

1. Flash sweep firmware on both boards (rp2040-range-tx-sweep + rp2040-range-rx-sweep)
2. Verify runtime bitrate switching works (indoor smoke test — see SWEEP_SWITCH messages)
3. If switching works: outdoor test, stand at each distance 12 min for full cycle
4. If switching fails: fall back to compile-time bitrate envs (one reflash per bitrate)
5. Solder GPS module when ready (GP0=TX, GP1=RX, GP9=PPS) — zero code changes needed
