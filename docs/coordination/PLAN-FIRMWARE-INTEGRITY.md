# PLAN: Firmware Binary Integrity & Flash Control

**Created:** 2026-07-24  
**Status:** PROPOSED  
**Problem:** Multiple sub-managers flash different firmware builds to the same boards with no record. TX and RX end up running mismatched commits → garbage data with no way to diagnose.

## ROOT CAUSE ANALYSIS

Today's flash chaos — 6+ commits to `multi_radio_sweep_gps.cpp`, each followed by a flash:

```
aaa7ebf  fix: align embedGPS/parseGPS byte offsets
543e96f  fix: RX UTC-driven loop — phase sync
57ea008  fix: GPS payload fix reflash
be354b0  fix: GPS payload verified
b182b81  data: walk test results
46032a0  data: extended walk capture
091218b  data: walk capture 599 lines
```

Each flash overwrote the previous with no verification. At some point TX was flashed from one commit and RX from another. Result: radio link works (RSSI -53 to -58 dBm) but payload parsing fails (sats=52195, lat=-209) because byte offsets don't match between builds.

**The mutex is insufficient because:**
1. Advisory flock — only blocks cooperative processes
2. Port mappings are static (ACM0→rx, ACM3→tx) but ports swap after replug
3. `BALLOON_TRACK` env var bypass — if not set, guard warns but proceeds
4. Guard not even ENABLED in platformio.ini (`extra_scripts` line missing)
5. No read-back verification after flash
6. No record of what's actually running

---

## THE 5-LAYER SOLUTION

### Layer 1: Firmware Self-Identification (In-Band)

**Goal:** Every board knows and reports exactly what it's running.

**Implementation:**

1. **Build-time injection** — PlatformIO `extra_scripts` reads git state and injects `#define`:
   ```python
   # tools/inject_git_version.py
   import subprocess
   hash_val = subprocess.check_output(
       ["git", "rev-parse", "--short", "HEAD"]
   ).decode().strip()
   dirty = subprocess.check_output(
       ["git", "describe", "--always", "--dirty"]
   ).decode().strip()
   build_time = subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%MZ"]).decode().strip()
   ```

2. **Firmware constants** (in `multi_radio_sweep_gps.cpp`):
   ```cpp
   const char FW_HASH[8] = FW_GIT_HASH;      // "a1b2c3d"
   const char FW_TAG[4]  = FW_BUILD_TAG;      // "TX0" or "RX0"
   const char FW_BUILT[18] = FW_BUILD_TIME;   // "2026-07-24T14:00Z"
   ```

3. **Boot banner** — first serial output on power-up / USB connect:
   ```
   FW_BOOT hash=a1b2c3d tag=TX0 built=2026-07-24T14:00Z git=aaa7ebf-dirty
   ```

4. **TX payload** — 7 extra bytes appended to every packet:
   ```
   [existing 24-byte payload][7-char hash][3-char tag]
   ```
   RX extracts and logs: `PKT rx=1 ... tx_fw=a1b2c3d tx_tag=TX0`

5. **PHASE_RESULT** — RX includes its own hash:
   ```
   PHASE_RESULT 3 HF-FLRC-2600 ... tx_fw=a1b2c3d rx_fw=e4f5g6h
   ```

**Effort:** ~2 hours (extra_script + firmware changes + RX parse update)

---

### Layer 2: Boot Banner Verification (Pre-Flight)

**Goal:** After ANY flash, read back and verify what's actually running.

**Implementation:**

1. **Post-flash verification script** (`tools/verify_flash.sh`):
   ```bash
   #!/bin/bash
   # Usage: verify_flash.sh <port> <expected_hash>
   PORT=$1
   EXPECTED=$2
   stty -F $PORT 115200 cs8 -cstopb -parenb raw -echo
   # Read boot banner (may need to reset board first)
   BANNER=$(timeout 5 cat $PORT 2>/dev/null | grep "FW_BOOT" | head -1)
   ACTUAL=$(echo "$BANNER" | grep -oP 'hash=\K[a-f0-9]+')
   if [ "$ACTUAL" != "$EXPECTED" ]; then
     echo "VERIFY FAILED: expected=$EXPECTED actual=$ACTUAL"
     exit 1
   fi
   echo "VERIFY OK: hash=$ACTUAL"
   ```

2. **Flash manifest** — every flash recorded to `data/FLASH-MANIFEST.csv`:
   ```csv
   timestamp,board,serial,old_hash,new_hash,flashed_by,purpose,verified
   2026-07-24T14:30Z,tx,F242D,unknown,a1b2c3d,range-tests,RSSI fix,Y
   2026-07-24T14:35Z,rx,8332,b2c3d4e,a1b2c3d,range-tests,RSSI fix,Y
   ```

3. **Pre-walk checklist** (mandatory before any walk test):
   - [ ] Read TX boot banner, verify hash
   - [ ] Read RX boot banner, verify hash
   - [ ] Confirm TX hash == RX hash (or documented compatible pair)
   - [ ] Record in manifest
   - [ ] If mismatch → STOP, reflash, re-verify

**Effort:** ~1 hour

---

### Layer 3: Mandatory Flash Guard (Hardware-Enforced)

**Goal:** Make it mechanically impossible to flash without authorization.

**Implementation:**

1. **Enable the existing guard** in `platformio.ini`:
   ```ini
   [env]
   extra_scripts = pre:tools/pio_upload_guard.py
   ```

2. **Remove the bypass** — fix `pio_upload_guard.py`:
   - Current: `if not track: return` (warns and proceeds)
   - New: `if not track: sys.exit(1)` (BLOCKS if no track set)
   - Exception: `--force` flag for manual operator override (logged)

3. **Use serial number, not port** — boards identified by udev serial:
   - TX board: serial contains `F242D` (always, regardless of ACM port)
   - RX board: serial contains `8332` (always, regardless of ACM port)
   - Lock is on board identity, not volatile port number

4. **udev rules** — create stable symlinks:
   ```
   # /etc/udev/rules.d/99-balloon-boards.rules
   SUBSYSTEM=="tty", ATTRS{idSerial}=="*F242D*", SYMLINK+="balloon-tx"
   SUBSYSTEM=="tty", ATTRS{idSerial}=="*8332*", SYMLINK+="balloon-rx"
   ```
   Flash and capture scripts use `/dev/balloon-tx` and `/dev/balloon-rx` — never raw ACM numbers.

5. **Capture-mode lock** — while `data/walk-official-rx.txt` is being actively written (capture running), ALL flash attempts to that board are blocked. No override.

**Effort:** ~1.5 hours

---

### Layer 4: Flash Coordination Protocol (Orchestrator-Controlled)

**Goal:** Only the orchestrator authorizes flashes. Sub-managers request, not self-serve.

**Protocol:**

1. **Sub-manager wants to flash:**
   - Escalates to orchestrator: `FLASH REQUEST: track=speed-tests board=rx commit=aaa7ebf purpose="GPS parser fix"`
   - Orchestrator checks: Is anyone testing? Is capture running? What's the priority?

2. **Orchestrator grants/denies/queues:**
   - GRANT: `FLASH APPROVED: track=speed-tests board=rx commit=aaa7ebf. Window: 15 min. Release lock after.`
   - DENY: `FLASH DENIED: board=rx is in active capture. Queue behind walk test. ETA: 2h.`
   - QUEUE: `FLASH QUEUED: position 2. Will notify when board available.`

3. **Flash window:** Orchestrator specifies a time window. Flash must complete + verify within window. After window, lock auto-released.

4. **Post-flash reporting:** Sub-manager reports: `FLASH COMPLETE: board=rx old=abc123d new=def456g verified=Y`

5. **Manifest update:** Orchestrator appends to `data/FLASH-MANIFEST.csv`

**Flash priority matrix:**

| Priority | Who | Preempts? |
|----------|-----|-----------|
| P0 — Active walk test | Operator + range-tests | Blocks ALL flashes to both boards |
| P1 — Operator-directed flash | Orchestrator | Preempts P2 |
| P2 — Bug fix flash | Sub-managers (approved) | Queue only |
| P3 — Experimental build | Sub-managers (approved) | Queue, lowest priority |

**Effort:** ~2 hours (protocol doc + orchestrator checklist + sub-manager AGENTS.md update)

---

### Layer 5: Continuous Monitoring

**Goal:** The orchestrator always knows what's running on each board.

**Implementation:**

1. **Board state check** — orchestrator can run anytime:
   ```bash
   # Read boot banner without disrupting capture (via ESP32 bridge)
   echo "FW_QUERY" > /dev/ttyACM1  # ESP32 bridge relays to RP2040
   # RP2040 responds: FW_BOOT hash=... tag=...
   ```

2. **Board state in status report** — every status pull includes:
   ```
   BOARD STATE:
   - TX (F242D): firmware=abc123d tag=TX0 last_seen=14:30Z
   - RX (8332): firmware=def456g tag=RX0 last_seen=14:31Z
   - MISMATCH: TX and RX running different commits
   ```

3. **Alert on mismatch** — if TX hash != RX hash (and not documented as intentional), orchestrator alerts the group immediately.

**Effort:** ~1 hour

---

## IMPLEMENTATION ORDER

| Phase | Task | Blocking? | Effort |
|-------|------|-----------|--------|
| 1A | Build-time git hash injection (`inject_git_version.py`) | No | 30 min |
| 1B | Firmware boot banner (TX + RX) | No | 30 min |
| 1C | TX payload includes hash (7 bytes) | No | 30 min |
| 1D | RX parses tx_fw from packets, logs in PHASE_RESULT | No | 30 min |
| 2 | Boot banner verification script + manifest | No | 1 hour |
| 3A | Enable pio_upload_guard.py in platformio.ini | Yes — requires flash | 15 min |
| 3B | Fix guard bypass (remove track-not-set exit) | Yes — requires flash | 15 min |
| 3C | udev rules for stable symlinks | Yes — requires replug | 30 min |
| 4 | Flash coordination protocol docs + AGENTS.md updates | No | 1 hour |
| 5 | Continuous monitoring (FW_QUERY command) | Yes — requires flash | 30 min |

**Total effort:** ~6 hours  
**Critical path:** Phases 1A-1D (firmware identification) — do FIRST so we never fly blind again.

---

## WHAT THE OPERATOR SEES (After Implementation)

Before walk test:
```
PRE-WALK VERIFICATION
  TX: reading boot banner... FW_BOOT hash=a1b2c3d tag=TX0 built=2026-07-25T09:00Z
  RX: reading boot banner... FW_BOOT hash=a1b2c3d tag=RX0 built=2026-07-25T09:00Z
  MATCH: YES ✓
  Manifest updated.
  Ready to walk.
```

During capture:
```
PKT rx=1 seq=12345 rssi=-54 phase=3 tx_fw=a1b2c3d tx_tag=TX0 tx_lat=32.639 tx_lon=-16.946 sats=12 fix=1
```

If a sub-manager tries to flash mid-walk:
```
PIO UPLOAD GUARD: REFUSED
Board 'rx' is in P0 active capture mode.
Flash request DENIED. Queue position: 1.
Contact orchestrator for approval.
```
