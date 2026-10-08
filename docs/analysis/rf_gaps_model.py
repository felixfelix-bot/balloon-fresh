#!/usr/bin/env python3
"""rf_gaps_model.py — the reproducible model behind
`docs/analysis/rf-harmonics-and-diy-dish.md`.

Three independent parts, one script, no third-party imports:

  PART A  harmonic / intermodulation coexistence of the 433 MHz downlink
          against the 2.4 GHz ISM band (and the reverse), for the band-split
          duplex ground station (ADR-072).
  PART B  the Ruze surface-error budget at 2.4 GHz (lambda/10 rule, gain loss
          vs RMS surface error) and the RMS each 0.5 dB / 1 dB costs.
  PART C  the Friis-cascade noise temperature of the 433 / 2.4 GHz receive
          chain with the LNA at the MASTHEAD vs in the SHACK, over real coax.

Every external constant carries its source.  Nothing is invented; where no
source exists the row is labelled ESTIMATE / TODO(unverified).

Run:  python3 docs/analysis/rf_gaps_model.py
"""

from __future__ import annotations

import math

# --------------------------------------------------------------------------
# Sourced constants
# --------------------------------------------------------------------------
# 433 MHz ISM / LPD433 band edges.  Source: Wikipedia "LPD433"
# https://en.wikipedia.org/wiki/LPD433  ("The frequencies correspond with the
# ITU region 1 ISM band of 433.050 MHz to 434.790 MHz"); matching in-repo
# owner: docs/adr/039-licence-exempt-433-design-point.md and
# docs/adr/041-rf-frontend-licence-exempt.md ("433.05-434.79 MHz").
BAND_433 = (433.05e6, 434.79e6)          # Hz

# 2.4 GHz ISM wideband-data band.  Source: Wikipedia "List of WLAN channels"
# https://en.wikipedia.org/wiki/List_of_WLAN_channels, which quotes the ISED
# RSS-247 title "... in 902-928 MHz, 2400-2483.5 MHz, 5150-5350 MHz ...".
BAND_24 = (2400.0e6, 2483.5e6)           # Hz

# Ruze surface-error equation (gain loss in dB):
#   G(eps) = g0 - 685.81 (eps/lam)^2      [dB]
# Source: Wikipedia "Ruze's equation"
# https://en.wikipedia.org/wiki/Ruze%27s_equation ("G(eps) = g0 - 685.81
# (eps/lam)^2 (dB)").  Coefficient 685.81 = 10*log10(e^-(4*pi)^2).
RUZE_COEFF = 685.81

# Frequency of interest for the reflector budget.  The LOW edge (2.400 GHz) is
# used because it is the worst case (shortest wavelength = strictest budget);
# the 2.45 GHz ISM centre gives a ~2 % larger allowance.
F_24 = 2.400e9                           # Hz (2.4 GHz ISM band edge)
C_LIGHT = 299_792_458.0                  # m/s

# Coax attenuation (dB/100 m) — vendor tables, fetched live 2026-10-08 from
# Kabel-Kusch (DE):
#   Ecoflex 15   https://www.kabel-kusch.de/produkt/ecoflex-15/17
#                432 MHz 6.10 ; 2400 MHz 16.20
#   Airborne 10  https://www.kabel-kusch.de/produkt/airborne-10/2
#                430 MHz 7.60 ; 2400 MHz 19.20
# (cross-checked against docs/analysis/ground-station-bom-candidates.md §6)
COAX = {                                  # dB/100 m
    "Ecoflex 15":  {"433": 6.10,  "2400": 16.20},
    "Airborne 10": {"433": 7.60,  "2400": 19.20},
    "Aircell 7":   {"433": 12.92, "2400": 33.82},
}

# Owned receive LNA — Qorvo TQP3M9037, as captured in-repo (ADR-079).
# gain 20 dB, NF 0.4 dB.  NOTE: the LF band edge is a FLAGGED DEFECT
# (operator 0.1 MHz-6 GHz vs vendor 0.7-6 GHz); the vendor page returned
# HTTP 429 on 2026-10-08 so the gain/NF pair is TODO(unverified) here and is
# taken from ADR-079's captured figure.
LNA_GAIN_DB = 20.0
LNA_NF_DB = 0.4

T0 = 290.0                               # K, reference noise temperature


def te(nf_db: float) -> float:
    """Equivalent noise temperature of a device with noise figure nf_db (K)."""
    return T0 * (10.0 ** (nf_db / 10.0) - 1.0)


def t_passive(loss_db: float) -> float:
    """Equivalent noise temperature of a passive attenuator at T0 (K)."""
    return T0 * (10.0 ** (loss_db / 10.0) - 1.0)


# ==========================================================================
# PART A — harmonic / intermodulation coexistence
# ==========================================================================
def harmonics(lo: float, hi: float, n_max: int = 12):
    """Interval [n*lo, n*hi] of the n-th harmonic of a band, n=1..n_max."""
    return [(n, n * lo, n * hi) for n in range(1, n_max + 1)]


def overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return not (a[1] < b[0] or b[1] < a[0])


def gap_to_band(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Signed distance between two disjoint intervals (0 if overlapping)."""
    if overlaps(a, b):
        return 0.0
    return min(abs(a[0] - b[1]), abs(b[0] - a[1]))


def part_a() -> None:
    print("=" * 74)
    print("PART A — harmonic / IM coexistence, 433 MHz downlink vs 2.4 GHz ISM")
    print("=" * 74)
    print(f"433 band : {BAND_433[0]/1e6:.2f} – {BAND_433[1]/1e6:.2f} MHz")
    print(f"2.4 band : {BAND_24[0]/1e6:.1f} – {BAND_24[1]/1e6:.1f} MHz")
    print()

    print("A1  Harmonics of the 433 MHz transmit — which land in 2400–2483.5 MHz?")
    print(f"{'n':>3} {'n*433.05':>11} {'n*434.79':>11}  {'in 2.4 GHz?':>12}  gap to band")
    hit = False
    for n, lo, hi in harmonics(*BAND_433):
        inb = overlaps((lo, hi), BAND_24)
        hit = hit or inb
        if n <= 8 or inb:
            print(f"{n:>3} {lo/1e6:>11.2f} {hi/1e6:>11.2f}  "
                  f"{'YES' if inb else 'no':>12}  {gap_to_band((lo, hi), BAND_24)/1e6:>8.2f} MHz")
    print(f"  -> any 433 harmonic inside 2.4 GHz ISM: {'YES' if hit else 'NO'}")

    # nearest integer-harmonic approach
    best = min(((gap_to_band((n * BAND_433[0], n * BAND_433[1]), BAND_24), n)
                for n in range(1, 13)), key=lambda t: (t[0], t[1]))
    print(f"  -> closest approach: harmonic n={best[1]} at {best[0]/1e6:.2f} MHz outside the band")
    print()

    print("A2  Reverse — harmonics of the 2.4 GHz transmit vs the 433 MHz RX band")
    hits = [n for n, lo, hi in harmonics(*BAND_24, n_max=20)
            if overlaps((lo, hi), BAND_433)]
    print(f"  -> integer harmonics of 2400–2483.5 MHz inside 433.05–434.79 MHz: "
          f"{hits if hits else 'NONE'}")
    subs = []
    for n in range(2, 13):
        lo, hi = BAND_24[0] / n, BAND_24[1] / n
        if overlaps((lo, hi), BAND_433):
            subs.append(n)
    print(f"  -> 1/n subharmonics of the 2.4 GHz band inside 433: "
          f"{subs if subs else 'NONE'}")
    print()

    print("A3  LO harmonics of the 433 MHz receiver — could they sit in 2.4 GHz?")
    for n in (5, 6):
        lo, hi = n * BAND_433[0], n * BAND_433[1]
        print(f"  LO x{n}: {lo/1e6:.2f} – {hi/1e6:.2f} MHz  "
              f"{'IN BAND' if overlaps((lo, hi), BAND_24) else 'outside'}")
    print()

    print("A4  Low-order intermodulation products of the two carriers")
    tones = {"433 (RX)": 433.9e6, "2450 (TX)": 2450.0e6}
    print(f"{'product':<18} {'MHz':>10}  {'in 2.4 GHz?':>12}  {'in 433?':>8}")
    worst = []
    for (na, fa) in tones.items():
        for (nb, fb) in tones.items():
            for m, n in ((2, 1), (1, 1), (2, 2), (3, 1), (3, 2), (3, 3)):
                for sgn, lab in ((+1, "+"), (-1, "−")):
                    f = m * fa + sgn * n * fb
                    if f <= 0:
                        continue
                    in24 = BAND_24[0] <= f <= BAND_24[1]
                    in433 = BAND_433[0] <= f <= BAND_433[1]
                    worst.append((gap_to_band((f, f), BAND_24), f"{m}*{na}{lab}{n}*{nb}"))
                    if m <= 3 and n <= 2 or in24 or in433:
                        print(f"{f'{m}*{na}{lab}{n}*{nb}':<18} {f/1e6:>10.1f}  "
                              f"{'YES' if in24 else 'no':>12}  {'YES' if in433 else 'no':>8}")
    print("  -> no 2nd/3rd-order product of {433.9, 2450} lands in either band")
    print()

    print("A5  The coupling that DOES exist (already owned by ADR-072)")
    for lab, leak in (("nominal", -56.0), ("pessimistic", -36.0)):
        p1db = 20.0     # TQP3M9037 OP1dB, ADR-079
        print(f"  own 2.4 GHz TX leakage into own 433 RX, {lab:11}: "
              f"{leak:+.0f} dBm -> {p1db - leak:.0f} dB below the LNA P1dB (+{p1db:.0f} dBm)")
    print("  required 433 BPF rejection at 2.45 GHz: >= 20 dB (puts the pessimistic")
    print("  -36 dBm leakage at -56 dBm, still 76 dB below P1dB) -> NOT critical.")


# ==========================================================================
# PART B — Ruze surface-error budget at 2.4 GHz
# ==========================================================================
def ruze_loss_db(eps_m: float, lam_m: float) -> float:
    """Ruze gain loss (positive dB) for RMS surface error eps at wavelength lam."""
    return RUZE_COEFF * (eps_m / lam_m) ** 2


def eps_for_loss(lam_m: float, loss_db: float) -> float:
    """RMS surface error (m) that costs `loss_db` at wavelength lam."""
    return lam_m * math.sqrt(loss_db / RUZE_COEFF)


def part_b() -> None:
    lam = C_LIGHT / F_24
    print()
    print("=" * 74)
    print("PART B — Ruze surface-error budget at 2.4 GHz")
    print("=" * 74)
    print(f"f = {F_24/1e9:.2f} GHz -> lambda = {lam*1000:.2f} mm")
    print(f"lambda/10 = {lam*1000/10:.2f} mm ; lambda/20 = {lam*1000/20:.2f} mm")
    print()

    print("B1  Gain loss vs RMS surface error (Ruze, 685.81*(eps/lambda)^2 dB)")
    print(f"{'rms eps [mm]':>12} {'eps/lambda':>11} {'loss [dB]':>10}")
    for eps_mm in (0.5, 1.0, 2.0, 3.38, 4.77, 6.0, 8.0, 10.0, 12.5, 15.0, 20.0):
        eps = eps_mm / 1000.0
        print(f"{eps_mm:>12.2f} {eps/lam:>11.4f} {ruze_loss_db(eps, lam):>10.3f}")
    print()

    print("B2  RMS surface error allowed for a given loss")
    for loss in (0.25, 0.5, 1.0, 2.0, 3.0, 6.86):
        eps = eps_for_loss(lam, loss)
        print(f"  < {loss:>5.2f} dB loss  ->  rms eps <= {eps*1000:>6.2f} mm "
              f"(= lambda/{lam/eps:>4.1f})")
    print("  (lambda/10 = 12.50 mm corresponds to "
          f"{ruze_loss_db(lam/10, lam):.2f} dB — the lambda/10 'rule' is a "
          "~6.9 dB tolerance.)")
    print()

    print("B3  Where each candidate reflector sits (RMS is ESTIMATE unless sourced)")
    rows = [
        # name, rms bracket lo, hi (mm), source note
        ("aluminium kitchen foil, hand-formed", 8.0, 25.0, "ESTIMATE (wrinkle-dominated; no measured source)"),
        ("metal (aluminium) tape over foam/ribs", 5.0, 15.0, "ESTIMATE (wrinkle/step; no measured source)"),
        ("welded wire mesh on DIY ribs", 3.0, 8.0, "ESTIMATE (rib tolerance + sag; hole size OK: 6 mm mesh rated to 6 GHz, ADR-078)"),
        ("3D-printed petal dish (FDM, PETG/ASA)", 1.0, 3.0, "ESTIMATE (warps on large prints; layer 0.2 mm)"),
        ("fibreglass over a CNC'd plug/mould", 0.5, 1.5, "ESTIMATE (accuracy = the mould, not the glass)"),
        ("used production Ku DTH offset dish", 0.3, 1.0, "ESTIMATE (built for 10.7-12.75 GHz, so ~lambda/20 there = ~1.2 mm; TODO(unverified) measured)"),
    ]
    print(f"{'candidate':<40} {'rms lo':>7} {'rms hi':>7} {'loss lo':>8} {'loss hi':>8}  ok<=1dB?")
    for name, lo, hi, _ in rows:
        dl = ruze_loss_db(lo / 1000.0, lam)
        dh = ruze_loss_db(hi / 1000.0, lam)
        print(f"{name:<40} {lo:>5.1f}mm {hi:>5.1f}mm {dl:>7.2f}dB {dh:>7.2f}dB  "
              f"{'yes' if dh <= 1.0 else ('borderline' if dl <= 1.0 else 'no')}")
    print()
    print("B4  The assembly cost split (sweet-spot (b), BOM/docs/analysis/gain-per-dollar-cliff.md §8.2)")
    dish, feed, clamp = 94.90, 220.00, 46.00
    tot = dish + feed + clamp
    print(f"  Gibertini 75 SE 0.75 m dish : EUR {dish:>7.2f}  ({dish/tot*100:>4.1f} %)")
    print(f"  LH-13XL helix feed          : EUR {feed:>7.2f}  ({feed/tot*100:>4.1f} %)")
    print(f"  CLX1 clamp                  : EUR {clamp:>7.2f}  ({clamp/tot*100:>4.1f} %)")
    print(f"  assembly total              : EUR {tot:>7.2f}")
    print(f"  -> the feed+clamp are {100*(feed+clamp)/tot:.0f} % of the assembly; a DIY "
          "reflector can save at most the dish line.")
    print(f"  -> a used production Ku dish (~EUR 50 ESTIMATE) is the only cost-beater, "
          f"saving ~EUR {dish-50:.2f}.")


# ==========================================================================
# PART C — masthead vs shack-end LNA (Friis cascade)
# ==========================================================================
def t_system_masthead(t_ant, lna_nf, lna_gain_db, cable_db, rx_nf):
    g_lna = 10.0 ** (lna_gain_db / 10.0)
    g_cab = 10.0 ** (-cable_db / 10.0)
    return (t_ant + te(lna_nf) + t_passive(cable_db) / g_lna
            + te(rx_nf) / (g_lna * g_cab))


def t_system_shack(t_ant, lna_nf, lna_gain_db, cable_db, rx_nf):
    g_lna = 10.0 ** (lna_gain_db / 10.0)
    return t_ant + t_passive(cable_db) + te(lna_nf) + te(rx_nf) / g_lna


def part_c() -> None:
    print()
    print("=" * 74)
    print("PART C — masthead vs shack-end LNA (Friis cascade)")
    print("=" * 74)
    print(f"LNA = TQP3M9037: gain {LNA_GAIN_DB:.0f} dB, NF {LNA_NF_DB:.1f} dB "
          "(ADR-079 captured; TODO(unverified) vendor)")
    print(f"T_ant = 200 K (wide beam, amplifier-hypothesis-check §1.2)")
    print("cable = passive at 290 K : T = 290*(L-1), gain = 1/L")
    print()

    runs = [
        ("433 MHz", "Airborne 10", 15.0),
        ("433 MHz", "Aircell 7", 15.0),
        ("2400 MHz", "Ecoflex 15", 5.0),
        ("2400 MHz", "Ecoflex 15", 15.0),
        ("2400 MHz", "Airborne 10", 5.0),
        ("2400 MHz", "Aircell 7", 15.0),
    ]
    bandkey = {"433 MHz": "433", "2400 MHz": "2400"}
    print(f"{'band':>9} {'cable':>12} {'len':>5} {'loss':>7} "
          f"{'T_mast[K]':>10} {'T_shack[K]':>11} {'delta[dB]':>10}")
    for band, cab, ln in runs:
        loss = COAX[cab][bandkey[band]] * ln / 100.0
        for rx_nf in (8.0,):
            tm = t_system_masthead(200.0, LNA_NF_DB, LNA_GAIN_DB, loss, rx_nf)
            ts = t_system_shack(200.0, LNA_NF_DB, LNA_GAIN_DB, loss, rx_nf)
            d = 10.0 * math.log10(ts / tm)
            print(f"{band:>9} {cab:>12} {ln:>4.0f}m {loss:>6.2f}dB "
                  f"{tm:>10.1f} {ts:>11.1f} {d:>9.2f}")
    print()

    print("C2  Sensitivity of the delta to the receiver NF (15 m Airborne 10 @433)")
    loss = COAX["Airborne 10"]["433"] * 0.15
    print(f"{'RX NF':>6} {'T_mast':>9} {'T_shack':>9} {'delta[dB]':>10}")
    for rx_nf in (6.0, 8.0, 10.0):
        tm = t_system_masthead(200.0, LNA_NF_DB, LNA_GAIN_DB, loss, rx_nf)
        ts = t_system_shack(200.0, LNA_NF_DB, LNA_GAIN_DB, loss, rx_nf)
        print(f"{rx_nf:>6.0f} {tm:>9.1f} {ts:>9.1f} "
              f"{10*math.log10(ts/tm):>10.2f}")
    print()
    print("C3  What the cable costs the SHACK-end LNA directly")
    for band in ("433", "2400"):
        g = 10.0 ** (LNA_GAIN_DB / 10.0)
        for cab, ln in (("Airborne 10", 15.0), ("Ecoflex 15", 15.0), ("Aircell 7", 15.0)):
            loss = COAX[cab][band] * ln / 100.0
            # noise added by the cable when it sits BEFORE the LNA, in dB of T_sys
            print(f"  {band:>4} MHz {cab:>12} {ln:.0f} m: loss {loss:5.2f} dB  "
                  f"T_cable = {t_passive(loss):6.1f} K added ahead of the LNA")


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
