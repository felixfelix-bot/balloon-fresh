# FLRC TX Throughput Optimization Plan — LR2021 Gen 4

## Division of Labor

### Subagent (delegate_task): Code + Analysis
- Edit firmware source files
- Build firmware (pio run)
- Analyze results from serial output I provide
- Research LR2021 datasheet parameters
- Write progress docs
- Prepare UF2 files for flashing
- Git commit + push

### Manager (me): Hardware Access — SINGLE POINT OF CONTROL
- Trigger BOOTSEL via ESP32 one-shot
- Mount RPI-RP2 volume + copy UF2 + sync + umount
- Read serial with pyserial+DTR (find correct port first)
- Send RUN command to trigger TX
- Capture full serial output
- Hand results to subagent for analysis
- Verify git push succeeded

### Why This Split
- Only ONE process can access /dev/ttyACM* at a time
- BOOTSEL trigger + flash is a physical sequence (ESP32 reflash → mount → copy → umount)
- Multiple agents reading serial simultaneously = garbled output
- Subagents have no access to physical hardware — they can only build code

## Current Proven Baseline
- **TX_DONE: 1000/1000 (100%)**
- **TX THROUGHPUT: 1366.4 kbps**
- **Elapsed: 1493 ms** for 1000 × 255-byte packets
- **Spin count: ~13692** per packet (IRQ poll wait = RF airtime)
- **SPI: 16MHz Arduino (beginTransaction/transfer/endTransaction)**
- **Preamble: 16 symbols, sync word: 4 bytes**
- **Firmware: flrc_raw_tx.cpp v4 (commit a90f546/6e59e98)**

## Theoretical Analysis

### Per-packet breakdown at 2600 kbps FLRC:
- Payload: 255 × 8 / 2600 = **0.785 ms**
- Preamble: 16 sym × 4 bits / 2600 = **0.025 ms**
- Sync word: 4 bytes × 8 / 2600 = **0.012 ms**
- Theoretical min airtime: ~0.822 ms
- Measured airtime: ~**1.49 ms** (13692 spin cycles)
- **Overhead: 0.67 ms/packet** (SPI commands + busy waits + chip processing)
- Theoretical max: 2482 kbps. Current: 1366 kbps = 55%

## Optimization Stages

### Stage 1: Preamble Reduction (16→8 symbols)
**Subagent does:**
- Change `0x0E` → `0x0C` in SET_FLRC_PACKET_PARAMS (TX file)
- Same change in RX file
- Build both: `pio run -e rp2040-raw-tx` + `pio run -e rp2040-flrc-rx-raw`
- Commit (not pushed yet — manager verifies first)

**Manager does:**
- Flash TX firmware to 8332 via BOOTSEL
- Read serial: TX_DONE count + throughput + spin count
- If TX_DONE=1000: flash RX to F242D, run RX, check reception
- If pass: tell subagent to push. If fail: tell subagent to revert.

**Expected:** ~0.012ms/pkt saved. Small but validates the test pipeline.

### Stage 2: 20MHz Direct HW SPI for Hot Loop
**Subagent does:**
- Keep Arduino SPI for init (proven reliable)
- Add direct HW SPI helpers (spiWriteBurst, spiWriteByte, spiDrain)
- Call `spi_set_baudrate(spi0, 20000000)` after `spiRf.begin()`
- Replace hot loop: Arduino transfer() → spi0_hw->dr register writes
- Add `#include <hardware/spi.h>`
- Build. Commit (manager verifies).

**Manager does:**
- Flash to 8332, read serial, record results
- Key check: TX_DONE still 1000/1000? CDC output alive?
- If pass: tell subagent to push. If fail: revert.

**Expected:** 25% faster SPI. SPI overhead ~0.3ms → ~0.24ms. ~50-70 kbps gain.

### Stage 3: Reduce Inter-Packet Dead Time
**Subagent does:**
- Profile current 3 CS assertions per packet:
  1. CLR_IRQ: rfWaitBusy + CS toggle + 6 bytes
  2. WRITE_FIFO: rfWaitBusy + CS toggle + 257 bytes
  3. SET_TX: rfWaitBusy + CS toggle + 5 bytes
- Try removing rfWaitBusy before WRITE_FIFO (chip already idle from CLR_IRQ)
- Try removing rfWaitBusy before SET_TX (FIFO write just completed)
- Build. Commit.

**Manager does:**
- Flash, read, record. One rfWaitBusy removal per test.
- If TX_DONE drops: revert that specific removal, keep what works.

**Expected:** ~0.1-0.2ms/pkt saved. ~70-140 kbps gain.

### Stage 4: FLRC Bitrate Increase
**Subagent does:**
- Research LR2021/SX1281 datasheet for FLRC bitrate values
- Current: `SET_FLRC_MOD_PARAMS = { 0x02, 0x48, 0x00, 0x25 }` (0x25 = 2600 kbps)
- Find valid higher bitrate values (3200? 5200?)
- Change bitrate param in TX + RX
- Build. Commit.

**Manager does:**
- Flash TX, verify TX_DONE count
- Flash RX, verify reception (higher bitrate = shorter range, need RX check)
- If TX+RX both work: record throughput

**Expected:** Linear gain. 3200 kbps = +23% airtime reduction → ~1680 kbps.

### Stage 5: FIFO Pipelining (after Stage 2 — needs HW SPI)
**Subagent does:**
- Prime first packet to FIFO + SET_TX before loop
- In loop: wait IRQ → immediately write next packet + SET_TX (no rfWaitBusy between)
- Use direct HW SPI (from Stage 2) for pipelined writes
- Build. Commit.

**Manager does:**
- Flash, read, record.
- Critical: TX_DONE must stay 1000/1000. Pipelining broke before (95e9ecf).

**Expected:** Eliminates WRITE_FIFO + SET_TX from critical path. ~0.2ms/pkt.

### Stage 6: Combined Optimization
**Subagent does:**
- Merge all successful stages: preamble=8 + 20MHz HW SPI + reduced dead time + pipelining + higher bitrate
- Build. Commit.

**Manager does:**
- Flash, read, record final throughput
- Flash RX, verify full TX→RX link

**Expected:** Cumulative gains. Target: ≥1500 kbps.

## Execution Flow Per Stage

```
Subagent: edit code → build → commit (local)
    ↓
Manager: git pull → trigger BOOTSEL → flash → read serial → record results
    ↓
    ├─ PASS: tell subagent → push to GitHub + ngit
    └─ FAIL: tell subagent → revert → analyze → try fix
```

## Manager's Hardware Procedure (repeated every test)

```bash
# 1. Check which port is 8332 (TX board)
for dev in /dev/ttyACM*; do
  [ -e "$dev" ] || continue
  serial=$(udevadm info -q property "$dev" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2)
  echo "$dev serial=$serial"
done
# 8332 = E663B035973B8332, F242D = E663B035977F242D

# 2. Trigger BOOTSEL via ESP32 on ACM1
cd ~/repos/balloon-fresh/firmware/esp32-bootsel-controller
pio run -e esp32c3 -t upload --upload-port /dev/ttyACM1
sleep 4
ls /dev/disk/by-label/RPI-RP2  # verify BOOTSEL

# 3. Flash UF2
DEV=$(readlink -f /dev/disk/by-label/RPI-RP2)
sudo mount -o uid=$(id -u),gid=$(id -g) $DEV /tmp/rp2040-flash
rm -f /tmp/rp2040-flash/*.uf2
cp ~/repos/balloon-fresh/firmware/rp2040/.pio/build/rp2040-raw-tx/firmware.uf2 /tmp/rp2040-flash/
sync && sudo umount /tmp/rp2040-flash
sleep 5

# 4. Find 8332 port again (may have changed)
for dev in /dev/ttyACM*; do
  [ -e "$dev" ] || continue
  serial=$(udevadm info -q property "$dev" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2)
  echo "$dev serial=$serial"
done

# 5. Read serial with pyserial+DTR (CRITICAL: cat does NOT work)
/opt/miniconda/bin/python3.13 -c "
import serial, time
s = serial.Serial('/dev/ttyACM0', 115200, timeout=1)  # adjust port
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

## Success Criteria
- ≥1500 kbps = 10% improvement (good)
- ≥1800 kbps = 32% improvement (great)
- ≥2000 kbps = 46% improvement (excellent)

## Key Lessons (from this session)
1. **CDC requires DTR** — `cat` doesn't assert DTR, use pyserial
2. **LR2021 needs CS deassert between different commands** — merging commands in one CS = broken
3. **Port order changes after BOOTSEL** — always check serial numbers
4. **One variable at a time** — every multi-change attempt broke something
5. **RF airtime is the bottleneck** — SPI optimization alone won't break 1400 kbps