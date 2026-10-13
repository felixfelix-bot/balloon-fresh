# E80-900MBL-02 — Hardware Claims Audit (Task C, 2026-08-17)

Method: read every repo doc mentioning the board, extracted the manual text layer
(pdftotext), and ran a **fresh independent OCR pass** (pdftoppm 600 dpi → tesseract,
full page + 2×/3×/4× region crops) on the vendor schematic PDF that IS in this repo:
`docs/e80-900mbl-02-eval/e80-900mbl-02-spec-id4397.pdf` (1 page, A4 landscape,
image-only, md5 `0c3b7084…` — byte-identical to `~/repos/lr2021-eval/pdfs/` copy).
"OCR-fresh" below = confirmed by this audit's own pass, not just by prior docs.

---

## 1. Claim table

| # | Claim | Source | Grade |
|---|-------|--------|-------|
| 1 | Vendor schematic PDF exists locally | `docs/e80-900mbl-02-eval/e80-900mbl-02-spec-id4397.pdf` (+ identical copy in lr2021-eval) | **VERIFIED** (file present, 1 page) |
| 2 | Vendor manual PDF exists locally, has text layer | `e80-900mbl-02-manual-id4396.pdf`, 389 text lines | **VERIFIED** |
| 3 | MCU = STM32F103**C8**T6 (64K/20K) | FLASHING.md, e80_isp_dump.py, Keil project target; **OCR-fresh: symbol reads `STM32F103C8Tx`** | **VERIFIED** (schema OCR + toolchain agree). NOTE: E80-FLASH-ACCESS-FINDINGS.md says "CBT6" and CAPABILITY_REPORT says "schematic shows CBT6" — both contradict my OCR; C8 is best supported. Settle definitively via SWD read of flash-size reg `mdw 0x1FFFF7E0 2` on first contact. |
| 4 | Package = LQFP48 | Inferred from T6 suffix; **OCR-fresh: schematic symbol pin numbers match LQFP48 exactly** (NRST=7, PA13/SWDIO=34, PB3=39, PB4=40, PB5=41, PB7=43, PB8=45, PB9=46, PB2/DIO8=20) | **VERIFIED** (no local datasheet needed — the symbol itself is the evidence) |
| 5 | SWD goes through series resistors to a 4-pin connector | `E80-SPI-BYPASS-WIRING.md` §1; **OCR-fresh: connector `U4` with `SWCLK—R2`, `SWDIO—(R?)`, `+3.3V`, `GND`** | **VERIFIED** (designator of SWDIO resistor NOT resolved — doc says R4, my OCR garbled it) |
| 6 | SWD series R value = 33 Ω (R2=SWCLK, R4=SWDIO) | SPI-BYPASS doc ("labels read 33R/3kR at OCR limits"); my OCR binds `R2` to SWCLK but captured no value; 33R values clearly seen only on the **CH340 UART nets** (`…33R] CH340X_RXD`, `…33R] CH340X_TXD`) | **PARTIAL** — 33 Ω on the *UART* lines is OCR-confirmed; 33 Ω on SWD lines is doc-only, digit uncertain (33 vs 3k). Harmless either way for probing. |
| 7 | U4/debug-header pin ORDER (GND/3V3/SWDIO/SWCLK) | E80-FLASH-ACCESS-FINDINGS "pin ORDER UNVERIFIED"; my OCR hints SWCLK→pin "4", SWDIO→pin "2" (low confidence, could be misread R4) | **UNVERIFIED** — and note: if SWCLK really were pin 4, the physical square pad (pin 1, no GND beep) wouldn't fit U4's numbering → keep an open mind that pads 1/2 might not be SWD |
| 8 | 4 back pads near USB: pad3=GND, pad4=3V3 (beep-confirmed), pads 1/2 = SWCLK/SWDIO presumed | Bench beep test (task context, most recent); FINDINGS doc says "2×2 cluster" while latest bench says **straight line** [1 sq][2-4 round] | GND/3V3 **VERIFIED (bench)**; pads1/2 = SWD **PRESUMED — UNVERIFIED** (SWD failed in both orders; layout discrepancy 2×2 vs line unresolved) |
| 9 | CH340 ↔ STM32: `USART1_TX ↔ CH340X_RXD`, `USART1_RX ↔ CH340X_TXD` | **OCR-fresh: both net labels on schematic** (near MCU right side + at J2-14/16 area); demo fw uses USART1 @115200 (main.c); F103 USART1 is pin-fixed TX=PA9/RX=PA10 | **VERIFIED** (schematic nets + F1 architecture + working transparent-bridge behavior) |
| 10 | CH340 ↔ PA9/PA10 specifically | Follows from #9 + F1 fixed AF; pin numbers 30/31 only weakly OCR'd ("50"/garble) | **VERIFIED by inference** (F103 has no alternate USART1 mapping — if USART1 works over CH340, it IS PA9/PA10) |
| 11 | J2-14 = MCU_TXD (PA9 net), J2-16 = MCU_RXD (PA10 net) tapped on header | Manual pin table (§2.3, text-layer) + schematic OCR ("42[=14?] USART1_TX CH340X_RXD", "44[=16?] USART1_RX CH340X_TXD") | **VERIFIED** — gives a labeled probe point for the UART nets! |
| 12 | **BOOT0 → 10 k pull-down → GND, no breakout anywhere** | FINDINGS doc (prior OCR+vision pass; itself flags "R2/R6 designation varied between passes"). My fresh OCR: BOOT0 pin label exists on MCU left edge, but **no resistor value/designator resolved near it**; no BOOT0 on J1/J2 (manual text) or U4 (OCR) | **PARTIALLY VERIFIED / WEAK** — see §2. Existence of a strap is corroborated *behaviorally* (demo fw boots & runs ⇒ BOOT0 low at reset; 150 s sync-spam + RESET presses on 2 boards ⇒ ROM ISP not enterable), but "10 k pull-down resistor" as a specific component is NOT independently confirmed |
| 13 | R6 = 10 kΩ pull-**up** on STM32_NRST (to 3V3) + RESET button on same net | SPI-BYPASS doc §1; **OCR-fresh: `R6` + `10K` + `STM32_NRST` cluster below MCU, next to PB4–PB9 pin column** | **VERIFIED** (also proves FINDINGS' "R2/R6 = BOOT0 pulldown" designator attribution wrong — R6 is the NRST pull-up, R2 is the SWCLK series R) |
| 14 | No NRST on debug connector U4 | SPI-BYPASS doc §1 + my OCR of U4 region (only SWCLK/SWDIO/3V3/GND) | **VERIFIED** |
| 15 | No CH340 DTR/RTS → BOOT0/NRST auto-download circuit | FINDINGS + FLASHING.md ("needs live probe verification"); my OCR saw the CH340 `RTS#` *pin label* but could NOT trace it — routing unresolved | **UNVERIFIED** — open lead, see probe plan (b3) |
| 16 | No BOOT0/PA13/PA14 on J1 or J2 | Manual §2.3 tables (text layer) | **VERIFIED** |
| 17 | Stock fw = transparent LoRa bridge, boots 850 MHz +22 dBm SF8 (out of PT band), silent UART | CAPABILITY_REPORT (demo source analysis) + bench observation | **VERIFIED** (behavior observed; RF-safety rules in FINDINGS/HANDOFF stand) |
| 18 | UART ISP dead on stock hw (NO-SYNC both boards, 150 s sync-spam + RESET presses) | `tools/e80_isp_dump.py` run 2026-08-16, FINDINGS doc | **VERIFIED as bench result** (root cause attribution = claim #12, weaker) |
| 19 | RP2040 debugprobe on-pico build: GP2=SWCLK, GP3=SWDIO | HANDOFF doc + tools/debugprobe_on_pico.uf2 v2.3.1 (and a pre-swapped `tools/debugprobe_swap_pins.uf2` exists) | Doc-level, plausible (matches official debugprobe default); **not re-verified here** |
| 20 | SWD fails "cannot read IDR" both pin orders | Bench (task context) | VERIFIED as observation; cause open — pin order, non-SWD pads, or need connect-under-reset |
| 21 | F103 IDCODE 0x1BA01477 expected | HANDOFF doc | From ST docs, from memory — correct for F1; verify on first contact |
| 22 | Board photos (Felix front+back) referenced as evidence | FINDINGS doc §Evidence 3 | **NOT IN REPO** — photos were session-live only; pad observations rest on that session + the newer beep test |
| 23 | "64 KB = full flash" dump size | e80_isp_dump.py/HANDOFF | Correct **iff C8** (claim 3); if CB, dump must be 128 KB — settle via claim-3 register read |
| 24 | repo KiCad files (hub_board_diy etc.) describe the E80 | — | **UNRELATED** — they are our own hub-board designs (no E80 SWD/BOOT0/NRST nets); no E80 vendor CAD in repo |

Datasheet status: **no STM32F103 datasheet exists locally** (repo PDFs are LR2021/chip + E80 kit docs only). All F103 pin numbers below are corroborated by the schematic symbol pin numbers where noted, otherwise **from memory, verify**.

---

## 2. BOOT0 provenance (the specific question)

- The claim originates from a **real schematic we possess** — `e80-900mbl-02-spec-id4397.pdf` — but via a prior session's OCR+**vision** read (the PDF is image-only; pdftotext yields 0 chars). FINDINGS §Evidence 1 cites it as "OCR + vision".
- **This audit re-OCR'd the sheet independently**: the `BOOT0` pin label on the MCU symbol is confirmed, but the claimed **10 k pull-down resistor (value + designator + GND connection) could NOT be re-extracted** — that region OCRs as graphics garbage. The prior pass itself admitted "R2/R6 designation varied between passes", and this audit proves both of those designators belong to other components (R2 = SWCLK series R, R6 = NRST 10 k pull-up).
- **Net verdict: BOOT0-strapped-low is an INFERENCED claim from a possessed-but-barely-readable schematic, strongly corroborated by bench behavior** (stock fw boots and runs; ROM ISP unreachable across 150 s × 2 boards). The specific component (10 k pulldown) remains unverified — treat its pad as "to be found by DMM" (plan b).
- **No NRST or BOOT0 test point/pad is documented anywhere**: manual J1/J2 tables have neither (NRST on J2-3 is the *radio's* reset — manual text + OCR `LR-NRESET`), U4 has no NRST, no jumper/test-point for BOOT0 appears on any sheet pass. The only access points are component pads: R6 (NRST net) and the unverified BOOT0 pulldown.

## 3. Package & pin numbers

Package: **LQFP48** (claim 4 — verified via schematic symbol numbering). No local datasheet; numbers marked ◆ were read off the schematic symbol by this audit, others are **from memory, verify**:

| Signal | LQFP48 pin | Corroboration |
|--------|-----------|---------------|
| NRST | **7** | ◆ OCR `NRST 7` (boot region crop) |
| BOOT0 | **44** | from memory, verify (OCR saw "44" near label, ambiguous) |
| PA13 / SWDIO | **34** | ◆ OCR `34. SWDIO` |
| PA14 / SWCLK | **37** | from memory, verify (SWCLK label OCR'd, number garbled) |
| PA9 / USART1_TX | **30** | from memory, verify (label OCR'd, number garbled "50") |
| PA10 / USART1_RX | **31** | from memory, verify |
| PB0 (radio NRST) | 18 | from main.h pin map (demo fw) |

## 4. Multimeter probe plan (bench human, DMM + iron, no scope)

Conventions: board **UNPOWERED, USB unplugged** for continuity/resistance; use resistance mode (read values, don't trust beep for 33 Ω vs 0 Ω). Known-good reference points: **GND = USB-C shell/mounting holes or back-pad 3; 3V3 rail = back-pad 4 or J2-2/J2-6.**

### (a) Verify CH340 TX/RX really lands on PA9/PA10 (UART ISP would work if BOOT0 lifts)

The schematic shows **33 Ω series resistors on the CH340 side** of both UART nets, and the manual shows the nets tapped at **J2-14 (MCU_TXD = PA9 net) and J2-16 (MCU_RXD = PA10 net)** — labeled pins, no soldering needed:

1. **J2-14 ↔ J2-16**: expect OPEN (>100 k) — different nets. If ~0 Ω, stop, something is wrong with the header mapping.
2. **J2-16 ↔ each CH340 pin** (CH340 = small SOP-8/16 near USB-C, top side): exactly one pin reads **≈33 Ω** → that is CH340 **TXD** → confirms PA10 ← CH340 chain incl. series R.
3. **J2-14 ↔ CH340 pins**: one other pin reads **≈33 Ω** → CH340 **RXD** → confirms PA9 → CH340.
4. **J2-14 or J2-16 ↔ GND**: expect OPEN; **↔ 3V3 rail**: expect OPEN (no pull on these nets).
5. Powered sanity (optional, stock fw idle): DC volts J2-14 and J2-16 vs GND ≈ **3.3 V both** (UART idle-high). A pin stuck at 0 V = wiring problem.

If 2–3 pass, the USB port genuinely terminates on USART1 = PA9/PA10, and the **only** thing blocking UART ISP is the BOOT0 strap → plan (b).

### (b) Locate the BOOT0 pull-down (momentary pull to 3V3 target)

No test point exists; find the resistor by its unique signature:

1. DMM resistance, black on GND. Scan small SMD resistor pads around the **MCU (back side, under/near the radio shield edge closest to USB)**. Signature of the BOOT0 pulldown: **one pad ≈ 0 Ω to GND, the OTHER pad of the same resistor ≈ 10 kΩ to GND** (measuring through the resistor itself), and that free pad **does NOT beep to the 3V3 rail** and **does NOT beep to J1/J2/U4 pads**.
2. Distinguish from the other 10 k on the board (R6, NRST pull-**up**): R6's far end **beeps to 3V3 rail**. BOOT0's far end must not.
3. **Open lead — CH340 handshake**: also measure resistance from CH340 **RTS# and DTR# pins** (pin labels OCR'd on schematic; CH340 near USB-C) to your BOOT0-net candidate and to the NRST net (from (c)). ≈0–1 kΩ on any of these = a hidden auto-download circuit exists → ISP entry may be possible by UART-signals alone (no mod needed). Expect OPEN per current docs.
4. If found: to enter ROM ISP — hold **RESET** pressed, touch a **1 k series** resistor from 3V3 (pad 4) to the BOOT0 free pad (or tack a wire), release RESET, immediately run `stm32flash`/`e80_isp_dump.py`. Remove the strap after flashing. (Momentary 3V3 through 1 k against a 10 k pulldown gives ≈2.7 V — safely above V_IH.)

### (c) Locate NRST (for connect-under-reset — and it may be the SWD fix)

NRST net = R6 pad + RESET button + MCU pin 7. No header pin. Find it without silkscreen:

1. Find **R6**: near the MCU on the **front** side (per schematic region: below/right of MCU between it and the J1 header row) — the resistor whose **one pad ≈ 0 Ω to 3V3 rail (pad 4/J2-2)** and other pad ≈ **10 kΩ to 3V3** (through itself) is R6; its non-3V3 pad = **STM32_NRST**.
2. Killer confirmation: resistance **NRST-candidate ↔ GND while pressing the RESET button** (component #7, near USB edge) drops to **≈0 Ω**; releases back to OPEN/10 k-to-3V3. That pad is NRST, guaranteed.
3. **Use it without soldering for connect-under-reset**: tape/Blu-Tack the RESET button **held down**, board USB-powered, start openocd (`-c 'reset_config none'` connect first, or cmsis-dap with `adapter speed 100`), then release the button — the DP stays alive while the core is held in reset, defeating any firmware that re-pins PA13/14 or sleeps. (Same trick SPI-BYPASS-WIRING §1 already documents for SPI bypass.)
4. Also worth one test before re-soldering anything: with the button taped down, retry SWD on back-pads 1/2 in **both** orders at **low adapter speed (100–500 kHz)**. If it connects now, the earlier "cannot read IDR" was firmware interference, not wiring — and no BOOT0 mod is needed at all.
5. Optional pad-level proof of pads 1/2 = SWD (needs magnification + steady hands): resistance pad↔MCU pin 34 / pin 37 should read ≈ series-R value (33 Ω-ish) — only if (4) fails and before plan-C soldering.

**Priority order for the bench:** (c)4 taped-button SWD retry (2 min, zero solder) → (c) full connect-under-reset → (a) UART chain verification (5 min) → (b) BOOT0 hunt (only if UART ISP is still wanted) → plan C (solder to R2/R4 pads per HANDOFF).

---

## Files

- This audit: `docs/E80-HARDWARE-CLAIMS-AUDIT.md` (new).
- OCR scratch: `/tmp/e80ocr/` (600 dpi render + tesseract outputs; not committed).
- No other repo files modified.
