# REPORT — hub plate stiffness/deflection check (ADR-055 D4's 0.4 mm gate)

Branch `analysis/hub-thickness-deflection` · base `github/main` @ `8032cb4` ·
gitignored (`.gitignore:68`), force-added on this branch only — **not for main**.

## Verdict
**`cannot be settled from the record.`** The check D4 demands has now been run; it terminates
in a **named gap plus a named bench measurement**, not in a fabricated margin. D4's decision
(0.4 mm target) is **unchanged** — nothing in the check says 0.4 mm is inadequate for the
*global* plate load.

## The deciding number
**The end-only solder joint's allowable plate curvature / end-rotation `κ_damage` — which the
record does not contain.** The demand at 0.4 mm is a **343 µε** board surface strain at the
cell lands (1 g, end-only wings); the sourceable solder-allowable band gives **0.1–1 %** joint
shear strain. The demand maps to **0.18–0.53 %** (global-plate BC, *inside* the band) or
**0.92–2.75 %** (local-socket BC, *1.4–2.7× outside*). **The BC/model choice is the missing
input** — hence opposite verdicts from the same arithmetic.

## Load cases
| case | number | sourced? |
|---|---|---|
| a. static gravity, 1 g, 4×176 mm wings | wing root moment 1.685 mN·m/wing (end-only 1.95 g); plate deflection **0.340 mm @0.4 mm**, **0.101 mm @0.6 mm** (BC-A centre-post) | **sourced** masses/geometry; **BC ASSUMED** |
| b. rotation / centrifugal | **0.0056 g @6 rpm**; **1 g needs 80.1 rpm** | **bounded** (no rate in repo) |
| c. ascent / launch | aero drag 0.144 g-equiv @20 km (5 m/s, sourced); **≤2 g** bound vertical | **bounded** (no accel in repo) |
| d. thermal (−60 °C) | CTE mismatch **752–1232 µε** over a 78.55 mm cell; cold *stiffens* FR4 (+0–20 % E) | **ranged** (no in-repo CTE/modulus) |

## Robust findings
- **4.5 g CONFIRMED exactly: 4.514 g** (13.542 → 9.028 g @ 106.1 cm²).
- Lever price, exact: **3.375× deflection, 2.250× surface strain** (`1/t³`, `1/t²`).
- **Thermal is NOT a differentiator** — CTE mismatch is thickness-independent; cold helps stiffness.
- Binding item is **LOCAL** (the 9 mm wing tab on the plate edge), not global: 0.4 mm global
  deflection is 0.33 % of span (less than normal FR4 warpage).
- **Option (iii) 0.4 mm + 4 socket doublers (0.613 g)**: socket strain 343 → **86 µε**, *better
  than 0.6 mm's 152 µε*, still banking **3.90 g** — but **4 added hand joints** on a
  hand-soldered minimum-part-count payload, and no help to the global case.

## Options
| option | plate g | stiffening g | total g | deflection (BC-A) |
|---|---|---|---|---|
| (i) 0.6 mm plain | 13.542 | — | 13.542 | 0.101 mm |
| (ii) 0.4 mm plain | 9.028 | — | 9.028 | 0.340 mm |
| (iii) 0.4 mm + local stiffening | 9.028 | 0.613 | 9.641 | 0.340 mm (socket strain ÷4) |

## Bench measurement needed (one coupon settles it)
Solder one real cell end-only to a **0.4 mm FR4 coupon** with the real 4.0×1.2 mm land and hand
fillet; measure fillet height `h_j`, then bend to find **`κ_damage`** (first joint damage);
repeat at −55 °C. That yields `δ_allow,cell = κ_damage·L_cell²/8` and `γ_allow`, collapsing the
1–100 µm band to one number and giving a yes/no against the 258 µm (0.4 mm) / 76 µm (0.6 mm)
demands. Supporting: weigh the cell/wing/plate; **measure bare-panel flatness** (the *warpage*
half, no bend test covers it); **freeze the wing orientation** (`OPEN-23`, worth 7×).

## Files
- NEW `docs/analysis/hub-thickness-deflection.md` (analysis, full arithmetic)
- NEW `docs/analysis/hub_thickness_deflection_model.py` (committed model, in-repo convention)
- MOD `docs/adr/055-hub-geometry-final.md` (**section 8 appended**; body untouched)
- INDEX regenerated (byte-identical — appended section, no new number); `test_adr_numbering.py` 3 passed.

## Unsourced assumptions (all TODO(unverified))
FR4 modulus 18–24 GPa; FR4 cold-stiffening ×1.00–1.20; ν 0.15; FR4 in-plane CTE 12–18 ppm/K;
solder allowable shear strain 0.1–1 %; cell float gap / fillet height 0.05–0.15 mm; the plate
boundary condition; the electronics on-plate mass ~2 g; the hub cell count (2 vs 4 LARGE);
rotation rate; launch/release/drop acceleration; bare-panel warpage.

## Explicitly NOT established
No measurement of any part; the *stack-up*/fabricability half of Open item 3 (supplier question);
panel warpage; any electrical decision. **Order nothing. Freeze no thickness.**
