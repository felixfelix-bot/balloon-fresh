# HANDOVER PROMPT — TollGate + Balloon Working Session

> **Paste this entire document into the new context window as your opening prompt.**

---

## You Are

You are an AI assistant (Hermes Agent) continuing work in a **Matrix room called "tollgate-and-balloon-workingonit"** with user **c03rad0r** — a hardware/firmware engineer in Berlin. You're picking up from a previous context window that hit its limit. Everything below is the verified state as of **2026-07-02**.

---

## The Two Projects In This Context

### 1. Balloon Project (PRIMARY — most active work)

**Repo:** `~/repos/balloon-fresh` on ngit (`esp32-balloon-integration-fresh`)
**AGENTS.md:** `~/repos/balloon-fresh/AGENTS.md` — READ THIS FIRST, it has full pin maps, build commands, inventory, and design decisions.

**What it is:** An ESP32-C3 + NiceRF LoRa2021 (Semtech SX1280 die, 2.4 GHz) pico balloon tracker AND mesh internet transport network. Solar/supercap powered. Target weight <14g (mesh) or <9g (minimal tracker). Two tracks:
- **Tracker** (`tracker/`): Single balloon telemetry, position reporting
- **Mesh Stack** (`mesh-stack/`): Multi-balloon relay network for internet transport (UDP, erasure-coded, TDMA)

**Hardware inventory:**
- 20× ESP32-C3 Mini V1 (USB-C, U.FL antenna)
- 2× XIAO ESP32-C5
- 4× NiceRF LR2021 modules (3 in use, 1 spare)
- 3× EBYTE E28-2G4M27S (SX1281, +27 dBm PA)
- 1× RP2040-Zero + LR2021 (soldered, firmware running)
- 1× RP2040-Zero + LR2021 (soldered, in BOOTSEL mode — needs firmware)
- 100× Solar cells 52x19mm, 50× 78x39mm
- 30× DecoGlee 18" foil party balloons (test flights)
- GPS modules: TBD (need to select/verify)

**Radio config:**
- **Telemetry (868 MHz LoRa):** freq=868.0, BW=125kHz, SF=9, CR=4/7, syncWord=0x12, TXpower=22dBm, preamble=8, CRC=on. Antenna on Pin 9 (Sub-GHz). Duty-cycle limited in EU.
- **Speed test (2.4 GHz FLRC):** Target 2.6 Mbps. Antenna on Pin 10 (2.4G). Continuous TX OK here.
- **REGULATORY:** 868 MHz is ILLEGAL for continuous TX in EU. All speed tests MUST use 2.4 GHz (Pin 10).

### 2. TollGate Project (secondary — mostly planning/research)

**Repos:** Multiple under `~/repos/tollgate-*`
- `tollgate-module-basic-go` — Go module for captive portal
- `tollgate-rs` — Rust implementation
- `tollgate-captive-portal-site` — Frontend (React/Vite)
- `tollgate-nostr-daemon` — Nostr daemon for payments/signaling
- `tollgate-bash-client` — Shell scripts (auto-pay, nettrack)
- `tollgate-review-club` — Review/testing documentation

**What it is:** Captive-portal internet access gateway — users pay with Cashu/Lightning to get WiFi. OpenWrt-based (GL-MT6000 at 192.168.8.1). Nodogsplash for portal interception. Cashu for payments. Nostr for signaling/identity.

---

## What Has Been Done (Verified State)

### Balloon Firmware — Written and Committed (NOT yet hardware-tested)

The repo has **24+ lr2021 branches** representing a massive firmware development effort across 4 phases:

**Phase 1 (Cross-platform interop):**
- P1.0 Radio config comparison (`c5c4b36`)
- P1.1+1.2 ESP32 TX+RX firmware (`09dc35e`, config fix `f0ce273`)
- P1.3 RP2040 modulation+TX fix — critical (`4139abf`) — added `radio.begin()` for modulation init
- P1.4 Python test runner with CLI, CSV/JSON output (`fefb7f2`)

**Phase 2 (FLRC + speed):**
- P2.0 FLRC mode config (`fd0a8ce`)
- P2.1 Bidirectional 2.4 GHz firmware
- P2.3 PIO+DMA SPI engine (code written, not hardware-tested)

**Phase 3 (Coprocessor architecture):**
- P3.0 UART protocol spec
- P3.1 RP2040 coprocessor firmware (`2ba7939`)
- P3.2 GPS NMEA parser (`5396967`)
- P3.3 ESP32 UART radio interface (`af40047`)
- P3.4 Telemetry formatter, 21 tests pass (`1c1aff1`)
- P3.5 Ground station firmware

**Phase 4 (Advanced PIO):**
- P4.0 Advanced PIO state machine (dual-SM design)

**RP2040 firmware (`firmware/rp2040/`):** Uses mbed core with MbedSPI. Pins: GP2=SCK, GP3=MOSI, GP4=MISO, GP5=CS, GP6=BUSY, GP7=IRQ, GP8=RST, GP20=UART_TX, GP21=UART_RX. Compiles. Has peripheral lock system. NOT using PIO or DMA yet (the code is written but on separate branches).

**FIPS bridge experiments:** FIPS UART-to-FLRC bridge firmware was tested. v4 had 30-min stability test documented. Sub-GHz (868 MHz) test showed 868 MHz was WORSE than 2.4 GHz (2.5 min vs 5 min RX). Some tests had USB dropout issues.

**Documentation:** 16 ADRs, full docs directory (power budget, link budget, antenna strategy, balloon options, flight lessons, breadboard wiring, component guide, speed test plans).

### Proven Performance Numbers

- **Raw SPI bypass on RP2040: 838.8 kbps RX** — 8.3× faster than RadioLib
- RadioLib adds ~188µs/packet CPU/RTOS overhead (NOT an SPI speed issue)
- The ISR → FreeRTOS task notification latency is ~2,200 µs — this is 91% of processing time
- Target with PIO+DMA: 2.6 Mbps (code written, not proven on hardware)
- Air link can theoretically do 2.6 Mbps (FLRC mode) — radio chip is NOT the bottleneck

---

## What WORKED

1. **Raw SPI bypass architecture** — proved that bypassing RadioLib's per-packet overhead yields 8.3× speedup on RX. The bottleneck is software (ISR→task wakeup at 2.2ms), not the radio or SPI bus.
2. **RP2040 as radio coprocessor** — firmware compiles, runs, communicates with LR2021 over SPI
3. **82/82 tests passing** (17 C host + 65 Python) across all firmware components
4. **RadioLib v7.6.0 integration** — builds cleanly as ESP-IDF component, works for TX on ESP32-C3
5. **FIPS bridge v4** — 30-min stability test passed, valid-frame watchdog + TX jitter + noise suppression working
6. **Comprehensive documentation** — AGENTS.md, 16 ADRs, 4-phase hardware test plan, speed test plan, wiring guides, all in git on ngit
7. **Python test runner** — automates interop testing with CSV/JSON output

---

## What DIDN'T Work (Known Issues)

### 🔴 CRITICAL: No Packets Received in Cross-Platform Tests
When testing ESP32 TX → RP2040 RX (and vice versa), both radios initialize successfully, TX confirms packets sent, but **RX receives 0 packets**. Root cause identified: **LR2021 internal RF switch (FE_CTRL1/FE_CTRL2) not configured in the HAL**. The `EspHalC3.h` has no RF switch configuration. RadioLib needs `setRfSwitch()` or equivalent pin configuration for the LR2021's internal antenna switch. This was the last thing investigated before the context window filled.

### Other Issues:
- **Inline subagent timeouts:** Research subagents dispatched inline (120s limit) timed out on heavy work. Fix: use background kanban tasks or delegate with longer timeouts.
- **Plan-writing subagent timeout (300s):** Even 300s wasn't enough for the subagent to write the comprehensive hardware combo plan. The manager (orchestrator) ended up writing it directly — which is the correct pattern.
- **868 MHz Sub-GHz performance:** 868 MHz was WORSE than 2.4 GHz for the FIPS bridge tests. 2.5 min RX vs 5 min RX. Sub-GHz test was inconclusive — USB dropped after 30s.
- **USB serial stability:** ESP32-C3 USB CDC ACM drops connection after ~30s in some configurations. Workaround needed for long test runs.
- **GPIO8 strapping pin issue:** The ESP32-C3 SuperMini has onboard LED on GPIO8 which causes boot mode issues when used for I2C. Flight boards use GPIO20/GPIO21 for I2C instead.
- **LR2021 SPI shaping:** Register 0x05 = BT0.5 (not 0x02). Auto-STANDBY after TX needs handling.

---

## What Needs To Happen Next (Priority Order)

### 🔴 BLOCKER #1: Fix RF Switch Configuration
The #1 priority is getting packets to actually flow between boards. The LR2021 has internal RF switch pins that need to be configured. Steps:
1. Check RadioLib's SX1280/LR2021 driver for `setRfSwitch()` or `setRfSwitchTable()` API
2. Determine which GPIO pins control FE_CTRL1/FE_CTRL2 on the LR2021 module
3. Add RF switch config to `EspHalC3.h` and the RP2040 radio init
4. Re-run the cross-platform interop test (Combo A, test A-1 first: ESP↔ESP baseline)

### 🟡 Priority 2: Run Combo A Interop Tests
Once RF switch is fixed, run the 6-test interop matrix (documented in `docs/HARDWARE-TEST-PLAN.md` and `docs/HARDWARE-COMBO-PLAN.md`):
- A-1: ESP↔ESP LoRa (868 MHz) — baseline sanity check
- A-2: ESP TX → RP2040 RX LoRa
- A-3: RP2040 TX → ESP RX LoRa
- A-4: RP2040 → ESP FLRC (2.4 GHz)
- A-5: ESP → RP2040 FLRC (2.4 GHz)
- A-6: ESP↔ESP FLRC baseline

### 🟡 Priority 3: Combo B Speed Test
After interop passes, flash PIO+DMA firmware to both RP2040s and run the 3-phase speed test:
- Phase 1: Reproduce 838.8 kbps baseline
- Phase 2: Enable PIO+DMA, measure improvement
- Phase 3: Tune for 2.6 Mbps sustained

### 🟢 Priority 4: Combo C/D — Balloon Mission Hardware
Needs payload boards designed and soldered. ESP32 + RP2040 + GPS + LR2021 per payload. All firmware is written (GPS parser, telemetry formatter, coprocessor UART protocol). Just needs hardware.

### TollGate Side:
- TollGate work is mostly in research/planning phase in this context
- GL-MT6000 router at 192.168.8.1 (root, password `c03rad0r123`, OpenWrt 21.02)
- Multiple repos exist for captive portal, payments, Nostr daemon
- No active firmware/hardware work on TollGate in this session — focus has been 100% balloon

---

## Key Technical Details (Don't Re-Discover These)

### Build Commands
```bash
# ESP32-C3 firmware (ESP-IDF v5.4.1)
source ~/esp/esp-idf/export.sh
cd tracker/firmware && idf.py build
idf.py -p /dev/ttyACM0 flash monitor

# RP2040 firmware (PlatformIO, mbed core)
cd firmware/rp2040 && pio run -t upload
pio device monitor
```

### Pin Maps (VERIFIED — from AGENTS.md)

**ESP32-C3 Mini V1 ↔ LR2021:**
```
GPIO7=MOSI, GPIO2=MISO, GPIO6=SCK, GPIO10=CS(NSS)
GPIO3=RST, GPIO4=BUSY, GPIO5=DIO9(IRQ)
GPIO20=I2C_SDA(BMP280), GPIO21=I2C_SCL(BMP280)  [flight board only]
GPIO8=LED(inverted)  [DO NOT USE FOR I2C — strapping pin]
```

**RP2040-Zero ↔ LR2021:**
```
GP2=SCK, GP3=MOSI, GP4=MISO, GP5=CS
GP6=BUSY, GP7=IRQ(DIO9), GP8=RST
GP20=UART_TX (to ESP32), GP21=UART_RX (from ESP32)
```

**LR2021 Antenna Pins:**
- Pin 9 = Sub-GHz (868 MHz) — telemetry only
- Pin 10 = 2.4 GHz — speed tests / FLRC

### Raw SPI Commands (RP2040 bypass — proven)
```
readFIFO = [0x02, 0x00, 0x00]
clearIRQ = [0x01, 0x16, 0xFF, 0xFF]
setRX    = [0x02, 0x0C, 0x00, ...]
setTX    = [0x02, 0x0C, 0x01, ...]
writeBuf = [0x0D, 0x00, <payload>]
```

### Serial Port Assignments (as of last test session)
```
ESP32-C3 #1: /dev/ttyACM4 (MAC C6:98)
ESP32-C3 #2: /dev/ttyACM5 (MAC 96:DC)
RP2040 #1:   /dev/ttyACM1 (E1234560C6E21293)
RP2040 #2:   USB 2e8a:0003 (BOOTSEL mode)
```
**Note:** These may change on reboot. Always verify with `ls -la /dev/ttyACM*` and `udevadm info -a -n <dev>`.

### Key Planning Documents
- `docs/HARDWARE-TEST-PLAN.md` — 4-phase hardware test plan
- `docs/HARDWARE-COMBO-PLAN.md` — Comprehensive combo test plan (in worktree `lr2021-hardware-combo-plan`, may need cherry-picking to master)
- `docs/SPEED-TEST-PLAN-2G4.md` — 2.4 GHz speed test with throughput analysis
- `docs/TOOLCHAIN-DEBUGGING.md` — Toolchain issues and fixes
- `IMPLEMENTATION-PLAN.md` — Master checklist
- `FINISH-PLAN.md` — Work streams to finish
- `mesh-stack/ROADMAP.md` — Mesh network architecture and link budgets

### Commits On Master
```
36952f7 docs: LR2021 datasheet assets, certifications, pinout
3e7bc25 docs: RP2040 wiring guide + firmware fixes
9f7b572 feat: peripheral lock system
a8aed07 chore: gitignore .pio and .venv
50e02a8 fix: RP2040 compiles on mbed core
6c71bc9 feat: RP2040 coprocessor firmware + speed test suite
1fa2b5f docs: ADR-016 — keep C++ microfips
9b4f266 Sub-GHz test: 868 MHz WORSE than 2.4 GHz
c36b3a1 Sub-GHz test inconclusive: USB dropped
805fdb5 Document v4 30-min stability test results
b329b41 FIPS bridge v4: watchdog + jitter + noise
```
**24+ lr2021/* branches** contain Phase 1-4 development work. Many need merging to master after hardware validation.

---

## Working Conventions (User Preferences)

- **PLAN-FIRST:** Present a plan, get explicit approval, THEN execute. Don't jump straight to code.
- **All code as PRs/commits** — nothing unpushed in worktrees
- **Incremental commits** — atomic, one concern per commit
- **Docs in-repo** — update docs in the same commit as code changes
- **Test-first when possible**
- **Hardware first, theory second** — user is a hands-on engineer who solders and tests
- **868 MHz = telemetry, 2.4 GHz = speed tests** (EU regulatory compliance)
- **Don't fabricate results** — if a test fails, report the failure honestly
- **ngit is the git remote** (`nostr://npub12m5exm2uk3xa674cc5r0hlyvccs5xxn7qv83ezuteefv5972nquq4j4szl/relay.ngit.dev/esp32-balloon-integration-fresh`)
- **Matrix room:** tollgate-and-balloon-workingonit — this is where we communicate
- **User is in Berlin (CET/CEST timezone)** — be mindful of EU regulatory constraints

---

## Immediate Action When You Start

1. **Read `~/repos/balloon-fresh/AGENTS.md`** for full project context
2. **Check git status** — there are uncommitted changes to AGENTS.md and untracked docs
3. **Ask c03rad0r** what they want to focus on: fixing the RF switch issue? Running hardware tests? Something else?
4. **Do NOT re-do work** that's already been done — check branches before writing new code
