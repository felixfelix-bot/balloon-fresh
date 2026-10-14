# Panel mounting: off-board, back-to-back, lamination, thin film — answered from existing evidence

**Date:** 2026-10-14 · **Status:** analysis, no freeze
**Operator question (verbatim):** *"would a thin film solar panel or a flexible solarpanel help
reduce our concerns about panels cracking due to temperature cycles and the need for circuit
boards backing the panels? Can we reduce our circuit board surface area then by just having thin
film panels hang from the board rather than having solid panels soldered to the board with the
board providing rigid structure?"*

## 0. The short answer

**Yes to the second question, and it is the right instinct — but it is INDEPENDENT of the
thin-film choice.** Our own survey (`docs/analysis/pico-balloon-solar-survey.md`, 524 lines,
every figure sourced) already recommends **mounting cells at their ENDS ONLY and not bonding them
to any substrate**. Nobody in the pico-balloon community bonds cells to a board. So the board does
**not** need to provide rigid structure, and **its area can be reclaimed** — with either cell class.

On thin film specifically: **it fixes the cracking worry, but at 1.9× worse W/g and 5.4× the area.**
Keep bare silicon as the primary array; use an encapsulated module only where robustness or low
sun angle is the binding constraint — which is exactly what the leading community designs do.

## 1. "Do we even need the board to back the panels?" — NO

The survey found that **no balloon source bonds cells to a substrate**, and the one that explains
why cites **thermal contraction, not vacuum**:

> KC9IKB attaches only the array ends *"so the cells can 'float' and contract a certain amount"*
> — and names the thermal mechanism: *"the temperature change between the assembly area and the
> cold at 40,000 feet + may crack a cell"*.

Both community patterns mount end-only, with **no bonded substrate**:

| Pattern | How the cells are held | Source |
|---|---|---|
| Traquito PCB sandwich | soldered by their **ends** through a PCB | Traquito guide |
| NIBBB foam frame | glued **corners only** | NIBBB |
| ZachTek | *"soldered in to a slot"* — no bonded substrate | ZachTek blog |
| KS4VA PowerFilm | clamped/soldered to a PCB **spreader**; the PCB is a *carrier*, not a bonded backing | KS4VA |

**The decisive point for our design:** the survey is explicit that **ADR-049's bonded-and-vented
substrate is *"not something any pico-balloon source in this survey does."** Our current hub
concept inherits that CubeSat-derived bond, and the evidence says drop it.

## 2. "Does it cost mass to hang them instead of backing them?" — Almost nothing

This is the number that usually kills the idea, and here it does not:

> NIBBB's measured array is **4.5–4.7 g** for **7 cells** of which the silicon is **≈3.5 g** —
> so the *entire* frame + glue + tape + 30 AWG wiring + solder is **≈1.0–1.2 g**, i.e.
> **≈0.15 g per cell**.

Our own **ADR-049 spine-and-ribs frame is already in that class** (12.846 g array, 0.187 W/g).
**So the mounting overhead in the balloon world is ~0.15 g/cell; there is essentially nothing to
save by changing the structure, and nothing to lose by getting the panels off the board.**

## 3. Thin film vs bare silicon — the numbers

| | Bare poly-Si (ours, measured) | Flexible thin film (PowerFilm MPT6-150, vendor) |
|---|---|---|
| Efficiency | **≈19.6 %** | **≈3.6 %** |
| W/g | **0.400** | 0.212 → **silicon wins 1.9×** |
| mg/cm² | 48.9 | **17.0 → thin film wins 2.9×** |
| Robustness | *"extremely fragile"*; *"Cracking … is par for the course"* | **"super durable and don't break"** — thin film wins decisively |
| Assembly | *"very tricky to solder to"*; 0.5 V/cell → many joints | solder into a slot; plastic need not be removed |
| Low sun angle | poor flat | PowerFilm good in indirect light; NIBBB's thin-film prism fires at **1.8°** elevation |

**And the area penalty is the killer.** To replace **7.2 W** from **367 cm²** of bare silicon:

> **12 × MPT6-150 = 33.96 g and 1997 cm²** — heavier than the cells it replaces *before* any frame,
> and **5.4× the area**, which is unaffordable structurally and aerodynamically at a 20–40 g payload.

So thin film is **3–4× heavier** for the same power in NIBBB's own words, and costs 5.4× the area.

## 4. Back-to-back and lamination — assessed against this evidence

- **Back-to-back:** two bonded wafers behave as a sandwich about a shared neutral axis, and bending
  stiffness scales roughly with *t³*, so the pair is much stiffer than two singles. **But** it
  **halves the collecting area per face**, and at altitude there is no albedo worth harvesting from
  below. It also **re-introduces the bond** the evidence says to avoid. **Verdict: a real
  stiffness win, the wrong trade for us.**
- **Lamination in plastic:** the survey found **no** balloon source laminating cells, and the only
  coating advice anywhere is Project:Traveler's **optional** conformal coat — **on the board, not
  over the cells**. Any coverglass would be **50–100× the cell's own mass** and is **not in evidence
  anywhere in this class**. **Verdict: not supported by the evidence; do not add.**
- **The honest gap:** there is **no measured allowable** for our cells. The unsupported-span model
  gives a **cantilever stress of 2.01 MPa and 174 µm deflection** for a 78.55 mm LARGE cell at 1g,
  and the repo records **no flexural strength / modulus of rupture** for the operator's cell.
  **So "is 2.01 MPa safe?" is currently unknown** — and that single number decides how far a cell
  may overhang.

## 5. Recommendation

1. **Take the panels OFF the board — with either cell class.** Mount the 434 MHz/array cells
   **end-only, no bond**, per the community pattern. This reclaims board area, which is what the
   operator asked for, and it is what the evidence supports. **ADR-049's bonded substrate should be
   dropped**, and **ADR-063's overhang direction (board sized by components, array on a separate
   carrier) is confirmed by this evidence as the right architecture.**
2. **Keep bare silicon as the primary array** (1.9× better W/g, 1/5.4 the area). Do **not** switch
   the array to thin film.
3. **Use thin film only surgically** — one encapsulated module as a **low-sun-angle blade** for
   winter launches (the NIBBB mixed strategy), where robustness and low-angle collection are the
   binding constraint. Not the whole array.
4. **One Schottky per parallel string** (ADR-049 already requires ≥2 A / 40 V; the community uses
   `1N5817` ×3 or 3 SMD Schottkys to isolate dark panels).
5. **Run the two bench tests that close the open numbers** — both cheap, both decisive:
   - **Coupon bend test** on a scrap cell → gives the missing allowable and settles how far a cell
     may overhang.
   - **Cold-soak + thermal cycle** a soldered cell string to ≈−55 °C → tests whether the
     *hand-soldered joints* survive, which is the untested failure mode (not the cell itself).

## 6. What this changes for the hub board

**Board area becomes a component-only number.** With the array off the board, the outline follows
the **measured component courtyard (2582 mm²)** — a **~60 × 60 mm** board at 72 % packing — not the
103 × 103 mm array-sized square.

| Outline | Area | 0.6 mm mass | JLCPCB tier |
|---|---:|---:|---|
| **60 × 60 mm** | 36.0 cm² | **4.60 g** | cheap (≤102 mm) |
| 65 × 65 mm | 42.3 cm² | 5.39 g | cheap |
| 70 × 70 mm | 49.0 cm² | 6.26 g | cheap |
| 103 × 103 mm (array-sized) | 106.1 cm² | 13.54 g | **over the 102 mm cliff ($31.60 vs $8)** |

**That is ~2.9× less board mass and a 4× cheaper board**, and it removes the 104 % oversubscription
that currently blocks the hub from routing. The 2582 mm² "problem" was self-inflicted by sizing the
board to the array.

## 7. Provenance

- `docs/analysis/pico-balloon-solar-survey.md` — the 524-line, fully-sourced survey this rests on
  (§2.2 flexible modules, §2.3 potting, §3.3 the deciding numbers, §5 thin film vs silicon,
  §6 nine real failure reports, §7 recommendation, §7.1 the open bench tests).
- `docs/analysis/hub-array-overhang-and-support.md` + `hub_array_overhang_model.py` — the
  overhang/span model and the mass table (`python3 hub_array_overhang_model.py`).
- **ADR-063** — *"Hub board area and array area are DECOUPLED: panels may overhang, the outline
  follows the components, and the array rides a separate carrier."* Operator direction verbatim
  2026-10-08: *"I'm fine with panels overhang[ing] the board. No need to waste board space."*
- **ADR-049** (spine-and-ribs frame; the bonded-and-vented substrate this recommends dropping),
  **ADR-052** (bare cells mounted end-only, no bond — already consistent with the evidence).
- **UNVERIFIED, and said so:** no datasheet flexural strength for the operator's cell; no
  balloon-world measurement of this exact cell class in a flown array; whether hand-soldered joints
  survive −50 °C is untested; the NIBBB "40 mA vs 400 mA" conflict is unresolved.
