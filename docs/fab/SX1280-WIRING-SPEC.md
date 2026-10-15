# SX1280 (U4) wiring spec — the authority for the redraw

Machine-readable version: `SX1280-WIRING-SPEC.json` (same directory).

**Why this exists.** Step 1 replaced U4's placeholder symbol with the real datasheet pinout. KiCad
connects by **pin number**, so installing the real table re-landed the existing wires on the real pins
and U4's connectivity **collapsed from 13 nets to 7** — landing on functions that do not match the net
names (`+3V3` on `VR_PA`, `/SX1280_CS_N` on `NRESET`, `GND` on `DCC_SW`). The wiring has to be redrawn,
and this file states every connection so that work is deterministic rather than re-derived.

## The 7 wrong connections, and why each is dangerous

| net | sits on | that pin is | the hazard |
|---|---|---|---|
| `+3V3` | 1 | **`VR_PA`** | a regulator **OUTPUT** — feeding it is a short against the regulator |
| `/SX1280_RESET_N` | 2 | `VDD_IN` | a supply input |
| `/SX1280_CS_N` | 3 | `NRESET` | holds the chip in reset |
| `/SX1280_MOSI` | 4 | `XTA` | a crystal pin |
| `/SX1280_DIO1` | 5 | `GND` | — |
| `/SX1280_DIO3` | 6 | `XTB` | a crystal pin |
| `GND` | 14 | **`DCC_SW`** | **disables the radio's internal regulator** |

## What must be added

| part | value | LCSC | tier | pins |
|---|---|---|---|---|
| `C10` | 100 nF | 0402 X7R | expand | VBAT ↔ GND |
| `R15` | 0 Ω | `C17168` | **base** | VBAT ↔ VBAT_IO |
| `C8` | 100 nF | 0402 X7R | expand | VBAT_IO ↔ GND |
| `C5` | 10 nF | `C15195` | **base** | `VR_PA` ↔ GND |
| `C6` | 10 nF | `C15195` | **base** | `V_DCC` ↔ GND |
| `L4` | 15 µH | `C2826623` | expand | `DCC_SW` ↔ `V_DCC` |
| `C9` | 470 nF | `C47339` | expand | `V_DCC` ↔ GND |
| `Q1` | 52 MHz | `C7502106` | expand | `XTA`/`XTB` + 2× GND |

**`V_DCC` node** = `L4.p2 · C9.p1 · C6.p1 · U4.12 (DCC_FB) · U4.2 (VDD_IN)` — the regulator output.

**`L4` and `C9` are mandatory**: the datasheet says the internal DC-DC is *"considered switched ON
unless otherwise stated"*, so omitting them leaves an **open regulator loop**.

**`C5` is a bypass on a regulator OUTPUT**, not a supply feed — the tempting reading is the wrong one.

**No crystal load capacitors.** Figure 15-1 shows none; the datasheet says the foot capacitances are
**internally integrated**. Do not add them, and do not "fix" their absence.

## Signal map

| net | → pin |
|---|---|
| `/SX1280_RESET_N` | 3 `NRESET` |
| `/SX1280_CS_N` | 19 `NSS_CTS` |
| `/SX1280_SCK` | 18 `SCK_RTSN` |
| `/SX1280_MOSI` | 17 `MOSI_RX` |
| `/SX1280_MISO` | 16 `MISO_TX` |
| `/SX1280_BUSY` | 7 |
| `/SX1280_DIO1/2/3` | 8 / 9 / 10 |
| `+3V3` | **15 `VBAT`** |
| `GND` | 5, 13, 20, 21, 23, 24, and pin 0 (exposed pad) |

## Two items that need the operator

1. **`RFIO` (pin 22) cannot be wired yet.** Figure 15-1 prints the matching/filter network
   `C0/L1/C1/L2/C4/C2/C3` with **no values** — described as layout-, frequency- and antenna-dependent.
   **Not guessed.**
2. **`/SX1280_ANT_SW` has no home.** The placeholder had an `ANT_SW` pin; **the real part does not.**
   Either an external RF switch is intended (**needs a control GPIO from `U1`, not `U4`**) or the net
   is vestigial from the placeholder. **This is a design ruling, not a wiring choice.**
