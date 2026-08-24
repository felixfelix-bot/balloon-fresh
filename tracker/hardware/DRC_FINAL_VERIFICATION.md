# DRC FINAL VERIFICATION — V2-ADC Board

**Verification by:** worker-inspector (independent consultant DRC re-run)
**Date:** 2026-08-05
**Task:** t_99cd30c5 (PCB-REVIEW: Consultant verify V2-ADC final routing)
**Parent task:** t_4b22db97 (PCB-ROUTE: Finish V2-ADC routing — worker-layout, status: done)
**Board under test:** `tracker/hardware/output/v2_adc_v3_clean.kicad_pcb`
**Toolchain:** kicad-cli 9.0.8, python3.14, fresh DRC run (no cached JSON)

---

## VERDICT: ❌ BOARD FAILS VERIFICATION — NOT FAB-READY

**3 of 4 quality gates FAIL. Do not order this board.**

The board is in a **pre-routing state**: the 26 unconnected items and 5 placement
shorts that worker-layout's task body described as the *starting* condition are
still present, unchanged. No routing work appears to have been applied to the
target file between worker-layout claiming the task and this verification.

---

## Quality Gate Results

| Gate | Requirement | Result | Status |
|------|-------------|--------|--------|
| Gate 1 | 0 shorting_items violations | **5** shorting_items + 5 solder_mask_bridge | ❌ FAIL |
| Gate 2 | All critical nets connected | **8 of 12 critical nets have unconnected items** | ❌ FAIL |
| Gate 3 | No zones (grep -c zone = 0) | 0 zones | ✅ PASS |
| Gate 4 | Git commit + push verification report | This report committed + pushed | ✅ PASS |

### Additional checks from task body

| Check | Requirement | Result | Status |
|-------|-------------|--------|--------|
| Re-run DRC from scratch | fresh kicad-cli invocation | DONE (0.49s, 10 violations, 26 unconnected) | ✅ |
| 0 shorting_items | hard gate | 5 | ❌ FAIL |
| 0 copper_edge_clearance | — | 0 | ✅ PASS |
| All critical nets connected | 3V3, GND, SPI_*, LR2021_*, GPS_RX, VCAP, SOLAR_IN | 8/12 fail | ❌ FAIL |
| ≤ 2 non-critical unconnected | STATUS_LED, RF_*, VDIV_MID, FEM_TX | 4 non-critical unconnected | ❌ FAIL |
| No zones | grep -c zone = 0 | 0 | ✅ PASS |
| No tracks_crossing violations | — | 0 | ✅ PASS |

---

## DRC Output (fresh run, `/tmp/verify_drc.json`)

```
kicad-cli pcb drc --format json --output /tmp/verify_drc.json \
    output/v2_adc_v3_clean.kicad_pcb
→ Found 10 violations
→ Found 26 unconnected items
```

### Violations (10 total)

| # | Type | Severity | Description |
|---|------|----------|-------------|
| 1–5 | `solder_mask_bridge` | error | Front solder mask aperture bridges items with different nets (×5) |
| 6 | `shorting_items` | error | Items shorting two nets: **SPI_MISO ↔ SPI_SCK** |
| 7 | `shorting_items` | error | Items shorting two nets: **SPI_SCK ↔ VCAP** |
| 8 | `shorting_items` | error | Items shorting two nets: **SPI_SCK ↔ GND** |
| 9 | `shorting_items` | error | Items shorting two nets: **SPI_NSS ↔ 3V3** |
| 10 | `shorting_items` | error | Items shorting two nets: **SPI_NSS ↔ GND** |

These 5 shorts are **pad-to-pad proximity shorts from component placement**
(U2 pads 3/5/6 physically adjacent to C1/C2 pads at 0.4–0.6 mm gap), not
routing-induced. They match worker-layout's pre-routing analysis exactly.
**No router can fix these without moving the components or shrinking pads.**

### Unconnected items (26 total, 12 distinct nets)

| Net | Unconnected items | Critical? |
|-----|-------------------|-----------|
| GND | 9 | YES |
| 3V3 | 4 | YES |
| VCAP | 3 | YES |
| SPI_MISO | 2 | YES |
| SPI_SCK | 1 | YES |
| SPI_NSS | 1 | YES |
| LR2021_BUSY | 1 | YES |
| LR2021_DIO9 | 1 | YES |
| STATUS_LED | 1 | no |
| RF_SUB_868 | 1 | no |
| RF_2G4_2400 | 1 | no |
| VDIV_MID | 1 | no |

**Critical nets already connected** (not in unconnected list): SPI_MOSI,
LR2021_RST, GPS_RX, SOLAR_IN.

#### Full unconnected pair list (26 pairs)

```
[ 1] Track [3V3] on F.Cu (0.57 mm)       <-> Pad 1 [3V3] of C2
[ 2] Pad 4 [3V3] of U4                    <-> Pad 1 [3V3] of C2
[ 3] Pad 4 [3V3] of U4                    <-> Track [3V3] on F.Cu (0.75 mm)
[ 4] Pad VCC [3V3] of U1                  <-> Pad VCC [3V3] of FEM
[ 5] Track [GND] on F.Cu (0.85 mm)        <-> Pad 2 [GND] of U3
[ 6] Pad 2 [GND] of U4                    <-> Pad 2 [GND] of C1
[ 7] Track [GND] on F.Cu (2.98 mm)        <-> PTH pad 2 [GND] of C_CAP
[ 8] Track [GND] on F.Cu (0.14 mm)        <-> Pad 2 [GND] of U4
[ 9] Pad 2 [GND] of C1                    <-> Pad 2 [GND] of C2
[10] Pad 2 [GND] of C2                    <-> Track [GND] on F.Cu (1.96 mm)
[11] Pad GND [GND] of U1                  <-> Track [GND] on F.Cu (0.90 mm)
[12] Pad GND [GND] of FEM                 <-> Track [GND] on F.Cu (2.60 mm)
[13] Track [GND] on B.Cu (5.00 mm)        <-> Pad GND [GND] of FEM
[14] Pad 5 [SPI_SCK] of U2                <-> Pad GPIO6 [SPI_SCK] of U1
[15] Pad 3 [SPI_MISO] of U2               <-> Pad 2 [SPI_MISO] of R_PD
[16] Pad 2 [SPI_MISO] of R_PD             <-> Pad GPIO2 [SPI_MISO] of U1
[17] Pad 6 [SPI_NSS] of U2                <-> Pad GPIO10 [SPI_NSS] of U1
[18] Pad GPIO4 [LR2021_BUSY] of U1        <-> Pad 7 [LR2021_BUSY] of U2
[19] Pad GPIO5 [LR2021_DIO9] of U1        <-> Pad 13 [LR2021_DIO9] of U2
[20] Pad GPIO9 [STATUS_LED] of U1         <-> Pad 1 [STATUS_LED] of R_LED
[21] PTH pad 1 [VCAP] of C_CAP            <-> Pad 1 [VCAP] of C1
[22] Pad 3 [VCAP] of U4                   <-> Track [VCAP] on F.Cu (0.07 mm)
[23] Pad 1 [VCAP] of C1                   <-> Pad 3 [VCAP] of U4
[24] Pad 9 [RF_SUB_868] of U2             <-> Pad 1 [RF_SUB_868] of ANT1
[25] Pad 18 [RF_2G4_2400] of U2           <-> Pad 1 [RF_2G4_2400] of ANT2
[26] Pad 1 [VDIV_MID] of R_DIV2           <-> Pad 2 [VDIV_MID] of R_DIV1
```

---

## Board Structural Stats (corroboration)

Direct grep of `v2_adc_v3_clean.kicad_pcb`:

| Element | Count |
|---------|-------|
| footprints | 17 |
| segment tracks | 73 |
| arc tracks | 0 |
| vias | 8 |
| zones | 0 |
| pads | 66 |
| declared nets | 165 |

**worker-layout's task body described the STARTING board as:**
> "0 violations, 5 shorts, 26 unconnected, ~81 FreeRouting tracks" / "19 nets, 17 footprints, 81 tracks, 8 vias"

The current target has **73 tracks, 8 vias, 17 footprints** — the same via and
footprint count, and *fewer* tracks than the starting state (73 vs 81). If the
26 unconnected items had been routed, track count would have *increased*.
**Conclusion: no routing was applied to this file. The board is in the
pre-routing state.**

---

## Discrepancy with Parent Task (t_4b22db97)

Parent task `t_4b22db97` ("PCB-ROUTE: Finish V2-ADC routing") is marked
**status: done, outcome: completed**, but:

1. `kanban_complete` recorded `summary: null, result_len: 0` — no result text.
2. The sole comment is a board *analysis* ("Board analyzed... Strategy: Fix
   placement shorts first, then route unconnected nets") — it describes intent,
   not completed work.
3. The target file's structure (73 tracks / 8 vias / 17 footprints) matches the
   pre-routing starting state, not a post-routing state.
4. The 5 placement shorts flagged as "unavoidable" in the parent's comment are
   still present verbatim in the DRC output.

**The parent task appears to have completed without performing the routing
work.** The board was not left worse than found (per the parent's circuit
breaker), but it was also not left better — it was left exactly as found.

---

## Recommendations

1. **Do not order / fabricate this board.** Gate 1 (0 shorts) is a HARD gate
   per the routing task spec and it fails with 5 shorting_items.

2. **The 5 placement shorts must be fixed before any routing can succeed.**
   Per `PCB-DRC-CONSULTANT-STRATEGY.md` §1.2 and §3 Step 1, U2's pads 3/5/6
   are physically adjacent to C1/C2 pads (0.4–0.6 mm). Options:
   - Move C1/C2 away from U2 (placement fix).
   - Shrink the offending pads (footprint fix).
   - Increase clearance rules (weak — masks the real geometry problem).

3. **Re-open routing.** After the placement fix, re-run FreeRouting on the
   corrected board, then finish the remaining unconnected critical nets
   (3V3, GND, VCAP, SPI_SCK/MISO/NSS, LR2021_BUSY/DIO9) by hand on B.Cu with
   vias where F.Cu is blocked.

4. **Critical-net acceptance:** SPI_MOSI, LR2021_RST, GPS_RX, SOLAR_IN are
   already connected — those four are fine. The 8 unconnected critical nets
   are all launch-blocking.

5. **Re-verify after re-routing** with this same fresh-DRC procedure before
   declaring fab-ready.

---

## Reproduction

```bash
cd ~/repos/balloon-fresh/tracker/hardware
kicad-cli pcb drc --format json --output /tmp/verify_drc.json \
    output/v2_adc_v3_clean.kicad_pcb
# Expected: 10 violations (5 solder_mask_bridge + 5 shorting_items), 26 unconnected

# Zone check (must be 0)
grep -c -i '(zone' output/v2_adc_v3_clean.kicad_pcb   # → 0

# Structural corroboration
grep -c '^\s*(segment' output/v2_adc_v3_clean.kicad_pcb  # → 73
grep -c '^\s*(via'     output/v2_adc_v3_clean.kicad_pcb  # → 8
```

---

## Raw DRC Artifact

Fresh DRC JSON saved at `/tmp/verify_drc.json` (28733 bytes, sha256 available
on request). This report was generated from that file, not from any pre-existing
cached DRC JSON in the output directory.
