#!/usr/bin/env python3
"""Float altitude vs payload mass — Yokohama 32-inch superpressure sphere.

WHY THIS EXISTS
---------------
Two inputs were previously unknown and are now pinned down: the envelope mass
(MEASURED 46.84 g, marker tared out) and the envelope's FULL VOLUME (derived
three ways below). Those two close the float-altitude question, so this script
answers it directly: *for a given payload mass, at what altitude does the balloon
settle, and how much does that depend on weather?*

THE PHYSICS, STATED ONCE
------------------------
A superpressure balloon is filled with a FIXED MASS of gas at launch and the film
expands as it rises, until the envelope is taut at its full volume. Above that it
holds a constant volume. At float the gas has equilibrated to ambient T and P, so
its density is rho_air * mu (mu = M_gas/M_air) and:

    displaced air mass = rho_air * V_full
    balloon mass       = M_dry + m_gas,   m_gas = rho_air * mu * V_full
    float  =>  M_dry = rho_air * V_full * (1 - mu)
    =>  rho_air(alt_float) = M_dry / ( V_full * (1 - mu) )

Two consequences that decide how to read the plot:

* **The float altitude depends only on M_dry and V_full** — payload + envelope +
  rigging, and the balloon's volume. NOT on how much gas you put in, provided the
  envelope actually reaches full volume.
* **The gas fill decides only WHETHER it gets there.** Filling for free lift F
  needs a ground volume V_launch = (M_dry + F) / (rho_air(0) * (1 - mu)). If
  V_launch < V_full the balloon is UNDERFILLED (free lift with no superpressure,
  which is the normal, safe launch) and it will rise to the constant-volume float
  level. This script checks that condition and says so per case.

CAVEATS — what is and is not modelled
-------------------------------------
* Gas at ambient temperature. Real superpressure balloons run a few K warm by day
  (solar superheat) and cool at night, so they OSCILLATE around the modelled
  altitude. The diurnal excursion is a few hundred metres and is NOT modelled.
* Temperature enters through the ISA profile only. It turns out to be a MINOR
  lever (see the sensitivity panel) because float is a density condition and a
  uniform temperature offset barely moves the density profile.
* Envelope material buoyancy neglected: 46.84 g of laminate at ~1.4 g/cm3 is
  ~33 cm3, displacing ~0.04 g of air.
* No wind, no ice, no gas diffusion, no superpressure limit modelled. Those
  change WHERE it goes and HOW LONG it stays, not the float density level.
* "Best" and "worst" are NOT weather forecasts — they are the ends of the
  physically defensible input ranges (volume, gas species, temperature).

Run:    python3 docs/analysis/balloon_altitude_vs_payload.py
Writes: docs/analysis/out/balloon_altitude_vs_payload.csv
        docs/analysis/out/balloon_altitude_vs_payload.png
"""

from __future__ import annotations

import csv
import math
import os
from typing import TypedDict

# ------------------------------------------------------------------ constants
M_AIR = 28.9647                      # g/mol
M_GAS = {"He": 4.0026, "H2": 2.01588}
MU = {k: v / M_AIR for k, v in M_GAS.items()}

R_SPEC = 287.05287                   # J/(kg K), dry air
G0 = 9.80665                         # m/s2
LAPSE = 0.0065                       # K/m
T0_ISA = 288.15                      # K
P0_ISA = 101325.0                    # Pa
H_TROP = 11000.0                     # m

# MEASURED 2026-10-14 (docs/analysis/MEASURED-MASSES.md). The marker that held
# the folded envelope flat was TARED OUT of this reading.
ENVELOPE_G = 46.84
# Repo allowance: neck tape ~1 g + 20 m dipole wire 1.2 g (number bank sec. 5).
ATTACH_G = 2.2
# Community free-lift band: Traquito 5-7, NIBBB 6-7, desertrats 6-8,
# Ruthroff "five or six". Repo protocol rejects >8 g as a burst risk.
FREE_LIFT_G = 6.0

CAP_M = 32000.0                      # altitude cap; above this we report a cap

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
CSV_PATH = os.path.join(OUT_DIR, "balloon_altitude_vs_payload.csv")
PNG_PATH = os.path.join(OUT_DIR, "balloon_altitude_vs_payload.png")


# ---------------------------------------------------------------- atmosphere
def atmosphere(h_m: float, dT: float = 0.0) -> tuple[float, float, float]:
    """ISA with a uniform temperature offset. -> (T [K], p [Pa], rho [kg/m3]).

    NOTE ON UNITS: 1 kg/m3 == 1 g/L numerically. Keep everything in kg/m3 here
    and convert only at the print/plot boundary — mixing the two by a factor of
    1000 is the easy way to make this model answer nonsense.
    """
    t0 = T0_ISA + dT
    if h_m <= H_TROP:
        temp = t0 - LAPSE * h_m
        pres = P0_ISA * (temp / t0) ** (G0 / (LAPSE * R_SPEC))
    else:
        t_tp = t0 - LAPSE * H_TROP
        p_tp = P0_ISA * (t_tp / t0) ** (G0 / (LAPSE * R_SPEC))
        temp = t_tp
        pres = p_tp * math.exp(-G0 * (h_m - H_TROP) / (R_SPEC * t_tp))
    return temp, pres, pres / (R_SPEC * temp)


def altitude_at_density(rho_kgm3: float, dT: float = 0.0) -> float:
    """Altitude [m] where the ISA density equals rho_kgm3.

    Returns nan in BOTH impossible directions, which is the point:
      * rho_kgm3 BELOW the density at CAP_M  -> floats above the cap, not modelled
      * rho_kgm3 ABOVE the sea-level density -> can never float at all. Without
        this branch the bisection converges on 0 m and the caller reads
        "floats at sea level" for a balloon that is simply too heavy.
    """
    if rho_kgm3 > atmosphere(0.0, dT)[2]:
        return float("nan")          # heavier than the air at sea level
    if atmosphere(CAP_M, dT)[2] > rho_kgm3:
        return float("nan")          # would rise past the cap
    lo, hi = 0.0, CAP_M
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if atmosphere(mid, dT)[2] > rho_kgm3:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- geometry
def volume_L_from_circumference_in(c_in: float) -> float:
    d_m = (c_in * 0.0254) / math.pi
    return (4.0 / 3.0) * math.pi * (d_m / 2.0) ** 3 * 1000.0


def volume_L_from_diameter_in(d_in: float) -> float:
    d_m = d_in * 0.0254
    return (4.0 / 3.0) * math.pi * (d_m / 2.0) ** 3 * 1000.0


# ---------------------------------------------------------------- the solver
class Case(TypedDict):
    vol_L: float
    gas: str
    dT: float
    note: str


CASES: dict[str, Case] = {
    "best": {"vol_L": 281.0, "gas": "H2", "dT": +15.0,
             "note": "geometric full inflation (32 in nominal), hydrogen, warm day"},
    "nominal": {"vol_L": 270.0, "gas": "He", "dT": 0.0,
                "note": "manufacturer volume, helium, ISA standard day"},
    "worst": {"vol_L": 250.0, "gas": "He", "dT": -15.0,
              "note": "conservative stretched volume, helium, cold day"},
}


def solve(payload_g: float, vol_L: float, gas: str,
          free_lift_g: float = FREE_LIFT_G, dT: float = 0.0) -> dict:
    """Return the float solution for one configuration.

    Reports BOTH the constant-volume float altitude and the launch state, so the
    underfilled-vs-taut assumption is visible rather than assumed.
    """
    mu = MU[gas]
    m_dry = payload_g + ENVELOPE_G + ATTACH_G                 # g
    rho0 = atmosphere(0.0, dT)[2]                             # kg/m3 == g/L

    # gas mass and ground volume needed to hold the launch free lift
    v_launch_L = (m_dry + free_lift_g) / (rho0 * (1.0 - mu))
    m_gas_g = v_launch_L * rho0 * mu                          # = (m_dry+F)*mu/(1-mu)

    # constant-volume float condition
    rho_float = m_dry / (vol_L * (1.0 - mu))                  # g/L
    alt_m = altitude_at_density(rho_float, dT)

    # altitude at which the film first goes taut (V reaches vol_L)
    rho_gas_taut = m_gas_g / vol_L                            # g/L
    rho_air_taut = rho_gas_taut / mu                          # g/L
    alt_taut_m = altitude_at_density(rho_air_taut, dT)

    taut_before_float = (not math.isnan(alt_taut_m)) and (
        math.isnan(alt_m) or alt_taut_m <= alt_m)
    return dict(
        payload_g=payload_g, m_dry_g=m_dry, gas=gas, vol_L=vol_L, dT=dT,
        free_lift_g=free_lift_g, m_gas_g=m_gas_g, v_launch_L=v_launch_L,
        fill_frac=v_launch_L / vol_L, rho_float=rho_float,
        alt_m=alt_m, alt_taut_m=alt_taut_m, taut_before_float=taut_before_float,
    )


def altitude_km(payload_g: float, case: str) -> float:
    c = CASES[case]
    return solve(payload_g, c["vol_L"], c["gas"], dT=c["dT"])["alt_m"] / 1000.0


# ---------------------------------------------------------------- validation
# Community flights on the SAME envelope, from the repo number bank
# (KevWal/Balloon-Info README, "Yoko 32 in New" row). Payload = flight package;
# the envelope is counted separately, as here.
VALIDATION = [(7.0, 13.5), (28.0, 10.3), (40.0, 10.0)]

PAYLOAD_GRID_G = [float(p) for p in range(0, 61, 2)]
OUR_PAYLOADS = {36.0: "cells-only array", 41.0: "spine+ribs array",
                57.0: "full-carrier array", 63.0: "double-sided carrier"}
OUR_PAYLOAD_G = 57.0


# ---------------------------------------------------------------- sensitivity
def lever_sensitivity(payload_g: float = OUR_PAYLOAD_G) -> tuple[float, list]:
    c = CASES["nominal"]
    base = solve(payload_g, c["vol_L"], c["gas"])["alt_m"]

    def a(vol_L=None, gas=None, dT=None, env=None, fl=None):
        m_dry_shift = 0.0 if env is None else (env - ENVELOPE_G)
        r = solve(payload_g + m_dry_shift,
                  vol_L if vol_L is not None else c["vol_L"],
                  gas or c["gas"],
                  free_lift_g=fl if fl is not None else FREE_LIFT_G,
                  dT=dT if dT is not None else c["dT"])
        return r["alt_m"]

    levers = [
        ("volume 270 -> 250 L", a(vol_L=250.0) - base),
        ("volume 270 -> 281 L", a(vol_L=281.0) - base),
        ("gas helium -> hydrogen", a(gas="H2") - base),
        ("free lift 6 -> 15 g", a(fl=15.0) - base),
        ("free lift 6 -> 3 g", a(fl=3.0) - base),
        ("atmosphere ISA +15 K", a(dT=+15.0) - base),
        ("atmosphere ISA -15 K", a(dT=-15.0) - base),
        ("envelope 46.84 -> 52 g", a(env=52.0) - base),
        ("envelope 46.84 -> 42 g", a(env=42.0) - base),
    ]
    return base, levers


# ---------------------------------------------------------------- report
def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    line = "=" * 78

    print(line)
    print("1. VOLUME — the 32-inch Yokohama sphere, three independent derivations")
    print(line)
    v_geo = volume_L_from_diameter_in(32.0)
    v_100 = volume_L_from_circumference_in(100.0)
    v_105 = volume_L_from_circumference_in(105.0)
    print(f"   geometric at 32 in nominal diameter : {v_geo:7.1f} L")
    print(f"   at 100 in circumference (community) : {v_100:7.1f} L")
    print(f"   at 105 in circumference (stretch)   : {v_105:7.1f} L")
    print("   manufacturer states 270 L; community '240-270 L stretched'")
    print("   => independent sources agree within ~11 %; 270-281 L is the range")
    print()

    print(line)
    print("2. LIFT — gross buoyancy at 15 C, 1013.25 hPa (rho_air = 1.2250 g/L)")
    print(line)
    for g in ("He", "H2"):
        rho_g = 1.2250 * MU[g]
        print(f"   {g:2s}: rho = {rho_g:.4f} g/L -> net lift {1.2250 - rho_g:.4f} g/L"
              f" | over {v_100:.0f} L = {v_100 * (1.2250 - rho_g):.1f} g")
    print()

    print(line)
    print("3. VALIDATION — against three real flights on this envelope")
    print("   (community number bank; model uses 277 L, He, 6 g free lift)")
    print(line)
    print(f"   {'payload':>8} {'model':>9} {'community':>10} {'delta':>9}")
    for pl, claimed in VALIDATION:
        r = solve(pl, v_100, "He")
        got = r["alt_m"] / 1000.0
        print(f"   {pl:6.0f} g {got:8.2f}k {claimed:9.1f}k {got - claimed:+8.2f}k")
    print("   => within ~1.5 km on three independent flights; the model is not")
    print("      optimistic by a factor, so the curves below can be read directly.")
    print()

    print(line)
    print("4. FLOAT ALTITUDE vs PAYLOAD")
    print(f"   (total mass = payload + {ENVELOPE_G} g envelope + {ATTACH_G} g rigging)")
    print(line)
    print(f"   {'payload':>8} {'total':>9} | {'worst':>8} {'nominal':>8} {'best':>8}"
          f" | {'fill':>6} taut?")
    rows = []
    for p in PAYLOAD_GRID_G:
        vals = {k: altitude_km(p, k) for k in ("worst", "nominal", "best")}
        rn = solve(p, CASES["nominal"]["vol_L"], "He")
        total = p + ENVELOPE_G + ATTACH_G
        rows.append((p, total, vals["worst"], vals["nominal"], vals["best"]))
        if int(p) % 10 == 0:
            print(f"   {p:6.0f} g {total:7.1f} g | {vals['worst']:7.2f}k"
                  f" {vals['nominal']:7.2f}k {vals['best']:7.2f}k |"
                  f" {rn['fill_frac'] * 100:5.0f}%  {rn['taut_before_float']}")
    print()

    print(line)
    print("5. WHAT OUR PAYLOAD OPTIONS DO")
    print(line)
    for p, tag in OUR_PAYLOADS.items():
        v = {k: altitude_km(p, k) for k in ("worst", "nominal", "best")}
        print(f"   {p:4.0f} g ({tag:20s}): {v['worst']:5.2f} - {v['best']:5.2f} km"
              f"   (nominal {v['nominal']:.2f})")
    print()

    print(line)
    print("6. MAX PAYLOAD FOR A TARGET ALTITUDE (nominal: 270 L, He)")
    print(line)
    for km in (10, 11, 12, 13, 14, 15):
        rho_t = atmosphere(km * 1000.0)[2]
        m_dry = rho_t * CASES["nominal"]["vol_L"] * (1.0 - MU["He"])
        payload = m_dry - ENVELOPE_G - ATTACH_G
        ok = "reachable" if payload > 0 else "IMPOSSIBLE"
        print(f"   {km:2d} km: all-up {m_dry:6.1f} g -> payload {payload:+6.1f} g  [{ok}]")
    print()

    print(line)
    print(f"7. WHICH LEVER MOVES THE ALTITUDE  (at our {OUR_PAYLOAD_G:.0f} g payload)")
    print(line)
    base_m, levers = lever_sensitivity()
    print(f"   nominal altitude: {base_m / 1000:.2f} km")
    for label, d in sorted(levers, key=lambda kv: abs(kv[1]), reverse=True):
        print(f"     {label:26s} {d / 1000:+6.2f} km")
    print("   => VOLUME and GAS SPECIES dominate. Temperature is a minor term:")
    print("      float is a density condition, and a uniform dT barely shifts the")
    print("      density profile. Weather matters for the diurnal excursion and for")
    print("      where it drifts, not for the mean float level.")
    print()

    with open(CSV_PATH, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["payload_g", "total_mass_g", "case", "volume_L", "gas", "dT_K",
                    "free_lift_g", "gas_mass_g", "fill_frac", "altitude_km"])
        for p, total, aw, an, ab in rows:
            for case, alt in (("worst", aw), ("nominal", an), ("best", ab)):
                c = CASES[case]
                r = solve(p, c["vol_L"], c["gas"], dT=c["dT"])
                w.writerow([f"{p:.1f}", f"{total:.2f}", case, f"{c['vol_L']:.0f}",
                            c["gas"], f"{c['dT']:+.0f}", f"{r['free_lift_g']:.1f}",
                            f"{r['m_gas_g']:.3f}", f"{r['fill_frac']:.4f}",
                            f"{alt:.4f}"])
    print(f"wrote {CSV_PATH}")

    plot(rows, levers, base_m)
    print(f"wrote {PNG_PATH}")


# ---------------------------------------------------------------- figure
def plot(rows, levers, base_m) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = [r[0] for r in rows]
    aw = [r[2] for r in rows]
    an = [r[3] for r in rows]
    ab = [r[4] for r in rows]

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(14, 6.0), gridspec_kw={"width_ratios": [1.7, 1]})

    # ---- panel 1: altitude vs payload ------------------------------------
    ax.fill_between(x, aw, ab, color="#cfe3f7", alpha=0.9, zorder=1,
                    label="best-to-worst envelope")
    ax.plot(x, an, color="#12457a", lw=2.6, zorder=4,
            label="nominal (270 L, He, ISA)")
    ax.plot(x, aw, color="#b3261e", lw=1.6, ls="--", zorder=3,
            label="worst (250 L, He, ISA-15 K)")
    ax.plot(x, ab, color="#1b7f3b", lw=1.6, ls="--", zorder=3,
            label="best (281 L, H2, ISA+15 K)")

    ax.axhspan(8.8, 12.5, color="#f2c9c4", alpha=0.5, zorder=0)
    ax.text(0.6, 12.72, "airliner cruise band  FL290-FL410  (8.8-12.5 km)",
            fontsize=8.5, color="#8a2b22", zorder=6)
    ax.axhline(13.5, color="#555", lw=1.0, ls=":", zorder=0)
    ax.text(0.6, 13.62, "13.5 km — above the traffic", fontsize=8.5,
            color="#444", zorder=6)

    ax.axvspan(36, 63, color="#ffe9a8", alpha=0.55, zorder=0)
    ax.text(49.5, 6.55, "our v9 payload options\n36 - 63 g", fontsize=8.5,
            ha="center", color="#7a5c00", zorder=6)

    r57 = altitude_km(57.0, "nominal")
    ax.plot([57.0], [r57], "o", ms=7, color="#12457a", zorder=7)
    ax.annotate(f"full-carrier 57 g\n{r57:.1f} km nominal",
                xy=(57.0, r57), xytext=(30.0, r57 + 2.1), fontsize=8.5,
                color="#12457a", zorder=7,
                arrowprops=dict(arrowstyle="->", color="#12457a", lw=1.1))

    ax.set_xlabel("payload mass added to the balloon  (g)")
    ax.set_ylabel("float altitude  (km)")
    ax.set_title("Yokohama 32-inch superpressure sphere — float altitude vs payload",
                 fontsize=11.5)
    ax.set_xlim(0, 60)
    ax.set_ylim(6, 16)
    ax.grid(alpha=0.25, zorder=0)
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.96)

    # ---- panel 2: lever sensitivity --------------------------------------
    labels = [l for l, _ in levers]
    vals = [d / 1000.0 for _, d in levers]
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    cols = ["#b3261e" if vals[i] < 0 else "#1b7f3b" for i in order]
    ax2.barh([labels[i] for i in order], [vals[i] for i in order],
             color=cols, alpha=0.88, zorder=3)
    ax2.axvline(0, color="#333", lw=1.1, zorder=4)
    ax2.set_xlabel(f"change in float altitude (km)   @ {OUR_PAYLOAD_G:.0f} g payload")
    ax2.set_title("Which lever actually moves the altitude", fontsize=11.5)
    ax2.grid(alpha=0.25, axis="x", zorder=0)
    lim = max(abs(v) for v in vals) * 1.45
    ax2.set_xlim(-lim, lim)
    for i, idx in enumerate(order):
        v = vals[idx]
        ax2.text(v + (0.02 * lim if v >= 0 else -0.02 * lim), i, f"{v:+.2f}",
                 va="center", ha="left" if v >= 0 else "right", fontsize=8.5,
                 zorder=5)

    # ---- provenance, built UNCONDITIONALLY, wrapped EXPLICITLY --------------
    # Two short lines beat one long one: a single wide string gets clipped at
    # BOTH edges by the figure box while the script still exits 0. The wrapping
    # is manual so the break points do not depend on a renderer's guess.
    prov_lines = [
        f"DERIVED model — not flight data.  Envelope {ENVELOPE_G} g MEASURED 2026-10-14 "
        f"(marker tared out); rigging {ATTACH_G} g;",
        f"V_full 250-281 L; free lift {FREE_LIFT_G} g; ISA with uniform dT; gas at ambient T "
        f"(no solar superheat, no diurnal term).",
    ]
    for i, txt in enumerate(prov_lines):
        fig.text(0.5, 0.036 - i * 0.021, txt, ha="center", fontsize=7.0, color="#444")

    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(PNG_PATH, dpi=150)


if __name__ == "__main__":
    main()
