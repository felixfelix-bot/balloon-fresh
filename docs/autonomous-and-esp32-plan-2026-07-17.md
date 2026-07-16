# Autonomous Range Testing + ESP32-C3 Platform Plan

**Date:** 2026-07-17
**Branch:** track/range-testing
**Depends on:** range-test-comprehensive-plan-v2.md

---

## PART A: AUTONOMOUS MODE — What Needs to Happen

### The Problem

Current setup requires a laptop at the RX end for serial capture. For 100m+
tests, solo work, or flight validation, both boards must run on battery with
no computer. Results logged to flash, dumped later.

### What Must Be Built (5 Components)

#### Component 1: Flash Logging on RP2040

Two storage tiers available:

**EEPROM (for configuration):**
- earlephilhower core provides `EEPROM.begin(size)` / `EEPROM.put()` / `EEPROM.commit()`
- Emulated in flash, ~4KB usable
- Stores: power, pkt_size, freq, mode, count, repeat_count, interval_ms
- Survives power cycle — load on boot
- Template: `EEPROM.put(0, config); EEPROM.commit();`

**LittleFS (for test results):**
- earlephilhower core provides `LittleFS` filesystem
- Capacity: up to ~1MB configurable in platformio.ini via `board_build.littlefs.storage_size`
- Stores structured result records as files
- Wear-leveling handled by LittleFS

**Result record struct (fixed 64 bytes):**
```c
struct RangeResult {
    uint32_t magic;           // 0x524C5453 = "RLTS" (valid record marker)
    uint32_t timestamp_ms;    // millis() at burst start (relative, not wall clock)
    uint16_t power_dbm_x10;   // 120 = 12.0 dBm
    uint16_t pkt_size;        // 255
    uint16_t freq_mhz;        // 2440
    uint8_t  mode;            // 0=FLRC2600, 1=FLRC1300, etc.
    uint8_t  reserved;
    uint32_t packets_sent;    // from TX config
    uint32_t packets_rx;      // actual received
    uint32_t packets_unique;
    uint32_t lost;
    int16_t  rssi_avg_dbm;    // averaged over burst
    int16_t  rssi_min_dbm;
    int16_t  rssi_max_dbm;
    uint32_t elapsed_ms;
    uint8_t  padding[16];     // future use (temp, gps flag, etc.)
    uint16_t crc;             // CRC-16 for data integrity
};
```

At 64 bytes per record, 512KB LittleFS = ~8000 test results stored.

**Logging strategy:**
- TX logs: config used + sent count + elapsed time per burst
- RX logs: received count + RSSI stats + loss pattern summary per burst
- Each burst = one record appended to log file
- File: `/results.bin` (binary records) or `/results.csv` (human-readable)

#### Component 2: Auto-Start TX Firmware (flrc_range_tx_auto.cpp)

Behavior on power-up (no serial connected):

```
POWER ON
  → Load config from EEPROM (or defaults if first boot)
  → LED: slow blink (ready, positioning window)
  → Wait AUTO_START_DELAY seconds (default: 5)
  → LED: fast blink (transmitting)
  → Send packet burst (configurable count, power, freq, mode)
  → Send DEADBEEF end-marker with sent_count
  → Log result to LittleFS
  → LED: solid on (burst complete)
  → If repeat_count > 0: wait interval_ms, repeat
  → Else: idle, LED slow blink, accept serial commands
```

**Serial commands (when laptop connected):**
```
POWER 12          Set TX power
PKTLEN 127        Set packet size
FREQ 2422         Set frequency
COUNT 500         Set packet count
MODE FLRC2600     Set modulation mode
REPEAT 3          Set repeat count (0=once, N=repeat N times)
INTERVAL 5000     Set inter-burst delay in ms
SAVE              Persist current config to EEPROM
RUN               Start transmission now
STATUS            Print current configuration
DUMP              Print all logged results
CLEAR             Erase log
AUTO ON           Enable auto-start on power-up (default)
AUTO OFF          Disable auto-start
HELP              Print command list
```

#### Component 3: Autonomous RX Firmware (flrc_range_rx_auto.cpp)

Behavior on power-up (no serial connected):

```
POWER ON
  → Load config from EEPROM
  → Init radio (same FLRC params as TX)
  → LED: slow blink (listening)
  → Enter continuous RX mode
  → On packet received:
      - Read RSSI
      - Track sequence numbers
      - LED: brief flash
  → On DEADBEEF marker received:
      - Log summary to LittleFS (one RangeResult record)
      - LED: solid on for 2 seconds
      - Re-enter RX mode (wait for next burst)
  → Continuous operation until power removed
```

**RSSI collection:**
- Read RSSI per packet via register 0x0AAB
- Accumulate sum + track min/max during burst
- Store avg/min/max in result record

**Sequence tracking:**
- Track last 64 sequence numbers in a bitmap (for gap analysis)
- Store first_lost_seq + max_gap + burst_loss_count in record

**Serial commands:**
```
RUN                Start/restart RX session
STATUS             Print current config + radio status
DUMP               Print all logged results as CSV
CLEAR              Erase all logged results
RSSI               Read current RSSI (live)
SAVE               Persist config to EEPROM
AUTO ON/OFF        Toggle auto-start on power-up
HELP               Print command list
```

#### Component 4: Time Synchronization

RP2040 has no RTC. millis() resets on power-up.

**Solution: TX and RX both record relative timestamps.**

Each board logs `timestamp_ms` = millis() at burst start. When analyzing data
post-test, match TX and RX records by burst sequence (TX sends burst N, RX
receives burst N). The relative timestamps allow calculating one-way latency
and burst duration. Absolute time is not needed — GPS provides that if required.

**For correlated data:** TX increments a burst_id counter, embeds it in the
DEADBEEF marker packet. RX stores burst_id in its record. Post-test, join TX
and RX records by burst_id.

#### Component 5: Physical Power Setup

**TX board (battery operated):**
- USB battery pack (any 5V output)
- No laptop needed — auto-starts
- LED indicates status: slow blink = ready, fast = transmitting, solid = done
- Power consumption: ~30-50mA (RP2040 + LR2021 TX)

**RX board (battery operated):**
- USB battery pack
- No laptop needed — logs to flash
- LED indicates status: slow blink = listening, flash = packet received, solid = burst complete
- Power consumption: ~20-30mA (RP2040 + LR2021 RX)

**Battery life estimate:**
- 5000mAh battery: ~100-150 hours continuous operation
- Testing sessions: effectively unlimited

### Build Order

| Step | What | Estimated Effort | Blocks |
|------|------|-----------------|--------|
| 1 | Write flrc_range_tx_auto.cpp (config EEPROM + auto-start + LittleFS logging) | 2h | Autonomous TX |
| 2 | Write flrc_range_rx_auto.cpp (RSSI + sequence tracking + LittleFS logging) | 2h | Autonomous RX |
| 3 | Add platformio.ini envs (rp2040-range-tx-auto, rp2040-range-rx-auto) | 15min | Builds |
| 4 | Add board_build.littlefs.storage_size to platformio.ini | 5min | LittleFS |
| 5 | Flash both boards, verify config persists across power cycle | 30min | Autonomous mode |
| 6 | Run battery test: configure via serial, disconnect, power from battery, verify logging | 30min | Validated |
| 7 | DUMP results, verify data integrity | 15min | Done |

**Total: ~6 hours of firmware development + testing**

### Autonomous Test Workflow (After Build)

```
PRE-TEST (at laptop):
  1. Connect TX via USB
  2. Configure: POWER 12, COUNT 1000, FREQ 2440, MODE FLRC2600
  3. SAVE
  4. Disconnect TX from laptop
  5. Connect RX via USB
  6. Confirm RX is in listening mode
  7. Disconnect RX from laptop

FIELD TEST (no laptop):
  8. Connect TX to battery pack → auto-starts in 5 seconds
  9. Position TX at test location
  10. Connect RX to battery pack → enters continuous RX
  11. Position RX at desired distance
  12. Wait for TX burst to complete (~2-3 seconds)
  13. LED on RX goes solid = burst received
  14. Move to next distance, repeat TX burst (if REPEAT > 0)

POST-TEST (back at laptop):
  15. Connect RX via USB
  16. Send DUMP → get all results
  17. Connect TX via USB
  18. Send DUMP → get TX-side logs
  19. Clear both logs
```

---

## PART B: ESP32-C3 + LR2021 TEST PLAN

### Why Test ESP32-C3

1. **Actual flight platform** — balloon tracker uses ESP32-C3, not RP2040
2. **WiFi capability** — could serve real-time results from RX without laptop
3. **Firmware already built** — speed track created it, just needs hardware validation
4. **4-way comparison** — isolates MCU/PCB effects from radio effects

### WiFi Interference Concern

Both ESP32 WiFi and FLRC operate at 2.4 GHz. Active WiFi CAN interfere with FLRC.

**Must measure, not assume.** Test plan includes interference quantification:
- Baseline: FLRC with WiFi OFF
- Interference: FLRC with WiFi ON (AP mode, no clients)
- Worst case: FLRC with WiFi active transfer

### Hardware Preparation

**Required:** Wire 2x spare LR2021 modules to 2x ESP32-C3 Mini V1 boards.

LR2021 → ESP32-C3 pin mapping (from AGENTS.md):

```
NiceRF Pin   Function    ESP32 GPIO
Pin 1        VCC         3V3
Pin 2,8,11,12,18  GND    GND
Pin 3        MISO        GPIO2
Pin 4        MOSI        GPIO7
Pin 5        SCK         GPIO6
Pin 6        NSS         GPIO10
Pin 7        BUSY        GPIO4
Pin 10       2.4G Antenna
Pin 14       RST         GPIO3
Pin 15       DIO9 (IRQ)  GPIO5
```

This is breadboard/jumper-wire work. No PCB fabrication needed for testing.

**WARNING:** The ESP32-C3 Mini V1 dev board has specific constraints:
- GPIO8 and GPIO9 are strapping pins — do NOT use for radio signals
- GPIO4-7 labeled "JTAG" but usable as GPIO when JTAG disabled
- Use SPI2 (HSPI) for the radio, not SPI3 (VSPI) which is shared with flash

### ESP32-C3 Firmware Status

**firmware/esp32-c3-flrc/main/main.cpp** (536 lines):
- TX mode: sends 1000-packet burst via spi_master DMA at 20 MHz
- RX mode: listens, counts packets, prints results (commented out in build)
- Same LR2021 init sequence as RP2040 raw SPI firmware
- Same sync word, frequency, packet params
- IRQ mapping: TX_DONE on DIO9 via bit mapping
- **NEVER TESTED ON HARDWARE** — builds but no bench validation yet

### Validation Phases

#### Phase 1: ESP32-C3 Bench Validation (TX only)

**Goal:** Prove ESP32-C3+LR2021 can transmit FLRC packets.

1. Wire one LR2021 module to one ESP32-C3 board (breadboard/jumpers)
2. Build TX mode: `source ~/esp/esp-idf/export.sh && cd firmware/esp32-c3-flrc && idf.py build`
3. Flash: `idf.py -p /dev/ttyACMX flash monitor`
4. Verify: "Radio init complete" + TX_DONE count > 0
5. Cross-check: Use existing RP2040 RX board to receive ESP32-C3 TX
   - Flash RP2040 RX with current canonical RX firmware
   - Position both at bench distance
   - Run ESP32-C3 TX → RP2040 RX → confirm packets received

**Success criteria:** ESP32-C3 TX → RP2040 RX = packets received with 0% loss at bench

#### Phase 2: ESP32-C3 RX Validation

**Goal:** Prove ESP32-C3+LR2021 can receive FLRC packets.

1. Wire second LR2021 module to second ESP32-C3 board
2. Enable RX mode in ESP32 firmware (uncomment/configure)
3. Flash RX mode
4. Cross-check: RP2040 TX → ESP32-C3 RX
   - Flash RP2040 TX with current canonical TX firmware
   - Run RP2040 TX → ESP32-C3 RX → confirm packets received

**Success criteria:** RP2040 TX → ESP32-C3 RX = packets received with 0% loss at bench

#### Phase 3: ESP32-C3 ↔ ESP32-C3 Link

**Goal:** Prove ESP32-C3 on both ends works.

1. Both ESP32-C3+LR2021 boards, one TX one RX
2. Run ESP32 TX → ESP32 RX → confirm packets received

**Success criteria:** ESP32→ESP32 = 0% loss at bench

#### Phase 4: 4-Way Comparison Matrix

All four combinations tested at bench distance (0.5m) first, then at 10m:

| TX → | RP2040 | ESP32-C3 |
|------|--------|----------|
| RP2040 RX | BASELINE (proven) | Test A |
| ESP32-C3 RX | Test B | Test C |

**Data collected per combination:**
- packets_sent, packets_rx, loss_pct
- RSSI (if available on ESP32-C3 firmware — needs RSSI SPI read added)
- throughput_kbps
- TX_DONE count (TX side)
- Notes: any CRC errors, timing issues, init failures

**Analysis:** If all four show 0% loss at bench and similar RSSI at 10m, the
platform choice (RP2040 vs ESP32-C3) does not affect range. Range depends on
radio chip + antenna, not MCU. Any differences reveal PCB layout or SPI timing
effects.

#### Phase 5: WiFi Interference Measurement

**Goal:** Quantify how much ESP32-C3 WiFi affects FLRC reception.

Use ESP32-C3 RX board at fixed distance from RP2040 TX:

| WiFi State | Test |
|------------|------|
| WiFi OFF | Baseline FLRC reception |
| WiFi AP ON, no clients | AP beacon interference |
| WiFi AP ON, 1 client connected | Active connection interference |
| WiFi STA connected, idle | Client mode interference |
| WiFi STA active transfer | Worst case (HTTP download) |

**Method:**
1. Start with WiFi OFF: `esp_wifi_stop()` before radio init
2. Run 1000-packet burst, record loss + RSSI
3. Enable WiFi AP: `esp_wifi_start()` + `esp_wifi_set_mode(WIFI_MODE_AP)`
4. Run 1000-packet burst, record loss + RSSI
5. Repeat for each WiFi state

**Deliverable:** Interference table — does WiFi kill FLRC or is it tolerable?

**Channel selection strategy:**
If interference is significant, select WiFi channel far from FLRC frequency:
- FLRC at 2440 MHz → use WiFi channel 1 (2412 MHz) or 11 (2462 MHz)
- FLRC at 2480 MHz → use WiFi channel 1 (2412 MHz)
- This frequency separation may reduce interference substantially

#### Phase 6: ESP32-C3 Autonomous Mode (Future)

If ESP32-C3+LR2021 link is validated:

1. Add LittleFS logging to ESP32-C3 firmware (ESP-IDF has SPIFFS/partition support)
2. Add WiFi web server: ESP32-C3 RX serves results page at http://192.168.4.1
3. Phone connects to ESP32-C3 AP, opens browser, sees real-time results
4. No laptop needed at all — phone-only operation

This is the ultimate field-deployable range testing setup:
- ESP32-C3 TX on battery (auto-start)
- ESP32-C3 RX on battery (logs + serves WiFi)
- Phone as display terminal
- GPS from phone

### ESP32-C3 Firmware Changes Needed

| Change | Phase | Description |
|--------|-------|-------------|
| RX mode enable | Phase 2 | Uncomment/configure RX code path in main.cpp |
| RSSI readback | Phase 4 | Add SPI read of register 0x0AAB in RX loop |
| Configurable params | Phase 6 | Accept parameters via serial (like RP2040 configurable TX) |
| WiFi AP + web server | Phase 6 | ESP-IDF HTTP server serving results JSON |
| Flash logging | Phase 6 | SPIFFS partition for result storage |

### ESP32-C3 Build & Flash

```bash
source ~/esp/esp-idf/export.sh
cd ~/worktrees/track-range-testing/firmware/esp32-c3-flrc
idf.py build
idf.py -p /dev/ttyACMX flash monitor
```

### Build Order Summary

| Priority | Task | Blocks |
|----------|------|--------|
| 1 | RP2040 autonomous TX+RX firmware | Extended range tests |
| 2 | RP2040 autonomous validation (battery test) | Confidence in autonomous data |
| 3 | Wire 2x ESP32-C3 + LR2021 (breadboard) | ESP32 validation |
| 4 | ESP32-C3 TX bench validation | ESP32 TX→RP2040 RX cross-test |
| 5 | ESP32-C3 RX bench validation | Full 4-way matrix |
| 6 | 4-way comparison at bench + 10m | Platform comparison data |
| 7 | WiFi interference measurement | ESP32 flight-readiness decision |
| 8 | ESP32-C3 autonomous + WiFi web server | Phone-only field operation |

---

## COORDINATION WITH SPEED TRACK

**Board sharing:** We share the two RP2040+LR2021 boards. Always use mutex:

```bash
export BALLOON_TRACK=range-test
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both \
    --purpose "range test: flash autonomous firmware" --timeout 120
# ... work ...
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
```

**ESP32-C3 boards:** We have 20x ESP32-C3 Mini V1. The speed track uses
ESP32-C3 boards for BOOTSEL control only (GPIO toggling, not SPI). We can use
separate ESP32-C3 boards for LR2021 testing without conflict.

**LR2021 modules:** 4 total. 2 on RP2040 boards (shared). 2 spare for ESP32-C3
wiring. No conflict with speed track.
