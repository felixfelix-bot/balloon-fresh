# PCB-S0 — flight-board placement frozen at ZERO pad overlap

**Task:** kanban `t_7c65638f` (worker-balloon) · **Date:** 2026-09-17 ·
**Repo:** `~/repos/balloon-e80bench` (clone of balloon-fresh) ·
**Plan:** `tracker/hardware/PLAN-flight-board-routing.md` §S0

**Frozen artefact:** `tracker/hardware/output/v_c3_flight_4layer_placed.kicad_pcb`
**sha256:** `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6`

---

## 1. GATE S0 — result

| criterion | required | measured | pass |
|---|---|---|---|
| pad-overlap pairs @0.2 mm (pad-box proxy) | 0 | **0** | ✅ |
| exact pad-rectangle overlaps @0.2 mm | — | **0** | ✅ |
| `courtyards_overlap` (kicad-cli DRC) | 0 | **0** | ✅ |
| segments / routes on the board | 0 | **0** (0 vias) | ✅ |
| footprint count | ≥ 10 | **20** | ✅ |
| `placement_guard.py` exit code | 0 | **0** | ✅ |

`gate25_check.py output/v_c3_flight_4layer_placed.kicad_pcb` (committed tool):

```json
{
  "board": "output/v_c3_flight_4layer_placed.kicad_pcb",
  "footprints": 20, "pads": 125, "segments": 0, "vias": 0, "zones": 3,
  "margin_mm": 0.2, "pads_with_no_net": 27,
  "pad_overlap_pairs_0.2mm": 0, "pad_overlap_examples": [],
  "exact_pad_overlap_pairs_0.2mm": 0, "exact_pad_overlap_examples": [],
  "courtyards_overlap": 0,
  "drc": {"violations_total": 4, "by_type": {"silk_edge_clearance": 4},
          "courtyards_overlap": 0, "shorting_items": 0, "clearance": 0,
          "unconnected": 64},
  "placement_gate": "PASS"
}
```

`placement_guard.py --gate25 output/v_c3_flight_4layer_placed.kicad_pcb` → exit 0,
`{"canonical_placement_source": {...}, "violations": [], "gate25": {"ok": true,
"detail": "gate25: fp=20 pad_overlaps=0 segments=0 -> PASS"}}`.

**DRC is the authority, the pad-box proxy is the screen.** The proxy uses one
half-extent (the largest pad) for the whole footprint, so it is CONSERVATIVE and
can overstate a conflict.  On the frozen board both agree: 0 proxy pairs, 0 exact
pad overlaps, 0 courtyard overlaps.  The only DRC items left are 4 ×
`silk_edge_clearance` (silkscreen over the board edge — cosmetic, ignored by
JLCPCB).  `unconnected = 64` is expected and NOT a fault: the placement lap carries
zero copper by definition, so the 22 nets have no connecting tracks yet — S1 owns
routing.

Baseline for comparison (the shipped routed board, sha `874cf608c65a`): the SAME
2 pad-overlap pairs (`U2/C4`, `D1/U1`), `courtyards_overlap = 2`, 18 segments, 48
vias, 3 clearance violations, 20 unconnected.  Those 2 pairs are the ceiling every
past routing attempt hit; they are now 0.

## 2. Method — dedicated tool, no hand-typed coordinates

```
prep_placement_input.py            rip 18 segments + 48 vias, KEEP 3 zone planes,
                                   drop 2 stale fills (input is copper-free)
        ↓
KRT py_placer/place_optimize.py    --max-displacement 3 --max-passes 10
   (v0.22.0, MIT)                  --halo-base 1.0 --halo-weight 6.0
                                   --lock ANT1 J1 J2 SOLAR
        ↓
gate25_check.py + kicad-cli DRC    referee (numbers above)
        ↓
publish_placed_board.py            writes output/v_c3_flight_4layer_placed.kicad_pcb
```

The whole chain is reproducible by one command — `python3
tracker/hardware/publish_placed_board.py` — and reproduced the frozen sha256
`f3cf0143e7de…` byte-for-byte on a rerun.

`--lock ANT1 J1 J2 SOLAR` is the constraint the LLM supplied: those four are
mechanical interfaces (U.FL RF port on the east face; programming header, debug
header and solar input on the south face) and must not drift, no matter what the
wirelength objective wants.  Everything else was free within ±3 mm.

### Laps tried (all KRT, all $0 inference)

| lap (placer args beyond `--max-displacement 3 --max-passes 10`) | locks | airwire mm | crossings | gate S0 | floorplan-intent errors |
|---|---|---|---|---|---|
| **chosen**: `--halo-base 1.0 --halo-weight 6.0 --lock ANT1 J1 J2 SOLAR` | 4 edges | 809.7 | 94 | **PASS** | 3 |
| `--halo-base 1.0 --halo-weight 6.0 --lock ANT1 J1 J2 SOLAR U2` | + radio | 824.5 | 94 | PASS | 2 |
| `--halo-base 1.0 --halo-weight 6.0` (no locks) | none | 788.2 | 90 | PASS | 4 |
| `--clearance 0.2 --halo-weight 4.0` | none | 770.2 | 87 | PASS | 6 |
| `--step 0.25 --halo-weight 4.0` | none | 804.9 | 84 | PASS | 3 (ANT1 5.45 mm off the east edge) |
| plain `--max-displacement 3` (no halo change) | none | 776.5 | 90 | **FAIL** (1 pair: `U1/D1` 0.3 mm) | 3 |

Baseline (untouched placement): airwire 816.4 mm, crossings 125.

Chosen lap rationale: every lock-free lap beats it on airwire, but each of them
MOVES `ANT1` 3 mm inboard (and three of them rotate it 180°), which invalidates
the enclosure's east-face exit — the exact "mechanical fact" failure mode the plan
warns about.  Pinning only the enclosure-facing parts costs ~2 % airwire versus
the best lock-free lap and buys back 25 % of the original crossings (125 → 94)
while keeping the U.FL seat pixel-identical to the drawn board.  Full lap evidence
(lap boards, KRT `JSON_SUMMARY` lines, `placement_score.py` terms,
`check_floorplan.py` grades) is in `output/.placement/s0_lap_matrix.json` and the
workspace `s0/` directory.

**Measured trade-off, not hidden.** `check_floorplan.py` grades every lap with
3–6 decap-distance findings (the derived limit is 2.83 mm): on the chosen lap
`C1` 4.50 mm from `U1`, `C3` 3.55 mm from `U4`, `C4` 4.98 mm from `U2`.  The
lock-free laps are not better in kind — `clr02` still carries 3.50/3.41/2.98 mm on
the same three caps — so this is a property of the board's seed placement (where
those caps start > 5 mm from their ICs and are not measured at all), not of the
lap.  Fixing decoupling proximity is a separate, later placement objective
(`place_fanout_clearance.py` exists in KRT for exactly that); it was NOT bundled
into S0 because S0's gate is legality and the mechanical seats.

## 3. Netlist audit — the 27 pads that carry no net

Board totals: 20 footprints, 125 pads, 22 nets, 27 pads with net 0.  The four-layer
routed board carried the SAME 27 netless pads, so the S0 placement change neither
introduced nor removed one.

**The detailed, pad-by-pad audit of record is
`tracker/hardware/PCB-S0-NETLIST-AUDIT.md`** (produced in parallel, with a pin
function and a confidence per pad; machine-readable copy
`output/v_c3_flight_4layer_placed_netlist_audit.json`).  **PCB-S0b (card `t_a1f8e389`) closed it.**  The table below now carries the settled
verdict per pad: **3 FIXED + 23 INTENTIONAL (cited) + 1 BLOCKED-ON-OPERATOR +
1 non-pad item, 0 "unknown"**.  The pre-S0b split was 11 GAP (4 HIGH / 1 LOW / 6
MEDIUM) + 16 intentional.  The netlist of record is
`output/v_c3_flight_4layer_placed_netfix.kicad_pcb` (sha256 `aa76fbbb85ce…`); the
placement anchor `f3cf0143e7de…` is left byte-identical (net ties only, no part
added or moved, so no re-freeze):

| pads | both audits agree | residual difference / what settles it |
|---|---|---|
| `U1` × 9 unnumbered `0.7×0.7 mm` SMD pads (3×3 grid) | **intentional (mechanical)** — WROOM-02 library footprint has 9 unnamed pads; an unnamed pad cannot be netted | none |
| `J1.6` | **intentional (spare pin)** — pads 1–5 carry GND/+3V3/EN/UART0_TX/UART0_RX | mark no-connect in the schematic so ERC stops reporting it |
| `U4.3` | **FIXED (S0b)** — TPS7A02 DBV pin 3 = EN; TI SBVS277C Table 5-1, p.3 gives EN an internal pulldown, so a floating EN *disables* the regulator and the rail never comes up. Tied to the input rail `VCAP` (= IN, pin 1): the datasheet's always-on configuration (electrical characteristics specified at V_EN = V_IN; abs max V_EN 6.5 V, p.4). This is path 2 of the card's three — no resistor, no new footprint. Part: TPS7A02, SOT-23-5 (DBV) | none — done |
| `U3.11` | **BLOCKED-ON-OPERATOR** — MAX-M10S `RF_IN` (UBX-20035208 Table 10, p.9: "GNSS signal input") has no antenna feed on the board: no GPS antenna part and no RF net touches U3 (the only RF part is `ANT1`, the 2.4 GHz U.FL). Not closed by declaration. Four options costed in `PCB-S0-NETLIST-AUDIT.md` §3.1 (recommended: U.FL + matching network); any option adds a part and therefore **forces a re-freeze** | operator decision |
| `U2.7`, `U2.11`, `U2.15`, `U2.16` | **SETTLED — all four INTENTIONAL (S0b)**. The land pattern on the board is the 16-pad HOPERF RFM9XW, and the vendor drawing it comes from (`HOPERF RFM95/96/97/98(W) data sheet §1.4 "Pin Description", p.11`) reads **7 = DIO5, 11 = DIO3, 15 = DIO1, 16 = DIO2** — four spare, software-configured digital I/O, *not* ground tabs. The parallel audit's "probable GROUND tab" reading is therefore refuted (grounding a DIO line would be the defect). The board's netted pads match that same table pin-for-pin: 2 MISO / 3 MOSI / 4 SCK / 5 NSS / 6 RESET / 9 ANT (`RF_OUT`) / 13 3.3V (`+3V3`) / 14 DIO0 (`LR_DIO0`), 1+8+10 GND, and pad 12 (vendor DIO4) used as `LR_BUSY` | declared no-connect. Separate operator item: the `U2` Value (`LR2021F33`) and the BOM ("NiceRF LoRa2021") describe 18-pin modules that cannot fit these 16-pad lands — audit §4.3 |
| `U3.4`, `U3.5`, `U3.6`, `U3.9`, `U3.13`–`U3.18` (10) | **SETTLED from the datasheet (S0b)** — the U3 footprint is the **full 18-pad module** (`ublox_MAX`), so every Table 10 pin exists on the board. **3 FIXED:** `U3.6` V_BCKP → `+3V3` (backup supply 1.65–3.6 V, electrical spec p.11 — the board's only 1 F cell is the `VCAP` supercap on the LDO input, a different net, so no supercap is intended here); `U3.9` RESET_N → `+3V3` (active low; Table 11, p.10 lists RESET_N as "Input pull-up" in every mode, so the internal pull-up makes the tie safe *and* deterministic). **6 INTENTIONAL no-connect:** `U3.4` TIMEPULSE (output), `U3.5` EXTINT ("leave open if not used"), `U3.13` LNA_EN (no external LNA), `U3.14` VCC_RF (no active antenna), `U3.16` SDA + `U3.17` SCL (module used over UART), `U3.18` SAFEBOOT_N ("leave open if not used"; footnote 15, p.9: internally linked to TIMEPULSE through 1 kΩ, so pad 4 must stay open too — it does). **1 INTENTIONAL that must stay open:** `U3.15` VIO_SEL — Table 10, p.9: "Connect to GND for 1.8 V supply, or leave open for 3.3 V supply"; the board's V_IO (pad 7) and the ESP32-C3 I/O are `+3V3`, and the electrical spec (p.11) allows V_IO up to 3.6 V only when VIO_SEL is open (tying it to GND caps V_IO at 1.98 V) | only `U3.11` RF_IN remains open (row above) |
| `U4.4` | **SETTLED — INTENTIONAL (S0b)**. TI SBVS277C Figure 5-2 / Table 5-1, p.3: DBV pin 4 = **NC** ("not internally connected. Connect to ground or leave floating.") and pin 5 = **OUT** — which is exactly what the board carries (`+3V3` on pad 5). **Two repo artefacts were wrong and were corrected**: `balloon_symbols.kicad_sym::TPS7A0233PDBVR` (pin 4/5 function order swapped, both in-repo copies) and `full_pipeline.py::make_ldo_pads()` (pad table + docstring), with `build_sch.py`'s RP2040-variant wiring moved to pin 5 for consistency | none on the board |

**Structural finding (this is the part that matters).** `schematics/v_c3_flight.kicad_sch`
is a STUB: it contains exactly ONE symbol (U2) and its `(nets)` section is empty.
`kicad-cli sch export netlist` on it emits a single component and zero nets.  The
board's 22 nets were authored in generator code (`gen_pcb.py` / `route_*.py`), not
imported from a schematic.  Consequence: **no pad on this board can be certified
"intentionally unconnected" from the repo** — every classification above is
component-semantics inference, and the two independent audits still disagree on 5
pads.  This is the ADR-028 schematic-first gap and a `needs_input` item for the
operator.

## 4. Provenance — which table produced the shipped placement

**Answer: `fix_placement_v2.py`** (commit `93427ca`, "C3 flight PCB placement — 0
shorting_items, 0 solder_mask_bridge (Gate 2.5 PASS)"), literal `placements` dict,
applied with pcbnew to `output/v_c3_flight_final.kicad_pcb`.

Evidence: the dict matches the shipped board's positions within 0.1 mm for 16 of
20 footprints; every other candidate table (`gen_pcb.py`, `grid_placement.py`,
`placement_fix.py`, `fix_placement.py`, `output/fix_placement_p0*.py`,
`output/replace_footprints*.py`) matches **0**.  That commit rewrote
`v_c3_flight_final.kicad_pcb` (−2279/+23 lines), and
`output/route_4layer_v2.py` then converted it to 4 layers.

Chain: `fix_placement_v2.py` → `v_c3_flight_final.kicad_pcb` →
`route_4layer_v2.py` → shipped `v_c3_flight_4layer_routed.kicad_pcb`.

Why it recurred: (a) the table's comments do the checking by hand ("Gap between U1
and U2: 29.5-20.7 = 8.8mm ✓") while the real overlaps are sub-millimetre;
(b) the scripts hard-code an absolute path into a *different clone*
(`~/repos/balloon-fresh`), so both clones inherited the same unresolved near-miss;
(c) two scripts wrote the same routed path, last writer wins.

**The ONE source of truth is now**
`KiCadRoutingTools py_placer/place_optimize.py` invoked by
`tracker/hardware/publish_placed_board.py`, with
`gate25_check.py` as the referee — recorded as `canonical_placement_source` in
`tracker/hardware/placement-source-of-truth.json`.

**Archived (11 files, `git mv` → `archive/hardware-placement-legacy/`, never
deleted):** `fix_placement.py`, `fix_placement_v2.py`, `placement_fix.py`,
`grid_placement.py`, `output/fix_placement_p0{,_v2,_v3}.py`,
`output/replace_footprints{,_v2}.py` (all hand-typed tables), plus
`route_4layer.py` and `r0r2_novias.py` (second writers of a live board path).
`placement_guard.py` now exits 0 (was 12 violations: 3 × R1 double-writer, 9 × R2
unregistered coordinate table).

## 5. Handoff to S1 (routing) — and the caveats

* **S0b (netlist of record):** build NEW routing on
  `output/v_c3_flight_4layer_placed_netfix.kicad_pcb` (sha256 `aa76fbbb85ce…`) — same placement,
  three pads tied. The pre-fix board floats `U4.3` EN, which leaves the 3V3 rail disabled
  (`PCB-S0-NETLIST-AUDIT.md` §2), so any board routed from it is dead on arrival.
* Build the PLACEMENT comparison on `output/v_c3_flight_4layer_placed.kicad_pcb`
  (`f3cf0143e7de…`); S1's comparability anchor is this sha256 + one frozen
  `.kicad_dru`.
* The board carries the 3 zone definitions (In1.Cu GND pour, In2.Cu +3V3 pour,
  4-layer keepout) with NO fill geometry — refill after every import.
* `unconnected = 64` at the start is the pre-route baseline, not a regression.
* Do NOT hand-nudge coordinates.  If a placement change is needed, rerun
  `publish_placed_board.py` (or the same placer with a different lap) and re-freeze
  with a new sha256 — that is the only sanctioned way.

Items requiring a human decision before fab (not blockers for S1):
1. `U4.3` (regulator EN) floating → tie to VCAP or ground it deliberately.
2. `U3` — 11 unconnected pads, no GPS RF net; confirm the fitted module's antenna
   strategy against the u-blox MAX-M10S datasheet.
3. The schematic is a stub — the board has no netlist provenance. ADR-028 says
   schematic first; a netlist re-derivation would close the whole class.

## 6. PCB-S0b — netlist closure (card `t_a1f8e389`)

The 27 netless pads of the frozen placement are closed: **3 FIXED, 23 INTENTIONAL (cited),
1 BLOCKED-ON-OPERATOR, 0 unknown** (full per-pad table + citations in
`PCB-S0-NETLIST-AUDIT.md`).

| item | value |
|---|---|
| netlist of record | `output/v_c3_flight_4layer_placed_netfix.kicad_pcb` |
| sha256 | `aa76fbbb85ce89ffd6b5e346ca7b5f53575035ba611ec137f3c086ac4dc0809a` |
| frozen placement | unchanged at `f3cf0143e7deff991e9650643f1322945388fd135efbf5191f51520dcd6edaa6` |
| gate25 (`output/s0b/gate25_netfix.json`) | fp 20 · pads 125 · segments 0 · vias 0 · zones 3 · netless 24 · pad_overlap_pairs_0.2 mm 0 · courtyards_overlap 0 · violations_total 4 (all `silk_edge_clearance`) · shorting_items 0 · clearance 0 · unconnected 67 · **PASS** |
| `placement_guard.py --gate25` | **exit 0** — `gate25: fp=20 pad_overlaps=0 segments=0 -> PASS`, `violations: []` |
| re-freeze triggered? | **no** — ties to nets that already exist; 20 footprints identical in position/rotation/identity, 0 tracks, 0 vias, 22-net table unchanged (`output/s0b/netlist_fix_report.json`) |

Ties applied (each to a net that already exists on the board):

| pad | function | from → to | authority |
|---|---|---|---|
| `U4.3` | TPS7A02 EN | (floating) → `VCAP` (= IN) | TI SBVS277C Table 5-1 p.3 + §6.5 (internal pulldown; EC at V_EN = V_IN) |
| `U3.9` | MAX-M10S RESET_N | (floating) → `+3V3` | UBX-20035208 Table 10 p.9 + Table 11 p.10 |
| `U3.6` | MAX-M10S V_BCKP | (floating) → `+3V3` | UBX-20035208 Table 10 p.9 + supply table p.11 (1.65–3.6 V) |

Still open for the operator (neither is a netlist typo, neither was closed by guessing):
`U3.11` RF_IN has no GNSS antenna feed (options + recommendation in the audit §3.1; a feed part
forces a re-freeze), and the `U2` lands/part mismatch (audit §4.3).
