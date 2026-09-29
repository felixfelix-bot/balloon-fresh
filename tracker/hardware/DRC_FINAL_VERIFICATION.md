# DRC FINAL VERIFICATION — V2-ADC Board

**Verification by:** worker-inspector (independent consultant DRC re-run, run 2)
**Date of this re-verification:** 2026-09-29
**Prior verification:** 2026-08-05 (same verdict; commit `1ffe97f`)
**Task:** t_99cd30c5 (PCB-REVIEW: Consultant verify V2-ADC final routing — independent DRC check)
**Parent task:** t_4b22db97 (PCB-ROUTE: Finish V2-ADC routing — worker-layout; now **archived**, terminated by the fleet loop guard)
**Board under test:** `tracker/hardware/output/v2_adc_v3_clean.kicad_pcb`
**Board sha256:** `f96d4a68c240f7ae1e1f6879f29573c01e1597b43341626722e8f4e05d44c148`
**Board git blob:** `0b280b1f356fc9a14b7d34c4d1f7822f632c39d4`
**Toolchain:** kicad-cli 9.0.8, Python 3.11 (analysis parses artefacts only, no pcbnew needed)
**Published:** `github/autonomous/mesh-baseline` (subject `verify(inspection): V2-ADC DRC re-verification 2026-09-29 — still FAILS, board unchanged since 2026-08-05`; find it with `git log -- tracker/hardware/DRC_FINAL_VERIFICATION.md`)

---

## VERDICT: ❌ BOARD FAILS VERIFICATION — NOT FAB-READY (unchanged)

**Gate 1 and Gate 2 FAIL. Gate 3 PASSES. Do not order this board.**

Re-running the complete verification from scratch on 2026-09-29 produces the
**same** result as the 2026-08-05 verification, down to the individual
violation and unconnected-item descriptions. The board file has not changed:

| Evidence of "no change" | Value |
|---|---|
| sha256 of board in the working tree | `f96d4a68…44c148` |
| sha256 of the same file in all 43 worktrees/repos on this host | `f96d4a68…44c148` (all identical) |
| git blob at `github/autonomous/mesh-baseline`, at `HEAD`, in the worktree | `0b280b1f…39d4` (all identical) |
| commits that ever touched this file (any ref) | exactly one — `5b45bf9` (2026-08-05 20:23) |
| `git diff HEAD -- <board>` | empty |
| violations + unconnected set vs the archived 2026-08-05 raw DRC | identical |

**Conclusion:** no routing work has landed on the target board in the 55 days
since the last FAIL. This card was re-dispatched by routine urgency triage
(`manager`, 2026-09-29), not by new routing output. The routing lane is empty:
the parent card is archived and its later runs died as "dead worker pid"
(reclaim strikes ×2, then `fleet_loop_guard`).

---

## Quality Gate Results (card t_99cd30c5)

| Gate | Requirement | Result | Status |
|------|-------------|--------|--------|
| Gate 1 | 0 `shorting_items` violations | **5** | ❌ FAIL |
| Gate 2 | All critical nets connected | **8 of 12 critical nets unconnected** | ❌ FAIL |
| Gate 3 | No zones (`grep -c zone` = 0) | 0 zones | ✅ PASS |
| Gate 4 | Git commit + push verification report | report + raw DRC JSON + summary JSON + inspection script committed and pushed to `github/autonomous/mesh-baseline` | ✅ PASS |

### Additional checks from the card body

| Check | Requirement | Result | Status |
|-------|-------------|--------|--------|
| Re-run DRC from scratch | fresh `kicad-cli` invocation | DONE — 4.2 s, 10 violations, 26 unconnected | ✅ |
| 0 `copper_edge_clearance` | — | 0 | ✅ PASS |
| 0 `tracks_crossing` | — | 0 | ✅ PASS |
| All critical nets connected | see list below | 8/12 fail | ❌ FAIL |
| ≤ 2 non-critical unconnected | — | **4** non-critical nets unconnected | ❌ FAIL |
| No zones | grep -c zone = 0 | 0 | ✅ PASS |
| DRC reproducible | two consecutive fresh runs | identical violation + unconnected sets | ✅ |

Critical-net list per `docs/coordination/PCB-DRC-CONSULTANT-STRATEGY.md` §Q5
(and parent card Gate 2): `3V3, GND, SPI_SCK, SPI_MOSI, SPI_MISO, SPI_NSS,
LR2021_RST, LR2021_BUSY, LR2021_DIO9, GPS_RX, VCAP, SOLAR_IN` — 12 nets.

- **Connected (4):** `SPI_MOSI`, `LR2021_RST`, `GPS_RX`, `SOLAR_IN`
- **Unconnected (8):** `3V3`, `GND`, `SPI_SCK`, `SPI_MISO`, `SPI_NSS`,
  `VCAP`, `LR2021_BUSY`, `LR2021_DIO9`
- **Non-critical unconnected (4 distinct nets, gate allows ≤ 2):**
  `STATUS_LED`, `RF_SUB_868`, `RF_2G4_2400`, `VDIV_MID`

---

## DRC output (fresh run, 2026-09-29)

```
$ kicad-cli pcb drc --format json --output /tmp/verify_drc.json \
      output/v2_adc_v3_clean.kicad_pcb
Found 10 violations
Found 26 unconnected items
Saved DRC Report to /tmp/verify_drc.json
```

Design rules are taken from the project file next to the board
(`output/v2_adc_v3_clean.kicad_pro`): `min_clearance` 0.15 mm,
`min_copper_edge_clearance` 0.5 mm, `solder_mask_to_copper_clearance` 0.05 mm.
`included_severities` = error + warning; all 10 reported violations are
**errors** and there are 0 warnings.

### Violations — 10 total (all severity `error`)

| # | Type | Description |
|---|------|-------------|
| 1 | `shorting_items` | nets **SPI_MISO** and **SPI_SCK** |
| 2 | `shorting_items` | nets **SPI_SCK** and **VCAP** |
| 3 | `shorting_items` | nets **SPI_SCK** and **GND** |
| 4 | `shorting_items` | nets **SPI_NSS** and **3V3** |
| 5 | `shorting_items` | nets **SPI_NSS** and **GND** |
| 6–10 | `solder_mask_bridge` | front mask aperture bridges the same 5 pad pairs |

Zero `copper_edge_clearance`, zero `tracks_crossing`, zero `clearance`,
zero `courtyard_overlap`, zero `unconnected_items`-type violations beyond the
26 listed below.

### The 5 shorts are physical pad-copper overlaps (placement, not routing)

Every item in every violation is a **pad**; no track, via or zone participates.
Resolving pad positions from the board's s-expression gives the following
axis-aligned rectangle geometry (all pads are `smd rect`, rotation 0°):

| Pair | Nets | pad sizes | centre-to-centre | copper **overlap area** |
|------|------|-----------|------------------|--------------------------|
| U2.3 ↔ U1.GPIO6 | SPI_MISO ↔ SPI_SCK | 1.2×0.8 / 1.0×0.6 | 0.640 mm | **0.14 mm²** |
| U2.5 ↔ C1.1 | SPI_SCK ↔ VCAP | 1.2×0.8 / 0.7×0.6 | 0.600 mm | **0.21 mm²** |
| U2.5 ↔ C1.2 | SPI_SCK ↔ GND | 1.2×0.8 / 0.7×0.6 | 0.400 mm | **0.33 mm²** |
| U2.6 ↔ C2.1 | SPI_NSS ↔ 3V3 | 1.2×0.8 / 0.7×0.6 | 0.600 mm | **0.21 mm²** |
| U2.6 ↔ C2.2 | SPI_NSS ↔ GND | 1.2×0.8 / 0.7×0.6 | 0.400 mm | **0.33 mm²** |

The pads are not merely closer than the 0.15 mm rule — they physically
overlap, so the copper is genuinely shorted and the front solder-mask
apertures merge. **No router can repair this.** It requires a placement or
footprint change:

- relocate C1 and C2 away from U2's left pad column (`x = 10.1`, pads 1–9 at
  2 mm pitch, `y = 12…28`). C1 and C2 are still at their **original**
  footprint origins `(10, 20)` and `(10, 22)`, so to clear U2's 1.2 mm-wide
  pads with the 0.7 mm-wide cap pads and ≥ 0.15 mm copper clearance the cap
  centres must move to roughly `x ≤ 9.2` or `x ≥ 11.1`, or
- move/shrink U1's `GPIO6` pad (U1 at `(12,12)`, pad `(10.5, 15.5)`, 1.0×0.6)
  relative to U2's pad 3 at `(10.1, 16.0)`, or reduce U2's 1.2 mm pad width.

### Unconnected items — 26 total, 12 distinct nets

| Net | Items | Critical |
|-----|-------|----------|
| GND | 9 | yes |
| 3V3 | 4 | yes |
| VCAP | 3 | yes |
| SPI_MISO | 2 | yes |
| SPI_SCK | 1 | yes |
| SPI_NSS | 1 | yes |
| LR2021_BUSY | 1 | yes |
| LR2021_DIO9 | 1 | yes |
| STATUS_LED | 1 | no |
| VDIV_MID | 1 | no |
| RF_SUB_868 | 1 | no |
| RF_2G4_2400 | 1 | no |

Full pair list (verbatim item descriptions from the DRC JSON):

```
[ 1] Track [3V3] on F.Cu, length 0.5660 mm  <->  Pad 1 [3V3] of C2 on F.Cu
[ 2] Pad 4 [3V3] of U4 on F.Cu               <->  Pad 1 [3V3] of C2 on F.Cu
[ 3] Pad 4 [3V3] of U4 on F.Cu               <->  Track [3V3] on F.Cu, length 0.7509 mm
[ 4] Pad VCC [3V3] of U1 on F.Cu             <->  Pad VCC [3V3] of FEM on F.Cu
[ 5] Track [GND] on F.Cu, length 0.8519 mm   <->  Pad 2 [GND] of U3 on F.Cu
[ 6] Pad 2 [GND] of U4 on F.Cu               <->  Pad 2 [GND] of C1 on F.Cu
[ 7] Track [GND] on F.Cu, length 2.9796 mm   <->  PTH pad 2 [GND] of C_CAP
[ 8] Track [GND] on F.Cu, length 0.1414 mm   <->  Pad 2 [GND] of U4 on F.Cu
[ 9] Pad 2 [GND] of C1 on F.Cu               <->  Pad 2 [GND] of C2 on F.Cu
[10] Pad 2 [GND] of C2 on F.Cu               <->  Track [GND] on F.Cu, length 1.9617 mm
[11] Pad GND [GND] of U1 on F.Cu             <->  Track [GND] on F.Cu, length 0.9000 mm
[12] Pad GND [GND] of FEM on F.Cu            <->  Track [GND] on F.Cu, length 10.0000 mm
[13] Track [GND] on B.Cu, length 5.0000 mm   <->  Pad GND [GND] of FEM on F.Cu
[14] Pad 5 [SPI_SCK] of U2 on F.Cu           <->  Pad GPIO6 [SPI_SCK] of U1 on F.Cu
[15] Pad 3 [SPI_MISO] of U2 on F.Cu          <->  Pad 2 [SPI_MISO] of R_PD on F.Cu
[16] Pad 2 [SPI_MISO] of R_PD on F.Cu        <->  Pad GPIO2 [SPI_MISO] of U1 on F.Cu
[17] Pad 6 [SPI_NSS] of U2 on F.Cu           <->  Pad GPIO10 [SPI_NSS] of U1 on F.Cu
[18] Pad GPIO4 [LR2021_BUSY] of U1 on F.Cu   <->  Pad 7 [LR2021_BUSY] of U2 on F.Cu
[19] Pad GPIO5 [LR2021_DIO9] of U1 on F.Cu   <->  Pad 13 [LR2021_DIO9] of U2 on F.Cu
[20] Pad GPIO9 [STATUS_LED] of U1 on F.Cu    <->  Pad 1 [STATUS_LED] of R_LED on F.Cu
[21] PTH pad 1 [VCAP] of C_CAP               <->  Pad 1 [VCAP] of C1 on F.Cu
[22] Pad 3 [VCAP] of U4 on F.Cu              <->  Track [VCAP] on F.Cu, length 0.0707 mm
[23] Pad 1 [VCAP] of C1 on F.Cu              <->  Pad 3 [VCAP] of U4 on F.Cu
[24] Pad 9 [RF_SUB_868] of U2 on F.Cu        <->  Pad 1 [RF_SUB_868] of ANT1 on F.Cu
[25] Pad 18 [RF_2G4_2400] of U2 on F.Cu      <->  Pad 1 [RF_2G4_2400] of ANT2 on F.Cu
[26] Track [VDIV_MID] on F.Cu, length 0.8837 mm <-> Pad 2 [VDIV_MID] of R_DIV1 on F.Cu
```

---

## Board structural stats (parsed from the s-expression)

| Element | Count |
|---------|-------|
| footprints | 17 |
| segments (tracks) | 73 |
| arcs | 0 |
| vias | 8 |
| zones | **0** |
| pads | 65 |
| `net` declarations | 165 |
| copper layers | 2 (`F.Cu`, `B.Cu`) |
| file size | 43 022 bytes |

The parent card's body described the **starting** board as "0 violations,
5 shorts, 26 unconnected, ~81 FreeRouting tracks". The current artefact has
73 tracks / 8 vias / 17 footprints — i.e. the same or fewer tracks, and the
same 5 shorts and same 26 unconnected items. Routing a net *adds* copper; this
board has none added.

---

## Claim-vs-artefact audit (parent card t_4b22db97)

worker-layout's comment thread on the parent card claims work that is **not
present in the board artefact**:

| Comment claim (2026-08-05) | Artefact reality |
|---|---|
| "Moved C1@(10,20)→(12,20) and C2@(10,22)→(12,22)", "Result: 10 violations → 4" | C1 footprint still at `(10, 20)`, C2 still at `(10, 22)`; violations still 10 |
| "C2@(14,24) fixed the LR2021_BUSY shorts. Down to 2 violations" | 5 shorts remain, incl. both U2.6/C2 pairs |
| "Added GND B.Cu track for U3.2. Unconnected: 26 → 25" | 26 unconnected remain; no B.Cu track reaches U3.2 |
| "Routed GND U3.2 (25→24) — SUCCESS!" | U3.2 is still unconnected (item [5]) |
| "Reverted to step1 as working baseline (4 violations, 26 unconnected)" | No commit after `5b45bf9` (2026-08-05 16:53 CEST) touches the board, and the working-tree file has been byte-identical to that blob ever since — the claimed edits (comments timestamped 17:02–17:41 CEST, i.e. *after* the commit) were never written to the canonical path |

The parent's `kanban_complete` recorded `summary: null, result_len: 0`, then
later runs died as dead worker pids and it was archived by the loop guard. The
board was never left worse than found, but it was also never improved.

**Hash-discrepancy note:** the previous handoff comment on this card cited the
verification commit as `6a11077`. No such object exists in this repository
(`git cat-file -t 6a11077` → *Not a valid object name*). The real report commit
from 2026-08-05 is **`1ffe97f`** ("verify(inspection): V2-ADC DRC final
verification — FAILS 3/4 gates, not fab-ready"), which is present on
`github/autonomous/mesh-baseline` and on the branch lineage of this file. The
substantive finding was correct; the cited hash was not.

---

## Existing fix lane (do not duplicate)

The fix work is already carded; this verification does not create new cards:

- `t_44f72333` — **ready** — worker-balloon — "PCB-FIX: FreeRouting-only run on
  V2-ADC with fixed pad placement" (`t_6d332912` → `t_44f72333`)
- `t_acbe0536` — **blocked** — worker-layout — "PCB-FIX: Independent DRC
  verification of fixed V2-ADC board" (`t_44f72333` → `t_acbe0536` → `t_cd67fdda`)
- `t_9c0e1e8f` — **running** — worker-layout — "PCB-4LAYER-REVIEW: kimi-k3
  consultant verify 4-layer board DRC, planes, routing"

Note that `t_44f72333`/`t_acbe0536` target `output/v2_adc_fixed.kicad_pcb`, a
**different file** from the board verified here. Whatever board the fix lane
produces must be verified with this same from-scratch procedure before any fab
order.

### Related verification (sibling artefact, same afternoon)

A separate independent verification landed on this branch while this report was
being written: commit `22fbbc2` (worker-layout, task `t_c5f37d19`/`t_9c0e1e8f`)
reports that the **4-layer** variant `tracker/hardware/output/v2_adc_4layer.kicad_pcb`
(sha256 `1f94ce86f45f554a…`) FAILS as well — it is an empty
`pcbnew.NewBoard()` stub (0 footprints, 0 nets, 0 copper on the inner layers,
1 `invalid_outline` violation), with header-only gerbers; report at
`tracker/hardware/DRC_4LAYER_VERIFICATION.md`, follow-up card `t_bba26596`.
So both the 2-layer and the 4-layer V2-ADC artefacts are currently
non-orderable, for different reasons: the 2-layer board is fully populated but
has 5 real copper shorts and 8 unconnected critical nets, the 4-layer board has
no design content at all.

---

## Recommendations

1. **Do not order / fabricate `output/v2_adc_v3_clean.kicad_pcb`.** Five real
   copper shorts would make the board non-functional and a fab house would
   reject or reproduce the defect.
2. **Fix placement first** (see the overlap table): move C1/C2 clear of U2's
   left pad column and resolve U2.3 ↔ U1.GPIO6. Do not attempt routing before
   this — a router cannot fix overlapping copper, which is why the parent card
   burned its whole budget.
3. **Then route the 26 remaining items** on a corrected board, prioritising
   the 8 unconnected critical nets; `GND` alone accounts for 9 items.
4. **Re-verify from scratch** with the procedure in §Reproduction before
   declaring fab-ready. Target: 0 `shorting_items`, 0 unconnected critical
   nets, ≤ 2 non-critical unconnected, 0 zones.
5. **Treat unverifiable progress claims as failures.** The parent card's
   comments described six successful edits that left no trace in the artefact.
   Any future routing task should be gated on a committed board plus a DRC
   JSON, not on prose.

---

## Reproduction

```bash
cd ~/repos/balloon-fresh/tracker/hardware

# 1. fresh DRC (the board is not modified by DRC)
kicad-cli pcb drc --format json --output /tmp/verify_drc.json \
    output/v2_adc_v3_clean.kicad_pcb

# 2. gates + per-net classification + pad-geometry proof
python3 verify_v2adc_inspection.py output/v2_adc_v3_clean.kicad_pcb \
    /tmp/verify_drc.json output/v2_adc_v3_clean_VERIFY_SUMMARY.json

# 3. confirm the artefact has not changed since this verification
sha256sum output/v2_adc_v3_clean.kicad_pcb
#   f96d4a68c240f7ae1e1f6879f29573c01e1597b43341626722e8f4e05d44c148
git log --all --oneline -- output/v2_adc_v3_clean.kicad_pcb
#   5b45bf9 chore: regenerate clean V2-ADC board + all routing scripts committed
```

Artefacts committed alongside this report:

- `tracker/hardware/output/v2_adc_v3_clean_VERIFY_DRC.json` — raw DRC JSON of the 2026-09-29 run
- `tracker/hardware/output/v2_adc_v3_clean_VERIFY_SUMMARY.json` — machine-readable summary (gates, per-net unconnected counts, shorting-pair geometry)
- `tracker/hardware/verify_v2adc_inspection.py` — the read-only inspection script used above
