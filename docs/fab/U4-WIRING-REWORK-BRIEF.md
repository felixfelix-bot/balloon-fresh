# U4 (SX1280) WIRING REWORK — task brief

**Repo:** `balloon-fresh`, worktree `/home/c08r4d0r/worktrees/v9-route`
**Branch:** `v9-route` (push to `github` → `master`, and `ngit` → `main`)
**File:** `tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`
**Authority:** `docs/fab/SX1280-WIRING-SPEC.json` (+ `.md`) — every connection, already decided.

## Why this is needed (measured, not assumed)

Step 1 replaced U4's placeholder symbol with the **real** datasheet pinout. KiCad connects by **pin
number**, so the existing wires re-landed on real pins. Measured damage:

| pin | real name | currently reaches | hazard |
|---|---|---|---|
| 1 | `VR_PA` | **`+3V3`** | **`VR_PA` is a regulator OUTPUT** — this shorts +3V3 against it |
| 2 | `VDD_IN` | `/SX1280_RESET_N` | reset drives a supply input |
| 3 | `NRESET` | `/SX1280_CS_N` | **chip-select RESETS the radio** |
| 4 | `XTA` | `/SX1280_MOSI` | **MOSI drives a crystal pin** |
| 5 | `GND` | `/SX1280_DIO1` | signal shorted to ground |
| 6 | `XTB` | `/SX1280_DIO3` | DIO3 drives a crystal pin |
| 14 | `DCC_SW` | **`GND`** | **disables the radio's internal regulator** |

## The structural problem you must solve

The old wiring is a **13-row stub field at 2.54 mm pitch**, on both the left (x = 314.96 → 320.04)
and right (x = 350.52 → 355.60) sides. Wire columns measured at:

```
x= 314.96  13 pts: y = 35.56 38.10 40.64 43.18 45.72 48.26 50.80 53.34 55.88 58.42 60.96 63.50 66.04
x= 320.04  13 pts: same y values          <-- LEFT PIN COLUMN
x= 350.52  12 pts: y = 35.56 .. 63.50     <-- RIGHT PIN COLUMN
x= 355.60  12 pts: same y values
```

The **real** part has **6 left / 3 bottom / 9 right / 6 top** pins at **5.08 mm** pitch. So **2.54 mm
stubs do not line up with the new pins, and the stub field cannot be reused.** Labels live on stubs
**5.08 mm away from the pin** (e.g. `SX1280_RESET_N` at `(314.96, 43.18)` for the pin at
`(320.04, 43.18)`).

**Therefore: rebuild the stubs and labels.** Do not attempt to relabel in place.

## EXACT pin coordinates (already computed — use these, do not re-derive)

U4 instance origin `(335.28, 50.80)`, rotation `0`. Absolute connection point of each pin:

```
pin  0 GND       (335.28, 50.80)   [exposed pad]
pin  1 VR_PA     (320.04, 38.10)   pin  2 VDD_IN   (320.04, 43.18)
pin  3 NRESET    (320.04, 48.26)   pin  4 XTA      (320.04, 53.34)
pin  5 GND       (320.04, 58.42)   pin  6 XTB      (320.04, 63.50)
pin  7 BUSY      (328.93, 71.12)   pin  8 DIO1     (335.28, 71.12)
pin  9 DIO2      (341.63, 71.12)   pin 10 DIO3     (350.52, 65.02)
pin 11 VBAT_IO   (350.52, 61.47)   pin 12 DCC_FB   (350.52, 57.91)
pin 13 GND       (350.52, 54.36)   pin 14 DCC_SW   (350.52, 50.80)
pin 15 VBAT      (350.52, 47.24)   pin 16 MISO_TX  (350.52, 43.69)
pin 17 MOSI_RX   (350.52, 40.13)   pin 18 SCK_RTSN (350.52, 36.58)
pin 19 NSS_CTS   (344.35, 30.48)   pin 20 GND      (340.72, 30.48)
pin 21 GND       (337.09, 30.48)   pin 22 RFIO     (333.47, 30.48)
pin 23 GND       (329.84, 30.48)   pin 24 GND      (326.21, 30.48)
```

## Target nets (from `docs/fab/SX1280-WIRING-SPEC.json`)

```
 1 VR_PA   -> /SX1280_VR_PA   (NOT a rail -- bypassed by C5; see the trap below)
 2 VDD_IN  -> /SX1280_VDD     (regulator node: ties to pin 12, L4.p2, C9.p1, C6.p1)
 3 NRESET  -> /SX1280_RESET_N
 4 XTA     -> /SX1280_XTA     (crystal)
 5 GND     -> GND
 6 XTB     -> /SX1280_XTB     (crystal)
 7 BUSY    -> /SX1280_BUSY
 8 DIO1    -> /SX1280_DIO1      9 DIO2 -> /SX1280_DIO2     10 DIO3 -> /SX1280_DIO3
11 VBAT_IO -> /SX1280_VBAT_IO  12 DCC_FB -> /SX1280_VDD    13 GND -> GND
14 DCC_SW  -> /SX1280_DCC_SW   15 VBAT -> +3V3             16 MISO_TX -> /SX1280_MISO
17 MOSI_RX -> /SX1280_MOSI     18 SCK_RTSN -> /SX1280_SCK  19 NSS_CTS -> /SX1280_CS_N
20,21,23,24 GND, pin 0 GND     22 RFIO -> /SX1280_RF
```

## Parts to ADD (values from the vendor — Table 15-1 / Figure 15-1)

`C` and `R` already exist in `lib_symbols`; **only `Q1` (crystal) and `L4` (inductor) need new
definitions.**

| ref | value | LCSC | pins |
|---|---|---|---|
| `C5` | 10 nF | `C15195` | `VR_PA` ↔ GND |
| `C6` | 10 nF | `C15195` | `V_DCC` ↔ GND |
| `C8` | 100 nF | 0402 X7R | `VBAT_IO` ↔ GND |
| `C10` | 100 nF | 0402 X7R | `VBAT` ↔ GND |
| `R15` | 0 Ω | `C17168` | `VBAT` ↔ `VBAT_IO` |
| `L4` | 15 µH | `C2826623` | `DCC_SW` ↔ `V_DCC` |
| `C9` | 470 nF | `C47339` | `V_DCC` ↔ GND |
| `Q1` | 52 MHz | `C7502106` | `XTA`/`XTB` + 2× GND (4-pad) |

**RF network** (7 parts, values now known — `docs/fab/SX1280-RF-SECTION.md`):
`C0` 0.8 pF, `C1`/`C2` 1.2 pF, `C3` 100 pF, `C4` 0.5 pF, `L1` 3.0 nH, `L2` 2.5 nH
Topology: `RFIO → C0↓ → L1 → C1↓ → (L2 ∥ C4) → C2↓ → C3 → ANT5 (U.FL)`

## THREE TRAPS — do not walk into these

1. **`VR_PA` (pin 1) must NOT go to `+3V3`.** It is a regulator **OUTPUT**; the datasheet bypasses it
   with `C5` to GND. Wiring it to a rail is the **original defect**.
2. **`L4` and `C9` are MANDATORY.** The datasheet says the internal DC-DC is *"considered switched ON
   unless otherwise stated"* — omitting them leaves an **open regulator loop**.
3. **NO crystal load capacitors.** The datasheet's foot capacitances are **internally integrated**
   (`Cload = 10 pF` stated in Table 15-1). Do not add them; do not "repair" their absence.

## Method requirements (this repo's discipline — learned the hard way)

- **Template whitespace from a file that already parses.** Never hand-build tabs. The symbol rewrite
  cost **six failed attempts** because indentation was guessed instead of templated.
- **Assert paren balance before and after**, and **assert the tab profile** of the template.
- **`kicad-cli sch export netlist` must succeed before writing.** A file that does not parse is worse
  than no change.
- **Validate the RESULT, not the intent:** after writing, export the netlist and assert every pin's net
  matches the target table above. **A generator that reports success while writing a broken file is the
  failure mode that wasted most of this campaign.**
- **Note:** `bidi` is **NOT** a valid KiCad pin electrical type — use **`bidirectional`**. One invalid
  token silently breaks the whole file (this cost six attempts).
- Net names in the exported netlist carry a **leading `/`** (hierarchical sheet path), e.g. the label
  `SX1280_RESET_N` exports as `/SX1280_RESET_N`. Match accordingly.

## Definition of done

1. `kicad-cli sch export netlist` succeeds on the modified schematic.
2. Exported netlist shows **every** U4 pin on its target net (the table above), with **zero**
   mismatches.
3. The 7 wrong connections are gone and the 7 new parts + RF network are present and wired.
4. `python3 tracker/hardware/tests/test_netlist_integrity.py` passes.
5. Committed with a conventional message and **pushed to both remotes**
   (`git push github HEAD:master` and `git push ngit HEAD:main`).
6. `REPORT.md` written at the worktree root.
