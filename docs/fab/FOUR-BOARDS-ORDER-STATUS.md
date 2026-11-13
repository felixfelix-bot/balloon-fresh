# Four boards requested for JLCPCB — measured state, 2026-11-13

The operator asked for **v11 flight**, the **solar-cell connector**, the **base station**, and the
**pre-stretch rig** to all be ready for a JLCPCB order. This is what each one measurably is.
One is orderable today. Three are not, for three different reasons, and none of those reasons is
"needs a bit more polish".

Measured on `origin/master` @ `abae5472`, KiCad 9.0.9.

| board | exists? | routed? | DRC | orderable now? |
|---|---|---|---|---|
| **Solar-cell connector** (`wing_interconnect_v1`) | **yes** | **32 tracks, 0 unconnected** | **0 / 0 / 0** | **YES — bare boards** → `docs/fab/wing-order/ORDER-SHEET-solar-connector.md` |
| **v11 flight** | **no board file** | — | — | **NO** — schematic only |
| **Base station** | yes, but **superseded design** | **0 tracks** | — | **NO** — and must not be ordered |
| **Pre-stretch rig** | **no board on master** | 77 opens (branch) | — | **NO** |

---

## 1. Solar-cell connector — ORDERABLE (fabrication only)

`tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`, sha256 `c05d5d5a…f1b0b0d`.

- **34.6 × 20.0 mm** Edge.Cuts centreline, **2 layers**, **0.4 mm**, 2 vias at 0.400 mm
- **DRC: 0 violations, 0 unconnected, 0 parity errors**
- Package rebuilds **byte-identically, 40/40 files** (`build_wing_order.py --check`)
- BOM: 3 × SS24 (C50645); CPL: 3 placements, all top

The repo marks it **NOT ORDERABLE**, correctly — but both blockers are **assembly** questions
(JLC's diode rotation model; whether a 0.4 mm 34.6 × 20 mm board is assemblable at all, since
0.4 mm is outside Economic PCBA and Standard needs ≥70 × 70 mm). **A bare-board order has
neither problem.** Order the boards, hand-solder three SMA diodes.

This is the one board that can be ordered today, and the order sheet is written.

---

## 2. v11 flight — NO BOARD EXISTS, and never has

**This is the most important correction in this document.** There is no v11 flight board file.

```
git log --all --oneline -- '*v11_flight*.kicad_pcb'   ->  (empty)
```

Not on master, not on any branch, not in any worktree. What exists is:

- `tracker/hardware/schematics/flight_board/v11_flight.kicad_sch` (403 KB schematic)
- `docs/fab/V11-DESIGN-SPEC.md` — which says of itself: *"**Status:** SPECIFICATION. No v11 board
  exists yet"*
- `docs/analysis/bulk-route-20261107/v11-dbp2-spec.kicad_pcb` — this is **v10 with exactly one
  part moved**, and that part is an experiment, not v11. Measured against the v10 board of record:

  | | v11-dbp2-spec | v10 board of record |
  |---|---|---|
  | footprint refs | 49 | 49 — **identical set** |
  | tracks / vias | 3092 / 161 | 3092 / 161 |
  | nets | 54 | 54 |
  | `D_BP2` | (36.50, 77.00) **F.Cu** | (29.00, 76.00) B.Cu |
  | `D_BP1`, `D_BP3`, `D_BP4` | unchanged from v10 | — |

  **Only `D_BP2` differs** — it is the ADR-146 "bypass diodes to the top face" trial. The other
  48 parts and all 3092 tracks are v10. It carries the name `v11` because it was used to
  *measure* one v11 change, not because it is v11.

Ordering that file would order **v10 with one diode moved**, under a v11 filename. That is the
single most dangerous thing in this request and it must not happen.

**What v11 actually needs** (from `V11-DESIGN-SPEC.md`), in dependency order:

| # | change | parts added | blocked by |
|---|---|---|---|
| 1 | ADR-146: `D_BP1..4` to the top face | 0 | nothing — sited, worst 1.42 mm |
| 2 | `/SCAP_ADC` + cut sense + solar dividers via I²C ADC | 2 × ADS1115 | resolved (ADR-148) |
| 3 | Real cut driver at `U_CUT1..4` | 4 × (latch + FET + Rg + Rsense) | **schematic** |
| 4 | ADR-145: GPIO expander for `U_C` | 1 × MCP23017 | **schematic** |
| 5 | Full re-route | — | 1–4 |

v11 is **not "v10 with tweaks"**: it starts with *more* to route than v10 ever had, and the v10
campaign took ~20 routing batches to get from 38 opens to 6. Steps 3 and 4 are not layout — they
are unselected circuits.

**Honest estimate:** this is a multi-week campaign, not a "prepare for order" task. The useful
deliverable is the spec (already written) plus a decision on steps 3 and 4.

---

## 3. Base station — the board on disk is the design ADR-149 RETIRED

`tracker/hardware/base_station/base_station_v1_placed.kicad_pcb`: **44 footprints, 0 tracks,
0 vias, 44 nets, 70.15 × 50.15 mm.**

It is placed and completely unrouted. More importantly, it is the **wrong design**: it still
carries the discrete analogue RF chain that ADR-149 (accepted by the operator) replaced with
bought SMA modules.

Measured on the file — these references are all still present:

```
FLT_433_A  FLT_433_B  Q_LNA_SW  TEE1  TEE2  U_DET  U_VGA  C_LNA1  C_LNA2  J_LNA_FEED
nets: +5V_DET  +5V_LNA_SW  +5V_VGA  DET_RF_IN  DET_VOUT  IOVDD  ADC_AVDD
```

`docs/fab/base_station/BOM-RESCOPE.md` retires **18 of those 44 parts** and adds modules instead.
So this file cannot become the orderable base station by routing it — routing it would fabricate
a board carrying parts the project has already decided not to buy.

**What the orderable base station needs:** a new schematic from the ADR-149/150/151 basis
(control board, SMA modules, pump rail), then placement, then routing. **No such board file
exists on any branch.**

Also note ADR-150 merged the base station and the inflator onto **one** board (~70 × 70 mm,
52 parts). So "the base station board" is now half of a combined board that has not been laid out.

---

## 4. Pre-stretch rig — no board on master; the routed candidate is on an unmerged branch

Master carries **documentation only** under `tracker/hardware/pressure-controller-core/`
(README, measurement and supply reports, footprint lib) — **no `.kicad_pcb`**.

The actual board lives on the unmerged branch `pr-pressure-compact-placement` (HEAD `b28cdb8d`):

- 65 × 50 mm single-sided candidate, **77 opens** at last recorded state (earlier routing reduced
  77 → 66, then a keep-out fix; the branch tip reports 77)
- `README.md` of that component: *"buck schematic milestone, **NOT FAB READY**"*
- Its own record: no motor rail, **no pump/cutter actuation**, no valve

And the rig's electrical spec states: *"Pump actuation is disabled; measurement-only work with
pump power disconnected is allowed."* ADR-152 additionally records that **no valve is selected**,
because the fill envelope decides the valve and the envelope class is not fixed.

So the pre-stretch board is blocked on: routing (77 opens), actuation circuitry that is
deliberately absent, and a valve that is deliberately unselected. Two of those three are
**safety decisions**, not engineering backlog.

---

## What to do, in order

1. **Order the solar-cell connector now** (bare boards, 10 pcs). Order sheet is written and
   every number is measured. Hand-solder the diodes.
2. **v11:** decide steps 3 and 4 of the change list (cut driver, GPIO expander). Those are the
   only things between the spec and a routable board. Then it is a routing campaign.
3. **Base station + inflator:** one combined board, new schematic from ADR-149/150/151. The
   existing file is retired and must not be routed.
4. **Pre-stretch:** needs an envelope class decision before the valve, and a routing campaign
   for the 65 × 50 board. Its actuation is intentionally disabled.

## Claims NOT made

- No board here is hardware-qualified. Gates M, S and E remain open.
- Nothing was fabricated, ordered, flashed or actuated in producing this document.
- The solar order sheet authorises nothing: it is settings for the operator to place.
