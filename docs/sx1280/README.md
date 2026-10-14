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
