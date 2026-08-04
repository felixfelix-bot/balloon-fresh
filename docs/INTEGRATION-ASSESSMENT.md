# Integration Assessment — balloon-range-tests

**Date:** 2026-08-05
**Assessor:** balloon-hermes orchestrator (delegated)
**Track scope:** Outdoor LR2021 FLRC range testing with adaptive bitrate sweep

---

## Track Scope and Components

Deliver **outdoor range test data** characterizing LR2021 FLRC performance
across bitrates, distances, and environments. Produces the empirical link-budget
data that informs mesh architecture decisions.

**Components:**
- `firmware/rp2040/` — 14 PlatformIO environments (TX/RX at 6 bitrates + sweep variants)
  - `flrc_range_tx_sweep.cpp` — auto-switches bitrate at window boundaries
  - `flrc_range_rx_sweep.cpp` — re-arms RX after each switch, full RSSI+PER
  - `gps_time.h/cpp` — NMEA parser + PPS interrupt + millis() fallback
  - `sweep_scheduler.h/cpp` — 4-mode state machine, 12-min cycle
- `firmware/esp32-c3-flrc/` — ESP32-C3 bench test firmware for RP2040 comparison
- `tools/walk_capture.py` — walk test automation (continuous RX capture)
- `tools/sweep_config.py` — payload sweep config generator (32/64/128/255B)

## What Works (Proven, Tested)

- ✅ **5 critical bugs fixed and verified on hardware:**
  - RX FIFO race (GPIO IRQ poll replaces SPI poll — 8+ session bug dead)
  - RSSI measurement (LR2021 cmd 0x024B replaces SX1280 0x022A)
  - PER calculation (cumulative DEADBEEF tracking, multi-burst window)
  - Packet size mismatch (rx-auto 144→127B matching TX)
  - Noise floor measurement (auto at RX boot via RSSI_INST 0x020B)
- ✅ **Verified indoor performance (~30cm):** -60 dBm RSSI, 43 dB SNR, 0% PER, 219 kbps
- ✅ **Adaptive bitrate sweep firmware** — works without GPS (millis fallback),
     auto-upgrades to UTC sync when GPS soldered
- ✅ **14 firmware environments all compile clean**
- ✅ **Walk test automation** — continuous RX capture script ready
- ✅ **Cross-track learnings adopted** from speed-tests (FLRC efficiency, LoRa bug fixes)

## What Doesn't Work (Blockers)

- ❌ **Runtime bitrate switching UNTESTED** — #1 risk. First attempt at runtime
     FLRC bitrate changes on LR2021. Radio may need full re-init of all
     registers, not just MOD_PARAMS.
- ❌ **No outdoor test data yet** — all measurements are indoor bench (~30cm).
     The entire point of this track is outdoor range characterization.
- ❌ **No GPS hardware soldered** — firmware has GPS support but no physical GPS
     module connected to the RP2040 boards.

## C3 Portability Assessment

**✅ GOOD — firmware is platform-agnostic by design:**

- Primary platform is RP2040 (PIO build), but ESP32-C3 bench firmware exists
  (commit d361cf9) and uses the same raw SPI 2-byte opcode protocol
- Sweep scheduler and GPS time module are pure C++ — portable to ESP-IDF
- Radio driver abstraction is identical between platforms
- No platform-specific dependencies beyond SPI + GPIO

**Concern:** ESP32-C3 has less RAM than RP2040 (258 KB vs 264 KB), but the
sweep firmware's working set is <20 KB. No issue.

## What's Next

1. **Verify runtime bitrate switching** — flash sweep firmware, confirm RSSI/PER
   differs between bitrate windows at same distance. If identical → switch broken.
2. **Outdoor walk test** — execute the walk test procedure with sweep firmware
3. **Solder GPS module** to at least one RP2040 for UTC-timestamped sweep data
4. **Characterize range vs bitrate tradeoff** — the core deliverable
5. **Feed results into mesh link budget** — outdoor data informs ADR-010 (adaptive TX)
