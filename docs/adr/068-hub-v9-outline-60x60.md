# ADR-068 — The hub v9 outline is 70 × 70 mm, sized by COMPONENTS

> **REVISED 2026-10-14 (same day, by measurement): the figure is 70 × 70 mm, not
> 60 × 60 mm.** The principle below — *sized by components, not by the array* — is
> **unchanged and confirmed**. The number moved because the 60 mm figure came from
> **aggregate courtyard arithmetic**, which cannot see that a single
> **39.65 × 22.30 mm** body (`U2`, the `LoRa2021F33-2G4`) wastes more area than its
> own footprint implies. **Measured (`tracker/hardware/seat_probe.py`):** 60 × 60
> overflows `U2`; **65 × 65 overflows `U5` instead** (a trap — it moves the problem,
> it does not solve it); **70 × 70 seats all 39 parts with no overflow** and routes
> **48/48 nets, 148/148 pads, zero open**. See
> `docs/fab/hub-v9/SEAT-PROBE-RESULT.md`. Cost: +1.66 g (4.60 → 6.26 g), still far
> inside JLCPCB's 102 mm cheap tier, so this record's cheap-tier and decoupling
> arguments are unaffected.
>
> **Honest correction to the text below:** §1.3's claim that "103 × 103 and 60 × 60
> route the SAME net count (43/49), so the shrink is routing-neutral" was true *as
> measured* — but it was measured with `U2` **parked at the board origin** by the
> unplaceable-part defect fixed later in `de8e05d1`. Once that defect was fixed the
> comparison inverted: **60 × 60 caps at 43/44; 70 × 70 reaches 48/48.**

> Numbered **068** on 2026-10-14 by `scripts/adr_next_number.py` → `68` (exit 0).
> The allocator's failure path was checked in the same run: the number is not
> hard-coded past this allocation and no file is renamed.

- Status: **Proposed** — the *direction* is the operator's and was given
  **explicitly on 2026-10-14**: *"1. The outline — 60×60 is my recommendation;
  65 or 70 mm also seat. yes please do that."* The **text** is not
  human-accepted; per the ADR-first rule (ADR-029 §Context) no BOM freeze,
  placement freeze or fabrication may treat it as frozen until a human accepts it.
- Date: 2026-10-14
- Decision owner: Felix (operator). The direction is his; the text is not accepted.
- Author: subagent (Hermes), branch `master` lineage, worktree `~/worktrees/v9-route`.
- Amends: **ADR-055 D5** (the 103 × 103 mm array-sized square — **superseded as the
  outline**, see §3), **ADR-051 §2.3** ("the hub outline must grow … a FORM-FACTOR
  CHANGE" — the *growth* is **superseded**, the *decoupling* is **adopted**).
- Executes: **ADR-063** ("Hub board area and array area are DECOUPLED: panels may
  overhang, the outline follows the components, and the array rides a separate
  carrier"), whose direction the operator gave verbatim on 2026-10-08:
  *"I'm fine with panels overhang[ing] the board. No need to waste board space."*
- Evidence: `docs/analysis/PANEL-MOUNTING-OFF-BOARD.md`,
  `docs/fab/hub-v9/COMPONENT-FLOOR-OUTLINE-RESULT.md`,
  `docs/analysis/hub_array_overhang_model.py` (run it: every figure below is its output),
  `docs/analysis/hub-outline-authority.md`, `docs/analysis/jlcpcb-pricing-and-size-tier.md`.
- **No hardware is ordered by this record. No board is re-placed, re-routed or generated.**

---

## 0. The decision, in one paragraph

**The v9 hub outline is 60 × 60 mm**, 4-layer, sized by its **measured component
courtyard (2582 mm²)**, not by its solar array. The array is carried on a separate
overhanging carrier (ADR-063) and contributes **zero** board area. This is a
**resident of the existing generator** — `build_hub_board_v9.py --outline 60x60` —
not a rework, and it was measured through the full chain before being proposed.

## 1. Why, with the numbers

### 1.1 The component floor (the binding constraint)

Measured component courtyard demand: **2582 mm² (25.82 cm²)**. The model's own
packing arithmetic:

| Packing | Required board | Square |
|---|---:|---:|
| 72 % | 3586 mm² = 35.86 cm² | **59.9 mm** |
| 75 % | 3443 mm² = 34.43 cm² | 58.7 mm |
| 80 % | 3228 mm² = 32.27 cm² | 56.8 mm |

Plus the four socket land rows (4 interfaces × 8 lands × 4.0 × 1.2 mm = 154 mm²)
and the 1.0–5.0 mm inboard keep-out band. **60 × 60 mm = 36.00 cm² clears the 72 %
figure with margin and is the operator's chosen value.**

### 1.2 The array-sized outline is superseded, and it was arithmetically unsatisfiable

ADR-055 D5 chose 103 × 103 mm = 106.09 cm² for exactly one reason — to fit a
106.1 cm² full-duty horizontal array. **That board could not hold the cells it was
sized for**: a LARGE cell is 78.55 × 38.90 mm, and only **2** fit a 103 × 103 square
= 61.11 cm² = **58 %** of the target. The outline was therefore sized for an array
that would not have fit on it, *and* at 103 mm it sits **over JLCPCB's 102 mm
cheap-tier cliff** (measured: 103 mm 4-layer = **$31.60** vs 102 mm = **$8.00**).

### 1.3 The resize is a decisive cost and mass win — and it does NOT harm routing

| Outline | Area | 0.6 mm mass | Tier |
|---|---:|---:|---|
| **60 × 60 mm** | 36.0 cm² | **4.60 g** | cheap (≤ 102 mm) |
| 65 × 65 mm | 42.3 cm² | 5.39 g | cheap |
| 70 × 70 mm | 49.0 cm² | 6.26 g | cheap |
| 103 × 103 mm (array-sized) | 106.1 cm² | 13.54 g | **over the cliff** |

**≈2.9× less board mass and a 4× cheaper board.**

Crucially, this was **tested, not assumed**. The same net count routes at both
outlines — **43/49** — so the shrink is demonstrably **routing-neutral**:

> `docs/fab/hub-v9/COMPONENT-FLOOR-OUTLINE-RESULT.md` — 103 × 103 and 60 × 60 both
> route 43/49 nets, with the **same six** nets failing. The earlier reading that the
> 2582 mm² oversubscription was *the* routing blocker was **incomplete**: the actual
> blocker was the wing-socket seat (16 pads off-board, fixed separately in
> commit `1be08238`), which failed **identically on every outline**.

## 2. What is NOT decided by this record

- **The trigger mode for the wing cutters** (ADR-051 §2.5 item 7) stays open.
- **`OPEN-25`** — the cut-sense GPIO/divider choice and values — stays open.
- **The five `TODO(unverified)` parts** (`U_CUT1–4`, `U_HUB_CVT`) are **not** decided
  here; until they are selected the BOM cannot complete and **no order can be placed**.
- **The array carrier's geometry** (rib pitch, unsupported span) is not frozen here;
  the missing flexural allowable is still a bench measurement
  (`docs/analysis/PANEL-MOUNTING-OFF-BOARD.md` §6).

## 3. Supersession, stated so no reader picks a side silently

| Record | Prior content | Effect of this record |
|---|---|---|
| **ADR-055 D5** | outline = 103 × 103 mm, `√106.1 cm²` | **SUPERSEDED** as the outline figure. The *decoupling principle* survives. |
| **ADR-051 §2.3** | "the hub outline must grow … a FORM-FACTOR CHANGE" | **SUPERSEDED** on the growth; **ADOPTED** on decoupling board area from array area. |
| **ADR-063** | board sized by components; panels overhang | **EXECUTED** — this record supplies the number ADR-063 deliberately left open. |
| `docs/analysis/hub-outline-authority.md` | 55 × 45 mm as of v8h | **Still true for v8h**; v9 is this record's 60 × 60. |

**55 × 45 mm was rejected on measurement**: its usable interior is 2279 mm² against a
2582 mm² demand — **96.7 % packing, which fails**. It is recorded here as a rejected
candidate, not a live option.

## 4. Consequences

1. `build_hub_board_v9.py`'s `DEFAULT_W/DEFAULT_H` must move from **103.0/103.0** to
   **60.0/60.0** so the default matches the authority. Until then the 60 × 60 result
   is reachable only by `--outline 60x60`, and a default run silently produces a
   superseded board. **This is a defect until fixed.**
2. Any record still asserting 103 × 103 mm as the v9 outline is **stale by
   definition** (per the repo's single-source-of-truth rule).
3. The hub-array overhang carrier becomes the **only** owner of array area.

## 5. What would falsify this

- A measurement showing 60 × 60 cannot seat the 39 placeable components at ≥ 72 %
  packing (it seats today, so this would require a component-count change).
- The wing-socket lands not clearing the edge at 60 × 60 — **measured OK**; 16
  off-board pads were found at 60 × 60 and **fixed** (`1be08238`), and
  `tracker/hardware/check_wing_seat.py` now gates it (0 off-board).
- A JLCPCB price at 60 × 60 that beats a larger board (not expected; the tier is
  per-board-area).
