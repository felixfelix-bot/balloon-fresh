# HANDOVER: Speed Testing Track (2026-07-17)

## For the next context window picking up throughput optimization

This document gives a fresh agent everything needed to continue SPI
speed optimization without reading the full session history.

---

## WHAT YOU'RE DOING

Maximizing SPI throughput between RP2040 and LR2021 radio chip. Current
ceiling: 1377 kbps. Goal: push higher using existing RP2040 hardware.
No FPGA, no platform switch.

## WHAT'S ALREADY DONE

### Proven working (DO NOT BREAK):
- TX: 1377 kbps, 1000/1000 TX_DONE, Arduino per-byte SPI.transfer()
- RX: 0% packet loss, 572µs blind window
- Radio link verified end-to-end (coordinated test)

### What FAILED (and WHY we think so):
All 5 alternative SPI methods failed. But we now have a new hypothesis:

The batch transfer test used TWO separate transfer() calls under one CS:
```cpp
spiRf.transfer(hdr, nullptr, 2);      // SCK runs, then STOPS
spiRf.transfer(data, nullptr, 255);   // SCK restarts
```

`spi_write_blocking()` drains FIFO between calls → SCK discontinuous →
LR2021 may reject this. This was NEVER tested with single combined call.

### What's BUILT but NOT YET TESTED:

1. **SPI timing diagnostic** — `firmware/rp2040/src/flrc_spi_timing_diag.cpp`
   - Builds OK (env `rp2040-spi-timing-diag`)
   - Measures per-byte vs split-batch vs single-batch timing
   - Board F242D is in BOOTSEL (needs reflashing)
   - Type "RUN" over serial to execute tests

## WHAT YOU NEED TO DO

Follow: docs/speed-test-comprehensive-plan-2026-07-17.md

Execution order:
1. Flash timing diagnostic → get exact µs numbers (10 min)
2. Write + flash single-batch TX → test with real radio (30 min)
3. Write + flash dual-core RX → shrink blind window (2-4 hrs)
4. SPI frequency push test (30 min)
5. DMA RX (if single-batch works)

## HARDWARE

| Item | Serial | Role |
|------|--------|------|
| RP2040 board 1 | E663B035973B8332 | TX (usually /dev/ttyACM3) |
| RP2040 board 2 | E663B035977F242D | RX (usually /dev/ttyACM0) |

Port assignments SWAP after BOOTSEL. Always re-discover:
```
for d in /dev/ttyACM*; do echo "$d: $(udevadm info -q property $d | grep SERIAL_SHORT | cut -d= -f2)"; done
```

## KEY DISCOVERY: SINGLE-BATCH HYPOTHESIS

This is the most important thing in this handover. Previous batch SPI
failures may have been caused by SCK discontinuity between two transfer()
calls, NOT by fundamental LR2021 incompatibility with batch mode.

**The fix to test:** Pre-build header+payload into ONE buffer, call
transfer() ONCE:
```cpp
uint8_t cmd[257];  // 2-byte header + 255-byte payload
cmd[0] = 0x00;     // header MSB
cmd[1] = 0x02;     // header LSB (WRITE_TX_FIFO)
memcpy(cmd + 2, payload, 255);
spiRf.transfer(cmd, nullptr, 257);  // ONE call, continuous SCK
```

If this works (TX_DONE=1000/1000), SPI time could drop from 535µs to
~170µs → throughput from 1377 to ~2200 kbps.

## FIRMWARE BUILD + FLASH

```bash
cd ~/repos/balloon-fresh/firmware

# Build
make rp2040-build ENV=rp2040-spi-timing-diag

# Flash (triggers BOOTSEL via 1200 baud)
make rp2040-flash ENV=rp2040-spi-timing-diag PORT=/dev/ttyACM0

# After flash, re-discover ports (they swap!)
```

PlatformIO envs are in `firmware/rp2040/platformio.ini`.

## SPI HELPER FUNCTIONS (CURRENT WORKING VERSION)

From `flrc_raw_tx.cpp` — these are the WORKING per-byte helpers:

```cpp
static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    rfCsHigh();
    spiRf.endTransaction();
}
```

The single-batch version should replace the for-loop with:
```cpp
spiRf.transfer(buf, nullptr, len);
```
But ONLY if header and payload are already in one contiguous buffer.

## PIN ASSIGNMENTS

```
GP2  = SCK (SPI clock)
GP3  = MOSI (Master Out)
GP4  = MISO (Master In)
GP5  = CS (Chip Select)
GP6  = BUSY (radio status)
GP7  = IRQ (packet interrupt / DIO9)
GP8  = RST (radio reset)
GP12 = UART TX (to ESP32 bridge, optional)
GP13 = UART RX
GP14 = Debug trigger (for scope/LA)
GP25 = LED (onboard)
```

## BOTTLENECK BREAKDOWN (per 255-byte packet)

| Component | Time | % | Reducible? |
|-----------|------|---|------------|
| RF air time | 803 µs | 54% | NO (physics) |
| Arduino SPI | 535 µs | 36% | YES (batch/DMA) |
| Loop overhead | 154 µs | 10% | Maybe |

RX blind window: 572 µs (514µs FIFO read + 58µs overhead)
- Reducible to ~100µs via dual-core pipelining

## WHAT NOT TO DO

- Don't attempt PIO state machine SPI — 3 versions failed, CDC dies
- Don't change radio init params — proven sequence, don't touch
- Don't use 1200 baud on serial unless you want BOOTSEL
- Don't use `spi_write_blocking()` directly (bypasses Arduino SPI config)
- Don't forget CDC DTR fix (pyserial dtr=True or firmware delay)
- Don't do range testing — that's the OTHER track
  (see docs/range-test-comprehensive-plan-2026-07-17.md)

## COMMIT EVERYTHING

After each experiment:
```bash
cd ~/repos/balloon-fresh
git add firmware/ docs/
git commit -m "test: single-batch SPI — TX_DONE=X/1000, throughput=Y kbps"
git push github master && git push origin master
```

## LINKS

- Full plan: docs/speed-test-comprehensive-plan-2026-07-17.md
- Master plan: docs/lr2021-dual-track-master-plan-2026-07-17.md
- Other track: docs/range-test-comprehensive-plan-2026-07-17.md
- Bottleneck analysis: docs/lr2021-spi-bottleneck-analysis-2026-07-16.md
- Skill: lr2021-throughput-optimization (load with skill_view)
- Repo: ~/repos/balloon-fresh
