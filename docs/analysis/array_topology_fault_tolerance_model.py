#!/usr/bin/env python3
"""
array_topology_fault_tolerance_model.py

Stdlib-only calculator for `docs/analysis/array-topology-fault-tolerance.md`.
Prints every number quoted in that document's topology tables.

Every INPUT is either CITED (repo file named in the comment), READ FROM A VENDOR
PRODUCT PAGE (dated, in the comment), or marked TODO(unverified). No figure is
invented and no part number is invented.

Run:  python3 docs/analysis/array_topology_fault_tolerance_model.py
"""

# ---------------------------------------------------------------- INPUTS (cited)
N_CELLS        = 12          # ADR-006 / ADR-049 / ADR-051 S1.1  (4 wings x 3)
CELLS_PER_WING = 3           # ADR-006
N_WINGS        = 4
V_CELL         = 0.50        # V  nominal MPP per cell (ADR-049 Measured inputs)
I_CELL         = 1.20        # A  large-cell current (ADR-049; wing-electrical S0.2)
A_CELL         = 30.6        # cm2 (ADR-049; ADR-051 S1.4)
P_CELL         = V_CELL * I_CELL           # 0.60 W
DENSITY        = P_CELL / A_CELL * 1000.0  # mW/cm2 -> 19.608 (ADR-051 S1.4)
V_OC_CELL_25   = 0.62        # V   TODO(unverified) - wing-electrical S5.1
D_VDT          = -2.1e-3     # V/degC/cell TODO(unverified) - wing-electrical S5.1
T_FLIGHT       = -60.0       # degC design case (ADR-050 S3.2)
T_ASSY         = 25.0

V_BANK_TOP     = 5.40        # ADR-006 / ADR-050 S3.3
V_BANK_FLOOR   = 3.00        # ADR-047 S3.2
E_BANK_USABLE  = 33.264      # J  ADR-047 S3.2
P_AVG          = 0.388       # W  POWER-BUDGET-V9-D2BE line 85 (daylight average)
P_PEAK         = 6.15        # W  ADR-047 S1.2
P_NIGHT        = 100e-6      # W  ADR-036 night anchor
DAY_H          = 7.852       # h  50 N winter solstice (wing-omnidirectional, H0=58.8884)
F_VERT         = 0.30511     # rotation factor, cells on VERTICAL planes (ADR-051 S1.4)
F_HORZ_DAY     = 0.18653     # day-mean, cells on HORIZONTAL plane (ADR-051 S1.4)
V_FLOOR_TI     = 2.50        # V  TPS63060 VIN min   (TI product page, verified)
V_FLOOR_LTC    = 2.70        # V  LTC3115-1 VIN min  (ADI product page, verified)
ETA            = 0.85        # ADR-050 S1 assumed power-path efficiency TODO(unverified)
V_F_DIODE      = 0.38        # V bypass V_F at 1.2 A - interpolated from PMEG4030ER's
                             #   460 mV @ 3 A -> TODO(unverified) at 1.2 A
LAND_I_MAX     = 2.73        # A  4.0x1.2 mm land, 1 oz, dT=10C (wing-electrical S6.3)
D_MASS_G       = 9e-3        # g/diode ESTIMATE from SOD123W 2.6x1.7x1.0 mm @ 2 g/cm3
                             #   TODO(unverified) - no datasheet states mass

def v_oc_cold(n):
    return n * (V_OC_CELL_25 + (-D_VDT) * (T_ASSY - T_FLIGHT))

def pct(x):
    return f"{100.0*x:.2f}%"

def i2r(i):
    return (i / I_CELL) ** 2

print("=" * 78)
print("ARRAY TOPOLOGY FAULT-TOLERANCE MODEL")
print("=" * 78)

print("\n--- 0. Baseline arithmetic -------------------------------------------")
print(f"P_cell             = {V_CELL} V x {I_CELL} A = {P_CELL:.2f} W")
print(f"density            = {DENSITY:.3f} mW/cm2 (nameplate, ADR-051 S1.4)")
print(f"P_wing             = {CELLS_PER_WING*V_CELL:.2f} V x {I_CELL} A = "
      f"{CELLS_PER_WING*V_CELL*I_CELL:.2f} W")
print(f"P_array            = {N_CELLS*V_CELL:.2f} V x {I_CELL} A = "
      f"{N_CELLS*V_CELL*I_CELL:.2f} W")
print(f"cold Voc 12s/6s/3s/1 = {v_oc_cold(12):.4f} / {v_oc_cold(6):.4f} / "
      f"{v_oc_cold(3):.4f} / {v_oc_cold(1):.4f} V")
print(f"bank-side current  = 7.20/{V_BANK_TOP} = {7.20/V_BANK_TOP:.3f} A  "
      f"(IDENTICAL in every topology)")
print(f"all-parallel I     = 7.20/{V_CELL} = {7.20/V_CELL:.2f} A ; "
      f"ratio {7.20/V_CELL/I_CELL:.0f}x -> I2R {(7.20/V_CELL/I_CELL)**2:.0f}x "
      f"(the brief's 144x)")

print("\n--- 1. Topology table (nominal V/I/P, I2R, land, cold Voc) -----------")
# name, V_nom, I_top(array side), n_series of the string the converter sees
TOPO = [
    ("T1  12S  + 12 cell diodes (no hub diode)", 6.00, 1.20, 12),
    ("T2  12S  +  4 group diodes",               6.00, 1.20, 12),
    ("T3  4P x 3S (1.5V) + 4 blocking",          1.50, 4.80, 3),
    ("T4  2S2P (3.0V) + 2 blocking",             3.00, 2.40, 6),
    ("T5  12P (0.5V) + 4 blocking",              0.50,14.40, 1),
    ("T6a 12S + 12 cell AND 4 wing diodes",      6.00, 1.20, 12),
    ("T7  4 x (3S + own harvester)",             1.50, 1.20, 3),
]
for name, v, i, ns in TOPO:
    print(f"{name:42s} V={v:5.2f} I_array={i:5.2f} "
          f"I2R={i2r(i):6.1f}x land_margin={LAND_I_MAX/i:5.2f}x "
          f"coldVoc={v_oc_cold(ns):5.2f}V")

print("\n--- 2. Converter INPUT CURRENT at 7.2 W ------------------------------")
print(f"ideal I_in = 7.20/V_nom ; at eta={ETA:.2f}: I_in = 7.20/({ETA}*V_nom)")
for name, v, i, ns in TOPO:
    if name.startswith("T7"):
        print(f"{name:42s} per string 1.80 W: ideal {1.80/v:.2f} A ; "
              f"@85% {1.80/(ETA*v):.2f} A  (x4 converters)")
    else:
        print(f"{name:42s} ideal {7.20/v:5.2f} A ; @85% {7.20/(ETA*v):5.2f} A")

print("\n--- 3. Cracked cell: OPEN (1 of 12 cells) ----------------------------")
r = ((12-1)*V_CELL - V_F_DIODE) / (12*V_CELL)
print(f"T1 / T6a  per-cell diode conducts, 1 cell lost: keeps {pct(r)} "
      f"(loss {pct(1-r)}) = {r*7.2:.2f} W")
r2 = ((12-3)*V_CELL - V_F_DIODE) / (12*V_CELL)
print(f"T2  group diode shorts the whole 3-cell group:  keeps {pct(r2)} "
      f"(loss {pct(1-r2)}) = {r2*7.2:.2f} W  <- 3 cells lost for 1 crack")
r0 = ((12-1)*V_CELL) / (12*V_CELL)
print(f"UNPROTECTED series (no diode at all):          keeps {pct(0.0)} "
      f"-> 0.00 W  (string current = 0; this is the defect)")
print(f"T3  4 parallel strings, 1 string open  : loss 25.00% = 5.40 W")
print(f"T4  2S2P, 1 branch open                : loss 50.00% = 3.60 W "
      f"(the surviving 3.0 V branch blocks the 1.5 V one)")
print(f"T5  12 parallel cells, 1 open          : loss  8.33% = 6.60 W")
print(f"T7  4 independent strings, 1 open      : loss 25.00% = 5.40 W "
      f"(with per-cell bypass in the wing: 8.33%)")

print("\n--- 4. Cracked cell: SHORTED (1 of 12 cells) -------------------------")
print("series string: a hard short is a CONDUCTOR - the string continues with "
      "n-1 cells")
print(f"  T1/T2/T6a: loss {1/12*100:.2f}% = 6.60 W (benign; the cell's own "
      f"bypass diode is simply shorted out too)")
print("  a SOFT/partial short is the real series defect: it eats string voltage "
      "and makes a local hot spot -> TODO(unverified) magnitude")
print("parallel group: a short CLAMPS the common node -> the other cells dump "
      "their current into it")
print(f"  T5  12P: 1 shorted cell -> the other 11 deliver 11 x 1.2 = "
      f"{11*I_CELL:.1f} A into the short; array ~0 W  = ~100% loss (WORST CASE)")
print(f"  T3  4P : 1 shorted cell -> that string runs at 1.0 V and is blocked; "
      f"loss 25.00%")
print(f"  T4  2S2P: 1 shorted cell -> that branch at 2.5 V is blocked by the "
      f"3.0 V branch; loss 50.00%")
print(f"  T7  4 indep: 1 shorted cell -> that wing at 1.0 V is below its own "
      f"converter's MPP; ~8.33-25% loss")

print("\n--- 5. WING CUT (the 3 cells of one wing removed) --------------------")
print("reading (a) cut ABOVE the wing's cell diodes (diodes survive, 3 drops):")
v = 9*V_CELL - 3*V_F_DIODE
print(f"   T1 as written: 9 cells - 3 x {V_F_DIODE} V = {v:.2f} V -> "
      f"{v*I_CELL:.2f} W, loss {pct(1-v*I_CELL/7.2)}")
print("reading (b) cut AT THE TAB (cell diodes leave with the wing -> the hub "
      "per-interface diode must carry):")
v = 9*V_CELL - 1*V_F_DIODE
print(f"   T2 / T6a: 9 cells - 1 x {V_F_DIODE} V = {v:.2f} V -> "
      f"{v*I_CELL:.2f} W, loss {pct(1-v*I_CELL/7.2)}  usable(>=2.5V)? "
      f"{'YES' if v>=V_FLOOR_TI else 'NO'}")
print(f"   T1 WITHOUT a hub diode: socket lands open -> string OPEN -> 0.00 W, "
      f"loss 100.00%  <- T1-as-specified is NOT cut tolerant")
print(f"T3  4P: 3 wings stay at 1.50 V -> 5.40 W, loss 25.00% ; "
      f"V=1.50 V usable? NO (< {V_FLOOR_TI} V floor of every wide-input part)")
print(f"T4  2S2P: 1.5 V pair is blocked by the 3.0 V pair -> 3.60 W, "
      f"loss 50.00% ; V=3.00 V usable? YES")
print(f"T5  12P: 9 cells at 0.50 V -> 5.40 W, loss 25.00% ; V=0.50 V usable? NO")
print(f"T7  4 indep: the cut wing's harvester idles; the 3 survivors are "
      f"unchanged -> 5.40 W, loss 25.00% ; per-string V=1.50 V, no change")

print("\n--- 6. Post-cut ladder vs the converter floor (series family) --------")
print("Each CUT wing leaves its own hub bypass diode in the string, and those")
print("bypassed POSITIONS ARE IN SERIES with each other -> the drops ADD.")
for cuts, lab in [(0,"0 cuts"),(1,"1 cut"),(2,"2 cuts"),(3,"3 cuts"),(4,"4 cuts")]:
    cells = 12 - 3*cuts
    if cells == 0:
        print(f"{lab:8s}  0 cells                          V=0.00 V  "
              f"no charge                       (ADR-051 tab: 0 V)")
        continue
    v = cells*V_CELL - cuts*V_F_DIODE
    ok50 = "charges" if v>=V_FLOOR_TI else "does NOT charge"
    okLTC = "charges" if v>=V_FLOOR_LTC else "does NOT charge"
    print(f"{lab:8s} {cells:2d} cells - {cuts}x{V_F_DIODE} V drop  V={v:5.2f} V"
          f"  TPS63060(2.5 V): {ok50:15s}"
          f"  LTC3115-1(2.7 V): {okLTC:15s}"
          f"  (ADR-051 tab: {cells*V_CELL:.2f} V, charges)")
print("  -> ADR-051 S2.4's table gives the RAW cell voltage and omits the "
      "bypass-diode drop;")
print("     with it, the 2-cut case is 2.24 V, below the 2.5 V floor of every "
      "verified part.")

print("\n--- 7. Diode count / mass / land check ------------------------------")
print("VERIFIED part: PMEG4030ER  40 V / 3 A low-VF Schottky, SOD123W "
      "(2.6 x 1.7 mm),")
print("  I_F(AV) <= 3 A (delta=0.5, 20 kHz, T_amb <= 40 C), V_F 460 mV typ / "
      "540 mV max @ 3 A,")
print("  T_amb -55..150 C, T_stg -65..150 C  (Nexperia, 23 Jan 2023)")
print("VERIFIED part: PMEG4020ER  40 V / 2 A, same SOD123W package, "
      "T_amb -55..150 C")
print("  NOTE both are rated to -55 C ambient; the design case is -60 C "
      "-> 5 C CROSSED (see open items)")
print("NOTE I_F(AV) is a delta=0.5 (20 kHz) rating. The permanent-continuous "
      "bypass path is")
print("  delta=1 (DC) -> read the DC curve, Fig. 9/11, not the 2/3 A headline. "
      "TODO(unverified)")
for name, nd in [("T1",12),("T2",4),("T3",4),("T4",6),("T5",4),("T6a",16),("T7",4)]:
    print(f"  {name:4s} diodes={nd:2d}  I_cont=1.20 A ({3.0/1.2:.2f}x under a "
          f"3 A part)  est. mass={nd*D_MASS_G*1000:.0f} mg "
          f"[{D_MASS_G*1000:.1f} mg/diode ESTIMATE, TODO(unverified)]")

print("\n--- 8. Part admissibility matrix ------------------------------------")
# (part, topology family it can serve, VINmin, VINmax, Iout, Iq_run, Iq_sd, note)
print(f"{'part':12s} {'VIN min':>8s} {'VIN max':>8s} {'Iout':>16s} "
      f"{'Iq run':>8s} {'Iq sd':>8s}")
MATRIX = [
 ("TPS63060",  2.50, 12.0, "2 A @5V buck",       "30 uA",  "-"),
 ("TPS63070",  2.00, 16.0, "2 A buck/boost",     "50 uA",  "-"),
 ("TPS63020",  1.80,  5.5, "2 A @3.3V",          "25 uA",  "-"),
 ("TPS63030",  1.80,  5.5, "0.5-0.8 A",          "25 uA",  "-"),
 ("TPS61200",  0.30,  5.5, "0.6 A @5V",          "50 uA",  "-"),
 ("TPS61099",  0.70,  5.5, "~0.3 A @5V",         "0.8/1 uA","-"),
 ("BQ25570",   0.60,  5.1, "0.1 A charge",       "488 nA", "<5 nA"),
 ("LTC3105",   0.225, 5.0, "0.4 A switch",       "24 uA",  "-"),
 ("LTC3129-1", 2.42, 15.0, "0.2 A (buck mode)",  "1.3 uA", "10 nA"),
 ("LTC3115-1", 2.70, 40.0, "1 A(V>=3.6)/2 A SD", "30 uA",  "3 uA"),
 ("ADP5091/92",0.08,  3.3, "0.15 A",             "510 nA", "-"),
 ("LM2623",    0.80, 14.0, "2.85 A switch(boost)","80 uA", "-"),
 ("SPV1040",   0.30,  5.5, "1.8 A pk",           "TODO",   "-"),
]
for p, vmin, vmax, iout, iq, iqsd in MATRIX:
    print(f"{p:12s} {vmin:8.3f} {vmax:8.1f} {iout:>16s} {iq:>8s} {iqsd:>8s}")

print("\n  (all TI/ADI figures: vendor product-page parameter tables, read "
      "2026-10-07;")
print("   SPV1040: ST product page via web.archive.org, read 2026-10-07)")
print("\n  REQUIRED: 1.57 A out at 5.4 V (7.20 W / 5.40 V / 0.85 = "
      f"{7.20/5.40/ETA:.3f} A)")
print("  REQUIRED night-quiet: Iq <= 5 uA (ADR-050 S3.6) = "
      f"{5e-6*V_BANK_TOP*1e6:.1f} uW = "
      f"{5e-6*V_BANK_TOP/P_NIGHT*100:.0f}% of the 100 uW anchor")
print("\n  series family (T1/T2/T6a) needs 1.5-9.58 V AND ~1.57 A AND Iq<=5uA")
print("    -> ONLY LTC3115-1 satisfies all three (2.7-40 V; 1-2 A; 3 uA shutdown)")
print("  parallel family (T3/T5) needs 0.5-3.0 V AND ~1.57 A AND Iq<=5uA")
print("    -> NO verified part: every sub-uA part caps at 0.1-0.4 A")
print("  per-string family (T7) needs 1.5-2.40 V AND 0.42 A per string "
      "(x4) AND Iq<=5uA")
print("    -> SPV1040 (0.3-5.5 V, 1.8 A pk, MPPT, TSSOP8) on voltage+current; "
      "Iq TODO")

print("\n--- 9. Winter-night requirement --------------------------------------")
night_J = P_NIGHT * (24 - DAY_H) * 3600
day_J   = P_AVG * DAY_H * 3600
print(f"dark            = {24-DAY_H:.2f} h  (brief says ~15 h; repo day-length "
      f"{DAY_H} h)")
print(f"night energy    = {P_NIGHT} W x {24-DAY_H:.2f} h = {night_J:.2f} J")
print(f"usable bank     = {E_BANK_USABLE} J -> covers the night "
      f"{E_BANK_USABLE/night_J:.1f}x over")
print(f"daytime load    = {P_AVG} W x {DAY_H} h = {day_J:.0f} J")
print(f"required day-mean P = (day+night)/(day h) = "
      f"{(day_J+night_J)/(DAY_H*3600)*1000:.3f} mW")
print(f"  -> +{night_J/(DAY_H*3600)*1e6:.1f} uW on {P_AVG*1000:.0f} mW = "
      f"+{pct(night_J/(DAY_H*3600)/P_AVG)}  (does NOT change the sizing)")
print(f"  worst case: drain the FULL {E_BANK_USABLE} J every night -> "
      f"+{(E_BANK_USABLE)/(DAY_H*3600)*1e6:.0f} uW = "
      f"+{pct(E_BANK_USABLE/(DAY_H*3600)/P_AVG)}  (still does not change it)")
