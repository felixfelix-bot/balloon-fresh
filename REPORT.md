# REPORT — first v9 hub PCB: created + placed, S0 gates PASS

**Task:** create and place the first v9 hub PCB from the settled v9 schematic and pass the S0
placement gates. **Branch** `feat/v9-hub-placement` · **worktree** `~/worktrees/bf-hubplace` ·
**base** `github/main` @ `a09dcbd6856ccb126b44a76ffbbb1497f59dd200` · 2026-10-07.
**This is S0 PLACEMENT ONLY — the board is NOT routed and nothing is frozen for fab.**

---

## board_created

`tracker/hardware/hub_board_v9.kicad_pcb` — 103.0 × 103.0 mm, 4 copper layers (ADR-029/030),
0.6 mm, 39 footprints, 251 pads, 51 nets, `(gr_rect (start 0 0) (end 103 103))` on Edge.Cuts.

**How, exactly.** `tracker/hardware/build_hub_board_v9.py` (new, this branch) is the single writer
(placement_guard R1) and holds no literal coordinate table (R2). Run
`python3 build_hub_board_v9.py --publish`:

1. reads the committed netlist of record `schematics/flight_board/v9_flight.net`
   (sha256 `d0708df92bd2ad357a9c91007c7a9e31d9c2fd1c92743ddb4a119f39cfa53db3`, 46 comps / 51 nets)
   — every component, value, footprint field and net comes from that file, nothing re-derived;
2. loads each footprint from its **real** library via `pcbnew.FootprintLoad`, sets the FPID to the
   netlist's lib_id and assigns the netlist's nets to the pads;
3. computes the mechanical floorplan seats (four wing sockets on the four edge centre lines at 90°
   spacing, ADR-046 §1; four U.FL sites on the board edge, ADR-029 D3 / ADR-045);
4. bottom-left packs the rest on a computed 1 mm grid, each part cleared against the gate's own
   conservative pad-box **proxy UNION its courtyard** (no typed coordinates);
5. emits `output/hub_board_v9_seed.kicad_pcb` (byte-deterministic — `pcbnew.KIID.SeedGenerator`);
6. runs the repo's canonical placer, KRT `py_placer/place_optimize.py`
   (`--max-displacement 1 --max-passes 6 --step 1.0 --clearance 0.7 --halo-base 1.2
   --halo-weight 12.0 --no-rotate --lock J_W1 J_W2 J_W3 J_W4 ANT1 ANT2 ANT3 ANT4`), and writes the
   lap to `tracker/hardware/hub_board_v9.kicad_pcb`.

Reproducibility **measured**: seed rebuilt twice → same sha256 (`8748e7587d59…`); the KRT lap run
twice from that seed → same sha256 (`2f0a66733b7a…`). The v9 hub needed a seeding stage the v_c3
board did not: KRT's `place_optimize` is a bounded-displacement quench and cannot place an unplaced
board, and `place_seed.py` requires a floorplan `--intent` JSON.

## outline_resolved

**103.0 × 103.0 mm square.** Source: `docs/adr/051-hub-array-and-cut-topology.md` §2.3 ("Implied
continuous single-face square … **103.0 × 103.0 mm**"; "the hub outline grows … to a panel sized by
the array"; "this is a **FORM-FACTOR CHANGE**, not a tweak") together with
`docs/adr/055-hub-geometry-final.md` D5 ("the hub grows to ≈103 mm square for 106 cm²",
`√106.1 cm² ≈ 103 mm`).

**The 55 × 45 vs ~103 mm question, answered explicitly.** `docs/analysis/hub-outline-authority.md`
s4 establishes the 55 × 45 mm figure (quoted 55.15 × 45.15 with the 0.15 mm stroke) as the *only*
outline encoded in a generated artifact — `output/v8i_krt_gnss.kicad_pcb` `gr_rect (0,0)→(55,45)`,
corroborated by v8b/v8f/v8h/v8j/v_c3_flight_final — and ADR-029 §Context ratifies that outline for
v9; ADR-055 §3 likewise calls 55 × 45 "the current outline". **I did not use it, and I did not pick
it silently — I measured it:**

* the 39 footprinted v9 components demand **2582 mm²** of courtyard against a **2475 mm²** board
  (usable interior 2279 mm²);
* a best-effort collision-checked pack **left 28 of 39 parts unseated** and the board scored
  **389 pad-box overlaps / 199 courtyard overlaps**;
* the interior alone needs **2203 mm² into 2279 mm² = 96.7 % packing density** — unachievable.

So the v8h-inherited outline cannot carry the v9 hub **for its electronics alone**, before the array
is considered. Combined with (a) ADR-055 §3's own words "no v9 hub PCB exists, so nothing is frozen
in a board file and **the outline remains ours to set**" and (b) the v9 hub being the **array
carrier** (the netlist carries the hub-array cells `PVA1…`, ADR-051 §2.1; ADR-055 D6 puts the cells
on the hub's UPPER face), the outline is the grown panel at its recorded value, 103.0 mm.

**Caveats on the record, not hidden:** ADR-051 and ADR-055 are both **Status: Proposed** (text not
human-accepted), ADR-055 §3 forbids treating its own content as frozen, and ADR-055 D3 makes the
array **AREA the operator's open duty choice** (106.1 / ≈80 / ≈53 cm² = full / 75 % / 50 %).
ADR-051 §2.3's *practical* outline — array square **plus** the four socket land rows, their 1.5 mm
component keep-out and the component court — is recorded only as "**≈90 × 90 … ≈115 × 115 mm**", i.e.
approximate, so it was not frozen to a millimetre. Therefore **103.0 mm is a placement-stage
floorplan, not a frozen fab outline**; a fab outline additionally needs those dead bands added.
ADR-055 D7 (one integrated board vs a separate thin array carrier) stays **open** and uncosted.

## placements

**39 of 46 components placed.** The 7 that could not be placed all carry an **EMPTY footprint
field** on the netlist — no land pattern exists: `PVA1`, `PVA2` (hub-array cells;
`V9_HUB_ARRAY_CELLS = 2` is a documented *placeholder* and ADR-051 §4 / ADR-054 §4.5 / ADR-055
D3+D7 leave the count, plane, carrier and outline OPEN), `U_CUT1..U_CUT4` and `U_HUB_CVT` (the parts
themselves are `TODO(unverified)`, `OPEN-26`/`OPEN-27`). Inventing a land for an open decision would
be exactly the "unverified promoted to a number" failure, so they are deferred, not guessed.

## placement_guard_exit

**1** — and **not** for this board. `placement_guard.py --gate25 hub_board_v9.kicad_pcb` reports
`"gate25": {"ok": true, "detail": "gate25: fp=39 pad_overlaps=0 segments=0 -> PASS"}`, but the
script's exit is `1 if problems else 0` where `problems` is a **repo-wide scan** and that scan
carries **two PRE-EXISTING violations on other boards**:

```
R1: board 'v_c3_flight_v7_diagonal.kicad_pcb' has 2 writers: output/route_v7_diagonal.py, route_diagonal.py
R2: 'auto_bootsel/auto_bootsel_pcb.py' defines 10 literal coordinate rows and is NOT a registered placement source
```

**Proven pre-existing:** a detached worktree of the untouched base (`git worktree add --detach
/tmp/bf-base a09dcbd`) returns the **identical two strings and the same exit 1**, and that tree
contains neither `hub_board_v9.kicad_pcb` nor `build_hub_board_v9.py`. The v9 hub board contributes
**no** violation (the guard's R1 pattern does not match its generator, and it defines no literal
coordinate table). They are **not fixed here** — they are other boards' provenance and fixing them
means editing someone else's build tooling.

**What I ran instead / in addition:** the repo's fuller referee `gate25_check.py`, whose
`placement_gate` is `PASS` on the frozen board:

```
footprints 39 | pads 251 | segments 0 | vias 0 | zones 0 | margin_mm 0.2 | pads_with_no_net 31
pad_overlap_pairs_0.2mm 0 | exact_pad_overlap_pairs_0.2mm 0 | courtyards_overlap 0 | placement_gate PASS
drc: violations_total 69 {drill_out_of_range 12, copper_edge_clearance 16, silk_overlap 12,
     silk_over_copper 16, lib_footprint_issues 7, silk_edge_clearance 6};
     courtyards_overlap 0, shorting_items 0, clearance 0, unconnected 157
```

## pad_overlap_pairs_0p2mm

**0** (pad-box proxy, and also 0 exact pad-rectangle overlaps).

## courtyards_overlap

**0** (from `kicad-cli pcb drc --format json` — the authority; `gate25_check.py` never re-implements
a courtyard test).

## frozen_board_sha256

```
tracker/hardware/hub_board_v9.kicad_pcb
2f0a66733b7a853b0052062e1e73833e7194fc7c38dcc257a749965314ab9238
output/hub_board_v9_seed.kicad_pcb   (reproducible input)
8748e7587d596dbd0f950b85e08f4c0c035a78ea9c9506a7fe5e41000e9d1533
netlist of record v9_flight.net
d0708df92bd2ad357a9c91007c7a9e31d9c2fd1c92743ddb4a119f39cfa53db3
```

Freeze recorded in the repo's existing convention: a new
`tracker/hardware/PLACEMENT-S0-FREEZE-v9-hub.md` (same shape as the v_c3
`PLACEMENT-S0-FREEZE.md`), a `v9_hub_board_placement` record + a `boards` entry in
`tracker/hardware/placement-source-of-truth.json`, and two rows appended to
`tracker/hardware/drc_snapshots/history.jsonl` (label `v9-hub-place`).

## slot_disposition

**Plain pads, no slot** (the spec's own documented Option B, `docs/WING-TO-HUB-SOCKET-SPEC.md` §2.2).
`J_W1..J_W4` are the `Tracker_Mechanical:Wing_Tab_4P` land sets — 8 lands, 4 per face — and the
footprint contains **no drill or NPTH feature at all** (verified by grep, and the DRC report shows no
slot item), so no 0.9 mm slot was propagated.

**Why:** ADR-046 §4.3's 0.9 mm slot is **below JLCPCB's minimum non-plated slot of 1.0 mm** (JLCPCB
capabilities, see skill `pcb-fab-readiness-gating` rule 15) and its tolerance stack worst-cases to
`(0.9 − 0.2) − (0.6 + 0.1) = 0.00 mm` — a zero-clearance interference fit. A **plated** 0.9 mm slot is
not an acceptable answer: it is a copper-lined barrel that would short the lands around the tab.
Option B needs no NPTH operation and no tolerance stack.

**This is a design change and the wing side must match it:**
`tracker/hardware/wing_board/wing_board_v9.kicad_pcb` carries an 8 mm tab built for the slot; with no
hub slot it becomes a flat, fillet-soldered lap on the pads, aligned by hand/fixture — the cost
§2.2 already prices.

## netless_pads

**31** pads carry no net; **0 unknown**. (1) **9** are the `RF_Module:ESP32-S3-WROOM-1U`
footprint's **unnumbered** shield/thermal pads — no pad number, so no net is possible (the same class
recorded at `PCB-S0-NETLIST-AUDIT.md` for the v_c3 board). (2) **19** are marked `no_connect` on the
sheet — U1 IO0/IO3/IO45/IO46 + IO35/IO36/IO37 (4 boot straps + 3 octal-PSRAM pins, **deliberately
unassigned**, ADR-108 §Electrical constraints + strapping audit); U2.10 `ANT-2G4` (the F33 carries TX
only, ADR-034 D5 / R1.3); U3.9/16/17 (R1.5); U5 VIO_SEL/SAFEBOOT_N (u-blox `UBX-20035208` Table 10 /
R1.5) and EXTINT/LNA_EN/VCC_RF/SDA/SCL (same datasheet table); U7.4 (TPS7A02 DBV pin 4 is NC on the
part, `SBVS277C` Table 5-1). (3) **3 EXPECTED** — `U1.3` EN, `U1.13` USB_D-, `U1.14` USB_D+: the
ESP32-S3 console is USB-Serial-JTAG and **no connector is fitted on this revision** (ADR-108 `OPEN-10`
/ R1.7). They are the sheet's **3 intentional ERC errors** (`v9_flight-erc.rpt`: 3 errors, all
`pin_not_connected`) and are expected here. **Nothing was "fixed"** — no schematic, netlist, band
split or part was touched.

Side finding, flagged not fixed: the socket spec §3/§3.2 still calls land 3 an unnetted `W<n>_RF`
provision, but the schematic wires it to `/CUT_SENSE_W<n>` and the repo's own gate
`scripts/hub_array_topology_check.py` **requires** that (`R8 cut-sense wired on interface(s):
W1, W2, W3, W4`; the script returns `VERDICT: PASS (exit 0)` on this revision). The **spec prose is
stale**, the schematic is the authority; neither was edited by this task.

## segments_and_vias

**`segments = 0`, `vias = 0`, `zones = 0`.** This is a **placement, not a route** — that is why the
S0 gates exist, and why no DRC number should be read as a routing quality claim. DRC on an unrouted
board is trivially quiet on copper: `shorts 0` / `clearance 0` assert nothing about routing. The
`unconnected = 157` is the pre-route ratsnest of the 51 nets, not a regression. Residual DRC classes
are all dispositioned: `drill_out_of_range ×12` = the WROOM-1U footprint's PTH shield pads
(footprint-inherited); `copper_edge_clearance ×16` = the four socket land rows on the interface edges,
which `WING-TO-HUB-SOCKET-SPEC.md` §4 says is *intentional* ("that edge is the one place copper
intentionally reaches the outline"; 4 sockets × 4 lands = 16); `silk_* ×34` cosmetic;
`lib_footprint_issues ×7` = the repo-local footprint libraries, unresolvable in a standalone DRC run.

## deferred

1. **7 components** with empty footprint fields (`PVA1/2`, `U_CUT1..4`, `U_HUB_CVT`) — no land
   pattern exists while ADR-051 §4 / ADR-054 §4.5 / ADR-055 D3+D7 leave the array open.
2. **The v9 footprint library does not load (repo defect, reported not fixed).**
   `balloon_flight_v9:LoRa2021F33_2G4`, `:LoRa2021_Castellated`, `:SX1280_QFN24` and
   `Tracker_Mechanical:Wing_Tab_4P` each carry a **duplicated** `(version …)/(generator …)` header and
   three carry `;;`/`#` comment lines the parser rejects; `kicad-cli fp export svg` says "Unable to
   load library" and `pcbnew.FootprintLoad` returns `None`. The builder reads a **normalised copy**
   from `output/.hub_v9_libcache/` (comments + duplicate header dropped, geometry byte-identical —
   pad counts 18 / 25 / 18 / 8 confirm the land patterns). The repo files were **not** modified;
   the generator that emits them should be fixed.
3. **Two pre-existing `placement_guard.py` scan violations** on other boards (see
   `placement_guard_exit`) — owner: whoever owns those boards' provenance.
4. **The stale socket-spec §3.2 land-3 description** vs the schematic's cut-sense wiring.
5. **Routing (S1)** — explicitly out of scope.
6. **Everything ADR-055 leaves open**: the operator's sustained-duty choice (freezes the array area),
   the 0.4 mm stack-up check (D4/Open item 3; the board carries the inherited 0.6 mm), the
   integrated-vs-split carrier cost (D7), the launch latitude/season, the standoff height, the loaded
   `Vmp`.
7. **No `TODO(unverified)` promoted to a number**; nothing ordered; nothing frozen for fab; no human
   sign-off requested (that comes only once a routed fab candidate is settled).

## tests_after

* `python3 -m pytest tests/test_pcb_pipeline_gates.py tests/test_pcb_track_import.py
  tests/test_adr_numbering.py tests/test_bypass_diode_check.py -q` → **42 passed, 13 skipped, 0 failed**.
* `python3 scripts/hub_array_topology_check.py` → **VERDICT: PASS (exit 0)**.
* `python3 gate25_check.py hub_board_v9.kicad_pcb` → `placement_gate: PASS` (0 / 0 / 0).
* `python3 placement_guard.py --gate25 hub_board_v9.kicad_pcb` → board gate `ok: true`,
  `fp=39 pad_overlaps=0 segments=0 -> PASS`; process exit **1** from the two pre-existing scan
  violations above (reproduced identically on pristine `a09dcbd`).

*Placement only. Nothing ordered, nothing frozen for fab.*
