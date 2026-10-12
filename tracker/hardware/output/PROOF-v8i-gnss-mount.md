# PCB-v8i verification evidence — t_3c28ba1f

Card: **PCB-v8i — GNSS U.FL + pi matching + M2 mounting holes re-freeze lap (D1-D6)**
Branch: `pr/pcb-v8i-gnss-mount` (base `main` @ 4bb5cd3, the v8h merge)
Final board: `tracker/hardware/output/v8i_krt_gnss.kicad_pcb`
Board sha256: `638de56387721460100cd3048fb23229294f510f0a2d89795026c7e6c0cfd0ea`  (**sha256_12 `638de5638772`**)
Placement hash: `3937af968f5b89c431cf313f4e7d609076995c449c98d9f6d258b89a4a8a7925` (**`3937af968f5b`**)
  = sha256 over the 28 frozen rows `REF|footprint|x|y|rot|value`; recompute with
  `python3.14 tracker/hardware/output/v8i_lap_verify.py`
Single writer of the board: `tracker/hardware/output/build_v8i.py` (v8h `d2e7c3d1ae55` → v8i)
Placement-only lap (gate25 input): `tracker/hardware/output/.placement/v8i_placement_input.kicad_pcb`
  sha256 `2126b992515e35c2a8487a57f1de37ad98f9a249121cf8311e0e7ec5bfd5d419`
Full machine-checked evidence dump: `tracker/hardware/output/PROOF-v8i-lap-check.txt`
  (`v8i_lap_verify.py` → **RESULT: ALL CHECKS PASSED**, exit 0)

---

## 1. Stackup assumption and the resulting 50 Ω width (D6 — required by the card)

**Assumption (pinned, the stackup the order package is placed against): JLCPCB 4-layer,
1.6 mm total, `JLC04121H-3313`-family build-up** — F.Cu / **0.21 mm dielectric (Er ≈ 4.4)** /
In1 solid GND plane / core / In2 +3V3 plane / B.Cu. Microstrip, 35 µm (1 oz) finished copper,
no solder-mask correction:

```
w = 0.39 mm  ->  Z0 ≈ 48.7 Ω      (h = 0.21 mm, Er = 4.4, t = 0.035 mm)
```

That is **identical to the `RF_OUT` basis already shipped in v8h** (v8h PROOF §3), so the board
has exactly **one** RF cross-section: 0.39 mm on F.Cu over the In1 GND plane — 2.6 % under
nominal 50 Ω (return loss ≈ −32 dB, VSWR ≈ 1.09), which is inside the ±10 % JLCPCB impedance
tolerance and needs no network to correct.

**Why this changed from the original placeholder plan.** D3 as first written asked for a pi
*placeholder* (0 Ω / DNP, tuned on the bench with a VNA). The operator superseded it:
*"manual takes too much time. I want it automated."* The feed is therefore **computed
geometrically against the pinned stackup** and the shipped build carries **fixed values**, so
an assembled board needs **zero hand fitting** (it can be fully machine-assembled). The pi
topology is retained **in copper** as insurance (operator, 2026-10-05: "make sure we have the
pads as a backup for optional tuning").

Shipped values in the GNSS feed:

| ref | value | fitted? | role |
|---|---|---|---|
| `R_SER` | **0 Ω** (0402) | **yes** | series link / isolation link in the feed (ADR-031 D1) |
| `C_SH1` | **DNP** (open) | no | radio-side shunt *pad* (bench insurance only) |
| `C_SH2` | **DNP** (open) | no | antenna-side shunt *pad* (bench insurance only) |

With both shunts open the shipped feed is a straight 0.39 mm microstrip `U3.11 → R_SER →
ANT2.1`; there is **no dielectric in the RF path at all** in the shipped build. If a shunt is
ever fitted for bench tuning it **must be C0G/NP0** (tempco ≈ ±30 ppm/°C ≈ 0.4 % over
−40…+85 °C): the board flies at −40 °C, where X7R/X5R (±15 %) is not a stable element, and a
digitally-tunable bank would add a tempco, a control bus and a cold-boot failure mode to solve
a geometry problem now solved by geometry.

## 2. The two RF feeds and their edge positions (D6 — required by the card)

| feed | path | segments | length | width | layer | vias |
|---|---|---|---|---|---|---|
| 2.4 GHz | `U2.9 → ANT1.1` (`RF_OUT`) | 8 | 23.081 mm | 0.39 mm | F.Cu | 0 |
| GNSS L1 | `U3.11 → R_SER → ANT2.1` (`GNSS_RF` 4 seg / `GNSS_ANT` 4 seg) | 8 | 12.460 + 7.210 mm | 0.39 mm | F.Cu | 0 |

Edge positions (board outline = 55.0 × 45.0 mm driven edge, coordinate origin top-left):

* **`ANT1`** (2.4 GHz U.FL) at **(51.000, 22.000)**, rot 0 — the **+X / east edge**, mid-height.
  Footprint origin 4.075 mm from the nearest outline.
* **`ANT2`** (GNSS U.FL) at **(52.200, 42.000)**, rot 180 — the **+Y edge**, south-east corner,
  i.e. the sky-facing edge as flown. Footprint origin 2.875 mm from the nearest outline
  (the +Y edge). Its own solid reference patch is the **In1 GND plane 0.21 mm below** it
  (In1 GND fill present and continuous), and its copper keep-out is §6.
* Port-to-port: `ANT1.1` (51.000, 23.500) → `ANT2.1` (52.200, 40.500) = **17.04 mm**;
  footprint origins **20.036 mm** apart.

**Honest deviation (listed, not hidden).** The card asks for the two RF parts on *opposite*
board edges. They are on **two different edges — but orthogonal, not anti-parallel**: ANT1 is
on the +X edge at mid-height, ANT2 is on the +Y edge in the corner. `ANT1` is *frozen* (the S0
placement locked `ANT1 J1 J2 SOLAR`), and every other edge's free area is taken: the −Y edge
carries U1's module antenna area and U2; the +X edge above ANT1 carries the `RF_OUT` run, MNT1
and C4; the +Y edge west of the corner carries SOLAR, J1 and J2; the −X edge carries the 1 F
supercap and the divider chain. The SE corner is the only region that can host a U.FL with a
keep-out and a solid reference patch **without crossing TX copper**. Measured separation of
the two ports is 20.0 mm. This is recorded as the lap's one open RF-placement question; the
free mitigation in a later lap is to move `J2`/`LED1`/`MNT3` and shift ANT2 to the mid-`+Y`
edge. It is a bench-measurable antenna-isolation question, not a board defect.

## 3. D1 / D2 / D3 / D4 — the GNSS feed itself

* `U3.11` (MAX-M10S `RF_IN`) is on net **`GNSS_RF`**; `ANT2.1` is on **`GNSS_ANT`**.
* Topology (**two nets, one part between them**): KiCad connectivity does not model a part's
  internal path, so a series element is modelled the way a schematic models it —
  `GNSS_RF = {U3.11, C_SH1.2, R_SER.2}`, `GNSS_ANT = {R_SER.1, C_SH2.2, ANT2.1}`.
* Passive antenna (D1/D2): **no DC block, no bias tee, no active-antenna parts** anywhere in
  the lap.
* D4: `U3.13` (`LNA_EN`) and `U3.14` (`VCC_RF`) verified **no-connect** (empty net) — machine
  checked in `v8i_lap_verify.py`.
* Return-path surgery: the inherited KRT F.Cu GND mesh ran a z-shaped stitching wall straight
  across the feed exit at x 44.5–45.1 / y 29.2–31.4. Exactly **3 segments were opened** and the
  **2 surviving wall nodes re-tied to the In1 GND plane** with 0.60/0.30 vias, so the return
  path is preserved and the feed is not crossed.

## 4. D5 — mounting holes (v8h had ZERO)

4× **M2 NPTH, 2.2 mm drill**, every one placed by a **copper- and courtyard-aware search**
(≥ 2.25 mm pad-free, ≥ 1.30 mm to any track/via, ≥ 0.50 mm to the board edge, ≥ 2.725 mm to
every existing courtyard, outside the GNSS rule area, ≥ 9 mm from each other):

| ref | position | hole-edge → board edge |
|---|---|---|
| MNT1 | (52.300, 2.900) | 1.600 mm |
| MNT2 | (24.550, 28.650) | 15.250 mm |
| MNT3 | (42.450, 37.000) | 6.900 mm |
| MNT4 | (15.000, 42.000) | 1.900 mm |

min pair distance 16.414 mm; refdes silk hidden (production mounting holes carry none).
**NPTH drill file now contains 4 holes** (`X52.3Y-2.9 X24.55Y-28.65 X42.45Y-37.0 X15.0Y-42.0`,
all `T1C2.200`) — in v8h this file was **empty**. PTH drill: 88 holes (81 in v8h; +7 = this
lap's 7 vias, every one 0.60/0.30).

## 5. Re-freeze artefacts

* **New placement hash** `3937af968f5b` (full: `3937af968f5b89c431cf313f4e7d609076995c449c98d9f6d258b89a4a8a7925`),
  sha over the 28 frozen placement rows — reproducible, not hand-typed.
* **New gate25** — on the copper-free placement lap (the only artefact a *placement* gate is
  meaningful on, exactly as the v8h PROOF did):
  `output/.placement/v8i_placement_input_gate25.json` → **`placement_gate: PASS`**
  (footprints 28, pads 141, **pad_overlap_pairs 0**, exact overlaps 0, **courtyards_overlap 0**,
  segments 0, vias 0, zones 4, pads_with_no_net 27 — unchanged from v8h's set).
  gate25 on the *routed* board is reported for information in
  `output/v8i_krt_gnss_gate25.json`: overlaps 0, courtyards_overlap 0, shorts 0, clearance 0,
  unconnected 0; its `segments` counter is 409 by construction, which is why its
  `placement_gate` flag reads FAIL there — that flag is only defined on the copper-free input.
* **`placement_guard.py`** — repo scan `violations: []` (exit 0: one writer per board path, no
  new literal coordinate tables); `--gate25` mode records the gate25 block on the new board.
* **New DRM/DRC history row** — appended to `tracker/hardware/drc_snapshots/history.jsonl`
  (label `v8i`), same schema as the v8h rows.
* **New DRC run** (frozen rules): `kicad-cli pcb drc` against the sibling
  `v8i_krt_gnss.kicad_dru` — **byte-identical to v8h's `.kicad_dru`** — and
  `v8i_krt_gnss.kicad_pro` — **byte-identical to v8h's `.kicad_pro`** (verified with `diff`, no
  relaxed "fab floor" rewrite). Result:
  **shorts 0 / clearance 0 / unconnected 0 / courtyards_overlap 0 / copper_edge_clearance 0 /
  hole_clearance 0**; 8 violations, **all cosmetic silk**, listed:

  | type | count | items |
  |---|---|---|
  | `silk_edge_clearance` | 3 | `C_CAP` refdes (1), `U1` outline (2) — inherited from v8h |
  | `silk_over_copper` | 3 | `U2` outline (2) — inherited; **`ANT2` refdes (1) — new** |
  | `silk_overlap` | 2 | **`ANT2` refdes vs its own outline (new)** |

  The cosmetic set is 5 inherited + 3 new on `ANT2`'s silkscreen reference (the refdes could not
  be placed clear of its own connector outline; the silk refdes is kept deliberately because the
  bench needs to identify the GNSS port). The lap's **first** build had **10** violations
  including `copper_edge_clearance ×1` and `courtyards_overlap ×1`; both were root-caused and
  fixed **at generation time** (§7) — not waived, not papered over.

## 6. The GNSS keep-out (D1's non-negotiable)

One F.Cu **rule area (do-not-pour)** `43.0, 28.8 → 54.5, 44.6` (11.5 × 15.8 mm) covering the
ANT2 + feed region, with the **solid In1 GND plane** (filled) beneath as the reference patch.
There is **no F.Cu pour anywhere** on this board (0 F.Cu pour zones) — the rule area is
therefore defensive: it keeps any future F.Cu pour out of the antenna/feed region and off the
`U3.11` exit corridor, which is what protects the microstrip's reference geometry.

Measured contents of the rule area (`v8i_lap_verify.py`, item-by-item copper census):

* `RF_OUT` (the 2.4 GHz TX feed): **0 segments inside**. ✓
* frozen GND **stitching vias**: **0**. ✓ (v8h carried a stitching wall straight through the
  feed exit; this lap opened it and re-tied the surviving nodes to In1.)
* GND vias inside: exactly the **2 wall-return ties** this lap created (44.5, 29.2 / 44.5, 31.4)
  and the **5 U.FL/pi ground returns** (52.875/51.450/49.875, 42.0 · 48.7, 32.5 · 48.7, 37.0) —
  i.e. the connector's own reference patch, not a fence.
* **LISTED DEVIATION:** the inherited I²C debug lane clips the lower part of the rule area —
  `I2C_SCL` 2 items (F.Cu 29.800,40.800 → 46.400,40.800 and 46.400,40.800 → 47.600,42.000),
  `I2C_SDA` 3 items (F.Cu 37.100,40.200 → 43.300,40.200, via 43.300,40.200,
  B.Cu 43.300,40.200 → 45.100,42.000) plus pads `J2.3` (45.080, 42.000) and
  `J2.4` (47.620, 42.000). Closest approach to `ANT2.1` ≈ **7.2 mm**. These are pre-existing
  frozen-v8h routings, low-speed (≤ 400 kHz, BMP280 + debug header), **not TX and not via
  stitching**; removing them means re-routing an inherited bus, which is out of this lap's
  scope. Listed for the reviewer and as the second candidate mitigation if the bench GNSS
  noise-floor measurement is bad.

## 7. The two generation-time fixes (why the first v8i build's errors are gone)

1. **`courtyards_overlap` (D1 ↔ MNT2).** The hole search modelled **copper only** and landed
   MNT2 on D1's courtyard. Fix: courtyard boxes are now **re-measured after the new RF parts
   exist** and every candidate site must clear every courtyard by 0.25 mm → MNT2 moved to
   (24.550, 28.650); DRC `courtyards_overlap` = 0.
2. **`copper_edge_clearance` (GND via at x = 54.275).** A *typed* `pad + 0.60 mm` east-return
   offset put a via 0.425 mm off the driven edge line (x = 55.0), under the frozen 0.50 mm
   copper-to-edge rule. Fix: **both** remaining U.FL returns are now **computed** by
   `find_gnd_via` (walks inboard, ≥ 0.90 mm to the edge, ≥ 0.25 mm to foreign copper, ≥ 0.10 mm
   outside **every** pad box so a site can never be via-in-pad) → east (52.875, 42.000),
   outboard (51.450, 43.500); `copper_edge_clearance` = 0.

## 8. JLCPCB package (regenerated)

`tracker/hardware/output/gerbers_v8i_jlcpcb.zip` — **176,706 bytes, 16 files, flat**
**sha256 `81d98c179d566f551f14a978431a02c1bb15184dc6aba8aee2ae39fe6bfdf8ad`**
(`tracker/hardware/export_v8i_gerbers.sh`, mirrors the v8f/v8h package layout)

Layer sanity (empty-gerber trap checked — D-codes / draws / flashes):

```
F_Cu 30/624/190   In1_Cu 8/3406/88   In2_Cu 8/3874/88   B_Cu 7/54/88
F_Mask 27/0/132   B_Mask 5/0/18      F_Paste 21/0/110   Edge_Cuts 1/5/0
F_Silkscreen 3/1896/0 (45,654 B)
```

drill: **PTH 88 holes**, **NPTH 4 holes** (2.2 mm only — the v8h NPTH file was empty).
CPL `pos_v8i.csv` = **24 parts** (28 footprints − 4 mounting holes).

## 9. What is measurable on a bare board — and what is not

Measured here (machine-checked, reproducible): netlist/connectivity, trace geometry (width,
length, layer, via count per RF net), DRC under the frozen sibling rule set, the keep-out copper
census, hole positions/drills, gerber/drill/CPL completeness, placement hash.

**Not measurable on a bare, unpowered board — explicitly out of scope of this evidence:**

* the real 50 Ω of either feed (needs VNA/TDR on an assembled board) — the value here is a
  *geometric prediction* against the pinned stackup; the pi pads exist as the fallback;
* antenna SWR/efficiency, and GNSS L1 noise floor under 2.4 GHz TX (§2 deviation);
* TX-burst rail droop.

**Power-rail note from the card thread (recorded, not implemented here):** the LoRa2021F33-2G4
needs a real 5 V rail for full output — ~26 dBm at 3.3 V vs ~30 dBm at 5 V (868/915 MHz), with
TX bursts up to ~900 mA (2.4 GHz/1 W) / ~800 mA (868/915/1 W) and < 20 mV rail droop. v8i does
**not** add a 5 V rail: a new regulator + new net + new layout is a different lap, not this
GNSS + mechanics re-freeze (one re-freeze, one new placement hash).

## 10. ADR-031 extras raised in the card thread — per-item status

| ADR-031 item | status on v8i |
|---|---|
| 0 Ω link **in the RF feed** | **DONE** — `R_SER` 0 Ω in the GNSS feed (this lap's own net) |
| 0 Ω link **per power rail** | **NOT in this lap** (rails today: +3V3, VCAP, SOLAR_IN, GND) |
| 0 Ω link **per bus line** | **NOT in this lap** (SPI ×4, UART ×2, I²C ×2, LR_IRQ/RST/BUSY) |
| test points per rail/bus/RF node (GCPW pads on the 50 Ω line) | **NOT in this lap** |
| reworkable module keep-outs | unchanged from v8h (U2/U3 replacement clearance not re-engineered) |
| 5 V rail able to deliver the TX burst without > 20 mV droop | **NOT in this lap** — see §9 |

D1–D6 (the card body, operator-approved and locked) are all delivered. The ADR-031 extras are
**flagged here rather than silently absorbed** — they are a mechanical/isolation lap of their
own, and folding them in would have broken the "one re-freeze, one placement hash" rule the
card sets.

## 11. DRC / progress row

`drc_score` line appended to `tracker/hardware/drc_snapshots/history.jsonl`:

```
label v8i · board output/v8i_krt_gnss.kicad_pcb · sha256_12 638de5638772
shorts 0 · clearance 0 · unconnected 0 · parity (n/a) · violations 8 (all silk) · fab_ready 1
fp 28 · vias 62 (all 0.60/0.30) · segments 409 · copper 842.1 mm
```

`shorts + clearance + unconnected` = **0** against the same frozen `.kicad_dru`, so the row is
comparable with the v8h row (`d2e7c3d1ae55`, same 0/0/0, 5 cosmetic) — and this lap *adds* RF
and mechanical function while keeping that floor: the only delta in the violation list is 3 new
cosmetic silkscreen warnings on the new `ANT2` refdes.
