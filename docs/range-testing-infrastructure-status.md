# Range Testing Track — Infrastructure Status (2026-07-16)

## Board Access Mutex

**Script:** `tools/balloon-board-lock.py` (in main repo)
**Lock files:** `~/.hermes/peripheral_locks/balloon-{tx,rx}.lock`
**Stale timeout:** 15 minutes (auto-release if holder crashed)

### Usage

```bash
# Acquire both boards for coordinated TX/RX test
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py acquire both \
    --purpose "baseline verification at 1m" --timeout 120

# Acquire single board
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py acquire tx \
    --purpose "flash configurable firmware" --timeout 120

# Release
BALLOON_TRACK=range-testing python3 tools/balloon-board-lock.py release both

# Check who holds what
python3 tools/balloon-board-lock.py status
```

**RULE:** Always acquire before touching boards. Always release after.

---

## Hardware

| Board | Serial | Chipset | Current Port | Role |
|-------|--------|---------|--------------|------|
| RP2040 + LR2021 | E663B035977F242D | NiceRF LoRa2021 Gen 4 | /dev/ttyACM0 | TX |
| RP2040 + LR2021 | E663B035973B8332 | NiceRF LoRa2021 Gen 4 | /dev/ttyACM3 | RX |

- 2x ESP32-C3 on /dev/ttyACM1, /dev/ttyACM2 — speed track, do not touch
- Ports SWAP after every BOOTSEL flash — always re-discover with `udevadm info -q property /dev/ttyACMX | grep SERIAL_SHORT`
- USB CDC requires DTR assertion (pyserial `s.dtr = True`) or firmware `delay(2000)`

### Board Discovery Command

```bash
for d in /dev/ttyACM*; do
  serial=$(udevadm info -q property $d 2>/dev/null | grep SERIAL_SHORT | cut -d= -f2)
  echo "$d → $serial"
done
```

---

## Proven Baseline

| Parameter | Value | Source |
|-----------|-------|--------|
| Frequency | 2440 MHz | Commit dceb6e5 |
| Modulation | FLRC 2600 kbps | RadioLib beginFLRC() |
| TX power | +12 dBm (0x0C) | Firmware default |
| Packet size | 255 bytes | Test firmware |
| Sync word | 0x12AD101B | TX/RX matched |
| TX throughput | 1377 kbps | Measured (54% of air rate) |
| RX packet loss | 0% at <1m | Measured |
| Packets tested | 1000 TX / 1000 RX | Coordinated test |

---

## Working Firmware

| File | PlatformIO Env | Purpose |
|------|---------------|---------|
| `firmware/rp2040/src/flrc_raw_tx.cpp` | `rp2040-flrc-tx-raw` | TX baseline (1377 kbps) |
| `firmware/rp2040/src/flrc_rx_raw.cpp` | `rp2040-flrc-rx-raw` | RX baseline (0% loss) |

### Build & Flash

```bash
cd ~/worktrees/track-range-testing/firmware/rp2040
pio run -e rp2040-flrc-tx-raw    # Build TX
pio run -e rp2040-flrc-rx-raw    # Build RX
pio run -e rp2040-flrc-tx-raw -t upload --upload-port /dev/ttyACM3
pio run -e rp2040-flrc-rx-raw -t upload --upload-port /dev/ttyACM0
```

### Test Harness

`scripts/coordinated_tx_rx_test.py` — Arms RX first (sends "RUN"), waits 2s,
triggers TX, captures 15s of serial from both boards, saves to
`/tmp/coordinated_results.txt`.

---

## What Failed (5 approaches, tested on real hardware)

### 1. Pico SDK spi_write_blocking (batch transfer)
- **Symptom:** Fake TX_DONE (spin=0), 8160 kbps reported (exceeds air rate 3x), 0 RX packets
- **Root cause:** Different FIFO management violates LR2021 SPI timing requirements
- **Lesson:** Only per-byte Arduino `transfer()` works with LR2021

### 2. DMA via spi0_hw->dr
- **Symptom:** Radio init fails (Status=0x00, IRQ=0x21000200)
- **Root cause:** Bypasses Arduino SPI transaction protocol
- **Lesson:** No direct hardware register access for SPI

### 3. Direct HW SPI register writes
- **Symptom:** 7034 kbps reported (fake), radio never transmits
- **Root cause:** Same as DMA — direct register access incompatible
- **Lesson:** Arduino `transfer()` is the ONLY working SPI path

### 4. Runtime SPI clock change (spi_deinit + spi_init)
- **Symptom:** All subsequent TX bursts produce fake results, radio never re-syncs
- **Root cause:** spi_deinit tears down SPI peripheral, LR2021 requires full RST pin toggle
- **Lesson:** SPI clock must be compile-time constant, never change at runtime

### 5. 20 MHz RX SPI
- **Symptom:** 231/1000 packets received, 77% packet loss
- **Root cause:** RX FIFO read timing requires slower SPI than TX
- **Lesson:** RX SPI must stay at 16 MHz (12 MHz actual)

---

## Key Technical Facts

### RP2040 SPI Clock Reality
- System clock: 125 MHz
- Pico SDK caps all SPI requests >=12 MHz to 12 MHz actual (prescaler limitation)
- "16 MHz" and "20 MHz" firmware both run at 12 MHz actual — difference is noise
- SPI clock is NOT the throughput bottleneck

### LR2021 IRQ Behavior
- DIO9 fires on ALL enabled IRQ bits, not just TX_DONE
- IRQ status 0x000A080A = TX_FIFO (bit 1) + TX_TIMESTAMP (bit 3) + PA_OCP_OVP (bit 11) + TX_DONE (bit 19)
- Works in practice (0% loss) but makes IRQ-based timing measurement unreliable
- BUSY pin (GP6) is ground truth for TX completion

### BOOTSEL Trap
- 1200 baud touch on serial port triggers RP2040 BOOTSEL mode
- Do not use 1200 baud accidentally
- Makefile targets exist: `make bootsel-tx PORT=/dev/ttyACMX`

### Per-Packet Time Breakdown (1377 kbps, 1492 us total)
| Component | Time | % | Reducible? |
|-----------|------|---|------------|
| RF air time | 803 us | 54% | No — physics |
| SPI per-byte transfer x 268 bytes | 535 us | 36% | No — only Arduino works |
| IRQ polling + loop overhead | 154 us | 10% | Partially |

---

## What Still Needs To Be Done

### High Priority
1. **Configurable TX firmware** — serial commands (POWER, PKTLEN, FREQ, COUNT, RUN) to avoid reflashing between test points
2. **Baseline verification** — confirm boards still work after transport/reconnection
3. **Distance sweep** — 10m, 25m, 50m, 100m outdoor LOS

### Medium Priority
4. TX power sweep (0, 3, 6, 9, 12, 12.5 dBm)
5. Packet size sweep (16, 32, 64, 128, 255 bytes)
6. RSSI readback firmware (if LR2021 supports it)

### Future
7. FLRC vs LoRa modulation comparison
8. Antenna configuration sweep (PCB trace vs wire dipole vs PCB Yagi)
9. Frequency channel sweep (2400-2480 MHz, correlate with WiFi)
10. EBYTE E28-2G4M27S (+27 dBm PA) integration — not yet wired up

---

## Test Plan Reference

Full 8-axis sweep plan: `docs/range-test-comprehensive-plan-2026-07-17.md`
Handover doc: `docs/handover-range-testing-2026-07-17.md`

### Data Recording Format

```
RANGE_TEST,date=YYYY-MM-DD,distance_m=X,power_dbm=Y,pkt_size=Z,\
mode=FLRC2600,freq_mhz=2440,antenna=TYPE,orientation=ORIENT,\
packets_sent=N,packets_rx=M,loss_pct=P,throughput_kbps=K,notes=ENV
```

Save to: `docs/range-test-results-YYYY-MM-DD.md`

---

## Commit History (Key Commits)

| Commit | Description |
|--------|-------------|
| dceb6e5 | Coordinated TX/RX verified — 1377 kbps, 0% loss, RF link confirmed |
| a99b64c | TX baseline (1000/1000 TX_DONE) |
| eee6147 | IRQ fix — DIO9 fires on all IRQ bits |
| 8b5385c | Makefile 1200 baud BOOTSEL targets + board identification |
| bd79ed3 | v4 firmware — pure Arduino SPI, proven baseline |
| 8581ec0 | balloon-board-lock.py mutex for cross-session board access |
