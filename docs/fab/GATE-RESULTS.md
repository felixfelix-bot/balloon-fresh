# HUB v9 — GATE RESULTS

**Latest run: 2026-10-17** (re-measurement; the previous record in this file was the 2026-10-16 pass)
**Board:** `tracker/hardware/hub_board_v9.kicad_pcb`
**Measured sha256:** `e55a294628fd38a73e5006fa7fa9138958ab986812b167263a9d130d661c93dd`

> The sha recorded by the 2026-10-16 pass was `2dd363764b2314e8c5f16db240fa979b4b20909afa521045df3eb0c857d8e4c5`,
> which is the board as of commit `352d86a26`. The board has changed since (commit `905b35272`, the `U4`
> library-nickname fix), so that recorded digest was **stale**; the value above is the one measured this run.

**Reading rule for this file.** A gate is "passing" only where an exit code of `0` was observed *and* the
check that produced it actually ran. A check that could not execute is recorded as **NOT RUN** with the
reason it printed — never as a pass. A "pending" check is not a pass. An exit code of `0` from a chain
script means *the chain completed*, not *the board passed*; the verdict is a separate line, and it is
quoted verbatim below.

---

## Gate 1 — netlist integrity — **PASS (exit 0)**, 2 checks NOT RUN

```
~/venvs/kicad/bin/python tracker/hardware/tests/test_netlist_integrity.py
EXIT 0
RESULT: 14 pass, 0 FAIL, 2 PENDING
```

| | |
|---|---|
| exit code | **0** |
| verdict | **PASS** for every check that ran — `14 pass, 0 FAIL` |
| count that proves it | `14 pass, 0 FAIL, 2 PENDING` |
| NOT RUN | 2 checks (`PENDING`, exit code unaffected) — see PENDING-SUMMARY |

Counts read out of this run:

- `v9_flight.net`: **59 components, 0 with an empty footprint**
- `base_station_v1.net`: **44 components, 0 with an empty footprint**
- C (declared vs placed): hub **netlist declares 59, board carries 59**; no extra footprints
- C2 (packaged board): **committed board 59 footprints / packaged board 59 footprints**
- E (discovery, evidence not a gate): 3 `TODO(unverified)` VALUES on the hub (`D_CLAMP`, `R_NTC1`,
  `TH_NTC1`), 2 on the base station

The two `PENDING` items are the base-station route artifacts; they **did not run** and are listed in
PENDING-SUMMARY below with the reason the script itself printed.

## Gate 2 — ERC + schematic-to-board parity — **FAIL (exit 1)**, ERC errors found; parity PASSES

```
bash tracker/hardware/run_erc.sh
EXIT 1
read_erc: 57 finding(s) across all nesting levels  {'error': 20, 'warning': 37}
erc: netlist regenerated (94057 bytes)
parity: netlist declares 230 (ref,pin) nodes
parity: compared 266 nodes that both sides declare
parity: every netlist node that the board also carries agrees on the net name
erc: RESULT -- PROBLEMS FOUND (see above)
```

| | |
|---|---|
| exit code | **1** |
| verdict | **FAIL** — 20 error-severity ERC findings in the schematic. Stage 3 (parity) **PASSES**, so the board has **not** drifted from the schematic |
| count that proves it | **20 errors / 37 warnings** (57 findings), **230** netlist (ref,pin) nodes, **266** compared, **0** mismatches |

ERC errors by class (the 20 printed, counted by type):

| type | count | detail |
|---|---|---|
| `pin_not_connected` | **17** | `U_CUT1–4` pins 4/5/6 (`ARM`, `CTRL`, `SENSE`) = **12 pins** (expected-open provisioning stubs); `U_HUB_CVT` pin 4 (`VOUT`); `U1` pins 3/13/14/35 |
| `power_pin_not_driven` | **2** | `U4` pins 2, 11 (`VDD_IN`, `VBAT_IO`) |
| `wire_dangling` | **1** | a 0.0508 mm stub |

**These counts match the 2026-10-16 record exactly (20 / 37; 12 of the 17 being `U_CUT1–4`) — no drift.**
The 20 ERC errors are real, are in the schematic, and are unchanged; the gate correctly refuses to call
this clean.

## Gate 3 — fab grade chain — chain completed (exit 0), verdict **NOT ORDERABLE**

```
bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9.kicad_pcb tracker/hardware/output/fabgrade_u1gate
EXIT 0
[0] preflight ok        KRT=/data/repos/KiCadRoutingTools  PY=python3
[1] route   : frozen floor 0.20 track / 0.20 clearance / 0.60 via / 0.30 drill, escalation OFF
    Single-ended:  1/3 routed (2 FAILED)
    Multi-point:   128/133 pads connected (5 FAILED)
    failed_single: ["/SX1280_MOSI", "/SX1280_SCK"]   escalations 0, min_clearance_used 0.2
[2] stitch  : 44 pads already stitched, 45 UNRESOLVABLE
[3] refill  : 3 zones, refill returned True
[4] DRC     : unconnected 4, violations 154 {error 16, warning 138}
VERDICT: NOT ORDERABLE
```

| | |
|---|---|
| exit code | **0** |
| verdict | **NOT ORDERABLE** |
| count that proves it | **4 unconnected items**, **154 violations {16 error / 138 warning}**, **2 unrouted nets** (0 tracks each) |

> **Exit code 0 is not a pass.** `fab_grade.sh` returns 0 whenever the chain runs to completion; it exits
> non-zero only for a missing input (router, rules, board, `kicad-cli`). The verdict is the line above:
> **NOT ORDERABLE**. Do not read the 0 as green.

DRC violation breakdown, quoted from the run:

| class | count | severity |
|---|---|---|
| `silk_overlap` | 77 | warning |
| `silk_over_copper` | 32 | warning |
| `copper_edge_clearance` | 16 | error — the `J_W*` wing interface; all 16 are the intentional edge-launch lands |
| `silk_edge_clearance` | 12 | warning |
| `via_dangling` | 8 | warning — includes `via [/SX1280_MOSI]` and `via [/SX1280_SCK]` |
| `lib_footprint_issues` | 7 | warning |
| `holes_co_located` | 2 | warning |

**Difference from the 2026-10-16 record, reported and not explained.** The previous record was
`unconnected 4, violations 153 {error 16, warning 137}`; this run measures `4` and `154 {16, 138}`. The
error count is **identical at 16**; one warning is new, in `lib_footprint_issues` (**6 → 7**). This run's
7 items name `U2`, `U3`, `U4` (missing library `balloon_flight_v9`) and `J_W1..J_W4` (missing library
`Tracker_Mechanical`). The `U4` library-nickname fix (`905b35272`) landed between the two runs, but
**whether that fix changed this count was not established in this session**, so no cause is asserted here.

The 4 unconnected items, quoted:

```
Via [/SX1280_MOSI] on F.Cu - B.Cu   <->  Pad 17 [/SX1280_MOSI] of U4
Pad 18 [/SX1280_SCK] of U4           <->  Pad 22 [/SX1280_SCK] of U1
Zone 'GND_PLANE_F.Cu'                <->  Zone 'GND_PLANE_B.Cu'
Zone 'GND_PLANE_F.Cu'                <->  Zone 'GND_PLANE_F.Cu'
```

### Companion measurement — `fab_readiness_guard.py --check` (exit 0)

```
~/venvs/kicad/bin/python tracker/hardware/fab_readiness_guard.py --check tracker/hardware/hub_board_v9.kicad_pcb
EXIT 0
fab-guard: tracker/hardware/hub_board_v9.kicad_pcb -> tracks 834, vias 286, nets 57/59
  fab-guard: NOT REFUSING, but noting 2 unrouted net(s) (accepted: 0).
             This board is NOT orderable as it stands.
```

Measured directly on the board with pcbnew (`/SX1280_*` each hold **exactly one via and zero tracks**):

```
/SX1280_MOSI: tracks=0 vias=1
/SX1280_SCK : tracks=0 vias=1
```

This is the known, accepted shortfall — **two nets unrouted, manually routed later. Not touched here.**

### Companion measurement — `pad_audit.py` (exit 0)

```
~/venvs/kicad/bin/python tracker/hardware/pad_audit.py
EXIT 0
PAD-AUDIT: PASS -- 0 findings, 23 warning(s).
```

All 23 warnings are the recorded correct idioms, including `U1 (ESP32-S3-WROOM-1U): pad number '41'
appears 13x, all on GND -- standard multi-pad single-net idiom` and `U1 ... 9 unnamed pad(s), PASTE-ONLY
(no copper layer)`.

## CI `test` job — 1 pre-existing, unrelated failure

```
~/venvs/ho-test/bin/python -m pytest tests/test_3d_models_wing.py -q
EXIT 1
1 failed, 35 passed
FAILED tests/test_3d_models_wing.py::test_board_still_carries_the_wings_12_references_and_the_cells
E       AssertionError: 0 segments
```

`0 segments` measured on **master** and on **this branch**; `tracker/hardware/wing_board/` and this test
file are byte-identical between `master..HEAD`. **Pre-existing on master, unrelated to this branch.
Recorded, not fixed here.**

---

## CORRECTIONS — the `U1.41` claim in this file was disproven

**Corrected 2026-10-17.** The 2026-10-16 pass recorded, twice, that `U1.41` was an electrical defect:

> (line 77, old) "**`U1.41` — the exposed QFN pad with no net — is confirmed on the board.** It appears
> **12 times** in the stitcher's unresolved-pad list ... This is an open defect from
> `SX1280_QFN24.kicad_mod` ... The pad-number mismatch means the RF ground pad is **not connected to GND**."
>
> (line 107, old) "1. **The `U1.41` exposed RF pad has no net** — an electrical defect in the radio's
> ground return."

**Both statements are wrong, on every clause.** The measurement that settles it is
`docs/fab/U1-FOOTPRINT-DIAGNOSIS.md`; re-measured on this board this session:

| old claim | measured 2026-10-17 |
|---|---|
| "`U1` is the SX1280" | **`U1` is the ESP32-S3-WROOM-1U** (`RF_Module:ESP32-S3-WROOM-1U`, 62 pad objects / 42 numbers). The SX1280 is **`U4`** |
| "the pad has **no net** — not connected to GND" | **all thirteen `41` pads are on `GND`**: twelve 0.6×0.6 mm PTH pads (0.2 mm drill) plus the central **3.9×3.9 mm** thermal pad, at **13 distinct positions**, all reporting `net=GND` |
| "an open defect from `SX1280_QFN24.kicad_mod`" | that footprint belongs to **`U4`** and is irrelevant here. The thirteen `41`s are the **stock thermal-via array** of the official ESP32-S3-WROOM-1U footprint — the standard KiCad idiom for *several physical pads, one net* |
| — | the **nine unnamed pads have no copper at all**: `layers=['F.Paste']` only, a 3 × 3 grid of 0.9×0.9 mm **stencil apertures** inside the thermal pad. Nothing to connect; not floating |
| "it appears **12 times**" in the stitcher list | the stitcher prints only the **first 20** of its unresolved pads; `U1.41` appears **13 times** in that printed list (13 it is). The `12` was a miscount of a truncated list |

**Independent corroboration from Gate 3 in this same run:** DRC reports **4** unconnected items, and
**none of them involves `U1`** — the two it names by net are `/SX1280_MOSI` and `/SX1280_SCK`. If those
thirteen pads were floating copper, DRC would list them, as it does those two nets. It does not.

**A stitcher `UNRESOLVABLE` entry is not a defect statement.** `stitch_gnd_planes.py` reports the pads it
declined to add a via to; pads already on the plane appear there. There is no `U1` electrical item here.

**Related correction recorded:** the one genuine footprint defect the 2026-10-16 pass found was `U4`'s
missing library nickname (`SX1280_QFN24` → `balloon_flight_v9:SX1280_QFN24`). Measured today:
`U4 fpid=balloon_flight_v9:SX1280_QFN24`. That item is **fixed** (commit `905b35272`).

**Not yet propagated — flagged, not edited here.** Two sibling records still carry the disproven wording:
`docs/fab/README.md` line 54 ("`U1.41` — the radio's exposed ground pad | has no net (pad-number
mismatch); an electrical defect") and `docs/fab/ERC-AND-U1-CLASSIFICATION.md` §1/§4 ("NUMBER COLLISION on
distinct copper", "NINE FLOATING PADS CONNECTED TO NOTHING"). `docs/fab/U1-FOOTPRINT-DIAGNOSIS.md` is the
record that owns the corrected reading. They are outside this file and were deliberately left untouched.

---

## PENDING-SUMMARY — measured present state (2026-10-17)

Status vocabulary: **PASS** = observed exit 0 for a check that ran · **FAIL** = observed non-zero, or an
error-severity finding · **NOT RUN** = the check could not execute; the reason it printed is quoted.
**NOT RUN is never a pass.**

| item | status | why it cannot run (as printed) | how to clear it |
|---|---|---|---|
| Gate 1 · `F. base station (first route — REJECTED, must FAIL): board present` | **NOT RUN** (PENDING) | `tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb does not exist`. The base station has a **netlist but no editable schematic**; these artifacts are OUTPUTS of routing work the Astra gap analysis places at items **B2–B9** | complete B2 (reconstruct the schematic) and B5–B6 (re-place, route); commit a deliberately-loose route as `bs_v1_routed.kicad_pcb` (must violate 0.10/0.45/0.20) |
| Gate 1 · `F. base station (strict, --escalation off, must PASS): board present` | **NOT RUN** (PENDING) | same — `bs_v1_routed_strict.kicad_pcb does not exist` | commit a strict route that meets 0.10/0.45/0.20 |
| Gate 2 · ERC | **FAIL** | ran; 20 error-severity findings in the schematic | fix or expressly exclude (a no-connect marker is the correct form for the 12 `U_CUT1–4` stubs — see `ERC-AND-U1-CLASSIFICATION.md`) |
| Gate 3 · orderability | **NOT ORDERABLE** | ran; 4 unconnected items, 16 error-class DRC items, 2 unrouted nets | route `/SX1280_MOSI` and `/SX1280_SCK`; obtain JLCPCB's written disposition of the 16 intentional edge lands |

**Not deleted on purpose.** The two `F` checks guard a real property — that a rejected route measures dirty
and a shipped one measures clean, graded **from the board**. A permanent red would train the reader to
ignore it; deletion would hide the gap.

---

## WHAT IS NOT ORDERABLE, AND WHY (measured present state)

1. **Two nets are unrouted**: `/SX1280_MOSI` and `/SX1280_SCK` each hold **exactly one via and zero
   tracks** (`tracks 834, vias 286, nets 57/59`; DRC: 4 unconnected items). **Known, accepted, deliberately
   not routed in this pass.**
2. **20 schematic ERC errors** — including 12 floating cut-driver pins and `U4`'s two power pins. Unchanged
   from the earlier record.
3. **16 `copper_edge_clearance` error-class items** need a fabricator's written acceptance — they are the
   intentional `J_W*` edge-launch lands, but the disposition is JLCPCB's to give, not ours to assume.
   See `JLC-QUERY-DRAFT-MESSAGE.md`.
4. **The wing joint geometry is OPEN** — ADR-046 §4.2.1; the board implements Option B while the ADR
   recommends Option A, and §4.2's stated reason was falsified by measurement.
5. **The wing board has 2 of 6 nets unrouted**; the base station has no editable schematic.

**No longer on this list:** *"the `U1.41` exposed RF pad has no net — an electrical defect in the radio's
ground return."* That item was disproven (see CORRECTIONS above); it was a correct thermal-via array on the
ESP32 module, not a defect, and it is not why the board is not orderable.

---

## Historical note — the 2026-10-16 pass

The 2026-10-16 session's own fix notes are preserved, because they describe defects that were real at the
time and are still guarded:

- **Gate 1, `G`** (no exemption relies on `Reference` matching) was a false positive — the check scanned
  comment lines. Now strips comments first and matches only `A.Reference`/`B.Reference`.
- **Gate 1, `C2`** — the order package held **39 footprints against the board's 59**, missing 20 parts
  including the entire SX1280 RF match/filter chain. Regenerated to **59/59**. An order cut from the old
  package would have produced a board with no 2.4 GHz matching network. Verified again this run: **59/59**.
- **Gate 3 preflight** reported *"ROUTE FAILED"* when the router path did not exist. A **missing tool** was
  being reported as a **routing failure**. The script now searches `/data`, `/opt`, `/srv`, refuses to fall
  through (exit 2 listing the searched paths), and picks the interpreter by actually importing `pcbnew`.
  This run shows it working: `[0] preflight ok  KRT=/data/repos/KiCadRoutingTools  PY=python3`.
