# OPEN-13 CLOSED — the SX1280 placeholder was WRONG on 20 of 24 pins

**Date:** 2026-10-14 · **Source supplied by the operator:** Semtech *SX1280/SX1281* Data Sheet
**Rev 3.2, March 2020** (DS.SX1280-1.W.APP), Table 2-1 "Transceiver Pinout" + Figure 2-1 "Transceiver
Pin Locations".

**Result: 4 of 24 pins correct. 20 wrong. The routing of U4 is invalid and must be redone.**

## The comparison

| pin | **REAL (DS Rev 3.2)** | real side | **OUR PLACEHOLDER** | verdict |
|---:|---|---|---|---|
| 1 | `VR_PA` | left | `VDD_IN` | **WRONG** |
| 2 | `VDD_IN` | left | `VDD_IO` | **WRONG** |
| 3 | `NRESET` | left | `GND` | **WRONG** |
| **4** | **`XTA`** | left | `NRESET` | **WRONG** |
| 5 | `GND` | left | `BUSY` | **WRONG** |
| **6** | **`XTB`** | left | `NSS` | **WRONG** |
| 7 | `BUSY` | **bottom** | `SCK` | **WRONG** |
| 8 | `DIO1` | **bottom** | `MOSI` | **WRONG** |
| 9 | `DIO2` | **bottom** | `MISO` | **WRONG** |
| 10 | `DIO3` | right | `DIO1` | **WRONG** |
| **11** | **`VBAT_IO`** | right | `DIO2` | **WRONG** |
| **12** | **`DCC_FB`** | right | `DIO3` | **WRONG** |
| 13 | `GND` | right | `ANT_SW` | **WRONG** |
| **14** | **`DCC_SW`** | right | `RFIO` | **WRONG** |
| **15** | **`VBAT`** | right | `GND` | **WRONG** |
| 16 | `MISO_TX` | right | `GND` | **WRONG** |
| 17 | `MOSI_RX` | right | `GND` | **WRONG** |
| 18 | `SCK_RTSN` | right | `GND` | **WRONG** |
| 19 | `NSS_CTS` | top | `GND` | **WRONG** |
| 20 | `GND` | top | `GND` | ok |
| 21 | `GND` | top | `GND` | ok |
| **22** | **`RFIO`** | top | `GND` | **WRONG** |
| 23 | `GND` | top | `GND` | ok |
| 24 | `GND` | top | `GND` | ok |

**Our symbol placed pins 1–13 on the LEFT and 14–25 on the RIGHT. The real part wraps 1–6 left,
7–9 bottom, 10–18 right, 19–24 top, with the exposed pad in the centre.** So **the side assignment is
wrong for 16 of 24 pins** as well as the names.

## Why this is worse than a pin-number shuffle

The placeholder was not a permutation of the real list — it was **a different part's shape**:

- **Our symbol has no `XTA`/`XTB` at all.** They are real pins **4 and 6**, on the **left**.
- **Our symbol has `VDD_IO` and `ANT_SW` — neither exists as a named pin.** The real supplies are
  **`VBAT` (15)** and **`VBAT_IO` (11)**; `ANT_SW` is not a pin on this part.
- **Our symbol has no `VR_PA` (1), no `DCC_FB` (12), no `DCC_SW` (14), no `VBAT` (15).**
- **`RFIO` is pin 22 on the TOP**, not pin 14 on the right.
- The SPI pins are named **`MISO_TX`/`MOSI_RX`/`SCK_RTSN`/`NSS_CTS` (16–19)** — the SX1280 is
  **dual-mode** (SPI *or* UART on the same pins), which is why the names carry both functions.

## What this invalidates

1. **Every trace to and from U4 on the committed hub board is wired to the wrong pads.** Not a
   re-route — a **re-lay**.
2. **`OPEN-1` (SX1280 supply, "pins 1, 2")** was wrong twice over: pin 1 is **`VR_PA`**, not a supply
   input, and the real supplies are **15 `VBAT`** and **11 `VBAT_IO`**, with **pin 2 `VDD_IN`
   explicitly documented as "Connect to Pin 12"** (`DCC_FB`) — a regulator loop the schematic does
   not contain at all.
3. **`OPEN-2` (`RFIO` "pin 14")** — `RFIO` is **pin 22**.
4. **The missing reference is now explained and located:** `XTA`/`XTB` are **pins 4 and 6**. ADR-060
   §1.3 correctly observed *"there is no XTA/XTB pin on the symbol at all"* — **the pins exist on the
   silicon; our symbol never had them.**
5. **The DC-DC is undocumented in our design.** `DCC_SW` (14) + `DCC_FB` (12) + an inductor are the
   SX1280's **buck converter**, which the datasheet says is *"considered switched ON unless otherwise
   stated"* — i.e. it is the default operating mode. **Our schematic has none of it.**

## The pin 0 catch, and why the pad count still works out

`Table 2-1` lists **pins 0–24**, where **pin 0 is the exposed ground pad**. Our symbol numbers the
exposed pad as **25** and its QFN footprint has **25 pads**. **So the pad count is right — it is only
the numbers and functions that are wrong,** and pin 0/25 is the exposed pad in both. That is why the
footprint *appeared* consistent and the defect hid this long.

## Direct answer to the operator's decision

**The operator approved "move U4 in position only — changes no pad mapping".** That premise is now
**false**: the pad mapping is **not** known-correct, so moving U4 would preserve a wrong wiring.

**And the pin-escape question I could not answer is now answerable** — but it must be answered as part
of re-laying the part, not before it:
- SPI group is **16–19**, all on the **right**, and `NSS`/`SCK` sit adjacently at **19/18**;
- `DIO1/2/3` are **8/9/10** — pin 8 and 9 are on the **bottom**, 10 on the **right**;
- `BUSY` is **7** (bottom); `NRESET` is **3** (left);
- `RFIO` is **22** (top);
- **`XTA/ XTB` are 4 and 6 (left)**, so the crystal wants a **quiet left-side** placement.

**This is a genuinely better routing problem than the one we had** — the SPI group is contiguous on
one side of the package — but it can only be exploited once the symbol and footprint are real.

## Required sequence, revised

1. **Rewrite the `SX1280` symbol** with the real pin names, numbers and side assignment.
2. **Verify `SX1280_QFN24.kicad_mod` against Figure 17-3 "QFN 4x4mm Land Pattern"** — a placeholder
   land pattern is as dangerous as a placeholder pinout.
3. **Add the missing support circuitry** the real part requires and our schematic never had:
   **`XTA`/`XTB` crystal (or TCXO on `XTA`) + load caps**, the **`DCC_SW`/`DCC_FB` buck** (inductor +
   caps) or an explicit decision to run it disabled, and the **`VBAT`/`VBAT_IO` decoupling** that
   `OPEN-33` asks for.
4. **Then** place, route, DRC.

**Steps 1–3 are schematic work.** `U4` cannot be routed, and the hub board cannot be ordered with `U4`
populated, until they are done. **This is the correct blocker, and closing `OPEN-13` found more than it
was asked to.**

## The FOOTPRINT is nearly right — but off by three pins (corrected measurement)

**My first footprint check reported "PACKAGE-LEVEL: INCONSISTENT". That was MY INSTRUMENT, not the
footprint.** It sorted *every* pad with `x > 0` by `y`, which mixes the right-hand column with the
BOTTOM-row pads, producing a bogus "uneven pitch" of `[0.0, 0.0, 0.7, 0.5, ...]`. Regrouped by
physical side, the real numbers are:

| side | pads | run-spacing |
|---|---|---|
| LEFT | 1–6 | **0.500 mm** |
| BOTTOM | 7–12 | **0.500 mm** |
| RIGHT | 13–18 | **0.500 mm** |
| TOP | 19–24 | **0.500 mm** |

| check | datasheet | our footprint | verdict |
|---|---|---|---|
| perimeter pads | 24 | **24** | ✅ |
| pitch | 0.5 mm | **0.500 mm every side** | ✅ |
| pad-centre span | ≤ 4 mm for 4×4 | **3.900 mm** | ✅ |
| exposed pad | 4×4 E-pad | 2.600 × 2.600 mm, pad 25 | plausible |
| **pin→side map** | **1–6 L, 7–9 B, 10–18 R, 19–24 T** | **1–6 L, 7–12 B, 13–18 R, 19–24 T** | ❌ **off by three** |

**So the land pattern is a competent 4×4 mm QFN24 — it is only the pin→side assignment that is wrong,
at exactly THREE pins: 10, 11 and 12.** Our footprint puts them on the **BOTTOM**; the datasheet puts
**10–18 all on the RIGHT.**

**That the corner pads are right is worth stating:** pads 1, 6, 7, 13, 18, 19 and 24 land correctly, so
the footprint was not drawn at random — it looks like a 6/6/6/6 layout applied to a part whose middle
group is **6 / 3 / 9 / 6**. That is a *small, exact* defect: three pads moved from BOTTOM to RIGHT, and
the pin names corrected.

**Still not provable from text:** the pad **sizes** and the exact **E-pad** dimensions live in
Figure 17-3, which is a **drawing** — its dimensions are not in the extracted text. **To close that
last gap the figure must be rendered and read.** Stating the limit is part of the finding.

**Corrected conclusion: the SYMBOL is wrong on 20 of 24 pins (a re-lay), and the FOOTPRINT is wrong on
3 of 24 (a three-pad fix).** Both must be fixed before any `U4` copper is trusted — but they are very
different sizes of job, and saying so is the difference between a re-lay and a patch.

## Note on the second supplied link

`https://www.alldatasheet.com/datasheet-pdf/download/1148172/SEMTECH/SX1280.html` is a bot-walled
mirror; **the DigiKey-hosted Rev 3.2 PDF worked and is the source used above.** Table 2-1 and
Figure 2-1 are quoted verbatim; **nothing here is inferred from a secondary source.**
