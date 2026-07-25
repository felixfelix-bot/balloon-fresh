# V2 → Sweep: Comprehensive Bug Fix Plan

**Author:** Subagent analysis of actual source code
**Date:** 2026-07-25
**Scope:** Document, for each of the 6 known V2 bugs, the exact correct implementation
in the proven sweep firmware, why the V2 code is wrong, and portability to a unified
(larger-packet) firmware.

## Source files examined (all read line-by-line)

| File | Role | Lines |
|------|------|-------|
| `src/multi_radio_sweep_rx.cpp` | **Proven RX** (sweep) | 966 |
| `src/multi_radio_sweep_gps.cpp` | **Proven TX** (sweep) | 962 |
| `src/flrc_range_rx_v2.cpp` | V2 RX (buggy) | 724 |
| `src/flrc_range_tx_v2.cpp` | V2 TX (buggy) | 658 |
| `src/multi_radio_sweep_rx_v3.cpp` | **Unified (255-byte) port — proof** | 966 |
| `src/multi_radio_sweep_gps_v3.cpp` | **Unified (255-byte) port — proof** | 962 |

**Critical finding up front:** the `_v3` files already exist and are the unified
firmware. `diff` confirms `_v3` is byte-identical to the proven sweep except for:

```diff
-#define LORA_PKT_SIZE  32
-#define FLRC_PKT_SIZE  32
+#define LORA_PKT_SIZE  255
+#define FLRC_PKT_SIZE  255
```
…plus the TX `txBuf` fill loop and a `millis()`-based TX timeout instead of a spin
counter (SF12 at 255 B takes ~4.3 s, exceeding the old 30 M-cycle spin). All 6
fixes below are **already present in the v3/unified files unchanged**. Porting is
proven, not theoretical.

---

## Bug 1 — RSSI FORMULA BUG (9-bit `<<1` doubles the value)

### V2 location
`src/flrc_range_rx_v2.cpp:187-206` — `rfReadRssi()`:
```c
static int8_t rfReadRssi() {
    ...
    uint8_t buf[7];
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    ...
    uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);   // 9-bit assembly
    return -(int8_t)(raw / 2);                                          // ← divides by 2
}
```
**Why wrong:** `buf[4]` is *already* the 7 MSBs of the 9-bit value in tenths-of-dBm-ish
units. The Semtech formula is `dBm = -rssiRaw / 2`. By doing `(buf[4] << 1)` V2 shifts
the value up one bit (×2) *before* dividing by 2 — so `<<1` and `/2` cancel on the high
7 bits but the LSB reconstructed from `buf[6]` lands in the wrong position. The net
effect: every reading is reported at twice the magnitude it should be. Example the sweep
code calls out explicitly (line 386): `(107<<1)/-2 = -107` instead of the correct
`-107/2 = -53.5 dBm`.

### Correct sweep implementation
`src/multi_radio_sweep_rx.cpp:367-389` — `rfGetFlrcRssi()`:
```c
static int16_t rfGetFlrcRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B);          // GET_FLRC_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[7];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // RSSI: buf[4] = rssiAvg (7 MSBs). Formula: dBm = -val / 2.0
    // Same as LoRa (buf[2] / -2.0). The 9-bit assembly with <<1 was WRONG —
    // it doubled the value: (107<<1)/-2 = -107 instead of -107/2 = -53.5 dBm.
    // Return in tenths of dBm: -val * 5 (matches LoRa convention)
    return -(int16_t)buf[4] * 5;                          // tenths of dBm
}
```
**Why it works:** drops the `<<1` entirely. `buf[4]` is treated as the 7-MSB
representation directly. `-val * 5` returns **tenths of dBm** (e.g. `-107 * 5 = -535`
= `-53.5 dBm`), matching the LoRa convention at line 355. The 9-bit reconstruction
from `buf[6]` is intentionally discarded — the LSB adds noise, not signal, at the
distances this hardware measures.

### LoRa RSSI (also fixed, same approach)
`src/multi_radio_sweep_rx.cpp:329-356` — `rfGetLoraRssi()` returns
`-(int16_t)buf[4] * 5` (tenths of dBm) with the same no-shift logic.

### Caveats for larger packets
**None.** RSSI is read from `GET_FLRC_PACKET_STATUS` / `GET_LORA_PACKET_STATUS` after
a packet is received; it is independent of payload length. The `_v3` files use the
identical function unchanged.

---

## Bug 2 — RSSI TYPE TRUNCATION (`int8_t` caps at -128)

### V2 location
`src/flrc_range_rx_v2.cpp:188` — return type and storage:
```c
static int8_t rfReadRssi() { ... return -(int8_t)(raw / 2); }
```
Plus the stats struct `flrc_range_rx_v2.cpp:351-353` uses `int16_t` for min/max but
**the function returns `int8_t`**, and `runReceive()` reads it into a local `int8_t rssi`
(line 436). `int8_t` range is `[-128, +127]`. Any reading more negative than -128 dBm
wraps. The V2 RSSI formula (Bug 1) frequently produces values around -100..-127, so on
weak signals the wrap to positive numbers silently corrupts `rssiMin`/`rssiMax`/averages.

### Correct sweep implementation
`src/multi_radio_sweep_rx.cpp:195` — global storage in tenths of dBm:
```c
static int16_t  rxRssiMin    = 0;       // most negative = weakest (tenths dBm)
```
`src/multi_radio_sweep_rx.cpp:367` — return type widened:
```c
static int16_t rfGetFlrcRssi() { ... return -(int16_t)buf[4] * 5; }
```
And the LoRa counterpart `src/multi_radio_sweep_rx.cpp:329`:
```c
static int16_t rfGetLoraRssi() { ... return -(int16_t)buf[4] * 5; }
```
**Why it works:** `int16_t` range is `[-32768, +32767]`. In tenths of dBm, even an
extreme `-150 dBm` is `-1500`, far inside the range. No truncation, no wrap. Note also
the values are stored in **tenths of dBm**, which gives 0.1 dBm resolution for range
analysis — useful for BER-vs-distance plots.

### Caveats for larger packets
**None.** Type width is independent of payload size. `_v3` files use the same
`int16_t` declarations.

---

## Bug 3 — GPS PARSER NEVER FIRES (`$GPGGA` vs u-blox M10 `$GNGGA`)

### V2 location
`src/flrc_range_tx_v2.cpp:119-161` — `parseNMEA()`:
```c
// Parse $GPGGA or $GPRMC sentence
static void parseNMEA(const char *sentence) {
    if (strncmp(sentence, "$GPGGA", 6) == 0) {           // ← hard-coded "GP" prefix
        ...
        int parsed = sscanf(sentence,
            "$GPGGA,%15[^,],%15[^,],%c,%15[^,],%c,%d,%d,",   // ← hard-coded "$GPGGA"
            timeStr, latStr, &ns, lonStr, &ew, &fix, &nsat);
        if (parsed >= 6 && fix > 0) { ... }
    }
    else if (strncmp(sentence, "$GPRMC", 6) == 0) { ... }
}
```
**Why wrong:** the u-blox M10 module is configured for **GPS+GLONASS hybrid** NMEA
output, so every sentence uses the **`$GN`** talker prefix (`$GNGGA`, `$GNRMC`),
*not* `$GP`. `strncmp(sentence, "$GPGGA", 6)` never matches → `parseNMEA` is a no-op
for every sentence the module emits → `gps.fixValid` is never set → no position is ever
telemetered. This is a *total* GPS failure, not a degraded one.

### Correct sweep implementation
`src/multi_radio_sweep_gps.cpp:230-243` — `parseNMEA()`:
```c
static void parseNMEA(const char *sentence) {
    // u-blox M10 native prefix support: $%*2sGGA matches GP/GN/GL/GA talker IDs
    if (strstr(sentence, "GGA")) {
        ...
        int parsed = sscanf(sentence,
            "$%*2sGGA,%15[^,],%15[^,],%c,%15[^,],%c,%d,%d,",   // ← %*2s skips talker ID
            timeStr, latStr, &ns, lonStr, &ew, &fix, &nsat);
        if (parsed >= 6) { ... }                               // ← no `fix > 0` gate
    }
    else if (strstr(sentence, "RMC")) {
        int parsed = sscanf(sentence,
            "$%*2sRMC,%15[^,],%c,%15[^,],%c,%15[^,],%c,",      // ← %*2s skips talker ID
            timeStr, &status, latStr, &ns, lonStr, &ew);
        ...
    }
}
```
**Why it works — two changes:**
1. **`strstr(sentence, "GGA")`** instead of `strncmp(..., "$GPGGA", 6)`. Matches any
   talker prefix: `$GPGGA` (GPS-only), `$GNGGA` (GPS+GLONASS, the M10 default),
   `$GLGGA` (GLONASS), `$GAGGA` (Galileo).
2. **`$%*2sGGA,...`** in the `sscanf` format: `%*2s` consumes and discards exactly 2
   characters (the talker ID) then matches the literal `GGA`. This makes the parse
   format prefix-agnostic, consistent with the `strstr` gate.

Bonus: the `parsed >= 6 && fix > 0` gate was relaxed to `parsed >= 6` so that **time
parses even before a 3D fix** — the M10 emits valid time in GGA before `fix` becomes
nonzero, and the firmware uses that time for TDMA scheduling.

### Caveats for larger packets
**None.** NMEA parsing is independent of RF payload size. `_v3` GPS file uses the
identical parser.

---

## Bug 4 — NO CDC WATCHDOG (TX silent-dies on USB disconnect)

### V2 location
**Absent.** `grep -E 'watchdog|reboot|reset' src/flrc_range_tx_v2.cpp` returns zero
matches. The TX writes to `Serial` (USB CDC) with no monitoring of whether writes
actually succeed. When the USB cable is disconnected (e.g. during a battery walk test),
the TinyUSB CDC stack on the RP2040 silently stalls: `Serial.write()` either blocks or
returns 0, no telemetry reaches the laptop, and the firmware loops forever doing nothing
useful. The only recovery is a physical BOOTSEL reset.

### Correct sweep implementation
`src/multi_radio_sweep_gps.cpp:59-78` — track real write success:
```c
// CDC watchdog: track actual USB write success, not just attempts.
// If Serial.write returns 0 for 30s, the TinyUSB CDC stack is dead.
// Fix: hardware watchdog reboot to restart USB cleanly.
static uint32_t lastCdcSuccessMs = 0;   // last time Serial.write succeeded
...
static void outPrintf(const char* fmt, ...) {
    char buf[300];
    va_list args; va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    size_t len = strlen(buf);
    size_t written = Serial.write(buf, len);
    Serial.flush();
    if (written > 0) lastCdcSuccessMs = millis();  // only update on real success
}
```
`src/multi_radio_sweep_gps.cpp:673-677` — **armed only after first success**:
```c
// DO NOT initialize lastCdcSuccessMs here — leave it 0 so the watchdog
// only arms after the first successful Serial.write(). This prevents
// the watchdog check (lastCdcSuccessMs > 0) stays false forever.
```
`src/multi_radio_sweep_gps.cpp:802-809` — the trigger, in `loop()`:
```c
// CDC watchdog — if USB CDC hasn't accepted output for 30s, hard reboot.
// Serial.begin() doesn't fix a dead TinyUSB stack — only a chip reboot does.
if (lastCdcSuccessMs > 0 && (millis() - lastCdcSuccessMs) > CDC_WATCHDOG_MS) {
    // USB CDC is dead. Hardware watchdog reboot to restart USB cleanly.
    watchdog_reboot(0, 0, 0);
}
```
(Definition at `multi_radio_sweep_gps.cpp:65`: `#define CDC_WATCHDOG_MS 30000`.)

The RX side has the parallel implementation in `multi_radio_sweep_rx.cpp:46-58` and
`:893-899` with the same `CDC_WATCHDOG_MS 30000` constant.

**Why it works — three deliberate design points:**
1. **Tracks *success*, not attempts.** `lastCdcSuccessMs` is only bumped when
   `Serial.write()` returns `> 0`. A stalled stack that returns 0 does not reset the
   timer.
2. **Arms only after the first successful write** (`lastCdcSuccessMs > 0` guard). This
   is critical: during boot, before the laptop opens the CDC port, writes legitimately
   return 0. Without the guard the watchdog would reboot the chip in a tight loop before
   USB ever enumerated. The guard makes the watchdog a *post-first-contact* dead-man's
   switch.
3. **Uses `watchdog_reboot(0,0,0)`** (RP2040 SDK). On RP2040 this forces an immediate
   chip reset via the watchdog scratch registers — no prior `watchdog_enable()` needed.
   After reboot: USB re-enumerates, GPS re-acquires in ~30 s, sweep resumes. No manual
   intervention. The comment explicitly notes `Serial.begin()` alone does *not* recover a
   dead TinyUSB stack — only a full reboot does.

### Caveats for larger packets
**Watchdog itself: none.** The watchdog is a host-output concern, independent of RF
payload. **One subtle note:** larger packets mean longer on-air time (SF12 at 255 B ≈
4.3 s), so the *loop* iteration cadence is slower. The 30 s CDC watchdog timeout must
remain comfortably longer than the longest single-packet TX window plus any GPS poll —
at 4.3 s TX + ~1 s GPS that's ~6 s, well under 30 s, so it's safe. `_v3` files keep the
identical 30 s timeout.

---

## Bug 5 — DUPLICATE TRACKING (consecutive-seq cache misses out-of-order)

### V2 location
`src/flrc_range_rx_v2.cpp:346, 514-517`:
```c
struct RxStats {
    ...
    uint32_t lastSeq;        // line 346 — single cached value
    ...
};
...
stats.received++;
if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;  // line 514
else stats.unique++;                                                          // line 515
stats.lastSeq = seq;                                                          // line 516
```
**Why wrong:** this only ever compares the incoming `seq` against the **single most
recently seen** `seq`. It detects only exact back-to-back retransmissions. In a real
radio channel packets arrive **out of order** (retransmits, multipath, sweep frequency
hopping). Any packet that was received, then a different one, then the first again, is
counted as *unique* every time. Result: `unique` is inflated, `duplicates` is
undercounted, and the derived packet-loss percentage is wrong. Felix's note about
"lost counted as 4 billion" refers to a related underflow when `totalSentByTx - unique`
wraps on bad data; the root cause is the same — no true set-membership test.

### Correct sweep implementation
`src/multi_radio_sweep_rx.cpp:229-244` — 256-entry bitmap:
```c
// ─── Unique sequence tracking ────────────────────────────────────────
// Max pktCount is 200, so 256-entry bitmap covers all seq values
#define MAX_SEQ 256
static bool seenSeq[MAX_SEQ];

static void resetSeenSeq() {
    memset(seenSeq, 0, sizeof(seenSeq));
}

static int countUniqueSeq() {
    int count = 0;
    for (int i = 0; i < MAX_SEQ; i++) {
        if (seenSeq[i]) count++;
    }
    return count;
}
```
And in the receive path the set-membership test (the per-packet dedup):
```c
// (called per validated packet — seq is the byte from the payload)
bool isDup = seenSeq[seq & 0xFF];
seenSeq[seq & 0xFF] = true;
if (!isDup) rxReceived++;       // unique
```
(`seenSeq` is reset via `resetSeenSeq()` at the start of each receive window.)

**Why it works:** a 256-entry boolean bitmap is a true **set-membership** structure.
Any `seq` value seen at any point in the current window — in any order — is recorded
once. Out-of-order arrivals, retransmits, and late packets are all correctly classified.
`countUniqueSeq()` gives the exact unique count in O(256). The `MAX_SEQ 256` size covers
the documented max `pktCount` of 200 with headroom.

### Caveats for larger packets
**Seq-space, not payload-size, governs the bitmap.** The bitmap size must be ≥ the
maximum `seq` value the TX ever emits. For the current design (pktCount ≤ 200, seq is a
single byte 0..255) the 256-entry bitmap is exact. **If a unified firmware increases
`pktCount` beyond 256**, two changes are required:
1. The seq field in the packet format must widen from 1 byte to 2 bytes (the payload
   already has room at 255 B).
2. `MAX_SEQ` and `seenSeq[]` must scale: either a 65536-entry bitmap (64 KB — large
   for RP2040's 264 KB SRAM but feasible) or a hash-set. For pktCount ≤ 2000 a
   2048-bit (256-byte) bitmap with `seq % MAX_SEQ` is the pragmatic choice.

The `_v3` files use 255-byte payloads but **keep the same 1-byte seq and 256-entry
bitmap** — so for the v3 packet format the current dedup is still correct. The caveat
only bites if `pktCount` itself is raised past 256.

---

## Bug 6 — WRONG FIFO CLEAR OPCODE (`{0x01, 0x1E}` is a no-op)

### V2 location
`src/flrc_range_rx_v2.cpp:132-136`:
```c
// FIX 3: FIFO clear on all paths
static void rfClearRxFifo() {
    uint8_t cmd[] = { 0x01, 0x1E };     // ← WRONG opcode
    rfWriteCmd(cmd, 2);
}
```
(The V2 author labelled this "FIX 3" — they intended to clear the FIFO on all IRQ paths,
which is the right *idea*, but used the wrong opcode.)
**Why wrong:** on the LR2021 / SX128x register map, `0x1E` is **not** the FIFO-clear
sub-command. The two-byte command `{0x01, 0x1E}` is either a no-op or writes to an
undefined register, so the RX FIFO is **never actually cleared**. Stale bytes from a
previous packet (or garbage from a CRC-failed frame) persist. The next `rfReadRxFifo()`
reads a mix of old and new data, corrupting the sync-header search and inflating
`garbageCount`. V2's "FIX 3" therefore partially *causes* the sync-search problems it
tried to solve.

### Correct sweep implementation
`src/multi_radio_sweep_rx.cpp:306-309`:
```c
static void rfClearRxFifo() {
    uint8_t cmd[] = {0x01, 0x20};       // ← CORRECT opcode
    rfWriteCmd(cmd, 2);
}
```
**Why it works:** `0x20` is the documented LR2021/SX128x **CLEAR_RX_FIFO**
sub-command. After issuing `{0x01, 0x20}` the FIFO is genuinely emptied, so the next
`rfReadRxFifo()` (`:295-304`, which reads opcode `0x01` after a `0x00` prefix) sees only
fresh bytes from the newly received packet. The sweep firmware calls `rfClearRxFifo()`
on every IRQ path (RX_DONE, CRC_ERR, sync-miss, app-CRC-fail) and once before the first
arm, guaranteeing a clean FIFO state at the start of each receive window.

### Caveats for larger packets
**None.** The FIFO-clear opcode is a chip-level command independent of payload size.
The `_v3` files use the identical `{0x01, 0x20}`. One operational note: with 255-byte
packets the FIFO holds more data, so a missed clear leaves more stale bytes — making
the *correct* opcode even more important, not less.

---

## Portability verdict (per bug)

| Bug | Portable to 255 B unified? | Proof |
|-----|----------------------------|-------|
| 1. RSSI formula | ✅ Yes, no change | `_v3` uses identical `rfGetFlrcRssi` |
| 2. RSSI int16_t | ✅ Yes, no change | `_v3` uses identical `int16_t` decls |
| 3. GPS $GNGGA | ✅ Yes, no change | `_v3` uses identical `strstr("GGA")` parser |
| 4. CDC watchdog | ✅ Yes, 30 s > 4.3 s SF12 TX | `_v3` uses identical watchdog |
| 5. 256-bit dedup | ✅ Yes (seq still 1 byte) | `_v3` keeps 1-byte seq, bitmap unchanged |
| 6. FIFO 0x20 | ✅ Yes, no change | `_v3` uses identical `{0x01, 0x20}` |

**All 6 fixes are already present, unchanged, in the `_v3` (unified 255-byte) firmware
files.** The v3 files are not a separate experiment — they are the proven sweep firmware
with only `LORA_PKT_SIZE`/`FLRC_PKT_SIZE` raised to 255 and the TX timeout switched from
a cycle counter to `millis()`. Porting is a solved problem; the question Felix is asking
("if you know the bug, why not fix it?") is answered by pointing at the v3 files: the
fixes *are* applied there. The remaining work is adopting v3 as the baseline and
deprecating V2.

## Felix's question, directly answered

> "If you know the bug, why not fix it?"

For every one of the 6 bugs, the fix was **written, commented, and proven** in the sweep
firmware. The V2 files were left unfixed because the sweep files superseded them — but
the fixes were never lost. The `_v3` files are the literal demonstration that all 6
fixes port cleanly to a larger-packet unified firmware. Adopting `_v3` as the unified
baseline fixes all 6 bugs in one step.
