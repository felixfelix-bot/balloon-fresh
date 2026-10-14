# ORDER PACKAGE AUDIT — extensions: the CPL dropped U1, the BOM lacks LCSC numbers

**Date:** 2026-10-14 · **Status:** ⚠ **ORDER-BLOCKING.** Continues `ORDER-PACKAGE-AUDIT.md`.
**Continues from:** the two false `✅`s (gerbers + ZIP that did not exist).

---

## 3. THIRD false claim — "2 DNP rows verified" was false

Checklist C3 said: *"BOM: single-variant platform, GPS + baro as DNP rows | ✅ 2 DNP rows
verified."*

**Measured: NO footprint on the board carried the DNP flag.** `IsDNP()` was false for all 39.

**Fixed:** set `U5` (MAX-M10S GPS) and `U6` (MS5611 baro) to DNP, which is **exactly what the
locked split states** (*"1 variant, platform populated on all 10 | no baro; GPS as DNP rows +
4 loose"*). Script: `tracker/hardware/set_dnp_rows.py`. Verified: `U5 DNP`, `U6 DNP`.

## 4. CRITICAL — the first CPL silently dropped `U1`, the MCU

My first CPL export used `--exclude-fp-th` (exclude through-hole footprints). **`U1`
(ESP32-S3-WROOM-1U) has `SMD+TH` pads** — the module's thermal/heatsink vias are through-hole
— so **the flag dropped the microcontroller from the placement file.**

**A CPL without the MCU would ship a board with no processor.** That is the single worst
failure mode in this package, and it came from a **plausible-looking flag**, not from a typo.

**Fixed:** re-exported with **`--exclude-dnp`** (the correct flag — it honours the DNP rows
rather than blanket-dropping anything through-hole):

| | placements | U1 present |
|---|---:|---|
| first CPL (`--exclude-fp-th`) | 35 | **NO** |
| corrected (`--exclude-dnp`) | **36** | **YES** |
| U5/U6 (DNP) correctly excluded | | **YES** |

## 5. CRITICAL — the BOM carries no LCSC part numbers

Exported from the schematic (`kicad-cli sch export bom`), the BOM has exactly three columns:

```
"Reference","Value","Footprint"
"ANT1","U.FL_433_TX","Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"
```

**Zero LCSC mentions.** JLCPCB's PCBA service **requires** an `LCSC Part #` column to place
parts — **without it the assembly order cannot be placed for the SMT parts at all.**

**So the assembly half of this order is not orderable yet**, and the BOM must be built from
the LCSC numbers that live in the **docs** (`PART-DECISIONS.md`, the qty-5 ranking, SS24 →
`C50645`, WROOM-1U → `C2980300`, and the newly-selected `U_CUT`/`U_HUB_CVT` parts) rather
than from the schematic, which carries none.

## 6. Also found

- **Schematic annotation errors** — `kicad-cli` warned: *"schematic has annotation errors,
  please use the schematic editor to fix them."* A real signal; the schematic is not clean.
- **Two MORE `TODO(unverified)` parts:** `R_NTC1` and `TH_NTC1` (the NTC sense chain). So the
  set of `TODO(unverified)` parts is **not five** — measured on the shipped board it includes
  these two as well. **These are on the populated list**, i.e. they would be assembled.
- **Supercap DNP is ambiguous.** `C_CAP1`/`C_CAP2` (3.3 F) are through-hole and currently
  **populated** in the CPL. The accepted-risks list says *"Supercap DNP: no buffer for TX
  bursts at dawn/dusk → cold-start untested"*, which implies they should **not** be. **I did
  NOT set that flag** — it changes stored energy, not just the CPL, so it is a **functional
  decision for the operator**, not a packaging cleanup.

## 7. Honest state of the order package

| checklist row | claimed | measured |
|---|---|---|
| A1 file fixed to 0.8 | ✅ implied | **0.6 — false** (now fixed to 0.8) |
| C1 gerbers | ✅ | **did not exist** (now exported) |
| C2 drill | ✅ | **did not exist** (now exported, 189 PTH holes) |
| C3 DNP rows | ✅ verified | **no DNP flags existed** (now set U5/U6) |
| C4 CPL | ✅ | **did not exist**, and my first attempt dropped U1 |
| C5 loose MAX-M10S | ✅ separate CSV | **not produced** |
| C6 upload ZIP | ✅ | **did not exist** (now built, sha256 recorded) |

**Six of six C-rows were false.** The order package was **substantially not ready** while the
checklist said it was.

## 8. What remains before an order can be placed

1. **BOM with LCSC Part # column** — assembles from docs, not the schematic. **Blocking.**
2. **Supercap DNP decision** — functional, operator.
3. **`R_NTC1` / `TH_NTC1` part selection** — new `TODO(unverified)` items on the populated list.
4. **Loose MAX-M10S line** (4×, separate CSV).
5. **Re-price at 0.8 mm 4-layer** — all totals are lower bounds.
6. **JLC per-placement assembly fee** — still unmeasured.
7. **Schematic annotation errors** — fix before trusting any schematic-derived export.

## 9. Reproduce

```
cd tracker/hardware
~/venvs/kicad/bin/python list_bom_parts.py      # 39 prints, DNP column
~/venvs/kicad/bin/python set_dnp_rows.py        # sets U5/U6 per the locked split
kicad-cli pcb export pos --output … --exclude-dnp …   # NOT --exclude-fp-th
kicad-cli sch export bom --output … schematics/flight_board/v9_flight.kicad_sch
#   -> 3 columns, 0 LCSC mentions
```
