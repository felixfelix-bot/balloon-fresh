# HUB v9 — PRE-ORDER CHECKLIST

**Created:** 2026-10-14 · **Status:** not yet orderable — open blockers below
**Rule:** an order is placed by the operator (Felix) manually. The agent verifies
the packet and the price; it never places the order.

---

## A. BLOCKING — must be cleared before the order goes in

| # | Item | Why it blocks | State |
|---|------|---------------|-------|
| A1 | **Stackup: select 0.8 mm on the order form** | ⬜ OPEN — **and the earlier claim that the "file fixed to 0.8" is FALSE:** measured 2026-10-14, `seed`, `hub_board_v9.kicad_pcb` and the graded `fg_in_filled.kicad_pcb` all still say **`thickness 0.6`**. Gerbers do **not** carry thickness, so 0.6 in the file **cannot** be mis-manufactured and the form is the only place thickness is set — but the stated reason was wrong. See `ORDER-PACKAGE-AUDIT.md`. |
| A2 | **Re-price at 0.8 mm 4-layer** | The captured quote was a page default (~1.6 mm). Every total so far is a *lower bound* on the PCB line. | ⬜ OPEN |
| A3 | **Flight mass budget reconciled** | Payload ~57 g vs the stale `<14 g` doc. The 32-inch chloroprene sphere **cannot** reach 12 km at any payload — envelope decision pending (latex research in flight). | ⬜ OPEN — see `docs/analysis/ALTITUDE-AND-MASS-REQUIREMENTS.md` |
| A4 | **Per-placement assembly fee measured** | Only the $25/side setup fee is captured. Per-placement adds are unknown → all order totals are **lower bounds**. | ⬜ OPEN |
| A5 | **Envelope choice locked** | 32-inch chloroprene floats only 6.4–9.5 km. 36-inch latex (~25 g) modelled at 12–13 km. Literature check in progress. | ⬜ OPEN |
| A6 | **EN pull-up decided** | EN is **absent from the netlist** (no pull-up). Boot reliability depends on the module's internal EN pull-up — unverified. Either accept + verify on first article, or add R in rev-10. | ⬜ OPEN |

## B. ORDER-FORM SETTINGS (copy these exactly)

| Setting | Value | Source |
|---|---|---|
| Layers | 4 | board design |
| Thickness | **0.8 mm** | JLC 4-layer minimum (0.6 mm is 2-layer only) |
| Surface finish | ENIG | U.FL + fine pitch |
| Via treatment | **Epoxy filled & capped** | operator standing preference |
| Assembly | 1 variant, platform populated on all 10 | no baro; GPS as DNP rows + 4 loose |
| Quantity | 10 | order split locked (`a8c10205`) |
| Qty-10 note | ICs cliff at qty 10 (−$2.11/board) | measured |

## C. PACKET CONTENTS (verify the zip before uploading)

> **⚠ AUDITED 2026-10-14 — the C-row `✅`s below were FALSE and are corrected.**
> `docs/fab/hub-v9/gerbers-0.8mm/` **does not exist**, `~/jlc-quote-inputs/` **does not
> exist**, and no gerber export exists on this machine. See
> `docs/fab/hub-v9/ORDER-PACKAGE-AUDIT.md`. **A `✅` that cannot be re-derived is worse than
> a `⬜`** — so each row now carries the command that proves it.

| # | Item | State |
|---|------|-------|
| C1 | Gerbers **exported at 0.8 mm** | ✅ `gerbers/` — 14 gerber/drill/job files (4 Cu, paste, silk, mask, Edge.Cuts, PTH+NPTH drill, .gbrjob), exported from the verified routed board at thickness 0.8 |
| C2 | Drill files in the same zip | ✅ `hub_v9-PTH.drl` (3 tools, **189 holes**) + `hub_v9-NPTH.drl`, in the zip |
| C3 | BOM: single-variant platform, GPS + baro as **DNP rows** | ✅ **NOW REAL** — `gerbers/hub_v9-bom-jlc.csv`, 23 lines (14 to assemble), built from live-API LCSC numbers and **verified consistent with the board** (`verify_bom_against_board.py`: 0 missing, 0 extra). DNP rows for the 12 hand-install/not-stocked parts incl. U5/U6 per the locked split. |
| C4 | CPL / positions matching the BOM | ✅ `gerbers/hub_v9-cpl.csv` — 36 placements, **U1 present**, U5/U6 excluded. **NOTE: export with `--exclude-dnp`, NEVER `--exclude-fp-th` (that flag silently drops U1, the MCU).** |
| C5 | GPS add-on line: **4× MAX-M10S loose** | ⬜ **NOT DONE** — separate CSV not yet produced |
| C6 | Zip prepared for upload | ✅ `~/jlc-quote-inputs/hub_v9_0.8mm.zip` — 14 files; BOM + CPL sit beside it (`hub_v9-bom-jlc.csv`, `hub_v9-cpl.csv`) |

**Audit method (recorded so it can be re-derived):**
```
cd tracker/hardware
ls ../../docs/fab/hub-v9/gerbers*                      # gerber dir + bom + cpl
sha256sum ~/jlc-quote-inputs/hub_v9_0.8mm.zip          # recorded hash
~/venvs/kicad/bin/python verify_bom_against_board.py   # BOM <-> board consistency, exit 0
```


## C2. WING v9 PACKET (the second board — added 2026-10-14)

| # | Item | State |
|---|------|-------|
| W1 | Wing routes / electrical completeness | ✅ **0 unconnected items**, 28 tracks on 4 solar nets |
| W2 | Wing DRC | ✅ 37 items, **all artifact or clip-not-reject**; the 2 `track_dangling` **resolved** as legal taps (zero unshared-not-on-pad endpoints) |
| W3 | Wing thickness | ✅ **0.6 → 0.8 fixed** (`fix_wing_issues.py`); the export script's own comment said "0.6 mm" and was stale too |
| W4 | `FB1` / `RF1` DNP | ✅ **fixed** — said DNP in the value TEXT only; flags now True, so a CPL generator will not try to place v2-only parts on a v1 board |
| W5 | Wing gerbers + drill | ✅ `output/gerbers_wing_v9_jlcpcb.zip`, PTH 8 holes / NPTH 3 holes |
| W6 | Wing zip sha256 | ✅ `5e36d1cd1a88a71a6a32c656faa5e45b46ee2099c6ea546c998822a9503aa1c3` |
| W7 | Wing BOM/CPL | ✅ **correctly absent** — no purchasable non-DNP part exists on the wing |

See `docs/fab/hub-v9/WING-V9-PACKAGE-AUDIT.md`.

## D. KNOWN ACCEPTED RISKS (do not re-litigate; log them)

- **Cold:** all ICs are −40 °C rated; 7–9 km float ambient is ≈ −40…−50 °C (a 12 km float would be colder). Accepted, to be **measured** in flight via the NTC sense lines.
- **U.FL edge proximity:** all four connectors are **2.5 mm** pad-centre to edge. Not a fab problem; mitigations = right-angle pigtails zip-tied 10 mm from the connector, mate on the bare bench, 1 spare board per 10.
- **Wing tabs / 2 mounting holes:** both holes at **x = 9.425** → the board is pinned along one edge and the far half cantilevers. Mitigations = thread/kevlar through both holes + a third soft tie, epoxy-fillet the holes, soft washer.
- **Supercap DNP:** no buffer for TX bursts at dawn/dusk → cold-start untested (E-CS1…6 planned).
- **Night descent:** floats cool and drop; not yet characterised (E-06).

## E. BENCH MEASUREMENTS NEEDED FROM THE OPERATOR (with calipers / scale)

Not on the internet — these change the flight answer.

| # | What | Why it matters | Method | State |
|---|---|---|---|---|
| E1 | **Empty balloon mass** | Decides float altitude (±1.5 km between the 60 g and 100 g bounds) and whether chloroprene can work at all | lab scale, one balloon | ✅ **46.84 g** (2026-10-14) |
| E2 | **One 52×19 mm solar cell mass** | 12 cells; 0.8 vs 1.6 g = 9.6 g swing, comparable to all hub components | lab scale | ✅ **0.4462 g** small / **1.4040 g** large (2026-10-14) |
| E3 | **One latex balloon you intend to fly** (36 in / 40 in) | The 25 g @ 36 in figure is **modelled, not measured**; it sets float altitude directly | lab scale | ⬜ **NEEDED** |
| E4 | **Hub PCB thickness after receipt** | Confirms 0.8 mm actually shipped | calipers | ⬜ after delivery |
| E5 | **Wing PCB thickness after receipt** | 0.6 mm 2-layer is legal, but confirm | calipers | ⬜ after delivery |
| E6 | **Envelope inflated diameter** (the 32-in sphere often measures smaller) | Volume ∝ D³ — a 5 % diameter error is ~16 % volume | tape, on a filled envelope | ⬜ NEEDED |
| E7 | **Fill fraction that just floats the payload** | Gives the real free-lift margin | bench: fill, weigh net lift | ⬜ NEEDED |

## F. TOOLING EVIDENCE (added 2026-10-14)

- `docs/analysis/lr2021-bench-audit-2026-10-14.md` — LR2021 receive-only audit on real silicon
- `ansible/e80-lr2021-audit.yml` — provision a host to run the audits
- `make lr2021-audit` / `make lorawan-plan-audit` — reproducible runners

## G. ORDER-DAY PROCEDURE

1. Clear **every** A-item (or record an explicit operator waiver for it).
2. Verify the packet table (C) against the uploaded zip — hash the zip.
3. Set the order-form values (B) **by hand**; never accept a page default.
4. Read the price back and compare against the model; note any delta ≥ 5 %.
5. Place the order (operator only). Record the order number + the final price.
6. On delivery: run E4/E5, then the first-article bring-up (see `esp32-s3-flash-*`).
