# LR2021 — does SET_AUTO_RX_TX (0x0211) support an auto-TX FIFO trigger?

Task: `t_84477ffe` — "Answer: does SET_AUTO_RX_TX (0x0211) support auto-TX FIFO trigger?"
Date: 2026-10-01 · Board: tollgate · Worker: worker-base · Branch: `pr/lr2021-auto-tx-trigger`
Corpus home: `docs/lr2021-research/` in `felixfelix-bot/balloon-fresh`.

**Bottom line (one line): NO — `SET_AUTO_RX_TX` (0x0211) cannot start a transmission on a TX-FIFO threshold crossing; its only documented triggers are the radio-operation events `RxDone` / `TxDone` (plus `TxTimeout`/`RxTimeout` for disabling), and the TX-FIFO thresholds (`tx_low_threshold`, `tx_high_threshold`) feed *only* the `ConfigFifoIrq` IRQ path, which never changes radio mode. TX is started only by `SET_TX` (0x020D) or `SetTxTestMode` (0x020E).**

## auto-TX trigger

### Verdict

| Question (task step) | Verdict | Enabling field | Citation |
|---|---|---|---|
| 1. Does 0x0211 contain any field that enables auto-**TX**? | **YES — auto-TX exists, but only as "Tx after an RxDone"** | `Mode(6:0)`, byte 2 bits 6:0 = `0x1` (`AUTO_MODE_ALWAYS`) / `0x2` (`AUTO_MODE_OK`) | DS §6.3.9, Table 6-15 (p.108); DS Rev 2.1 §6.3.9, Table 6-15 (p.104); DRV `inc/lr20xx_radio_common_types.h:318-325` |
| 2. Can that auto-TX be **triggered by a TX-FIFO threshold crossing**? | **NO** | — (no such field, and no such trigger path) | DS Table 6-15 + §6.3.9 prose (p.108); §6.10.1 Table 6-50 (p.126); §5.7 Table 5-20 (p.99); AN1200.104 §2.4.4 (p.9) |
| 3. FIFO-threshold semantics / range / unit | `tx_low_threshold(15:0)` / `tx_high_threshold(15:0)`, counted in **bytes of Tx-FIFO fill**; ≥0–256 usable without the 1024-byte-FIFO workaround; range above that partly UNKNOWN | `tx_fifo_irq_enable(7:0)`, `tx_high_threshold(15:0)`, `tx_low_threshold(15:0)` | DS §6.10.1 Table 6-50 (p.126); §5.3.2 (p.79); §6.10.6 Table 6-58/6-59 (p.129); §5.3.3.1.2 (p.80); DRV `src/lr20xx_radio_fifo.c:181-202` |
| 4. One-shot or re-arming? | `SET_AUTO_RX_TX` = **ONE-SHOT, must be re-enabled**; the FIFO-threshold IRQ = **edge-triggered, re-arms on each threshold crossing** | — | DS §6.3.9 (p.108) "can only be triggered once, and must be re-enabled"; DRV `inc/lr20xx_radio_common.h:499-500`; DRV `inc/lr20xx_radio_fifo.h:143-146` |

**Trigger that 0x0211 actually accepts (the complete, documented set):** an `RxDone` event (→ automatic Tx), a `TxDone` event (→ automatic Rx), and — only when the `clear` bit is set — a `TxTimeout`, an `RxTimeout`, or an invalid-packet `RxDone` under `AUTO_MODE_OK` (→ *disable* the feature). **No FIFO-level event is in this set.**

---

### 1. Full bitfield layout of SET_AUTO_RX_TX (0x0211)

**DS §6.3.9 "SetAutoRxTx", Table 6-15** (Rev 2.2, p.108), frame quoted verbatim (10 bytes: 2 opcode + 8 params):

```
 Byte              0      1           2              3            4           5             6          7              8              9
 Data from                            clear        Timeout        Timeout     Timeout        Delay      Delay         Delay            Delay
                  0x02      0x11
    host                             Mode(6:0)       (23:16)        (15:8)       (7:0)       (31:24)    (23:16)        (15:8)           (7:0)
```

Field-by-field (all quotes verbatim from §6.3.9, p.108):

| Byte | Field | Bits | Semantics (verbatim) |
|---|---|---|---|
| 0-1 | opcode | — | `0x02 0x11` |
| 2 | `clear` | 7 | "Setting this bit disables AutoRxTx mode on a TxTimeout or RxTimeout, as well as on an RxDone with an invalid packet when the mode is AUTO_MODE_OK." |
| 2 | `Mode` | 6:0 | "Sets the auto Rx-Tx mode: 0x0: AUTO_MODE_NONE, this disables the AutoRxTx mode; 0x1: AUTO_MODE_ALWAYS, this enables AutoRxTx on every RxDone or TxDone.; 0x2: AUTO_MODE_OK, this enables AutoRxTx on a valid Rx packet only. No specific effect on Tx: works as AUTO_MODE_ALWAYS." |
| 3-5 | `Timeout` | 23:0 | "(in 1/32.768 kHz steps): Timeout used for the auto Rx or auto Tx." |
| 6-9 | `Delay` | 31:0 | "(in 1/32MHz steps): Delay between the RxDone/TxDone and going into Tx/Rx, allowing a maximum of 134 seconds delay." |

**Independent cross-checks of the layout (three sources agree):**

- **DRV** (Semtech LR20xx driver v1.3.1) — enum `LR20XX_RADIO_COMMON_CONFIGURE_AUTO_TX_RX = 0x0211` (`src/lr20xx_radio_common.c:134`), length `( 2 + 8 )` (`:94`), and the packing loop `src/lr20xx_radio_common.c:546-558`: byte2 = `condition | (disable_on_failure ? 0x80 : 0x00)`, bytes 3-5 = `tx_rx_timeout_in_rtc_step` `>>16/>>8/>>0`, bytes 6-9 = `delay_in_tick` `>>24/>>16/>>8/>>0`. **Matches the datasheet byte-for-byte.**
- **DS Table 5-7 "Common Radio Commands (Sheet 2 of 2)"** (p.89) — `SetAutoRxTx 0x0211`, parameters listed as `clear Mode(7:0) | Timeout(23:0) | Delay(31:0)`, description "Activates or deactivates the auto Tx/Auto Rx mode".
- **LIB** (RadioLib master @75e486a5) — `#define RADIOLIB_LR2021_CMD_SET_AUTO_RX_TX (0x0211)` (`LR2021_commands.h:23`); constants `RADIOLIB_LR2021_AUTO_MODE_NONE/ALWAYS/OK` and `AUTO_MODE_CLEAR_DISABLED/ENABLED` (`:211-215`); caller `LR2021::autoTxRx()` (`LR2021_cmds_chip_control.cpp:116-122`).

No byte, bit, or RFU position in this frame carries a FIFO level, FIFO threshold, FIFO pointer, or "start Tx" field. The frame is fully accounted for by `{clear|Mode, Timeout, Delay}`.

> **Note / observation (not a chip-behaviour claim):** RadioLib's `autoTxRx()` packs its three arguments in an order that does **not** match the datasheet field order — `LR2021_cmds_chip_control.cpp:117-120` emits `{delay>>16, delay>>8, delay, mode, timeout>>16, timeout>>8, timeout}`, i.e. `delay` lands in the datasheet's `Timeout(23:0)` bytes and `mode` lands in byte 5 (inside the `Timeout` field), while the datasheet expects `{clear|Mode, Timeout(23:0), Delay(31:0)}`. The vendor driver (DRV `lr20xx_radio_common.c:546-558`) packs it the datasheet way. This is a byte-packing discrepancy in the third-party wrapper, flagged here because a caller could otherwise mis-attribute "auto-TX didn't fire" to the FIFO question. It is not evidence about FIFO triggers either way.

### 2. Is there any auto-TRANSMIT (as opposed to auto-RX) capability? — YES, but RxDone-driven only

- **DS §6.3.9** (p.108), verbatim:
  > "The command SetAutoRxTx allows to automatically switch to Tx after an RxDone, or to Rx after a TxDone (depending on the Mode value), with a programmable Delay and a specific Timeout for the Tx/Rx."
- **Direction rules — DRV `inc/lr20xx_radio_common.h:478-480`** (verbatim):
  > "The order of operation depends on the mode manually requested after issuing this command: — If the radio is set to Tx mode, then an automatic Rx will be executed; — If the radio is set to Rx mode, then an automatic Tx will be executed."
- **Enabling field for auto-TX:** the `Mode(6:0)` field of byte 2. `0x1` (`AUTO_MODE_ALWAYS`) = "auto rx-tx on every RxDone or TxDone event" (LIB `LR2021_commands.h:212`); `0x2` (`AUTO_MODE_OK`) = "(Tx always)" for the Tx direction (LIB `:213`; DS §6.3.9 "No specific effect on Tx: works as AUTO_MODE_ALWAYS"). There is **no separate enable bit** — `Mode` *is* the selector, and `0x0` disables it.
- **Trigger event for auto-TX is an Rx completion, not a FIFO state.** The datasheet's own prose names the trigger in the first sentence (`after an RxDone`). The vendor driver's enum doc-comments state the same in trigger terms — DRV `inc/lr20xx_radio_common_types.h:320-324` (verbatim):
  > `LR20XX_RADIO_COMMON_AUTO_TX_RX_OFF = 0x00,  //!< Disable Auto Tx (or Rx) after Rx (or Tx) operation`
  > `LR20XX_RADIO_COMMON_AUTO_TX_RX_ALWAYS = 0x01,  //!< Always trigger Tx (or Rx) operation after Rx (or Tx) operation`
  > `LR20XX_RADIO_COMMON_AUTO_TX_RX_RX_DONE_ONLY = 0x02,  //!< Trigger Tx operation only if Rx operation terminates with CRC Ok.`
- **Timing:** the automatic Tx starts `Delay` ticks (1/32 MHz, ≤134 s) after the *Rx/Tx operation terminates*, per §6.3.9 and DRV `inc/lr20xx_radio_common.h:482-493`; the delay budget explicitly covers "PA ramp-up / TCXO start time / Configured fallback mode / Radio state switching time" — i.e. a *post-operation* start, not a FIFO-level start.

**⇒ The only way 0x0211 starts a transmission is as a reaction to a completed Rx operation. FIFO content is not part of the trigger.**

### 3. TX-FIFO threshold semantics (the mechanism that *does* exist — IRQ only)

The TX-FIFO threshold feature is real, but it lives in a **different command** and produces **only an interrupt/flag**, never a mode change.

**(a) Where the thresholds live — `ConfigFifoIrq` 0x011A, not 0x0211**

- **DS §6.10.1 "ConfigFifoIrq", Table 6-50** (p.126), verbatim:
  > "The ConfigFifoIrq command configures which FIFO level status flags trigger an RxFifo or TxFifo IRQ (Interrupt Request) as well as the threshold levels triggering the flags."
  > "`tx_fifo_irq_enable` defines for all bits set in this parameter, the corresponding Tx FIFO flag that triggers the **TxFifo IRQ**."
  > "Optional parameters for threshold levels: … `tx_low_threshold` sets the threshold level to use for the Tx FIFO low flag. … `tx_high_threshold` sets the threshold level to use for the Tx FIFO high flag."
  Frame: byte 0-1 opcode `0x01 0x1A`; byte 2 `rx_fifo_irq_enable(7:0)`; byte 3 `tx_fifo_irq_enable(7:0)`; bytes 4-5 `rx_high_threshold(15:0)`; bytes 6-7 `tx_low_threshold(15:0)`; bytes 8-9 `rx_low_threshold(15:0)`; bytes 10-11 `tx_high_threshold(15:0)`.
- **DRV `src/lr20xx_radio_fifo.c:181-202`** — signature `lr20xx_radio_fifo_cfg_irq(context, rx_fifo_irq_enable, tx_fifo_irq_enable, rx_fifo_high_threshold, tx_fifo_low_threshold, rx_fifo_low_threshold, tx_fifo_high_threshold)`; the byte order emitted matches Table 6-50 exactly (`:186-199`). Opcode `LR20XX_RADIO_FIFO_CFG_IRQ_OC = 0x011A` (`:77`). Decl `inc/lr20xx_radio_fifo.h:162-165`.
- **LIB** `configFifoIrq(rxFifoIrq, txFifoIrq, rxHighThreshold, txLowThreshold, rxLowThreshold, txHighThreshold)` (`LR2021.h:973`, impl `LR2021_cmds_chip_control.cpp:241-254`) — **same parameter order as the vendor driver**, unlike `autoTxRx()`.
- **HW** (first-party driver) — `lr2021_spi.h` declares `OP_DIO_IRQ_CONFIG_RX/TX` (`:191-192`) and the FIFO ops (`:185-188`) but **does not declare 0x0211 or 0x011A at all** (verified: the only `0x11` occurrences are `OP_CLEAR_ERRORS = {0x01,0x11,0x00,0x00}` at `:158` and the DIO9 value inside `OP_DIO_FUNCTION = {0x01,0x12,0x09,0x11}` at `:169`); i.e. the first-party transport never uses the auto-Rx-Tx command or the FIFO-threshold command.

**(b) What is counted, and the unit**

- **Counted quantity = the fill level of the Tx FIFO, in bytes.** DS §6.10.6 "GetTxFifoLevel" (p.129), verbatim: "The GetTxFifoLevel command retrieves the fill level of the Tx radio FIFO in bytes." Response `Level(15:0)` (Table 6-59). DRV `lr20xx_radio_fifo_get_tx_level(context, uint16_t* fifo_level)` with doc-comment "@param [out] fifo_level Tx FIFO level in byte" (`inc/lr20xx_radio_fifo.h:138`, impl `src/lr20xx_radio_fifo.c:158-173`).
- **Direction of the comparisons** — the flag definitions are explicit (DS §6.10.1, p.126, flags quoted verbatim; same list in AN1200.104 §2.4.1 p.8):
  > "`0x01`: FifoEmpty / `0x02`: FifoLow — FIFO level is below the low threshold / `0x04`: FifoHigh — FIFO level exceeds the high threshold / `0x08`: FifoFull / `0x10`: FifoOverflow / `0x20`: FifoUnderflow"
  and the driver documents the same direction: "`tx_fifo_low_threshold` Tx FIFO threshold **below** which an interrupt … is triggered"; "`tx_fifo_high_threshold` Tx FIFO threshold **above** which an interrupt … is triggered" (DRV `inc/lr20xx_radio_fifo.h:152-158`). Bit values confirmed in `inc/lr20xx_radio_fifo_types.h:69-76` (`FLAG_EMPTY=(1<<0)`, `FLAG_THRESHOLD_LOW=(1<<1)`, `FLAG_THRESHOLD_HIGH=(1<<2)`, `FLAG_FULL=(1<<3)`, `FLAG_OVERFLOW=(1<<4)`, `FLAG_UNDERFLOW=(1<<5)`).
- **FIFO sizes:** default 256 bytes, extendable to 1024 — DS §5.3.3 (p.79-80): "The default size of both the RX and TX FIFO is 256 bytes. The LR20xx drivers also expose a set of functions that move the FIFOs to a larger memory region, allowing both FIFOs to reach 1024 bytes in size."

**(c) Valid range of the threshold fields**

- **Field width is 16 bits** (`tx_low_threshold(15:0)`, `tx_high_threshold(15:0)` — DS Table 6-50, p.126; DRV `inc/lr20xx_radio_fifo.h:162-165`; LIB `LR2021.h:973`).
- **Documented usable range:** DS §5.3.3.1.2 "Step 2 (optional): Configure threshold IRQs" (p.80), verbatim:
  > "If the application does not use the low-threshold IRQs, or if all the low thresholds stay within the range 0–256, this step is not needed. If the application needs the low thresholds (`tx_fifo_low_threshold` / `rx_fifo_low_threshold`) to exceed 256, meaning the application is expecting to send or receive packets that are larger than 1 kB and must make use of the dynamic buffer reading/filling, then the application must use the workaround wrapper `lr20xx_workarounds_1024_byte_fifo_cfg_irq`, as the standard `lr20xx_radio_fifo_cfg_irq()` cannot express low thresholds above 256."
- **UNKNOWN:** the datasheet gives no range statement for `tx_high_threshold` comparable to the low-threshold 0–256 rule, and no statement of what the chip does when a threshold is set above the FIFO size (clamp? ignore? never-fire?). DS §5.3.3.1.2 discusses only the *low* thresholds, and §22 "Known Limitations and Workarounds" (p.232-234; errata copy `docs/lr2021-research/errata/semtech-datasheet-v2.2-section22-known-limitations-and-workarounds.txt`) contains **no** FIFO-threshold item (its items are OOK detection threshold, RTTOF accuracy, PRAM, regulatory compliance). Searched with no result: DS §5.3.2/§5.3.3/§6.10.1–6.10.8, DRV, LIB, `errata/semtech-usp-doc-KNOWN_LIMITATIONS.md`, `errata/radiolib-lr2021-issue-index.txt`.
  *Reason for UNKNOWN: the documentation specifies a 16-bit field and one 0–256 workaround rule for low thresholds, but never states the high-threshold ceiling or out-of-range behaviour.*

**(d) Interaction with the TX-FIFO base/pointer registers**

- **DS §5.3.3.1.1 "Step 1: Switch the FIFO(s) to the large region"** (p.80): "Under the hood, each call writes two registers: the FIFO base address and the FIFO size. The writes are done via WriteRegMem32(register_address, new_register_value);" — **Table 5-2** gives `Tx FIFO base address 0x00F3002C`; **Table 5-3** gives `Tx FIFO size` register `0x00F30034`, value `0x000003FC` (= 1020, "bits 9:2 (8 bits) representing N + 1 words. Total 1024 bytes") for the 1024-byte configuration. (Same register addresses appear in the datasheet's register map, p.240.) No FIFO-threshold field shares these registers — thresholds are command parameters of 0x011A, not memory-mapped.
- **Two documented interactions that matter if you size thresholds against the extended FIFO:**
  1. DS §5.3.3.1.3 "Step 3 (optional): Preserve the configuration across sleep" (p.80): "The FIFO location registers and the workaround threshold registers are not retained by default when the chip enters sleep mode." (Retention helpers: `lr20xx_radio_fifo_1024_byte_tx_fifo_store_retention_mem`, `lr20xx_workarounds_1024_byte_fifo_cfg_irq_store_retention_mem`.)
  2. DS §5.3.3 note (p.79): "While using the extended FIFOs, if any CalibFe command is issued, the content of the FIFOs is not valid anymore. Any data in the FIFOs is overwritten with data used during calibration."
- Also note (DS §5.3.2, p.79; FIFO IRQ flags `Overflow`/`Underflow` exist for the Tx FIFO): the host is told to keep the FIFO fed — "For payloads superior to 256 bytes, the Tx FIFO has to be written when data is being transmitted, avoiding an underflow of the Tx FIFO, using the threshold informations available through the API or the DIOs." The instruction is addressed to the **host**; no chip-side action is described.

**(e) The threshold IRQ is informational — no radio action**

- **DS §5.7 "Host Interrupts (LR20xx)", Table 5-20** (p.99), sheet 1 row quoted verbatim:
  > `Bit 1 | TxFifo | Tx FIFO threshold reached | Tx | All`
  (the `Mode` column reads `Tx`; i.e. the TxFifo IRQ is produced by the Tx direction. The table's columns are `Bit / IRQ / Description / Mode / Packet Type`; nothing in the row states or implies that the IRQ *initiates* Tx.)
- **DS §6.8.3 "SetDioIrqConfig", Table 6-46** (p.124): "maps specific IRQs (Interrupt Requests) to the specified DIO pin when it is set as an IRQ using the SetDioFunction command"; "`Irq`: See Section 5.7 for a description of the Irq bits." → the endpoint of the TxFifo IRQ is a **DIO pin to the host MCU**.
- **AN1200.104 §2.4.1** (p.8): "The host controller can monitor the DIO pin state, receiving an interrupt when the configured FIFO condition occurs. The host can then check which specific FIFO flag triggered the interrupt using command `GetFifoIrqFlags(...)`."
- **AN1200.104 §2.4.4 "Practical Implementation Strategy"** (p.9) states the intended TX flow explicitly — it is a **host loop**, no chip autonomy:
  > "For TX operations: 1. Configure TX FIFO low threshold IRQ to trigger when the FIFO has space for new data. 2. When the IRQ triggers, check `GetTxFifoLevel(...)` to determine exactly how much space is available. 3. Write new data to the FIFO using `WriteRadioTxFifo(...)`."
  (Contrast the RX half of the same section: "For continuous reception, clear the RX IRQ flag using `ClearFifoIrqFlags(...)`." — again pure host bookkeeping.)
- **DS §5.3.2 "Tx Data FIFO"** (p.79) lists the Tx-FIFO threshold information as a *status* surface only: "Status information in the ConfigFifoIrq command includes `tx_low_threshold`, `tx_high_threshold` and FIFO flags `FifoUnderflow`, `FifoEmpty`, `FifoFull`, and `FifoOverflow`."
- **HW** (first-party transport) uses exactly this host-driven pattern: it maps FIFO/DIO IRQs (`lr2021_spi.h:191-192`) and issues `OP_SET_TX_CMD = {0x02, 0x0D, 0x00, 0x00, 0x00}` (`lr2021_spi.h:172`) as an explicit host action — no auto-TX path exists in that driver.

**⇒ FIFO thresholds can *notify* the host; they cannot *start* a transmission.**

### 4. One-shot vs re-arming

- **`SET_AUTO_RX_TX` (0x0211) is ONE-SHOT and must be re-armed explicitly.** DS §6.3.9 (p.108), verbatim:
  > "This mode can only be triggered once, and must be re-enabled: it is automatically disabled once triggered."
  Same in Rev 2.1 §6.3.9 (p.104). DRV `inc/lr20xx_radio_common.h:499-500`, verbatim:
  > "Once the automatic operation triggers, the feature is automatically disabled. So that to engage again an automatic operation after a manual one, the `lr20xx_radio_common_configure_auto_tx_rx` must be called to enable it again."
  Cancellation before trigger is also documented: "Calling `lr20xx_radio_common_configure_auto_tx_rx` with condition being `LR20XX_RADIO_COMMON_AUTO_TX_RX_OFF` disables the automatic Tx or Rx behavior. Doing so after end of Rx (or Tx) operation and start of automatic Tx (or Rx) also cancels the automatic Tx or Rx operation." (DRV `inc/lr20xx_radio_common.h:495-497`; LIB `AUTO_MODE_NONE = 0x00` `LR2021_commands.h:211`).
  *Note:* this one-shot statement is about 0x0211's trigger. It has no bearing on the FIFO question — it describes **how many times** the auto-Tx-after-RxDone fires, not **what** can fire it.
- **The FIFO-threshold IRQ is NOT one-shot — it is edge-triggered and re-arms on each crossing.** DRV `inc/lr20xx_radio_fifo.h:143-146`, verbatim:
  > "When configured, the FIFO interrupts are triggered if the FIFO level crosses the threshold in the correct direction. Therefore if a threshold related IRQ is cleared, it will be raised again only if the FIFO level crosses the threshold on the correct direction."
  Consistent with the flag model: FIFO flags persist until cleared — DS §6.10.2 "GetFifoIrqFlags" (p.127): "retrieves all FIFO flags that have been triggered since the last clear operation… clearing the RxFifo/TxFifo IRQ does not clear the flags. As a result, the flags are not affected, but the IRQ can still be triggered if a flag is activated again."
- **UNKNOWN:** whether the `clear` bit's auto-disable interacts with a re-arm after an *RxTimeout* in duty-cycle mode is described only for RxDutyCycle starts (DS §6.3.9: "If an RxDutyCycleMode is started, this mode behaves the same way as with a normal Rx. But if the clear bit is set, this mode is automatically disabled on the first Rx: if no packet is received, for the autoRxTx, it is considered an RxTimeout.") — not relevant to FIFO triggering, and not further specified.

### 5. What *does* start a transmission on this chip (for completeness)

| Path | Starts TX? | Trigger | Citation |
|---|---|---|---|
| `SET_TX` 0x020D | **YES** | explicit host command | DS §6.3.6, Table 6-12 (p.106): "The SetTx command activates the radio's Tx mode, initiating RF packet transmission…" |
| `SetTxTestMode` 0x020E mode 0x01/0x02 | **YES** | explicit host command (infinite preamble / CW) | DS §21.2, Table 21-2 (p.231); §4.4.5 (p.76-77) |
| `SET_AUTO_RX_TX` 0x0211 | YES, but only after **RxDone** (auto-Tx); or after **TxDone** (auto-Rx) | radio-operation completion | DS §6.3.9 (p.108); DRV `lr20xx_radio_common.h:478-480` |
| `SetLoraCadParams` exit mode `CAD_LBT = 0x10` | YES | CAD completion with no activity detected | DS §6.3.11, Table 6-18 (p.109): "The chip performs a CAD operation and if no activity is detected, it goes to Tx mode and takes cad_timeout as Tx timeout."; §9.4 (p.154): "Start transmission (for example to perform LBT)" |
| `LrFhssBuildFrame` 0x0256 | **NO** | — | DS §17.2.1 (p.206): "This command does not initiate the packet transmission… To send the packet, this command must be followed by the normal SetTx command, which triggers the actual transmission process." |
| **TX-FIFO threshold crossing** | **NO** | — | DS §6.10.1 Table 6-50 (p.126); §5.7 Table 5-20 (p.99); §5.3.2 (p.79); AN1200.104 §2.4.4 (p.9) |

### 6. Explicit UNKNOWNs (with reasons)

1. **High-threshold valid range and out-of-range behaviour: UNKNOWN.** Reason: DS Table 6-50 (p.126) declares `tx_high_threshold(15:0)` but §5.3.3.1.2's range/workaround statement (p.80) covers only the *low* thresholds (0–256); no ceiling or clamping rule for `tx_high_threshold` is stated anywhere in §5.3, §6.10, or §22.
2. **Whether a Tx-FIFO threshold IRQ can be given any radio-level effect by some other (undocumented) command: UNKNOWN.** Reason: no command in DS Table 5-7 (p.88-89) or §6 carries a "trigger on TxFifo IRQ" parameter; §6.10.1–6.10.8 define the thresholds only as flag/IRQ sources. Absence of a documented mechanism is not proof of absence in silicon, so this is recorded as UNKNOWN rather than "impossible".
3. **The 1024-byte-FIFO low-threshold workaround's interaction with `tx_high_threshold`: UNKNOWN.** Reason: DS §5.3.3.1.2 mentions only "low thresholds" exceeding 256 for the `lr20xx_workarounds_1024_byte_fifo_cfg_irq` wrapper; the wrapper's behaviour for the high thresholds is not described in the corpus (`errata/semtech-usp-lr20xx_workarounds.h` present in the corpus has no FIFO-threshold entry, and `lr20xx_workarounds.c` in the local driver clone contains no `1024_byte_fifo_cfg_irq` symbol).
4. **`SET_AUTO_RX_TX` frame in Rev 2.1 vs 2.2: no difference found** — both editions give the identical frame and the identical trigger prose (§6.3.9, Table 6-15; Rev 2.1 p.104, Rev 2.2 p.108), so the NO verdict is revision-stable across the two datasheet editions in the corpus.

---

## Sources (path prefixes used throughout)

| Tag | Source |
|---|---|
| **DS** | `docs/lr2021-research/semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` — Semtech LR2021/LR2022/LR2012 Final Datasheet **Rev 2.2** (DS.LR20xx, 29/07/26, 250 pp). Section/table/page numbers are **Rev 2.2** numbering. |
| **DS21** | `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` (repo root, Rev 2.1, 243 pp) — used only for revision stability checks. |
| **DRV** | Semtech official LR20xx driver (vendored), `~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/` — `LR20XX_DRIVER_VERSION "v1.3.1"` (`inc/lr20xx_driver_version.h:60`) |
| **RAL** | same repo, `.../third_party/Radio/radio_hal/ral_lr20xx.h` |
| **LIB** | RadioLib snapshot, `docs/lr2021-research/radiolib-master/LR2021-module/` (master @75e486a5) |
| **HW** | first-party raw-SPI driver, `docs/lr2021-research/vendor/balloon-lr2021-transport/lr2021_spi.h` |
| **AN104** | `docs/lr2021-research/semtech-official/AN1200.104_LR20xx_ModemInterface_v1.0.pdf` (Rev 1.0, Oct 2025, 31 pp) |
| **ERRATA** | `docs/lr2021-research/errata/` (datasheet §22 known-limitations, Semtech USP known-limitations, RadioLib issue index) |

Method note: the Rev 2.2 PDF was converted with `pdftotext -layout` and quoted text extracted verbatim; page numbers were derived by mapping each quoted line to the last page footer ("N of 250") above it. `file:line` numbers are 1-based line numbers in the cited file at the revision given.

## Acceptance summary

| Acceptance criterion | Met |
|---|---|
| Verdict is yes/no/UNKNOWN | **NO** (auto-TX-to-FIFO-threshold), stated up front and per-question in §"Verdict" |
| Enabling field(s) named with bit position | `Mode(6:0)` byte 2 bits 6:0 (auto-TX exists, RxDone-driven); no FIFO field exists in 0x0211 |
| FIFO threshold semantics + valid range + unit | bytes of Tx-FIFO fill; `tx_low_threshold(15:0)` / `tx_high_threshold(15:0)`; 0–256 documented usable for low thresholds; high-threshold ceiling UNKNOWN |
| One-shot vs re-arming | 0x0211 = one-shot (re-enable required); FIFO-threshold IRQ = edge-triggered, re-arms per crossing |
| Every register-behaviour claim cited | DS section + table + page, or file:line, for every claim; UNKNOWNs carry their reason |
