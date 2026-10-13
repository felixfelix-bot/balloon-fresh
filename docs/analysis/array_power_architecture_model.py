#!/usr/bin/env python3
"""
array_power_architecture_model.py

Reproducible model for docs/analysis/array-power-architecture.md.

Every input carries its citation inline. Every output prints its own formula.
stdlib only. Run:  python3 array_power_architecture_model.py
"""

import math

# ----------------------------------------------------------------------------
# INPUTS (cited)
# ----------------------------------------------------------------------------
# Cells [CITED docs/adr/049-wing-architecture.md "Measured inputs";
#        docs/analysis/wing-electrical.md 0.1]
SMALL_L, SMALL_W = 52.07, 19.65      # mm
SMALL_A_CM2 = 10.232                 # cm2  (52.07 x 19.65 mm = 1023.2 mm2)
SMALL_V, SMALL_I = 0.5, 0.4          # V, A (nominal, listing)
SMALL_G = 0.50                       # g   [component-guide per wing-electrical 3a]
LARGE_L, LARGE_W = 78.55, 38.90      # mm
LARGE_A_CM2 = 30.556                 # cm2  (78.55 x 38.90 mm = 3055.6 mm2)
LARGE_V, LARGE_I = 0.5, 1.2          # V, A  (1.2 A = area-scaled; TODO(unverified))
LARGE_G = 1.50                       # g

# Accepted array [CITED docs/adr/049-wing-architecture.md Decision;
#                 docs/analysis/wing-electrical.md 3(a)]
WINGS = 4
CELLS_PER_WING = 3
CELLS_ACCEPTED = WINGS * CELLS_PER_WING            # 12
V_WING = CELLS_PER_WING * LARGE_V                  # 1.5 V
V_ARRAY = WINGS * V_WING                           # 6.0 V
I_ARRAY = LARGE_I                                  # 1.2 A
P_WING = V_WING * LARGE_I                          # 1.80 W
P_ARRAY = V_ARRAY * I_ARRAY                        # 7.20 W

# Loads [CITED docs/adr/047-v9-power-provisioning.md 1.2; docs/POWER-BUDGET-V9-D2BE.md 2]
P_RADIO_PEAK = 5.5 * 1.118                         # 6.1495 W -> 6.15 W
P_AVG = 0.388                                      # W representative daylight average input
TX_DUTY = 0.01                                     # 1 % TX duty on the 5 V rail

# Bank [CITED docs/adr/047-v9-power-provisioning.md 3.1/3.2]
C_ACC, C_DBL = 1.65, 3.3                           # F
V_TOP, V_MIN = 5.4, 3.0                            # V
V_MIN_LDO = 3.5                                    # V  [POWER-BUDGET-V9-D2BE 1]

# Charge path [CITED docs/adr/006-supercapacitor-power.md Schottky]
V_DIODE = 0.3                                      # V BAT54 forward drop

# Radio supply limits [CITED docs/adr/047-v9-power-provisioning.md 5]
V_RADIO_MIN, V_RADIO_MAX = 3.0, 5.5                # V
V_FULL_PWR = 5.0                                   # V  -> 33.0 dBm row

# Board materials [CITED docs/adr/049-wing-architecture.md rejected-options table]
FR4_MG_CM2 = 127.6                                 # mg/cm2 for 0.6 mm FR4

# Margin convention for derived outlines [CITED docs/analysis/wing-electrical.md 3(a)]
GAP_MM, EDGE_MM = 6.0, 4.0                         # inter-cell gap, end margin


def hdr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def p(formula, value, unit=""):
    print(f"  {formula:<62s} = {value:>12,.4f} {unit}".rstrip())


def line(s=""):
    print(s)


# ----------------------------------------------------------------------------
hdr("S0. ACCEPTED ARRAY (baseline)")
p("V_wing = 3 cells x 0.5 V", V_WING, "V")
p("V_array = 4 wings x 1.5 V", V_ARRAY, "V")
p("I_array (large cell)", I_ARRAY, "A")
p("P_wing = 1.5 V x 1.2 A", P_WING, "W")
p("P_array = 6.0 V x 1.2 A", P_ARRAY, "W")
p("P_array / P_radio_peak (6.1495 W)", P_ARRAY / P_RADIO_PEAK, "x")
p("P_array / P_avg (0.388 W)", P_ARRAY / P_AVG, "x")

# ----------------------------------------------------------------------------
hdr("S1. THE COST OF PER-WING 6 V")
n_cells_6v = round(6.0 / LARGE_V)
p("cells per wing for 6.0 V = 6.0 V / 0.5 V", n_cells_6v, "cells")
tot_large = WINGS * n_cells_6v
tot_small = WINGS * n_cells_6v
p("cells total (4 wings, large)", tot_large, "cells")
p("cells total (4 wings, small)", tot_small, "cells")

area_large = tot_large * LARGE_A_CM2
area_small = tot_small * SMALL_A_CM2
area_base_large = CELLS_ACCEPTED * LARGE_A_CM2
area_base_small = CELLS_ACCEPTED * SMALL_A_CM2
mass_large = tot_large * LARGE_G
mass_small = tot_small * SMALL_G
mass_base_large = CELLS_ACCEPTED * LARGE_G
mass_base_small = CELLS_ACCEPTED * SMALL_G
P_pw_large = 6.0 * LARGE_I
P_pw_small = 6.0 * SMALL_I
P_arr_pw_large = WINGS * P_pw_large
P_arr_pw_small = WINGS * P_pw_small

line("\n  LARGE-cell build (12 large cells per wing):")
p("  P_wing = 6.0 V x 1.2 A", P_pw_large, "W")
p("  P_array = 4 x 7.2 W", P_arr_pw_large, "W")
p("  installed cell area = 48 x 30.556 cm2", area_large, "cm2")
p("  installed cell mass = 48 x 1.50 g", mass_large, "g")
line("\n  SMALL-cell build (12 small cells per wing):")
p("  P_wing = 6.0 V x 0.4 A", P_pw_small, "W")
p("  P_array = 4 x 2.4 W", P_arr_pw_small, "W")
p("  installed cell area = 48 x 10.232 cm2", area_small, "cm2")
p("  installed cell mass = 48 x 0.50 g", mass_small, "g")

line("\n  MULTIPLES vs the accepted 12-cell (3-large-per-wing) array:")
p("  cells   48 / 12", tot_large / CELLS_ACCEPTED, "x")
p("  area    %.1f / %.1f cm2" % (area_large, area_base_large), area_large / area_base_large, "x")
p("  mass    %.1f / %.1f g" % (mass_large, mass_base_large), mass_large / mass_base_large, "x")
p("  power   %.2f / %.2f W" % (P_arr_pw_large, P_ARRAY), P_arr_pw_large / P_ARRAY, "x")
line("  (accept. 12 large: area %.1f cm2, mass %.1f g, power %.2f W)"
     % (area_base_large, mass_base_large, P_ARRAY))
line("  (accept. 12 small: area %.1f cm2, mass %.1f g, power %.2f W)"
     % (area_base_small, mass_base_small, CELLS_ACCEPTED * SMALL_V * SMALL_I))

line("\n  IS THE PER-WING-6V ARRAY NEEDED AT ALL?")
p("  P_array(4x6V large) / P_radio_peak", P_arr_pw_large / P_RADIO_PEAK, "x")
p("  P_array(4x6V small) / P_radio_peak", P_arr_pw_small / P_RADIO_PEAK, "x")
p("  P_array(4x6V large) / P_avg", P_arr_pw_large / P_AVG, "x")
line("  accepted 12-large array / P_radio_peak = %.3f x  (already exceeds the max draw)"
     % (P_ARRAY / P_RADIO_PEAK))


def outline(rows, cols, cl, cw, gap=GAP_MM, edge=EDGE_MM):
    """width = rows*cell_w + (rows-1)*gap + 2*edge ; length = cols*cell_l + (cols-1)*gap + 2*edge"""
    width = rows * cw + (rows - 1) * gap + 2 * edge
    length = cols * cl + (cols - 1) * gap + 2 * edge
    return width, length


line("\n  WING OUTLINES for 12 cells per wing (mm):")
w, l = outline(4, 3, LARGE_L, LARGE_W)
p("  LARGE 4 rows x 3 cols: W = 4x38.90+3x6+8", w, "mm")
p("  LARGE 4 rows x 3 cols: L = 3x78.55+2x6+8", l, "mm")
line("     -> %.2f x %.2f mm board, %.1f cm2" % (l, w, l * w / 100.0))
w2, l2 = outline(2, 6, SMALL_L, SMALL_W)
p("  SMALL 2 rows x 6 cols: W = 2x19.65+1x6+8", w2, "mm")
p("  SMALL 2 rows x 6 cols: L = 6x52.07+5x6+8", l2, "mm")
line("     -> %.2f x %.2f mm board, %.1f cm2" % (l2, w2, l2 * w2 / 100.0))
w3, l3 = outline(1, 12, SMALL_W, SMALL_L)  # ADR-046 orientation: 52 mm across width
p("  SMALL ADR-046 orientation 12 along: W = 52.07+6", w3, "mm")
p("  SMALL ADR-046 orientation 12 along: L = 12x19.65+11x6+8", l3, "mm")
line("     -> %.2f x %.2f mm board, %.1f cm2" % (l3, w3, l3 * w3 / 100.0))
line("     ADR-049 3-large arm = 167.1 x 86.8 mm = %.1f cm2 -> 4x = %.1f cm2"
     % (167.1 * 86.8 / 100.0, 4 * 167.1 * 86.8 / 100.0))
line("     wing-electrical 3-large arm = 255.65 x 44.90 mm = %.1f cm2 -> 4x = %.1f cm2"
     % (255.65 * 44.90 / 100.0, 4 * 255.65 * 44.90 / 100.0))

# ----------------------------------------------------------------------------
hdr("S2. CAPACITOR vs REGULATOR (numbers only, prose in the doc)")
VOC_CELL_25, dVOC_dT = 0.62, -2.1e-3               # V, V/degC/cell [wing-electrical 5.1]
dT = -60 - 25
voc_cold = VOC_CELL_25 + dVOC_dT * dT
p("V_OC cell(-60C) = 0.62 + (-2.1e-3)x(-85)", voc_cold, "V")
p("V_OC 12-cell array(-60C)", 12 * voc_cold, "V")
p("through BAT54 (0.3 V)", 12 * voc_cold - V_DIODE, "V")
p("V_OC 12-cell array(25C)", 12 * VOC_CELL_25, "V")
line("  -> a '12-cell 6 V' wing's open-circuit output spans %.2f V (25C) to %.2f V (-60C):"
     % (12 * VOC_CELL_25, 12 * voc_cold))
line("     i.e. %.0f%% to %.0f%% above the nominal 6.0 V it is called."
     % (100 * (12 * VOC_CELL_25 / 6.0 - 1), 100 * (12 * voc_cold / 6.0 - 1)))

# ----------------------------------------------------------------------------
hdr("S3. THE REAL LIMIT (peak vs average)")
for k in (4, 3, 2, 1):
    pk = k * P_WING
    p("  %d wings: P = %d x 1.80 W" % (k, k), pk, "W")
    p("     vs P_radio_peak 6.1495 W -> ratio", pk / P_RADIO_PEAK, "x")
    p("     deficit", P_RADIO_PEAK - pk, "W")
line()
for k in (4, 3, 2, 1):
    pk = k * P_WING
    p("  %d wings: P / P_avg(0.388 W)" % k, pk / P_AVG, "x")
p("P_radio_peak / P_avg = duty-cycle ratio", P_RADIO_PEAK / P_AVG, "x")
line("\n  Voltage available at the string top (series string, no bypass):")
for k in (4, 3, 2, 1):
    p("  %d wings x 1.5 V" % k, k * 1.5, "V")
p("  bank design top (needs array > bank + diode)", V_TOP, "V")
for k in (3, 2):
    top = k * 1.5 - V_DIODE
    p("  bank top reachable with %d wings = %d x 1.5 V - 0.3 V" % (k, k), top, "V")
    E = 0.5 * C_DBL * (max(top, V_MIN) ** 2 - V_MIN ** 2)
    p("     usable bank energy to 3.0 V", E, "J")
    p("     endurance at 6.1495 W", E / P_RADIO_PEAK, "s")

# ----------------------------------------------------------------------------
hdr("S4. THE SERIES-CUT PROBLEM AND THE BYPASS DIODE")
p("string with 1 wing cut, bypass fitted: 3 x 1.5 V", 3 * 1.5, "V")
p("minus bypass Schottky drop 0.3 V", 3 * 1.5 - V_DIODE, "V")
p("design bank top", V_TOP, "V")
line("  can %.1f V charge a %.1f V bank? %s" % (3 * 1.5 - V_DIODE, V_TOP,
     "YES" if (3 * 1.5 - V_DIODE) > V_TOP else "NO"))
line("  => the bank can be charged only UP TO %.1f V with 3 of 4 wings." % (3 * 1.5 - V_DIODE))
Vr = 4.5
p("F33 output at 4.0 V rail (ADR-047 5 table)", 31.2, "dBm")
p("F33 output at 4.5 V rail", 31.8, "dBm")
p("interpolated at 4.2 V = 31.2 + 0.2x(31.8-31.2)/0.5", 31.2 + 0.2 * (31.8 - 31.2) / 0.5, "dBm")
p("vs 33.0 dBm at 5.0 V -> penalty", 33.0 - (31.2 + 0.2 * (31.8 - 31.2) / 0.5), "dB")
line("  full 2 W (33.0 dBm) requires >= 5.0 V  [ADR-047 5] -> NOT available with 3 wings")

# ----------------------------------------------------------------------------
hdr("S5. CONVERTER OPTION (MPPT boost/buck-boost, 3.0-6.5 V in, 5.4 V out)")
p("boost ratio at Vin=3.0 V: 5.4/3.0", 5.4 / 3.0, "x")
p("boost ratio at Vin=4.5 V: 5.4/4.5", 5.4 / 4.5, "x")
p("boost ratio at Vin=6.0 V (buck-boost needed)", 5.4 / 6.0, "x")
ETA = 0.85
p("ASSUMED efficiency (TODO(unverified))", ETA)
p("conversion loss fraction 1 - eta", 1 - ETA)
line("  Direct connection model (ASSUMPTION, stated): the array is clamped to the bank")
line("  voltage, so P_direct(Vb) = Vb x I_MPP = Vb x 1.2 A (CONSERVATIVE: a PV cell's")
line("  current rises above I_MPP as V falls toward I_sc, so the true figure is higher).")
line("  MPPT model: P_mppt = eta x P_MPP = eta x 7.20 W, INDEPENDENT of bank voltage.")
P_MPPT_OUT = ETA * P_ARRAY
p("converter output = 0.85 x 7.20 W", P_MPPT_OUT, "W")
print()
print("  %-10s %-12s %-12s %-12s" % ("bank V", "P_direct W", "P_mppt W", "MPPT gain"))
for vb in (3.0, 3.5, 4.0, 4.5, 5.0, 5.4):
    pd_ = vb * LARGE_I
    print("  %-10.1f %-12.2f %-12.2f %+11.1f%%"
          % (vb, pd_, P_MPPT_OUT, 100 * (P_MPPT_OUT / pd_ - 1)))
V_BREAKEVEN = P_MPPT_OUT / LARGE_I
p("break-even bank V = P_mppt / I_MPP", V_BREAKEVEN, "V")
line("  break-even as a fraction of bank top 5.4 V: %.3f (%.1f %%)"
     % (V_BREAKEVEN / 5.4, 100 * V_BREAKEVEN / 5.4))
line("  -> below %.2f V of bank voltage the converter wins on ENERGY; above it, direct wins."
     % V_BREAKEVEN)
p("quiescent: 1 uA at 5.4 V", 5.4 * 1e-6 * 1e6, "uW")
p("as fraction of ADR-036 100 uW night anchor", 5.4e-6 / 100e-6, "x")
line("  ADR-044 3 option (b) cost: EUR 1.50-4.00, 0.5-1.5 g, I_Q part-dependent, NOT selected")
line("  ADR-044 3 option (b) also forces: BOM active parts, ADR-030 placement keep-out,")
line("  ADR-032 simulation of switcher harmonics; ADR-029 5 tests 1 & 3 (<3 dB noise rise,")
line("  <1 dB GNSS C/N0 drop) become acceptance numbers.  [CITED ADR-044 3]")

# ----------------------------------------------------------------------------
hdr("S6. THE REDUNDANCY PRICE (full power with N-1 wings)")
need_per_wing = P_RADIO_PEAK
p("required per-wing power = P_radio_peak", need_per_wing, "W")
p("at 6.0 V that needs I = 6.1495/6.0", need_per_wing / 6.0, "A")
p("one 12-large string gives", 6.0 * LARGE_I, "W")
line("  => each self-contained wing must be 12 large cells (identical to S1).")
tot = 4 * 12
p("cells for 4 such wings", tot, "cells")
p("vs accepted 12", tot / 12.0, "x")
p("cell area", tot * LARGE_A_CM2, "cm2")
p("cell mass", tot * LARGE_G, "g")
line("  carrier: wing board 459.2-580.1 cm2 (S1); FR4 at 127.6 mg/cm2 =")
p("     459.2 cm2 x 0.1276 g/cm2", 459.2 * 0.1276, "g/wing")
p("     x4 wings", 4 * 459.2 * 0.1276, "g")
p("     580.1 cm2 variant x4", 4 * 580.1 * 0.1276, "g")
p("delta cell mass vs accepted (large)", tot * LARGE_G - 12 * LARGE_G, "g")
line("  NOTE: ADR-049 REJECTS the full-area FR4 carrier (2.61x heavier per cm2 than the")
line("  silicon it carries); the real carrier is spine+ribs, which still scales with area.")
line("\n  Parallel per-wing-6V buses: 4 wings x 1.2 A = 4.8 A at 6.0 V into the bank")
p("charge-path current re-rate", 4 * LARGE_I, "A")
p("vs accepted", (4 * LARGE_I) / LARGE_I, "x")

# ----------------------------------------------------------------------------
hdr("S7. RECOMMENDATION INPUTS")
p("accepted V_MPP / bank top", 6.0 / 5.4, "x")
p("n >= (5.4 + 0.3)/0.5 = 11.4 -> 12 cells (why 12)  [wing-electrical 5.3]", 11.4, "cells")
p("n <= 5.5/0.80 = 6.9 -> <=6 cells (cold V_OC limit)", 6.9, "cells")
line("  mutually exclusive -> a clamp is required regardless of series count.")
p("DECIDING NUMBER: P_radio_peak / P_avg = 6.1495 / 0.388", P_RADIO_PEAK / P_AVG, "x")
p("3 wings peak / P_avg = 5.40 / 0.388", 5.40 / P_AVG, "x")
line("=" * 78)
print("END OF MODEL")
