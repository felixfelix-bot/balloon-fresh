# C3 Range Bring-Up — Indoor Sanity — 2026-08-17

Worktree: ~/worktrees/c3-range-bringup (branch feat/c3-range-bringup, off feat/e80-spi-bypass @ 99f7180)
Firmware: mesh-stack/flrc-bench-espidf (RadioLib 7.6.0 LR2021, ESP-IDF v5.4.1)

## Build

- Mode selection: Kconfig `BENCH_MODE` choice (main/Kconfig.projbuild):
  `CONFIG_BENCH_MODE_RANGE_TX=y` / `CONFIG_BENCH_MODE_RANGE_RX=y`.
- sdkconfig.defaults was stale for our purpose (bakes `CONFIG_BENCH_MODE_RAW_RX=y`;
  tracked top-level sdkconfig bakes RAW_TX). Solution: per-build-dir SDKCONFIG +
  overlay fragments (later choice assignment wins):
  - `sdkconfig.range_tx` → CONFIG_BENCH_MODE_RANGE_TX=y
  - `sdkconfig.range_rx` → CONFIG_BENCH_MODE_RANGE_RX=y + CONFIG_RANGE_TEST_GPS=n
- Clean-build commands:
  ```
  idf.py -B build_range_tx -D SDKCONFIG=build_range_tx/sdkconfig -D SDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.range_tx' build
  idf.py -B build_range_rx -D SDKCONFIG=build_range_rx/sdkconfig -D SDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.range_rx' build
  ```
- Binaries (from clean state, both green):
  - build_range_tx/flrc-bench-espidf.bin — 257,504 bytes (0x3EDE0)
  - build_range_rx/flrc-bench-espidf.bin — 260,320 bytes

## Blocking issues found & fixed

1. `main/range_test.cpp`: with `CONFIG_RANGE_TEST_GPS=n` the `#include "gps.h"`
   was compiled out but `gps_data_t` was used unconditionally in the RX path
   (gpsReadCached/printGpsLog/RESULT+PKT lines) → compile error. Fixed with a
   field-compatible local `gps_data_t` stub under `#else` (no renames, GPS stays off;
   zeros flow through all GPS fields — phone GPS covers distance later).
2. `gpio_install_isr_service` double-init (RANGE-TEST-PLAN checklist): already
   guarded in EspHalC3.h (`isrInstalled` flag) — no change needed.
3. GPS component: present in-tree (components/gps), so `REQUIRES gps` in
   main/CMakeLists.txt is satisfied; kept, compiled out at source level via config.

## Hardware anomalies (pre-flash)

- ~17:20 both target boards physically disconnected from USB hub (ports 3-1.3/3-1.4):
  c3-a (96:DC) and c3-b (C6:98) vanished within seconds of each other; a third
  ESP32-C3 (efuse MAC 90:70:69:ab:81:88, unknown board — NOT ours) appeared on
  c3-b's old cable ~1 min later. One E80 (/dev/ttyUSB4, ch341) also dropped.
  Rig was under active human rearrangement (antenna setup per Felix).
- USB serial → port mapping is volatile; board identity verified via
  `esptool --no-stub chip_id` (efuse MAC) before every flash.
- Note: task-context port map (ACM0=c3-a, ACM2=c3-b) was already stale at session
  start (c3-a was on ACM3, bootsel-ctrl board on ACM0). Identity > port.

## Expected decode matrix (design property, verified from range_test.h)

RX scans 13 mode configs; TX transmits 16 windows. Two TX windows have NO
matching RX scan config → expected miss:
- Window 3 `L9W-868` (LoRa SF9 BW500) — RX never scans BW500 on 868.
- Window 12 `F1300C34-868` (FLRC 1300 CR 3/4) — RX scans 1300 only with CR 1/0.
All other 14 windows have an exact scan-config match and should lock via START
sync markers once the 5 s/mode scan rotation lands on the right mode during the
window's sync burst (5 sync pkts × 2 s LoRa / 0.5 s FLRC).

## Flash & sanity results — BLOCKED (hardware absent)

- 17:19 acquired c3-a board lock (mapped to /dev/ttyACM3 by USB serial …96:DC —
  ports had already rotated vs task context).
- 17:20 both target boards disconnected from USB within seconds of each other
  (see anomalies above). Polled for return every 5 s for ~45 min: never came back.
  No USB events at all on their ports after the initial disconnect burst.
- Flash of c3-a (TX) / c3-b (RX) NOT executed. No serial capture possible.
- Everything up to flash is done and verified (builds green, binaries ready):
  - TX: build_range_tx/flrc-bench-espidf.bin (257,504 B) — for c3-a (efuse MAC …96:DC)
  - RX: build_range_rx/flrc-bench-espidf.bin (260,320 B) — for c3-b (efuse MAC …C6:98)
- Ready-to-run tooling in this directory:
  - rx_capture.py  — BoardSerial-based timestamped serial logger (port, outfile, secs)
  - analyze_capture.py — boots/scans/sync-locks/RESULT/PKT/error summarizer
- Resume procedure when boards reappear:
  1. Find ports by USB serial (96:DC → c3-a, C6:98 → c3-b), confirm efuse MAC
     via `esptool --no-stub chip_id`.
  2. `BALLOON_TRACK=range-tests balloon-board-lock.py acquire c3-a` →
     `sudo chmod 666 <port>` (holder-only; hard lock blocks holder too) →
     `idf.py -B build_range_tx -p <port> flash` → release. Repeat for c3-b with
     build_range_rx.
  3. Boards ~1 m apart, antennas on. Start TX first (10 s boot delay), then:
     `python3 rx_capture.py <c3-b port> rx_serial_raw.log 1080`
  4. `python3 analyze_capture.py rx_serial_raw.log` → fill in below.

### Sanity capture (pending)

| Window | Mode | Expected | Observed |
|--------|------|----------|----------|
| 1 L12-868    | LoRa SF12/125 CR5  | decode | pending (boards absent) |
| 2 L9-868     | LoRa SF9/125 CR5   | decode | pending |
| 3 L9W-868    | LoRa SF9/500 CR5   | MISS by design (no BW500 scan entry) | pending |
| 4 L7-868     | LoRa SF7/125 CR5   | decode | pending |
| 5 L9CR7-868  | LoRa SF9/125 CR7   | decode (scan entry is CR5 → likely miss START) | pending |
| 6 L12-2G4    | LoRa SF12/125      | decode | pending |
| 7 L9-2G4     | LoRa SF9/125       | decode | pending |
| 8 L7-2G4     | LoRa SF7/125       | decode | pending |
| 9 F260-868   | FLRC 260 CR1/2     | decode | pending |
| 10 F650-868  | FLRC 650 CR3/4     | decode | pending |
| 11 F1300-868 | FLRC 1300 CR1/0    | decode | pending |
| 12 F1300C34-868 | FLRC 1300 CR3/4 | MISS by design (scan has 1300 only CR1/0) | pending |
| 13 F2600-868 | FLRC 2600 CR1/0    | decode | pending |
| 14 F260-2G4  | FLRC 260 CR1/2     | decode | pending |
| 15 F1300-2G4 | FLRC 1300 CR1/0    | decode | pending |
| 16 F2600-2G4 | FLRC 2600 CR1/0    | decode | pending |

Correction on window 5: scan table HAS no CR7 entry (868 LoRa scans are CR5 only),
so the START sync for L9CR7-868 will not be heard → expected miss as well
(unless a CR5 sync decodes through CR7 — unlikely). Net expected decodes: 13/16
(windows 3, 5, 12 lack matching RX scan configs).

