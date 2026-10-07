# PROGRESS — v9 hub board, first PCB, S0 placement

Branch `feat/v9-hub-placement`, worktree `/home/c03rad0r/worktrees/bf-hubplace`,
base `github/main` @ `a09dcbd6856ccb126b44a76ffbbb1497f59dd200`.

(force-added: `PROGRESS.md`/`REPORT.md` are gitignored, `.gitignore:67/68`.)

## Cluster 1 — recon (done)
- Read the deciding records: ADR-055 (hub geometry, **Proposed**), ADR-051 §2.3 (growth),
  `docs/analysis/hub-outline-authority.md`, ADR-046 / `docs/WING-TO-HUB-SOCKET-SPEC.md`
  (wing sockets + the 0.9 mm slot), ADR-048, ADR-054, ADR-053, ADR-052, ADR-108 R1
  (pin plan of record).
- Tooling present and working: `kicad-cli` 9.0.8, `pcbnew` 9.0.8 (`/usr/bin/python3.14`),
  `placement_guard.py`, `gate25_check.py`, `drc_score.py`, `placement-source-of-truth.json`,
  `drc_snapshots/history.jsonl`, `PLACEMENT-S0-FREEZE.md`, KRT v0.22.0 at
  `~/tools/KiCadRoutingTools` (`py_placer/place_optimize.py`, `py_placer/place_seed.py`).
- Netlist of record: `tracker/hardware/schematics/flight_board/v9_flight.net`
  sha256 `d0708df92bd2ad357a9c91007c7a9e31d9c2fd1c92743ddb4a119f39cfa53db3`
  — 46 components, 51 nets (matches the brief).

## Cluster 2 — board creation (done)
- Wrote `tracker/hardware/build_hub_board_v9.py` — the single writer of
  `tracker/hardware/hub_board_v9.kicad_pcb` (placement_guard R1), no literal coordinate
  table (R2). It reads the committed netlist, loads every footprint from its real library,
  assigns the netlist's nets, seats the mechanical interfaces parametrically and packs the
  rest by computed FFDH.
- **Repo defect found (reported, NOT fixed):** the three committed v9_lib footprints
  (`LoRa2021F33_2G4`, `LoRa2021_Castellated`, `SX1280_QFN24`) and
  `Tracker_Mechanical:Wing_Tab_4P` are **not loadable by KiCad 9** — each carries a
  duplicated `(version …)/(generator …)` header, and three carry `;;`/`#` comment lines.
  `kicad-cli fp export svg` → "Unable to load library"; `pcbnew.FootprintLoad` → None.
  Workaround in the builder: a NORMALISED COPY in `output/.hub_v9_libcache/` (comment lines
  + the duplicated header tokens dropped, geometry untouched). Pad counts confirm the real
  geometry: F33 = 18 pads, SX1280_QFN24 = 25, LoRa2021_Castellated = 18, Wing_Tab_4P = 8.
- 39 of 46 components are placeable. **7 are not**: `PVA1`, `PVA2` (hub array cells) and
  `U_CUT1..U_CUT4`, `U_HUB_CVT` all carry an **EMPTY footprint field** on the netlist
  (no land pattern exists) — deferred, see REPORT.md.

## Cluster 3 — outline resolution (done, MEASURED)
- `--outline 55x45` (the v8h-inherited outline of record): the pack **ran out of room**;
  28 of 39 parts were left unseated and the board scored **389 pad-box overlaps / 199
  courtyard overlaps**. Quantitative reason: the interior (edge parts removed) needs
  **2203 mm²** of courtyard against **2279 mm²** available on 55×45 = a **96.7 % packing
  density** — unachievable. **The v9 electronics do not fit on 55 × 45 mm.**
  (Sum of measured courtyard areas 2582 mm² > board area 2475 mm².)
- **Resolution: the outline is 103.0 × 103.0 mm** — ADR-051 §2.3 ("Implied continuous
  single-face square … 103.0 × 103.0 mm") + ADR-055 D5.  The 55 × 45 mm figure is the
  *starting* outline (ADR-055 §3), not the destination.  All 39 parts seat.
- Caveats on the record: ADR-051/ADR-055 are **Proposed**; the array AREA is the
  operator's open **duty choice**; ADR-055 D7 (integrated vs split carrier) is open;
  ADR-051 §2.3's *practical* outline is only "≈90×90 … ≈115×115 mm" so it was not frozen.

## Cluster 4 — placement (done)
- Packer rewritten as a **collision-checked bottom-left pack on a computed 1 mm grid**,
  cleared against the gate's own pad-box proxy UNION the courtyard.  The first two attempts
  (naive FFDH shelf, then a bounding-box pack) scored 389/199 and 7/2 — both rejected.
- Fixed a floorplan bug: ANT2/ANT4 had both been seated on the north edge at the same
  fraction; the four U.FL sites now sit at distinct fractions clear of the socket seats.
- `KIID.SeedGenerator(20261007)` added → the emitted board is **byte-deterministic**
  (two runs → identical sha256).
- KRT `place_optimize.py` laps tried: `--max-displacement 2 --clearance 0.3` → gate 2 proxy
  pairs (KRT reports `pad_overlap_pairs 0` on its own metric while the gate's conservative
  proxy finds 2) → rejected; `--max-displacement 1 --clearance 0.7 --no-rotate --lock
  J_W1..J_W4 ANT1..ANT4` → **gate 0/0** → **frozen**.  Both the seed and the lap reproduce
  byte-identically across runs.

## Cluster 5 — S0 gates + freeze record (done)
- `gate25_check.py hub_board_v9.kicad_pcb` → **placement_gate PASS**: 39 fp, 251 pads,
  0 segments, 0 vias, `pad_overlap_pairs_0.2mm 0`, `exact_pad_overlap_pairs_0.2mm 0`,
  `courtyards_overlap 0`.
- `placement_guard.py --gate25 hub_board_v9.kicad_pcb` → `ok: true`,
  `fp=39 pad_overlaps=0 segments=0 -> PASS`; **process exit 1** from **two PRE-EXISTING
  repo-scan violations on other boards**, proven pre-existing on a detached worktree of
  the untouched `a09dcbd`.
- Frozen sha256 `2f0a66733b7a853b0052062e1e73833e7194fc7c38dcc257a749965314ab9238`;
  seed sha256 `8748e7587d596dbd0f950b85e08f4c0c035a78ea9c9506a7fe5e41000e9d1533`.
- Freeze recorded: `PLACEMENT-S0-FREEZE-v9-hub.md`, a `v9_hub_board_placement` record in
  `placement-source-of-truth.json`, two rows in `drc_snapshots/history.jsonl`.
- Slot: **plain pads, no slot** (WING-TO-HUB-SOCKET-SPEC §2.2 Option B) — the wing side
  must match.

## Cluster 6 — netlist audit (done)
31 netless board pads, all classified, 0 unknown:
- **9** — `U1` unnamed shield/thermal pads of `RF_Module:ESP32-S3-WROOM-1U` (no pad number
  ⇒ cannot carry a net; the same class recorded at `PCB-S0-NETLIST-AUDIT.md`).
- **19** — marked `no_connect` in the schematic (19 `(no_connect …)` items): U1
  IO0/IO3/IO45/IO46 + IO35/IO36/IO37 (ADR-108 §Electrical constraints + strapping audit);
  U2.10 `ANT-2G4` (ADR-034 D5 / R1.3); U3.9/16/17 (R1.5); U5 EXTINT/LNA_EN/VCC_RF/VIO_SEL/
  SDA/SCL/SAFEBOOT_N (R1.5 + MAX-M10S `UBX-20035208` Table 10); U7.4 = TPS7A02 DBV pin 4,
  NC on the part (SBVS277C Table 5-1 / R1.5).
- **3 EXPECTED** — `U1.3` EN, `U1.13` USB_D-, `U1.14` USB_D+: the console connector is not
  fitted (OPEN-10 / ADR-108 R1.7). These are the sheet's 3 ERC errors and are expected on
  this revision. Not fixed.

Side findings (flagged, not fixed): the v9 footprint library does not load in KiCad 9
(duplicated headers + comment lines); the socket spec §3.2 still calls land 3 an unnetted
RF_FEED while the schematic wires it to CUT_SENSE and `hub_array_topology_check.py` R8
requires that.

## Cluster 7 — tests (done)
`pytest tests/test_pcb_pipeline_gates.py tests/test_pcb_track_import.py
tests/test_adr_numbering.py tests/test_bypass_diode_check.py -q` → 42 passed, 13 skipped,
0 failed.  `scripts/hub_array_topology_check.py` → PASS (exit 0).
