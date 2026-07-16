# Autonomous Operation + ESP32-C3 Testing Plan

**Date:** 2026-07-16
**Status:** PLANNING
**Dependencies:** Configurable firmware (Session 0)

---

# PART 1: AUTONOMOUS OPERATION MODE

## What "autonomous" means

Configure boards via laptop serial, disconnect, attach battery, walk apart,
trigger test via hardware button. Boards run pre-programmed test, log results
to flash. Reconnect to laptop later to dump results.

No computer needed at either end during the actual test.

## The Coordination Problem

The fundamental challenge: TX and RX boards must be time-coordinated without
a serial link between them. RX must be listening before TX starts sending.

### Solution: Countdown Timer + Manual Trigger

```
1. Configure both boards via laptop (power, pktsize, freq, count)
2. Send AUTOSTART 30 to both boards (30-second countdown)
3. Disconnect USB, connect battery
4. RX board: press trigger → enters RX mode immediately → LED steady
5. Walk to TX position (timer still counting down)
6. TX board: timer expires OR press trigger → starts TX burst
7. TX board: LED blinks per 100 packets, solid when done
8. RX board: LED blinks per 100 received, solid when silence detected
```

Alternative: skip the timer, use pure manual trigger:
```
RX: press trigger → LED steady = "listening"
(walk to TX position)
TX: press trigger → LED blinks = "transmitting"
```
This is simpler and more reliable. Timer is backup for long distances
where you can't reach the TX button in time.

## Hardware Requirements

### Power (BOTH BOARDS)

RP2040 Pico + LR2021 power draw:
- TX active: ~100mA (LR2021 PA) + ~20mA (RP2040) = ~120mA
- RX active: ~40mA (LR2021 RX) + ~20mA (RP2040) = ~60mA
- Idle: ~20mA

Options:
1. **USB power bank (RECOMMENDED):** Any 5V/1A bank works. Even 1000mAh
   runs for 8+ hours. $5-10. Connects via standard USB cable. No wiring.
2. **LiPo battery (3.7V):** Connect to Pico VSYS pin (pin 39). Needs
   TP4056 charge module or direct JST connector. Lighter, flight-relevant.
3. **2x AAA (3V):** Marginal — Pico needs 1.8-5.5V on VSYS but LR2021
   needs solid 3.3V. Not recommended.

**Use USB power banks for range testing.** They're reliable, cheap, and
the boards already work with USB power.

### Trigger Button (BOTH BOARDS)

The RP2040 Pico has a BOOTSEL button on the board. But BOOTSEL reboots
into USB mass storage mode — NOT usable as a runtime trigger.

Instead, wire a momentary push button to a free GPIO:

**TX Board:**
```
GP14 → button → GND
(internal pullup enabled, button pulls LOW when pressed)
```

**RX Board:**
```
GP15 → button → GND
(internal pullup enabled, button pulls LOW when pressed)
```

GP14 and GP15 are both free on both boards. Any momentary switch works.
If no button available: use a jumper wire to momentarily touch GND.

### Status LED (ALREADY PRESENT)

Both boards have onboard LED on GP25. Firmware controls it:
- 3 blinks at startup = "configured, ready"
- Solid = active (TX transmitting or RX listening)
- Blink per 100 packets = progress
- 5 fast blinks = test complete
- Continuous slow blink = error (radio init failed, etc.)

## Firmware Changes Needed

### 1. Flash Logging (CRITICAL)

Store test results in RP2040 flash. The earlephilhower Arduino core provides:
- `EEPROM` class (emulates EEPROM in last flash sector, 4KB usable)
- `LittleFS` (filesystem on flash, configurable size)

**Approach: EEPROM emulation (SIMPLEST)**

4KB is enough for ~15 test results as 256-byte structs. For more capacity,
use LittleFS with a larger partition.

```cpp
#include <EEPROM.h>

struct TestResult {
    uint32_t magic;           // 0xDEADBEEF = valid entry
    uint32_t test_id;         // sequential test number
    uint8_t  power_dbm;       // TX power used
    uint16_t pkt_size;        // packet size
    uint16_t freq_mhz;        // frequency
    uint8_t  mode;            // 0=FLRC2600, 1=FLRC1300, etc
    uint16_t packets_sent;    // TX side: sent count
    uint16_t packets_rx;      // RX side: received count
    uint16_t unique_rx;       // unique packets
    uint16_t duplicates;      // duplicate packets
    uint8_t  rssi_min;        // weakest packet RSSI (raw byte)
    uint8_t  rssi_max;        // strongest packet RSSI
    uint8_t  rssi_avg_x2;     // average RSSI × 2 (fixed point)
    uint32_t elapsed_ms;      // total test duration
    uint32_t timestamp;       // millis() at test start
    uint8_t  reserved[32];    // padding for future fields
};  // sizeof = 64 bytes
```

At 64 bytes per result, 4KB EEPROM = 64 test results. Sufficient.

For TX board: log power/pktsize/count/sent/elapsed.
For RX board: log power/pktsize/received/unique/dup/rssi/elapsed.

Commands:
```
LOGDUMP     → Print all stored results as CSV to serial
LOGCLEAR    → Erase all stored results
LOGSTAT     → Show count of stored results, bytes used
```

### 2. Trigger Input (CRITICAL)

```cpp
#define PIN_TRIGGER_TX  14   // GP14 = trigger button (active LOW)
#define PIN_TRIGGER_RX  15   // GP15 = trigger button

pinMode(PIN_TRIGGER_TX, INPUT_PULLUP);
pinMode(PIN_TRIGGER_RX, INPUT_PULLUP);

// Wait for button press (debounced)
bool waitForTrigger(uint32_t timeout_ms) {
    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        if (digitalRead(PIN_TRIGGER) == LOW) {
            delay(50);  // debounce
            return true;
        }
    }
    return false;  // timeout
}
```

### 3. Autonomous Mode State Machine

```
States:
  CONFIG  → Serial connected, accept commands to set parameters
  ARMED   → Serial disconnected (detected via CDC connection check),
            waiting for trigger or timer
  RUNNING → Test in progress
  DONE    → Test complete, results logged, LED showing completion
  SLEEP   → Low power (optional, reduce current draw)

Transition CONFIG → ARMED:
  - User sends AUTOSTART command, or
  - USB CDC disconnects (SerialDTR goes false), or
  - Trigger pressed

Transition ARMED → RUNNING:
  - Trigger button pressed, or
  - Countdown timer expires (if AUTOSTART N was used)

Transition RUNNING → DONE:
  - TX: all packets sent
  - RX: silence for 3 seconds after last packet
```

### 4. RSSI Per-Packet Logging (IMPORTANT FOR RANGE DATA)

The radio driver already has `radio_get_rssi()` in radio.cpp reading
register 0x0AAB. Add this to the RX hot loop:

```cpp
// After successful packet reception:
float rssi = radio_get_rssi();  // returns dBm
stats.rssi_sum += rssi;
stats.rssi_count++;
if (rssi < stats.rssi_min) stats.rssi_min = rssi;
if (rssi > stats.rssi_max) stats.rssi_max = rssi;
```

Note: `radio_get_rssi()` uses a different SPI class (MbedSPI) than the
raw TX/RX firmware (SPIClassRP2040). Need to either:
- Port the RSSI read to the raw SPI functions used by flrc_rx_raw.cpp, or
- Read register 0x0AAB directly via the existing rfReadReg() function

Direct register read (simpler, matches existing code):
```cpp
static uint8_t rfReadRSSI() {
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01);  // READ_REGISTER
    spiRf.transfer(0xAB);  // register address 0x0AAB low byte
    spiRf.transfer(0x0A);  // register address high byte
    uint8_t val = spiRf.transfer(0x00);  // dummy read
    digitalWrite(PIN_CS, HIGH);
    return val;  // RSSI = -(val/2) dBm
}
```

### 5. Configuration Persistence (IMPORTANT)

Currently: parameters are compile-time #defines. For autonomous mode,
parameters must be settable via serial and persist across power cycles.

Store current configuration in EEPROM alongside test results:

```cpp
struct Config {
    uint32_t magic;           // 0xCAFEBABE = valid config
    uint8_t  power_dbm;       // default 12
    uint16_t pkt_size;        // default 255
    uint16_t freq_mhz;        // default 2440
    uint16_t pkt_count;       // default 1000
    uint8_t  mode;            // default 0 (FLRC 2600)
    uint16_t inter_delay_ms;  // default 0 (max rate)
    uint8_t  auto_delay_s;    // default 0 (manual trigger)
};  // 16 bytes, fits in first EEPROM block
```

On boot: load config from EEPROM. If magic != 0xCAFEBABE, write defaults.
On `POWER 12` command: update config in RAM + write to EEPROM.

**WARNING:** SPI frequency MUST stay compile-time. Runtime SPI clock
changes break the radio (proven in Session 0, commit f5170b8 revert).
Only power, pktsize, freq, count, mode are runtime-configurable.

### 6. CDC Disconnect Detection

Detect when USB cable is unplugged to trigger autonomous mode:

```cpp
// earlephilhower core: Serial connected when DTR is asserted
bool isUsbConnected() {
    return Serial && Serial.dtr();  // DTR true = host connected
}

// In main loop:
if (autonomousEnabled && !isUsbConnected()) {
    // USB disconnected → enter ARMED state
    enterArmedState();
}
```

## Full Autonomous Test Protocol

### Setup (at laptop, ~30 seconds)

```bash
# 1. Acquire board mutex
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py acquire both \
    --purpose "configure autonomous test" --timeout 120

# 2. Flash configurable firmware to both boards
cd ~/worktrees/track-range-testing/firmware/rp2040
pio run -e rp2040-config-tx -t upload --upload-port /dev/ttyACM3
pio run -e rp2040-config-rx -t upload --upload-port /dev/ttyACM0

# 3. Configure TX board
python3 scripts/config_board.py --port /dev/ttyACM3 --tx \
    --power 12 --pktlen 255 --freq 2440 --count 1000 --mode FLRC2600

# 4. Configure RX board
python3 scripts/config_board.py --port /dev/ttyACM0 --rx \
    --mode FLRC2600 --freq 2440 --rssi on

# 5. Clear logs on both
python3 scripts/config_board.py --port /dev/ttyACM3 --clearlog
python3 scripts/config_board.py --port /dev/ttyACM0 --clearlog

# 6. Enable autonomous mode
python3 scripts/config_board.py --port /dev/ttyACM3 --autostart 30
python3 scripts/config_board.py --port /dev/ttyACM0 --autostart 30

# 7. Release mutex
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py release both

# 8. Disconnect USB, connect power banks
```

### Field Test (~2 minutes)

```
1. RX board: press trigger button → LED goes solid = listening
2. Walk to distance (with TX board + power bank)
3. TX board: press trigger button → LED blinks = transmitting
4. Wait for TX completion (LED 5 fast blinks, ~2 seconds for 1000 packets)
5. Walk back to RX board → LED 5 fast blinks = received + logged
```

### Data Retrieval (at laptop, ~10 seconds)

```bash
# Acquire mutex
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py acquire both \
    --purpose "dump logs" --timeout 30

# Dump TX results
python3 scripts/config_board.py --port /dev/ttyACM3 --logdump

# Dump RX results
python3 scripts/config_board.py --port /dev/ttyACM0 --logdump

# Release
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py release both
```

## Files To Create

| File | Purpose | Priority |
|------|---------|----------|
| `firmware/rp2040/src/flrc_config_tx.cpp` | Configurable TX with serial commands + trigger + flash log | CRITICAL |
| `firmware/rp2040/src/flrc_config_rx.cpp` | Configurable RX with RSSI + flash log + trigger | CRITICAL |
| `firmware/rp2040/src/flash_log.h` | Flash logging library (EEPROM-based) | CRITICAL |
| `firmware/rp2040/src/flash_log.cpp` | Flash logging implementation | CRITICAL |
| `scripts/config_board.py` | Python tool for serial configuration + log dump | HIGH |
| `scripts/run_autonomous_test.sh` | Shell script automating setup + dump cycle | MEDIUM |

---

# PART 2: ESP32-C3 + LR2021 TESTING

## Why Test ESP32-C3

1. **Flight hardware is ESP32-C3**, not RP2040. Must validate the radio
   works on the actual flight platform.
2. **ESP32 has WiFi** — could enable real-time results relay at the RX
   end without a laptop (future enhancement).
3. **ESP32 firmware already exists** — built by speed track, untested on
   real hardware.
4. **4-way comparison** validates platform independence of the radio link.

## Hardware Setup

### Available Components

- 4x NiceRF LR2021 modules total
- 2x already on RP2040 boards (F242D, 8332)
- 2x spare modules available
- 20x ESP32-C3 Mini V1 (22.52x18mm, USB-C, U.FL antenna connector)

### Wiring: ESP32-C3 Mini V1 + LR2021

Per the breadboard wiring guide (docs/breadboard-wiring-guide.md), the
pin mapping is already defined in AGENTS.md:

```
LR2021 Pin    Function    ESP32-C3 GPIO    Silkscreen
Pin 1         VCC         3.3V             3V3
Pin 2,8,11,12,18  GND    GND              GND
Pin 3         MISO        GPIO2            D2
Pin 4         MOSI        GPIO7            D7
Pin 5         SCK         GPIO6            D6
Pin 6         NSS         GPIO10           D10
Pin 7         BUSY        GPIO4            D4
Pin 14        RST         GPIO3            D3
Pin 15        DIO9(IRQ)   GPIO5            D5
Pin 10        2.4G ANT    Wire dipole      61mm
```

### Antenna for 2.4 GHz

The LR2021 Pin 10 is the 2.4 GHz antenna output. Need a wire dipole:
- Quarter wavelength at 2440 MHz = 30.75mm per element
- Two 31mm wires, bent 180° apart from Pin 10
- OR solder a U.FL pigtail to Pin 10 and use a proper 2.4 GHz antenna

The ESP32-C3 Mini V1 also has its own U.FL connector — but that's for
the ESP32's WiFi radio, NOT the LR2021. Don't confuse them.

### Assembly Options

**Option A: Breadboard (QUICK, recommended for first test)**
- Plug ESP32-C3 Mini V1 on breadboard
- Plug LR2021 module on breadboard (it has 2.54mm pitch pins)
- Jumper wires between them
- 100nF decoupling cap on LR2021 VCC
- Wire dipole soldered to LR2021 Pin 10

**Option B: Solder directly to dev board (COMPACT, for flight testing)**
- Solder LR2021 module directly to ESP32-C3 Mini V1 pads
- Smaller, lighter, flight-relevant
- Harder to change/fix if wiring error

**Use breadboard first.** Validate the link works before soldering.

### Physical Steps (requires hands-on)

1. Get 1x ESP32-C3 Mini V1 + 1x spare LR2021 module
2. Place both on breadboard
3. Wire per pin table above (10 connections: VCC, GND×4, SPI×4, BUSY, IRQ, RST)
4. Add 100nF decoupling cap on VCC
5. Solder 2x 31mm wire dipole to LR2021 Pin 10
6. Verify continuity with multimeter (optional but recommended)
7. Connect USB-C to ESP32-C3 Mini V1

## ESP32-C3 Firmware Status

The speed track built `firmware/esp32-c3-flrc/main/main.cpp` (536 lines).
It includes both TX and RX modes:

- **TX mode (default):** Uses `spi_master` with DMA at 20 MHz. Writes
  TX FIFO + SET_TX in single batch transfer. This is the untested
  approach that could break the RP2040 ceiling.
- **RX mode:** Compile with `-DCONFIG_FLRC_RX`. Reads RX FIFO, counts
  packets, tracks duplicates.

### What The Firmware Does NOT Have Yet

| Feature | Status | Priority |
|---------|--------|----------|
| TX mode | ✅ Written, builds OK, UNTESTED on hardware | Test first |
| RX mode | ✅ Written (compile flag) | Test second |
| RSSI readback | ❌ Not implemented | Add for range testing |
| Configurable params (serial) | ❌ Hardcoded constants | Add for range testing |
| Flash logging | ❌ Not implemented (ESP32 has NVS/flash) | Add later |
| Autonomous trigger | ❌ Not implemented | Add later |
| WiFi results relay | ❌ Not implemented | Future enhancement |

## Test Plan: 4-Way Comparison

### Prerequisites

1. Solder/wire one ESP32-C3 + LR2021 on breadboard
2. Build ESP32 firmware (TX and RX variants)
3. Have both RP2040 boards with proven firmware ready
4. Acquire mutex for all boards

### Test A: RP2040 TX → RP2040 RX (BASELINE — already proven)

- Already done: 1377 kbps, 0% loss, 1000/1000 packets
- Just re-verify at 1m to confirm boards still work
- Log as reference point

### Test B: ESP32 TX → RP2040 RX

1. Flash ESP32 with TX firmware: `idf.py build`
2. Flash RP2040 RX: `pio run -e rp2040-raw-rx -t upload`
3. Arm RX (send "RUN" over serial)
4. Trigger ESP32 TX (it auto-starts 2s after boot)
5. Capture RP2040 RX output
6. Compare: packet count, loss %, throughput

**Expected:** Similar to RP2040 TX (radio is same, SPI speed different but
air rate is the bottleneck at 2600 kbps).

**If FAIL:** Check ESP32 SPI wiring (most common issue), decoupling,
antenna connection, sync word match.

### Test C: RP2040 TX → ESP32 RX

1. Flash ESP32 with RX firmware: `idf.py -DSDKCONFIG=sdkconfig.rx build`
   (or `idf.py -DCONFIG_FLRC_RX=1 build`)
2. Flash RP2040 TX: `pio run -e rp2040-raw-tx -t upload`
3. Boot ESP32 RX first (2s delay built in)
4. Trigger RP2040 TX
5. Capture ESP32 RX output via USB serial monitor
6. Compare results

**Expected:** Similar packet count and loss %.

**If FAIL:** ESP32 RX IRQ handling may be too slow (single core, RTOS
overhead). Check DIO9 IRQ wiring, BUSY pin response.

### Test D: ESP32 TX → ESP32 RX

1. Need TWO ESP32-C3 + LR2021 breadboard setups
2. Flash one as TX, one as RX
3. Run coordinated test
4. Compare all results

**Expected:** May show different throughput characteristics due to ESP32
SPI DMA vs RP2040 per-byte transfer. Throughput could be HIGHER (ESP32
batch transfer) or LOWER (RTOS overhead per packet).

### Comparison Table Template

```
TEST_MATRIX,
date=YYYY-MM-DD,
distance_m=1,
test_id=A,
tx_platform=RP2040,rx_platform=RP2040,
packets_tx=1000,packets_rx=1000,loss_pct=0.0,
throughput_tx_kbps=1377,throughput_rx_kbps=1377,
rssi_avg=-XX,notes=baseline

test_id=B,
tx_platform=ESP32,rx_platform=RP2040,
packets_tx=1000,packets_rx=???,loss_pct=???,
throughput_tx_kbps=???,throughput_rx_kbps=???,
rssi_avg=-XX,notes=esp32_tx_validation

test_id=C,
tx_platform=RP2040,rx_platform=ESP32,
...

test_id=D,
tx_platform=ESP32,rx_platform=ESP32,
...
```

## ESP32 WiFi Interference Test

After validating the 4-way link at 1m, measure WiFi impact:

1. Run Test B (ESP32 TX → RP2040 RX) with ESP32 WiFi OFF
2. Same test with ESP32 WiFi ON, AP mode, no clients connected
3. Same test with ESP32 WiFi ON, phone connected to AP
4. Same test with ESP32 WiFi ON, actively serving HTTP (data relay simulation)

Record packet loss at each WiFi state. If loss increases significantly
with WiFi on, we know WiFi interferes and must be disabled during FLRC
bursts in the field.

**WiFi channel strategy:** Set ESP32 AP to channel 1 (2412 MHz). FLRC
at 2440 MHz should be far enough (28 MHz separation) to avoid overlap.

## ESP32 Firmware Development Tasks

### For Initial Validation (just test what exists)

1. Build the existing firmware as TX
2. Build as RX (check compile flag works)
3. Flash to breadboard ESP32
4. Run Tests B and C

### For Range Testing (needs new code)

4. Add RSSI readback (read register 0x0AAB via ESP32 SPI)
5. Add serial command interface (ESP_LOG input parsing)
6. Add ESP32 flash logging (NVS partition or LittleFS)
7. Add configurable parameters (power, pktsize, freq)

### For WiFi Results Relay (ADVANCED)

8. Start WiFi AP on channel 1
9. HTTP server with JSON endpoint: GET /results → packet stats
10. WebSocket or SSE for real-time packet counter
11. Test WiFi interference (does FLRC work with AP active?)

## Execution Order

### Phase 1: Autonomous Firmware (INDOOR, no hardware changes)

1. Write flash_log.h/cpp (EEPROM-based logging)
2. Write flrc_config_tx.cpp (configurable TX + trigger + logging)
3. Write flrc_config_rx.cpp (configurable RX + RSSI + logging)
4. Write scripts/config_board.py (serial configuration tool)
5. Add PlatformIO envs for configurable firmware
6. Build, flash, test all commands at 1m with laptop connected
7. Test autonomous mode: configure, disconnect, trigger, dump
8. Commit and push

### Phase 2: ESP32 Validation (NEEDS BREADBOARD ASSEMBLY)

1. Assemble ESP32-C3 + LR2021 on breadboard (hands-on)
2. Verify wiring continuity
3. Build ESP32 TX firmware
4. Run Test B: ESP32 TX → RP2040 RX at 1m
5. If pass: build ESP32 RX firmware, run Test C
6. If pass: log results, commit, push
7. If fail: debug ESP32 SPI (check logic analyzer if needed)

### Phase 3: ESP32 Range Features (AFTER VALIDATION)

1. Add RSSI readback to ESP32 firmware
2. Add configurable parameters
3. Run Test D: ESP32 ↔ ESP32
4. WiFi interference test
5. If WiFi relay works: field test with phone-only RX end

## Mutex Coordination

Both phases need board access. ALWAYS use the mutex:

```bash
# For RP2040 boards (our track's boards):
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py acquire both \
    --purpose "flash configurable firmware" --timeout 120

# For ESP32 boards (shared with speed track):
# Check if speed track has a lock on ACM1/ACM2
python3 tools/balloon-board-lock.py status
# If ESP32 boards aren't covered by existing locks, we need to
# coordinate with the speed track on a case-by-case basis
```

The current mutex script covers "tx" and "rx" (the RP2040 boards).
ESP32 boards on ACM1/ACM2 may need additional lock entries if the
speed track is actively using them.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ESP32 SPI wiring error | HIGH | Board won't init radio | Check continuity, use known-good pinout |
| ESP32 TX batch transfer fails (same as RP2040 SDK batch) | MEDIUM | No throughput improvement | Fall back to per-byte SPI (proven on RP2040) |
| WiFi interference makes ESP32 unusable for FLRC | LOW-MEDIUM | Can't use WiFi relay during tests | Disable WiFi during FLRC, relay between bursts |
| Flash wear from repeated logging | LOW | EEPROM sector fails after 100K writes | Use wear leveling, spread across sectors |
| Trigger button wiring error | LOW | Can't start autonomous test | Test trigger in CONFIG mode before field use |
| Battery dies mid-test | LOW | Lose data | Flash logging is persistent — data survives power loss |
| Two agents flash same board simultaneously | MEDIUM | Corrupt firmware | ALWAYS use mutex lock |

## Summary: What Needs To Be Built

### For Autonomous Mode

| Component | Effort | Blocks Outdoor Testing? |
|-----------|--------|------------------------|
| Flash logging library | 2h | YES |
| Configurable TX firmware | 4h | YES |
| Configurable RX firmware (with RSSI) | 4h | YES |
| config_board.py script | 2h | YES |
| Trigger button wiring | 15min | YES (manual trigger only without it) |
| Autonomous state machine | 2h | NO (timer mode is fallback) |

**Total: ~14h of firmware + tooling work before outdoor testing**

### For ESP32 Validation

| Component | Effort | Blocks ESP32 Testing? |
|-----------|--------|-----------------------|
| Breadboard assembly | 30min (hands-on) | YES |
| Build existing ESP32 firmware | 30min | YES |
| Test B (ESP32 TX → RP2040 RX) | 1h | YES |
| Test C (RP2040 TX → ESP32 RX) | 1h | NO (do after B passes) |
| ESP32 RSSI firmware | 2h | NO (after validation) |
| ESP32 WiFi relay | 4h+ | NO (future enhancement) |

**Total: ~3h for initial validation, more for advanced features**
