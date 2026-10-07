# REPORT — v9 balloon flight board: system diagram + reproducible BOM

Branch: `docs/v9-system-diagram` (worktree `/home/c03rad0r/worktrees/bf-sysdiag`,
based on `github/main` tip `e4d0569`).
Commit: **`8eee7a1e9a85bb8786f929c64364736b9d6c39ec`** (short `8eee7a1`).
Design/documentation work only: **nothing ordered, no connectivity changed.**

---

## 1. What was delivered

| Artefact | What it is |
|---|---|
| `docs/v9-system-diagram.svg` | System-level explanatory diagram, 1900 × 1472, dark theme, **self-contained** (inline styles only, system fonts, no external CSS/JS/fonts). Functional blocks and the connections between them — **not** a schematic capture and **not** a PCB layout. |
| `docs/v9-system-diagram.png` | Raster render of the same file for messaging preview: **1900 × 1472, 614 904 bytes**. |
| `docs/v9-BOM.md` | Bill of materials, **generated from the netlist by script** (never hand-typed). 46 rows + "Parts and their key ratings" + per-reference net audit table. |
| `scripts/gen_v9_bom.py` | The BOM generator (reproducible; `--check` mode). |
| `scripts/render_v9_diagram_png.sh` | PNG renderer with the documented fallback chain. |
| `scripts/check_v9_diagram_layout.py` | Layout gate: measures the SVG in a real browser and fails on text overflow / box collision. |
| `PROGRESS.md` | Working log (gitignored in this repo; tracked on this branch with `git add -f`). |

### Diagram contents (what the operator sees at a glance)

* **POWER** — harvest (4 wings × 3 LARGE cells = 12 cells, one series string, 7.2 W peak,
  9.58 V cold Voc) → 4 wing sockets → `D_BP1..D_BP4` bypass (SS24, 2 A / 40 V,
  populated, hub-side) → `D1` BAT54 → **supercap bank** (`C_CAP1/C_CAP2`, 1.65 F @ ≤5.4 V;
  doubled bank 3.3 F, **33.264 J usable**, **NO BATTERY**) → `VSCAP`.
  The **hub array is drawn as an INDEPENDENT string** (`PVA1`/`PVA2` + `D_HUB1/D_HUB2`
  → `U_HUB_CVT`, TPS63060-class buck-boost) with its own converter input (ADR-051).
  Then `U7` TPS7A0233 LDO → `+3V3`, and `VSCAP → J_VCC pin 1` = the **F33 PRE-REGULATOR
  FEED**, with the reason drawn on the diagram: **the LDO cannot feed the F33**
  (1100 mA ÷ 200 mA = **5.59× over**) and the PA cannot run off 3V3.
* **RADIO** — three chips, three bands, four antennas:
  `U2 LoRa2021F33-2G4` = **433 MHz DOWNLINK TX**, internal **0.5 ppm TCXO**,
  +33 dBm / 2 W at 5 V, 1100 mA burst, pre-regulator feed;
  `U3 LoRa2021` (bare) = **2.4 GHz UPLINK RX**, crystal only, no TCXO;
  `U4 SX1280` = **2.4 GHz RANGING only** — explicitly labelled *not a link carrier* and
  *not the timing authority* (ADR-060 §1.4).
  `ANT1..ANT4` drawn as U.FL jacks with **wire dipoles on the HUB**, so a wing cut costs
  no comms (ADR-009). Band/direction arrows for **DOWNLINK 433 (out)**, **UPLINK 2.4 (in)**,
  **RANGING 2.4 (two-way)**.
* **SENSING** — `U5 MAX-M10S` GNSS with **1PPS on TIMEPULSE → GPIO21** drawn as the
  zero-gram / zero-watt clock discipline (ADR-056 D3); `U6 MS5611-01BA` barometer on I2C
  with the **MS5611 vs MS5607 discrepancy flagged in place**.
* **COMPUTE & STORAGE** — `U1 ESP32-S3-WROOM-1U-N8R8`: **8 MB flash + 8 MB PSRAM on-module**,
  **no external storage part fitted** (ADR-061), flash = persistent log, PSRAM = staging only,
  plus the full bus map out of U1.
* **CUT / SHED** — `U_CUT1..U_CUT4` latched cut drivers, **each fed from `VSCAP`
  (post-BAT54 / pre-LDO)** so a cut fires with the converter dead, `J_W1..J_W4` sockets,
  nichrome elements, and cut continuity **sensed by reusing the `RF_FEED` line**
  (net `/CUT_SENSE_W<n>` = `J_W<n>.3` + `U_CUT<n>.3`, from the netlist).
  Variant B (hub only, no wings, no cut) is stated.
* **KEY NUMBERS** — 7.2 W peak · 33.264 J usable · 0.388 W average · 100 µW night anchor ·
  33 dBm / 1100 mA PA + pre-regulator need · 0.5 ppm TCXO (F33 only) · −60 °C Voc ≈ 9.58 V ·
  6.15 W max radio draw · 3.1 µW rail-monitor bias · 46 components / 47 nets.
* **DNP is visually distinct** — dashed outline + DNP label (legend explains it), used for
  `R_NTC1` / `TH_NTC1` and for every not-wired / `TODO(unverified)` item.

---

## 2. Reproducing the deliverables

### BOM (script-generated, never hand-typed)

```sh
cd <worktree root>
python3 scripts/gen_v9_bom.py            # writes docs/v9-BOM.md
python3 scripts/gen_v9_bom.py --check    # exit 1 if docs/v9-BOM.md is stale
```

If the schematic moves first, regenerate the netlist:

```sh
python3 tracker/hardware/schematics/flight_board/build_flight_sch.py v9
kicad-cli sch export netlist \
  --output tracker/hardware/schematics/flight_board/v9_flight.net \
  tracker/hardware/schematics/flight_board/v9_flight.kicad_sch
```

`gen_v9_bom.py` reads Reference / Value / Footprint / library id / DNP / net membership
straight out of `v9_flight.net`. The only authored columns are **FUNCTION** (prose) and
**Parts and their key ratings**. It **exits non-zero** if the netlist ever grows a
reference that has no FUNCTION entry, so the table cannot silently drift from the schematic.
Also verified: `build_flight_sch.py v9` is deterministic — re-running it left
`v9_flight.kicad_sch` byte-identical (`git status` clean after the regeneration).

### SVG

Hand-authored. Validate the XML:

```sh
python3 -c 'import xml.etree.ElementTree as E; E.parse("docs/v9-system-diagram.svg")'
```

Verify the layout (this is how the diagram was checked — the worker has no working
vision provider, so "look at the picture" was replaced by measurement):

```sh
python3 scripts/check_v9_diagram_layout.py
# == TEXT OVERFLOW: 0
# == RECT OVERLAP (non-nested): 0
# == TEXT-vs-TEXT OVERLAP: 0
# PASS: 0 defect(s) in .../docs/v9-system-diagram.svg
```

The gate renders the SVG in headless Chromium only to measure each `<text>` element's real
`getBBox()` against the rectangle it sits in. The first layout attempt failed 22 of these
checks; the grid was rebuilt (wider canvas, 3-column power chain) until it passed.

### PNG

```sh
scripts/render_v9_diagram_png.sh
# renderer: /home/c03rad0r/.local/bin/chromium (fallback - the three preferred renderers are not installed)
# wrote docs/v9-system-diagram.png (614904 bytes)
# docs/v9-system-diagram.png PNG 1900x1472
```

**Renderer availability — stated explicitly, as required.** The three preferred renderers
were tried in the specified order and **none of them is installed on this host**:

| Preferred renderer | Result |
|---|---|
| `rsvg-convert` | **ABSENT** (not on PATH) |
| `inkscape --export-type=png` | **ABSENT** (not on PATH) |
| `python3 -c 'import cairosvg'` | **ABSENT** (`ModuleNotFoundError`) |

`magick`/`convert` **is** installed but its SVG delegate also points at the missing
`rsvg-convert`, and forcing its internal MSVG renderer fails outright:
`non-conforming drawing primitive definition 'stroke-dasharray'`.
So the PNG was produced with **headless Chromium** (the same engine the layout gate uses).
This is a genuine raster of the same `docs/v9-system-diagram.svg` — **no PNG was
fabricated, and none was generated from a different source.**

PNG verified non-trivial:

* size **614 904 bytes** (≫ 10 KB)
* dimensions **1900 × 1472**, 8-bit sRGB
* corners sample exactly the diagram background `srgb(13,17,23)` = `#0d1117`
* ~4.9 % bright pixels (text/lines), **41 660 unique colours** — real rendered content,
  not a blank or near-blank image.

---

## 3. What was measured from the schematic (not assumed)

From `v9_flight.net` / `v9_flight.kicad_sch`, regenerated with `build_flight_sch.py v9`:

* **46 components**, **47 nets**, 225 symbol pins, 122 net labels, 63 power pins,
  12 no-connects, 32 `TODO(unverified)` notes. Title block: *Balloon v9 Tri-Band Flight
  Board*, rev *v9-design-intent*.
* **DNP parts = exactly two**: `R_NTC1`, `TH_NTC1`.
* **ERC** (`v9_flight-erc.rpt`, 2026-10-07T16:35:38): **23 errors, 0 warnings**, all
  `pin_not_connected` (deliberate provision / unverified pins: `U3` pads 16/17,
  `U4` VDD_IN/VDD_IO/RFIO, `U6` PS/SDO/CSB, `U5` ~SAFEBOOT/VIO_SEL, `U1` EN/IO11/IO12/
  USB_D±/IO47/IO48 …). No short or drive conflict.
* `/VSCAP` = {`C_CAP1.1`, `D1.1`, `J_VCC.1`, `R_BAL1.1`, `R_DIV1.1`, `U7.1`, `U7.3`,
  `U_CUT1..4.1`} — confirms the cut drivers ride the **post-BAT54 / pre-LDO** node.
* `/CUT_SENSE_W<n>` = {`J_W<n>.3`, `U_CUT<n>.3`} — confirms the cut-sense reuse of the
  `RF_FEED` line.
* Antenna nets: `/ANT1_433_TX` = `ANT1.1`+`U2.9`; `/ANT2_2G4_TXRX` = `ANT2.1`+`U2.10`;
  `/ANT3_2G4_RX` = `ANT3.1`+`U3.10`; `/ANT4_GNSS_L1` = `ANT4.1`+`U5.11`.
* `/GNSS_PPS` = `U1.23`+`U5.4` (1PPS into the S3).

---

## 4. Discrepancies found (flagged on the diagram and in the BOM, not resolved)

1. **Barometer.** Schematic/netlist say `U6 = MS5611-01BA`; `docs/adr/108-f33-sx1280-pin-plan.md`
   names **MS5607-02BA03**. The diagram and BOM draw **MS5611-01BA** (what the schematic says)
   and flag the discrepancy in place. Operator to reconcile.
2. **Bypass diodes — part family, rating and DNP state.** `docs/adr/048-v9-hub-wing-interfaces.md`
   §2.3 says "BAT54 family, SOD-323, **DNP for the first prototype**". `docs/adr/049-wing-architecture.md`
   §"Consequences" 1 re-rates the requirement to **≥2 A / 40 V (SS24 or PMEG4020ER class)** because
   BAT54's 200 mA / 30 V is undersized against the 1.2 A LARGE-cell string. The schematic follows
   ADR-049: `D_BP1..D_BP4` are **SS24 in `Diode_SMD:D_SMA`, populated**, with **no** DNP flag in the
   netlist. ADR-048's text is stale against its own re-rating.
3. **Wing pin 3 `RF_FEED`.** ADR-048 §2.3 states pin 3 "carries NO net on v9"; the netlist wires it to
   `CUT_SENSE_W<n>`. The design intent (cut continuity sensed on that line) is what the schematic
   implements. The ERC consequently reports the four `J_W<n>` pin-3 pads — read the ERC count as an
   expected baseline, not a defect.
4. **`U_HUB_CVT` output rail.** The netlist gives `HUB_CONVERTER` only `HUB_PV_P` (pin 1),
   `GND` (pin 2) and `HUB_PV_N` (pin 3). **No output net is assigned** — which rail the hub
   converter feeds, and whether it parallels the wing string into `VSCAP` or drives `+3V3`,
   is **`TODO(unverified)`**; it is not in the netlist. Drawn as a dashed box with a `?` arrow.
5. **Other `TODO(unverified)` values carried on the diagram rather than invented:**
   `D_CLAMP` TVS set point, `U4` VDD/RFIO terminations, the `U_CUT1..4` driver part number,
   `R_NTC1`/`TH_NTC1` values (R25/beta).
6. **ADR-059 vs ADR-061 numbering.** ADR-059 states its provision pads to `VTCXO`/`NTC_SENSE`,
   and both ADRs carry in-file renumber records (058→059 and 059→061). The BOM cites ADR-059
   for the NTC DNP reason as the file currently reads; the numbering history is ADR-internal
   and not restated on the diagram.

---

## 5. Honesty note on sourcing

Every number on the diagram and in the BOM ratings table is traceable to `v9_flight.net` or
to a named in-repo file (ADR or analysis doc), and the BOM ratings table cites the file and
line for each row. **No part number, rating, datasheet figure or citation was invented.**
Anything unsourceable is marked `TODO(unverified)` and stays marked on the drawing.
