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

Board totals: 20 footprints, 125 pads, 22 nets, 27 pads with net 0.

| # | pads | what they are | classification |
|---|---|---|---|
| 1 | `U2.7`, `U2.11`, `U2.15`, `U2.16` (4) | LR2021F33 on the HOPERF RFM9XW pad map: pins 7/11/15/16 are the spare modem DIO lines (RFM9x: 7=DIO5, 11=DIO3, 15=DIO1, 16=DIO2). The design routes only DIO0 (`LR_DIO0` net 15) and BUSY (`LR_BUSY` net 14). | **intentional (NC)** — 4 |
| 2 | `U1` × 9 unnumbered `0.7×0.7 mm` SMD pads in a 3×3 grid | `ESP32-C3-WROOM-02` module underside/mechanical pad array. They carry NO pin number, so no netlist can reach them; the module's numbered ground pad (`U1.19`, 13 copper items incl. 12 PTH vias) is on GND. | **intentional (mechanical/thermal)** — 9. Action: stitch to GND in the pour/routing stage (S1) |
| 3 | `J1.6` (1) | 6th pin of the 1×06 programming header. Pins 1–5 carry GND / +3V3 / EN / UART0_TX / UART0_RX. | **intentional (spare pin)** — 1 |
| 4 | `U4.3`, `U4.4` (2) | SOT-23-5 regulator (`TPS7A02`): `U4.1`=VCAP, `U4.2`=GND, `U4.5`=+3V3 are connected. On the TI SOT-23-5 pin map 3 = EN and 4 = NC. | **U4.4 = intentional (NC). U4.3 = GAP — needs a decision**: an enable pin left floating is not a design choice, it must be tied to VCAP (or deliberately grounded to keep the rail off). Verify against the TPS7A02 datasheet before fab — 1 gap |
| 5 | `U3.4`, `U3.5`, `U3.6`, `U3.9`, `U3.11`, `U3.13`, `U3.14`, `U3.15`, `U3.16`, `U3.17`, `U3.18` (11) | u-blox MAX form-factor GPS (`ublox_MAX` footprint, 18 pads). Connected: `U3.1/10/12`=GND, `U3.2/3`=UART, `U3.7/8`=+3V3. | **GAP / UNVERIFIED — 11**: in the MAX pin family the majority of the 18 pads are GND/shield and pin 11 is the RF input. The board routes NO RF net to U3 at all, so either the fitted module has an internal antenna or the GPS antenna is missing. The u-blox pin table could not be fetched from this host (the vendor PDF URL returned an HTML error page and the browser daemon is down), and **no datasheet for it exists in the repo** |

**Structural finding (this is the part that matters).** `schematics/v_c3_flight.kicad_sch`
is a STUB: it contains exactly ONE symbol (U2) and its `(nets)` section is empty.
`kicad-cli sch export netlist` on it emits a single component and zero nets.  The
board's 22 nets were authored in generator code (`gen_pcb.py` / `route_*.py`), not
imported from a schematic.  Consequence: **no pad on this board can be certified
"intentionally unconnected" from the repo** — classifications 1–4 above rest on
component semantics (RFM9x pin map, footprint construction, header usage), and the
11 U3 pads cannot be closed at all without the u-blox datasheet.  This is the
ADR-028 schematic-first gap, and it is a `needs_input` item for the operator.

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

* Build ONLY on `output/v_c3_flight_4layer_placed.kicad_pcb`
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
