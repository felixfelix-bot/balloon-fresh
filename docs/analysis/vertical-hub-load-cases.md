# Vertical hub mounting: load-case analysis

**Status:** analysis only; does not replace ADR-063 D4. Reproduction: `python3 docs/analysis/vertical_hub_load_cases.py` (creates the figure beside this file).

## Scope and inputs

This compares an end-supported bare silicon cell in a horizontal panel with the same cell in a vertical panel. The cell is **78.55 x 38.90 x 0.21 mm**, the geometry recorded in ADR-063 §D4 and ADR-049. ADR-063 §D4 gives the measured/derived calibration **0.504 MPa at 1 g over 78.55 mm** and **1.007 MPa at 2 g**, for the simply-supported, end-only case. It explicitly says the allowable/flexural strength is not known and `S_crack` must be measured.

For calculations below, the existing in-repo model is used: `sigma = 3 rho g S^2/(4 t)`, with `rho = 2330 kg/m^3`, `t = 0.21 mm`, and `g = 9.80665 m/s^2` (`docs/analysis/hub_array_overhang_model.py`, lines 18–27 and 103–107). The model's 170 GPa Si modulus is only an in-repo standard value (`docs/analysis/hub-thickness-deflection.md` §3). The wider **130–170 GPa** range quoted in the task brief corresponds to standard single-crystal silicon values found in public engineering references (e.g. MatWeb's "Silicon" datasheet, Ioffe Institute NSM archive); **no URL is asserted here because none was fetched in this session — treat the range as `TODO(unverified)` until a datasheet is actually retrieved.** The CTE used here is **2.6e-6/K**, the standard room-temperature value for silicon (Ioffe NSM "Silicon - thermal expansion", `TODO(unverified)` — not fetched this session). If those references cannot be produced at design freeze, the material properties remain TODO(unverified), not design allowables.

The stress figures are **demand**, not strength. No sourceable silicon flexural strength or modulus of rupture exists in this repository; therefore no numeric span can honestly be called safe without the coupon.

## Coordinate convention

`theta` is the instantaneous angle by which the effective gravity vector is tilted out of its static direction toward the panel normal. For a horizontal panel, static gravity is transverse; for a vertical panel, static gravity is in-plane. The components are:

| case | horizontal panel: transverse / in-plane | vertical panel: transverse / in-plane |
|---|---:|---:|
| static | `1.000 g / 0 g` | `0 g / 1.000 g` |
| pendulum at angle `theta` | `cos(theta) g / sin(theta) g` | `sin(theta) g / cos(theta) g` |

This is a geometry result, not a claim about a measured flight swing amplitude.

## 1. Static self-weight bending (ADR-063 D4 case)

At any unsupported span `S`, the transverse bending stress is:

`σ_b = 3 rho g_perp S²/(4t) = 0.816 MPa * (S/100 mm)² * (g_perp/g)` (0.504 MPa at 78.55 mm, reproducing ADR-063).

At the 78.55 mm cell length, the ADR-063 calibration is 0.504 MPa per g transverse:

| mounting | transverse g | transverse bending at 78.55 mm | in-plane component |
|---|---:|---:|---:|
| horizontal, static | 1.000 | **0.504 MPa** | 0 |
| vertical, static | 0 | **0 MPa bending** | 1.000 g axial/plane load; bending not predicted by this beam equation |

The vertical orientation removes **this one static transverse term**. It does not establish a larger allowable pitch: the unknown `S_crack` is a failure boundary, not a stress number.

## 2. Pendulum swing — the hypothesis-breaking case

The repository documents a real payload pendulum model: a 241.3 mm chain has `T = 0.99 s`, and its swing is driven by balloon rotation, jetstream gusts and cut recoil (`docs/analysis/wing-ladder.md` §4.3 and §5). It does **not** provide a measured swing angle. Therefore the numeric angle below is an explicit **illustrative 30° case**, `TODO(unverified)` as a flight envelope.

At `theta = 30°`, `sin(theta)=0.500` and `cos(theta)=0.866`:

| mounting | transverse g | in-plane g | bending stress at 78.55 mm |
|---|---:|---:|---:|
| horizontal | `cos 30° = 0.866` | `sin 30° = 0.500` | **0.436 MPa** |
| vertical | `sin 30° = 0.500` | `cos 30° = 0.866` | **0.252 MPa** |

Thus vertical mounting halves the D4 bending demand in this **assumed** 30° swing, but does not make it zero. More generally, vertical-panel transverse stress is `0.504 sin(theta) MPa` at 78.55 mm. At 60° it is **0.436 MPa**; at 90° it is **0.504 MPa**, exactly the horizontal static demand. The number that kills the strong hypothesis is therefore **a 90° effective-gravity rotation reproduces 1 g transverse bending even when the panel is vertical**. Since no flight maximum `theta` is sourced, this is not a claim that 90° occurs; it proves orientation alone cannot remove the constraint.

If a coupon establishes `S_crack` at 1 g transverse, the pendulum-only vertical pitch scale is `S_crack / sqrt(sin(theta_max))`; at 30° this is **1.414 S_crack**, at 60° **1.075 S_crack**, and at 90° **1.000 S_crack**. These are conditional scaling factors, not safe design values, and they ignore thermal and acceleration cases.

**Failure mode:** transverse flexural cracking if the transverse component exceeds the unmeasured crack threshold; the static vertical component is primarily axial/in-plane and requires a separate end-joint/load-path check.

## 3. Ascent/descent acceleration

No measured or specified payload acceleration g-load was found. The repository has an assumed **5 m/s ascent speed** for aerodynamic drag and **~0.45 m/s descent speed** (`docs/analysis/wing-jettison.md` §2.1), but speed is not acceleration and cannot be converted into a structural g-load without a trajectory/time history. The same document labels its **10 g burst shock** an assumption/TODO(unverified), not a measurement.

Therefore the design acceleration load is:

- horizontal: `N_g * 0.504 MPa` at 78.55 mm transverse, plus any in-plane component;
- vertical: `N_g * 0.504 MPa` only for the transverse component of the acceleration vector; static gravity remains in-plane.

`N_g` and its direction history: **TODO(unverified)**. Do not substitute the 10 g assumption for a flight requirement. **Failure mode:** flexural cracking for transverse acceleration; axial buckling/joint overload is a separate unsolved vertical-panel case.

## 4. Thermal cold soak

The cold-soak point is ADR-063 D4's **approximately -55 °C** repeat condition. Taking 25 °C as the notional assembly reference gives `ΔT = -80 K`; the 25 °C reference is an explicit calculation assumption, `TODO(unverified)` if the actual cure/assembly temperature differs.

Free silicon contraction is isotropic in the panel plane and does not depend on whether the panel is horizontal or vertical:

`epsilon_th = alpha ΔT = 2.6e-6/K * (-80 K) = -208 microstrain`.

If contraction is fully restrained in one in-plane direction, the uniaxial elastic stress estimate is:

`|sigma_th| = E alpha |ΔT| = 27.0 MPa (E=130 GPa) to 35.4 MPa (E=170 GPa)`.

That stress is **orientation-independent**. It is not a bending stress from the cell's self-weight and is zero for an ideal freely contracting cell; the actual value depends on solder lands, frame compliance, temperature gradient, and restraint. Those constraints are not characterized. **Failure mode:** thermal tensile/shear stress at silicon ends, solder joints, or defects; it can govern even when vertical static bending is zero.

## 5. Vibration / buffet

No citable panel vibration spectrum, acceleration PSD, gust spectrum, or qualification requirement was found in the repository. `docs/balloon-test-results.md` mentions jetstream wind qualitatively, but does not provide a structural vibration input. This case is therefore **omitted rather than invented**: vibration/buffet spectrum and resulting stress are `TODO(unverified)`. Failure mode, if later excited, is fatigue/crack growth and joint fatigue.

## Comparison and verdict

| load case | horizontal transverse bending | vertical transverse bending | governing unknown |
|---|---:|---:|---|
| static 1 g, 78.55 mm | 0.504 MPa | 0 | `S_crack` / flexural strength |
| pendulum, illustrative 30° | 0.436 MPa | 0.252 MPa | measured `theta_max` and `S_crack` |
| pendulum, 90° limit | 0.0 MPa at that instant | **0.504 MPa** | `S_crack` |
| acceleration | `0.504 N_g` MPa if transverse | `0.504 N_g` MPa if transverse | `N_g` TODO(unverified) |
| fully restrained -55 °C thermal | 27.0–35.4 MPa in-plane | 27.0–35.4 MPa in-plane | restraint/strength TODO |

**VERDICT: vertical mounting does not remove `S_crack`; it relocates and conditionally reduces the transverse bending demand.** At a documented-but-not-quantified pendulum, a 30° illustrative swing still gives **0.252 MPa (0.5 g) transverse**, and a 90° rotation gives **0.504 MPa (1 g)**—the full D4 demand. The larger thermal demand estimate, **27–35 MPa if restrained**, is orientation-independent and is not covered by the gravity coupon. Therefore the rib pitch cannot be increased above `S_crack` by orientation alone. A larger pitch could only be justified after measuring the swing/acceleration envelope and running a combined thermo-mechanical qualification; no honest factor larger than 1 can be frozen now.

**Disposition:** the `S_crack` card **must still run**. Minimum alternative only if the operator first proves a bounded flight envelope: (1) instrumented pendulum test measuring `theta_max` and acceleration vector, (2) cold-soaked end-supported real-cell test at -55 °C with that measured transverse g envelope, and (3) inspection for cracks/joint damage. This is not the full unbounded D4 coupon, but it still requires real-cell testing. Given current unknowns, do not relax the card.

## Sources and unsourced items

- `docs/adr/063-decouple-board-area-from-array-overhang.md` §D4: cell geometry, 0.504/1.007 MPa calibration, -55 °C test, and `S_crack` rule.
- `docs/adr/049-wing-architecture.md` (measured cell inputs and vertical wing architecture).
- `docs/adr/065-wing-skeletonised-double-sided.md` (vertical-plane skeletonized carrier and coupon dependency).
- `docs/analysis/hub_array_overhang_model.py` (rho, g, thickness, beam equation).
- `docs/analysis/wing-ladder.md` §4.3/§5 (pendulum period and drivers; no measured angle).
- `docs/analysis/wing-jettison.md` §2.1/§2.2 (5 m/s ascent, 0.45 m/s descent, assumed 10 g shock; no measured acceleration).
- External material references: silicon E ≈ 130–170 GPa and CTE ≈ 2.6e-6/K are standard literature values (MatWeb silicon datasheet; Ioffe Institute NSM silicon pages). **No external URL was fetched in this session; these are named sources only and remain `TODO(unverified)` until retrieved.**

**Unsourced/TODO(unverified):** flexural strength/modulus of rupture; maximum swing angle; acceleration g-load and vector history; vibration/buffet spectrum; exact assembly reference temperature; degree of thermal restraint; and whether the illustrative MatWeb modulus range applies to this cell texture/orientation.
