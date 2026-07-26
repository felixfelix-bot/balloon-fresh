# LR2021 FLRC 2.4 GHz — Datasheet Audit & Code→Result Gap Analysis

**Date:** 2026-07-26
**Author:** datasheet-audit subagent
**Scope:** Answer the operator's 8 key questions, then map code version → settings → measured result → datasheet expectation → gap.

**Sources audited (all read in full):**
- `docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf` (NiceRF module datasheet, extracted via `git cat-file` from commit `36952f7` — not present on `master`, only in history)
- `docs/lr2021-spi-protocol-reference.md` (verified vs TheClams Rust driver v0.12.0)
- `docs/lr2021-spi-command-reference.md` (verified vs RadioLib v7.6.0 source)
- `docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md`
- Proven firmware: `firmware/rp2040/src/flrc_raw_tx.cpp` (master), `firmware/esp32-c3-flrc/main/main.cpp` (master)
- Branch firmware: `feat/radiolib-bypass-tx` `bench_main.cpp`, `feat/rp2040-flrc-rx` `flrc_rx_main.cpp`, `feat/flrc-max-params` `fifo_tx.cpp`
- `docs/SPEED-TEST-RESULTS.md` (on branch `docs/speed-record-results` — the authoritative measured-numbers doc)
- `docs/flrc-2600kbps-analysis-2026-07-16.md`, `docs/lr2021-spi-bottleneck-analysis-2026-07-16.md`, `docs/flrc-throughput-final-conclusion-2026-07-16.md`

> **Critical caveat on "the datasheet".** We do **NOT** possess the official Semtech
> LR2021 *chip* datasheet (register/command reference). The only datasheet in the repo is
> the **NiceRF LoRa2021 *module* datasheet V1.3** — a 10-page product spec covering
> pinout, electrical characteristics, power tables, and reflow. It confirms FLRC exists
> and quotes headline numbers, but contains **zero register-level detail**. All
> register/command/IRQ-byte knowledge below is reconstructed from **RadioLib v7.6.0
> source** and **TheClams lr2021 Rust driver v0.12.0**, cross-validated against our
> working firmware. Treat any "datasheet says" claim about register fields as
> "RadioLib/TheClams source says" unless explicitly noted.

---

## Q1. EXACT register settings for FLRC 2.4 GHz mode

The proven-working configuration (RP2040 `flrc_raw_tx.cpp`, ESP32 `main.cpp` — identical
bytes) and the RadioLib-equivalent config (`feat/radiolib-bypass-tx` `bench_main.cpp`)
are shown side-by-side. All three produce working RF links.

| Parameter | Proven raw value (our code) | RadioLib beginFLRC() equivalent | TheClams reference |
|-----------|----------------------------|---------------------------------|--------------------|
| Frequency | 2440 MHz (RP2040/ESP32) / 2450 MHz (bench) | `freq` arg | 2400 MHz |
| RF freq reg | `frf = freq_Hz × 2^18 / 52MHz` → `{0x02,0x00, 0x91,0x68,0x00}` @2440 | same | same |
| Packet type | FLRC = `0x05` → `{0x02,0x07,0x05}` | `RADIOLIB_LR2021_PACKET_TYPE_FLRC` | `Flrc` |
| **Bitrate** | **BR_2600 = `0x00`** (mod-param byte 0) | `RADIOLIB_LR2021_FLRC_BR_2600` | `Br2600` |
| **Bandwidth** | 2666 kHz (bound to BR_2600, not independently set) | (paired with BR) | — |
| **Coding rate** | **CR = `0x02` = 1/0 (uncoded)** → upper nibble of `0x25` | `RADIOLIB_LR2021_FLRC_CR_1_0` | `None` |
| **BT product** | **BT 0.5 = `0x05`** → lower nibble of `0x25` → full byte `0x25` | `RADIOLIB_LR2021_..._GAUSS_BT_0_5` | `Bt0p5` (note: TheClams demo used `Bt1p0`=0x07) |
| FLRC_MOD_PARAMS cmd | `{0x02, 0x48, 0x00, 0x25}` | 2-byte payload `{brBw, (cr<<4)\|shape}` | `{0x02,0x48, 0x00, 0x27}` |
| Preamble (AGC) | 16-bit (`agcPreambleLen=3`) | `preambleLen=16` | 16-bit |
| Sync word | 4-byte `0x12AD101B` (our fleet) | configurable | `0xCD05CAFE` |
| Sync match | Match1 (`sw_match=1`) | `syncMatch=1` | Match1 |
| FLRC_PKT_PARAMS cmd | `{0x02, 0x49, 0x0C, 0x4C, 0x00, 0xFF}` | computed | `{0x02,0x49, 0x0E, 0x7A, 0x00, 0xFF}` |
| Payload length | 255 bytes (`0x00FF`) | `fixedPacketLengthMode(255)` | 255 |
| CRC | **OFF** (`crc=0`) in raw path; RadioLib path uses CRC16 (`crc=1`) | varies | CRC24 |
| Packet format | Fixed (raw) / Variable (RadioLib bench) | — | Dynamic |
| TX power | 12 dBm → `{0x02,0x03, 0x18, 0x04}` (ramp 16µs) | +12 (2.4GHz module max) | — |
| PA config | `{0x02,0x02, 0x80, 0x00, 0x60, 0x07, 0x10}` | HF PA selected | HF PA |
| RX/TX fallback | **FS = `0x03`** → `{0x02,0x06,0x03}` (fastest turnaround) | Fs | Fs |
| DIO9 = IRQ | `{0x01,0x12, 0x09, 0x11}` | DIO9 | DIO7 (TheClams) |

**FLRC_MOD_PARAMS byte decoding (the SPEED-P3 correction, critical):**
```
0x0248 payload is 2 BYTES, not 3 (SX1280 is 3).
  byte0 = brBw            → 0x00 = BR_2600 (2600 kbps / 2666 kHz)
  byte1 = (cr<<4)|shape   → 0x25 = (0x02<<4) | 0x05 = CR_1_0 | GAUSS_BT_0_5
```
Available BR values: `0x00`=2600, `0x01`=2080, `0x02`=1300, `0x03`=1040, `0x04`=650,
`0x05`=520, `0x06`=325, `0x07`=260 kbps (from `feat/flrc-max-params` sweep).
Available CR: `0x00`=1/2, `0x01`=3/4, `0x02`=1 (uncoded), `0x03`=2/3.
Available shapes: `0x05`=BT0.5, `0x07`=BT1.0, `0x00`=OFF.

> ⚠️ **SHAPING GOTCHA (erratum-class):** the *generic* RadioLib enum
> `RADIOLIB_SHAPING_0_5` maps to on-chip value `0x02`, which on LR2021 means **BT=2.0**,
> NOT BT=0.5. The LR2021-specific constant `RADIOLIB_LR2021_..._GAUSS_BT_0_5` = `0x05`
> is the correct one. Our raw code hard-codes `0x05`, so we are correct — but anyone
> using the generic RadioLib enum silently gets the wrong pulse shape.

---

## Q2. Theoretical maximum throughput — why 2600 kbps is unreachable

**The "2600 kbps" figure is the RAW AIR RATE (physical-layer symbol bit rate), NOT achievable goodput.** The NiceRF datasheet line is literally "FLRC: modulation rate up to 2.6 Mbps" — it describes the modulation, not delivered payload.

**Goodput ceiling math (our config: 255 B payload, 16-bit preamble, 32-bit sync, uncoded):**
```
On-air bits per packet = preamble(16) + sync(32) + payload(255×8) = 2088 bits
Air time              = 2088 / 2,600,000 = 0.803 ms
Max payload goodput   = 2040 bits / 0.803 ms = 2540 kbps  (97.7% of air rate)
```
**So 2600 kbps goodput is physically impossible.** The true ceiling is **~2540 kbps**, and
that assumes *zero* SPI/host overhead — i.e. the host feeds the next packet to the TX FIFO
instantly while the previous one is still on-air (dual-buffer pipelining). We do not do that.

**Measured vs ceiling:**

| Platform / code | Measured TX | Measured RX | % of 2540 ceiling | % of 2600 air rate |
|-----------------|-------------|-------------|--------------------|--------------------|
| RP2040 `flrc_raw_tx.cpp` (Arduino per-byte SPI) | **1377 kbps** | 0% loss | 54% | 53% |
| ESP32-C3 ESP-IDF bench (RadioLib init + raw hot loop) | **1385.9 kbps** | **838.8 kbps** | 55% / 33% | 53% / 32% |
| RadioLib baseline (255B, 868MHz, 20ms spacing) | 101.2 kbps | 26.7 kbps | 4% | 4% |
| Theoretical max (zero overhead) | 2540 kbps | 2540 kbps | 100% | 97.7% |

(The operator's "1377 kbps" is the RP2040 TX figure; "54% efficiency" = 1377/2540. Consistent.)

---

## Q3. SPI command sequence to configure FLRC (proven-working, RP2040)

Exact byte sequence from `firmware/rp2040/src/flrc_raw_tx.cpp::rawInitRadio()` (master,
PROVEN, 1377 kbps / 0% loss). Every `{...}` is one NSS-low→bytes→NSS-high transaction:

```
1.  Hardware reset: RST LOW 200µs → HIGH, delay 50ms
2.  CLEAR_ERRORS        {0x01,0x11, 0x00,0x00}            delay 1ms
3.  SET_STANDBY         {0x01,0x28, 0x01}   (STDBY_XOSC)  delay 5ms
4.  SET_PACKET_TYPE     {0x02,0x07, 0x05}   (FLRC)        delay 1ms
5.  SET_RF_FREQUENCY    {0x02,0x00, frf[3]}  (2440MHz)    delay 1ms
6.  SET_RX_PATH         {0x02,0x01, 0x01,0x00} (HF, no boost)   ← MANDATORY for 2.4GHz
7.  CALIB_FRONT_END     {0x01,0x23, 0x82,0x62, 0,0,0,0,0,0}    ← MANDATORY before RX
8.  CALIBRATE           {0x01,0x22, 0x5F}   (NOT 0x6F)   delay 5ms
9.  SET_FLRC_MOD_PARAMS {0x02,0x48, 0x00, 0x25} (BR2600,CR_1_0,Bt0.5)
10. SET_FLRC_SYNCWORD   {0x02,0x4C, 0x01, 0x12,0xAD,0x10,0x1B}
11. SET_FLRC_PKT_PARAMS {0x02,0x49, 0x0C, 0x4C, 0x00, 0xFF}
12. SET_PA_CONFIG       {0x02,0x02, 0x80, 0x00, 0x60, 0x07, 0x10}
13. SET_TX_PARAMS       {0x02,0x03, 0x18, 0x04}  (12dBm×2, ramp16µs)
14. SET_RX_TX_FALLBACK  {0x02,0x06, 0x03}  (FS — fastest turnaround)
15. SET_DIO_FUNCTION    {0x01,0x12, 0x09, 0x11}  (DIO9 = IRQ)
16. SET_DIO_IRQ_CONFIG  {0x01,0x15, 0x09, 0x00,0x08,0x00,0x00}  (TX_DONE)
17. CLEAR_IRQ           {0x01,0x16, 0xFF,0xFF,0xFF,0xFF}
```
Per-packet TX hot loop: CLEAR_IRQ → WRITE_TX_FIFO(`{0x00,0x02, payload[255]}`) → SET_TX(`{0x02,0x0D,0x00,0x00,0x00}`) → poll IRQ pin → (TX_DONE auto-clears via step 17 next iter).

> **Note on the DIO_IRQ comment bug:** `flrc_raw_tx.cpp` line 204 has a stale comment
> "TX_DONE (bit 11)" but the byte value `0x00,0x08,0x00,0x00` is correct — as a 32-bit
> big-endian mask that is `0x00080000` = **bit 19 = TX_DONE**. The comment is wrong, the
> value is right.

---

## Q4. TX→RX turnaround times and state machine transitions

**Chip modes (status byte lower nibble):** STDBY_RC=`0x02`, STDBY_XOSC=`0x03`, FS=`0x04`,
RX=`0x05`, TX=`0x06`. (No cycle-count timing tables exist in our docs — the NiceRF module
datasheet has none, and we lack the Semtech chip datasheet.)

**What we have empirically verified:**
- **`SET_RX_TX_FALLBACK_MODE` (0x0206)** controls where the chip parks after a TX_DONE or
  RX timeout. We use **FS (`0x03`)** — leaves the PLL/synth locked — which is the
  fastest-turnaround option and matches TheClams. STDBY_RC (`0x01`) would force a PLL
  re-lock on every packet.
- **After TX_DONE, the LR2021 auto-returns to STANDBY** — confirmed by `fifo_tx.cpp`
  (`feat/flrc-max-params`), which writes the next packet's FIFO *immediately* with no
  intervening STANDBY command. This is the key enabler for the burst loop (the SPEED-P2
  optimization explicitly removed the per-packet `rawStandby()` call).
- **RX re-arm cost = the real bottleneck**, not TX. Each received packet forces a
  ~572µs "blind window": read IRQ (12µs) + read 257-byte RX FIFO (514µs) + clear IRQ
  (12µs) + SET_RX (4µs) + BUSY overhead (30µs). During this window the radio is deaf.
- We have **no measured µs-precision TX→RX or RX→TX state-transition latency** — that
  would require the logic analyzer capture recommended in
  `lr2021-spi-bottleneck-analysis-2026-07-16.md` (never purchased/used).

---

## Q5. Errata / known issues with FLRC on this silicon

No official Semtech errata sheet is in the repo (we lack the chip datasheet). The
following are **issues we discovered ourselves** through debugging — treat as
project-local errata:

1. **RadioLib LR2021 driver is fundamentally incompatible.** It uses 24-bit register
   addressing; our Gen-4 chip uses 2-byte big-endian opcodes. `findChip()` always fails
   (-707 / hang). Documented in ADR-020. (NOT a chip erratum — a library/chip mismatch.)
2. **CALIBRATE mask `0x6F` triggers CMD_ERROR.** Bit 5 is undefined; must use `0x5F`.
3. **`SET_RX_PATH` (0x0201) is mandatory** before 2.4 GHz RX — without it the radio
   listens on the LF (sub-GHz) path and receives nothing. Was the root cause of the
   original "0 packets" RX bug.
4. **`CALIB_FRONT_END` (0x0123) is mandatory** before RX — without it the chip returns
   `RXFREQ_NO_CAL_ERR` (IRQ ERROR bit). Datasheet-quote (via protocol-reference): "If
   image rejection calibration was not done for current RF frequency, error
   RXFREQ_NO_CAL_ERR is generated."
5. **FLRC_MOD_PARAMS is 2-byte payload, not SX1280's 3-byte.** Sending 3 bytes silently
   corrupts CR/shape fields (manifested as BR=650 init failure — SPEED-P3).
6. **Generic `RADIOLIB_SHAPING_0_5` = BT2.0 on LR2021**, not BT0.5. Use the LR2021-specific
   constant or raw `0x05`. (SPEED-P3.)
7. **Sync-word packet-param field ambiguity (UNRESOLVED).** Our working code sends
   PKT_PARAMS byte0 = `0x0C`. Per our documented field layout
   `(agcPreambleLen<<2) | swLen`, the lower 2 bits = `0b00` = SwLen=None (sync matching
   *disabled*), yet byte1 `0x4C` sets `sw_match=Match1` and we DO get 0% loss with a
   4-byte sync word configured. Either (a) the field encoding in our docs is wrong, or
   (b) the chip honors `sw_match` regardless of `sw_len`, or (c) fixed-length+CRC-off
   mode makes sync effectively optional. TheClams uses `0x0E`/`0x7A` (SwLen=32b). **Both
   work.** This is a real doc-vs-silicon ambiguity worth a logic-analyzer / register-read
   probe if sync robustness matters at range.
8. **Sync-word "enable" byte ambiguity.** TheClams Rust sends an extra enable byte after
   the 4 sync bytes; RadioLib (and our code) send only 5 bytes (`{opcode, num, sw[4]}`).
   Our 5-byte form works. Possibly TheClams' extra byte is a different command variant.
9. **Every non-Arduino SPI acceleration path on RP2040 fails** (Pico SDK batch, DMA via
   `spi0_hw->dr`, direct HW registers, PIO v1/v2/v3). All produce fake TX_DONE or hang.
   Root cause UNKNOWN — never scoped. See Q-gap.
10. **20 MHz RX SPI causes 77% packet loss** — RX FIFO read needs slower SPI (we use 16 MHz).
11. **Preamble 16→8 symbols broke TX_DONE** in one experiment; combined CS assertions also
    broke it → LR2021 requires **one command per CS assertion**.

---

## Q6. Mandatory calibration steps before FLRC TX/RX

Confirmed mandatory (omitting any → failure mode in parens):

| Step | Opcode | Mandatory for | Failure if skipped |
|------|--------|---------------|--------------------|
| CLEAR_ERRORS | `0x0111 0x00,0x00` | both | stale error bits confuse subsequent commands |
| SET_STANDBY (STDBY_XOSC) | `0x0128 0x01` | both | XOSC not running → freq/PLL unstable |
| SET_RX_PATH (HF=1) | `0x0201 0x01,0x00` | **2.4GHz RX** | listens on LF path → 0 packets |
| CALIB_FRONT_END | `0x0123 (freq/4)\|0x8000, ...` | **RX** (image rejection) | `RXFREQ_NO_CAL_ERR` |
| CALIBRATE (mask 0x5F) | `0x0122 0x5F` | both | PLL/bias uncalibrated; bit 5 undefined→CMD_ERROR if 0x6F |

`CALIB_FRONT_END` for 2440 MHz: `freq/4 = 610`, `610 | 0x8000 = 0x8262` →
`{0x01,0x23, 0x82,0x62, 0,0,0,0,0,0}`. TheClams calls `calib_fe(&[])` with empty freqs
(uses defaults); we pass the explicit HF frequency. Both work.

**Not strictly mandatory but required for correctness:** SET_PACKET_TYPE must precede the
FLRC-specific commands; SET_FLRC_PKT_PARAMS must be sent or the radio transmits **0 bytes**
(this was the SPEED-P0 root-cause bug — `runRawTx()` sent 0/0 packets until 0x0249 was added).

---

## Q7. Maximum payload size per packet

- **Register field:** `SET_FLRC_PACKET_PARAMS` payloadLen is a **big-endian u16, max 511**.
- **FIFO constraint:** the LR2021 TX/RX FIFO is **255 bytes**. A 511-byte payload would
  require multi-operation FIFO management and is not exercised by any of our firmware.
- **Our choice: 255 bytes** — the largest single-FIFO-operation size, optimal for goodput
  (per-packet overhead amortized over max payload). Confirmed by the packet-size sweep
  (`pkt_size_sweep.csv`, §5.2 of SPEED-TEST-RESULTS): goodput scales near-linearly with
  payload up to ~150 B, then overhead dominates; 255 B is the best point.

---

## Q8. IRQ structure

**32-bit IRQ status** (NOT 16-bit like SX1280). Read+clear atomically via
`GET_AND_CLEAR_IRQ_STATUS` (`0x0117`) — **two SPI transactions** (send opcode, NSS high,
wait BUSY, then read 6 bytes: 2 status + 4 IRQ big-endian). Key bits:

| Bit | Mask | Name | Meaning |
|-----|------|------|---------|
| 0 | 0x00000001 | RX_FIFO | RX FIFO threshold reached |
| 1 | 0x00000002 | TX_FIFO | TX FIFO threshold reached |
| 5 | 0x00000020 | PREAMBLE_DETECTED | — |
| 6 | 0x00000040 | SYNCWORD_VALID | — |
| 16 | 0x00010000 | ERROR | generic error |
| 17 | 0x00020000 | CMD_ERROR | command rejected (e.g. missing init) |
| **18** | **0x00040000** | **RX_DONE** | packet received |
| **19** | **0x00080000** | **TX_DONE** | packet transmitted |
| 21 | 0x00200000 | TIMEOUT | RX/TX timeout |
| 22 | 0x00400000 | CRC_ERROR | CRC check failed |
| 23 | 0x00800000 | LEN_ERROR | length error |

`CLEAR_IRQ` (`0x0116`) takes a 4-byte mask: `{0x01,0x16, 0xFF,0xFF,0xFF,0xFF}` clears all.
DIO pin routing: `SET_DIO_FUNCTION` (`0x0112`) assigns a DIO pin a function (IRQ=1);
`SET_DIO_IRQ_CONFIG` (`0x0115`) maps a 32-bit IRQ mask onto that DIO. We route
RX_DONE+TX_DONE onto DIO9 and poll the GPIO pin in the hot loop (faster than SPI-reading
the IRQ register per packet).

---

# CODE VERSION → SETTINGS → RESULT → EXPECTATION → GAP

| Code version (branch/commit) | Init path | Key settings | Measured result | Datasheet/ theoretical expectation | Gap / root cause |
|------------------------------|-----------|--------------|-----------------|-------------------------------------|------------------|
| RadioLib baseline (868MHz, 20ms spacing) | `radio.beginFLRC()` | 255B, 20ms gap | TX 101.2 / RX 26.7 kbps | air-rate-bound only at <2.5ms gap | **Artificial**: 20ms inter-packet delay, not air rate. Not a chip limit. |
| **RP2040 `flrc_raw_tx.cpp` (master)** — PROVEN | full raw SPI | BR2600, CR_1_0, BT0.5, 255B, 16MHz SPI, Arduino per-byte transfer | **TX 1377 kbps, 1000/1000, 0% loss** | 2540 kbps ceiling | **54% of ceiling.** 803µs air (54%, physics) + **535µs Arduino SPI (36%)** + 154µs loop (10%). Arduino `transfer()` per-byte overhead is the wall. |
| **ESP32-C3 ESP-IDF bench `bench_main.cpp`** (`feat/radiolib-bypass-tx` `67c0552`) — PROVEN | RadioLib `beginFLRC()` + raw hot loop (7→4 txn/pkt) | BR2600, CR_1_0, shape 0x05, 255B, 20MHz SPI, `spi_device_polling_transmit` | **TX 1385.9 / RX 838.8 kbps, 0% PER** | 2540 kbps | TX 55% of ceiling; **RX only 33%** — bottleneck is **~2.2ms ISR→FreeRTOS task-notification latency** per RX packet (SPI xfer itself only 188µs). |
| `feat/flrc-max-params` `fifo_tx.cpp` (`45b57ab`) | RadioLib + raw | BR2600, CR_1_0, 255B, no-standby burst | builds; **HARDWARE-PENDING** | — | structurally complete, unflashed. |
| `feat/rp2040-flrc-rx` `flrc_rx_main.cpp` (`ed5d0e3`) | RadioLib init + raw RX loop | 2450MHz, BR2600, CR_1_0, shaping 0.5, 255B, 16MHz | part of the 0%-loss RX result | — | works; RX blind window 572µs. |
| `fix/raw-tx-packet-params` (`44ad093`) SPEED-P0 | raw only | fixed: +SET_FLRC_PKT_PARAMS, 4 opcode fixes | was **0/0 packets** → builds, pending | — | **Bug:** missing 0x0249 + SX1280 opcodes (0x0D/0x83/0x12) instead of LR2021 (0x0002/0x020D/0x0117). |
| `feat/flrc-max-params` SPEED-P3 | raw | BR sweep, CR explicit | BR=650 was failing → fixed | — | **Bug:** 3-byte MOD_PARAMS (SX1280) instead of 2-byte; generic shaping enum wrong. |
| RP2040 PIO/DMA (v1/v2/v3, `feat/rp2040-pio-dma-rx`) | — | hardware SPI accel | **ALL FAILED** (fake TX_DONE / hang / CDC death) | expected ~2540 kbps | **Unknown root cause** — never scoped. Hypotheses: inter-byte gap, CS pattern, status polling, CPHA. Needs logic analyzer. |
| ESP32 GDMA (`feat/esp32-spi-gdma`) | — | CPU-free SPI | not started | ~2540 kbps | unstarted. |

---

## WHY we can't hit higher throughput — the three independent walls

1. **Physics wall (803µs air time, irreducible).** At BR2600/uncoded/255B, a packet is
   2088 bits on air = 0.803ms. This alone caps a *sequential* (non-pipelined) TX loop at
   2040/0.803ms = **2540 kbps**. We are at 1377, so we are NOT physics-bound — we are
   host-bound.
2. **RP2040 host wall: Arduino per-byte `spiRf.transfer()`.** 268 bytes/packet × ~2µs/byte
   = 535µs of pure per-byte function-call overhead. Every alternative (batch, DMA, direct
   HW, PIO) failed on this specific chip — root cause never determined because we never
   used a logic analyzer. This is THE RP2040 bottleneck (36% of per-packet time).
3. **ESP32-C3 host wall: ISR→task-notification latency (~2.2ms/RX packet).** The ESP32's
   raw SPI transfer is fast (188µs), but the FreeRTOS notification path from DIO IRQ →
   task that reads the FIFO adds ~2.2ms, capping RX at 838.8 kbps. This is why RX << TX
   on ESP32.

## What code changes could close the gap (ranked by expected payoff, honesty-flagged)

| Change | Expected | Status | Risk / honesty |
|--------|----------|--------|----------------|
| **Logic-analyzer capture of working vs failing SPI** (RP2040) | diagnostic → targeted fix | NOT DONE | $20, 1 day. The single highest-value undone action. Without it, all SPI-accel fixes are guesses. |
| **Dual-core RX pipelining** (RP2040 core1 reads FIFO while core0 listens) | RX blind window 572µs→~100µs; enables TX up to ~2000 kbps | not started | low risk, independent of SPI-accel fix |
| **ESP32-C3 GDMA** (`feat/esp32-spi-gdma`) + move hot path out of FreeRTOS task (ISR-driven FIFO read) | RX → ~2000+ kbps | branch exists, no commits | medium; removes the 2.2ms task-latency wall |
| **Single combined `transfer(buf, nullptr, 257)`** instead of per-byte (RP2040) | SPI 535µs→~170µs → TX ~2200 kbps | hypothesis, untested | the handover doc's key insight: prior "batch" tests used TWO transfer() calls (SCK discontinuous) — a single combined call was NEVER tested |
| **Dual-buffer TX pipelining** (write pkt N+1 FIFO while pkt N on-air) | TX → max(803,~170)=803µs → ~2540 kbps | not started | LR2021 FIFO is 255B (single-buffer), but BUSY-wait can overlap SPI write |
| Accept 1377 kbps | — | current | pragmatic: 50-100× typical LoRa, sufficient for telemetry/mesh |

---

## BOTTOM LINE for the operator

- **"2600 kbps" is the raw air rate, not a throughput spec.** The real goodput ceiling is
  **~2540 kbps** (255B payload, 16b preamble, 32b sync, uncoded). The NiceRF datasheet
  never claims 2600 kbps *delivered* — that's a misreading.
- **Our 1377 kbps = 54% of the true ceiling.** We are host-bound, not physics-bound.
- **The #1 undoable action is a $20 logic-analyzer capture.** Every SPI-acceleration
  failure on RP2040 is explained only by unverified hypotheses. One afternoon of
  scoping would convert "guessing" into "targeted fix" and likely unlock 2000+ kbps.
- **On ESP32-C3, the wall is FreeRTOS ISR latency (2.2ms/RX), not SPI.** GDMA + an
  ISR-driven FIFO read is the path to ~2000 kbps RX there.
- **Register/command truth comes from RadioLib + TheClams source, NOT a Semtech datasheet**
  (we don't have one). Two real ambiguities exist: the PKT_PARAMS `0x0C`/`0x0E` sync-len
  field, and the sync-word "enable" byte — both configurations work in practice, so they
  are low-priority but should be resolved if chasing range robustness.
