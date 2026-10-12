#!/usr/bin/env python3
"""
insolation_factors.py — reproducible arithmetic for
docs/analysis/wing-insolation-geometry.md (branch analysis/wing-insolation).

Every number quoted in that document is printed by this script.

Physical model
--------------
A flat solar panel's per-unit-area output is  f = cos(theta)  where theta is the
angle between the panel normal and the unit sun vector.  Negative cosine = the
panel faces away = zero output, so all rotation averages clamp at 0.

Sun vector (azimuth 0 = the sun's own azimuth plane; elevation h):
    s = (cos h, 0, sin h)
Panel normal, plane tilted beta from the HORIZONTAL plane (beta=90 deg -> vertical
panel; beta=0 -> horizontal panel), rotated by azimuth psi about the vertical:
    n = (sin beta cos psi, sin beta sin psi, cos beta)
    s . n = cos h sin beta cos psi + sin h cos beta  =  a + b cos psi
    a = sin h cos beta      b = cos h sin beta

Run:  python3 docs/analysis/insolation_factors.py
"""

import math

R2D = 180.0 / math.pi
D2R = math.pi / 180.0

# ----------------------------------------------------------------------------
# Site / season assumptions (assumed; no latitude is stated anywhere in the repo)
# ----------------------------------------------------------------------------
PHI = 50.0          # assumed launch latitude, deg N   -> TODO(unverified)
DEC = -23.44        # winter-solstice solar declination, deg


def noon_elevation(phi=PHI, dec=DEC):
    """Solar elevation at local solar noon, deg.  h = 90 - |phi - dec|."""
    return 90.0 - abs(phi - dec)


def sun_elevation(hour_angle_deg, phi=PHI, dec=DEC):
    """sin h = sin phi sin dec + cos phi cos dec cos H  ->  h."""
    H = hour_angle_deg * D2R
    s = (math.sin(phi * D2R) * math.sin(dec * D2R)
         + math.cos(phi * D2R) * math.cos(dec * D2R) * math.cos(H))
    return math.asin(max(-1.0, min(1.0, s))) * R2D


def sunset_hour_angle(phi=PHI, dec=DEC):
    """Half day length in hour-angle degrees:  cos H0 = -tan phi tan dec."""
    x = -math.tan(phi * D2R) * math.tan(dec * D2R)
    return math.acos(max(-1.0, min(1.0, x))) * R2D


# ----------------------------------------------------------------------------
# (1) Baseline comparison at winter noon
# ----------------------------------------------------------------------------
def face_factor(h_deg):
    """cos(incidence) for a panel whose normal points straight at the sun."""
    return math.cos(h_deg * D2R)


def horizontal_factor(h_deg):
    """cos(incidence) for a horizontal panel (normal straight up) = sin h."""
    return math.sin(h_deg * D2R)


# ----------------------------------------------------------------------------
# (2) Rotation averages
# ----------------------------------------------------------------------------
def arm_average(beta_deg, h_deg):
    """Mean over a full 360 deg rotation (uniform psi) of max(0, a+b cos psi),
    for ONE panel of plane-tilt beta from horizontal, in sun of elevation h.

        a = sin h cos beta ;  b = cos h sin beta
        if a >= b :  mean = a
        else      :  mean = ( a*psi0 + sqrt(b^2 - a^2) ) / pi ,  psi0 = acos(-a/b)
    """
    h = h_deg * D2R
    bt = beta_deg * D2R
    a = math.sin(h) * math.cos(bt)
    b = math.cos(h) * math.sin(bt)
    if a >= b:
        return a
    psi0 = math.acos(max(-1.0, min(1.0, -a / b)))
    return (a * psi0 + math.sqrt(max(0.0, b * b - a * a))) / math.pi


def four_arm_total(beta_deg, h_deg, psi_deg):
    """Instantaneous sum of cos(incidence) over a 4-arm cross with arms at 90 deg
    azimuth spacing, as a function of the rotation angle psi (psi = 0 puts arm 1
    in the sun's azimuth plane)."""
    h = h_deg * D2R
    bt = beta_deg * D2R
    a = math.sin(h) * math.cos(bt)
    b = math.cos(h) * math.sin(bt)
    return sum(max(0.0, a + b * math.cos((psi_deg + 90.0 * k) * D2R))
               for k in range(4))


def four_arm_minmax(beta_deg, h_deg, n=3601):
    vals = [four_arm_total(beta_deg, h_deg, 90.0 * i / (n - 1)) for i in range(n)]
    return min(vals), max(vals)


def four_arm_average(beta_deg, h_deg):
    """Mean over rotation of the 4-arm total = 4 * single-arm mean (each arm has
    the same mean because psi is uniform)."""
    return 4.0 * arm_average(beta_deg, h_deg)


def day_average_arm(beta_deg, n=8001):
    """Whole-day mean of the single-arm rotation average.
    TIME WEIGHTING: equal time per unit hour angle H (the sun's hour angle
    advances at a constant 15 deg/h), integrated over the sunny half-day
    H = 0..H0.  i.e. mean_H[ <F>_1(beta, h(H)) ]."""
    H0 = sunset_hour_angle()
    tot = 0.0
    for i in range(n):
        H = H0 * i / (n - 1)
        tot += arm_average(beta_deg, max(0.0, sun_elevation(H)))
    return tot / n


def day_average_horizontal(n=8001):
    """Whole-day mean of sin h (a horizontal panel; rotation-independent)."""
    H0 = sunset_hour_angle()
    tot = 0.0
    for i in range(n):
        H = H0 * i / (n - 1)
        tot += horizontal_factor(max(0.0, sun_elevation(H)))
    return tot / n


def series_metric(beta_deg, h_deg, psi_deg):
    """SERIES-STRING metric.  The four wings are one series string (ADR-046 2.3):
    the string current is the weakest illuminated wing, the voltage is the sum of
    the illuminated wings.  With an ideal per-wing bypass diode the best string
    operating point is

        P / P_ideal = max_{j=1..4} ( j * cos_(j) ) / 4

    where cos_(j) is the j-th LARGEST of the four instantaneous cos(incidence)
    factors.  (No bypass -> the string is limited by the unlit wing -> 0.)"""
    h = h_deg * D2R
    bt = beta_deg * D2R
    a = math.sin(h) * math.cos(bt)
    b = math.cos(h) * math.sin(bt)
    factors = [max(0.0, a + b * math.cos((psi_deg + 90.0 * k) * D2R))
               for k in range(4)]
    fs = sorted(factors, reverse=True)
    return max((j + 1) * fs[j] for j in range(4)) / 4.0


def series_average(beta_deg, h_deg, n=181):
    return sum(series_metric(beta_deg, h_deg, 90.0 * i / (n - 1))
               for i in range(n)) / n


def series_day_average(beta_deg, n=181, m=91):
    H0 = sunset_hour_angle()
    tot = 0.0
    for i in range(n):
        H = H0 * i / (n - 1)
        tot += series_average(beta_deg, max(0.0, sun_elevation(H)), m)
    return tot / n



# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------
def main():
    h_noon = noon_elevation()
    print("=" * 78)
    print("SITE / SEASON")
    print("=" * 78)
    print(f"assumed latitude phi            = {PHI:.2f} deg N   [TODO(unverified)]")
    print(f"declination dec (winter solstice)= {DEC:.2f} deg")
    print(f"noon elevation  h = 90-|phi-dec| = 90 - |{PHI:.1f} - ({DEC:.2f})|"
          f" = {h_noon:.4f} deg")
    print(f"sunset hour angle H0 = acos(-tan phi tan dec) = {sunset_hour_angle():.4f} deg"
          f"  -> day length = {2*sunset_hour_angle()/15.0:.3f} h")

    print()
    print("=" * 78)
    print("(1) BASELINE AT WINTER NOON")
    print("=" * 78)
    fa = horizontal_factor(h_noon)
    fb = face_factor(h_noon)
    print(f"(a) horizontal panel   cos(inc) = sin h = {fa:.4f}")
    print(f"(b) vertical facing sun cos(inc) = cos h = {fb:.4f}")
    print(f"    ratio (a)/(b) = tan h = {fa/fb:.4f}   ;  (b)/(a) = {fb/fa:.4f}")
    beta_opt_noon = 90.0 - h_noon
    print(f"(c) optimal tilt at noon beta = 90 - h = {beta_opt_noon:.4f} deg from"
          f" horizontal  -> cos(inc) = {face_factor(0.0):.4f}")
    print(f"    optimal tilt at h=0 (sunrise/sunset) beta = 90.0000 deg from"
          f" horizontal  -> cos(inc) = {face_factor(0.0):.4f}")
    # one fixed tilt cannot serve both: beta=73.44 at h=0, azimuth aligned
    mis = math.cos((90.0 - beta_opt_noon - 0.0) * D2R)
    print(f"    noon-optimal tilt {beta_opt_noon:.2f} deg evaluated at h=0 (azimuth"
          f" aligned): cos(90-beta-h) = {mis:.4f}")

    print()
    print("=" * 78)
    print("(2) ROTATION AVERAGES  (uniform azimuth, 360 deg)")
    print("=" * 78)
    v_arm = arm_average(90.0, h_noon)
    print(f"single VERTICAL arm (beta=90), noon: <cos theta> = cos h / pi"
          f" = {fb:.4f}/pi = {v_arm:.5f}")
    v4 = four_arm_average(90.0, h_noon)
    print(f"  check 4-fold: 4 * {v_arm:.5f} = {v4:.5f}")
    print(f"  closed form for beta=90: total(psi) = (|cos psi| + |sin psi|) * cos h")
    lomin, lomax = four_arm_minmax(90.0, h_noon)
    print(f"  min (sun on one arm)   = 1.0000 * cos h = {lomin:.5f}")
    print(f"  max (sun at 45 deg)    = sqrt(2) * cos h = {lomax:.5f}"
          f"   [sqrt2*cos h = {math.sqrt(2)*fb:.5f}]")
    print(f"  mean                   = (4/pi) * cos h = {v4:.5f}"
          f"   [4/pi*cos h = {4/math.pi*fb:.5f}]")
    print(f"  as fraction of 4x nameplate: min={lomin/4:.4f} max={lomax/4:.4f}"
          f" mean={v4/4:.4f}")
    print(f"  <|cos psi|> over a full rotation = 2/pi = {2/math.pi:.4f}"
          f" ; <max(0,cos psi)> = 1/pi = {1/math.pi:.5f}")
    hz = horizontal_factor(h_noon)
    print(f"horizontal arm (beta=0), noon: cos(inc)=sin h = {hz:.4f}"
          f" (rotation-INDEPENDENT); 4-arm total = {4*hz:.4f}")
    print(f"  vertical mean total {v4:.4f}  /  horizontal total {4*hz:.4f}"
          f" = {v4/(4*hz):.4f}  (noon only)")
    print(f"day-mean single VERTICAL arm  = <cos h>/pi  = {day_average_arm(90.0):.5f}")
    print(f"day-mean single HORIZONTAL arm= <sin h>     = {day_average_horizontal():.5f}")
    print(f"  day ratio vertical/horizontal = {day_average_arm(90.0)/day_average_horizontal():.4f}")

    print()
    print("(2b) SERIES-STRING CONSEQUENCE (ADR-046 2.3 wires the 4 wings in SERIES)")
    print("     P/Pideal = max_j ( j * cos_(j) ) / 4 , ideal per-wing bypass fitted;")
    print("     with no bypass the string is limited by the unlit wing -> 0.")
    for b in (0.0, 90.0):
        print(f"  beta={b:5.1f}: series noon avg = {series_average(b, h_noon):.5f}"
              f" ; series day avg = {series_day_average(b):.5f}")
    print(f"  series example beta=90, noon: psi=0 deg (one blade dead-on sun) ->"
          f" {series_metric(90.0, h_noon, 0.0):.5f} ; psi=45 deg ->"
          f" {series_metric(90.0, h_noon, 45.0):.5f}")
    print(f"  series example beta=0 , noon: psi-independent ->"
          f" {series_metric(0.0, h_noon, 0.0):.5f}  (= sin h = {hz:.4f})")

    print()
    print("=" * 78)
    print("(3) TILT SWEEP  (4-arm cross, 90 deg spacing)")
    print("=" * 78)
    print(f"{'beta(deg)':>9} {'4-arm@noon':>12} {'4-arm day':>12}"
          f" {'series@noon':>12} {'series day':>11}")
    best_noon = (None, -1.0)
    best_day = (None, -1.0)
    best_sn = (None, -1.0)
    best_sd = (None, -1.0)
    sweep = list(range(0, 91, 5))
    for b in sweep:
        n4 = four_arm_average(b, h_noon)
        d4 = 4.0 * day_average_arm(b)
        sn = series_average(b, h_noon)
        sd = series_day_average(b)
        print(f"{b:>9} {n4:>12.5f} {d4:>12.5f} {sn:>12.5f} {sd:>11.5f}")
        if n4 > best_noon[1]:
            best_noon = (b, n4)
        if d4 > best_day[1]:
            best_day = (b, d4)
        if sn > best_sn[1]:
            best_sn = (b, sn)
        if sd > best_sd[1]:
            best_sd = (b, sd)
    # finer sweep near each optimum
    def fine(lo, hi, key):
        bb, bv = None, -1.0
        x = lo
        while x <= hi + 1e-9:
            v = key(x)
            if v > bv:
                bb, bv = x, v
            x += 0.5
        return bb, bv
    bn = fine(60, 90, lambda b: four_arm_average(b, h_noon))
    bd = fine(30, 90, lambda b: 4.0 * day_average_arm(b))
    print(f"noon-maximising beta (0.5 deg grid) = {bn[0]:.1f} deg -> {bn[1]:.5f}")
    print(f"day -maximising beta (0.5 deg grid) = {bd[0]:.1f} deg -> {bd[1]:.5f}")
    v_noon = four_arm_average(90.0, h_noon)
    v_day = 4.0 * day_average_arm(90.0)
    print(f"plain vertical beta=90: noon 4-arm = {v_noon:.5f} ; day 4-arm = {v_day:.5f}")
    print(f"  noon gain of optimum / vertical = {bn[1]/v_noon:.4f}"
          f"  (+{(bn[1]/v_noon-1)*100:.2f} %)")
    print(f"  day  gain of optimum / vertical = {bd[1]/v_day:.4f}"
          f"  (+{(bd[1]/v_day-1)*100:.2f} %)")
    sbn = fine(0, 90, lambda b: series_average(b, h_noon))
    sbd = fine(0, 90, lambda b: series_day_average(b))
    v_sn = series_average(90.0, h_noon)
    v_sd = series_day_average(90.0)
    print(f"series noon-max beta = {sbn[0]:.1f} deg -> {sbn[1]:.5f}"
          f"  (vs vertical {v_sn:.5f}, ratio {sbn[1]/v_sn:.4f})")
    print(f"series day -max beta = {sbd[0]:.1f} deg -> {sbd[1]:.5f}"
          f"  (vs vertical {v_sd:.5f}, ratio {sbd[1]/v_sd:.4f})")
    print(f"series horizontal beta=0: noon {series_average(0.0,h_noon):.5f}"
          f" ; day {series_day_average(0.0):.5f}")
    print(f"  -> series day horizontal/vertical ="
          f" {series_day_average(0.0)/v_sd:.4f}")

    print()
    print("=" * 78)
    print("(4) SHAPES")
    print("=" * 78)
    # (a) flat horizontal cross
    print(f"(a) flat horizontal cross beta=0: per-panel {hz:.4f} (rot-indep),"
          f" total {4*hz:.4f}; day total {4*day_average_horizontal():.5f}")
    # (b) four vertical blades
    print(f"(b) four vertical blades beta=90: per-panel mean {v_arm:.5f},"
          f" total {v4:.5f} (min {lomin:.5f} / max {lomax:.5f});"
          f" day total {v_day:.5f}")
    # (c) V / inverted-V : two half-panels at 75 and 40 deg per arm
    b1, b2 = 75.0, 40.0
    noon_v = 0.5 * arm_average(b1, h_noon) + 0.5 * arm_average(b2, h_noon)
    day_v = 0.5 * day_average_arm(b1) + 0.5 * day_average_arm(b2)
    best_noon_b = four_arm_average(bn[0], h_noon) / 4.0
    best_day_b = day_average_arm(bd[0])
    print(f"(c) V arm = 0.5*F(75)+0.5*F(40):  noon {noon_v:.5f}  day {day_v:.5f}"
          f"   (noon per-arm means: F75={arm_average(b1,h_noon):.5f},"
          f" F40={arm_average(b2,h_noon):.5f})")
    print(f"    single full-area panel at noon-opt {bn[0]:.1f} deg: noon"
          f" {best_noon_b:.5f}  day {best_day_b:.5f}")
    print(f"    V / single-optimum : noon {noon_v/best_noon_b:.4f}"
          f"  day {day_v/best_day_b:.4f}")
    print(f"    V / plain vertical : noon {noon_v/v_arm:.4f}"
          f"  day {day_v/day_average_arm(90.0):.4f}")
    # (d) cone / funnel beta = 73.44 (17 deg from vertical)
    cone = beta_opt_noon
    c_noon = four_arm_average(cone, h_noon)
    c_day = 4.0 * day_average_arm(cone)
    print(f"(d) cone/funnel beta={cone:.2f} deg (17.0 deg from vertical):"
          f" noon total {c_noon:.5f}  day total {c_day:.5f}")
    print(f"    cone/plain-vertical: noon {c_noon/v_noon:.4f}"
          f" (+{(c_noon/v_noon-1)*100:.2f} %)  day {c_day/v_day:.4f}"
          f" (+{(c_day/v_day-1)*100:.2f} %)")
    print(f"    noon facing factor of the 17-deg-normal panel = {face_factor(0.0):.4f}")
    # (e) half shape
    print(f"(e) half wing (half cells, 1 panel/arm): area 0.5x -> energy 0.5x of the"
          f" full shape at the same tilt; per-unit-area factor unchanged")

    print()
    print("=" * 78)
    print("(5) GEOMETRY SIZING")
    print("=" * 78)
    for name, w, l in (("small", 52.07, 19.65), ("large", 78.55, 38.90)):
        gap = 6.0          # inter-cell gap, ADR-046 3.3 (pitch 58 = 52 + 6)
        tab = 8.0          # tab protrusion, ADR-046 3.2
        m_end = 3.8        # end margin per end, chosen to reproduce ADR-046's 176 mm
        side = 2.675       # side margin per side
        body_len = 3 * w + 2 * gap + 2 * m_end
        width = l + 2 * side
        print(f"{name} cell {w} x {l} mm: 3 in a row along the wing length ->"
              f" body {body_len:.1f} x {width:.1f} mm, tab {tab:.0f} x 9.0 mm,"
              f" total {body_len+tab:.1f} mm; cell area/wing"
              f" {3*w*l/100:.2f} cm2")
        print(f"    4-arm diameter = 2 x {body_len+tab:.1f} ="
              f" {2*(body_len+tab):.1f} mm")
        # cross-check the ADR-046 packing (52.07 -> 176x25)
    print("large-cell ALTERNATE packing (38.90 mm dimension along the wing):"
          f" body {3*38.90 + 2*6.0 + 2*3.8:.1f} x"
          f" {78.55 + 2*2.675:.1f} mm, tab 8 x 9 -> total"
          f" {3*38.90 + 2*6.0 + 2*3.8 + 8:.1f} mm")
    print("ADR-046 packing cross-check: 3*52.07 + 2*6 = 168.21 mm cell field;"
          " ADR body 176 mm -> 3.8 mm end margins -> matches ADR-046 176 x 25 mm")
    print("array area: small 12 * 52.07 * 19.65 mm2 =",
          f"{12*52.07*19.65/100:.2f} cm2 ; large 12 * 78.55 * 38.90 mm2 =",
          f"{12*78.55*38.90/100:.2f} cm2")


if __name__ == "__main__":
    main()
