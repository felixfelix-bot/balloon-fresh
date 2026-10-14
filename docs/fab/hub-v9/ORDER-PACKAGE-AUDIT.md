# ORDER PACKAGE AUDIT — two `✅` items in the pre-order checklist are FALSE

**Date:** 2026-10-14 · **Status:** ⚠ **ORDER-BLOCKING.** Operator must know before paying.
**Found during:** the edge-clearance route work (an incidental measurement).

---

## 0. Headline

The pre-order checklist claims the gerbers and the upload ZIP are **done**. **Neither
exists.** Measured:

| checklist claim | measured reality |
|---|---|
| `C1 | Gerbers **re-exported at 0.8 mm** | ✅ docs/fab/hub-v9/gerbers-0.8mm/` | **directory MISSING** |
| `C6 | Zip prepared for upload | ✅ ~/jlc-quote-inputs/hub_v9_0.8mm.zip` | **file MISSING**, dir **MISSING** |

```
ls docs/fab/hub-v9/gerbers-0.8mm        -> No such file or directory
ls docs/fab/hub-v9/gerbers              -> No such file or directory
ls ~/jlc-quote-inputs                   -> No such file or directory
```

**There is no gerber export on this machine.** The package that would be uploaded to
JLCPCB **does not exist.**

## 1. And the thickness claim is also false

The checklist says at A1: *"⬜ OPEN — **file fixed to 0.8**, must be chosen at order time"*.

**Measured:** the v9 board files are **`thickness 0.6`**, not 0.8:

| file | thickness |
|---|---|
| `tracker/hardware/seed` | **0.6** |
| `tracker/hardware/hub_board_v9.kicad_pcb` | **0.6** |
| `tracker/hardware/fg_in_filled.kicad_pcb` (the graded, routed board) | **0.6** |

The only file in the tree at 0.8 is `hub_board_f33.kicad_pcb` — **a different board**, not
the v9 hub. **So "file fixed to 0.8" is wrong: the file was never changed.**

**Why this matters, and it is not fatal:** gerbers **do not carry board thickness**, so
0.6 in the file cannot be mis-manufactured — the **order form** is the only place thickness
is set, and the checklist's A1 correctly says to select **0.8 mm** there (0.8 is JLCPCB's
**4-layer minimum**; 0.6 mm is 2-layer only). **But the stated reason for the action is
false**, which means anyone re-reading the checklist would trust a "fixed" file that is not
fixed.

## 2. What this does NOT mean

- **The routed board itself is sound.** 48/48 nets, 0 unconnected, JLC-legal geometry.
- **The thickness decision is correct** (0.8 mm on the form).
- This is **not** a board defect. It is a **documentation/reality drift** in the order
  package — the same class as the stale zone-fill and the stale gerber ZIP this campaign
  caught before.

## 3. The fix (mechanical, and I should just do it)

1. **Set the board thickness to 0.8 mm in the board file** so the file matches the decision
   (belt-and-braces; the form still governs).
2. **Export the gerbers** from the verified routed board and record the **sha256**.
3. **Build the upload ZIP** and record its sha256.
4. **Correct the checklist** so every `✅` corresponds to a file that exists, and the
   audit method is recorded (a `✅` that cannot be re-derived is worse than `⬜`).

## 4. The lesson — the fourth instance of one failure mode

This campaign has now caught **four** cases of an **artifact and its derived state drifting
apart**:

| # | what looked done | what was true |
|---|---|---|
| 1 | DRC report green | graded against a **stale zone fill** |
| 2 | gerber ZIP existed | ZIP was **stale** vs the routed board |
| 3 | `U1` footprint "defective" | **my own counting error** |
| 4 | **gerbers + ZIP `✅` in the checklist** | **neither file exists** |

**Common cause: a status recorded once and never re-derived.** The guard that catches all
four is the same: **verify the artefact exists and re-derive its hash immediately before
trusting it** — and never write a `✅` without recording the command that reproduces it.

## 5. Reproduce

```
cd tracker/hardware
grep -m1 thickness seed hub_board_v9.kicad_pcb fg_in_filled.kicad_pcb   # all 0.6
ls ../../docs/fab/hub-v9/gerbers-0.8mm                                  # No such file
ls ~/jlc-quote-inputs                                                   # No such file
```
