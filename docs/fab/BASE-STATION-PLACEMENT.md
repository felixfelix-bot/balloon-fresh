# BASE-STATION PCBA v1 — PLACED at 55×40 mm

**Date:** 2026-10-14 · **Status:** ✅ **44/44 placed, geometry verified.** Routing in progress.
No KiCad schematic editor file yet; placement is generated from the verified netlist.

Third concrete step on the largest remaining deliverable (spec `c3ccedec` → netlist `01d97c2b` →
placement `6998e06e`).

## Result

| | |
|---|---|
| components placed | **44 / 44** |
| skipped | **0** |
| overflow | **0** |
| outline | **55 × 40 mm** |
| part (gate-rect) area | **913.8 mm²** |
| utilisation | **41.5 %** at 55×40 · 33.8 % at 60×45 · 26.1 % at 70×50 |

## Geometry verified, not assumed

`verify_placement_geometry.py` grades placement with the **packer's own measure** — the pad-box
∪ courtyard rectangle from `hubgen.rel_rect`, not `GetBoundingBox`:

- **all 44 rectangles inside the outline** with the 1 mm edge margin ✅
- **ZERO gate-rectangle overlaps** at the packer's 0.5 mm clearance ✅

**55×40 is the tight option**; 60×45 gives 34 % and real routing room. **Decision deferred to
routing results** — if the 55×40 route struggles, 60×45 is the fallback, and neither is a
geometric commitment yet.

## Three real defects found and fixed

### (1) My own netlist format was wrong — and failed SILENTLY

The hub's proven reader does `fp = re.search(r'\(footprint "([^"]*)"\)', b)` with a `""` fallback.
**A netlist that emits the footprint only as `(field (name "Footprint") …)` yields an EMPTY
`lib_id`** — so **every part silently became "unplaceable": 44 on the netlist, 44 "unplaceable",
0 placed, no error.**

**Fixed** by emitting a **direct `(footprint "…")` token** as well. *Same silent-drop class as the
`kicad-cli` flags that dropped `U1` and `J_VCC` from the CPL.*

### (2) Seven footprint names did not resolve

Resolved each against **what is actually installed** — no invented replacement:

| ref | was | now (verified on disk) |
|---|---|---|
| `J_PWR` | `Connector_TerminalBlock:TerminalBlock_bornier-2_P5.08mm` | `TerminalBlock_4Ucon:TerminalBlock_4Ucon_1x02_P3.50mm_Vertical` |
| `L1` | `Inductor_SMD:L_4x4mm_H3mm` | `Inductor_SMD:L_Bourns-SRN4018` |
| `FLT_433_A/B` | `Filter:Filter_1109W98` | `Filter:Filter_SAW-6_3.8x3.8mm` |
| `TEE1/TEE2` | `Connector:Conn_01x03_Male` | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` |

### (3) The RP2040 footprint exists ONLY in a KiCad DEMO library

**Measured:** `/usr/share/kicad/footprints/MCU_RaspberryPi_and_Boards.pretty` **does not exist**;
the RP2040 QFN-56 ships only in `/usr/share/kicad/demos/tiny_tapeout/tinytapeout-kicad-libs/`,
**which a KiCad upgrade may remove.**

**Vendored** into `tracker/hardware/base_station/library.pretty` with the **source path and sha256
`83bb951b1fe64f1d82e57e6b4cc49b62f91c036a2e8bba6e8a6c1cbf74839808` recorded in the file**, so the
build is reproducible from a library we control.

## pcbnew import-order trap (recorded for reuse)

Importing the hub builder **via `importlib`** leaves `pcbnew.FootprintLoad`'s plugin as `None`:

```
AttributeError: 'NoneType' object has no attribute 'FootprintLoad'
```

**The same call works in a bare interpreter on the same library path** — so the fault is the
**import order**, not the library. Fix: import `pcbnew` and load footprints **before** pulling in
the hub builder as a module.

## I corrected my own verifier — sixth instance of the campaign's recurring lesson

The first version reported **326 overlapping pairs and 250 % area** — **both numbers were my bug.**
I used `GetBoundingBox()`, which **includes silkscreen and reference text**, where the packer clears
the gate's own pad-box-union-courtyard rectangle. Re-measured with the real measure: **zero
overlaps.**

**Also: the earlier "ALL SEATED" readings at 50×40 … 100×80 were meaningless** — the loader had
placed **zero** parts, so nothing could overflow. **A check that cannot fail proves nothing.**

## Files

| file | role |
|---|---|
| `base_station/base_station_v1.net` | 44 comps, 44 nets — verified 25/25 against the spec |
| `base_station/place_base_station.py` | loads the netlist into a scaffolded, packed board |
| `base_station/verify_placement_geometry.py` | grades with the packer's own rectangle |
| `base_station/size_base_station.py` | part-extent census + outline trials |
| `base_station/vendor_rp2040_footprint.py` | vendors the demo-library footprint with provenance |
| `base_station/library.pretty/RP2040-QFN-56.kicad_mod` | the vendored footprint |
| `base_station/base_station_v1_placed.kicad_pcb` | the placed board |

## Reproduce

```
cd tracker/hardware/base_station
python3 gen_base_station_netlist.py            # 44 comps / 44 nets
python3 test_netlist_implements_spec.py        # 25/25
~/venvs/kicad/bin/python place_base_station.py --outline 55x40
~/venvs/kicad/bin/python verify_placement_geometry.py 55x40
```

## Next

**Route → DRC → classify → refill → export → STEP.** The hub's chain is proven and reusable, and
the **`--board-edge-clearance 0.6` lesson is applied from the start** so this board does not inherit
the hub's edge-track defect.
