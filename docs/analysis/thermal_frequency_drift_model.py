#!/usr/bin/env python3
"""thermal_frequency_drift_model.py — companion arithmetic for
`docs/analysis/thermal-and-frequency-drift.md`.

Every number the analysis prints is produced here from the repo's own figures,
so the arithmetic is reproducible and auditable. No datasheet value is invented:
inputs taken from the repo are cited inline; anything estimated is marked and
exported in the `ESTIMATES` list.

Run:  python3 docs/analysis/thermal_frequency_drift_model.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Vehicle energy figures — all from the repo (cited in the analysis doc)
# ---------------------------------------------------------------------------
P_AVG = 0.388          # W   input average, daylight TDM  (docs/POWER-BUDGET-V9-D2BE.md L85)
P_PEAK_ARRAY = 7.2     # W   12 cells x 0.5 V x 1.2 A     (ADR-051 S1.1 / ADR-054 S1.1)
P_SOLAR_PEAK = 2.4     # W   6.0 V x 0.400 A direct sun   (ADR-006)
E_BANK_USABLE = 33.264 # J   3.3 F, 5.4 -> 3.0 V           (ADR-047 S3.2 / ADR-054 S2.5)
E_BANK_16 = 16.632     # J   1.65 F, 5.4 -> 3.0 V         (ADR-047 S3.1, accepted bank)
P_NIGHT_ANCHOR = 100e-6  # W  ADR-036 night anchor
NIGHT_H = 10.0         # h   conservative "10 h night" used by ADR-036/POWER-BUDGET
SECONDS_PER_H = 3600.0

# ---------------------------------------------------------------------------
# Oscillator target: OCXO-class stabilisation = hold the crystal at its
# turning point (~+25 C) from a stratospheric ambient of -50 to -56 C.
# The operator's task states the span as "an 80 K rise".
# ---------------------------------------------------------------------------
T_TURNING = 25.0       # degC  OCXO turning point of an AT-cut crystal (typical, ESTIMATE)
T_AMB_LOW = -56.0      # degC  DESIGN CASE cold  (ADR-043 mission minimum -60; ADR-042 uses -55/-60)
T_AMB_HIGHCOLD = -50.0 # degC  upper end of the quoted -50..-56 band
DT_80 = 80.0           # K     the task's stated rise, used as the headline delta-T

# Plausible thermal CONDUCTANCES G (P = G * delta-T).  These are ESTIMATES:
# the repo's only thermal figure is ADR-042 S D1's R_thermal ~ 100 K/W = G 10 mW/K.
# No measured enclosure G exists (ADR-042 / ADR-043 both mark it TODO(unverified)).
G_VALUES = [  # (label, G in W/K, is_estimate)
    ("well-insulated small package, R=333 K/W", 0.003, True),
    ("repo assumption R_thermal=100 K/W (ADR-042 D1)", 0.010, True),
    ("typical small insulated enclosure, R=33 K/W", 0.030, True),
    ("unsealed board-scale, R=10 K/W (ADR-042 falsify bound)", 0.100, True),
]


def banner(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def heater_at(dt: float, g: float) -> float:
    """P = G * delta-T, in watts."""
    return g * dt


def main() -> None:
    banner("1. THE HEATER ARITHMETIC — P = G * delta-T")
    print(f"turn point            = {T_TURNING:+.1f} C  (OCXO-class setpoint, ESTIMATE)")
    print(f"cold ambient band     = {T_AMB_LOW:+.1f} .. {T_AMB_HIGHCOLD:+.1f} C")
    print(f"delta-T (headline)    = {DT_80:.0f} K   "
          f"[derived: {T_TURNING:.0f}-({T_AMB_LOW:.0f}) = {T_TURNING - T_AMB_LOW:.0f} K to "
          f"{T_TURNING - T_AMB_HIGHCOLD:.0f} K; task uses 80 K]")
    print()
    print(f"{'G (mW/K)':>10} | {'P = G*dT (W)':>13} | {'x avg 0.388 W':>13} | "
          f"{'% of 7.2 W peak':>15} | {'night 10 h (kJ)':>15} | {'bank/need (x)':>13}")
    print("-" * 95)
    for label, g, est in G_VALUES:
        p = heater_at(DT_80, g)
        night_j = p * NIGHT_H * SECONDS_PER_H
        need_vs_avg = p / P_AVG
        pct_peak = 100.0 * p / P_PEAK_ARRAY
        bank_ratio = night_j / E_BANK_USABLE
        print(f"{g*1000:10.1f} | {p:13.3f} | {need_vs_avg:12.2f}x | "
              f"{pct_peak:14.1f}% | {night_j/1000:15.3f} | {bank_ratio:12.1f}x")
        print(f"           | {label}{'  [ESTIMATE]' if est else ''}")

    banner("2. THE HEATER RUN-TIME AGAINST THE FITTED BANK (33.264 J)")
    for label, g, _ in G_VALUES:
        p = heater_at(DT_80, g)
        print(f"G={g*1000:5.1f} mW/K -> P={p:6.3f} W -> "
              f"t = 33.264 J / {p:.3f} W = {E_BANK_USABLE/p:6.2f} s   "
              f"(16.632 J bank: {E_BANK_16/p:6.2f} s)")

    banner("3. RATIO TO THE OPERATOR'S NUMBERS (stated plainly)")
    p_mid = heater_at(DT_80, 0.010)
    print(f"at the repo's own R_thermal=100 K/W (G=10 mW/K):")
    print(f"  P_heater                        = {p_mid:.3f} W")
    print(f"  / array average 0.388 W         = {p_mid/P_AVG:.2f}x  "
          f"({'FAILS' if p_mid>P_AVG else 'ok'} against the daylight average)")
    print(f"  / night anchor 100 uW           = {p_mid/P_NIGHT_ANCHOR:,.0f}x")
    print(f"  night energy  = {p_mid:.3f} W x {NIGHT_H:.0f} h x 3600 = "
          f"{p_mid*NIGHT_H*SECONDS_PER_H:,.0f} J")
    print(f"  / usable bank 33.264 J          = "
          f"{p_mid*NIGHT_H*SECONDS_PER_H/E_BANK_USABLE:,.0f}x  "
          f"(fails by this factor)")
    print(f"  ADR-036 night budget 100 uW x 10 h = {P_NIGHT_ANCHOR*NIGHT_H*SECONDS_PER_H:.1f} J "
          f"-> heater is {p_mid*NIGHT_H*SECONDS_PER_H/(P_NIGHT_ANCHOR*NIGHT_H*SECONDS_PER_H):,.0f}x it")

    banner("4. GPS 1PPS DISCIPLINE — COUNTING RESOLUTION (arithmetic only)")
    print("Fractional-frequency resolution of a gated counter: dF/F = 1/(f_ref * T)")
    for f_ref, name in [(32e6, "LR2021 32 MHz"), (52e6, "SX1280 52 MHz")]:
        print(f"\n  {name}:")
        for T in (1, 10, 100, 1000):
            n = f_ref * T
            res = 1.0 / n
            print(f"    T={T:5d} s -> N={n:.3e} counts -> dF/F={res:.3e} "
                  f"= {res*1e6:9.5f} ppm")
    print()
    print("  Parametric 1PPS-noise limit (1PPS jitter sigma_t is TODO(unverified)):")
    print("    per-sample dF/F = sigma_t / 1 s ; averaged over M s -> sigma_t / (1 s * sqrt(M))")
    for sigma in (30e-9, 100e-9, 1e-6):
        for M in (10, 100, 1000):
            print(f"    sigma_t={sigma*1e9:6.0f} ns, M={M:5d} s -> "
                  f"{sigma/(1.0*M**0.5)*1e6:9.5f} ppm")

    banner("5. SYNTHESIZER TRIM GRANULARITY (frf = f_rf * 2^18 / f_xtal)")
    print("One LSB of the 18-bit divider = f_xtal / 2^18 at the RF frequency.")
    for f_xtal, name in [(32e6, "LR2021"), (52e6, "SX1280")]:
        lsb = f_xtal / (2 ** 18)
        print(f"\n  {name} (f_xtal={f_xtal/1e6:.0f} MHz): LSB = {lsb:.2f} Hz")
        for f_rf in (433e6, 868e6, 2400e6):
            print(f"    at {f_rf/1e6:6.0f} MHz -> {lsb/f_rf*1e6:.4f} ppm/LSB")

    banner("6. ADJACENT THERMAL: KEEPING THE ELECTRONICS ABOVE RATING")
    print("Rating gap (ADR-054 open item 2 / fault-tolerance S9.5): verified parts are")
    print("rated -55 C (diodes) or -40 C (converters) against a -60 C design case.")
    print("Cost to hold a target temperature from a -56 C ambient:")
    print(f"\n{'target':>8} | {'dT (K)':>7} | {'G=10mW/K':>9} | {'G=30mW/K':>9} | {'G=100mW/K':>10}")
    print("-" * 60)
    for target in (-40.0, -20.0, 0.0):
        dt = target - T_AMB_LOW
        row = [heater_at(dt, g) for g in (0.010, 0.030, 0.100)]
        print(f"{target:+8.0f} | {dt:7.0f} | {row[0]:9.3f} | {row[1]:9.3f} | {row[2]:10.3f}")
    print()
    print("At -40 C target, G=10 mW/K (0.160 W):")
    p40 = heater_at(-40.0 - T_AMB_LOW, 0.010)
    print(f"  = {p40:.3f} W = {100*p40/P_AVG:.1f}% of the 0.388 W daylight average")
    print(f"  night energy = {p40:.3f} W x 10 h = {p40*NIGHT_H*SECONDS_PER_H:,.0f} J = "
          f"{p40*NIGHT_H*SECONDS_PER_H/E_BANK_USABLE:,.0f}x the 33.264 J usable bank")

    banner("7. SUPERCAP COLD SENSITIVITY (parametric — cold C/ESR are TODO(unverified))")
    esr_cell_25 = 0.10   # ohm/cell at 25 C (ADR-047 appendix uses 2 x 0.10 ohm for 2 cells)
    print("ESR scales the instantaneous drop under a 1.2 A TX pulse.")
    print("Accepted 1.65 F bank = 2 cells in series -> 2*ESR_cell; doubled 3.3 F bank = 1*ESR_cell.")
    print(f"\n{'ESR factor':>10} | {'dVecap 1.65F (V)':>17} | {'dVecap 3.3F (V)':>16} | "
          f"{'% of 2.4 V headroom':>20}")
    print("-" * 72)
    for k in (1, 2, 3, 5, 10):
        dv2 = 1.2 * (2 * esr_cell_25 * k)
        dv4 = 1.2 * (1 * esr_cell_25 * k)
        print(f"{k:10.0f} | {dv2:17.3f} | {dv4:16.3f} | {100*dv4/2.4:19.1f}%")
    print()
    print("Capacitance loss scales usable energy linearly: E_usable(c) = c * 33.264 J")
    for c in (1.0, 0.9, 0.75, 0.5):
        print(f"  C retained {c*100:5.0f}% -> usable {c*E_BANK_USABLE:6.2f} J "
              f"= {c*E_BANK_USABLE/6.1495:5.2f} s at the 6.1495 W radio peak")


if __name__ == "__main__":
    main()
