#!/usr/bin/env python3
"""
ground_station_dish_model.py — computed tables for the dish mechanical study.

Companion to docs/analysis/ground-station-dish.md and
hardware/ground-station/dish/dish.scad.

Every number in the analysis doc that is marked "COMPUTED" is this script's
own printed output.  Run:

    python3 docs/analysis/ground_station_dish_model.py

Nothing here is a datasheet figure.  Estimates show the formula and assumed
inputs inline.  Unsourced assumptions are flagged TODO(unverified).
"""
import math, json, textwrap, sys

RHO_AIR = 1.225  # kg/m^3, sea-level, 15 C (ISA) — estimate, not measured here
G = 9.80665

# ---------------------------------------------------------------------------
# 1. Parabolic geometry
# ---------------------------------------------------------------------------
def geom(d_mm, fod):
    D = d_mm / 1000.0
    f = fod * D
    sag = D**2 / (16 * f)
    # feed sits at height f above the vertex; rim is at height sag.
    # half-angle from focus to rim:
    half = math.atan((D/2) / (f - sag))
    full = 2 * half
    return dict(D_mm=d_mm, f_over_D=fod, f_mm=f*1000, sagitta_mm=sag*1000,
                half_angle_deg=math.degrees(half),
                illumination_angle_deg=math.degrees(full))

def table1():
    rows = []
    for D in [600, 900, 1200, 1500]:
        for fod in [0.35, 0.40, 0.45]:
            rows.append(geom(D, fod))
    print("=== TABLE 1: parabolic geometry ===")
    print(f"{'D[mm]':>6} {'f/D':>5} {'f[mm]':>7} {'sag[mm]':>8} {'half[deg]':>9} {'illum[deg]':>10}")
    for r in rows:
        print(f"{r['D_mm']:6d} {r['f_over_D']:5.2f} {r['f_mm']:7.1f} "
              f"{r['sagitta_mm']:8.1f} {r['half_angle_deg']:9.2f} "
              f"{r['illumination_angle_deg']:10.2f}")
    return rows

# ---------------------------------------------------------------------------
# 2. Surface-accuracy budget
# ---------------------------------------------------------------------------
def surface_budget():
    c = 299792458.0
    freqs = {"433 MHz": 433e6, "2.4 GHz": 2.4e9}
    print("\n=== TABLE 2: surface RMS budget (lambda/20 and lambda/16) ===")
    print(f"{'band':>10} {'freq':>10} {'lambda[mm]':>11} {'lam/20[mm]':>11} {'lam/16[mm]':>11}")
    out = {}
    for name, fr in freqs.items():
        lam = c / fr * 1000
        out[name] = dict(freq=fr, lam_mm=lam, lam20=lam/20, lam16=lam/16)
        print(f"{name:>10} {fr/1e6:>7.1f}MHz {lam:11.2f} {lam/20:11.2f} {lam/16:11.2f}")
    # efficiency loss from RMS error: Ruze formula  eta = exp[-(4*pi*sigma/lambda)^2]
    print("\n=== Ruze efficiency vs RMS error at 2.4 GHz (lambda=125 mm) ===")
    lam = c / 2.4e9 * 1000
    print(f"{'sigma[mm]':>10} {'4pi*s/lam':>10} {'eta_Ruze':>9} {'loss[dB]':>9}")
    for sigma in [1, 2, 3, 6.25, 8, 10, 12.5, 20]:
        x = 4*math.pi*sigma/lam
        eta = math.exp(-x**2)
        print(f"{sigma:10.2f} {x:10.3f} {eta:9.3f} {10*math.log10(eta):9.2f}")
    return out

# ---------------------------------------------------------------------------
# 3. Wind drag and elevation torque
# ---------------------------------------------------------------------------
def wind(D_m, v_ms, Cd):
    A = math.pi * D_m**2 / 4
    F = 0.5 * RHO_AIR * v_ms**2 * A * Cd
    return F, A

def table_wind():
    D = 1.2
    print("\n=== TABLE 6: wind drag on a 1.2 m dish (A = pi*D^2/4) ===")
    A = math.pi * D**2 / 4
    print(f"Aperture area A = {A:.4f} m^2")
    print(f"{'v[m/s]':>8} {'v[km/h]':>9} {'Cd':>5} {'F[N]':>8} {'F[kgf]':>8}")
    rows = []
    for v in [10, 15, 20, 25]:
        for Cd in [1.4, 0.5]:
            F, _ = wind(D, v, Cd)
            rows.append(dict(v=v, Cd=Cd, F_N=F, F_kgf=F/G))
            print(f"{v:8d} {v*3.6:9.1f} {Cd:5.1f} {F:8.1f} {F/G:8.2f}")
    # elevation torque: lever arm = D/2 (worst case, axis at the rim / back edge)
    # and lever = D/4 (axis at dish centre / balanced)
    print("\n=== TABLE 7: elevation torque (lever arm from axis to dish Cp) ===")
    print("Assumptions: elevation axis behind the dish vertex.")
    print("  lever_A = D/2 = 0.60 m (axis at rim plane, worst case)")
    print("  lever_B = D/4 = 0.30 m (axis through dish centre of pressure, balanced)")
    print(f"{'v[m/s]':>8} {'Cd':>5} {'F[N]':>8} {'T_A[Nm]':>9} {'T_B[Nm]':>9}")
    for r in rows:
        T_A = r['F_N'] * 0.60
        T_B = r['F_N'] * 0.30
        print(f"{r['v']:8d} {r['Cd']:5.1f} {r['F_N']:8.1f} {T_A:9.1f} {T_B:9.1f}")
    return rows

# ---------------------------------------------------------------------------
# 4. 3D-print feasibility estimates
# ---------------------------------------------------------------------------
def print_feasibility():
    print("\n=== PRINT FEASIBILITY (estimates — formula shown, assumptions flagged) ===")
    # Shell surface area of a paraboloid: S = (pi*D^2/8) * [sqrt(1+(D/4f)^2) + 4f/D * ln(D/4f + sqrt(1+(D/4f)^2))]
    # For f/D=0.4: D/4f = 1/(4*0.4) = 0.625
    D = 1.2; fod = 0.4; f = fod*D
    k = D/(4*f)
    s = (math.pi*D**2/8) * (math.sqrt(1+k**2) + (1/k)*math.log(k + math.sqrt(1+k**2)))
    print(f"Paraboloid surface area (D=1.2m, f/D=0.4): {s:.4f} m^2")
    # shell volume at 2 mm wall
    vol_shell = s * 0.002  # m^3
    mass_shell = vol_shell * 1240  # kg, PLA density 1.24 g/cm3 = 1240 kg/m3
    print(f"  Shell volume @2mm wall: {vol_shell*1e6:.0f} cm^3 = {vol_shell*1e3:.3f} L")
    print(f"  Shell mass @PLA 1.24 g/cm^3: {mass_shell*1000:.0f} g = {mass_shell:.2f} kg")
    # print time at 15 mm^3/s
    t_shell = vol_shell*1e9 / 15.0  # mm^3 / (mm^3/s) = s
    print(f"  Print time @15 mm^3/s: {t_shell/3600:.1f} h  (ESTIMATE, TODO unverified throughput)")
    # ribs only: 12 ribs, each ~ D/2 long, cross-section rib_w x rib_h
    rib_len = D/2; rib_w = 0.012; rib_h = 0.025; nribs = 12
    vol_rib = nribs * rib_len * rib_w * rib_h
    # rings: outer ring circumference pi*D, cross-section 12x8mm; hub ring ~ pi*0.07 x 12x25
    vol_ring = math.pi*D * (rib_w*0.008) + math.pi*0.07 * (rib_w*rib_h)
    vol_ribs = vol_rib + vol_ring
    mass_ribs = vol_ribs * 1240
    t_ribs = vol_ribs*1e9 / 15.0
    print(f"  Ribs-only volume: {vol_ribs*1e6:.0f} cm^3")
    print(f"  Ribs-only mass: {mass_ribs*1000:.0f} g = {mass_ribs:.2f} kg")
    print(f"  Ribs-only print time @15 mm^3/s: {t_ribs/3600:.1f} h  (ESTIMATE)")
    # petal count for common build volumes
    print("\n  Petal count for 1.2 m dish at common build volumes:")
    # chord at rim for one petal = 2*(D/2)*sin(pi/segments) must fit < build_X
    for bx, by, bz, label in [(220,220,250,"220^3"), (350,350,350,"350^3")]:
        # the radial length of a petal is D/2 = 600mm; must fit in build diagonal
        # but more practically the petal's bounding box: length ~ D/2 along radial,
        # width ~ chord at rim.  For a flat-printed petal lying on the bed:
        # radial length 600 mm >> 350, so even 350 mm bed needs 2 radial segments.
        # We estimate petals = ceil(D/2 / max_bed_dim) * segments
        radial_segments = math.ceil(600 / max(bx, by))
        total = radial_segments * 12
        print(f"    {label}: radial splits={radial_segments}, total pieces={total}")
    print("  NOTE: each joint is a surface discontinuity costing efficiency (see doc §5).")

# ---------------------------------------------------------------------------
# 5. STL triangle counts and bounding boxes
# ---------------------------------------------------------------------------
def stl_info(path):
    """Return (triangle_count, bbox (xmin,ymin,zmin,xmax,ymax,zmax)) from an ASCII
    or binary STL.  Minimal parser — no external deps."""
    import struct, os
    size = os.path.getsize(path)
    with open(path, 'rb') as fh:
        header = fh.read(80)
        # try binary: 80-byte header + 4-byte uint32 count
        fh.seek(80)
        try:
            n_tri = struct.unpack('<I', fh.read(4))[0]
        except:
            return None
        expected = 84 + n_tri * 50
        if expected == size:
            # binary STL
            tris = []
            mn = [float('inf')]*3; mx = [float('-inf')]*3
            for _ in range(n_tri):
                fh.read(12)  # normal
                for i in range(3):
                    v = struct.unpack('<fff', fh.read(12))
                    tris.append(v)
                    for j in range(3):
                        mn[j] = min(mn[j], v[j]); mx[j] = max(mx[j], v[j])
                fh.read(2)  # attr
            return n_tri, (mn[0],mn[1],mn[2],mx[0],mx[1],mx[2])
        else:
            # ASCII STL
            fh.seek(0)
            text = fh.read().decode('utf-8', errors='replace')
            n_tri = text.count('facet normal')
            import re
            verts = re.findall(r'vertex\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)', text)
            xs=[float(v[0]) for v in verts]; ys=[float(v[1]) for v in verts]; zs=[float(v[2]) for v in verts]
            return n_tri, (min(xs),min(ys),min(zs),max(xs),max(ys),max(zs))

def table_stl():
    print("\n=== STL EXPORT SUMMARY ===")
    import os, glob
    d = os.path.join(os.path.dirname(__file__), '..', '..', 'hardware', 'ground-station', 'dish', 'export')
    d = os.path.abspath(d)
    if not os.path.isdir(d):
        print(f"  (export dir not found: {d})")
        return []
    out = []
    for f in sorted(glob.glob(os.path.join(d, '*.stl'))):
        info = stl_info(f)
        name = os.path.basename(f)
        if info is None:
            print(f"  {name}: could not parse")
            out.append(dict(path=f, triangles=None, bbox=None))
        else:
            n, b = info
            print(f"  {name}: {n} triangles, bbox=({b[0]:.1f},{b[1]:.1f},{b[2]:.1f})..({b[3]:.1f},{b[4]:.1f},{b[5]:.1f}) mm")
            out.append(dict(path=f, triangles=n, bbox=b))
    return out

# ---------------------------------------------------------------------------
if __name__ == '__main__':
    t1 = table1()
    t2 = surface_budget()
    t6 = table_wind()
    print_feasibility()
    stls = table_stl()
    print("\n=== DONE ===")