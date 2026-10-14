# Hub-outline authority for the v9 flight board — 22 × 22 mm vs 55.15 × 45.15 mm

> **STATUS: ANALYSIS, NOT A DECISION RECORD.** This document resolves a factual contradiction
> between two committed figures. It changes **no** design decision, freezes **no** number, and
> orders nothing. It is not an ADR and carries no authority of its own — it is an evidence
> audit. Where the evidence does not settle a question it is marked `TODO(unverified)`.

---

## 0. Headline verdict

**The current figure is 55 × 45 mm (quoted throughout the repo as 55.15 × 45.15 mm, which is the
same rectangle plus its 0.15 mm Edge.Cuts stroke).** The single strongest piece of evidence is a
generated board file: `tracker/hardware/output/v8i_krt_gnss.kicad_pcb:8136–8144` encodes the
outline as `(gr_rect (start 0 0) (end 55 45) … (layer "Edge.Cuts"))`, i.e. a **physical
55.000 × 45.000 mm rectangle**, and the same rectangle is in every other generated flight board
(v8b, v8f, v8h, v8j, v_c3_flight_final). **No generated artifact anywhere in `main` encodes
22 × 22 mm.**

The 22 × 22 mm figure has exactly one source: `docs/hardware-design.md:13`, a German-language
v1-era concept document last committed **2026-05-20** — 4½ months before every v9 record that
says 55 × 45. It is inherited prose, not a drawn outline.

Consequence for the array-growth question: a ~106.1 cm² hub array is a **≈4.3× growth** from
today (106.1 / 24.90), not the **21.9×** that ADR-051 computes off 4.84 cm².

---

## 1. The two figures, quoted exactly

### 1.1 The 22 × 22 mm figure

| Where | Line | Exact wording |
|---|---|---|
| `docs/hardware-design.md` | 13 | `- **Groesse**: 22mm x 22mm` |
| `docs/hardware-design.md` | 21 | `Hub-Board Top-Ansicht (22x22mm):` |
| `docs/hardware-design.md` | 62 | `- **Groesse**: 65mm x 28mm` (the same document's wing, itself superseded — see §3) |

`docs/hardware-design.md` is a v1/v2-era concept document. Its hub component court (lines 25–40)
is ESP32-C3 + LR2021 module + BMP280 + **SKY66112 FEM** + **SP4T switch** + TPS7A02 + 2× supercaps,
2-layer. Every one of those choices is superseded for v9 by ADR-037 (**SKY66112 omitted from
v9**), ADR-038 (Wi-Fi/BT never enabled), ADR-029 (ESP32-S3-WROOM-1U, not C3), ADR-040/044/047
(two LR2021 sites + F33 5 V rail), ADR-029/030 (4-layer, deterministic pipeline). It is the only
source of the 22 mm number in the whole repo.

### 1.2 The 55 × 45 mm figure

| Where | Line | Exact wording |
|---|---|---|
| `docs/adr/029-dual-band-flight-board.md` | 42 | `v8h is the current fab-ready flight board: 55.15 x 45.15 mm, 4 copper layers, DRC-clean` |
| `docs/adr/029-dual-band-flight-board.md` | 47 | `55 x 45 mm board**: a long-range sub-GHz telemetry link, a 2.4 GHz link radio,` |
| `docs/adr/029-dual-band-flight-board.md` | 199 | `- **39 x 21 mm on a 55 x 45 mm board** — the module dominates the layout and constrains` |
| `docs/POWER-BUDGET-V9-D2BE.md` | 166 | `Board dimensions from ADR-029: **55.15 mm × 45.15 mm**. Thickness from the` |
| `docs/POWER-BUDGET-V9-D2BE.md` | 172 | `\| FR4 PCB, 55.15 × 45.15 × 0.6 mm \| 2.76 \| …; thickness from \`tracker/hardware/hub_board_v1_clean.kicad_pcb\` \|` |
| `docs/COEXISTENCE-V9.md` | 4 | `LR2021 @868 MHz (SPI0), SX1280 @2.4 GHz (SPI1), MAX-M10S @1575.42 MHz (UART), 4-layer 55x45,` |
| `docs/adr/040-v9-radio-site-optionality.md` | 164 | `- **Two F33 modules cannot fit** on the 55 × 45 mm v9 board: 39.6 × 21.6 mm each ≈ 79.2 mm of` |
| `docs/adr/030-deterministic-zero-inference-pcb-pipeline.md` | 45 | `- The same **two pad-overlap pairs** (\`U2/C4\`, \`D1/U1\`) survived a 55×45 mm outline, an 80×60 mm` |

---

## 2. The generated artifact (the decisive evidence)

No v9 **hub** PCB has ever been drawn — this is stated three times in the repo:

- `docs/adr/048-v9-hub-wing-interfaces.md:265` — `**No v9 hub PCB exists**, so this cannot be measured yet.`
- `docs/adr/048-v9-hub-wing-interfaces.md:287` — `here; no v9 hub outline exists to check against.`
- `docs/adr/051-hub-array-and-cut-topology.md:206` — `- The v9 hub has **no drawn outline**: ADR-048 §5 notes "no v9 hub outline exists to check`

The nearest thing to a drawn v9 hub is the **v8 flight board**, whose outline v9 inherits
(ADR-029 §Context: the v9 board is the v8h outline carrying four RF systems). That outline is a
real rectangle in real files:

| File | Line(s) | Edge.Cuts geometry | Outline (mm) |
|---|---|---|---|
| `tracker/hardware/output/v8i_krt_gnss.kicad_pcb` | 8136–8144 | `(gr_rect (start 0 0) (end 55 45) (stroke (width 0.15) …) (layer "Edge.Cuts"))` | **55.000 × 45.000** |
| `tracker/hardware/output/v8j_krt_ms5611.kicad_pcb` | 8137 | `(end 55 45)` under `gr_rect` / `start 0 0` | 55.000 × 45.000 |
| `tracker/hardware/output/v8h_krt_u2_lora2021.kicad_pcb` | 6979–6981 | `gr_rect` / `(end 55 45)` | 55.000 × 45.000 |
| `tracker/hardware/output/v8b_krt_routed.kicad_pcb` | 7025–7027 | `gr_rect` / `(end 55 45)` | 55.000 × 45.000 |
| `tracker/hardware/output/v8f_krt_margin_escaped.kicad_pcb` | — | parses to `gr_rect (0,0)→(55,45)` | 55.000 × 45.000 |
| `tracker/hardware/output/v_c3_flight_final.kicad_pcb` | 7022–7024 | `gr_rect` / `(end 55 45)` | 55.000 × 45.000 |

All are **rectangles** (single `gr_rect` on `Edge.Cuts`), not stepped or notched outlines.

### 2.1 Where "55.15 × 45.15" comes from — and why it is the same board

The 0.15 mm excess is the **Edge.Cuts stroke**, not a second outline. The `gr_rect` carries
`(stroke (width 0.15))`, so its outer envelope is 55.000 + 0.15 = **55.150 mm** and
45.000 + 0.15 = **45.150 mm**.

- `tracker/hardware/output/PROOF-v8i-lap-check.txt:5` —
  `edge bbox       : -0.075,-0.075 .. 55.075,45.075  (55.150 x 45.150 mm)`
  (half the 0.15 mm stroke on each side).
- `tracker/hardware/C3-SIGNOFF.md:156` — the `.gbrjob` declares `Size: 55.15 × 45.15`.
- `tracker/hardware/C3-SIGNOFF.md:165` — `- Board is **55.15 × 45.15 mm**, not the 50 × 40 mm the plan §3.2 specifies.`

So **55.15 × 45.15 and 55 × 45 are the same board** at two measurement conventions (plot
envelope vs. rectangle centreline). `docs/adr/029-dual-band-flight-board.md` uses both in the
same §Context (line 42 "55.15 x 45.15", line 47 "55 x 45") without flagging a difference —
correctly, because there is none.

### 2.2 No generated artifact encodes 22 × 22 mm

The v1 hub boards that *were* drawn are **not** 22 × 22 either:

| File | Edge.Cuts | Outline |
|---|---|---|
| `tracker/hardware/hub_board_v1_clean.kicad_pcb` | `(gr_rect (start 0 0) (end 50 40) (stroke (width 0.15) …) (layer "Edge.Cuts"))` | 50.000 × 40.000 |
| `tracker/hardware/hub_board_v1_placed.kicad_pcb` | `gr_rect (0,0)→(50,40)` | 50.000 × 40.000 |
| `tracker/hardware/hub_board_diy/hub_board_diy.kicad_pcb` | `gr_rect (0,0)→(45,38)` | 45.000 × 38.000 |
| `tracker/hardware/hub_board_f33.kicad_pcb` | `gr_rect (0,0)→(75,55)` | 75.000 × 55.000 |

`tracker/hardware/gen_pcb.py:143` (`W, H = 50, 40`) and `tracker/hardware/full_pipeline.py:30–31`
(`BOARD_WIDTH_MM = 50.0`, `BOARD_HEIGHT_MM = 40.0`) are the v1 generators; they emit 50 × 40.
The only appearance of "22x22" in executable code is a **print statement** in a placeholder:
`tracker/hardware/assembly/generate_gerbers.py:8` — `print("Hub board: 22x22mm")`, inside
`generate_assembly()`, whose first line is `print("Assembly generator placeholder")`. It draws
nothing.

**No `.kicad_pcb`, no `build_*.py`, no `gen_pcb.py`, no `full_pipeline.py` and no gate script in
`main` emits a 22 × 22 mm outline.** The 22 × 22 mm hub therefore appears never to have been
drawn at all.

---

## 3. Are these the same board at different stages, two different boards, or a genuine contradiction?

**Answer: the same board lineage at two different design stages — and, on the evidence, a figure
that was never physically realised.** They are not two concurrent boards.

1. **Same lineage, different stage.** `docs/hardware-design.md` (2026-05-20) is the v1 concept:
   a small 22 × 22 hub with **four separate 65 × 28 mm wing boards** folded 90°
   (`generate_gerbers.py:9` — `print("Wing boards: 4x 65x28mm at 90-degree intervals")`). The
   v8h/v9 flight board is the single 55 × 45 mm board that replaced that hub+wing concept.
   `docs/adr/051-hub-array-and-cut-topology.md:363` names exactly this growth:
   `**The hub outline grows from 22 × 22 mm to a panel sized by the array.**`
2. **Not two concurrent boards.** There is no second "radio-only" board. ADR-040's two
   *radio sites* (Site A nested F33/bare, Site B bare) are two populations of one board, not two
   boards; both sit on the 55 × 45 mm hub (`docs/adr/040-v9-radio-site-optionality.md:164`,
   ADR-051 Related: "ADR-040 (both v9 radio sites on the hub)").
3. **There is a real contradiction between workers**, but it is a *citation* contradiction, not a
   *design* contradiction. The 2026-10-07 records repeatedly cite the stale 22 mm number as the
   *current* hub outline while simultaneously placing the board at 55 × 45:
   - `docs/adr/048-v9-hub-wing-interfaces.md:69` — table row
     `| Hub outline the slots sit on | 22 × 22 mm | **CITED**: \`docs/hardware-design.md\` line 13 ("Groesse: 22mm x 22mm") …`
   - `docs/adr/046-wing-board-interface.md:269` — `6.0 mm keeps the slot 5.0 mm short of the 22 mm hub's centre`
     (a **derived** number that has 11 mm — half of 22 — baked into it).
   - `docs/WING-TO-HUB-SOCKET-SPEC.md:132` — `on a 22 × 22 mm hub an 8 mm-wide tab centred on a 22 mm edge leaves 7 mm per side`
   - `docs/adr/051-hub-array-and-cut-topology.md:367` — `| Current (inherited) hub outline | **22 × 22 mm = 4.84 cm²** | CITED: \`docs/hardware-design.md\` line 13 …`
   These records each *label* the figure as inherited/cited, but ADR-051 then reasons on it as
   the baseline for a form-factor change.

The repo has already noticed this contradiction and filed it:
`docs/analysis/two-variant-mass-budget.md:468–473` —

> `8. **The v9 hub board outline and thickness.** The repo contradicts itself: \`hardware-design.md\`
> line 13 says **22 × 22 mm** (≈ 0.54 g bare FR4 at 0.6 mm) while \`POWER-BUDGET-V9-D2BE.md\` §4
> and ADR-029 use **55.15 × 45.15 mm** (2.76 g bare / 3.18 g with the ×1.15 rule) — a **5.9×**
> PCB-mass difference. \`docs/adr/048-v9-hub-wing-interfaces.md\` §5 item 5 records the outline
> as unfixed. This alone moves both variants' totals by up to ~2.6 g.`

(The 5.9× is the finished-board ratio 3.18 / 0.54; my own computation of the bare-FR4 ratio is
2.764 / 0.537 = **5.15×** — `[COMPUTED]` from 2490.2 mm² and 484 mm² at 0.6 mm × 1.85 g/cm³.
Both figures are in the same 5–6× band; the ordering is unaffected.)

---

## 4. The current outline, if a generated artifact encodes it

- **Effective outline: 55.000 × 45.000 mm rectangle, 4 copper layers, 0.6 mm thick.**
  Source: `tracker/hardware/output/v8i_krt_gnss.kicad_pcb:8136–8144` (gr_rect on Edge.Cuts),
  corroborated by v8h/v8j/v8b/v8f/v_c3_flight_final (§2) and by
  `tracker/hardware/output/PROOF-v8i-lap-check.txt:4` `copper layers   : 4` and
  `.gbrjob BoardThickness: 0.6` (`tracker/hardware/C3-SIGNOFF.md:155`).
- **Quoted size for fab: 55.15 × 45.15 mm** = the same rectangle + the 0.15 mm Edge.Cuts stroke
  (§2.1).
- **Shape: a plain rectangle.** Every flight board carries a single `gr_rect` on `Edge.Cuts`;
  there is no notch, step, tab or corner cut in the flight-board outline in `main`.
  (The **wing** is a different shape — `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`
  uses 8 `gr_line` Edge.Cuts segments spanning x −8…176, y 0…25, i.e. body + 8 mm tab, per
  ADR-046 §3.2 — but that is the wing, not the hub.)
- **For v9 specifically:** the hub outline is still *unfixed* per
  `docs/adr/048-v9-hub-wing-interfaces.md:265/287` and
  `docs/analysis/wing-mass-shape.md:556` — `the v9 hub outline is unfixed (ADR-048 §5 item 5)`.
  What is fixed is that v9 **inherits the 55 × 45 mm v8h outline**
  (`docs/adr/029-dual-band-flight-board.md:42/47`), and that ADR-051 (Proposed) would grow it to
  ≈90 × 90 … ≈115 × 115 mm (`docs/adr/051-hub-array-and-cut-topology.md:371`).

---

## 5. What is dimensionally pinned to this outline (must be re-frozen if it changes)

Every item below was frozen against a hub outline. The **first three** are frozen against
22 mm specifically and are the ones that break first.

### 5.1 Frozen against the 22 mm figure (the stale datum is baked into a derived number)

1. **ADR-046 wing-tab insertion depth — 6.0 mm.**
   `docs/adr/046-wing-board-interface.md:269`:
   `6.0 mm keeps the slot 5.0 mm short of the 22 mm hub's centre, clear of the component court.`
   Re-freeze trigger: 6.0 mm was justified against an 11 mm half-edge. On a 55 × 45 mm hub the
   "centre" is 27.5 / 22.5 mm away, so the *rationale* changes even if the number survives.
2. **Socket slot-to-slot interference arithmetic.**
   `docs/WING-TO-HUB-SOCKET-SPEC.md:132` and `docs/adr/048-v9-hub-wing-interfaces.md:202–204`
   (`(22 − 9.0)/2 = **6.5 mm** per side`). Re-freeze trigger: the arithmetic datum is the 22 mm
   edge.
3. **ADR-048 §5 item 8 corner-radius check.**
   `docs/adr/048-v9-hub-wing-interfaces.md:287`: the routed slot + 1.0 mm keep-out is checked
   against `the 22 mm hub's corners`. Re-freeze trigger: not performed; no v9 hub outline exists
   to check against.

### 5.2 Frozen against *the* hub outline (whichever it is)

4. **The four wing socket land rows at 90°** — 4 interfaces, 8 lands each (4 F.Cu + 4 B.Cu),
   land **4.0 × 1.2 mm**, land pitch **1.8 mm** (0.6 mm gap), tab width **9.0 mm**.
   Source: `docs/adr/048-v9-hub-wing-interfaces.md:69–78` and `:146`;
   `docs/adr/046-wing-board-interface.md:114`. Land row sits **1.0 mm … 5.0 mm** inboard of the
   interface edge (`docs/adr/048-v9-hub-wing-interfaces.md:196–197`). These four rows are the
   "dead bands" ADR-051 explicitly re-derives the new outline around
   (`docs/adr/051-hub-array-and-cut-topology.md:371`, "the dead bands are the socket rows at 4
   edges").
5. **Slot geometry** — 0.9 mm ± 0.10 mm routed slot, 6.0 mm depth, per-interface DNP bypass
   Schottky (`docs/adr/048-v9-hub-wing-interfaces.md:85`; `docs/adr/046-wing-board-interface.md:270`).
6. **The two v9 radio sites** — Site A (nested F33/bare, mutually exclusive) and Site B (bare
   LP), both DNP by default, both on the hub (`docs/adr/040-v9-radio-site-optionality.md:50–56`,
   `:164`; ADR-051 Related line: "ADR-040 (both v9 radio sites on the hub)").
7. **U.FL antenna feed positions on the board edge** — ADR-029 D3 assigns U.FL to the board
   edge; the frozen v8i placement is
   `ANT1 (U.FL) at (51.000,22.000)` and `ANT2 (U.FL_GNSS) at (52.200,42.000)`, each within
   4.075 mm / 2.875 mm of the nearest edge (`tracker/hardware/output/PROOF-v8i-lap-check.txt`,
   "RF parts and edges"). ADR-029 §6 line 621: `U.FL on all four feeds converts an unsolvable
   55 x 45 mm problem into a solvable 3D one.`
8. **The antenna solder-access keep-out** — ADR-045 requires the antenna edge/castellated pad to
   reach the board edge with **≥ G_min = 1.0 mm** clear
   (`docs/adr/045-antenna-solder-access.md:142–144`, `:186–196`). The keep-out is a function of
   where the board edge is.
9. **The GNSS sky-facing keep-out** — ADR-029 §2(d); in the frozen v8i board it is a single F.Cu
   rule area `box 43.0,28.8 .. 54.5,44.6` with no 2.4 GHz TX copper inside
   (`tracker/hardware/output/PROOF-v8i-lap-check.txt`, "F.Cu GNSS keep-out"). It is anchored to
   two board edges.
10. **Mounting / attachment** — 4 × M2 NPTH (2.2 mm drill) at
    `MNT1 (52.300,2.900)`, `MNT2 (24.550,28.650)`, `MNT3 (42.450,37.000)`, `MNT4 (15.000,42.000)`,
    frozen by gate D5 (`≥ 9 mm apart`, min pair 16.414 mm) —
    `tracker/hardware/output/PROOF-v8i-lap-check.txt`, "D5 mounting holes".
11. **The ADR-030 deterministic placement gate** — must be **re-run** on any new outline.
    `docs/adr/030-deterministic-zero-inference-pcb-pipeline.md:119–126` (D3: "The placement gate
    comes before any copper exists") and `:148–152` (D5: placement pinned by hash). The frozen
    v8i/v_c3-family placement hash is recorded in
    `tracker/hardware/PLACEMENT-S0-FREEZE.md` (`sha256: f3cf0143e7deff99…`), and the v8i lap
    record carries `PLACEMENT_HASH: 3937af968f5b89c4…`
    (`tracker/hardware/output/PROOF-v8i-lap-check.txt`).
12. **Board area, hence PCB mass** — `docs/POWER-BUDGET-V9-D2BE.md:172` F4 line
    `FR4 PCB, 55.15 × 45.15 × 0.6 mm | 2.76` (bare) / 3.18 g (×1.15). Any outline change moves
    this and every total that includes it (`two-variant-mass-budget.md:150/221`, and the
    "shrink the board" lever at `:265`).

---

## 6. Statements that lean on one of the two figures

These inherit the error. If the outline moves, each must be re-checked.

### 6.1 Leaning on **22 × 22 mm** (the stale figure)

| File:line | What it does with the figure |
|---|---|
| `docs/adr/051-hub-array-and-cut-topology.md:367` | Baseline of the whole form-factor argument: `**22 × 22 mm = 4.84 cm²**` |
| `docs/adr/051-hub-array-and-cut-topology.md:369` | `**Implied ratio** | **12.6× (H2) … 21.9× (horizontal)** the 22 × 22 mm area \| 61.2/4.84 ; 106.1/4.84` |
| `docs/adr/051-hub-array-and-cut-topology.md:373,389` | "on 22 × 22 mm a 61.2 cm² array **cannot be mounted at all**"; `TODO(unverified)` on 90–115 mm panel loads |
| `docs/adr/048-v9-hub-wing-interfaces.md:69` | `Hub outline the slots sit on \| 22 × 22 mm` |
| `docs/adr/048-v9-hub-wing-interfaces.md:202–204` | `(22 − 9.0)/2 = **6.5 mm** per side` |
| `docs/adr/048-v9-hub-wing-interfaces.md:287` | corner-radius check against "the 22 mm hub's corners" |
| `docs/adr/046-wing-board-interface.md:269` | `6.0 mm keeps the slot 5.0 mm short of the 22 mm hub's centre` |
| `docs/WING-TO-HUB-SOCKET-SPEC.md:132` | `on a 22 × 22 mm hub an 8 mm-wide tab centred on a 22 mm edge leaves 7 mm per side` |
| `docs/analysis/wing-mass-shape.md:47` | `\| Hub outline \| 22 × 22 mm \| **CITED** … (used only for the arm-length datum)` |
| `docs/analysis/wing_mass_model.py:185` | `R0 = 0.011  # m, hub is 22 x 22 mm (docs/hardware-design.md line 13)` |
| `docs/analysis/wing-jettison.md:111` | `\| Root radius r0 \| 11 mm \| CITED \`docs/hardware-design.md\` line 13 (22 mm hub) \|` |
| `docs/analysis/wing-omnidirectional.md:213,267` | Hub shadow bound `484 mm²` = 1.3 % of the array |
| `docs/analysis/wing_omnidirectional.py:395–396` | prints the 22 × 22 hub tab-cluster footprint |
| `docs/analysis/wing-insolation-geometry.md:493,520` | slot fit on a 22 mm edge; shadow from a 22 mm hub |
| `docs/analysis/two_variant_mass_model.py:36` | `HUB_SMALL_MM2 = 22.0 * 22.0   # [REPO] hardware-design.md line 13` |
| `docs/analysis/two-variant-mass-budget.md:470` | cites 22 × 22 ≈ 0.54 g as the small alternative |

The **arm-length datum** group (`wing-mass-shape.md:47`, `wing_mass_model.py:185`,
`wing-jettison.md:111`) is the one where the wrong figure is load-bearing rather than merely
tabulated: `R0 = 11 mm` is half of 22 mm. On a 55 × 45 mm hub there is no single half-edge and
`R0` becomes direction-dependent (`TODO(unverified)` — no repo source re-derives it).

### 6.2 Leaning on **55.15 × 45.15 mm** (the current figure)

| File:line | What it does with the figure |
|---|---|
| `docs/POWER-BUDGET-V9-D2BE.md:166,172` | Hub mass line: 2.76 g bare FR4; the 0.6 mm thickness is taken from `hub_board_v1_clean.kicad_pcb` (which is itself 50 × 40, §2.2 — dimension and thickness come from *different* sources in that sentence) |
| `docs/analysis/two-variant-mass-budget.md:150,221` | Row A1/B1: `Hub PCB, 55.15 × 45.15 × 0.6 mm FR4 \| 2.76` in both variants |
| `docs/analysis/two-variant-mass-budget.md:265` | the "shrink the board" lever: 0.4 mm at same outline = 2.12 g (−0.64 g); a 30 × 30 mm board = 1.04 g |
| `docs/analysis/two_variant_mass_model.py:35` | `HUB_BIG_MM2 = 55.15 * 45.15   # [REPO] POWER-BUDGET-V9-D2BE.md §4 (ADR-029)` |
| `docs/analysis/wing-mass-shape.md:555` | `FR4 (2.76 g for the 55.15 × 45.15 mm v8i)`; same paragraph says the v9 outline is unfixed |
| `docs/analysis/mppt-charge-path-specification.md:370,604` | "The v9 flight board is **55.15 × 45.15 mm** (ADR-029, via POWER-BUDGET §4)" |
| `docs/analysis/array-power-architecture.md:438,653` | same citation |
| `docs/adr/029-dual-band-flight-board.md:42,47,199,297,365,378,423,621,655,664` | v9 fits on `55 x 45` — the whole coexistence plan is argued against this outline |
| `docs/adr/040-v9-radio-site-optionality.md:164` | two F33 do not fit on 55 × 45 |
| `docs/adr/030-deterministic-zero-inference-pcb-pipeline.md:45` | 55×45 listed among the tried outlines |
| `tracker/hardware/C3-SIGNOFF.md:156,165` | `.gbrjob Size: 55.15 × 45.15`; "not the 50 × 40 mm the plan §3.2 specifies" |
| `docs/COEXISTENCE-V9.md:4,56,119` | the coexistence memo itself: "4-layer 55x45" |
| `docs/V9-RADIO-SITE-MATRIX.md` (companion to ADR-040) | inherits ADR-040's 55 × 45 constraint implicitly |

### 6.3 Statements that name the contradiction without resolving it

| File:line | Wording |
|---|---|
| `docs/analysis/two-variant-mass-budget.md:468–473` | "The repo contradicts itself: … 22 × 22 mm … while … 55.15 × 45.15 mm … — a **5.9×** PCB-mass difference … This alone moves both variants' totals by up to ~2.6 g." |
| `docs/analysis/wing-mass-shape.md:556` | `the v9 hub outline is unfixed (ADR-048 §5 item 5)` |
| `docs/adr/048-v9-hub-wing-interfaces.md:265,287` | `**No v9 hub PCB exists**` / `no v9 hub outline exists to check against` |
| `docs/adr/051-hub-array-and-cut-topology.md:206` | `The v9 hub has **no drawn outline**` |

---

## 7. Open questions

1. **`TODO(unverified)` — ADR-051's array-growth ratio.** `docs/adr/051-hub-array-and-cut-topology.md:369`
   computes 12.6× … 21.9× against 4.84 cm². Against the real 24.90 cm² (55.15 × 45.15) the same
   numerators give **2.46× … 4.26×** (`[COMPUTED]` 61.2/24.90 = 2.46; 106.1/24.90 = 4.26). ADR-051
   is **Proposed**, and its sizing figures are recorded as **uncommitted**:
   `docs/analysis/two-variant-mass-budget.md:476–478` — "the only in-repo artefact is an
   **uncommitted** gate script in a local worktree; its 65 cm² / 33 cm² sizing … are **not
   committed**". What would resolve it: commit that gate script, or an operator statement of which
   baseline ADR-051 intends to grow from.
2. **`TODO(unverified)` — whether the v9 hub stays 55 × 45 or grows.** ADR-051 line 363 proposes
   the growth and line 371 sizes it at ≈90 × 90 … ≈115 × 115 mm; ADR-029 (also Proposed) fixes
   55 × 45. Both cannot describe the same board. What would resolve it: a drawn v9 hub
   `.kicad_pcb`, which does not exist on `main`.
3. **`TODO(unverified)` — the v9 hub layer count and thickness.**
   `docs/adr/048-v9-hub-wing-interfaces.md:267–269` (item 5): "whether the hub is 2-layer or 4-layer,
   and therefore whether the hub and the wing can share one panel, is undecided." Note the current
   0.6 mm figure is cited from `hub_board_v1_clean.kicad_pcb` (`POWER-BUDGET-V9-D2BE.md:166–167`),
   which is a **50 × 40 mm, 2-layer** v1 board — the thickness may not carry either.
4. **`TODO(unverified)` — whether a 22 × 22 mm hub ever existed as a drawn artifact.** No file in
   `main` draws it; every drawn v1 hub is 45 × 38, 50 × 40 or 75 × 55. What would resolve it:
   `git log --all --name-only` over `*.kicad_pcb` on unmerged branches, or an operator statement
   that the 22 mm figure was always conceptual. **This audit checked `main` only.**
5. **`TODO(unverified)` — the ADR-029 "55 x 45" vs the v8h 55.15 × 45.15 in the same §Context.**
   This audit resolves it as a stroke-envelope difference (§2.1); ADR-029 does not itself say so.
   What would confirm it: a statement in ADR-029, or the `kicad-cli pcb export gerbers` job file
   for v8h (present at `tracker/hardware/output/gerbers_v8h/v8h_krt_u2_lora2021-job.gbrjob:17`,
   `"X": 55.15`).

---

## 8. Summary (one paragraph)

The v9 flight board's authoritative outline figure is **55 × 45 mm — quoted as 55.15 × 45.15 mm
because that is the same rectangle plus its 0.15 mm Edge.Cuts stroke** — encoded in every generated
flight board (`tracker/hardware/output/v8i_krt_gnss.kicad_pcb:8136–8144` and siblings) and ratified
for v9 in `docs/adr/029-dual-band-flight-board.md:42/47`. The **22 × 22 mm** figure is stale prose
from `docs/hardware-design.md:13` (2026-05-20, v1 concept with an FEM and an ESP32-C3 that v9 has
dropped), is drawn by no artifact, and is quoted as "inherited"/"no drawn outline" by the very
records that cite it. The socket/insertion-depth/slot-interference numbers in ADR-046 and ADR-048
were derived against the 22 mm datum and must be re-derived on any outline change; the v9 hub
outline itself remains `TODO(unverified)` because no v9 hub PCB exists.

---

*Analysis only. No design decision changed, no number re-frozen, nothing ordered.*
*Evidence gathered from `main` @ `61e932b` in worktree `~/worktrees/bf-outline`, branch
`analysis/hub-outline-authority`.*
