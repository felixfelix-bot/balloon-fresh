# FLRC TX Throughput Optimization Plan — LR2021 Gen 4

## Current Proven Baseline
- **TX_DONE: 1000/1000 (100%)**
- **TX THROUGHPUT: 1366.4 kbps**
- **Elapsed: 1493 ms** for 1000 × 255-byte packets
- **Spin count: ~13692** per packet (IRQ poll wait = RF airtime)
- **SPI: 16MHz Arduino (beginTransaction/transfer/endTransaction)**
- **Preamble: 16 symbols, sync word: 4 bytes**
- **Firmware: flrc_raw_tx.cpp v4 (commit a90f546)**

## Theoretical Analysis

### FLRC 2600 kbps bitrate breakdown per 255-byte packet:
- Payload: 255 × 8 / 2600 = **0.785 ms** (pure data)
- Preamble: 16 symbols × 4 bits / 2600 = **0.0246 ms** (16 sym @ FLRC)
- Sync word: 4 bytes × 8 / 2600 = **0.0123 ms**
- Total RF airtime (theoretical min): ~0.822 ms
- Measured airtime: 13692 spin / 9.2 cycles/spin ≈ **1.49 ms**
- **Overhead: 0.67 ms per packet** = SPI commands + busy waits + chip processing

### Theoretical max throughput:
- At 0.822 ms/pkt: 1000 × 255 × 8 / 0.822 = **2482 kbps**
- Current: 1366 kbps = **55% of theoretical max**
- Headroom: ~80% improvement possible if overhead eliminated

## Optimization Stages (test one variable at a time)

### Stage 1: Preamble Reduction (16→8 symbols)
- **TX change:** `0x0E` → `0x0C` in SET_FLRC_PACKET_PARAMS
- **RX change:** Same byte in flrc_raw_rx.cpp
- **Expected gain:** ~0.012 ms/pkt saved (small but measurable across 1000 pkts)
- **Risk:** RX may not sync with shorter preamble at longer range
- **Test:** TX_DONE count + throughput. Then RX reception count.
- **Commit message:** `opt(flrc-tx): preamble 16→8 symbols`

### Stage 2: Sync Word Reduction (4→2 bytes)
- **TX change:** `0x0E` → `0x0C` (preamble byte already changed in Stage 1)
  Actually: sync length is in the same packet_params byte
  `0x4C` = syncTx=1 | syncMatch=1 | fixed=1 | crc=0
  Sync length is controlled by bits in the preamble/sync byte
  Need to check LR2021 datasheet for sync length field
- **Expected gain:** ~0.006 ms/pkt
- **Risk:** RX false sync at shorter sync word
- **Test:** Same as Stage 1

### Stage 3: Direct HW SPI for Hot Loop (20MHz)
- **Change:** Replace Arduino `beginTransaction`/`transfer`/`endTransaction` 
  with direct `spi0_hw->dr` register writes in the TX loop only
- **Keep Arduino SPI for init** (proven reliable for radio init)
- **Use `spi_set_baudrate(spi0, 20000000)`** after `spiRf.begin()` to set 20MHz
- **Expected gain:** 16MHz→20MHz = 25% faster SPI. SPI overhead ~0.3ms → ~0.24ms
- **Risk:** Direct HW SPI may break if Arduino SPI state machine conflicts
- **Test:** TX_DONE + throughput. CDC output (DTR fix already known).
- **Previous attempt:** 95e9ecf tried this but left beginTransaction open (broke TX)
  This time: call beginTransaction once in setup, use HW registers in loop,
  call endTransaction never (or before loop() returns)

### Stage 4: Reduce Inter-Packet Dead Time
Current per-packet sequence:
1. CLR_IRQ: rfWaitBusy + CS LOW + 6 bytes + CS HIGH = ~3 bus cycles
2. WRITE_FIFO: rfWaitBusy + CS LOW + 2 + 255 bytes + CS HIGH = ~130 bus cycles
3. SET_TX: rfWaitBusy + CS LOW + 5 bytes + CS HIGH = ~3 bus cycles
4. Wait IRQ: ~13692 spin cycles

**Optimization:** 
- Move CLR_IRQ to AFTER IRQ detect (already tested — no gain, but cleaner)
- Skip rfWaitBusy before WRITE_FIFO if we just cleared IRQ (chip already idle)
- Skip rfWaitBusy before SET_TX if WRITE_FIFO just completed
- **Expected gain:** ~0.1-0.2ms/pkt by removing 2 busy waits
- **Risk:** Chip not ready → command ignored → TX_DONE=0
- **Test:** Incremental — remove one rfWaitBusy at a time

### Stage 5: FIFO Pipelining (prime next packet during TX)
- **Strategy:** While waiting for TX_DONE IRQ, pre-load next packet into a buffer.
  When IRQ fires, immediately write FIFO + SET_TX without waiting.
- **Previous attempt:** 95e9ecf — broke TX because beginTransaction was left open
- **Correct approach:** Use direct HW SPI for pipelined writes (after Stage 3)
- **Expected gain:** Eliminates WRITE_FIFO + SET_TX time from critical path
- **Risk:** High complexity, chip state management

### Stage 6: Packet Size Reduction (255→128 bytes)
- **Change:** `FLRC_PKT_SIZE` 255→128
- **Both TX + RX must change**
- **Expected:** Each packet airtime halves. But overhead stays same.
  128×8/2600 = 0.394ms payload vs 0.785ms
  With 0.67ms overhead: 128B → (0.394+0.67)ms = 1.064ms/pkt → 963 kbps (WORSE)
- **Conclusion:** Smaller packets = WORSE (overhead dominates). Skip this.
- **Counter:** Try LARGER packets? LR2021 FIFO max = 255 bytes. Already at max.

### Stage 7: FLRC Bitrate Increase (2600→3200 or higher)
- **LR2021 supports higher FLRC bitrates** — need to check datasheet
- Current: `SET_FLRC_MOD_PARAMS = { 0x02, 0x48, 0x00, 0x25 }`
- 0x25 = bitrate field. Check datasheet for higher values.
- **Expected:** Linear throughput gain. 3200 kbps = +23% airtime reduction
- **Risk:** Range/sensitivity decrease at higher bitrate
- **Test:** TX_DONE + RX reception (sensitivity check)

## Test Protocol (for each stage)
1. Edit flrc_raw_tx.cpp (and flrc_raw_rx.cpp if needed)
2. Build: `cd firmware/rp2040 && pio run -e rp2040-raw-tx`
3. Trigger BOOTSEL: `cd firmware/esp32-bootsel-controller && pio run -e esp32c3 -t upload --upload-port /dev/ttyACM1`
4. Flash: mount RPI-RP2, copy UF2, sync, umount
5. Read TX serial (find 8332 port first):
   ```python
   /opt/miniconda/bin/python3.13 -c "
   import serial, time
   s = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
   s.dtr = True; s.rts = True
   time.sleep(0.5)
   s.write(b'RUN\n')
   start = time.time()
   while time.time() - start < 20:
       data = s.read(4096)
       if data:
           print(data.decode('utf-8', errors='replace'), end='', flush=True)
   s.close()
   "
   ```
6. Record: TX_DONE count, timeout count, elapsed ms, throughput kbps, spin count
7. If TX_DONE=1000: commit + push. If TX_DONE<1000: revert, commit failure doc.
8. If TX works: flash RX, run RX, check reception count (link quality)

## Hardware Notes
- 8332 (TX): serial E663B035973B8332 — port varies ACM0/ACM2 after BOOTSEL
- F242D (RX): serial E663B035977F242D — port varies
- ESP32 BOOTSEL controller: ACM1 (serial 70:AF:09:13:21:00)
- Always check serial numbers before reading serial
- CDC requires DTR assertion (pyserial s.dtr=True, not cat)

## Priority Order
1. **Stage 1 (preamble)** — easy, low risk, test RF
2. **Stage 3 (20MHz HW SPI)** — highest expected gain, medium risk
3. **Stage 4 (reduce dead time)** — medium gain, low risk
4. **Stage 7 (higher bitrate)** — highest gain, but needs datasheet check
5. **Stage 5 (pipelining)** — complex, do after Stage 3
6. **Stage 2 (sync word)** — tiny gain, skip unless bored

## Success Criteria
- ≥1500 kbps = 10% improvement (good)
- ≥1800 kbps = 32% improvement (great)
- ≥2000 kbps = 46% improvement (excellent)
- ≥2482 kbps = theoretical max (impossible — overhead exists)