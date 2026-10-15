# SX1280 primary sources

Files here exist for one reason: **to close `OPEN-13`** — the gap that said the `SX1280` symbol's pin
numbering and the `SX1280_QFN24` land pattern were **unverified placeholders**. That gap stayed open
across many sessions because the Semtech datasheet **could not be retrieved from the build host**, so
the record that closes it is kept here rather than only in a chat log.

## Files

| file | what it is |
|---|---|
| `SX1280-81_Rev3.2_Mar2020.pdf` | **SX1280/SX1281 Data Sheet Rev 3.2, March 2020** — doc id `DS.SX1280-1.W.APP`, 158 pages, 2,526,810 bytes. The vendor's own file, **unmodified**. |
| `SX1280-81_Rev3.2_Mar2020.text-extract.txt` | `pdftotext -layout` extraction of the same PDF (470,645 bytes). Keep it: **the decisive evidence is text** — Table 2-1 and Figure 2-1 — and a text extract is greppable and diffable where a 158-page PDF is not. |

## Provenance

Supplied by the operator as
`https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/483/SX1280-81_Rev3.2_Mar2020.pdf`
and retrieved **HTTP 200, 2,526,810 bytes**. SHA256 is recorded in the commit that added these files.

A **second link the operator supplied is bot-walled** and was therefore not used:
`https://www.alldatasheet.com/datasheet-pdf/download/1148172/SEMTECH/SX1280.html`. Recorded as
tried-and-not-used rather than silently dropped.

Vendoring vendor datasheets is **established practice here**, not a new one — see
`docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` and `docs/lr2021-research/semtech-official/`.

## What is proved by these files

Everything in `../fab/OPEN-13-CLOSED-SX1280-PINOUT.md` is quoted **verbatim** from this PDF —
**nothing is inferred from a secondary source**:

- **Table 2-1 "Transceiver Pinout"** (page 17) — the real pin names and numbers, **pins 0–24**.
- **Figure 2-1 "Transceiver Pin Locations"** (page 18) — the physical side of each pin.
- **§17.1 / §17.4** — the package is **QFN24 4×4 mm, 0.5 mm pitch**.
- **§17.5** — thermal: **9 thermal vias** recommended, `ΘJA` 50.3 °C/W.

## What is NOT proved here

**§17.3 "Land Pattern" is Figure 17-3 — a DRAWING.** Its dimensions are **not in the text**, so this
extract cannot verify the pad **sizes** or the exact **E-pad** dimensions of `SX1280_QFN24.kicad_mod`.

**To close that last gap the figure must be rendered and read.** Stating the limit is part of the
record — a text extract that is trusted past its evidence is exactly how a placeholder survives.


## Figure 17-3 — QFN 4x4mm Land Pattern

`Figure17-3-QFN4x4-LandPattern.png` is page 153 of the vendored PDF, rendered at 200 dpi:

    pdftoppm -f 153 -l 153 -r 200 -png SX1280-81_Rev3.2_Mar2020.pdf Figure17-3

It is kept as an IMAGE rather than transcribed numbers because it is a DRAWING: the dimension
callouts live in the vector art, and a text extract cannot carry them. Reading it with a vision
model is what closed the land-pattern question.

What it says (read from the rendering):

    X = 0.30 mm   pad width
    Y = 0.80 mm   pad length (radial)
    P = 0.50 mm   pad pitch
    H = 2.70 mm   exposed pad
    K = 2.70 mm   exposed pad
    Z = 4.80 mm   pad-centre span
    6 pads per side

Verify the footprint against it with `tracker/hardware/verify_fp_fig173.py`.


## Figure 15-1 — Transceiver Application Design Schematic

`Figure15-1-Application-Schematic.png` is page 145, rendered at 200 dpi:

    pdftoppm -f 145 -l 145 -r 200 -png SX1280-81_Rev3.2_Mar2020.pdf Figure15-1

This is the source for the support-part selection in `docs/fab/SX1280-SUPPORT-PARTS-SELECTION.md`:
the 52 MHz crystal (Q1), the DC-DC filter (L4 15 uH, C9 470 nF), the supply bypassing (C5/C6 10 nF,
C8/C10 100 nF) and the 0 R rail link (R15).

TWO THINGS TO KNOW BEFORE TRUSTING IT:

1. **No external crystal load capacitors are drawn.** The datasheet states the foot capacitances are
   internally integrated, which is why the crystal must be specified AT C_LOAD = 10 pF. Reading the
   absence as "we forgot them" would produce a wrong BOM.
2. **The RF network C0/L1/C1/L2/C4/C2/C3 have NO VALUES printed.** They are described as layout-,
   frequency- and antenna-dependent. They are NOT derivable from this document and must not be
   guessed.

Page 147 holds Figure 15-3 (the optional TCXO variant) if the crystal is ever replaced.
