# UART telemetry protocol — ESP32-C3 tracker ⇄ RP2040 radio

**Status:** normative specification, version 1
**Card:** `t_79ae3ee7` (balloon board)
**Implementation:** `tracker/firmware/components/uart_telemetry/`
**Host tests:** `tracker/firmware/components/uart_telemetry/test/` (`make test`)

---

## 1. Scope and roles

The flight stack splits responsibilities across two MCUs on the same board:

| Role | MCU | Owns |
|------|-----|------|
| **Producer** | ESP32-C3 | GNSS fix, barometer/temperature, battery + solar rails, epoch/uptime, transmit policy |
| **Consumer / radio** | RP2040 | LR2021/SX1280 radio, modulation config, PA, packet counters, mesh membership |

The two are wired on a single 115200 baud link. This document fixes the frame
format, the payload layouts in both directions, and the framing/CRC rules that
let the receiver recover from noise without losing lock.

### 1.1 Physical link (already verified — do not re-derive)

From `docs/uart-bridge-pin-verification.md` (bidirectional test, CONFIRMED):

```
RP2040 GP12 (UART0 TX) ──→ ESP32-C3 GPIO3 (UART1 RX)
RP2040 GP13 (UART0 RX) ←── ESP32-C3 GPIO2 (UART1 TX)
GND ──────────────────────── GND
```

* 115200 baud, 8 data bits, no parity, 1 stop bit, no flow control.
* Both directions are independent; there is no shared clock.
* The link is **not** an ASCII console. The RP2040 bench console
  (`firmware/rp2040/src/bench/`, `docs/BENCH-CONSOLE-SPEC.md`) is a *separate*
  surface and must not be multiplexed onto this byte stream: a binary frame and
  a `PKT,` text line can never be distinguished by a shared parser. If the
  bench console has to share the physical UART, it goes on UART1 while
  telemetry stays on UART0.

---

## 2. Frame format

Every frame on this link has exactly this shape:

```
 offset  0      1      2     3      4       5           6 .. 5+len      6+len  7+len
       +------+------+-----+------+------+------+ - - - - - - - - +-------+-------+
       | 0xAA | 0x55 | VER | TYPE | LEN  | SEQ  |     PAYLOAD     | CRC_lo| CRC_hi|
       +------+------+-----+------+------+------+ - - - - - - - - +-------+-------+
          SOF (2 bytes)      ── header ──      └── LEN bytes ──┘   └── LE u16 ──┘
```

| Field | Size | Meaning |
|-------|------|---------|
| SOF | 2 | Start-of-frame marker, always `0xAA 0x55`. Never appears inside the CRC-covered range (§2.3). |
| VER | 1 | Protocol version. Only `1` is defined; any other value is a framing error. |
| TYPE | 1 | Frame type: `0x01` TELEMETRY, `0x02` MESH_STATUS. |
| LEN | 1 | Payload length in bytes. Must equal the fixed size for `TYPE` (§3, §4). `0` and `> 64` are invalid. |
| SEQ | 1 | Frame-level sequence byte, monotonically increasing mod 256, reset per boot. Always present so both directions can report link loss identically. |
| PAYLOAD | `LEN` | Type-specific payload. |
| CRC | 2 | CRC-16/CCITT-FALSE over `VER..PAYLOAD`, little-endian on the wire. |

Total frame size = `6 + LEN + 2`.

**Structs are never overlaid onto the wire buffer.** The RP2040 is a Cortex-M0+
with no unaligned access; encode/decode moves each field byte-wise through
explicit little-endian helpers. On the wire every multi-byte integer is
little-endian regardless of host endianness.

### 2.1 Frame types

| TYPE | Name | Direction | Fixed LEN |
|------|------|-----------|-----------|
| `0x01` | TELEMETRY | ESP32-C3 → RP2040 | 32 |
| `0x02` | MESH_STATUS | RP2040 → ESP32-C3 | 20 |

`LEN` must match the table exactly. A type/length mismatch is rejected as
`ERR_PAYLOAD_SIZE` — the frame is never partially applied.

### 2.2 CRC-16/CCITT-FALSE

* Polynomial `0x1021`, init `0xFFFF`, no input/output reflection, no final XOR.
* Check value: `crc16("123456789") == 0x29B1`.
* Additional golden vectors used by the host suite:
  * 64 × `0x00` → `0xD6DA`
  * 4096 bytes of `i % 256` → `0x0F69`

This is the **same algorithm already in use** by `components/telemetry`
(`telemetry_crc16`), `components/frag` (`frag_crc16`) and
`firmware/rp2040/src/bench/buffer.c` (`crc16_ccitt_false`). One golden vector
set covers all four call sites; there is no second CRC dialect in this repo.

### 2.3 Why the CRC excludes SOF

The CRC covers `VER..PAYLOAD` and starts at offset 2. Two consequences:

1. A **false SOF is harmless once the decoder is locked.** It is already
   counting bytes towards `expect` for the frame in flight, so a `0xAA 0x55`
   appearing inside a covered region (which is entirely possible — latitude
   and longitude bytes hit it regularly) is consumed as ordinary payload and
   can never be mistaken for a frame boundary.
2. A dropped/inserted byte shifts every subsequent field, so the CRC fails and
   the decoder re-synchronises rather than silently mis-parsing.

Note what is **not** claimed: excluding SOF does *not* make `0xAA55`
unproducible inside the covered range, and it does not change the CRC's
detection strength. CRC-16/CCITT-FALSE gives a residual undetected-error rate
of about 2⁻¹⁶ per frame, i.e. roughly one undetected corruption per 18 hours of
continuous 1 Hz traffic on a noisy link. That is acceptable for a periodic
telemetry broadcast with no ARQ (§6), and it is the reason the sequence
counters — not the CRC alone — are the link-health signal.

The `test_frame_size_and_sof()` assertion that the whole-frame CRC differs from
the covered-range CRC is a wiring check, not a proof of the above; the
behaviour it protects is pinned by `test_decoder_corruption()` (a good frame
immediately after a corrupt one still decodes).

### 2.4 Reserved / reserved-value handling

`0x02` is the only defined back-channel type. Values `0x03..0x7F` are reserved
for future peer-to-peer frames; a receiver that sees one must **drop the frame
without applying it** and continue. `0x80..0xFF` are reserved for vendor
extensions and are never emitted by this firmware.

---

## 3. TELEMETRY payload (ESP32-C3 → RP2040), 32 bytes

All offsets are payload-relative. Multi-byte fields are little-endian.

| Offset | Type | Field | Unit / notes |
|--------|------|-------|--------------|
| 0 | `uint32` | `seq` | Monotonic telemetry counter (sensor epoch, not the framing SEQ). |
| 4 | `uint32` | `uptime_ms` | Milliseconds since C3 boot. |
| 8 | `int32` | `lat_deg1e7` | WGS84 latitude × 1e7 (48.1234567° → 481234567). |
| 12 | `int32` | `lon_deg1e7` | WGS84 longitude × 1e7, negative west. |
| 16 | `int32` | `alt_mm` | Altitude above MSL, millimetres (signed; below-sea-level sites are legal). |
| 20 | `uint16` | `battery_mv` | Battery rail, millivolts. |
| 22 | `uint16` | `solar_mv` | Solar rail, millivolts; `0` = not instrumented. |
| 24 | `int16` | `temp_cdeg` | Board temperature, centi-degrees Celsius (`2150` = 21.50 °C). |
| 26 | `uint16` | `pressure_hpa10` | Barometric pressure, hPa × 10 (`10132` = 1013.2 hPa). |
| 28 | `uint8` | `sats` | Satellites used in the fix. `0` when no fix. |
| 29 | `uint8` | `hdop_x10` | HDOP × 10. `0` = unknown. |
| 30 | `uint8` | `flags` | See §3.1. |
| 31 | `uint8` | `tx_mode` | See §3.2. |

### 3.1 Flags (byte 30)

| Bit | Name | Meaning |
|-----|------|---------|
| 0 | `GPS_VALID` | Position fields are a real fix and may be trusted. |
| 1 | `GPS_FIX_3D` | Fix is 3-D (altitude trustworthy), not 2-D. |
| 2 | `SOLAR_ACTIVE` | Solar rail is producing; `solar_mv` is meaningful. |
| 3 | `LOW_BATTERY` | Battery below the mission threshold; the C3 is about to shed load. |
| 4 | `MESH_JOINED` | The C3 believes it is on the mesh (mirror of the back-channel bit). |
| 5 | `BROWNOUT` | A brownout reset has occurred since the last clear. |
| 6–7 | — | Reserved, must be sent as `0`. |

**Contract:** when `GPS_VALID` is clear, the receiver must ignore
`lat_deg1e7` / `lon_deg1e7` entirely, even if they hold stale numbers. `0/0` is
the canonical "no fix" sentinel and is explicitly rejected by the validator if
`GPS_VALID` is set — this is the classic NaN-island bug and it is a hard error.

### 3.2 `tx_mode` (byte 31)

| Value | Name | Meaning |
|-------|------|---------|
| `0` | `LORA` | Long-range, low-rate mode. |
| `1` | `FLRC` | High-rate short-range mode. |
| `2` | `IDLE` | Do not transmit. |

The C3 only requests `FLRC`/`LORA` when the back-channel reports
`RADIO_READY | TX_GRANTED`; otherwise it sends `IDLE`. The RP2040 treats
`tx_mode` as a *request*, never as a command it must obey — it may refuse.

---

## 4. MESH_STATUS payload (RP2040 → ESP32-C3), 20 bytes

| Offset | Type | Field | Unit / notes |
|--------|------|-------|--------------|
| 0 | `uint32` | `seq` | RP2040-side counter. |
| 4 | `uint32` | `uptime_ms` | Milliseconds since RP2040 boot. |
| 8 | `int16` | `rssi_half_dbm` | RSSI in **0.5 dBm** steps: `-145` = −72.5 dBm. Not `dBm × 10`. `-280` (−140.0 dBm) is the `UART_TLM_RSSI_NO_SIGNAL` sentinel for "no packet received yet" and is accepted by the validator. |
| 10 | `int8` | `snr_qdb` | SNR in 0.25 dB steps: `-12` = −3.0 dB. |
| 11 | `uint8` | `flags` | See §4.1. |
| 12 | `uint16` | `pkt_rx` | Packets received since boot (wraps). |
| 14 | `uint16` | `pkt_tx` | Packets transmitted since boot (wraps). |
| 16 | `uint16` | `crc_err` | Radio-level CRC failures since boot (wraps). |
| 18 | `uint8` | `state` | Radio state machine: `0` IDLE, `1` RX, `2` TX, `3` FAULT. |
| 19 | `uint8` | `chan` | Active channel / config index. |

The RSSI/SNR scaling matches the existing bench wire format
(`firmware/rp2040/src/bench/bench_pkt.h`: `rssi_half_dbm`, `snr_qdb`), so a
capture from either path is directly comparable.

### 4.1 Flags (byte 11)

| Bit | Name | Meaning |
|-----|------|---------|
| 0 | `RADIO_READY` | Radio initialised and not faulted. |
| 1 | `MESH_JOINED` | Node is a member of the mesh. |
| 2 | `TX_GRANTED` | The C3 may transmit now (radio idle + joined). |
| 3 | `PA_ENABLED` | External PA is powered. |
| 4 | `RX_OVERRUN` | The RP2040 saw an incomplete frame mid-flight — the C3 is sending too fast. |
| 5–7 | — | Reserved, sent as `0`. |

### 4.2 The back-channel contract

The C3 needs exactly three things from the RP2040, and all three are in this one
frame — there is no separate query/response exchange:

1. **May I transmit?** → `RADIO_READY | TX_GRANTED`.
2. **How should I transmit?** → `state`, `chan` (the C3 mirrors this into
   `tx_mode`).
3. **Is the link healthy?** → `rssi_half_dbm`, `snr_qdb`, `crc_err`, `pkt_rx`.

A MESH_STATUS frame is emitted at 1 Hz regardless of radio activity. **Silence
is the failure signal:** if no MESH_STATUS arrives for 5 s, the C3 must treat
the back-channel as dead, clear `MESH_JOINED`, force `tx_mode = IDLE`, and keep
transmitting TELEMETRY — losing the radio must not lose the sensor record. This
is implemented as `TLM_MESH_STALE_MS` in both drivers.

---

## 5. Framing and re-synchronisation

The decoder is a byte-fed state machine (`uart_tlm_decoder_t`). It must:

1. **Hunt** for `0xAA` then `0x55`; any other byte in the hunt state is
   discarded silently.
2. **Survive a false SOF.** A `0xAA` followed by anything other than `0x55` is
   noise. If the unexpected byte is itself `0xAA`, it becomes the new SOF
   candidate (so `AA AA 55` resyncs correctly) — this is the exact case a naive
   "restart on mismatch" decoder gets wrong, and it is covered by
   `test_decoder_resync_noise()`.
3. **Validate `LEN` as soon as byte 4 arrives.** `LEN == 0` or `LEN > 64`
   aborts the frame immediately rather than waiting for a byte count that will
   never arrive.
4. **Validate `VER`.** Any version other than `1` aborts: without a known
   version the framing cannot be trusted.
5. **Wait for exactly `6 + LEN + 2` bytes**, then verify the CRC.
6. **Only write the caller's payload buffer after the CRC passes.** A rejected
   frame must never partially clobber live sensor state.

Be precise about what step 3 buys. "Aborts immediately" holds for a `LEN` that
is *out of range*. A `LEN` corrupted to a different **in-range** value (say
32 → 20) cannot be detected at byte 4: the decoder waits for the wrong byte
count, swallows the bytes of the next frame, and only fails at the CRC. The
frame that was swallowed is lost until the sender's next frame re-locks the
pair. This is inherent to length-prefixed framing, not a defect, and it is why
the recovery time matters more than the recovery trigger — see the resync rule
below.

The assembler also carries a `have >= UART_TLM_MAX_FRAME` backstop that drops a
frame and re-hunts. With the current field widths it is **unreachable** (the
`LEN` check at byte 4 caps `expect` at `MAX_FRAME`, and the frame is finished
the moment `have == expect`); it is kept as a bound on `buf[]` in case the
`LEN` validation is ever loosened, and `len_errors` counts it so a future
reachability change cannot be silent.

**Re-synchronisation keeps a partial SOF.** When a frame is abandoned, the
decoder retains the trailing bytes that could *begin* a frame — a lone `0xAA`,
or a complete `0xAA 0x55` — and discards everything else. Retaining only a lone
`0xAA` would drop a valid frame whose SOF arrived inside the tail of a
corrupted (or truncated) frame, costing one whole frame period instead of a
partial frame's worth of bytes.

### 5.1 Error codes

| Code | Value | Cause |
|------|-------|-------|
| `UART_TLM_OK` | `0` | Byte consumed, or a valid frame produced. |
| `UART_TLM_ERR_CRC` | `-1` | Frame boundary found, CRC mismatch. |
| `UART_TLM_ERR_LEN` | `-2` | `LEN` is `0` or exceeds 64. |
| `UART_TLM_ERR_TYPE` | `-3` | Bad `SOF` pair, unknown `TYPE`, or unknown `VER`. |
| `UART_TLM_ERR_PAYLOAD_SIZE` | `-4` | `LEN` ≠ the fixed size for that type. |
| `UART_TLM_ERR_OVERFLOW` | `-5` | Caller output buffer too small. |
| `UART_TLM_ERR_ARG` | `-6` | `NULL` or otherwise invalid argument. |

A recovered error is **not** fatal: the decoder is left hunting and the next
valid frame decodes normally (verified by feeding a corrupted frame followed by
a good one in `test_decoder_corruption()`).

### 5.2 Link statistics

The decoder accumulates, monotonically since init:

| Field | Meaning |
|-------|---------|
| `frames_ok` | Valid frames produced. |
| `crc_errors` | Frames with a bad CRC. |
| `len_errors` | Frames with an invalid `LEN` or that overflowed the assembler. |
| `resyncs` | Times the decoder abandoned a partial frame. |
| `seq_drops` | Gaps in the frame-level `SEQ` byte. The **first** frame is never counted as a drop. |
| `last_seq` / `seq_valid` | Last accepted `SEQ`, and whether one has been seen yet. |

`seq_drops / frames_ok` is the link-loss metric to log; a sustained non-zero
rate means the wiring or the baud rate is wrong, not that the protocol is
misbehaving.

---

## 6. Rate and timing

| Direction | Rate | Rationale |
|-----------|------|-----------|
| TELEMETRY | 1 Hz (optionally up to 10 Hz) | A 40-byte frame at 115200 8N1 takes ≈ 3.5 ms. At 10 Hz that is 3.5 % of the wire — no risk of overrun. |
| MESH_STATUS | 1 Hz | The C3's transmit policy does not need sub-second resolution. |

The link has no handshake and no retransmission: it is a periodic broadcast in
both directions. Loss is handled by the sequence counters, not by ARQ. At 1 Hz
and 256 sequence values a gap is detected within 256 s, which is well inside the
mission requirement.

`RX_OVERRUN` (bit 4 of the MESH_STATUS flags) exists so the RP2040 can tell the
C3 it is overrunning *before* packets are actually lost, rather than only
reporting the damage afterwards.

---

## 7. Versioning

`VER` is `1`. Changing any field's offset, width or scaling requires:

1. bumping `VER` in `uart_telemetry.h`,
2. keeping the old decode path for at least one flight campaign,
3. adding the new payload size to `uart_tlm_payload_len()` **without** removing
   the old one.

Within a version the payloads are **append-only**: new fields go on the end and
`LEN` grows; existing offsets never move. Version 1 rejects **any** `LEN` that is
not the exact fixed size for the type (`ERR_PAYLOAD_SIZE`), in both directions —
see `uart_tlm_encode()` and the `LEN == 0 || LEN > MAX_PAYLOAD` abort in
`uart_tlm_decoder_feed()`.

That is deliberately strict for v1, and it is what the tests pin: a partial
decode would mean guessing at field semantics that no shipped peer has ever
produced, and a 32-byte struct interpreted as a 30-byte one is exactly the class
of bug that is invisible until it corrupts a flight. If a future peer needs
shorter-payload tolerance, it is a **version** decision: add the tolerated size
to `uart_tlm_payload_len()` for the new `VER`, and keep the v1 path exact.


---

## 8. File map

| File | Role |
|------|------|
| `include/uart_telemetry.h` | Protocol constants, payload structs, decoder state, API. |
| `uart_telemetry.c` | Portable core: CRC, encode, decode, re-sync, validation. No target headers. |
| `uart_telemetry_c3.cpp` | ESP32-C3 producer driver (ESP-IDF UART + gps/bmp280/power_manager). Guarded by `UART_TLM_C3_TARGET`. |
| `uart_telemetry_rp2040.cpp` | RP2040 consumer driver (earlephilhower Arduino core). Guarded by `UART_TLM_RP2040_TARGET`. |
| `test/test_uart_telemetry.c` | 105 host assertions; `make test`. |
| `test/Makefile` | Host build of the core + suite. |

### 8.1 Integration checklist

1. `cd tracker/firmware/components/uart_telemetry/test && make test` → `105 passed, 0 failed`.
2. Register the component in the CMakeLists of whichever firmware links it, and
   declare the two guard macros above for the target builds only — the host
   suite must build the core alone, with no ESP-IDF or Pico-SDK headers.
3. C3: call `uart_tlm_c3_init()` once, then `uart_tlm_c3_task_step(&baro)` from a
   1 Hz timer.
4. RP2040: call `uart_tlm_rp_init()` once, then `uart_tlm_rp_task_step()` from
   `loop()`, and wire the radio driver's callbacks to
   `uart_tlm_rp_on_rx_packet()` / `on_tx_packet()` / `on_crc_error()` /
   `set_radio_state()`.
5. Do not multiplex the bench console onto this UART (§1.1).

### 8.2 Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `frames_ok == 0`, `resyncs` climbing | TX/RX crossed, or wrong baud. Re-check GP12/GP13 ↔ GPIO3/GPIO2. |
| `crc_errors` non-zero but `frames_ok` healthy | Marginal link — usually a shared ground or cable length, not a code bug. |
| `len_errors` climbing | A peer is emitting a `LEN` this build does not know. Version mismatch. |
| `seq_drops` non-zero, other counters clean | Frames genuinely being dropped. Check the producer's rate. |
| C3 stuck in `tx_mode = IDLE` | No MESH_STATUS within 5 s, or the RP2040 is not asserting `RADIO_READY | TX_GRANTED`. |
| `RSSI` reads as a huge negative number | Scaling: `rssi_half_dbm` is dBm × 2, not dBm × 10 (§4). |
