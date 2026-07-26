# Walk Test Postmortem — 2026-07-24

## Summary

5.7km outdoor walk test. TX in rucksack (GPS, battery). RX on balcony (USB).
FLRC range PROVEN EXCELLENT. LoRa PROVEN DEAD (phase desync, not range).
Multiple system failures discovered.

---

## WHAT WORKED

| Item | Result |
|------|--------|
| FLRC range | RSSI -55 dBm stable from 1km to 5.7km. Near-zero path loss. |
| HF FLRC (2.4 GHz) | 1273 packets across 4 modes. Median -53 dBm. |
| LF FLRC (868 MHz) | 418 packets across 4 modes. Median -56 dBm. |
| ESP32 bridge failover | RX Pico USB dropped at 12:53. ESP32 bridge (ACM1) kept capture alive for 90+ min. |
| CDC auto-reconnect | 10 USB dropouts handled seamlessly by `timeout 300 cat` loop. |
| Phone GPS correlation | 440 GPS points with epoch timestamps. Excellent ground truth. |
| Capture script robustness | 4-hour background capture survived USB drops, process kills, port changes. |

## WHAT FAILED

### F1: TX/RX firmware mismatch (CRITICAL)

**Symptom:** Walk data shows garbage GPS payloads (lat=-131, lon=133, sats=60665).
**Root cause:** Sub-managers independently flashed boards. Multiple binaries deployed
during the test. We don't know which build was on TX/RX during the walk.
**Evidence:** Theft log shows 5 board-lock steals on 2026-07-24. Range-tests sub-manager
ran `pio run -t upload` bypassing pio-flash.sh wrapper. Lock is advisory-only — flock
does not block raw `cat` or `pio upload`.
**Impact:** All GPS payload data from walk is unreliable. RSSI data is valid (hardware-level).

### F2: Byte alignment drift (CRITICAL)

**Symptom:** First 1-3 packets per phase decode correctly. Subsequent packets show
garbage GPS fields while RSSI is valid.
**Root cause:** TX and RX use different packet sizes per mode (LoRa vs FLRC have
different payload lengths). RX parses the buffer assuming a fixed layout, but the
byte offset drifts when packet boundaries aren't re-synced each receive cycle.
Gets worse at lower bitrates (325 kbps FLRC, SF12 LoRa) because more data accumulates
per IRQ cycle.
**Evidence:** FIPS track independent analysis confirms first-packet-correct-then-drift
pattern. Indoor tests showed 178 valid packets on FLRC-2600, then degradation.
**Impact:** GPS lat/lon/sats/fix fields unreliable after 2-3 packets per phase.

### F3: CRC false positives (CRITICAL)

**Symptom:** `crc_err=0` on ALL packets, including ones with obviously garbage payloads
(lat=-131, sats=60665).
**Root cause:** CRC is computed over raw bytes. If byte alignment drifts, the CRC
bytes themselves shift position — the RX reads a different region of the buffer,
and by coincidence the shifted bytes produce CRC=0. The CRC is NOT validating the
correct byte window.
**Impact:** Cannot trust crc_err field. Every packet appears "valid" even when garbage.

### F4: LoRa phase desync (MAJOR)

**Symptom:** Zero LoRa packets received across all SF (SF7/SF9/SF12) on both bands.
**Root cause:** TX computes phase from GPS UTC. RX computes phase from SET_TIME.
GPS UTC and laptop epoch differ by seconds. Over a 202s cycle, a few seconds offset
means TX is in LoRa phase while RX is in FLRC phase. They never align.
**Evidence:** FLRC phases (shorter, 8s each) occasionally overlap enough to catch
packets. LoRa phases (15-50s) never overlap because the phase offset is >50s.
**Impact:** Zero LoRa characterization data from the walk.

### F5: RX USB cable loose (MAJOR)

**Symptom:** RX Pico disappeared from USB at 12:53 UTC. Never came back.
**Root cause:** Physical USB cable on balcony came loose (wind/movement).
No one home to re-seat it.
**Impact:** Lost direct USB capture. ESP32 bridge saved the day but at lower fidelity.

### F6: Board lock bypassed by sub-managers (MAJOR)

**Symptom:** Multiple processes competing for /dev/ttyACM0 during walk.
Sub-manager spawned capture scripts while orchestrator had lock.
**Root cause:** flock is advisory. It does NOT block:
  - `cat /dev/ttyACM0` (reads from same port)
  - `pio run -t upload` (flashes board)
  - `picotool` operations
The pio-flash.sh wrapper exists but is voluntary — sub-managers bypass it.
**Impact:** Potential data corruption (two readers splitting serial output).
Confirmed 5 board-lock thefts in theft log.

---

## FIX PLAN

### Phase 1: Firmware Version Tracking (P0 — before next test)

Goal: Every packet self-documents which firmware sent it.

**1a. Embed FW_BUILD_ID in TX packet (bytes 22-23)**

```
Byte 22: FW_BUILD_ID (uint8, auto-incremented by build script)
Byte 23: FW_CONFIG_FLAGS (uint8: bit0=GPS_ACTIVE, bit1=SET_TIME_RX, bit2=CDC_WATCHDOG)
```

- Build script (`platformio.ini` extra_scripts) auto-increments build counter
- TX transmits build_id + flags in every packet
- RX echoes build_id in PHASE_RESULT lines
- Both boards print on USB boot: `FW_BUILD=N COMMIT=<short_hash> BINARY=<name>`

**1b. Build mapping file**

`firmware/BUILD_MAP.md` — auto-updated by build script:
```
| build_id | git_commit | binary_name | date |
|----------|-----------|-------------|------|
| 1        | aaa7ebf   | sweep-gps-tx | 2026-07-24 |
| 2        | b182b81   | sweep-rx     | 2026-07-24 |
```

**1c. Pre-flight verification script**

`tools/verify_board.sh` — reads first 3 lines from serial, verifies build_id:
```bash
# Usage: verify_board.sh /dev/ttyACM0 expected_build_id
# Exit 0 = match, exit 1 = mismatch
```

Before ANY test: run verify_board.sh on BOTH boards. If mismatch → STOP.

**1d. Capture filenames include build_id**

`walk-build5-tx-vs-build6-rx-20260724.txt`

### Phase 2: Hard Board Locking (P0 — before next test)

Goal: Physical prevention of unauthorized access, not just advisory.

**2a. udev chmod on lock acquire/release**

Modify `balloon-board-lock.py`:
- On acquire: `chmod 000 /dev/ttyACMx` (blocks ALL access)
- On release: `chmod 666 /dev/ttyACMx` (restores access)
- Lock holder gets exclusive access via file descriptor kept open

Problem: lock holder ALSO can't read if chmod 000. Solution:
- Lock holder opens fd BEFORE chmod
- Others get EACCES on open()

**2b. picotool/openocd wrappers in PATH**

Create `~/.local/bin/picotool` and `~/.local/bin/openocd` shims:
```bash
#!/bin/bash
# Check board lock before allowing picotool
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py check $BALLOON_TRACK || exit 1
exec /usr/bin/picotool "$@"
```

This intercepts ALL flashing paths, not just pio-flash.sh.

**2c. Flash queue coordination**

`docs/coordination/FLASH-QUEUE.md`:
```
| track | board | purpose | requested | approved | duration |
|-------|-------|---------|-----------|----------|----------|
| range-tests | TX+RX | byte align fix | 14:00 | YES | 30min |
```

Rule: NO flashing without orchestrator approval. Sub-managers escalate flash requests.

### Phase 3: Fix Byte Alignment (P1)

Goal: RX correctly parses every packet, not just the first 2-3.

**3a. Fixed packet length per mode**

TX and RX MUST agree on exact byte count per mode. Currently TX sends variable
length (LoRa vs FLRC have different overhead). Fix:
- Define `PKT_LEN[14]` array with exact byte count per phase
- TX sends exactly that many bytes
- RX reads exactly that many bytes
- No variable-length parsing

**3b. Sync preamble + header per packet**

Add a 2-byte sync header (0xA5 0x5A) at the START of every packet:
- RX scans for sync header before parsing fields
- If sync not found at expected position → search forward byte-by-byte
- This re-establishes byte alignment on EVERY packet, not just first

**3c. Per-packet CRC validation**

Recompute CRC over the CORRECT byte window (after sync header found):
- CRC covers bytes [2..N-2] (payload only)
- If CRC fails → mark as crc_err=1, discard payload
- Only accept packets where CRC validates AND sync header found

### Phase 4: Fix Phase Synchronization (P1)

Goal: TX and RX stay on same phase for entire walk.

**4a. GPS as primary clock for BOTH boards**

- TX: GPS UTC → phase = unixTime % cycleSec (already done)
- RX: GPS UTC → phase = unixTime % cycleSec (NEW — currently uses SET_TIME)
- SET_TIME becomes FALLBACK only, not primary
- When RX has no GPS, use SET_TIME. When GPS available, override with GPS.

**4b. Periodic re-sync**

- RX re-reads GPS every loop() iteration (non-blocking)
- TX re-reads GPS every loop() iteration
- Both compute phase fresh from UTC each cycle
- Eliminates drift from millis() accumulation

**4c. Extended RX listen windows**

- RX listens 2x the TX slot duration + 10s guard
- Already implemented but verify it's active
- Catches packets even with ±5s phase offset

### Phase 5: Walk Test Protocol Improvements (P2)

Goal: Capture survives every hardware failure mode.

**5a. Dual capture (USB + ESP32 bridge simultaneously)**

Always capture BOTH /dev/ttyACM0 (Pico USB) AND /dev/ttyACM1 (ESP32 bridge).
If one drops, the other continues. Merge post-walk by deduplication.

**5b. Secure USB cable**

- Hot-glue USB connector to Pico board
- Tape cable to balcony railing
- Use right-angle USB adapter to reduce strain

**5c. Pre-walk checklist**

```
[ ] verify_board.sh TX → build_id matches expected
[ ] verify_board.sh RX → build_id matches expected
[ ] Lock both boards (balloon-board-lock.py acquire both)
[ ] Notify ALL sub-managers: hands off
[ ] Start dual capture (USB + bridge)
[ ] Confirm packets flowing on both ports
[ ] Phone GPS recording
[ ] TX battery > 80%
[ ] GPS antenna external (not in rucksack)
```

---

## IMPLEMENTATION PRIORITY

| Phase | Priority | Effort | Blocks next walk? |
|-------|----------|--------|-------------------|
| Phase 1 (version tracking) | P0 | 2h | YES |
| Phase 2 (hard lock) | P0 | 1h | YES |
| Phase 3 (byte align) | P1 | 3h | YES (for valid GPS) |
| Phase 4 (phase sync) | P1 | 2h | YES (for LoRa data) |
| Phase 5 (walk protocol) | P2 | 30min | No |

Total: ~8.5h of work. Can be parallelized across tracks.

## ASSIGNMENT

- **range-tests**: Phase 1, 3, 5 (firmware changes, byte alignment)
- **speed-tests**: Phase 2 (board lock hardening — they own the lock infra)
- **orchestrator**: Phase 4 coordination + Phase 2c flash queue

---

## DATA PRESERVED

All walk test data committed and pushed:
- `data/walk-official-rx.txt` — raw RX capture (2959 lines, 253 packets)
- `data/phone-gps-walk-20260724.csv` — phone GPS ground truth (440 points)
- `data/walk-correlation.json` — parsed/correlated data
- `data/walk-comprehensive-analysis.png` — 6-panel analysis plot
- `data/walk-5km-results.png` — 4-panel summary plot

Git commits: 5a5046f, af841c1, b182b81, be354b0
