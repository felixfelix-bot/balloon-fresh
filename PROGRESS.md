# PROGRESS — v8j MS5611 board → passing order gate

Branch: `pr/v8j-ms5611-reroute` (worktree `/home/c03rad0r/worktrees/v8j-ms5611-reroute`)
Gate: `~/.hermes/profiles/manager/scripts/fleet/pcb_order_gate.py` — UNCHANGED, authority.

## RESULT

**ORDER GATE: PASS** — exit 0, errors=0, unconnected=0, warnings=14 (non-blocking),
kicad 9.0.8. `--verify` against the recorded artifact pair: **VERIFIED**.
board_sha256 `f6f40338e312c65202659d49dab40600415416b6a04f173e6f72863df9228422`
fab_sha256  `937e4eda1e9cd8b47f4920a68a663e09b6bdaf4340c3362368f500e0715ec644`

## Failure-class counts, BEFORE → AFTER (clusterer `v8j_drc_cluster.py`)

| cluster | before | after | how it was cleared |
|---|---|---|---|
| `clearance` | 138 | **0** | **zone refill** — the 138 were all stale In1(GND)/In2(+3V3) fill polygons (actual 0.2005 vs the frozen zone clearance 0.220). `ZONE_FILLER.Fill()` regenerates them. |
| `drill_out_of_range` | 12 | **0** | the salvaged `v8j_krt_ms5611.kicad_pro` carried a *stricter* board setup than the PASSING v8i (`min_through_hole_diameter` 0.3 vs 0.2, `min_hole_clearance` 0.25 vs 0.2). Restored the frozen v8i rule files. |
| `hole_clearance` | 9 | **0** | same rule restore + refill (NPTH MNT pads vs planes). |
| `unconnected_items` | 11 | **0** | U5 pad→net map corrected to the real MS5611 pinout, then KRT routed GND/EN/I2C_SDA/I2C_SCL/+3V3 (68/68 pads). |
| `track_dangling` | 4 | 3 | KRT re-routed the truncated I2C/EN stubs; 3 residual cosmetic stubs remain (warning). |
| `via_dangling` | 1 | 1 | residual cosmetic (warning). |
| `via_diameter` | 0 | **0** (5 transient) | KRT emitted 5 × 0.55 mm vias (below our frozen 0.60); legalised 0.55→0.60/0.30 + refill. |
| `silk_overlap` | 3 | 3 | pre-existing v8i silk (the PASSING v8i carries 2; non-blocking warnings). |
| `silk_over_copper` | 3 | 3 | pre-existing v8i silk (non-blocking). |
| `silk_edge_clearance` | 3 | 3 | pre-existing v8i silk (non-blocking). |
| `lib_footprint_mismatch` | 1 | 1 | warning only (F.Cu footprint vs library copy); non-blocking. |

Gate-record before: `status=FAIL errors=170 warnings=15 unconnected=11`
(board_sha256 `cb6e61094455…`, fab `ae1bae58dee7…`).
Gate-record after: `status=PASS errors=0 warnings=14 unconnected=0`.

One line per cluster: clearance 138→0, drill_out_of_range 12→0, hole_clearance 9→0,
unconnected 11→0, track_dangling 4→3 (warn), via_dangling 1→1 (warn),
via_diameter 5 transient→0, silk×3 3/3/3→3/3/3 (warn, inherited),
lib_footprint_mismatch 1→1 (warn).

## Root cause (CONFIRMED, refined from the handover hypothesis)

The handover hypothesised "stale placement/geometry left behind". Confirmed and
sharpened — there were **three independent defects**, none of which was a
clearance/geometry regression in the v8i routing (the v8i routing is intact and
was proven sound: refilling it alone dropped 159 of 170 errors):

1. **Stale plane fills** (138 clearance + 9 hole_clearance). U5's swap and the
   removal of its local copper were done without refilling In1/In2, so the fills
   still hugged the OLD geometry.
2. **Wrong project rule file** (12 drill + the hole_clearance floor). The
   salvaged `.kicad_pro` was KRT's output, not the frozen sibling the board must
   be judged against; it raised `min_through_hole_diameter` 0.2→0.3 and
   `min_hole_clearance` 0.2→0.25. There was also **no `v8j_krt_ms5611.kicad_dru`**
   sibling at all. Copying the frozen v8i pair fixes both.
3. **U5 was never re-routed** (11 unconnected + 4 track_dangling + 1 via_dangling)
   and, worse, carried the **BMP280 pad→net assignment** on the MS5611 footprint
   (pad3/pad4 → SDA/SCL). Also the EN run to J1.3 had been deleted because the
   wider MS5611 courtyard crossed it.

## Pipeline used (deterministic, zero inference)

`tracker/hardware/output/v8j_drc_cluster.py`   diagnose
`tracker/hardware/output/v8j_clearance_probe.py` classify violation item-pairs
`tracker/hardware/output/v8j_refill_test.py`   prove the refill hypothesis
`tracker/hardware/output/v8j_u5_netfix.py`     set the real MS5611 pad→net map + frozen siblings
`tracker/hardware/route_v8j.sh`                KRT `--nets GND EN I2C_SDA I2C_SCL +3V3 --keep-input-copper`
`tracker/hardware/output/v8j_refill_final.py`  refill + DRC
`tracker/hardware/output/v8j_via_legalise.py`  0.55→0.60 via legalise + refill
`tracker/hardware/export_v8j_gerbers.sh`       JLCPCB package (v8i layer set)
`~/.hermes/profiles/manager/scripts/fleet/pcb_order_gate.py`  the gate (unchanged)

## MILESTONE LOG
- [x] clusterer run — 174 viol / 11 unconn, classes captured.
- [x] refill hypothesis proven — 170 errors → 11 (only unconnected left).
- [x] MS5611 pinout pinned from the official KiCad symbol; `build_v8j.py` pin-4 bug found.
- [x] U5 nets fixed + KRT routed → 0 unconnected, 5 via_diameter errors left.
- [x] vias legalised + refill → 0 errors, 0 unconnected.
- [x] gerbers exported, gate **PASS**, record `--verify` **VERIFIED**.
- [x] pushed to github + ngit + origin, refs verified.
