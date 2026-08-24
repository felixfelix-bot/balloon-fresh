# Pico-Balloon Tracker & E80 Range Test Bench

Ultralight (<15 g) pico-balloon tracker (ESP32-C3 + Semtech LR2021) with a
dedicated **E80-STM32 bench firmware** for distributed LoRa/FLRC range
testing.  Two boards, two laptops, one `make` command each — that's all
it takes to run a full PER / RSSI / SNR sweep.

---

## ⚡ Getting Started

```bash
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh/firmware/e80-stm32-bench
git checkout feat/2g4-sweep

# One-time: flash the board (needs both USB cables connected)
make flash

# On the TX machine:
make tx

# On the RX machine (within 4 minutes of `make tx`):
make rx

# After both finish, merge logs:
make range-merge RX=rx-log.csv TX=tx-log.csv
```

**That's it.** The system auto-detects serial ports, computes a synchronised
start time (T0), beeps a countdown, and writes results to CSV.

> **Want the minimal package?** Download the pre-built
> [range-test ZIP](../../releases) — contains only the files you need to
> flash + run TX/RX. See [Part 4](#4-minimal-range-test-zip) below.

---

## 📋 Table of Contents

| # | Section |
|---|---------|
| 1 | [What is this repo?](#1-what-is-this-repo) |
| 2 | [Hardware Requirements](#2-hardware-requirements) |
| 3 | [Quick Start (Linux / macOS / Windows)](#3-quick-start) |
| 4 | [Minimal Range-Test ZIP](#4-minimal-range-test-zip) |
| 5 | [Repository Structure](#5-repository-structure) |
| 6 | [Key Documentation](#6-key-documentation) |
| 7 | [Tools Reference](#7-tools-reference) |
| 8 | [Config Presets](#8-config-presets) |
| 9 | [Development & Testing](#9-development--testing) |
| 10 | [Hardware](#10-hardware) |

---

## 1. What is this repo?

This repository hosts **two related projects**:

1. **Pico-Balloon Tracker** — An ESP32-C3 + Semtech LR2021 ultra-light
   balloon tracker (<15 g) with multi-band LoRa (2.4 GHz + Sub-GHz), FLRC
   high-speed mode, 3D PCB-Yagi antenna array, solar/supercap power, and
   BMP280 sensing.

2. **E80 Range Test Bench** — A STM32F103C8T6 based firmware (`firmware/e80-stm32-bench/`)
   for the E80-900MBL-02 board, used for distributed LoRa/FLRC range
   testing.  Measures PER, RSSI, SNR, and bit error rate across modulation
   schemes at various distances.  Two boards act as TX/RX, each connected
   to a separate computer.  Role is set at runtime — boards are
   interchangeable.

---

## 2. Hardware Requirements

| Item | Qty | Notes |
|------|-----|-------|
| E80-900MBL-02 board | 2 | One per machine. Boards are interchangeable (TX/RX is software-selected). |
| Computer (laptop/mini PC) | 2 | One per board. Linux, macOS, or Windows. |
| USB cables | 2 per board | CH340 USB-serial (data) + CMSIS-DAP/Pico SWD probe (debug). Both required. |
| Phone with GPS | 1 (opt.) | For distance measurement. Any app that exports GPX/KML. |

### E80 Board Anatomy

- **STM32F103C8** — microcontroller (64 KB flash / 20 KB RAM)
- **LR2021** — Semtech LoRa Gen 4 radio (supports LoRa + FLRC)
- **CH340** — USB-serial chip for host communication
- **Raspberry Pi Pico** (CMSIS-DAP) — SWD probe for flashing + board reset

### Pico-Balloon Hardware

| Component | Spec |
|-----------|------|
| MCU | ESP32-C3 (ESP-C3-12F / XIAO ESP32C3) |
| LoRa | Semtech LR2021 (Gen 4) / LR1121 (Gen 3 alt.) |
| PA/LNA | Skyworks SKY66112-11 (+22 dBm TX, +14 dB LNA RX) |
| Antennas | 4× PCB-Yagi + SP4T switch (lighthouse mode) |
| Power | 12× solar cells → BAT54 → 2× 3.3 F supercaps → TPS7A02 LDO |
| Sensor | BMP280 (pressure/temperature) |
| Target weight | <15 g |

---

## 3. Quick Start

### Linux

```bash
# Install toolchain
sudo apt install cmake arm-none-eabi-gcc openocd python3 python3-pip
pip install pyserial

# Clone & build
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh/firmware/e80-stm32-bench
git checkout feat/2g4-sweep

# Add user to dialout group (needed for serial port access)
sudo usermod -aG dialout "$USER"
# Log out and back in, or: newgrp dialout

# Flash firmware (first time only — both USB cables connected)
make flash
```

### macOS

```bash
# Install toolchain
brew install cmake gcc-arm-embedded openocd python3
pip3 install pyserial

# Clone & build
git clone https://github.com/felixfelix-bot/balloon-fresh.git
cd balloon-fresh/firmware/e80-stm32-bench
git checkout feat/2g4-sweep

make flash
```

### Windows

1. Install [STM32CubeIDE](https://www.st.com/en/development-tools/stm32cubeide.html)
   or a standalone `arm-none-eabi-gcc` toolchain.
2. Install [OpenOCD](https://gnutoolchains.com/arm-eabi/openocd/).
3. Install [Python 3](https://www.python.org/downloads/) + `pip install pyserial`.
4. Clone the repo, open a terminal (Git Bash or PowerShell) in
   `firmware/e80-stm32-bench/`.
5. Run `make flash`.

### Running a Test

```bash
# On TX machine:
make tx

# On RX machine (within 4 minutes of make tx):
make rx

# After both finish (either machine):
make range-merge RX=rx-log.csv TX=tx-log.csv
```

> For full instructions including flashing details, serial port detection,
> GPS stitching, and troubleshooting, see the
> **[E80 Range Test Operator Guide](firmware/e80-stm32-bench/docs/RANGE-TEST-GUIDE.md)**.

---

## 4. Minimal Range-Test ZIP

For operators who just want the files needed to flash + run TX/RX without
cloning the whole repo:

**Download:** See [GitHub Releases](../../releases) for `e80-range-test-*.zip`.

**Build your own:**

```bash
cd firmware/e80-stm32-bench
bash tools/create-range-test-zip.sh
# Output: e80-range-test-<sha7>.zip
```

The ZIP contains:

| Path | Description |
|------|-------------|
| `Makefile` | Convenience targets (flash, tx, rx, merge) |
| `CMakeLists.txt` | Firmware build config |
| `cmake/` | Toolchain file (arm-none-eabi) |
| `ld/` | Linker scripts (STM32F103C8) |
| `src/` | Firmware source code |
| `third_party/` | STM32 HAL + Semtech LR2021 driver |
| `tools/e80_bench_ctl.py` | Board controller — TX/RX, PER bench |
| `tools/e80_detect.py` | Auto-detect board serial port |
| `tools/gps_stitch.py` | Stitch GPS track onto RX packet log |
| `tools/merge_csvs.py` | Merge TX + RX logs into PER report |
| `tools/countdown.py` | Countdown timer with beeps |
| `configs/envelope-4cfg-max.json` | Default range test preset (4 configs, max payload) |
| `configs/outdoor-10.json` | Outdoor range test preset (10 pkts per config) |
| `docs/RANGE-TEST-GUIDE.md` | Full operator guide |
| `README-RANGE-TEST.txt` | Quick start card |

---

## 5. Repository Structure

```
balloon-fresh/
├── firmware/
│   ├── e80-stm32-bench/          # E80 STM32 range test firmware
│   │   ├── Makefile              # Flash, tx, rx, merge targets
│   │   ├── CMakeLists.txt        # Firmware build config
│   │   ├── src/                  # Firmware source (bench, radio, console)
│   │   ├── tools/                # Python tools (comms, GPS, CSV, sweep)
│   │   ├── cmake/                # ARM cross-compile toolchain
│   │   ├── ld/                   # STM32 linker scripts
│   │   ├── third_party/          # STM32 HAL + Semtech LR2021 driver
│   │   ├── docs/                 # RANGE-TEST-GUIDE, flashing, timing analysis
│   │   ├── tests/                # Host-side unit tests (C unit + pytest)
│   │   └── FLASHING.md           # Flashing procedures
│   ├── esp32-c3-flrc/            # ESP32-C3 FLRC bench firmware
│   ├── esp32-bootsel-controller/ # ESP32 boot/select controller
│   ├── esp32-uart-bridge/        # UART bridge firmware
│   ├── rp2040-flrc-max/          # RP2040 FLRC tests
│   └── scripts/                  # Build/deploy scripts
├── mesh-stack/                   # ESP-NOW mesh + FLRC bench + LR2021 drivers
├── hardware/                     # PCB design (KiCad), enclosures
├── configs/                      # Range test config presets (JSON)
├── tools/                        # Shared repo-wide tools & scripts
├── docs/                         # Project documentation, ADRs, plans
├── data/                         # Captured test data & analysis
├── tests/                        # Integration tests
├── bom/                          # Bill of materials
├── ansible/                      # Deployment playbooks (range-setup)
├── scripts/                      # Repo-wide automation scripts
└── tracker/                      # Ground station & tracker firmware
```

---

## 6. Key Documentation

| Document | Description |
|----------|-------------|
| **[E80 Range Test Guide](firmware/e80-stm32-bench/docs/RANGE-TEST-GUIDE.md)** | Complete self-contained operator guide — hardware setup, flashing, TX/RX, merge, GPS, troubleshooting |
| [E80 Flashing Guide](firmware/e80-stm32-bench/FLASHING.md) | Detailed flashing procedures (SWD, stm32flash) |
| [Timing Tolerance Analysis](firmware/e80-stm32-bench/docs/timing-tolerance-analysis.md) | T0 sync mechanism analysis |
| [Hardware Integration Findings](firmware/e80-stm32-bench/docs/hardware-integration-findings.md) | Live hardware test results |
| [Operator Quickstart](firmware/e80-stm32-bench/tools/OPERATOR-QUICKSTART.md) | Quick reference for command structure |
| [ADR Index](docs/adr/) | Architecture Decision Records |
| [Hardware Connections](HARDWARE_CONNECTIONS.md) | Board wiring reference |

---

## 7. Tools Reference

| Tool | Location | Purpose |
|------|----------|---------|
| `e80_bench_ctl.py` | `firmware/e80-stm32-bench/tools/` | Main board controller — TX burst, RX arm, PER measurement, sweep runner |
| `e80_detect.py` | `firmware/e80-stm32-bench/tools/` | Auto-detect E80 board role + serial port (handles CH340 port swapping) |
| `gps_stitch.py` | `firmware/e80-stm32-bench/tools/` | Stitch GPS track points onto RX packet log by nearest timestamp |
| `merge_csvs.py` | `firmware/e80-stm32-bench/tools/` | Merge TX + RX logs into PER report (joins on session/config/pkt_idx) |
| `countdown.py` | `firmware/e80-stm32-bench/tools/` | Countdown to T0 with terminal bell beeps |
| `e80_sweep_full.py` | `firmware/e80-stm32-bench/tools/` | Full modulation sweep (FLRC + LoRa at multiple bitrates/SF) |
| `create-range-test-zip.sh` | `firmware/e80-stm32-bench/tools/` | Build minimal ZIP package for range test operators |

---

## 8. Config Presets

Config files live in `configs/` at the repo root:

| File | Description |
|------|-------------|
| `outdoor-10.json` | Outdoor range test — 10 pkts per config, 868 MHz EU SRD |
| `indoor-baseline.json` | Indoor baseline test |

Each JSON config specifies a list of modulation configurations:

```json
{
  "label": "FLRC-650 LEN64",
  "mod": "flrc",
  "br": 650,
  "pa": 10,
  "freq": 868000000,
  "plen": 64,
  "gap": 5000,
  "n_pkts": 10
}
```

Fields: `mod` (flrc/lora), `sf` (LoRa spreading factor), `bw` (bandwidth kHz),
`br` (bitrate kbps), `pa` (TX power dBm), `freq` (Hz), `plen` (payload bytes),
`gap` (inter-packet gap ms), `n_pkts` (packets per config).

---

## 9. Development & Testing

```bash
# Firmware build
cd firmware/e80-stm32-bench
make firmware          # Cross-compile with arm-none-eabi-gcc

# Host unit tests (uses system gcc)
make test-host

# Run pytest suite
cd firmware/e80-stm32-bench/tools
python3 -m pytest ../tests/ -v

# Run a dry-run of the range test (prints schedule, no hardware)
make range-dry-run
```

---

## 10. Hardware

| Directory | Description |
|-----------|-------------|
| `hardware/` | PCB design files (KiCad), enclosure CAD |
| `bom/` | Bill of materials |
| `docs/pcb/` | PCB design documentation |
| `docs/hardware-reference/` | Hardware reference materials |

---

## License

See individual source files and `firmware/e80-stm32-bench/third_party/`
for licensing details. Third-party drivers retain their original licenses
(Semtech BSD, ST BSD-3-Clause).
