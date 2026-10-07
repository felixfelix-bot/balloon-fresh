# PCB-S0 — v9 HUB board placement frozen at ZERO pad overlap

**Branch:** `feat/v9-hub-placement` · **Worktree:** `~/worktrees/bf-hubplace` ·
**Date:** 2026-10-07 · **Base:** `github/main` @ `a09dcbd6856ccb126b44a76ffbbb1497f59dd200`
**Repo convention followed:** `tracker/hardware/PLACEMENT-S0-FREEZE.md` (the v_c3 flight board),
`placement-source-of-truth.json`, `tracker/hardware/drc_snapshots/history.jsonl`.

**Frozen artefact:** `tracker/hardware/hub_board_v9.kicad_pcb`
**sha256:** `07b0683bcfa967a25840f2855a4d8bd657d28d1785b4db864614fc3c611a3217`
**Reproducible input (seed):** `tracker/hardware/output/hub_board_v9_seed.kicad_pcb`
**seed sha256:** `06ac5c92baa3214f11d89a30033e5815b07a07f3376f67f1d76256b55a832abf`
**Netlist of record:** `tracker/hardware/schematics/flight_board/v9_flight.net`
**netlist sha256:** `d0708df92bd2ad357a9c91007c7a9e31d9c2fd1c92743ddb4a119f39cfa53db3`

> **UPDATED 2026-10-07 by `fix/f33-land-size` — read §7 before trusting this sha.**
> The F33 castellated pad **land size** was re-derived from the operator-supplied
> castellation hole diameter **D = 0.80 ± 0.10 mm** (was the guess 2.0 × 1.0 mm). The
> frozen board embeds that footprint, so its **bytes changed** even though the
> **placement did not move**. A control run that restores the OLD footprint reproduces
> the previous sha `2f0a6673…` **exactly**, which proves the only input that moved the
> bytes is the land size. **Classification: RE-VERIFICATION ONLY — not a re-place, not a
> re-route.** The figures recorded in §1 below were re-measured on the new board and are
> unchanged (0 pad-box overlaps, 0 courtyard overlaps, `placement_gate PASS`); the DRC
> class counts are identical to the table in §1.

**This is a PLACEMENT. It is NOT routed.** `segments = 0`, `vias = 0`, `zones = 0` — by design.

---

## 1. GATE S0 — result

`python3 gate25_check.py hub_board_v9.kicad_pcb`:

```json
{
  "board": "hub_board_v9.kicad_pcb",
  "footprints": 39, "pads": 251, "segments": 0, "vias": 0, "zones": 0,
  "margin_mm": 0.2, "pads_with_no_net": 31,
  "pad_overlap_pairs_0.2mm": 0, "pad_overlap_examples": [],
  "exact_pad_overlap_pairs_0.2mm": 0, "exact_pad_overlap_examples": [],
  "courtyards_overlap": 0,
  "drc": {"violations_total": 69,
          "by_type": {"drill_out_of_range": 12, "copper_edge_clearance": 16,
                      "silk_overlap": 12, "silk_over_copper": 16,
                      "lib_footprint_issues": 7, "silk_edge_clearance": 6},
          "courtyards_overlap": 0, "shorting_items": 0, "clearance": 0,
          "unconnected": 157},
  "placement_gate": "PASS"
}
```

| criterion | required | measured | pass |
|---|---|---|---|
| pad-overlap pairs @0.2 mm (pad-box proxy) | 0 | **0** | ✅ |
| exact pad-rectangle overlaps @0.2 mm | — | **0** | ✅ |
| `courtyards_overlap` (kicad-cli DRC) | 0 | **0** | ✅ |
| segments / vias on the board | 0 | **0 / 0** | ✅ |
| footprint count | ≥ 10 | **39** | ✅ |
| `gate25_check.py` `placement_gate` | PASS | **PASS** | ✅ |

`placement_guard.py --gate25 hub_board_v9.kicad_pcb` →
`"gate25": {"board": "hub_board_v9.kicad_pcb", "ok": true,
"detail": "gate25: fp=39 pad_overlaps=0 segments=0 -> PASS"}`.

**Process exit code is 1, and it is NOT this board.** `placement_guard.py` returns
`1 if problems else 0` where `problems` is the *repo-wide scan*, and the scan carries **two
PRE-EXISTING violations on other boards**:

```
R1: board 'v_c3_flight_v7_diagonal.kicad_pcb' has 2 writers: output/route_v7_diagonal.py, route_diagonal.py
R2: 'auto_bootsel/auto_bootsel_pcb.py' defines 10 literal coordinate rows and is NOT a registered placement source
```

Proven pre-existing, not introduced here: a `git worktree` of the untouched base
**`--detach a09dcbd`** returns the *identical two strings* and the *same exit 1*, and that tree
contains neither `hub_board_v9.kicad_pcb` nor `build_hub_board_v9.py`. The v9 hub board
contributes **no** violation to the scan (neither pattern in the guard matches its generator:
it is a single writer and it defines no literal coordinate table). The two items are flagged as
deferred (§6) — they belong to other boards' provenance and are not fixable from this task
without changing someone else's build tooling.

**DRC is not a substitute for this gate.** An unrouted board passes DRC trivially — that is why
the S0 gate exists. The `unconnected = 157` is the pre-route ratsnest of the 51 nets (0 copper),
not a fault; `shorts 0` / `clearance 0` / `courtyards_overlap 0` are what this placement asserts.
Residual DRC classes, all dispositioned and none a placement defect:
* `drill_out_of_range` ×12 — PTH shield pads of the `RF_Module:ESP32-S3-WROOM-1U` footprint
  (footprint-inherited, not a placement item).
* `copper_edge_clearance` ×16 — the four wing sockets' lands on the interface edges. This is
  *intentional and specified*: `WING-TO-HUB-SOCKET-SPEC.md` §4 — "across the interface edge itself
  the land is the interface — that edge is the one place copper intentionally reaches the outline".
  4 sockets × 4 lands = 16.
* `silk_*` ×34 and `lib_footprint_issues` ×7 — silkscreen cosmetics; and the 7 repo-local
  footprints (`balloon_flight_v9:*`, `Tracker_Mechanical:*`) whose libraries are not in the global
  fp-lib-table for a standalone DRC run.

## 2. Board creation — how

```
v9_flight.net  (46 components / 51 nets, committed)
   │  read by build_hub_board_v9.py            (netlist facts only - nothing re-derived)
   ▼
footprints loaded from their REAL libraries   (F33 = 18 pads, SX1280_QFN24 = 25,
   │                                           LoRa2021_Castellated = 18, Wing_Tab_4P = 8)
   ▼
computed floorplan seats                      4 wing sockets on the 4 edge centre lines at 90 deg
   │                                          (ADR-046 §1); 4 U.FL sites on the board edge
   │                                          (ADR-029 D3 / ADR-045)
   ▼
collision-checked bottom-left pack            computed 1 mm grid; cleared against the gate's OWN
   │                                          pad-box proxy UNION the courtyard
   ▼
output/hub_board_v9_seed.kicad_pcb            byte-deterministic (KIID.SeedGenerator(20261007))
   │
   ▼  KRT py_placer/place_optimize.py
      --max-displacement 1 --max-passes 6 --step 1.0 --clearance 0.7
      --halo-base 1.2 --halo-weight 12.0 --no-rotate
      --lock J_W1 J_W2 J_W3 J_W4 ANT1 ANT2 ANT3 ANT4
   ▼
tracker/hardware/hub_board_v9.kicad_pcb   ← FROZEN
```

One command reproduces both artefacts: `python3 build_hub_board_v9.py --publish`.

**Reproducibility measured, not claimed.** The seed regenerated twice → identical sha256
`8748e7587d59…`; the KRT lap run twice from that seed → identical sha256 `2f0a66733b7a…`.

**Laps tried (all $0 inference).** The v9 hub needed a *seeding* stage the v_c3 board did not:
KRT's `place_optimize` is a bounded-displacement quench off an existing pose, so it cannot place an
unplaced board, and `place_seed.py` requires a floorplan `--intent` JSON.

| lap | locks | gate S0 (pad-box proxy / courtyards) | verdict |
|---|---|---|---|
| **frozen**: parametric pack + KRT `--max-displacement 1 --clearance 0.7` | 8 edge parts | **0 / 0** | **PASS** |
| parametric pack alone (the seed) | 8 edge parts | 0 / 0 | PASS (kept as the reproducible input) |
| KRT `--max-displacement 2 --max-passes 8 --clearance 0.3` | 8 edge parts | 2 / 0 | **rejected** |
| KRT `--max-displacement 6 --clearance 0.3` off the naive shelf seed | 8 edge parts | 2 / 2 | rejected |
| FFDH shelf seed on **55 × 45 mm** | 8 edge parts | 389 / 199, 28 of 39 unseated | **rejected — outline infeasible** |

The `--max-displacement 2 --clearance 0.3` lap is the informative rejection: KRT reports
`pad_overlap_pairs 0` on **its own** courtyard metric while the gate's *conservative pad-box proxy*
finds **2** pairs (`U4/R_BAL2` −0.305 mm, `U4/R_DIV1` −0.305 mm). KRT's objective is airwire
length and does not contain the proxy, so a KRT lap that is clean by KRT is not automatically clean
by the S0 gate — the gate grades the artefact, not the router's opinion of itself.

## 3. Outline of record — and why the 55 × 45 mm figure was rejected

**Frozen outline: 103.0 × 103.0 mm**, `(gr_rect (start 0 0) (end 103 103) … "Edge.Cuts")`,
stroke 0.15 mm, 4 layers (ADR-029/030), 0.6 mm thickness.

Sources, both printed in the record:
* `docs/adr/051-hub-array-and-cut-topology.md` §2.3 — "Implied continuous single-face square
  **78.2 × 78.2 mm (H2) … 103.0 × 103.0 mm**", "the hub outline grows … to a panel sized by the
  array", "this is a FORM-FACTOR CHANGE, not a tweak".
* `docs/adr/055-hub-geometry-final.md` D5 — "the hub grows to ≈103 mm square for 106 cm²"
  (`√106.1 cm² ≈ 103 mm`).

Why the two other recorded candidates were not used:
* **55.0 × 45.0 mm** (the v8h-inherited outline, the only outline encoded in a *generated*
  artifact — `output/v8i_krt_gnss.kicad_pcb` `gr_rect (0,0)→(55,45)`; ADR-029 §Context ratifies it
  for v9) — is **MEASURABLY TOO SMALL for the v9 electronics**. Its 39 footprinted components
  demand **2582 mm²** of courtyard against a board of **2475 mm²** (usable interior 2279 mm²); the
  edge-seated interfaces did not free enough. A best-effort pack left **28 of 39 parts unseated**
  and the board scored 389 pad-box overlaps / 199 courtyard overlaps. The interior alone needs
  **2203 mm² into 2279 mm² = a 96.7 % packing density**, which no real placer achieves. The growth
  ADR-051 §2.3 calls a form-factor change is therefore forced for the *electronics*, before the
  array is even considered.
* **≈90 × 90 … ≈115 × 115 mm** (ADR-051 §2.3, "the practical outline incl. the four socket land
  rows, their 1.5 mm component keep-out and the component court") is recorded only as "≈", so it
  was not frozen to a millimetre; and the exact value would carry the duty choice with it.

**Caveats carried on the record, not hidden:** ADR-051 and ADR-055 are both **Status: Proposed**
(text not human-accepted), ADR-055 §3 says "no schematic, placement, BOM freeze or fabrication may
treat it as frozen", and ADR-055 D3 makes the array AREA the operator's **open duty choice**
(106.1 / ≈80 / ≈53 cm² = full / 75 % / 50 %). ADR-055 §3 also states "no v9 hub PCB exists, so
nothing is frozen in a board file and **the outline remains ours to set**". So 103.0 mm is a
**placement-stage floorplan**, not a frozen fab outline; a fab outline additionally needs the four
socket dead bands and the component court added (the ≈90–115 mm row above).

## 4. Slot disposition — design change, wing side must match

**Chosen: plain pads, NO slot.** The four wing interfaces `J_W1..J_W4` are land sets only
(`Tracker_Mechanical:Wing_Tab_4P`: 8 lands, 4 per face, 0.9 mm routed slot **not drawn**; the
footprint contains no drill or NPTH feature at all — verified by grep and by the DRC report, which
shows no slot item).

Why: ADR-046 §4.3's **0.9 mm** slot is **below JLCPCB's minimum non-plated slot of 1.0 mm**, so it
is not orderable as written; and its tolerance stack worst-cases to
`(0.9 − 0.2) − (0.6 + 0.1) = 0.00 mm` — a zero-clearance interference fit that may not assemble.
A *plated* 0.9 mm slot is not an acceptable substitute (a copper-lined barrel would short the lands
around the tab). Rather than re-spec the slot to ≥ 1.0 mm NPTH, this builder takes the spec's own
documented fallback — **Option B, `docs/WING-TO-HUB-SOCKET-SPEC.md` §2.2** — which needs no NPTH
operation and no tolerance stack.

**This is a design change and the wing side must match it.**
`tracker/hardware/wing_board/wing_board_v9.kicad_pcb` carries the 8 mm tab built for the slot; with
no hub slot it becomes a flat, fillet-soldered lap on the pads, aligned by hand/fixture
(spec §2.2 already prices this as the cost of the option).

## 5. Netlist audit — the 31 pads that carry no net

Board totals: 39 footprints, 251 pads, 51 nets, **31 pads with net 0**. Full per-pad classification,
**0 unknown**:

| pads | count | disposition | authority |
|---|---|---|---|
| `U1` × **9 unnumbered** `0.7×0.7 mm` pads | 9 | **MECHANICAL** — the official `RF_Module:ESP32-S3-WROOM-1U` footprint's shield/thermal grid has no pad *number*, so it cannot carry a net | same class recorded at `PCB-S0-NETLIST-AUDIT.md` (v_c3) |
| `U1` IO0, IO3, IO45, IO46 (pins 27, 15, 26, 16) and IO35, IO36, IO37 (pins 28, 29, 30) | 7 | **INTENTIONAL (cited)** — the 4 boot-strapping pins and the 3 octal-PSRAM connections are deliberately unassigned | `ADR-108` §"Electrical constraints" ("IO35, IO36 and IO37 are reserved for octal PSRAM … must not appear on either radio bus"; "IO0, IO3, IO45 and IO46 are boot strapping pins and are deliberately not assigned") + §"Explicit strapping-pin audit" |
| `U2.10` F33 `ANT-2G4` | 1 | **INTENTIONAL (cited)** — the F33 carries TX only, so this port has no destination and no matching network is fitted | ADR-034 D5; ADR-108 R1.3; ADR-029 D8 item 2 |
| `U3.9` bare sub-GHz `ANT`, `U3.16` DIO8, `U3.17` DIO7 | 3 | **INTENTIONAL (cited)** | ADR-108 R1.5 (ADR-034 D1; ADR-040 D1/D2; LR2021-LESSONS) |
| `U5.15` VIO_SEL, `U5.18` SAFEBOOT_N | 2 | **INTENTIONAL (cited)** — "Connect to GND for 1.8 V supply, **or leave open for 3.3 V supply**"; "Safeboot mode (active low). **Leave open if not used.**" | u-blox MAX-M10S `UBX-20035208-R08` Table 10; ADR-108 R1.5 |
| `U5.5` EXTINT, `U5.13` LNA_EN, `U5.14` VCC_RF, `U5.16` SDA, `U5.17` SCL | 5 | **INTENTIONAL (cited, datasheet)** — output/leave-open pins, no external LNA, no active antenna, module used over UART | `UBX-20035208` Table 10 (same class as `PCB-S0-NETLIST-AUDIT.md` §3) |
| `U7.4` TPS7A02 DBV pin 4 | 1 | **INTENTIONAL (cited)** — pin 4 of SOT-23-5 **is NC on the part** | TI `SBVS277C` Table 5-1 / R1.5 |
| `U1.3` EN, `U1.13` USB_D-, `U1.14` USB_D+ | 3 | **EXPECTED** — the ESP32-S3 console is USB-Serial-JTAG and **no console connector is fitted** on this revision; R1 names the connector (1×06 2.54 mm header) and the reset RC (10 kΩ / 1 µF) as a later BOM pass. These are the sheet's **3 intentional ERC errors** | ADR-108 R1.7 (`OPEN-10`); `v9_flight-erc.rpt` = 3 errors, all `pin_not_connected` |

`19` of the 22 numbered netless pads are marked `no_connect` on the sheet (19 `(no_connect …)` items
in `v9_flight.kicad_sch`); the remaining `3` are the EXPECTED console pins above. **Nothing was
"fixed"** — the sheet, the netlist, the band split and every part are untouched.

**Supporting schematic invariants re-run on this revision (read-only):**
`scripts/hub_array_topology_check.py` → `VERDICT: PASS (exit 0)` (the hub array is an independent
series string; its hot net shares no node with the wing chain).

**Discrepancy found and flagged (not fixed, and NOT a schematic defect):** the netlist wires
`J_W<n>.3` to `/CUT_SENSE_W<n>`, whereas `docs/WING-TO-HUB-SOCKET-SPEC.md` §3/§3.2 still describes
land 3 as `W<n>_RF` (RF_FEED) and says "leave as a land with **no net** on v9". The **schematic is
the authority here, not the spec prose**: the repo's own gate
`scripts/hub_array_topology_check.py` (run on this revision: **VERDICT PASS, exit 0**) carries
`R8 cut-sense wired on interface(s): W1, W2, W3, W4` — it *requires* exactly this wiring. So the
**spec text is stale** and should be updated to match the sheet; the placement may not edit either,
and this task edited neither. Flagged so the socket spec's owner closes the loop.

## 6. Deferred (with reasons)

1. **`PVA1`, `PVA2`** (hub-array cells) — **EMPTY footprint field** on the netlist. No land pattern
   exists: `V9_HUB_ARRAY_CELLS = 2` is a *documented placeholder* in the generator, and ADR-051 §4 /
   ADR-054 §4.5 / ADR-055 D3+D7 leave the cell COUNT, the mounting plane, the carrier
   (integrated vs split) and the OUTLINE **OPEN**. A land cannot be invented for an open decision.
2. **`U_CUT1..U_CUT4`, `U_HUB_CVT`** — **EMPTY footprint field**; the parts themselves are
   `TODO(unverified)` (harvester and cut-driver selection is `OPEN-26`/`OPEN-27`).
   → **39 of 46 components placed; 7 cannot be until those records land.**
3. **The committed v9 footprint library does not load (repo defect, reported not fixed).**
   `balloon_flight_v9:LoRa2021F33_2G4`, `:LoRa2021_Castellated`, `:SX1280_QFN24` and
   `Tracker_Mechanical:Wing_Tab_4P` each carry a **duplicated** `(version …)/(generator …)` header
   and three carry `;;` / `#` comment lines the footprint parser rejects; `kicad-cli fp export svg`
   answers "Unable to load library" and `pcbnew.FootprintLoad` returns `None`. The builder reads a
   **normalised copy** from a build cache (`output/.hub_v9_libcache/`, comment lines + the duplicate
   header dropped, geometry untouched — pad counts 18/25/18/8 confirm the real land patterns). The
   repo files were **not** modified. The generator that emits them should be fixed.
4. **Two pre-existing `placement_guard.py` scan violations** on other boards (§1) — not fixable
   here without editing another board's build tooling.
5. **The `J_W<n>.3` = `CUT_SENSE_W<n>` vs `W<n>_RF` socket-spec conflict** (§5).
6. **Routing (S1)** — out of scope by instruction. One rule set, later.
7. **Everything ADR-055 leaves open**: the operator's sustained-duty choice (which freezes the array
   AREA), the 0.4 mm stack-up check, the integrated-vs-split carrier cost (D7), the launch
   latitude/season, the standoff height, the loaded `Vmp`.
8. **No `TODO(unverified)` was promoted to a number.** No hardware ordered, nothing frozen for fab,
   no human sign-off requested (that comes only after a routed fab candidate is settled).

*Placement only. Order nothing.*

---

## 7. ADDENDUM — 2026-10-07: F33 land-size correction. RE-VERIFIED, NOT re-placed

**Change:** on `fix/f33-land-size` the F33 castellated pad **land size** was re-derived from
the operator-supplied castellation hole diameter **D = 0.80 ± 0.10 mm** (datasheet §9 p8, read
by the operator) as `land = D + 2 × 0.25 = 1.30 × 1.30 mm`, replacing the declared guess
**2.0 × 1.0 mm** (`TODO(unverified)`, now dropped). Pad **centres did not move** — the 18
pad-centre list is byte-identical (sha256 `960877b2…`) before and after.

### 7.1 Does the placement need to change? — the classification

The decision rule for a geometry edit *after* a placement freeze is which of three things
it forces:

| case | what changes | does it apply here? |
|---|---|---|
| **re-route** | only copper/tracks are redrawn; component seats unchanged | n/a — this board has **no tracks** (`segments = 0`), so there is nothing to redraw |
| **re-place** | one or more components must move to a new floorplan **seat** | **NO** — see §7.2: no component left its seat; the frozen placement stands |
| **re-verify only** | board bytes change because an embedded footprint changed, but every seat and every S0 criterion still holds | **YES — this is the case** |

**Verdict: RE-VERIFICATION ONLY.** It is **not** a re-place (the placement is unchanged) and
**not** a re-route (there is no routing yet — this is an S0 placement-only board).

### 7.2 Evidence

* **Frozen sha changed** — `2f0a6673…` → `07b0683bcfa967a25840f2855a4d8bd657d28d1785b4db864614fc3c611a3217`
  (seed: `06ac5c92baa3214f11d89a30033e5815b07a07f3376f67f1d76256b55a832abf`). The board
  embeds the footprint, so its bytes must change.
* **Control run** — restoring the OLD footprint and re-running `--publish` reproduces the OLD
  sha `2f0a66733b7a853b0052062e1e73833e7194fc7c38dcc257a749965314ab9238` **exactly**. So the
  land size is the *only* input that moved the bytes.
* **Board diff (frozen → new):** **38 of 39 footprints byte-identical** in position *and*
  geometry. The **only** mover is **U2 (the F33 itself)**, `y 12.00 → 12.15` (+0.15 mm) — the
  generator's own pad-box proxy re-seats it because its pad box shrank; **no other component
  changed seat**, and no component left the board.
* **S0 gates on the new board** — `gate25_check.py`: `pad_overlap_pairs_0.2mm = 0`,
  `exact_pad_overlap_pairs_0.2mm = 0`, `courtyards_overlap = 0`, `placement_gate = PASS`;
  `placement_guard.py --gate25`: `ok: true, fp=39 pad_overlaps=0 segments=0`. DRC class counts
  identical to §1 (69 total, same six classes).
* **Reproducible** — two consecutive `--publish` runs from the corrected footprint give the
  same sha `07b0683b…`.

**Nothing was ordered, routed, or frozen for fab. No pad position, net, or other part moved.
The freeze record is updated, not left stale.**

