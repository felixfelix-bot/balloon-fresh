# LR2021 — errata / silicon-revision notes affecting continuous TX, auto-TX FIFO triggers, FIFO IRQ thresholds, TX underrun

Task: `t_da19111d` — "Answer: LR2021 errata and silicon revisions affecting TX / FIFO IRQ thresholds"
Date: 2026-10-01T00:19Z · Board: tollgate · Worker: worker-base · Branch: `pr/lr2021-errata-tx-fifo`
Corpus home: `docs/lr2021-research/` in `felixfelix-bot/balloon-fresh` @ base `08d718b3`.
Host: `c03rad0r-DQ05proplus`.

**Bottom line (one line): NO errata document was located for the LR2021 — so every question in
scope resolves to UNKNOWN — and of the three Semtech known-limitation artifacts that *were*
inspected end-to-end (§22, USP `KNOWN_LIMITATIONS.md`, `lr20xx_workarounds.{h,c}` + driver
README), the union of the four target features {continuous TX, auto-TX FIFO trigger, FIFO IRQ
threshold, TX underrun} matches **zero** entries; the only LR2021 FIFO-related defect found
anywhere is a *host-side RadioLib* bug (`configFifoIrq()` wire format, fixed 2026-08-11), not a
silicon erratum.**

Notation: **DS** = `semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` (Semtech Final
Datasheet **Rev 2.2**, `DS.LR20xx 29/07/26`, 250 pp; § / Table numbers are v2.2 numbering).
`file:line` = line number in that file. Path prefixes are relative to `docs/lr2021-research/`.

---

## 0. Answer in the task's own terms

| Task's target feature | Any errata / silicon-revision note found? |
|---|---|
| continuous TX | **UNKNOWN** — no document located (see §5). No limitation note in the inspected known-limitation artifacts (§2–§4), but "not mentioned" ≠ "no erratum". |
| auto-TX FIFO triggers | **UNKNOWN** — no document located. Note: the datasheet's auto-TX command (`SetAutoRxTx`) is *not* FIFO-driven at all, so the phrase "auto-TX **FIFO** trigger" has no counterpart register/command in DS Rev 2.2 (see §6.2). |
| FIFO IRQ thresholds | **UNKNOWN** — no errata document located. One **host-driver** defect found (RadioLib `configFifoIrq()`), fixed in RadioLib, not silicon (§6.1). |
| TX underrun | **UNKNOWN** — no document located. DS documents the *flag/IRQ* only and never the device *action* on underflow (§6.3); no errata note exists on top of that. |

**The load-bearing statement for downstream consumers: no stand-alone Semtech LR2021 errata sheet
exists in the searchable record (independently re-verified this run — §1), and none of the three
Semtech-authored known-limitation artifacts that stand in for it raises any of these four
features.** Any downstream claim of the shape "per LR2021 errata, X" is unsourced and must be
marked UNKNOWN.

---

## 1. Search locations (acceptance criterion: "Search locations are listed")

Every location searched this run. "Result" is what the search *returned*, not an inference.

### 1.1 In-corpus (read/re-grepped end-to-end, not just keyword-sampled)

| # | Location | What was done | Result |
|---|---|---|---|
| S1 | `semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf` (full text, `pdftotext -layout`, 13441 lines) | term sweep `erratum\|errata\|silicon revision\|chip revision\|stepping` over the **whole** document | **0 hits** |
| S2 | same PDF, §22 "Known Limitations and Workarounds" (p.232–234) | §22 read verbatim; extract byte-verified — `sed -n '12296,12416p'` of the fresh extract hashes **identical** (`445b7e22…465a`) to the committed `errata/semtech-datasheet-v2.2-section22-known-limitations-and-workarounds.txt` | 4 limitations; **none** of the four target features (§2) |
| S3 | same PDF, `underflow` (all occurrences) | `grep -in underflow` | **4** lines: 4424 (Rx FIFO flag list), 4442 (Tx FIFO flag list), 4444 ("avoiding an underflow…"), 6952 (`0x20: FifoUnderflow`). All descriptive; no limitation/errata claim |
| S4 | `semtech-official/AN1200.101_LR2021_FLRC_Improvements.pdf` | full-text sweep | `errata\|erratum` = **0**, `underflow` = 0, `fifo` = 0 |
| S5 | `semtech-official/AN1200.102_LR20xx_LoRaImprovements_Rev1.1.pdf` | full-text sweep | `errata\|erratum` = **0**, `fifo` = 0 |
| S6 | `semtech-official/AN1200.104_LR20xx_ModemInterface_v1.0.pdf` | full-text sweep | `errata\|erratum` = **0**; `underflow` = **1** (line 267, `0x20: FifoUnderflow - FIFO has underflowed`, a restatement of DS Table 6-50); `fifo` = 71 |
| S7 | `errata/semtech-usp-doc-KNOWN_LIMITATIONS.md` (Lora-net/usp, commit `351b2015`) | read end-to-end | 10 limitations; **none** of the four target features (§3) |
| S8 | `errata/semtech-usp-lr20xx_driver-README.md` ("## Workarounds" + body) | read end-to-end | 11 workarounds; **none** TX-FIFO (§4) |
| S9 | `errata/semtech-usp-lr20xx_workarounds.h` / `.c` (whole files) | function inventory + full-body grep for `version\|get_version\|0x0110\|2513` | 22 public workaround functions; **no** version read or revision gate; **no** version-conditional compilation in the `.c` (§4) |
| S10 | `errata/radiolib-lr2021-issue-index.txt` | read | 60 LR2021 items + 13 `errata` items (0 LR2021) (§5.1) |
| S11 | `errata/provenance.md` (the sourcing card's own NOT-FOUND record) | read | records the errata-sheet hunt already performed (§1.3) |

### 1.2 Live re-verification this run (not inherited from `provenance.md`)

| # | Action | Result |
|---|---|---|
| L1 | `curl https://www.semtech.com/products/wireless-rf/lora-plus/lr2021` | **HTTP 200**, 226470 B (byte-size identical to the archived page in `provenance.md` R9) — documentation list is still **Datasheets + Application Notes only**; `errata\|erratum\|known issue` → **0 hits** |
| L2 | `gh api 'search/repositories?q=LR2021+errata'` | `total_count` = **0** |
| L3 | `gh api 'search/issues?q=LR2021+errata'` | `total_count` = **2**, neither a Semtech errata document: `ScotMesh/RepeaterTastic#3`, `Xinyuan-LilyGO/T-Display-P4#11` |
| L4 | `gh api 'search/issues?q=repo:jgromes/RadioLib+errata'` | `total_count` = **13**, **none LR2021** (all SX12xx/LoRaWAN/CC1101 — list reproduced in `errata/radiolib-lr2021-issue-index.txt` L67–L82) |
| L5 | `gh api 'search/commits?q=repo:jgromes/RadioLib+errata'` | 4 commits, **none LR2021**: CC1101 `b9c214db95`, SX127x `498b638234`/`d91c6d0712`, SX126x `02b6024e65` |
| L6 | `gh api 'search/commits?q=repo:jgromes/RadioLib+silicon'` | 4 commits, **none LR2021** (Silicon Labs CI/EFR32, SX1231 `ec9bc64ce0`) |
| L7 | `gh api 'repos/jgromes/RadioLib/commits?path=src/modules/LR2021&per_page=40'` + `search/commits?q=…+LR2021+workaround` | full LR2021 commit log inspected for errata/silicon/workaround-labelled work; findings in §5.2–§5.3 |

### 1.3 Already-searched by the sourcing card (re-cited, not re-run)

`errata/provenance.md` §3.1 records the prior "standalone errata sheet = NOT FOUND" hunt:
F1–F2 (Semtech product page + archived copy, 0 errata matches), F3–F6 (Semtech site-search / API,
JS-only or 404), F7 (`support/technical-support` **HTTP 404**), F8 (`semtech.com/quality` 200, 0
errata matches), F9 (DuckDuckGo HTML, **HTTP 202** bot challenge), F10–F12 (GitHub global
repos/issues/code → 0 / 2 / 91, none an errata document), F13–F17 (RadioLib tree/contents/changelog
404s + in-tree scan), F18–F19 (LoRa Alliance, no LR2021 results). Independently re-verified this
run at L1–L6; **consistent**.

### 1.4 NOT searched / still open (see §8)

- `AN1200.103` (LR20xx CPFSK Modem Improvements), `AN1200.106` (LR20xx Xtal Temperature drift
  Mitigation), `AN1200.107` (LR20xx Analog Improvements) — listed on the product page (L1) but
  **absent from this corpus and not retrieved**. The two "Improvements" notes that *are* in the
  corpus (AN1200.101/.102, S4–S5) contain 0 errata terms, but they are different documents.
- Semtech support/KB articles (login-gated; `support/technical-support` → 404, F7).
- Any Semtech NDA/PCN channel.

---

## 2. E1 — Datasheet Rev 2.2 §22 "Known Limitations and Workarounds" (the in-datasheet substitute for an errata sheet)

DS §22 opens (p.232, verbatim):

> "At the time of authoring this document, some limitations are known. Implementations of
> workarounds are described inside the readme of the LR2021/LR2022/LR2012 drivers hosted on the
> Semtech Github page available at https://github.com/lora-net. Some workarounds are automatically
> applied by the drivers. Review the guidelines provided individually for each workaround."

Complete enumeration of §22 — all four entries, with the scope each declares:

| § | Title | Scope declared in the title/body | Touches any of the 4 target features? | Documented workaround |
|---|---|---|---|---|
| 22.1 | OOK Detection Threshold Adjustment (LR20xx) | threshold too high ⇒ weak-signal loss; too low ⇒ false detections/missed packets (PER) | **NO** (RX-detection threshold, not FIFO threshold) | `lr20xx_workarounds_ook_set_detection_threshold_level()`; compare against `lr20xx_workarounds_ook_get_default_detection_threshold_level()` |
| 22.2 | RTTOF Accuracy for SX1280-compatible Bandwidths (LR2021/LR2022) | "For LoRa bandwidths 203, 406 and 812 kHz (at either 2.4 GHz or sub-GHz), the RTToF accuracy is optimized when calling specific workarounds described in `lr20xx_workarounds.c`." | **NO** | `lr20xx_workarounds_rttof_results_deviation()` (+ retention helper) |
| 22.3 | Firmware Patch RAM (PRAM) | "While not strictly required, **using the chip without the PRAM can create performance issues and unexpected bugs.** The use of the PRAM is therefore highly recommended." Lost after reset/cold start; preserved in sleep-with-retention; +80 nA sleep current. Also modifies Z-Wave `GetZwavePacketStatus` and OQPSK length-check bypass | **NO directly** — see §7 (PRAM is the *mechanism* by which silicon limitations are fixed, and it is the one place a silicon-revision effect could hide) | Load PRAM to `0x801000` via `WriteRegMem32`, activate with opcode `0x012D` arg `0x00`; verify `0x800FF8 == 0x600DB002`; PRAM version at `0x800FFC` (`(v>>8)&0xFFFF`) |
| 22.4.1 | CN470 SRRC Compliance for China (FLRC) | regulatory | **NO** | Gaussian BT=0.3; `WriteRegMemMask32(0xF40110, 0x7, 0x05)`; `WriteRegMemMask32(0xF30904, 0x100, 1<<8)` |
| 22.4.2 | IN865 Compliance for India (FLRC) | regulatory | **NO** | `WriteRegMemMask32(0xF30904, 0x100, 1<<8)` |

**⇒ Document found; it lists no errata relevant to continuous TX, auto-TX FIFO triggers, FIFO IRQ
thresholds, or TX underrun.** (This is the "document found and lists no relevant errata" case from
the task's step 4.) Note the two FIFO-adjacent *thresholds* in the whole datasheet are **RX
detection** (22.1) and the **RTToF/SX1280 BW** set (22.2) — neither is the Tx-FIFO threshold
mechanism. The word "errata"/"erratum" does not occur in the datasheet at all (S1).

---

## 3. E2 — USP `doc/KNOWN_LIMITATIONS.md` (Semtech, `Lora-net/usp` @ `351b2015`)

Complete enumeration (10 entries). File is stored verbatim at
`errata/semtech-usp-doc-KNOWN_LIMITATIONS.md` (3440 B, sha256 `464c2ec1…7d44e`).

| Entry | Subject | Touches any of the 4 target features? |
|---|---|---|
| #131 | `hw_modem` integration: `modem-bridge` not provided | NO |
| #119 | `hw_modem`: STORE & FORWARD not functional (defines not activated in `cmd_parser.c`) | NO |
| #130 | Some programmed packets could be dropped (Relay RX), message `task schedule aborted because in the past -1`; mitigation extend `RP_MARGIN_DELAY` 8→12 in `smtc_rac_lib/radio_planner/src/radio_planner_types.h` | NO — this is a **host radio-planner** timing limitation, explicitly "may also occur occasionally with other features and radios"; not a TX-FIFO/IRQ-threshold/silicon issue |
| #129 | Geolocation tools missing (`full_almanac_update`, `lr11xx_flasher`, `wifi_region_detection`) | NO |
| #98 | `smtc_rac_submit_radio_transaction()` accepts out-of-range frequency silently (previous frequency used) | NO |
| #94 | **LR20xx + LoRa BW 7/10/15/20 ⇒ division-by-zero** | **NO** — modulation-parameter guard, not FIFO/TX-trigger |
| #102 | `smtc_rac_radio_lora_params_t/symb_nb_timeout` limited to `uint8_t` (caps LoRa preamble length); "LoRaWAN Relay TX/RX are not affected" | NO |
| — | `rf_certification` sample temporarily unavailable | NO |
| #125 | `RAL_LORA_CAD_LBT` CAD mode of the `cad` example not functional (Zephyr & baremetal) | NO |

**⇒ Document found; no entry touches the four target features.** Note especially that #130 (the
only "packets dropped" entry) is a host-scheduler timing issue with an explicit app-level
mitigation — it is not evidence of a silicon erratum and does not concern FIFO thresholds or
underrun.

---

## 4. E3 — Semtech's LR20xx silicon-workaround catalogue (`lr20xx_workarounds.{h,c}` + driver README)

This is the closest thing in existence to a published LR20xx errata sheet — it is the set of
register pokes Semtech ships to compensate for known silicon behaviour. **Scope statement (driver
README, verbatim):**

> "The workarounds defined here are expected to be used for LR20xx **engineering samples (date
> code: `2513`, version `0x0110`)**."

That is the *only* silicon-revision scope any Semtech artifact states. Consequences, verified:

- **No revision gate anywhere in the code.** `lr20xx_workarounds.c` contains **no** version read, no
  `GetVersion` call, and no `#ifdef`-style revision conditional (S9: grep for
  `defined|ifdef|ifndef|endif|else` returns only three plain `else` control-flow branches at lines
  257/542/556). `lr20xx_workarounds.h` has exactly three compile-time switches, and they disable
  *automatic application*, they do not gate *applicability* to a revision:
  `LR20XX_WORKAROUNDS_DISABLE_AUTOMATIC_DCDC_RESET` (h:57),
  `LR20XX_WORKAROUNDS_DISABLE_AUTOMATIC_DCDC_CONFIGURE` (h:63),
  `LR20XX_WORKAROUND_DISABLE_AUTOMATIC_BLE_2MBPS_PREAMBLE_LENGTH` (h:69).
- **Therefore: whether a given workaround applies to a given chip revision is not determinable from
  the artifact.** "Engineering samples, date code 2513 / version 0x0110" is declared, and the
  functions are unconditional. No produced-chip date code or FW version is named anywhere in the
  corpus. DS §6.7.2 Table 6-40 gives the silicon/firmware version *read path* (`GetVersion` opcode
  `0x0101`; LR2021 `FWMajor=0x01`, `FWMinor=0x18`) but no §22 entry keys a limitation to it.

Full inventory of the 22 public workaround functions (`.h` decl line → `.c` impl line), annotated
against the four target features:

| Workaround (`.h` → `.c`) | Subject | Touches 4 targets? |
|---|---|---|
| `bluetooth_le_phy_coded_syncwords` (104 → 207) | BLE Coded PHY access address fails to TX/RX correctly ⇒ degraded PER | NO (BLE PHY, not LR2021 continuous TX) |
| `bluetooth_le_phy_coded_frequency_drift` (119 → 216) | default freq drift hurts sensitivity | NO |
| `…frequency_drift_store_retention_mem` (135 → 224) | retention slot helper | NO |
| `bluetooth_le_2mbps_preamble_length` (152 → 231) | "default preamble length for BLE `LE_2M` is **incorrect**" | NO (BLE preamble, not LoRa/TX FIFO) |
| `lora_enable_sx1276_compatibility_mode` (172 → 241) | SX1276 LoRa interop | NO |
| `lora_disable_sx1276_compatibility_mode` (187 → 246) | ditto | NO |
| `lora_sx1276_compatibility_mode_store_retention_mem` (204 → 263) | retention slot | NO |
| `lora_freq_hop_enable_sx1276_compatibility_mode` (220 → 270) | intra-packet freq-hop interop | NO |
| `lora_freq_hop_disable_sx1276_compatibility_mode` (232 → 275) | ditto | NO |
| `lora_freq_hop_sx1276_compatibility_mode_store_retention_mem` (249 → 280) | retention slot | NO |
| `ook_set_detection_threshold_level` (274 → 287) | §22.1 | NO |
| `ook_get_default_detection_threshold_level` (289 → 296) | §22.1 helper | NO |
| `rttof_truncate_pll_freq_step` (308 → 484) | "Biased RTToF results may be observed if the RF frequency configured is not a multiple of 122 Hz"; freq moves ≤122 Hz | NO |
| `rttof_rssi_computation` (336 → 490) | "The RSSI value returned by the chip can be incorrect." Auto-applied unless `LR20XX_WORKAROUND_DISABLE_RTTOF_RSSI_COMPUTATION_FIX` | NO |
| `dcdc_reset` (354 → 510) | auto-applied after `set_pkt_type`; DCDC/sensitivity | NO — **RX path**: the `.h` doc block is explicit that it applies when "Rx operations are intended / DCDC mode / sub-GHz" |
| `dcdc_configure` (379 → 521) | auto-applied after the 6 modulation/Rx-path setters; same RX-path condition | NO |
| `dcdc_store_retention_mem` (395 → 562) | retention slot | NO |
| `rttof_results_deviation` (416 → 568) | §22.2, fractional BWs | NO |
| `rttof_results_deviation_store_retention_mem` (435 → 580) | retention slot | NO |
| `rttof_extended_stuck_second_request_enable` (451 → 589) | `RTTOF_MODE_EXTENDED`: "manager stays stuck for few seconds" | NO |
| `…disable` (466 → 596) | ditto | NO |
| `…store_retention_mem` (482 → 603) | retention slot | NO |

Plus one internal helper `rttof_rssi_computation_get_gain_power` (c:641).

Driver README workaround prose adds no further entries beyond the above (BLE ×3, SX1276 LoRa ×2,
OOK ×1, RTToF ×5, DCDC ×1) and states for each the call-order contract and the retention-memory
caveat. **None of the 22 functions concerns TX-continuous, an auto-TX FIFO trigger, FIFO IRQ
thresholds, or TX underflow.**

---

## 5. RadioLib — driver source, commit log, issue tracker

### 5.1 In-tree snapshot (`radiolib-master/LR2021-module/`, master @ `75e486a5`)

Grep for `errata|silicon|revision|workaround|limitation|known issue` over the whole snapshot
returns **no LR2021 erratum claim**. The only LR2021-labelled workaround machinery is the **DCDC**
port (`LR2021.h:1074-1076`, `LR2021_cmds_chip_control.cpp:348-381`, called from
`LR2021_cmds_{radio,ook,gfsk,flrc,lora}.cpp`) — Semtech's RX-path DCDC workaround, not a TX-FIFO
one. `LR2021.h:790` "The following limitations apply:" heads the LoRa side-detector constraints
(RX/CAD, spreading-factor ordering) — not in scope.

The snapshot's `configFifoIrq()` already carries the **fixed** 10-byte body (matches DS Table 6-50
field order `rxHigh, txLow, rxLow, txHigh`). See §5.2 for why that matters.

### 5.2 The ONLY LR2021 FIFO-relevant defect found anywhere: RadioLib `configFifoIrq()` wire format

This is a **host-driver** bug, not a silicon erratum, and it is the single closest thing in the
entire search to a "FIFO IRQ threshold" issue. Recorded because it is what a downstream "FIFO IRQ
threshold problem" report most likely traces back to.

- Issue **#1848** "[LR2021] Incorrect `ConfigFifoIrq` command format" (closed, opened
  2026-08-11T08:35:04Z). The reporter quotes DS Table 6-50 and the then-current code:

  ```cpp
  int16_t LR2021::configFifoIrq(uint8_t rxFifoIrq, uint8_t txFifoIrq, uint8_t rxHighThreshold, uint8_t txHighThreshold) {
    uint8_t buff[] = { rxFifoIrq, txFifoIrq, rxHighThreshold, txHighThreshold };
  ```

  i.e. **4 payload bytes** where DS Table 6-50 specifies **10** (`rx_fifo_irq_enable`,
  `tx_fifo_irq_enable`, then four 16-bit thresholds), and 8-bit instead of 16-bit thresholds.

- PR **#1849** "[LR2021] Fix `configFifoIrq()`" (closed, merged 2026-08-11T15:46:03Z, commit
  `e3e6fdc7b7`) changed the signature to
  `(uint8_t rxFifoIrq, uint8_t txFifoIrq, uint16_t rxHighThreshold, uint16_t txLowThreshold, uint16_t rxLowThreshold, uint16_t txHighThreshold)`
  and emits all six fields big-endian.

  **⇒ Impact for our firmware: any LR2021 `configFifoIrq()` call made with a RadioLib revision
  older than `e3e6fdc7b7` (2026-08-11) wrote a malformed 4-byte frame — it could not set
  `tx_low_threshold`/`tx_high_threshold` at all (the fields did not exist) and mis-sized the Rx
  threshold as one byte.** This is a concrete, cited explanation for "my Tx-FIFO IRQ threshold does
  not behave as configured" that has nothing to do with silicon.

- The DS-side contract it was fixed *to* is §6.10.1 Table 6-50 (p.126), verbatim field semantics:
  > "`rx_fifo_irq_enable` defines for all bits set in this parameter, the corresponding Rx FIFO flag
  > that triggers the RxFifo IRQ. `tx_fifo_irq_enable` defines for all bits set in this parameter,
  > the corresponding Tx FIFO flag that triggers the TxFifo IRQ. […] `tx_low_threshold` sets the
  > threshold level to use for the Tx FIFO low flag. […] `tx_high_threshold` sets the threshold
  > level to use for the Tx FIFO high flag."
  > Flags: "`0x01: FifoEmpty` / `0x02: FifoLow` / `0x04: FifoHigh` / `0x08: FifoFull` /
  > `0x10: FifoOverflow` / `0x20: FifoUnderflow`."

### 5.3 Other LR2021 workaround-labelled work in the commit log (all non-errata, non-FIFO)

- PR **#1864** / commit `67d7121d2a` (2026-09-13) "[LR2021] Feature: Add DCDC mode for LR2021" —
  ports Semtech's `lr20xx_workarounds.c` DCDC code into RadioLib.
- Issue **#1879** (closed, opened 2026-09-28T10:00:44Z) "The DC-DC workaround for LR2021 is
  flagging as a potential buffer overrun": `setDCDCworkaround()`/`resetDCDCworkaround()` passed
  `sizeof(uint32_t)` as the *word count* to `readRegMem32()`/`writeRegMem32()`, moving 4 words where
  1 was intended (12 bytes of stack past the local `uint32_t`), ASAN-confirmed. Explicitly
  "**Semtech's reference implementation … passes `1`**."
- PR **#1880** / commit `3509dbc8e6` (2026-09-28) "Pass 1, as Semtech's reference implementation
  does. **Regression from #1864.**" Addendum in the same PR: `LRxxxx::writeCommon()` sends one byte
  too many on LR2021 (3-byte address written, `4 + 4*len` sent) — fixed by `94755e9ca`.

  **⇒ Both are RadioLib-side regressions/fixes; neither is a silicon erratum and neither touches
  FIFO thresholds or TX underrun.** They matter here only as the reason `setDCDCworkaround()` now
  runs on *every* `setRxPath()` / LoRa modulation change — i.e. more SPI traffic around TX
  staging, but no FIFO-threshold effect.

- Commit search `LR2021+workaround` → 3 commits, all of the above. `FifoIrq` commit search → 0
  (the fix landed under the PR merge, not a commit message containing "FifoIrq").

### 5.4 RadioLib items that *look* errata-adjacent but are not

- **#1804** "Stops receiving packets larger than the last transmitted packet (explicit header
  mode)" — real and TX-adjacent (a TX corrupts subsequent RX), but root-caused in the issue body to
  `LR2021::stageMode(TX)` writing `cfg->transmit.len` into the LoRa packet params and RX not
  restoring them. **RadioLib state-machine bug, not silicon.**
- **#1857** "[LR11x0][LR2021] Reply to a get command is sometimes read before the chip has it
  ready" — SPI read-timing race with the chip's status stream; host-side sequencing.
- **#1829** FLRC throughput limited by per-packet `standby()`/`startReceive()` overhead — host
  driver overhead.
- **#1843** "New functions to support fewer missed transmissions" — feature request (`resumeReceive`).
  Not an erratum.
- **#1861** broken LoRa header (-24) in CAD Rx exit mode — user-side CAD config; not an erratum note.

---

## 6. What DS Rev 2.2 actually says about the four target features (so the UNKNOWN in §0 is bounded)

Included so a downstream consumer can see the *edge* of the documentation, i.e. exactly where
"UNKNOWN" begins.

### 6.1 Continuous TX — documented, and nothing in the inspected limitations touches it

`SetTxTestMode` (0x020E), DS §21.2 Table 21-2: `mode` `0x01` = infinite preamble, `0x02` =
continuous wave, `0x03` = PRBS9. DS §4.4.5: "In CW mode, the carrier frequency is transmitted
indefinitely until another command is issued to change the mode." `SET_TX_PARAMS` (0x0203) carries
only `{tx_power, ramp_time}` — no continuous field. (Enumerated in detail by card `t_57122640` /
`t_e00b32dc`; restated here only to fix the feature's DS location.)

**Errata status: no §22 entry, no `KNOWN_LIMITATIONS.md` entry, no workaround function, no
RadioLib issue → UNKNOWN, with the caveat of §1.4.**

### 6.2 "auto-TX FIFO trigger" — no such construct exists in DS Rev 2.2

The datasheet's auto-TX mechanism is **`SetAutoRxTx` (0x0211)**, DS §6.3.9 Table 6-15 (p.108) — and
it is **event-driven, not level/FIFO-driven**:

> "The command `SetAutoRxTx` allows to automatically switch to Tx after an RxDone, or to Rx after a
> TxDone (depending on the `Mode` value), with a programmable `Delay` and a specific `Timeout` for
> the Tx/Rx. **This mode can only be triggered once, and must be re-enabled: it is automatically
> disabled once triggered.**"
> `Mode`: `0x0` `AUTO_MODE_NONE`; `0x1` `AUTO_MODE_ALWAYS`; `0x2` `AUTO_MODE_OK`.
> `clear`: disables AutoRxTx on a TxTimeout/RxTimeout, and on an RxDone with an invalid packet in
> `AUTO_MODE_OK`. `Delay` in 1/32 MHz steps, "allowing a maximum of **134 seconds** delay."

The only hardware *triggers* are the **DIO Rx/Tx triggers** (§5.5, p.84): "When a DIO pin is
configured as an Rx or Tx trigger, it starts an Rx or Tx sequence (behavior identical to `SetRx` or
`SetTx` command)… During this sequence, the default timeouts (configured with
`SetDefaultRxTxTimeout`) are applied." §5.5 also documents a real, in-main-body behaviour (not §22,
not errata): "*If a command initiating a mode change is already ongoing when a DIO trigger is
received, the trigger is discarded, and the error bit `CHIP_BUSY` is set*".

**⇒ "auto-TX **FIFO** trigger" has no counterpart register or command.** FIFO levels trigger
**IRQs** (§6.10.1), never a TX start. Any downstream spec using that phrase is conflating
`SetAutoRxTx`/DIO triggers with `ConfigFifoIrq`.

> **Cross-reference (sibling card, same conclusion, deeper evidence):** `t_84477ffe` — "Answer: does
> SET_AUTO_RX_TX (0x0211) support auto-TX FIFO trigger?" — was dispatched separately and published
> as `answers/t_84477ffe-auto-tx-fifo-trigger.md` (origin/main `d4d17b7f`). It answers the
> register-level half of this card's step 2 in full: complete 0x0211 bitfield with three-source
> cross-checks (DS Table 6-15 / DRV `lr20xx_radio_common.c:546-558` / LIB), the `tx_low_threshold` /
> `tx_high_threshold` byte-range semantics, and the one-shot-vs-edge-trigger distinction between
> `SET_AUTO_RX_TX` and the FIFO-threshold IRQ. It also flags a RadioLib `autoTxRx()` byte-packing
> discrepancy vs the datasheet. Its verdict ("NO — FIFO thresholds feed only the `ConfigFifoIrq` IRQ
> path, which never changes radio mode") is consistent with §6.2 here; this card adds only the
> **errata/silicon-revision** dimension, i.e. that no errata document bears on it either.

### 6.3 TX underrun — flag documented, *action* undocumented, and no errata on top

DS §5.3.2 "Tx Data FIFO" (p.78), verbatim:

> "For payloads superior to 256 bytes, the Tx FIFO has to be written when data is being
> transmitted, **avoiding an underflow of the Tx FIFO**, using the threshold informations available
> through the API or the DIOs."

The underflow **flag/IRQ** exists (`FifoUnderflow = 0x20`, DS Table 6-50; readable without enabling
IRQ via §6.10.2 `GetFifoIrqFlags`). The device **action** on underflow (abort / pad / stall) is
**not stated anywhere** in DS Rev 2.2, and — the point of this card — **no errata note supplies it
either**: `underflow` occurs on exactly 4 lines of the datasheet (S3) and in exactly one line of
AN1200.104 (a restatement of the flag table), and in **zero** lines of §22, `KNOWN_LIMITATIONS.md`,
`lr20xx_workarounds.{h,c}`, the driver README, or the RadioLib tracker.

---

## 7. Silicon-revision scope — what *is* stated, and the PRAM channel

| Item | Statement | Source |
|---|---|---|
| Applicability of the workaround catalogue | "expected to be used for LR20xx **engineering samples** (date code: `2513`, version `0x0110`)" | driver README, `errata/semtech-usp-lr20xx_driver-README.md:27` |
| Revision gating in code | **none** — no `GetVersion` read, no revision `#ifdef`; only 3 macros that disable *automatic application* | `lr20xx_workarounds.c` (0 `#if`), `.h:57/63/69` |
| Chip version read path | `GetVersion` 0x0101 (§6.7.2 Table 6-40); LR2021 `FWMajor=0x01`, `FWMinor=0x18` | DS §6.7.2 |
| Silicon-limitation fix channel | **PRAM**: "the LR202x transceiver family is provided with a program (PRAM) that can be loaded into the chip to **optimize performance and provide a workaround for some limitations**. While not strictly required, using the chip without the PRAM can create **performance issues and unexpected bugs**." | DS §22.3 |
| PRAM load/verify | write to `0x801000` via `WriteRegMem32`; activate opcode `0x012D` arg `0x00`; verify `0x800FF8 == 0x600DB002`; version `0x800FFC` → `(v>>8)&0xFFFF`; lost after reset/cold sleep, kept in sleep-with-retention; +80 nA | DS §22.3.1–22.3.2 |
| PRAM's own enumerated effects | Z-Wave: last-received-packet channel in `GetZwavePacketStatus`; OQPSK: bypass flag for received-length check | DS §22.3 |

**⇒ PRAM is the one documented mechanism by which a silicon revision affects behaviour, and it is
the only place a hidden TX/FIFO fix could live.** Card `t_da19111d` found no enumeration of PRAM
contents, no PRAM release notes, and no statement that any PRAM revision fixes a TX-FIFO or
TX-continuous defect. **UNKNOWN** — and PRAM release history is a good candidate for a follow-up
card (see §8).

---

## 8. Explicit UNKNOWN statement, and what would falsify it

**No LR2021 errata document was obtainable.** Per the task's step 4, this is stated as
*no document located*, **not** as "no errata exist":

- **No stand-alone errata sheet** — independently re-verified (L1–L3; also `provenance.md` §3.1
  F1–F12, F18–F19). There is no Semtech "errata" category on the LR2021 product page, no
  errata-named file anywhere in this corpus (`provenance.md` §3.2: `errata|erratum|known issue` =
  0 matches across the datasheet + AN1200.101/.102/.104), and GitHub global repo/issue search for
  "LR2021 errata" yields no errata document.
- **One in-datasheet limitations chapter does exist** (§22, E1) and **was read end-to-end** — it
  lists 4 limitations, **none** of the four target features. This is the "document found, lists no
  relevant errata" case, and it is reported as such.
- **Two Semtech known-limitation artifacts exist** (`KNOWN_LIMITATIONS.md`, `lr20xx_workarounds.{h,c}`
  + driver README) and **were read end-to-end** — 10 and 22 entries respectively, **none** of the
  four target features.
- **RadioLib** has no LR2021 erratum claim anywhere (in-tree snapshot, commit log, or tracker);
  its only FIFO-relevant item is a host-driver wire-format bug (#1848/#1849).

**Would falsify / is still open (candidate follow-up work, not attempted here):**

1. `AN1200.103`, `AN1200.106`, `AN1200.107` (on the product page at L1, absent from the corpus) —
   the "Improvements"-family app notes are where silicon changes are described; AN1200.101/.102 are
   0-errata but are different documents.
2. Semtech PRAM release notes / PRAM version history (DS §22.3 gives the version *read* path but no
   changelog).
3. Semtech support/KB (login-gated; `support/technical-support` → 404).

---

## 9. Acceptance summary

| Acceptance criterion | Where satisfied |
|---|---|
| Every erratum claim has a citation | §2 (DS §22, page/section + verbatim quotes), §3 (entry numbers), §4 (`.h`/`.c` file:line + README line), §5.2–§5.3 (issue/PR numbers, merge dates, commit SHAs, quoted bodies/diffs) |
| Absence of evidence reported as UNKNOWN, never "no errata" | §0 and §8 — worded "no document located" / "UNKNOWN"; §2's negative result is separately worded "document found; lists no relevant errata" |
| Search locations are listed | §1.1 (S1–S11, in-corpus, with commands), §1.2 (L1–L7, live re-verification), §1.3 (inherited F1–F19), §1.4 (still-open) |
| Distinguish "no document" from "document with no relevant errata" | §1.4 + §8 vs §2/§3/§4 — the three documents *found* are enumerated in full and each entry's relevance is scored |
| Driver source / commit log checked for errata-labelled workarounds | §5.1 (in-tree grep), §5.2–§5.3 (commit log + `search/commits` for `errata`/`silicon`/`workaround`); the DCDC port is the only LR2021 workaround machinery and it is RX-path |
| Revision scope + workaround recorded per hit | §4 (only revision statement in existence: "engineering samples, date code `2513`, version `0x0110`"; workaround per function), §7 (PRAM, `GetVersion`) |

**Target-feature verdicts:** continuous TX = **UNKNOWN** (no errata document); auto-TX FIFO
trigger = **UNKNOWN** (and the construct does not exist in DS Rev 2.2 — §6.2); FIFO IRQ threshold =
**UNKNOWN** for silicon (host-side RadioLib wire-format bug is the cited alternative explanation —
§5.2); TX underrun = **UNKNOWN** for silicon (flag documented, action undocumented — §6.3).

---

## 10. Reproduction

```bash
# full-text extracts (scratch only, outside the repo)
pdftotext -layout semtech-official/LR2021_LR2022_LR2012_Datasheet_v2.2.pdf ds.txt   # 13441 lines
grep -in -E 'erratum|errata|silicon revision|chip revision|stepping' ds.txt        # 0 hits
grep -in 'underflow' ds.txt                                                          # 4 hits
sed -n '12296,12416p' ds.txt | sha256sum   # == committed §22 extract sha256 445b7e22…465a
for a in AN1200.101_LR2021_FLRC_Improvements AN1200.102_LR20xx_LoRaImprovements_Rev1.1 \
         AN1200.104_LR20xx_ModemInterface_v1.0; do
  pdftotext -layout "semtech-official/$a.pdf" "$a.txt"; grep -ic 'errata\|erratum' "$a.txt"; done   # 0 0 0

# negative-evidence sweep over the errata corpus (all four features)
grep -rn -i -E 'AutoRxTx|auto.?Tx|FifoUnderflow|underflow|tx_low_threshold|tx_high_threshold|continuous|infinite preamble|SetTxTestMode' errata/

# live re-verification
curl -sL https://www.semtech.com/products/wireless-rf/lora-plus/lr2021 | grep -oiE 'errata|erratum|known issue' | wc -l   # 0
gh api 'search/repositories?q=LR2021+errata' --jq .total_count                                                          # 0
gh api 'search/issues?q=LR2021+errata' --jq .total_count                                                                # 2 (neither an errata doc)
gh api 'search/issues?q=repo:jgromes/RadioLib+errata' --jq .total_count                                                 # 13 (none LR2021)
gh api 'search/commits?q=repo:jgromes/RadioLib+errata' -H 'Accept: application/vnd.github.cloak-preview' --jq .total_count  # 4 (none LR2021)
gh api repos/jgromes/RadioLib/issues/1848 ; gh api repos/jgromes/RadioLib/pulls/1849/files
```

Artifact hashes (this corpus, for citation stability): §22 extract `445b7e22…465a` ·
`KNOWN_LIMITATIONS.md` `464c2ec1…7d44e` · driver README `50cd3407…b38c` · `workarounds.c`
`b219a288…6976` · `workarounds.h` `1a3b6715…150e` · RadioLib issue index `213ffc92…0eb3`.

<!-- kanban-metadata
{
  "card": "t_da19111d",
  "deliverable": "docs/lr2021-research/answers/t_da19111d-errata-silicon-tx-fifo-irq.md",
  "verdicts": {
    "errata_sheet_located": "NO - not found (re-verified live)",
    "continuous_tx": "UNKNOWN (no errata doc); no limitation entry in any inspected artifact",
    "auto_tx_fifo_trigger": "UNKNOWN; construct absent from DS Rev 2.2 (SetAutoRxTx is event-driven, DIO triggers are not FIFO-driven)",
    "fifo_irq_threshold": "UNKNOWN for silicon; cited non-silicon alternative = RadioLib configFifoIrq wire-format bug #1848 fixed by PR #1849 (commit e3e6fdc7b7, merged 2026-08-11)",
    "tx_underrun": "UNKNOWN for silicon; flag FifoUnderflow=0x20 documented (DS Table 6-50), device action on underflow undocumented"
  },
  "documents_inspected_end_to_end": [
    "datasheet v2.2 SS22 (E1) - 4 limitations, none relevant",
    "Lora-net/usp doc/KNOWN_LIMITATIONS.md (E2) - 10 entries, none relevant",
    "lr20xx_workarounds.h/.c + driver README (E3) - 22 workarounds, none TX-FIFO",
    "RadioLib snapshot + 40-commit LR2021 log + tracker"
  ],
  "only_revision_scope_stated": "engineering samples date code 2513, version 0x0110 (driver README); no version gate in workarounds code",
  "open_for_followup": ["AN1200.103/106/107 not retrieved", "PRAM release notes/version history", "Semtech support KB (login-gated)"]
}
-->
