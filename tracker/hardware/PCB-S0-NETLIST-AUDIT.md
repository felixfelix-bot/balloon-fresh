# Netlist audit of record — flight board, closed under PCB-S0b

**Card:** kanban `t_a1f8e389` (PCB-S0b) · **Parent:** `t_7c65638f` (S0 placement freeze)
**Date:** 2026-09-17 · **Branch:** `pr/pcb-s0b-netlist`
**Supersedes:** the first revision of this file (27 netless pads = 11 GAP + 16 intentional,
produced in parallel with `PLACEMENT-S0-FREEZE.md` §3; that split is preserved below as the
"before" column so the closure can be checked row by row).

## 0. Verdict

**Zero rows are "unknown".** The 27 netless pads of the frozen placement are now
**3 FIXED + 23 INTENTIONAL (each with a datasheet/vendor citation) + 1 BLOCKED-ON-OPERATOR**,
plus one non-pad finding (U2 lands/part mismatch) that is also BLOCKED-ON-OPERATOR.
Row counts are machine-checked against the board census, not counted by hand (§4).

## 1. Artefacts and hashes

| artefact | role | sha256 |
|---|---|---|
| `output/v_c3_flight_4layer_placed.kicad_pcb` | S0 placement freeze — **byte-identical, untouched** (still the S1/S2 comparability anchor) | `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6` |
| `output/v_c3_flight_4layer_placed_netfix.kicad_pcb` | **netlist of record after S0b** (same 20 footprints, same positions/rotations, 0 tracks, 0 vias, 3 zones) | `aa76fbbb85ce89ffd6b5e346ca7b5f53575035ba611ec137f3c086ac4dc0809a` |
| `output/v_c3_flight_4layer_placed_netfix.kicad_dru` | frozen JLCPCB rule set, byte-identical to the S1 file | `5acd7dced4a0d8b3edb8b3b977cc2a110a0a97fba0c6d867ce698b243835ca59` |
| `output/v_c3_flight_4layer_placed_netfix.kicad_pro` | project/netclass carrier, byte-identical to the S0 file | `a29acec391bae6b1d53f69be95e0fcce6af5bae7c6d06a4ba0706f7a54920238` |
| `netlist_fix_s0b.py` | the tool that derives the netfix board from the frozen board and re-verifies the invariants | see `output/s0b/netlist_fix_report.json` |
| `output/s0b/gate25_netfix.json` | gate25 output for the board above | — |
| `output/s0b/netlist_fix_report.json` | before/after census (pad nets, positions, copper, net table) | — |

**No re-freeze was required.** A re-freeze is only triggered when a part is added or moved.
S0b changes three `(pad … (net …))` assignments to nets that **already exist** on the board, so
footprint count (20), position, rotation, footprint identity, pad position/size, the 22-net table,
track count (0), via count (0) and zone count (3) are all provably unchanged
(`netlist_fix_report.json`: `placement_identical`, `copper_unchanged`, `net_table_unchanged: 22`).
The frozen artefact is therefore left byte-identical and a new artefact carries the netlist.

## 2. Item 1 — U4.3 (regulator EN) floating → FIXED, direct tie to the input rail

**Part fitted:** `U4` = **TPS7A02**, package DBV (SOT-23-5), 3.3 V / 200 mA nanopower LDO
(`bom/BOM.md` row 12; footprint `Package_TO_SOT_SMD:SOT-23-5`; TI datasheet **SBVS277C**).

**Path taken: 2 of 3 — the pin is assigned to the input-rail net; no new footprint, no resistor.**

| question the card asks | answer |
|---|---|
| does the board already have a pull-up style for EN/CE pins? | **Yes — a direct rail tie, no discrete resistor.** `gen_pcb.py` LDO table `{1:VCAP, 2:GND, 3:VCAP, 5:3V3}` (pin 3 = EN tied to the IN rail), `full_pipeline.py` pad 3 `# EN (tie to IN)`, `schematics/v_c3_rp2040/build_sch.py` `add_label("VBAT", …)  # EN pulled to VBAT (always-on)`. The consistent style on this board is a plain copper tie to the regulator's own input net. |
| can the pin just be assigned to the input-rail net? | **Yes.** U4.1 = IN = net `VCAP` (the supercap rail, this board's input rail — solar → BAT54 → 1F supercap → `VCAP` → TPS7A02 IN). Tying EN to IN is the datasheet's own always-on configuration. |
| discrete resistor required? | **No.** No part added → no re-placer, no re-freeze. |

**EN threshold, from the datasheet (TI SBVS277C):**
* `Table 5-1, p.3` — `EN` is an **input**, DBV pin 3: *"Driving this pin to logic high enables the
  device; driving this pin to logic low or floating this pin disables the device. This pin features
  an internal pulldown resistor, which is disconnected when EN is driven high externally…"*
  → a floating EN is an **internal pulldown to disabled**: the 3V3 rail would never come up. This is
  the electrical reason the audit called it a GAP.
* `Absolute Maximum Ratings, p.4` — V_EN = **–0.3 … 6.5 V**, i.e. the rail tie at 3.3–5.5 V is
  in spec; the electrical characteristics are specified at **V_EN = V_IN** (`§6.5`), which is
  exactly the tie implemented.

**Change:** `U4.3 (EN)`: no net → **`VCAP`** (= IN, pin 1).

## 3. Item 2 — the 11 netless MAX-M10S (U3) pads, classified from the datasheet

**Authority:** u-blox **UBX-20035208** (MAX-M10S data sheet, R08). Per-pad citations below are to
**Table 10 "MAX-M10S pin assignment", p.9** unless stated otherwise. Extracted text of the vendor
PDF is attached to the card (`maxm10s.txt`); the PDF is also in `~/worktrees/pcb-refs/`.

**Footprint question — the board exposes the FULL module, not a subset:**
`U3` carries the `ublox_MAX` (KiCad `RF_GPS:u-blox_MAX-M10` family) footprint with **18 pads,
numbered 1–18, all present** — so every pin of Table 10 exists on the board and every one is
classified. Before S0b: 4 pads netted to `+3V3` (7 V_IO, 8 VCC) / 3 to `GND` (1, 10, 12) /
2 to the UART (`2` TXD→`GPS_RX`, `3` RXD→`GPS_TX`) / **11 netless**. After S0b: 9 netless, all declared.

| pad | Table 10 name | direction | verdict | evidence / citation |
|---|---|---|---|---|
| 4 | TIMEPULSE | O | **INTENTIONAL** — declared no-connect, function named | UBX-20035208 Table 10, p.9: "Time pulse signal (shared with SAFEBOOT_N pin)¹⁵". Output only; no 1PPS consumer on this board. |
| 5 | EXTINT | I | **INTENTIONAL** — declared no-connect | Table 10, p.9: "External interrupt. **Leave open if not used.**" |
| 6 | V_BCKP | I (supply) | **FIXED → `+3V3`** | Table 10, p.9 "Backup voltage supply"; electrical spec p.11: **V_BCKP 1.65 … 3.6 V**. `+3V3` = 3.3 V is in range → hot-start backup live. (No supercap intended on this rail: the board's only 1 F cell is the `VCAP` supercap on the LDO input, and it is a different net.) |
| 9 | RESET_N | I | **FIXED → `+3V3`** | Table 10, p.9: "System reset (active low). Has to be low for at least 1 ms to trigger a reset." Table 11 "Pin state", **p.10**: RESET_N = "Input pull-up" in every mode, so the module has an internal pull-up and a floating pin is not fatal — but a hard tie makes power-up deterministic and costs nothing. **Tied high = never held in reset.** |
| 11 | RF_IN | I (RF) | **BLOCKED-ON-OPERATOR** — genuine hardware gap, see §3.1 | Table 10, p.9: "GNSS signal input". Nothing on this board connects to it. |
| 13 | LNA_EN | O | **INTENTIONAL** — declared no-connect | Table 10, p.9: "On/off external LNA or active antenna". No external LNA and no active antenna is fitted, so the output is unused. |
| 14 | VCC_RF | O (RF supply) | **INTENTIONAL** — declared no-connect | Table 10, p.9: "Output voltage RF section" (p.11: VCC_RF = VCC − 0.1 V, I ≤ 50 mA). It exists to power an **active** antenna; none fitted. Revisit if an active antenna is added. |
| 15 | VIO_SEL | I | **INTENTIONAL — must be LEFT OPEN** (this is not a gap) | Table 10, p.9: "Voltage selector for V_IO supply. **Connect to GND for 1.8 V supply, or leave open for 3.3 V supply.**" The board runs 3.3 V I/O: U3.7 V_IO and the ESP32-C3 I/O are on `+3V3`. Corroborated by the electrical spec, **p.11**: VIO_SEL = open → V_IO 2.7 / 3.3 / VCC (max 3.6) V, versus VIO_SEL = GND → 1.76 / 1.8 / max 1.98 V. Tying it to GND would move the module's I/O rail to 1.8 V and *underrange* the 3.3 V logic. **Do not tie.** |
| 16 | SDA | I/O | **INTENTIONAL** — declared no-connect | Table 10, p.9: "I2C data. Leave open if not used". The module is used over UART (pads 2/3 carry `GPS_RX`/`GPS_TX`). |
| 17 | SCL | I | **INTENTIONAL** — declared no-connect | Table 10, p.9: "I2C clock. Leave open if not used". As pad 16. |
| 18 | SAFEBOOT_N | I | **INTENTIONAL** — declared no-connect | Table 10, p.9: "Safeboot mode (active low). **Leave open if not used.**¹⁵". Footnote 15, p.9: *"The receiver enters safeboot mode if this pin is low at start up. The SAFEBOOT_N pin is internally connected to TIMEPULSE pin through a 1 kΩ series resistor."* Left open = not in safeboot; Table 11, p.10 shows the internal "Input pull-up" state in continuous mode, so an open pin floats high. **Do not tie it to GND, and note the 1 kΩ internal link to TIMEPULSE (pad 4) — pad 4 must therefore also stay open** (it is). |

### 3.1 U3.11 RF_IN — the one real hardware gap (needs an operator decision)

The board has **no GNSS antenna feed of any kind**: the only RF part on it is `ANT1` (U.FL,
2.4 GHz, net `RF_OUT`, driven by U2), and no net touches U3.11. Per the card this row is **not**
closed by declaration. Costed options:

| option | change | rough cost / consequence |
|---|---|---|
| **A. U.FL + matching network** (passive or active antenna) | 1 × U.FL + 1–2 passives (DC block / matching) + a 50 Ω feed; needs a keep-out and a re-placement → **forces a re-freeze** | ~1–2 EUR parts; board area on an already-tight 20-part placement; enables any external GNSS antenna |
| **B. Ceramic patch antenna on-board** | 1 × 25 × 25 mm patch + feed + ground keep-out → **forces a re-freeze** and a mechanical/enclosure change | ~1–3 EUR; needs a clear sky-facing ground plane; biggest mechanical impact |
| **C. Accept no GNSS** | none | $0; the MAX-M10S is fitted but deaf; U3's rails/UART stay declared as-is. Firmware must not block on a GPS fix. |
| **D. Swap to a module with an integral antenna** | new part + new footprint → **forces a re-freeze** | e.g. MAX-M10S with an integrated patch (u-blox MAX-M10S eval variant): removes the feed problem but changes the land pattern and the BOM. |

**Recommendation: A** (U.FL + matching network): it is the smallest delta that turns the already-fitted
receiver into a working one, it reuses the design language of `ANT1`, and it keeps the antenna choice
(passive vs active) reversible. **It requires a re-freeze** (new part ⇒ new placement hash, new gate25,
new `placement_guard` run). This card does **not** invent the feed.

## 4. U2 (RFM9XW lands) and U4.4/5 — arbitration of the two former contradictions

### 4.1 U4 pad 4 vs 5: the BOARD was right, two repo artefacts were wrong → both corrected

**Authority:** TI **SBVS277C** Figure 5-2 + Table 5-1, **p.3** (DBV, 5-pin SOT-23):
`1 = IN`, `2 = GND`, `3 = EN`, **`4 = NC`**, **`5 = OUT`**.
("NC — No connect pin. This pin is not internally connected. **Connect to ground or leave floating.**")

* The flight board carries `+3V3` on **pad 5** and nothing on **pad 4** → **the board matches TI.**
  `gen_pcb.py` (`{5:"3V3"}`) and the `S0` audit agree with the board.
* **`balloon_symbols.kicad_sym::TPS7A0233PDBVR` said pin 4 = `OUT`, pin 5 = `NC`** — wrong pin-to-function
  order. Corrected to **pin 5 = OUT (power_out), pin 4 = NC (no_connect)** in both in-repo copies
  (`tracker/hardware/schematics/v_c3_rp2040/balloon_symbols.kicad_sym` and
  `tracker/hardware/output/pcb-handoff/balloon_symbols.kicad_sym`); the schematic builder's wiring for
  the RP2040 variant was moved with it (`build_sch.py`: label `3V3` on pin **5**, `nc()` on pin **4**) so
  the library and the generator cannot disagree again.
* **`full_pipeline.py::make_ldo_pads()` said `(IN, GND, EN, OUT, NC)`** — same error. Corrected to
  `1 IN (VCAP) / 2 GND / 3 EN (tied to IN) / 4 NC / 5 OUT (3V3)`, with the datasheet citation in the
  docstring.
* **Result on the flight board: `U4.4` = INTENTIONAL no-connect** (TI allows floating; grounding it is
  equally valid but adds nothing at a no-internal-connection pad), and `U4.5 = +3V3 (OUT)` as built.
  No board change on either pad.

### 4.2 U2 pads 7 / 11 / 15 / 16: the "ground tab" reading is REFUTED → all four are declared no-connect

**Authority:** HOPERF **RFM95/96/97/98(W) data sheet §1.4 "Pin Description", p.11** — the vendor drawing
the board's land pattern is taken from (`HOPERF_RFM9XW_SMD`; the KiCad footprint's own `descr` cites
`hoperf.com/…/5bfcbea20e9ef.pdf`, i.e. exactly this document). 16-pad pin table, verbatim:

```
 1 GND     2 MISO   3 MOSI   4 SCK    5 NSS    6 RESET
 7 DIO5    8 GND    9 ANT   10 GND   11 DIO3  12 DIO4
13 3.3V   14 DIO0  15 DIO1  16 DIO2
```

The flight board's U2 nets are a strict subset of that table and match it pin for pin:
`2 MISO · 3 MOSI · 4 SCK · 5 NSS · 6 RESET · 9 ANT (RF_OUT) · 13 3.3V (+3V3) · 14 DIO0 (LR_DIO0) ·
1/8/10 GND`, with **pad 12 (DIO4) repurposed as `LR_BUSY`**.

| pad | vendor function | verdict | evidence |
|---|---|---|---|
| 7 | DIO5 | **INTENTIONAL** — declared no-connect | HOPERF §1.4 p.11: "Digital I/O, software configured". Not a ground tab. |
| 11 | DIO3 | **INTENTIONAL** — declared no-connect | same; **this refutes the parallel audit's "probable GROUND tab" reading** — grounding a DIO line is the actual defect risk here, and the S0 audit's MEDIUM-confidence GAP is closed as intentional. |
| 15 | DIO1 | **INTENTIONAL** — declared no-connect | same. |
| 16 | DIO2 | **INTENTIONAL** — declared no-connect | same; refutes the second "probable GROUND tab" reading. |

Pad 12 is netted (`LR_BUSY`) and is therefore not part of this list; note it is the vendor's **DIO4**,
so the radio's BUSY line rides a configurable DIO — acceptable for an SPI-driven LR2021-class module
whose BUSY is a status output, but it is the kind of remap that must be confirmed against the fitted
module's driver (recorded as an open finding, §5).

### 4.3 Lands/part mismatch on U2 — BLOCKED-ON-OPERATOR (non-pad finding)

`U2`'s **Value is `LR2021F33`** and the BOM lists **"NiceRF LoRa2021"**, but the land pattern on the
board is the **16-pad HOPERF RFM9XW** (`output/pcb-handoff/ROUTING-HANDOVER.md` line 21: "U2 = HOPERF RFM9XW / LR2021 radio
(66,14) — 16 pads"). The repo's own module tables describe two *different*, 18-pin packages:
`footprints/nicerf-lora2021.json` (19.81 × 14.98 mm, 18 pins, pin1 VCC … pin9 ANT) and
`footprints/nicerf-lora2021f33-2g4.json` (39 × 21 mm, 18 pins, 2.0 mm pitch, pin1 VCC, pin5 CE,
pin9 ANT, pins 12–18 SPI/RST/IRQ). **Neither 18-pin part can be soldered into a 16-pad land pattern**,
and their pin numbering does not match the board's nets at all. So one of the following must be true
and only the operator can say which:

1. the **fitted module is a 16-pad RFM9xW-class part** and the `Value`/BOM text (`LR2021F33`,
   `NiceRF LoRa2021`) is a **documentation error** → fix the Value field and the BOM line; no board change; or
2. the **intended module is the 18-pin NiceRF part** → the **land pattern is wrong** and the board needs
   a new footprint, a new placement and therefore a **re-freeze**.

**Recommendation:** option 1 if the flight radio really is an RFM9xW/LR2021 hybrid (the nets and the
supports `mesh-stack/meshcore-lr2021` driver work both assume an SPI module on these pads), otherwise
option 2. **No netlist action is taken here** — pads 7/11/15/16 above are classified against the land
pattern that is actually on the board, which is the only thing that can be classified today.

## 5. Row counts (machine-checked, not hand-counted)

Census of `output/v_c3_flight_4layer_placed_netfix.kicad_pcb` (`gate25_check.py --json`,
`output/s0b/netlist_fix_report.json`):

| class | rows | detail |
|---|---|---|
| **FIXED** | **3** | `U4.3` EN → `VCAP`; `U3.6` V_BCKP → `+3V3`; `U3.9` RESET_N → `+3V3` |
| **INTENTIONAL** (netless, cited) | **23** | `U1` × 9 unnamed library mechanical pads · `J1.6` spare header pin · `U4.4` NC (TI SBVS277C) · `U2.7/11/15/16` unused DIO5/DIO3/DIO1/DIO2 (HOPERF §1.4) · `U3.4/5/13/14/15/16/17/18` unused/optional/defective-if-tied pins (UBX-20035208 Table 10 + Table 11) |
| **BLOCKED-ON-OPERATOR** | **1 pad + 1 finding** | `U3.11` RF_IN (no GNSS antenna feed, options costed §3.1) · `U2` lands/part mismatch (§4.3) |
| **unknown** | **0** | — |
| netless pads before → after | 27 → **24** | 24 = 23 intentional + RF_IN; `unconnected` in DRC 64 → 67 because the three newly netted pads have no copper yet (this lap carries 0 tracks by definition — routing is S1/S3) |

## 6. Evidence contract

| item | value |
|---|---|
| board file after this card | `tracker/hardware/output/v_c3_flight_4layer_placed_netfix.kicad_pcb` |
| sha256 | `aa76fbbb85ce89ffd6b5e346ca7b5f53575035ba611ec137f3c086ac4dc0809a` |
| frozen placement (unchanged) | `output/v_c3_flight_4layer_placed.kicad_pcb` = `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6` |
| gate25 (`output/s0b/gate25_netfix.json`) | `footprints 20 · pads 125 · segments 0 · vias 0 · zones 3 · pads_with_no_net 24 · pad_overlap_pairs_0.2mm 0 · exact_pad_overlap_pairs_0.2mm 0 · courtyards_overlap 0 · DRC violations_total 4 (all silk_edge_clearance) · shorting_items 0 · clearance 0 · unconnected 67 · placement_gate PASS` |
| `placement_guard.py --gate25` exit code | **0** (`gate25: fp=20 pad_overlaps=0 segments=0 -> PASS`, `violations: []`) |
| tool | `netlist_fix_s0b.py` (reproduces the output sha256 byte-for-byte) |
| re-freeze | **not required** — net ties only, no part added or moved |

## 7. Open findings carried forward

1. `U3.11` RF_IN antenna feed — operator decision (§3.1, recommendation A), **forces a re-freeze** when taken.
2. `U2` lands vs Value/BOM mismatch — operator decision (§4.3), may force a re-freeze.
3. `U2.12` is vendor DIO4 used as `LR_BUSY` — confirm against the fitted module's driver.
4. Any routed artefact derived from the **pre-S0b** netlist (e.g. `output/v8_krt_routed.kicad_pcb`, S1)
   still carries a floating `U4.3` EN ⇒ **that board would never enable 3V3**. Routing must be re-run
   from the S0b netlist of record before fab (`output/v_c3_flight_4layer_placed_netfix.kicad_pcb`).
5. The schematic is still a stub (`schematics/v_c3_flight.kicad_sch`), so the board's nets have no
   schematic provenance (ADR-028). S0b makes the netlist *correct*, not *derived*.
