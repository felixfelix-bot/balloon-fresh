#!/usr/bin/env python3
"""Ground-station "amplifier vs antenna" cost + link model.

Reproduces every numeric table in
  docs/analysis/ground-station-amplifier-vs-antenna.md

Read the doc's "Reproduce" line:
    python3 docs/analysis/ground_station_amp_vs_ant_model.py

Physics/relationships used (all standard, stated so results are checkable):
  FSPL(dB)   = 20*log10(d_km) + 20*log10(f_MHz) + 32.44
  Aperture   D = (lambda/pi) * sqrt(10**(G/10) / eta)          (eta default 0.55)
  Beamwidth  HPBW = 70 * lambda / D            (standard practical formula)
  Pointing   = 0.10 * HPBW                     (operator's ~10% of beamwidth rule)
  Friis      F = F1 + (F2-1)/G1 + (F3-1)/(G1 G2) + ...
  T_ant      antenna noise temperature, *assumed* from a noise model (see doc)
  G/T(dB/K)  = G_ant(dBi) - 10*log10(T_sys(K)),  T_sys = T_ant + T_LNA + T_coax
  EIRP       = P_tx(dBm) + G_tx(dBi)
  P_rx       = EIRP - FSPL + G_rx

Every SOURCED input (price, NF, gain, P1dB, max input) is quoted with its URL in the
doc; this file only computes. Inputs marked ASSUMED are design assumptions and are
flagged as such in the doc (never presented as sourced).
"""
import math

def fspl(f_mhz, d_km):
    return 20*math.log10(d_km) + 20*math.log10(f_mhz) + 32.44

def aperture_d(g_dbi, f_mhz, eta=0.55):
    lam = 299.792458 / f_mhz        # metres
    return (lam/math.pi) * math.sqrt(10**(g_dbi/10.0)/eta)

def hpbw(g_dbi, f_mhz, eta=0.55):
    lam = 299.792458 / f_mhz
    return 70.0*lam/aperture_d(g_dbi, f_mhz, eta)

def db2lin(d): return 10**(d/10.0)
def db2nf(d): return 10**(d/10.0)          # noise factor from NF(dB)
def nf2db(f): return 10*math.log10(f)
def t_from_nf(nf_db, t0=290.0): return (db2lin(nf_db)-1)*t0
def dbm2w(p): return 10**(p/10.0)/1000.0
def w2dbm(w): return 10*math.log10(w*1000.0)

def cascade(stages):
    """stages: list of (NF_dB, gain_dB). Returns total NF in dB."""
    F = 0.0; Gc = 0.0
    first = True
    for nf, g in stages:
        Fi = db2nf(nf); Gi = db2lin(g)
        if first:
            F = Fi
            first = False
        else:
            F += (Fi-1.0)/db2lin(Gc)
        Gc += g
    return nf2db(F)

def hdr(t): print("\n" + "="*78 + "\n" + t + "\n" + "="*78)

# ----------------------------------------------------------------------------
hdr("1. FSPL at the two design bands")
for f in (433.05, 2400.0):
    print(f"  f={f:8.2f} MHz : " +
          "  ".join(f"{d:>6.0f}km={fspl(f,d):6.1f}dB" for d in (5,25,70,100,300,650)))
print(f"  433-vs-2400 delta @300km = {fspl(2400,300)-fspl(433.05,300):.1f} dB")

# ----------------------------------------------------------------------------
hdr("2. Gain -> aperture -> beamwidth -> pointing (eta=0.55)")
print("  2.4 GHz (lambda=12.49 cm)")
print("   G(dBi)  D(cm)   HPBW(deg)  pointer 10% (deg)")
rows_24 = []
for g in (0, 2, 6, 9, 12, 15, 18, 21, 24, 27):
    d = aperture_d(g, 2400.0); h = hpbw(g, 2400.0)
    rows_24.append((g, d*100, h, 0.1*h))
    print(f"   {g:5d}   {d*100:5.1f}   {h:7.1f}      {0.1*h:6.2f}")
print("\n  433 MHz (lambda=69.24 cm)")
print("   G(dBi)  D(cm)   HPBW(deg)  pointer 10% (deg)")
rows_433 = []
for g in (0, 2, 6, 9, 12, 15, 18, 21, 24, 27):
    d = aperture_d(g, 433.05); h = hpbw(g, 433.05)
    rows_433.append((g, d*100, h, 0.1*h))
    print(f"   {g:5d}   {d*100:5.1f}   {h:7.1f}      {0.1*h:6.2f}")
print("  NOTE: a Yagi is a long-aperture, not a dish; the 70*lambda/D beamwidth")
print("        is the pencil-beam equivalent. Yagi H/E planes differ (cite vendor).")

# ----------------------------------------------------------------------------
hdr("3. Balloon apparent angular rate at the ground station")
for v in (10, 30, 60):
    for d in (5, 70, 300):
        rate = math.degrees(v/(d*1000.0))     # deg/s
        print(f"  ground speed {v:2d} m/s @ {d:3d} km : {rate:.4f} deg/s = {rate*3600:6.1f} deg/h"
              f"   -> {rate*60:6.3f} deg per minute")
print("  A 10%-HPBW budget of 0.73 deg (27 dBi @2.4GHz) is consumed in:")
v, d = 30, 300
print(f"    {0.73/(math.degrees(v/(d*1000.0))):.0f} s at 30 m/s, 300 km  (telemetry-fed open loop fine)")
print("    At 5 km slant / 30 m/s the rate is 0.34 deg/s -> 0.73 deg in ~2 s (but link is then trivial).")

# ----------------------------------------------------------------------------
hdr("4. Friis cascade: ground 433 MHz RX chain (LNA -> coax -> receiver)")
print("  Coax: Ecoflex 15 loss 0.61 dB/10m @433 (SOURCED, BOM candidates F1)")
lna_nf, lna_g = 0.7, 20.0            # SSB Electronic LNA ISM 433 (SOURCED)
rx_nf = 6.0                          # ASSUMED ground receiver NF (mark TODO in doc)
for pre_m, post_m in ((0, 0), (5, 20), (10, 20), (20, 20), (40, 20), (80, 20)):
    L1 = 0.61*pre_m/10.0; L2 = 0.61*post_m/10.0
    with_lna = cascade([(L1, -L1), (lna_nf, lna_g), (L2, -L2), (rx_nf, 0)])
    no_lna   = cascade([(L1, -L1), (L2, -L2), (rx_nf, 0)])
    print(f"  pre-LNA coax {pre_m:3d} m ({L1:4.2f} dB), post-LNA {post_m:3d} m ({L2:4.2f} dB):"
          f"  NF {no_lna:5.2f} dB -> {with_lna:5.2f} dB   benefit {no_lna-with_lna:5.2f} dB")
print("  => the LNA's *benefit* = the NF of everything AFTER it (post-LNA coax + receiver),")
print("     ~6.4 dB here. Pre-LNA coax loss does not change the benefit, but it appears 1:1")
print("     in the absolute NF, so the LNA must be mast-mounted to keep system NF low.")

# ----------------------------------------------------------------------------
hdr("5. Receive noise temperature & G/T: narrow dish (cold sky) vs wide antenna (warm ground)")
# ASSUMED antenna noise temperatures (design assumptions, stated in doc):
cases = [
  ("2.4 GHz narrow (27 dBi) at cold sky",  2400, 27, 25.0),
  ("2.4 GHz wide  (6 dBi) sees warm ground", 2400, 6, 200.0),
  ("433 MHz narrow (15 dBi) at sky",       433, 15, 70.0),
  ("433 MHz wide  (7 dBi) sees warm ground",433, 7, 200.0),
]
for name, f, g, t_ant in cases:
    lna_nf = 0.7 if f < 1000 else 0.9
    t_lna = t_from_nf(lna_nf)
    t_sys = t_ant + t_lna
    gt = g - 10*math.log10(t_sys)
    print(f"  {name:42s} G={g:2d} dBi  T_ant={t_ant:5.0f} K T_LNA={t_lna:4.1f} K"
          f"  T_sys={t_sys:6.1f} K  G/T={gt:+6.2f} dB/K")
print("  Noise-temperature penalty of dropping the antenna gain (same LNA):")
print(f"    2.4 GHz: {10*math.log10((200+t_from_nf(0.9))/(25+t_from_nf(0.9))):.2f} dB")
print(f"    433 MHz: {10*math.log10((200+t_from_nf(0.7))/(70+t_from_nf(0.7))):.2f} dB")

# ----------------------------------------------------------------------------
hdr("6. 2.4 GHz PA: DC power, efficiency, heat")
pas = [("DXpatrol QO100-PA-1W  (+30 dBm, 5V/450mA)", 30.0, 5.0, 0.450),
       ("DXpatrol QO100-AMP12 @12V (5 W out)",     w2dbm(5.0), 12.0, None),
       ("DXpatrol QO100-AMP12 @28V (12 W out)",    w2dbm(12.0), 28.0, None)]
for name, pout, v, i in pas:
    if i is None:
        print(f"  {name:44s} P_out={pout:5.1f} dBm  DC current NOT PUBLISHED -> TODO")
        continue
    pdc = v*i
    print(f"  {name:44s} P_out={pout:5.1f} dBm  P_DC={pdc:5.2f} W  eff={dbm2w(pout)/pdc*100:4.1f}%"
          f"  heat~{pdc-dbm2w(pout):4.2f} W")
print("  Task's worked example (10 W @30% eff = 33 W DC): 12 W LDMOS at 45% eff = 26.7 W DC")
print("  -> 12 V rail: ~2.75 A (with the supplied 12/28 V step-up), i.e. a car battery, not a field pack.")

# ----------------------------------------------------------------------------
hdr("7. Balloon 2.4 GHz RX overload: range at which the ground EIRP saturates it")
print("  LR2021 Table 3-1 absolute max RF input = +10 dBm (SOURCED).")
print("  Demod saturation assumed -20..0 dBm (ASSUMED, mark TODO).")
print("  G_balloon(2.4GHz) = 10 dBi (ASSUMED, per link-budget doc 6-10 dBi).")
print("   P_tx   G_gtx    EIRP    range@-20dBm  range@0dBm  range@+10dBm(abs max)")
for p_tx, g_tx in ((30.0, 6.0), (30.0, 15.0), (30.0, 27.0),
                   (40.8, 6.0), (40.8, 27.0), (36.0, 6.0)):
    eirp = p_tx + g_tx
    def rng(limit):
        # P_rx = eirp - fspl(2400,d) + 10 ; solve fspl = eirp + 10 - limit
        need = eirp + 10.0 - limit
        # fspl = 20log10(d_km)+20log10(2400)+32.44
        km = 10**((need - 20*math.log10(2400.0) - 32.44)/20.0)
        return km*1000.0
    print(f"   {p_tx:5.1f}  {g_tx:5.0f}  {eirp:6.1f}   {rng(-20):8.0f} m  {rng(0):8.0f} m  {rng(10):8.0f} m")

# ----------------------------------------------------------------------------
hdr("8. Self-desense: 2.4 GHz ground PA coupling into the co-located 433 LNA")
print("  Free-space coupling 2.4 GHz, isotropic-to-isotropic (worst case, no isolation):")
for sep in (0.3, 1, 3, 10, 30, 100):
    cpl = fspl(2400.0, sep/1000.0)
    for p_tx in (30.0, 40.8):
        p_at = p_tx - cpl
        print(f"   sep {sep:5.1f} m: coupling {cpl:5.1f} dB -> {p_at:+7.1f} dBm at the 433 LNA input"
              f"  (P_tx {p_tx:.1f} dBm)  [LNA P1dB ~ -10..0 dBm -> {'BLOCKED' if p_at>-10 else 'ok'}]")
print("  Same-band RX LNA must be protected by a limiter and sequencing; a 433 BPF gives")
print("  tens of dB at 2.4 GHz but the fundamental of a 40 dBm PA still needs isolation.")

# ----------------------------------------------------------------------------
hdr("9. EUR per dB tables")
def eurdb(name, eur, db):
    print(f"  {name:52s} {eur:8.2f} EUR / {db:6.2f} dB = {eur/db:7.2f} EUR/dB")
print("\n  433 MHz Yagi (SOURCE: funktechnik-bielefeld, BOM candidates A1..A9)")
e433 = [("Sirio WY 400-3N 7 dBi", 99.0, 7.0), ("Sirio WY 400-6N 11 dBi", 132.0, 11.0),
        ("Sirio WY 400-10N 14 dBi", 155.0, 14.0), ("Diamond A-430S10R 13.1 dBi", 69.0, 13.1),
        ("Diamond A-430S15R 14.8 dBi", 74.5, 14.8), ("FlexaYagi FX7015V 12.4 dBi", 125.0, 12.4),
        ("FlexaYagi FX7044 16.6 dBi", 164.0, 16.6), ("FlexaYagi FX7073 18.0 dBi", 215.0, 18.0)]
for n, e, g in e433: eurdb(n, e, g)
print("  marginal 13.1->14.8 dBi:", f"{(74.5-69.0)/(14.8-13.1):.2f} EUR/dB")
print("  marginal 14.8->18.0 dBi:", f"{(215.0-74.5)/(18.0-14.8):.2f} EUR/dB")
print("\n  433 MHz LNA (SOURCE: wimo)")
eurdb("SSB Electronic LNA ISM 433 (20 dB gain, 0.7 dB NF)", 257.0, 20.0)
print("    ^ as RAW gain. As SYSTEM improvement it buys only the NF delta (see table 4):")
for benefit in (6.36, 5.0, 4.0):
    print(f"      - if it improves system NF by {benefit:4.2f} dB -> {257.0/benefit:6.2f} EUR/dB EFFECTIVE")
print("\n  2.4 GHz PA (SOURCE: wimo)")
eurdb("DXpatrol QO100-PA-1W (+18.5 -> +30 dBm = +12 dB)", 69.0, 12.0)
eurdb("DXpatrol QO100-AMP12 @28V (+18.5 -> +40.8 dBm = +22.3 dB)", 185.0, 22.3)
print("    (+ a 12/28 V step-up is included in the price; the DC energy is not)")
print("\n  2.4 GHz ground antenna (SOURCE: wimo + BOM candidates)")
eurdb("13 cm Yagi 2304 MHz (17-31 el, ~15-18 dBi)", 239.0, 12.0)
eurdb("Gibertini 75 SE Profi 0.75 m + 2.4 GHz feed(185)", 94.9+185.0, 18.0)
eurdb("Gibertini OP100SE 1.0 m + 2.4 GHz feed(185)", 143.9+185.0, 21.0)
print("\n  Coax (SOURCE: BOM candidates F1/F3)")
eurdb("Ecoflex 15 (0.61 dB/10m @433)", 13.60*10, 0.61)
eurdb("Airborne 10 / LMR-400 (0.76 dB/10m @433)", 6.50*10, 0.76)

# ----------------------------------------------------------------------------
hdr("10. Three candidate ground stations - all-in EUR/dB")
stations = [
 ("A antenna-led",
   "433: Sirio WY400-10N 14 dBi (155) | 2.4: 1.0m Ku dish+feed (329) | tracker SPID RAS (1260.8) | "
   "mast/coax (300)",
   155+328.9+1260.82+300, 14+21),
 ("B amplifier-led",
   "433: Sirio WY400-3N 7 dBi (99) + 433 LNA (257) | 2.4: 7 dBi Yagi+whip (60) + 12W PA (185) | "
   "tracker open-loop stepper (40) | mast/coax incl BPF/limiter/relay (400)",
   99+257+60+185+40+400, 7+6.4+ (40.8-18) + (6-0)),
 ("C balanced",
   "433: Diamond A-430S15R 14.8 dBi (74.5) + 433 LNA optional | 2.4: 13cm Yagi 15 dBi (239) + "
   "1W PA (69) | tracker light rotator G-450CDC (399) | mast/coax (250)",
   74.5+239+69+399+250, 14.8+15+12),
]
print("  (link dB = sum of the RX-antenna gain + TX-EIRP gain used in each column;")
print("   see the doc for the per-direction budget and tracker class)")
for n, desc, cost, db in stations:
    print(f"\n  [{n}] cost = {cost:.0f} EUR, link dB awarded = {db:.1f}, EUR/dB = {cost/db:.2f}")
    print("     " + desc)

print("\nDone.")
