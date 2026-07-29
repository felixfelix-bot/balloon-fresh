# LoRa Sweep Progress — 2026-07-23

## Status: Phase 2 Firmware Ready, ESP32 Bridge Recovery Needed

### Phase 1: FLRC — COMPLETE (committed + pushed)

| Bitrate (kbps) | Packets RX | Sustained (kbps) | % of Theoretical | RSSI (dBm) | PER |
|----------------|-----------|-------------------|-------------------|------------|-----|
| 2600           | 21,923    | 1484.9            | 57.1%             | -71.0      | 0%  |
| 1300           | 11,906    | 806.4             | 62.0%             | -71.3      | 0%  |
| 650            | 6,203     | 420.1             | 64.6%             | -73.2      | 0%  |
| 325            | 3,543     | 240.0             | 73.8%             | -73.1      | 0%  |

### Phase 2: LoRa — Firmware Built, Blocked on Hardware

**Firmware built and ready:**
- `rp2040-lora-tx-sf7` — auto-start TX, SF7, BW812, 200 packets
- `rp2040-lora-tx-sf9` — auto-start TX, SF9, BW812, 200 packets
- `rp2040-lora-tx-sf12` — auto-start TX, SF12, BW812, 200 packets
- `rp2040-lora-rx` — auto-listen RX (already flashed, verified working)

**LoRa firmware verified alive via UART bridge:**
- TX: radioReady=1, SF7, BW812, CR=4/5
- RX: auto-listening, window 81+, 30s windows with 5s silence timeout

### Blocker: ESP32 TX Bridge WDT Crash Loop

The ESP32 UART bridge at ACM0 (controlling F242D/TX board) entered a watchdog timer crash loop from repeated pyserial open/close cycles during testing. Recovery attempts:
- `usbreset` — resets but WDT fires again immediately
- `esptool --after hard-reset run` — same result
- Raw serial write — hangs (port occupied by crash loop)

**Fix: Physical USB reconnect of the ESP32 at ACM0.** After reconnect:
1. Send `BOOTSEL` via ACM0 to put F242D in bootloader mode
2. `sudo picotool load .pio/build/rp2040-lora-tx-sf7/firmware.elf -x`
3. TX auto-starts in 3s, sends 200 packets at SF7/BW812
4. Read results from ACM2 (RX bridge — stable)
5. Repeat for SF9, SF12

### Key Learnings

1. **ESP32 bridges crash from rapid serial cycling** — WDT timeout from repeated pyserial open/close. Use persistent connections with `dsrdtr=False`.
2. **RP2040 USB CDC output unreliable** with earlephilhower core on this hardware. Input works (Serial.available + readString), output doesn't (no Serial.print output). UART bridges (GP12/GP13 via ESP32) are the only reliable serial path.
3. **Auto-start firmware is mandatory for sweeps** — eliminates serial command dependency entirely. TX starts 3s after boot.
4. **LoRa init works** — SET_PACKET_TYPE(0x00), SET_RX_PATH(HF), CALIB_FRONT_END, CALIBRATE(0x5F) all confirmed working. radioReady=1.
5. **FIFO offset bug** (reads from offset ~72 not 0) present in all RX firmware variants. Masked by PER-only measurement. Does not affect packet count or RSSI.
6. **40MHz SPI corrupts FIFO writes** — reverted to 20MHz (hard ceiling for LR2021 on RP2040).
7. **Multipath cannot cause duplicates** at these timescales — 33ns path delay vs 680us packet spacing = 20,000x gap. Multipath causes fading/loss, not duplicates.

### Test Configuration

- Frequency: 2440 MHz (2.4 GHz)
- Packet size: 127 bytes (LoRa) / 255 bytes (FLRC)
- TX power: 12 dBm
- TX board: F242D (RP2040 #2, serial E663B035977F242D)
- RX board: 8332 (RP2040 #1, serial E663B035973B8332)
- ESP32 bridges: ACM0→F242D (TX), ACM2→8332 (RX)
- SPI: 20 MHz
- Protocol: raw 2-byte opcode SPI (ADR-020, no RadioLib)

### Commits This Branch

- `1092c3f` — fix: revert 40MHz SPI to 20MHz (corrupts FIFO), tune cont-rx debug
- `21f1169` — feat: infinite TX + cont-rx hex debug, sequential seq confirmed
- `73e1eb4` — feat: cont-rx firmware + 4 platformio envs
- `2fe99c0` — feat: 40MHz SPI overclock — TX 1753→1925 kbps (+9.7%) (since reverted)
- `647bf90` — fix: RX SPI IRQ polling + 255-byte pkt match, 0% PER 1492 kbps verified
- `994ebb8` — docs: reframe sustained throughput sweep as binary-step methodology
