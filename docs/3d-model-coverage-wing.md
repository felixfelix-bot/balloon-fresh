# 3D model coverage — v9 WING board

**Board:** `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`
**Board sha256 after this work:** `3bfd420749a6c8a779a84140eed4cee87e3672b47cd80f7fc7b98b3cb4296a86`
(was `8448d76b3a4e108f12016e1980bb954f068625d27522a1640a07ffc72fa3682c`; the delta is **+99
lines, 0 deletions**, all of them `(model …)` metadata — see §6 "what changed / what did not")
**Models:** `tracker/hardware/3dmodels/**/*.wrl` — plain-text VRML 2.0, committed, no install needed
**Generator:** `scripts/gen_3d_models_wing.py` (`--check` fails closed if the tree is stale)
**Gate:** `tests/test_3d_models_wing.py` (run: `python3 -m pytest tests/test_3d_models_wing.py -q`)

**Why this exists:** the wing carries the peak-power solar array and is jettisonable, so the
operator wants to *see* it before ordering. Before this work **no** reference on the wing carried
a 3D model, so a render showed four bare FR4 outlines: the three cells the wing exists to fly were
invisible. (The hub board is worse — its `${KICAD9_3DMODEL_DIR}/…step` references need
`kicad-packages3d`, 4.77 GB, which is **not** installed here and must not be: ~3 GB free.)

---

## 1. Measured board geometry (from the board file, not assumed)

| Item | Measured | Source |
|---|---|---|
| Body | **176.0 × 25.0 mm** | the 4 long Edge.Cuts `gr_line`s: `(0,0)→(176,0)`, `(176,0)→(176,25)`, `(176,25)→(0,25)`, `(0,25)→(0,17)` |
| Tab | **8.0 mm protruding × 9.0 mm wide**, at one end, y ∈ [8,17] | `gr_line`s `(-8,8)→(0,8)`, `(0,8)→(0,0)`, `(0,25)→(0,17)`, `(0,17)→(-8,17)`, `(-8,17)→(-8,8)` — matches `docs/adr/046-wing-board-interface.md` §3.2 |
| **Total outline (incl. tab)** | **184.0 × 25.0 mm** | x ∈ [−8, 176] from the Edge.Cuts extent (agrees with ADR-046 §3.2 "Total outline length (incl. tab) 184.0 mm") |
| Thickness | 0.6 mm, 2 layers | `(general (thickness 0.6))`; stackup F.Cu 0.035 / core 0.51 / B.Cu 0.035 |
| Placed references | **12**: `FB1 FID1 FID2 FID3 H1 H2 H3 J1 RF1 SC1 SC2 SC3` | parsed from the board (`reference` properties) |
| Lands / pads / segments | 19 pads, 8 track segments, 8 Edge.Cuts lines, 1 `gr_text` | parsed from the board |

## 2. The solar cells — class and count

**Class used: SMALL** (`52.07 × 19.65 × 0.20–0.21 mm`) — **not** the LARGE class.
**Count: 3** (`SC1`, `SC2`, `SC3`), one series string.

Evidence, strongest first:

1. `wing_board_v9.kicad_pcb` puts all three cell footprints under lib id **`WingV9:SolarCell_52x19mm`**
   with value **`SolarCell_52x19mm_0.5V`**, body silk `fp_rect (-26,3)–(26,22)` = **52 × 19 mm**, with
   one 1.6 × 4.0 mm land at x = ±28 (the two ends).
2. `docs/adr/046-wing-board-interface.md` §3.3 gives the cells' spans as x 4…56 / 62…114 / 120…172
   and y 3…22 — i.e. **52 mm along x, 19 mm along y** each.
3. `docs/adr/049-wing-architecture.md` §"Measured inputs" (operator-measured) gives the two classes:
   **small 52.07 × 19.65 × 0.20–0.21 mm** and large 78.55 × 38.90 × 0.21 mm (the large figure is
   repeated in `docs/adr/051-hub-array-and-cut-topology.md` §1.4). 52.07 × 19.65 is the only class
   that fits the board's 52 × 19 land field **and** fits the 25 mm body width; a 38.90 mm-wide cell
   cannot be placed on this board at all.
4. Cross-check: the modelled cell's measured extent in the delivered render is **51.88 mm** per cell
   (three runs), i.e. the board of record really is built around the SMALL cell.

> **Careful, and recorded as a live contradiction:** ADR-049 *recommends* three **LARGE** cells per
> wing (status **Proposed** — not human-accepted). The board of record is SMALL. The LARGE model is
> therefore shipped as a shared asset (`3dmodels/cells/`) for the hub/array direction, but it is
> **not** assigned to any wing footprint. Whatever the array decision becomes, the wing board in the
> repo today is a SMALL-cell board.

### Land-vs-cell discrepancy (finding, not fixed — it is a placement question)

As drawn, the land pitch is **56.00 mm** (lands at ±28 mm from each cell centre, ADR-046 §3.4) while
the measured cell is **52.07 mm** long: the modelled cell stops **1.17 mm short of each land's inner
edge**, so the cell body does not overlap its own lands. That is a genuine
`TODO(unverified)` — the real cell-tab geometry (contact width, pitch and offset from the cell edge)
has never been measured, and ADR-049 files it as **the order blocker**. Nothing was changed here: the
position/land geometry belongs to the placement record, not to this card.

## 3. Coverage — all 12 references

What each model *adds* matters, so the status column distinguishes a real part body from a
copper-matched land/dot (the board renderer already draws the F.Cu pads itself; those models only
make the reference explicit and tinted — they never invent an added body).

| Ref | Status | Model | Modelled dims (mm) | Dimensional source | What the model adds |
|---|---|---|---|---|---|
| `SC1` | **modeled** | `cells/solar_cell_small_52.07x19.65x0.21.wrl` | 52.07 × 19.65 × 0.21 | ADR-049 measured inputs (SMALL) | the cell body itself — invisible before (bare board render) |
| `SC2` | **modeled** | idem | idem | idem | idem |
| `SC3` | **modeled** | idem | idem | idem | idem |
| `J1` | **modeled** | `wing/wing_v9_tab_4pin_lands.wrl` | 4 lands 4.0 × 1.2 × 0.035, pitch 1.8, at x=−5, y=9.8/11.6/13.4/15.2 | board pads of `WingV9:WingTab_v9_4pin`; ADR-046 §2.1 pinout; F.Cu 0.035 from the stackup | the 4-pin interface lands (copper-matched); the 8×9×0.6 tab **finger** is board outline and is drawn by KiCad |
| `RF1` | **modeled** | `wing/wing_v9_rf_provision_pad_2x2.wrl` | 2.0 × 2.0 × 0.035 | board pad (2 × 2 rect); ADR-046 §2.4 (V2 provision) | the RF feed land (copper-matched); no antenna/matching/connector exists on v9 to model |
| `FB1` | **modeled** | `wing/ferrite_bead_0402_dnp.wrl` | 1.016 × 0.508 × **0.5** | 0402 imperial code = 0.040 × 0.020 in = 1.016 × 0.508 mm (definitional); **height is `TODO(unverified)`** (typical 0402) | a 0402 body — and it is **DNP** (`FerriteBead_0402_DNP_V2only`), so it renders at transparency 0.75 as a phantom, never as a fitted part |
| `FID1` | **modeled** | `wing/wing_v9_fiducial_1mm_dot.wrl` | ⌀1.0 × 0.035 | board pad (1 × 1 circle); footprint name `Fiducial_1mm_Mask2mm` | the fiducial copper dot (copper-matched); the 2 mm mask opening is not geometry |
| `FID2` | **modeled** | idem | idem | idem | idem |
| `FID3` | **modeled** | idem | idem | idem | idem |
| `H1` | **NO MODEL** | — | — | board pad (⌀2.2 `np_thru_hole`, drill 2.2) + board thickness 0.6 | **deliberate** — see §4 |
| `H2` | **NO MODEL** | — | — | idem | idem |
| `H3` | **NO MODEL** | — | — | idem | idem |

**Counts: 9 `modeled` / 3 `NO MODEL`** (of the 9: 4 real part bodies — `SC1`–`SC3`, `FB1` — and 5
copper-matched land/dot models — `J1`, `RF1`, `FID1`–`FID3`).

### Reused vs created

* **Created here (6 models):** the three-ref group `cells/solar_cell_small_52.07x19.65x0.21.wrl`,
  `cells/solar_cell_large_78.55x38.90x0.21.wrl` (shared asset, unassigned), plus
  `wing/wing_v9_tab_4pin_lands.wrl`, `wing/wing_v9_fiducial_1mm_dot.wrl`,
  `wing/ferrite_bead_0402_dnp.wrl`, `wing/wing_v9_rf_provision_pad_2x2.wrl`.
* **Reused: nothing.** Checked before creating: `git ls-tree -r github/main | grep -iE
  '3dmodel|\.wrl'` → **empty**, and no `feat/3d-models-hub` branch existed on `github` **or** `ngit`
  when this branch was cut (`git ls-remote --heads github 'refs/heads/feat/3d*'` → no match), so
  there were no hub-worker cell/part models to reuse. The shared cell models therefore live in a
  subdirectory named for sharing — `3dmodels/cells/` — **so the hub worker can reuse them instead of
  duplicating** (a LARGE-cell model is already there for the hub array direction).

## 4. Why the three NPTH holes carry **no** model (measured, not a preference)

`kicad-cli`'s renderer **punches the NC drill bore itself**. Measured 2026-10-08 with
`kicad-cli pcb render --side top --quality basic --width 700 --height 500` (basic = no floor, and no
`--perspective`, so a punched bore is literally see-through), counting transparent pixels inside a
5×5 window centred on each of the three hole positions:

| Board variant | `H1` | `H2` | `H3` |
|---|---|---|---|
| no model assigned (delivered) | **20/25 transparent** | **20/25** | **20/25** |
| first design: a ⌀2.2 × 0.6 cylinder filling the drill volume (z = −0.6…0) | 0/25 | 0/25 | 0/25 |
| second design: zero-thickness bore liner at the drill radius | *byte-identical image to "no model"* → buys nothing | | |

So modelling the hole **removes** it: the plug fills the bore. In the delivered
`--quality high --perspective` render (which has a floor/post-process) the bores are drawn by the
renderer as a black disc at each hole site (measured mean RGB ≈ (1,1,1) and (0,0,0) at `H1`/`H2`
against a neighbour patch of (38,63,49)) — the hole reads as a hole **because nothing was assigned**.
Also for the record: `H1`–`H3` are handling holes and the wing's jettisonability is itself
`TODO(unverified)` (ADR-049 open items), so there is no fastener to model either.

## 5. Model frame + unit convention (measured, because getting it wrong is silent)

KiCad reads a VRML coordinate as **2.54 mm (0.1 in)**, in the frame
**X = footprint-local +x, Y = −(footprint-local +y), Z = up with Z = 0 at the board's top face**.
Both parts were measured before any model was written:

1. **Probe export.** A throwaway 100 × 60 mm board with a 10 × 10 mm notch cut out of its (0,0)
   corner carried a 4 × 4 × 1 mm marker model authored with model-Y = −(footprint-local y).
   `kicad-cli pcb export vrml --units mm` reproduced the marker at exactly 4.00 × 4.00 × 1.00 mm,
   passed the model coordinates through with **no rotation**, mirrored the outline notch in Y, and
   added `translation 0 0 0.11811024` (= 0.3 mm = half the 0.6 mm thickness) to the model subtree.
2. **A shipped demo model.** `/usr/share/kicad/demos/ecc83/3d_shapes/ecc83.wrl` spans
   8.86 × 8.86 × 20.963 units = 22.5 × 22.5 × 53.3 mm against a footprint courtyard radius of
   10.6 mm — an ECC83 is ~22 mm across with a vertical axis. ×2.54 fits; ×1 does not.

**Render confirmation of the whole chain** (delivered top render, 1768 × 1376): calibrated on the
known 184.0 mm outline (7.4022 px/mm), the three cell faces measure **51.88 mm** wide each
(three runs: 294–677, 721–1104, 1148–1531 px) with 5.81 mm gaps — against the modelled 52.07 mm and
5.93 mm. The blue (cell-face) area is 167 017 px ≈ 3 × 52.07 × 19.65 mm². A `--side bottom` control
render contains **0** blue pixels, i.e. the cells are on the **top** face (a wrong Z convention would
have sunk them inside the 0.6 mm board).

## 6. Renders

| File | Size | Command |
|---|---|---|
| `tracker/hardware/wing_board/renders/wing_v9_top.png` | 1768 × 1376 | `kicad-cli pcb render --output renders/wing_v9_top.png --side top --quality high --perspective --width 1800 --height 1400 wing_board_v9.kicad_pcb` |
| `tracker/hardware/wing_board/renders/wing_v9_iso.png` | 1768 × 1376 | `… --side top --rotate -45,0,45 --quality high --perspective --width 1800 --height 1400 …` |

(kicad-cli 9.0.8 emits 1768 × 1376 for a requested 1800 × 1400 — the size is quoted as delivered.)
`--side right` was tried first for the "isometric" view and **rejected**: it is nearly edge-on for a
184 × 25 mm flat board and renders **0** pixels of cell face. The `-45,0,45` rotate is the isometric
view; both images show the three cell faces (top: 167 017 blue px; iso: 123 105 blue px).

**What is NOT in these renders:** they are the *bare board plus its parts* — no hub, no second wing,
no balloon line, no jettison hardware. They must not be described as an assembly.

## 7. What changed / what did not (the honest delta)

Changed: `build_wing_v9.py` (emits the `(model …)` children), the regenerated board
(**+99 lines, 0 deletions**), the models, the renders, this report, the test, and the wing's gate
record (`board_sha256` only).

Verified unchanged by parsing both revisions of the board and set-comparing: **nets (17)**,
**footprints (12) with their lib ids, references, positions and every pad**, **track segments (8)**,
**Edge.Cuts lines (8)**, **`gr_text` (1)**, **board thickness (0.6)** — all identical.
`assertion_changed: no` — no assertion, no net, no part position and no ADR decision was touched.

**Gate:** `pcb_order_gate.py … --fab tracker/hardware/output/gerbers_wing_v9` →
**ORDER GATE: PASS, errors 0, unconnected 0, warnings 23** (same five warning categories and the same
counts as the pre-change record: 12 `lib_footprint_issues`, 6 `silk_edge_clearance`, 2 `silk_overlap`,
2 `text_height`, 1 `silk_over_copper`), `--verify` → **VERIFIED, exit 0**, `fab_sha256` unchanged
(`90cb2480…`). Re-plotting the gerbers from the new board reproduces the committed package with only
the two embedded creation-date lines differing, i.e. **the copper is unchanged and the fab package
was not re-cut.**

---

## 8. ASSEMBLY: what would be needed to render hub + 4 wings (and why it is NOT done here)

**No assembly render is produced, and no wing orientation is invented.** The input below is missing,
and one of the candidate orientations is a measured contradiction, so any assembly transform would be
this worker's invention rather than a record. (`docs/adr/048-v9-hub-wing-interfaces.md` item 6 /
sheet item `OPEN-23` records exactly this: the contradiction is live.)

**Blocked by these unknowns, all of them records rather than opinions:**

1. **The wing's plane orientation is CONTRADICTORY across records, and unresolved:**
   * `docs/adr/049-wing-architecture.md` §5 item 6 — wing plane **VERTICAL**. Recorded there as a
     *derived inference*, not a cited fact, and that ADR's status is **Proposed (not human-accepted)**.
   * `docs/WING-TO-HUB-SOCKET-SPEC.md` §1 — the long axis is "perpendicular to the hub plane" **and**,
     in its next sentence, wings 1–2 are **horizontal** in the hub plane with 3–4 inclined ≈30° below
     it (self-contradictory in a single paragraph).
   * `docs/adr/046-wing-board-interface.md` §4.1 — "**90° to the hub plane**, wing plane normal to the
     hub plane" (a third variant, and it cannot hold together with the socket spec's sibling sentence).
   * `docs/adr/048-v9-hub-wing-interfaces.md` item 6 / `OPEN-23` — the contradiction is recorded
     **unresolved**; the hub footprint deliberately asserts **no** rotation. A parallel worker is
     resolving it right now; until that lands there is no frozen orientation ⇒ no assembly transform,
     and no socket mating axis.
2. **The socket mating geometry is unmeasured and not even fab-legal yet.** Hub-side land row, slot
   depth and slot tolerance are ADR-048 items 3/6 and sheet item `OPEN-24` (`TODO(unverified)`,
   ±0.10 mm assumed); ADR-049 §5 item 4 notes the 0.9 mm slot is **below JLCPCB's 1.0 mm minimum
   non-plated slot** with 0.00 mm worst-case clearance against a 0.6 mm tab. So the joint has neither
   a verified geometry nor a verified manufacturing route.
3. **The standoff height above the array is an open item — `docs/adr/055-hub-geometry-final.md` D6.**
   D6 fixes the array on the hub's **upper** face with the suspension attachment **raised on a
   standoff** so the balloon line and its shadow cone clear the array. Its *constraint* is known — the
   shadow centre is thrown `cot(e) × Z = 3.363 Z` away (`docs/analysis/wing-omnidirectional.md` §4) —
   but **the value is not fixed** ("the exact standoff is a layout number, `TODO(unverified)`"), and
   ADR-055 §Open items 6 lists it as unverified. Without it the hub-to-attachment vertical offset —
   and hence the whole stack's Z — is undefined.
4. **The hub half of the geometry is not renderable yet either.** `docs/adr/055` fixes the hub at
   ≈103 mm square, 0.4 mm, array plane **horizontal**, cells on the upper face; the hub board of
   record (`tracker/hardware/hub_board_v9.kicad_pcb`) exists but its 32 model assignments point at
   `${KICAD9_3DMODEL_DIR}/…step` — `kicad-packages3d` is not installed and must not be — so a hub+wings
   render would today show a bare hub plate beside a finished wing. (Fix is the parallel
   `feat/3d-models-hub` worker's scope; **not touched here**.)
5. **The joint itself may not be solder.** ADR-049's open items include "whether the wing should be
   jettisonable (under study, see the release mechanism analysis)" — if the wing is released rather
   than soldered, the mating feature is a release mechanism whose geometry does not exist in any
   record, and the wing tab drawn in copper is a placeholder for it.
6. **No cell-tab geometry** (`TODO(unverified)`, §2 above) — so even a single wing cannot be shown
   *bonded* to its own lands, only placed on them.

**What a future assembly render needs, precisely:** (a) the frozen wing plane + per-wing tilt for
wings 1–4 from the resolving worker (replacing ADR-049 §5 item 6 / socket spec §1 / ADR-046 §4.1 with
one value); (b) the socket's mating geometry — slot width/depth and tolerance, or the no-slot
plain-pad fallback (ADR-048 items 3/6, socket spec §2.1 Option A/B); (c) the ADR-055 D6 standoff
height, chosen against `3.363 Z`; (d) a renderable hub (committed models, not
`${KICAD9_3DMODEL_DIR}`); (e) a decision on jettison vs solder at the tab. Only then is an assembly
transform derivable rather than invented.

*Report scope note: this card owns the WING only. Hub board, schematic and master netlist were not
touched.*
