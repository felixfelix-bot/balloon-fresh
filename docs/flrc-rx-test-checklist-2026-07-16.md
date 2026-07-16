# FLRC RX Test Checklist — 2026-07-16

**Date:** 2026-07-16  
**Repo:** balloon-fresh  
**Purpose:** Step-by-step checklist for running FLRC RX tests against PIO TX (v3) or v4 baseline TX.

---

## Hardware Setup

| Role | Board  | Device           | Notes                                     |
|------|--------|------------------|-------------------------------------------|
| TX   | F242D  | `/dev/ttyACM0`   | RP2040 + LR1121. If in BOOTSEL, it vanishes. |
| RX   | F242D  | `/dev/ttyACM2`   | If TX is in BOOTSEL, RX may appear at ACM0. |

**Rule:** Check `ls /dev/ttyACM*` before starting. Device assignments shift
when boards are reset or enter BOOTSEL mode.

---

## RX Firmware

- **PlatformIO env:** `rp2040-raw-rx`
- **Source file:** `src/flrc_raw_rx.cpp`
- **CDC fix:** Already includes `delay(2000)` at boot for TinyUSB enumeration.
- **RX mode:** Continuous listen, prints `RX_PKT` lines on received packets.

### Expected RX Output Format

```
RX LISTENING
RX_PKT seq=0 rssi=-45 snr=12
RX_PKT seq=1 rssi=-44 snr=11
RX_PKT seq=2 rssi=-45 snr=12
...
RX_PKT seq=999 rssi=-44 snr=11
RX DONE — total=1000 lost=0 loss_pct=0.00%
```

- **`seq`**: Sequence number from packet payload (0–999 for 1000-packet test).
- **`total`**: Count of packets actually received.
- **`lost`**: Count of missing sequence numbers.
- **`loss_pct`**: lost / 1000 × 100.

---

## TX Firmware Options

| TX Version | Source file | CDC during TX | Throughput | Status |
|------------|-------------|---------------|------------|--------|
| v4 baseline | `src/flrc_tx_v4.cpp` (or equivalent) | Alive | 1367 kbps proven | ✅ Ready |
| PIO v3 | `src/flrc_pio_tx_v3.cpp` | Dead during TX, restored after | Unknown | Awaiting test |

---

## Test Procedure

### Step 1: Verify Board Connections

```bash
ls /dev/ttyACM*
```

- Confirm TX board at `/dev/ttyACM0` (or wherever it is).
- Confirm RX board at `/dev/ttyACM2` (or wherever it is).
- If unsure which is which, reset one and see which device disappears/reappears.

### Step 2: Start RX Serial Capture

```bash
# Use screen, minicom, or stty+cat — pick one:
screen /dev/ttyACM2 115200
# OR
stty -F /dev/ttyACM2 115200 raw -echo && cat /dev/ttyACM2 | tee rx_output.log
```

- **Wait for:** `RX LISTENING` line to appear.
- If no output after 5 seconds, reset the RX board (unplug/replug or press RESET).
- RX firmware has `delay(2000)` — wait at least 3 seconds after reset for CDC to enumerate.

### Step 3: Start TX (Trigger TX Loop)

For **v4 baseline TX:**
```bash
# Open TX serial — the 10-second WAIT window should appear
screen /dev/ttyACM0 115200
# TX starts automatically after the WAIT window expires
# OR press a key if the firmware waits for input
```

For **PIO v3 TX:**
```bash
# Open TX serial — CDC is alive during init + WAIT window
screen /dev/ttyACM0 115200
# After WAIT window, TX loop runs (CDC will die — this is expected)
# After TX completes, CDC restores and results print
```

**Alternative (no serial needed for TX):** If TX firmware auto-starts after
the WAIT window, you don't need to open the TX serial — just let it run.
The TX board will start transmitting after ~10 seconds.

### Step 4: Capture Both Serials Simultaneously

For accurate timing, capture both serials in parallel:

```bash
# Terminal 1 — RX capture
stty -F /dev/ttyACM2 115200 raw -echo
cat /dev/ttyACM2 > rx_capture.log &

# Terminal 2 — TX capture (optional, for TX_DONE count)
stty -F /dev/ttyACM0 115200 raw -echo
cat /dev/ttyACM0 > tx_capture.log &

# Wait for TX to complete (~2-3 seconds for 1000 packets)
# Then kill both cat processes
kill %1 %2
```

### Step 5: Analyse RX Output

```bash
# Check for RX LISTENING
grep "RX LISTENING" rx_capture.log

# Count received packets
grep -c "RX_PKT" rx_capture.log

# Check final summary
grep "RX DONE" rx_capture.log

# Extract sequence numbers to find gaps
grep "RX_PKT" rx_capture.log | sed 's/.*seq=\([0-9]*\).*/\1/' | sort -n > seqs_received.txt
# Find missing sequence numbers
seq 0 999 > seqs_expected.txt
comm -23 seqs_expected.txt seqs_received.txt > seqs_missing.txt
wc -l seqs_missing.txt
```

---

## Verification Criteria

### 1. Packet Loss

- **Acceptable:** 0% loss (1000/1000 received) — matches v4 baseline.
- **Tolerable:** <2% loss (< 20 packets lost) — indicates marginal timing.
- **Failure:** >5% loss (> 50 packets lost) — indicates timing or RF issue.

### 2. Throughput Sanity Check

- **Hard limit:** Throughput must **NOT exceed 2600 kbps** (FLRC air rate).
- If reported throughput > 2600 kbps → **fake TX_DONE** (radio reports done
  before packet actually finishes transmitting).
- Expected range: 1200–1400 kbps (v4 baseline: 1367 kbps).

### 3. RSSI / SNR

- RSSI should be > -60 dBm for boards within 1 meter.
- SNR should be > 8 dB.
- If RSSI < -80 dBm or SNR < 0 → check antenna connections.

### 4. Sequence Continuity

- Sequence numbers should be 0–999 with no gaps for 0% loss.
- Any gaps indicate dropped packets (TX sent but RX didn't capture).
- Duplicates indicate RX firmware bug (same packet processed twice).

---

## Troubleshooting

### RX board produces no output

1. Check `ls /dev/ttyACM*` — board may have enumerated at a different address.
2. Reset RX board — unplug USB, replug, wait 3 seconds.
3. Check baud rate: RX firmware uses 115200.
4. Try `stty -F /dev/ttyACM2 115200 raw -echo` then `cat /dev/ttyACM2`.
5. If CDC is dead (no output at all), the RX firmware may need reflash with
   `delay(2000)` fix — but current `flrc_raw_rx.cpp` already has this.

### TX board produces no output

- For PIO v3: CDC dying during TX is **expected behaviour**. Output should
  return after TX completes (~2-3 seconds after WAIT window expires).
- For v4: CDC should be alive throughout. If dead, check `delay(2000)` fix.

### High packet loss (>5%)

1. Move boards closer (< 50 cm).
2. Check antennas are connected to both boards.
3. Check both boards are on the same frequency (FLRC mode, same config).
4. Verify TX is actually sending: check TX_DONE count (for v4) or use
   an SDR / spectrum analyser to confirm RF output.
5. If TX_DONE = 1000 but RX receives < 950 → RX firmware timing issue
   (not spending enough time in RX mode, or missing packets during processing).

### Throughput > 2600 kbps reported

- **This is impossible** — 2600 kbps is the FLRC air rate.
- If reported, the TX_DONE flag is being read incorrectly (fake TX_DONE).
- Radio reports TX_DONE before the packet has actually finished transmitting.
- This means the TX firmware is starting the next packet before the previous
  one is in the air — packets are being dropped at the radio level.
- Fix: increase inter-packet delay or poll TX_DONE more carefully.

---

## Test Matrix

| Test # | TX Version | RX Firmware | TX Pkts | Expected Result | Date |
|--------|------------|-------------|---------|-----------------|------|
| 1      | v4 baseline | flrc_raw_rx | 1000    | 1367 kbps, 0% loss | 2026-07-16 (baseline) |
| 2      | PIO v3     | flrc_raw_rx | 1000    | ~1370 kbps, ≤2% loss | Awaiting |
| 3      | PIO v1     | flrc_raw_rx | 1000    | ~1377 kbps, unknown loss | Optional (CDC dead) |

---

## Quick Reference: One-Liner Test

```bash
# Start RX capture in background
stty -F /dev/ttyACM2 115200 raw -echo && \
  cat /dev/ttyACM2 > rx_capture_$(date +%Y%m%d_%H%M%S).log &

# Wait for RX LISTENING (check log)
sleep 3 && grep "RX LISTENING" rx_capture_*.log

# Reset TX board to trigger TX (or wait for WAIT window to expire)
# ... TX runs for ~2-3 seconds ...

# Stop capture and check results
kill %1
grep -c "RX_PKT" rx_capture_*.log
grep "RX DONE" rx_capture_*.log
```

---

*Document generated 2026-07-16. RX firmware: `flrc_raw_rx.cpp` with `delay(2000)` CDC fix.*