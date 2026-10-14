#!/usr/bin/env python3
"""Panel + envelope masses from the operator's 2026-10-14 scale readings.

Prints every number in docs/analysis/MEASURED-MASSES-2026-10-14.md.
stdlib only; no arguments.

Run:  python3 docs/analysis/panel_mass_measured.py
"""

# ---- raw readings, tier: user-measured (Felix, 2026-10-14) -------------------
PACK_LARGE = (10, 14.04)    # (count, grams)
PACK_SMALL = (10, 4.462)
ONE_LARGE = 1.382
ONE_SMALL = 0.440
ENVELOPE_YOKOHAMA = 46.84

# ---- repo outlines (ADR-049 "measured inputs") ------------------------------
OUTLINE_LARGE_MM = (78.55, 38.90)
OUTLINE_SMALL_MM = (52.07, 19.65)

# ---- repo assumptions to reconcile against ----------------------------------
ASSUMED_MODEL_G = 1.5       # docs/analysis/wing_mass_model.py
ASSUMED_OLD_G = 0.8         # earlier budgets
ASSUMED_THINFILM_G = 0.4    # PAYLOAD-WEIGHT-ESTIMATES.md recommendation

# ---- envelope figures already in the number bank ---------------------------
ENV_VALVED_COMMUNITY = 41.0
ENV_VALVELESS_COMMUNITY = 48.6

# ---- budget terms (20 C) ----------------------------------------------------
THRESHOLD_G = 20.0
HELIUM_G = 4.17             # 20 g payload + 6 g free lift @ 20 C
ATTACHMENTS_G = 2.20


def area_cm2(dims_mm):
    return dims_mm[0] * dims_mm[1] / 100.0


def report(name, pack, one, dims_mm):
    n, total = pack
    mean = total / n
    A = area_cm2(dims_mm)
    print(f"\n--- {name} ---")
    print(f"  single            : {one:.3f} g")
    print(f"  {n}-pack            : {total:.3f} g  ->  mean {mean:.4f} g")
    print(f"  agreement         : {abs(mean - one) / one * 100:.2f} %")
    print(f"  outline           : {dims_mm[0]} x {dims_mm[1]} mm  = {A:.3f} cm2")
    print(f"  areal (10-pack)   : {mean / A * 1000:.2f} mg/cm2")
    print(f"  areal (single)    : {one / A * 1000:.2f} mg/cm2")
    return mean, A


print("=" * 68)
print("SOLAR CELL MASSES  (tier: user-measured, 2026-10-14)")
print("=" * 68)
m_large, A_large = report("LARGE", PACK_LARGE, ONE_LARGE, OUTLINE_LARGE_MM)
m_small, A_small = report("SMALL", PACK_SMALL, ONE_SMALL, OUTLINE_SMALL_MM)

print("\n--- identification check (areal density must lie on one line) ---")
print(f"  mass ratio  large/small : {m_large / m_small:.3f}")
print(f"  area ratio  large/small : {A_large / A_small:.3f}")
print(f"  areal ratio             : {(m_large / A_large) / (m_small / A_small):.3f}")
print(f"  -> alt reading (large = {OUTLINE_SMALL_MM[0]}x{OUTLINE_SMALL_MM[1]}) would give"
      f" {m_large / A_small * 1000:.0f} mg/cm2: IMPLAUSIBLE, rejected")

print("\n--- reconciliation with repo assumptions (LARGE cell) ---")
for label, assumed in (("wing_mass_model.py 1.5 g", ASSUMED_MODEL_G),
                       ("old budget 0.8 g", ASSUMED_OLD_G)):
    d = m_large - assumed
    print(f"  measured {m_large:.4f} g vs {label:24s}: {d:+.4f} g ({d / assumed * 100:+.1f} %)")
d = m_small - ASSUMED_THINFILM_G
print(f"  measured {m_small:.4f} g vs {'thin-film ~0.4 g':24s}: {d:+.4f} g ({d / ASSUMED_THINFILM_G * 100:+.1f} %)")

print("\n--- array totals ---")
print(f"  12 LARGE cells (ADR-049 primary, 3/wing) : {12 * m_large:.2f} g")
print(f"  36 SMALL cells (ADR-049 fallback, 9/wing): {36 * m_small:.2f} g")
print(f"  (PAYLOAD-WEIGHT-ESTIMATES.md carries a 4-cell array at 1.6 g)")
print(f"  4 LARGE cells would be                   : {4 * m_large:.2f} g")
print(f"  4 SMALL cells would be                   : {4 * m_small:.2f} g")

print("\n" + "=" * 68)
print("ENVELOPE  (tier: user-measured, 2026-10-14)")
print("=" * 68)
print(f"  Yokohama envelope, as-shipped : {ENVELOPE_YOKOHAMA:.2f} g")
print(f"  community, old valved         : {ENV_VALVED_COMMUNITY:.1f} g")
print(f"  community, new valveless      : {ENV_VALVELESS_COMMUNITY:.1f} g")
print(f"  delta vs valveless (the one the budget used): "
      f"{ENVELOPE_YOKOHAMA - ENV_VALVELESS_COMMUNITY:+.2f} g")

print("\n--- the subtraction (total-mass reading) ---")
budget = THRESHOLD_G - ENVELOPE_YOKOHAMA - HELIUM_G - ATTACHMENTS_G
print(f"  {THRESHOLD_G:8.2f} g  threshold")
print(f"  {-ENVELOPE_YOKOHAMA:8.2f} g  envelope (MEASURED, was -{ENV_VALVELESS_COMMUNITY})")
print(f"  {-HELIUM_G:8.2f} g  helium (20 g payload + 6 g free lift, 20 C)")
print(f"  {-ATTACHMENTS_G:8.2f} g  attachments")
print(f"  {'-' * 8}")
print(f"  {budget:8.2f} g  -> NO payload budget; envelope is "
      f"{ENVELOPE_YOKOHAMA / THRESHOLD_G:.2f}x the {THRESHOLD_G:.0f} g threshold")
