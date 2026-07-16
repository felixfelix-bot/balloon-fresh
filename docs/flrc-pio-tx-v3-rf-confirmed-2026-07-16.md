# FLRC PIO TX v3 — RF Output Confirmed, Results Capture Blocked

**Date:** 2026-07-16
**Commits:** fbfe319, 92903f3, ae56e94 (all pushed to GitHub + ngit)

## BREAKTHROUGH: PIO TX v3 Produces Real RF Output

RX board (F242D) received packets from TX board (8332) running PIO TX v3:

```
100,412551800
200,2919153234
```

Format: `received_count,sequence_number` (matching flrc_raw_rx.cpp output format).

**This confirms: PIO+DMA SPI at 20.83 MHz successfully drives the LR2021 radio and produces real RF packets received by the RX board.**

## Issues

### 1. Sequence Numbers Wrong
Expected: 0, 1, 2, 3, ... 999 (big-endian uint32 in pkt[0:4])
Actual: 412551800, 2919153234 — these are garbage/large numbers

Root cause: The PIO SPI transfer may be sending bytes in wrong order (endianness issue in DMA BSWAP), or the packet buffer is being modified by PIO/DMA before transmission. The `pkt[0:4]` bytes set by CPU may arrive at LR2021 FIFO in different order after PIO+DMA transfer.

### 2. TX Throughput Unknown
v3 outputs all TX results to Serial1 (UART GP0/GP1) only — USB CDC is dead during PIO mode. No USB-UART bridge connected to read Serial1. Cannot capture TX_DONE count or throughput.

Previous PIO v1 test (with CDC delay fix) showed 1377 kbps with 1000/1000 TX_DONE — v3 should be similar since the TX hot loop is identical, only output method changed.

### 3. RX Board Silent on CDC
RX board (F242D) produces no USB CDC serial output despite having `delay(2000)` CDC fix. Likely stuck in radio init or CDC died after init. Cannot get full RX statistics (total received, loss %, duplicates).

### 4. Cannot Reflash Without Physical BOOTSEL
Both boards lack USB reset interface in firmware. picotool `reboot -u -f` fails with "Unable to locate reset interface." DTR/RTS doesn't trigger BOOTSEL (no wiring). Need physical BOOTSEL button press.

## What We Know

| Metric | Value | Source |
|--------|-------|--------|
| PIO TX v3 RF output | CONFIRMED | RX received packets 100, 200 |
| TX_DONE count | Unknown | UART-only output, no bridge |
| TX throughput | ~1377 kbps (est) | Based on PIO v1 result |
| RX packets received | At least 200 | RX output captured |
| RX total/loss | Unknown | RX CDC silent |
| Sequence numbers | Wrong (garbage) | Endianness in PIO+DMA transfer |

## Architecture Summary

PIO TX v3:
1. Arduino SPI for radio init (CDC-safe) ✓
2. 8-second WAIT window (CDC alive) ✓
3. `spiRf.end()` releases Arduino SPI ✓
4. PIO+DMA init (CDC survives) ✓
5. TX loop with PIO+DMA at 20.83 MHz (UART-only output) ✓
6. RF output confirmed by RX reception ✓
7. CDC dead during TX loop (expected) ✓

## Next Steps

1. **Physical BOOTSEL** — press BOOTSEL on both boards to reflash:
   - TX: Flash v3 with deferred printing (pioSpiStop + Serial.print after TX)
   - RX: Flash fresh flrc_raw_rx.cpp
2. **Fix sequence number endianness** — investigate PIO+DMA BSWAP setting, may need to disable BSWAP or adjust byte order in packet buffer
3. **Run full TX+RX test** — capture both serials simultaneously
4. **Alternative: Add USB reset interface** — add `#include "pico/bootrom.h"` and `reboot_into_bootsel()` command to firmware for remote BOOTSEL trigger

## Flash Method (when BOOTSEL available)

```bash
# TX board (8332):
PICOTOOL=~/.platformio/packages/tool-picotool-rp2040-earlephilhower/picotool
sudo $PICOTOOL reboot -u -f --ser E663B035973B8332  # If reset iface available
# OR physical BOOTSEL → mass storage → UF2 copy
sudo mount /dev/sdX1 /mnt
sudo cp ~/repos/balloon-fresh/firmware/rp2040/.pio/build/rp2040-pio-tx-v3/firmware.uf2 /mnt/
sync && sudo umount /mnt

# RX board (F242D):
cd ~/repos/balloon-fresh/firmware/rp2040
pio run -e rp2040-raw-rx
# Physical BOOTSEL → UF2 copy
sudo cp .pio/build/rp2040-raw-rx/firmware.uf2 /mnt/
```