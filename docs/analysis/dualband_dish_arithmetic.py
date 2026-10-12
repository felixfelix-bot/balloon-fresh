#!/usr/bin/env python3
"""
Reproduce the key dualband dish arithmetic from docs/analysis/dualband-single-dish.md.

Usage: python3 docs/analysis/dualband_dish_arithmetic.py
"""
import math

c = 299.792458e6  # m/s

f_24 = 2.4e9
f_433 = 433e6
f_ku = 12.0e9

lam_24 = c / f_24
lam_433 = c / f_433
lam_ku = c / f_ku


def aperture_gain(diameter, wavelength, eta=0.60):
    return 10.0 * math.log10(eta * (math.pi * diameter / wavelength) ** 2)


def print_section(title):
    print(f"\n=== {title} ===")


print_section("Wavelengths")
print(f"lambda(2.4 GHz)  = {lam_24 * 1000:6.1f} mm")
print(f"lambda(433 MHz)  = {lam_433 * 1000:6.1f} mm")
print(f"lambda(12 GHz)   = {lam_ku * 1000:6.2f} mm")

print_section("Surface accuracy rules")
for rule, frac in [("lambda/20", 20), ("lambda/16", 16)]:
    print(f"{rule:12s} @ 2.4 GHz = {lam_24 / frac * 1000:4.1f} mm")
    print(f"{rule:12s} @ 433 MHz  = {lam_433 / frac * 1000:4.1f} mm")
    print(f"{rule:12s} @ 12 GHz   = {lam_ku / frac * 1000:5.2f} mm")

print_section("Ruze surface-error loss")
for sigma_mm in [0.3, 0.5, 1.0]:
    sigma = sigma_mm / 1000.0
    for name, lam in [("2.4 GHz", lam_24), ("433 MHz", lam_433), ("12 GHz", lam_ku)]:
        eta_ratio = math.exp(-(4 * math.pi * sigma / lam) ** 2)
        loss_db = -10.0 * math.log10(eta_ratio)
        print(f"  sigma={sigma_mm}mm @ {name:8s}: {loss_db:6.3f} dB")

print_section("Gain vs diameter (eta=0.60)")
print(f"{'D (m)':>6s}  {'G@2.4GHz':>10s}  {'G@433MHz':>10s}")
for D in [0.6, 0.9, 1.2, 1.5, 3.0, 5.0]:
    print(f"{D:6.1f}  {aperture_gain(D, lam_24):9.1f} dBi  {aperture_gain(D, lam_433):9.1f} dBi")

print_section("D for target gain at 433 MHz")
for eta in [0.55, 0.65]:
    for target in [15.0, 20.0]:
        # G = 10*log10(eta*(pi*D/lam)^2)  =>  D = (lam/pi)*10^((G - 10*log10(eta))/20)
        D = (lam_433 / math.pi) * 10 ** ((target - 10.0 * math.log10(eta)) / 20.0)
        print(f"  eta={eta:.2f}, target={target:.0f} dBi -> D={D:.2f} m")

print_section("Feed illumination half-angle")
print(f"{'f/D':>6s}  {'theta (deg)':>12s}")
for fd in [0.35, 0.4, 0.5, 0.6, 0.7]:
    theta = 2.0 * math.degrees(math.atan(1.0 / (4.0 * fd)))
    print(f"{fd:6.2f}  {theta:11.1f}")

print_section("Lambda/4 feed positioning tolerance")
print(f"lambda/4 @ 433 MHz  = {lam_433 / 4 * 1000:5.1f} mm")
print(f"lambda/4 @ 2.4 GHz  = {lam_24 / 4 * 1000:5.1f} mm")

print_section("Electrical size of a 2.4 GHz feed at 433 MHz")
feed_size = lam_24 / 2.0
print(f"2.4 GHz lambda/2 feed = {feed_size * 1000:.1f} mm")
print(f"In wavelengths at 433 MHz = {feed_size / lam_433:.3f} lambda")

print_section("Defocus loss estimate (lambda/4 = 1 dB rule)")
for delta_cm in [2, 5, 10, 15]:
    delta = delta_cm / 100.0
    frac_433 = delta / (lam_433 / 4.0)
    frac_24 = delta / (lam_24 / 4.0)
    print(
        f"  delta={delta_cm:2d} cm: 433MHz ~{1.0 * frac_433 ** 2:5.3f} dB, "
        f"2.4GHz ~{1.0 * frac_24 ** 2:5.1f} dB"
    )

print_section("3 dB beamwidth")
print(f"{'D (m)':>6s}  {'HPBW@2.4GHz':>12s}  {'HPBW@433MHz':>12s}")
for D in [0.9, 1.2, 1.5]:
    hpbw_24 = 70.0 * lam_24 / D
    hpbw_433 = 70.0 * lam_433 / D
    print(f"{D:6.1f}  {hpbw_24:11.1f} deg  {hpbw_433:11.1f} deg")

print("\nDone.")
