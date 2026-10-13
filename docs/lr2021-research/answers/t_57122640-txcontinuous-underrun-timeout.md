# LR2021 — TXContinuous / infinite-TX mode, FIFO underrun and timeout behaviour

Task: `t_57122640` — "Answer: TXContinuous / infinite-TX mode, underrun and timeout behaviour"
Date: 2026-10-01 · Board: tollgate · Worker: worker-base · Branch: `pr/lr2021-txcontinuous`
Corpus home: `docs/lr2021-research/` in `felixfelix-bot/balloon-fresh`.

**Bottom line (one line): `TXContinuous` via `SET_TX_PARAMS` = NO; continuous/infinite TX is reachable via `SetTxTestMode` (0x020E) modes `0x01`/`0x02`; Tx-FIFO-underrun device *action* = UNKNOWN (only the flag/IRQ is documented); TX watchdog = configurable 24-bit `tx_timeout` (≤512 s, 0 disables).**

## Sources (path prefixes used throughout)

| Tag | Source |
|---|---|
| **DS** | `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` — Semtech LR2021/LR2022/LR2012 Final Datasheet **Rev 2.2** (DS.LR20xx, 29/07/26, 250 pp). Section/table numbers below are the **v2.2** numbering. |
| **DRV** | Semtech official LR20xx driver (vendored), `~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/` (v1.3.1; inventoried at `docs/lr2021-research/local-inventory.md` §2) |
| **RAL** | same repo, `.../Radio/radio_hal/ral_lr20xx.h` |
| **LIB** | RadioLib snapshot, `docs/lr2021-research/radiolib-master/LR2021-module/` (master @75e486a5) |
| **HW** | first-party raw-SPI driver, `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_spi.h` |
| **ERRATA** | `docs/lr2021-research/errata/` (datasheet §22 known-limitations, Semtech USP known-limitations, RadioLib issue index) |

Notation: `file:line` = line number in that file; `§` / `Table` = datasheet section/table in the Rev 2.2 PDF.

---

## 1. TXContinuous — is there a continuous / infinite TX mode, and is it in SET_TX_PARAMS?

**Answer: NO via `SET_TX_PARAMS` (0x0203). YES via a separate command `SetTxTestMode` (0x020E).**

### 1.1 `SET_TX_PARAMS` (0x0203) — every field enumerated; **no** continuous/infinite bit

`SET_TX_PARAMS` carries **exactly two parameter bytes** and neither selects TX length/mode:

- **DS §7.4.3 "SetTxParams", Table 7-23** (p.147):
  > "The SetTxParams command sets the Transmit (Tx) power and ramp time of the Power Amplifier (PA)."
  > Byte layout (verbatim): `0x02 | 0x03 | tx_power(7:0) | ramp_time(7:0)`
  > "`tx_power` sets the Tx power at PA output (HF or LF) in +0.5dB steps… `ramp_time` sets the ramp time for both PAs…" (Table 7-24 ramp table, 2 µs … 304 µs).
- **DRV `src/lr20xx_radio_common.c:288-299`** — `lr20xx_radio_common_set_tx_params()` writes exactly `{0x02, 0x03, power_half_dbm, ramp_time}`; opcode constant `LR20XX_RADIO_COMMON_SET_TX_PARAMS_OC = 0x0203` at `:121`; length `( 2 + 2 )` at `:78`. Header decl `inc/lr20xx_radio_common.h:201-202`. **No mode/length/continuous parameter exists in either the datasheet layout or the driver.**
- **LIB `LR2021_commands.h:70`**: `#define RADIOLIB_LR2021_CMD_SET_TX_PARAMS (0x0203)` (opcode only; no continuous field anywhere in the module's TX-params handling).
- **HW `lr2021_spi.h:174`**: `static const uint8_t OP_SET_TX_PARAMS[] = {0x02, 0x03};` — the first-party driver declares only the 2 opcode bytes and never populates a continuous field.

⇒ **The `TABLE 7-23` bit/field set is `{tx_power, ramp_time}` only. There is no "continuous", "infinite", "unbounded", or "CW" bit/field in `SET_TX_PARAMS`.** (Cross-checks the earlier enumeration in card `t_e00b32dc`.)

### 1.2 The actual continuous-TX command: `SetTxTestMode` (0x020E)

Continuous / infinite TX **is** reachable — as a dedicated command, not a `SET_TX_PARAMS` field:

- **DS §21.2 "SetTxTestMode", Table 21-2** (p.231): wire frame `0x02 | 0x0E | mode(7:0)`, with modes quoted verbatim:
  > "`0x00`: Normal Tx (same as a SetTx(0))"
  > "`0x01`: Infinite preamble (not available in LR-FHSS)"
  > "`0x02`: Continuous wave (not available in LR-FHSS)"
  > "`0x03`: PRBS9, Pseudo Random Bit Sequence (not available in LoRa/LR-FHSS)"
- **DS §4.4.5 "Transmit (Tx)"** (p.76-77), Tx sub-modes, quoted verbatim:
  > "**Continuous Wave (CW) Mode:** In CW mode, the carrier frequency is transmitted indefinitely until another command is issued to change the mode. This mode is useful for generating continuous RF signals without any data modulation, and it is often utilized for testing and signal generation purposes."
  > "**Infinite Preamble Mode:** In infinite preamble mode, an infinite preamble of the configured modulation is continuously output on the RF (Radio Frequency)."
- **DS Table 21-1 "ETSI Test Signals"** (p.230) names the regulator-facing commands explicitly:
  > D-M1 = "Unmodulated carrier — Tx CW mode (**SetTxCw(...)** command)"
  > D-M2 = "Continuously modulated signal with the greatest occupied RF bandwidth — Continuous modulation (**SetTxInfinitePreamble(...)** command)"
- **Enabling bit/field:** the `mode(7:0)` byte of `SetTxTestMode`; `0x01` = infinite preamble, `0x02` = continuous wave. There is **no enable bit elsewhere** — the mode byte *is* the selector.
- **How to invoke (driver layers):**
  - **DRV**: enum `LR20XX_RADIO_COMMON_TX_TEST_MODE_INFINITE_PREAMBLE = 0x01`, `LR20XX_RADIO_COMMON_TX_TEST_MODE_CONTINUOUS_WAVE = 0x02`, `LR20XX_RADIO_COMMON_TX_TEST_MODE_PRBS9 = 0x03` — `inc/lr20xx_radio_common_types.h:230-234`; impl `lr20xx_radio_common_set_tx_test_mode()` at `src/lr20xx_radio_common.c:491-501`; opcode `LR20XX_RADIO_COMMON_SET_TX_TEST_MODE_OC = 0x020E` at `:131`.
  - **RAL**: thin aliases `ral_lr20xx_set_tx_cw()` (`ral_lr20xx.h:200`) and `ral_lr20xx_set_tx_infinite_preamble()` (`ral_lr20xx.h:205`) — these are the driver names behind the datasheet's `SetTxCw(...)` / `SetTxInfinitePreamble(...)`.
  - **LIB**: `setTxTestMode(uint8_t mode)` → `SPIcommand(RADIOLIB_LR2021_CMD_SET_TX_TEST_MODE, …)` (`LR2021_cmds_misc.cpp:31-33`); opcode `0x020E` (`LR2021_commands.h:146`); constants `TX_TEST_MODE_INF_PREAMBLE (0x01)`, `TX_TEST_MODE_CW (0x02)`, `TX_TEST_MODE_PRBS9 (0x03)` (`LR2021_commands.h:527-530`). RadioLib's raw/direct transmit goes straight to CW: `transmitDirect()` ends with `return(setTxTestMode(RADIOLIB_LR2021_TX_TEST_MODE_CW));` (`LR2021.cpp:396`).

### 1.3 Cross-checks for other "continuous TX" paths

| Candidate path | Verdict | Evidence |
|---|---|---|
| `SET_TX_PARAMS` length=0 / 0xFFFF convention | **NO / not applicable** | `SET_TX_PARAMS` has **no length field at all** (DS Table 7-23; DRV `lr20xx_radio_common.c:288-299`). Frame/payload length lives in the packet-params command, not here. |
| `SET_TX` (0x020D) payload length = 0 or 0xFFFF | **NO continuous path documented** | `SET_TX` takes only a 24-bit `tx_timeout` (DS §6.3.6 Table 6-12). `0x020E mode 0x00` is explicitly "Normal Tx (**same as a SetTx(0)**)" — i.e. `SetTx(0)` is *normal single-packet TX*, not continuous. No 0/0xFFFF length convention is documented for continuous modulation. |
| `SET_TX` `tx_timeout = 0` | **Removes the watchdog only** | DS §6.3.6: "`0x000000`: Disables the timeout function during Tx mode." This is still fixed-length *packet* TX; it does not make the modulation continuous. |
| Dedicated CW / continuous-modulation command | **YES** | `SetTxTestMode` 0x020E modes `0x01` / `0x02` (§1.2). |
| PA ramp / TX timeout fields select continuous | **NO** | `ramp_time` is PA ramp-up time only (DS Table 7-24); `tx_timeout` is a watchdog (DS §6.3.6). |
| PRBS9 continuous modulated test signal | **YES (modulated)** | `SetTxTestMode mode 0x03` (DS §21.2; DRV `lr20xx_radio_common_types.h:233`). |

**TXContinuous verdict: YES (via `SetTxTestMode` 0x020E, `mode` = 0x01 infinite preamble or 0x02 continuous wave); NOT in `SET_TX_PARAMS`.**

---

## 2. Underrun behaviour — what happens when the TX FIFO runs dry

**Answer: the *flag* and *IRQ* are documented; the device *action* (abort vs pad vs stall) is UNKNOWN (undocumented).**

### 2.1 What IS documented

- **DS §5.3.2 "Tx Data FIFO"** (p.78), verbatim:
  > "In transmit mode, the LR2021/LR2022/LR2012 requires that the data to be sent is written into the Tx data FIFO using the WriteRadioTxFifo command. The level of the Tx FIFO is continuously monitored to trigger specific interrupts). Status information in the ConfigFifoIrq command includes `tx_low_threshold`, `tx_high_threshold` and FIFO flags `FifoUnderflow`, `FifoEmpty`, `FifoFull`, and `FifoOverflow`."
  > "For payloads superior to 256 bytes, the Tx FIFO has to be written when data is being transmitted, **avoiding an underflow of the Tx FIFO**, using the threshold informations available through the API or the DIOs."
- **FIFO size**: 256 bytes default, extendable to 1024 bytes both FIFOs — **DS §5.3.3 "Extending the Data FIFOs"**: "The default size of both the RX and TX FIFO is 256 bytes. The LR20xx drivers also expose a set of functions that move the FIFOs to a larger memory region, allowing both FIFOs to reach 1024 bytes in size."
- **IRQ mask / flag bits (exact names & bits, verbatim):**
  - **DS §6.10.1 "ConfigFifoIrq", Table 6-50** (p.126): `tx_fifo_irq_enable` "defines for all bits set in this parameter, the corresponding Tx FIFO flag that triggers the **TxFifo IRQ**." Available FIFO flags quoted verbatim:
    > "`0x01`: FifoEmpty / `0x02`: FifoLow / `0x04`: FifoHigh / `0x08`: FifoFull / `0x10`: FifoOverflow / `0x20`: **FifoUnderflow**"
  - **DRV** `inc/lr20xx_radio_fifo_types.h:69-76` — enum `lr20xx_radio_fifo_flag_e`:
    `LR20XX_RADIO_FIFO_FLAG_EMPTY = (1<<0)`, `_FLAG_THRESHOLD_LOW = (1<<1)`, `_FLAG_THRESHOLD_HIGH = (1<<2)`, `_FLAG_FULL = (1<<3)`, `_FLAG_OVERFLOW = (1<<4)`, **`LR20XX_RADIO_FIFO_FLAG_UNDERFLOW = (1<<5)`** (i.e. mask `0x20`, bit 5).
  - Related global host interrupts (different register, for reference), **DS Table 5-20 "Host Interrupts (Sheet 2 of 2)"** (p.99): `Bit 19 = TxDone — "Packet transmission completed"`; `Bit 21 = Timeout — "Rx or Tx timeout"`.
- **Readout of the flags without IRQ**: **DS §6.10.2 "GetFifoIrqFlags"** (p.127) — "retrieves all FIFO flags that have been triggered since the last clear operation… independent of whether the corresponding IRQs are enabled or not." (Clear via §6.10.3/§6.10.4.)

### 2.2 What is NOT documented → UNKNOWN

- **Device action on Tx-FIFO underrun during continuous/infinite TX: UNKNOWN.**
  The datasheet only instructs the host to *avoid* underflow (§5.3.2) and exposes an underflow *flag/IRQ* (§6.10.1). It does **not** state whether, on underrun, the radio **aborts** the transmission, **pads/repeats** the last byte, or **stalls**.
- Searched with no result: datasheet §5.3.2, §6.10.1-6.10.8; driver sources; the **ERRATA** corpus (`errata/semtech-datasheet-v2.2-section22-known-limitations-and-workarounds.txt`, `errata/semtech-usp-doc-KNOWN_LIMITATIONS.md`, `errata/radiolib-lr2021-issue-index.txt`, `errata/radiolib-lr2021-limitation-excerpts.txt`) — **no** statement on Tx-FIFO-underflow action.
- **Note (naming):** there is **no** dedicated 32-bit global IRQ bit named "underflow"; underflow is surfaced only through the **FIFO-flag** mechanism (`FifoUnderflow = 0x20`) and the **`TxFifo IRQ`** it can trigger via `tx_fifo_irq_enable`. Any UAPI/IRQ name for the FIFO IRQ is the per-command `TxFifo` IRQ, not a Table-5-20 host bit.

**Underrun verdict: IRQ/flag = documented (`FifoUnderflow` bit `0x20`, routed through `tx_fifo_irq_enable` → `TxFifo IRQ`); physical action (abort/pad/stall) = UNKNOWN.**

---

## 3. Timeout limits — TX watchdog / maximum TX duration

**Answer: a configurable TX watchdog exists — the 24-bit `tx_timeout` on `SET_TX` (0x020D), ≤512 s, `0x000000` disables it; on expiry a `Timeout` IRQ fires and transmission is stopped.** No *fixed* hardware maximum TX duration is documented.

### 3.1 `SET_TX` `tx_timeout` (0x020D)

- **DS §6.3.6 "SetTx", Table 6-12** (p.106), verbatim:
  > "The SetTx command activates the radio's Tx mode, initiating RF packet transmission, and starting the RTC with the specified `tx_timeout` value."
  > Frame: `0x02 | 0x0D | tx_timeout(23:16) | tx_timeout(15:8) | tx_timeout(7:0)`
  > "`tx_timeout` is expressed in periods of the 32 kHz RTC (Real-Time Clock) and **can have a maximum value of 512 seconds**."
  > "`0x000000`: **Disables the timeout function during Tx mode.** Tx timeout can be used as a safeguard in case transmission fails and TxDone interrupt never occurs."
  > "If the RTC event fires before the transmission completion, **a Timeout IRQ is triggered, and the transmission is stopped prematurely**."
  > "After a Timeout IRQ or TxDone IRQ, the device returns to one of the following modes defined by the command SetRxTxFallbackMode (Standby RC, Standby XOSC or FS mode)."
- **Configurable vs fixed: CONFIGURABLE.** Set per-`SetTx`, or defaulted via **`SetDefaultRxTxTimeout` (0x0215) — DS §6.3.17 / Table 6-25**: "configures the default Rx and Tx timeouts… `rx_timeout` and `tx_timeout` … expressed in periods of the 32.768 kHz RTC"; `SET_TX`: "`tx_timeout` is optional. If not explicitly set, the value configured with the SetDefaultRxTxTimeout command is used."
- **IRQ:** `Timeout` — global host IRQ **Bit 21**, "Rx or Tx timeout" (DS Table 5-20, p.99). (Distinct from `TxDone` = Bit 19.)
- **DRV** `inc/lr20xx_radio_common.h:363` `lr20xx_radio_common_set_tx(context, timeout_in_ms)`; `:365-381` `lr20xx_radio_common_set_tx_with_timeout_in_rtc_step()` with verbatim remark: "Maximal timeout value is 0xFFFFFF, which gives a maximal timeout of 511 seconds. **If `timeout_in_rtc_step` is set to 0, then no timeout is used.**"
- **Discrepancy flagged:** the datasheet says the max is **512 s** (DS §6.3.6) while the driver header says **511 s** for `0xFFFFFF` (`lr20xx_radio_common.h:371`). Both agree the ceiling is 0xFFFFFF / 0x000000 = disabled; the ±1 s is an off-by-one in the docs, not a behaviour difference.

### 3.2 Does a watchdog apply to `SetTxTestMode` (CW / infinite preamble)?

**UNKNOWN.** `SetTxTestMode` carries only `mode(7:0)` (DS Table 21-2) — **no timeout parameter**. CW/infinite-preamble duration is defined as "transmitted indefinitely until another command is issued to change the mode" (§4.4.5). Whether the `SET_TX`/`SetDefaultRxTxTimeout` watchdog also governs test mode is **not documented** → UNKNOWN.

### 3.3 Other limits

- No **fixed** maximum TX duration or hardware watchdog beyond the configurable `tx_timeout` is documented anywhere in §6.3.6, §6.3.17, or §22 (known limitations). The `tx_timeout` is explicitly described as a *host-chosen safeguard*, confirming it is configurable, not fixed.

**Timeout verdict: configurable 24-bit `tx_timeout`, max 0xFFFFFF (≤512 s), `0x000000` = disabled; expiry → `Timeout` IRQ (Bit 21) + premature stop + return to `SetRxTxFallbackMode` target. Applicability to `SetTxTestMode` = UNKNOWN.**

---

## Acceptance summary

| Question | Verdict | Citation |
|---|---|---|
| TXContinuous reachable via `SET_TX_PARAMS`? | **NO** — only `{tx_power, ramp_time}` | DS §7.4.3 Table 7-23; DRV `lr20xx_radio_common.c:288-299,121`; LIB `LR2021_commands.h:70`; HW `lr2021_spi.h:174` |
| Continuous/infinite TX reachable at all? | **YES** — `SetTxTestMode` 0x020E `mode`=0x01/0x02 | DS §21.2 Table 21-2; §4.4.5; DRV `lr20xx_radio_common_types.h:230-234`, `lr20xx_radio_common.c:491-501,131`; LIB `LR2021.cpp:396`, `LR2021_commands.h:146,527-530`; RAL `ral_lr20xx.h:200,205` |
| Underrun action (abort/pad/stall)? | **UNKNOWN** (flag/IRQ documented, action not) | DS §5.3.2, §6.10.1; ERRATA corpus (no statement) |
| Underrun IRQ bit name/mask? | `FifoUnderflow` = **0x20** (bit 5), via `tx_fifo_irq_enable` → **`TxFifo IRQ`** | DS §6.10.1 Table 6-50; DRV `lr20xx_radio_fifo_types.h:75` |
| TX timeout limit / configurable? | **Configurable** 24-bit `tx_timeout`, ≤512 s (0xFFFFFF), `0x000000`=disabled; expiry → `Timeout` IRQ Bit 21 | DS §6.3.6 Table 6-12, §6.3.17, Table 5-20; DRV `lr20xx_radio_common.h:365-381` |
| Watchdog applies to test mode? | **UNKNOWN** | DS Table 21-2 (no timeout field); §4.4.5 |
