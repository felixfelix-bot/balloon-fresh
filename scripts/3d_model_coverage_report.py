#!/usr/bin/env python3
"""Emit `docs/3d-model-coverage-hub.md` - the HONEST per-footprint 3D coverage statement.

WHY THIS EXISTS (2026-10-08, render-fidelity revision)
-----------------------------------------------------
A render of `hub_board_v9.kicad_pcb` was produced and it was MISLEADING twice:

1. First every model reference pointed at `${KICAD9_3DMODEL_DIR}/...step` with
   the library uninstalled: **0 of 32 references resolved** and a vision model
   "saw" components that were only silkscreen text.
2. Then the models were made repo-local - but authored in **raw millimetres**.
   KiCad reads a VRML coordinate as **2.54 mm per unit**, so every model
   rendered **2.54x too large**: the solar cell rendered as a 199.5 x 98.8 mm
   grey slab and the supercap placeholder as a 25.7 x 25.7 x 17.8 mm thick can.
   The operator read that render as "grey slabs all over the place ... some grey
   things are really thick" - a CORRECT reading of a wrong render.

The cure is this report: for EVERY footprint on the board, one row stating
whether the 3D model is `library` / `custom-faceted` / `custom-box` / `missing`,
its Z height, and where that height came from.  A render is only evidence if you
can say, for every footprint, what was actually drawn and where its dimensions
came from.  This report is regenerated from the committed board, so it cannot go
stale silently.

    python3 scripts/3d_model_coverage_report.py            # write the doc
    python3 scripts/3d_model_coverage_report.py --check    # exit 1 if it is stale
"""
from __future__ import annotations

import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BOARD = os.path.join(REPO, "tracker", "hardware", "hub_board_v9.kicad_pcb")
INDEX = os.path.join(REPO, "tracker", "hardware", "footprints", "3dmodels", "MODEL-INDEX.json")
DOC = os.path.join(REPO, "docs", "3d-model-coverage-hub.md")
LIB_ROOT = "/usr/share/kicad/3dmodels"

# Z heights of the KiCad library models, MEASURED from the library .step files
# themselves (CARTESIAN_POINT Z extent above the seating plane z=0, body only;
# THT leads extend below z=0 and are excluded).  Reproduce with
# scripts/3d_model_coverage_report.py --remeasure.
LIB_Z_MEASURED = {
    "R_0402_1005Metric.step": 0.35,
    "C_0402_1005Metric.step": 0.50,
    "C_1206_3216Metric.step": 1.60,
    "CP_Radial_D10.0mm_P5.00mm.step": 10.0,
    "D_SMA.step": 2.22,
    "D_SOD-123.step": 1.26,
    "D_SOD-323.step": 1.11,
    "LGA-8_3x5mm_P1.25mm.step": 0.80,
    "SOT-23-5.step": 1.55,
}


def s_expr_blocks(text, keyword):
    out, i, tok = [], 0, "(" + keyword
    while True:
        s = text.find(tok, i)
        if s < 0:
            break
        nxt = text[s + len(tok):s + len(tok) + 1]
        if nxt and (nxt.isalnum() or nxt == "_"):
            i = s + 1
            continue
        depth, j = 0, s
        while j < len(text):
            c = text[j]
            if c == '"':
                j += 1
                while j < len(text) and text[j] != '"':
                    if text[j] == "\\":
                        j += 1
                    j += 1
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(text[s:j + 1])
        i = j + 1
    return out


def prop(block, name):
    m = re.search(r'\(property "%s" "([^"]*)"' % re.escape(name), block)
    return m.group(1) if m else ""


def parse(board_path):
    text = open(board_path, encoding="utf-8", errors="replace").read()
    rows = []
    for blk in s_expr_blocks(text, "footprint "):
        lib = re.match(r'\(footprint "([^"]+)"', blk).group(1)
        ref = prop(blk, "Reference")
        val = prop(blk, "Value")
        layer = re.search(r'\(footprint "[^"]+"\s*\n?\s*\(layer "([^"]+)"\)', blk)
        ly = layer.group(1) if layer else "?"
        dnps = re.findall(r"\(dnp (yes|no)\)", blk)
        dnp = "yes" if (dnps and dnps[0] == "yes") else "no"
        models = re.findall(r'\(model "([^"]+)"', blk)
        rows.append(dict(ref=ref, value=val, lib=lib, layer=ly, dnp=dnp, models=models))
    return rows


def measure_step_z(path):
    """Measure a library .step body height (Z extent above the seating plane z=0)."""
    try:
        d = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return None
    pts = re.findall(r"CARTESIAN_POINT\([^)]*\(([^)]*)\)\)", d)
    zs = []
    for p in pts:
        parts = [x.strip() for x in p.split(",")]
        if len(parts) == 3:
            try:
                z = float(parts[2])
            except ValueError:
                continue
            zs.append(z)
    if not zs:
        return None
    body = [z for z in zs if z >= 0.0]
    if body:
        return round(max(body) - min(body), 2)
    return None


def classify(model_ref):
    """(state, basename) where state is library / custom-faceted / custom-box / missing."""
    if not model_ref:
        return "missing", ""
    base = os.path.basename(model_ref)
    if "${KICAD" in model_ref:
        return "library", base
    # repo-local custom model
    return None, base  # refined by caller from MODEL-INDEX kind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--remeasure", action="store_true",
                    help="re-measure library .step heights instead of using the table")
    a = ap.parse_args()

    rows = parse(BOARD)
    idx = json.load(open(INDEX, encoding="utf-8"))
    custom = idx["custom_models"]
    lib_map = idx.get("library_models", {})

    # custom model lookup by file basename
    by_file = {m["file"]: (name, m) for name, m in custom.items()}

    counts = {"library": 0, "custom-faceted": 0, "custom-box": 0, "missing": 0}
    table = []
    unsourced = []
    thick_flags = []
    for r in sorted(rows, key=lambda r: r["ref"]):
        state, src, files, z_mm, origin = "missing", "-", [], "", ""
        if r["models"]:
            f = r["models"][0]
            files = [os.path.basename(x) for x in r["models"]]
            base = os.path.basename(f)
            if "${KICAD" in f:
                state = "library"
                # find the Z from the measured table or re-measure
                if a.remeasure:
                    p = os.path.join(LIB_ROOT, f.split(".3dshapes/")[-1]) if ".3dshapes/" in f else None
                    z_mm = measure_step_z(p) if p and os.path.exists(p) else "?"
                    origin = "measured from the library .step (Z extent of CARTESIAN_POINTs, body above z=0)"
                else:
                    z_mm = LIB_Z_MEASURED.get(base, "?")
                    origin = ("Z measured from the library .step file "
                              f"({f.split('${')[-1]}) CARTESIAN_POINT Z extent")
                if base == "CP_Radial_D10.0mm_P5.00mm.step":
                    origin += ("  **PART MISMATCH FLAG**: the library model is a "
                               "10.0 mm-diameter radial electrolytic can, body 10.0 mm "
                               "tall; the actual part is '3.3F 2.7V (AVX SCC)', a "
                               "stacked-coin supercapacitor whose body dimensions are "
                               "NOT stated in any in-repo record - "
                               "TODO(unverified).  The footprint name pins the LAND, "
                               "not the can; the rendered can is a PLACEHOLDER.")
                    thick_flags.append((r["ref"], 10.0, "library .step (radial can placeholder; actual AVX SCC body TODO(unverified))"))
            elif base in by_file:
                name, meta = by_file[base]
                state = "custom-faceted" if meta.get("kind") == "cell" else "custom-box"
                z_mm = meta["height_mm"]
                origin = meta["source"]
                if meta.get("todo_unverified"):
                    origin += " **TODO(unverified)**: " + "; ".join(meta["todo_unverified"])
                    unsourced.append((name, meta["todo_unverified"]))
            else:
                state = "custom-box"
                origin = "repo-local model not in MODEL-INDEX?"
        counts[state] = counts.get(state, 0) + 1
        table.append((r, state, src, files, z_mm, origin))

    n_fp = len(rows)
    n_modeled = n_fp - counts["missing"]
    out = []
    out.append("# 3D model coverage - `hub_board_v9.kicad_pcb` (v9 hub)  \n")
    out.append("> GENERATED BY `scripts/3d_model_coverage_report.py` - do not hand-edit.")
    out.append("> Regenerate with `python3 scripts/3d_model_coverage_report.py`;")
    out.append("> `--check` exits 1 if this file is stale; `--remeasure` re-measures")
    out.append("> library .step heights from `/usr/share/kicad/3dmodels/`.\n")

    out.append("## 1. Why this document exists\n")
    out.append("A render of this board was **misleading twice**, and each time the operator")
    out.append("(or a vision model) correctly read a defect that was in the render, not the")
    out.append("reader:\n")
    out.append("1. **Empty render.** Every model reference pointed at `${KICAD9_3DMODEL_DIR}/…`")
    out.append("   with the library uninstalled: 0 of 32 references resolved, and a vision")
    out.append("   model reported components that were only silkscreen text.")
    out.append("2. **2.54x oversize models.** The repo-local models that replaced them were")
    out.append("   authored in raw millimetres, but KiCad reads a VRML coordinate as")
    out.append("   **2.54 mm per unit** - so the 78.55 x 38.90 x 0.21 mm solar cell rendered")
    out.append("   as a 199.5 x 98.8 x 0.53 mm grey slab and the supercap placeholder as a")
    out.append("   25.7 x 25.7 x 17.8 mm thick can.  The operator's \"grey slabs all over the")
    out.append("   place\" and \"some grey things are really thick\" was a CORRECT reading.\n")
    out.append("The cure: this table states, for every footprint, what is drawn and where")
    out.append("every dimension came from.  **Never read a render without it.**\n")

    out.append("## 2. The cell face fix (ADR-055 D6)\n")
    out.append("`PVA1`/`PVA2` are DNP illustrative array cells.  They were first emitted on")
    out.append("`B.Cu`; **ADR-055 D6 states \"The hub-array cells are mounted on the UPPER")
    out.append("face of the board\"**, and with the hub plane horizontal (D1) the upper face")
    out.append("is the sun-facing side (the array is \"effectively single-face\", §D2).")
    out.append("The cells are now on `F.Cu` (operator-approved 2026-10-08).  Their model is")
    out.append("the **two-material IndexedFaceSet cell** ported from the wing generator - a")
    out.append("dark-blue silicon face (diffuseColor 0.09 0.10 0.42) over a light-grey frame")
    out.append("(diffuseColor 0.55 0.56 0.60) - in correct VRML units (mm / 2.54).\n")

    out.append("## 3. Render environment\n")
    out.append("**The render now REQUIRES** `export KICAD9_3DMODEL_DIR=/usr/share/kicad/3dmodels`")
    out.append("(the `kicad-packages3d 9.0.7-1` package, 4.6 GB, IS installed on this host).")
    out.append("Without it the 20 library-modelled footprints below silently vanish and the")
    out.append("render regresses to the empty-board confabulation.\n")

    out.append("## 4. Coverage table\n")
    out.append("| reference | value | face | 3D model | model file | Z mm | dimension source |")
    out.append("|---|---|---|---|---|---|---|")
    for r, state, src, files, z_mm, origin in table:
        dnptag = " **(DNP)**" if r["dnp"] == "yes" else ""
        f = ", ".join(files) if files else "-"
        z = z_mm if z_mm != "" else "-"
        out.append("| `%s`%s | %s | %s | **%s** | %s | %s | %s |" %
                   (r["ref"], dnptag, r["value"].replace("|", "/"), r["layer"],
                    state, f, z, origin))
    out.append("")

    out.append("## 5. Coverage counts\n")
    out.append("| state | footprints |")
    out.append("|---|---|")
    for k in ("library", "custom-faceted", "custom-box", "missing"):
        out.append("| `%s` | %d |" % (k, counts.get(k, 0)))
    out.append("| **total** | **%d** |" % n_fp)
    out.append("")
    out.append("Of %d footprints, **%d carry a resolving 3D model** and **%d do not**.\n" %
               (n_fp, n_modeled, counts["missing"]))

    out.append("## 6. Thick-part audit (the \"really thick grey things\")\n")
    out.append("Every model's Z, with its source.  Anything implausible is flagged here,")
    out.append("not hidden in the render:\n")
    out.append("| ref | Z mm | source / disposition |")
    out.append("|---|---|---|")
    for r, state, src, files, z_mm, origin in table:
        if z_mm not in ("", "-", "?") and float(z_mm) >= 2.0:
            out.append("| `%s` | %s | %s |" % (r["ref"], z_mm, origin))
    out.append("")
    out.append("**Supercap disposition (C_CAP1/C_CAP2):** the part is '3.3F 2.7V (AVX SCC)'")
    out.append("per the netlist; no in-repo record states its body dimensions (the only")
    out.append("in-repo supercap figure, Ø8 x 7 mm in docs/PAYLOAD-WEIGHT-ESTIMATES.md:65,")
    out.append("is for a DIFFERENT part, a 1F 5.5V gold cap).  The library")
    out.append("CP_Radial_D10.0mm model is therefore a **placeholder can with a visible")
    out.append("mismatch flag**, not a verified body: TODO(unverified).  The AVX SCC series")
    out.append("body must be measured from the physical part or its datasheet before fab.\n")

    out.append("## 7. Unsourced dimensions (`TODO(unverified)`)\n")
    out.append("These dimensions are **display values only** - they are NOT claims, and every")
    out.append("one is flagged as `TODO(unverified)` in the model header itself.\n")
    out.append("| model | TODO(unverified) |")
    out.append("|---|---|")
    for name, todos in unsourced:
        out.append("| `%s` | %s |" % (name, "; ".join(todos)))
    out.append("")

    out.append("## 8. Reproduce\n")
    out.append("```sh")
    out.append("python3 scripts/gen_3d_models.py            # regenerate the committed custom models")
    out.append("python3 scripts/gen_3d_models.py --check    # fail if any model drifts")
    out.append("/usr/bin/python3.14 tracker/hardware/build_hub_board_v9.py --publish   # rebuild the board")
    out.append("python3 scripts/3d_model_coverage_report.py  # regenerate this document")
    out.append("export KICAD9_3DMODEL_DIR=/usr/share/kicad/3dmodels   # REQUIRED for the render")
    out.append("kicad-cli pcb render --output out.png --side top --quality high \\")
    out.append("    --width 1800 --height 1400 tracker/hardware/hub_board_v9.kicad_pcb")
    out.append("```")
    out.append("")
    out.append("> Standard parts use the REAL KiCad library (`${KICAD9_3DMODEL_DIR}`); custom")
    out.append("> parts the library will never carry are committed under")
    out.append("> `tracker/hardware/footprints/3dmodels/` in correct VRML units (mm / 2.54).\n")
    text = "\n".join(out) + "\n"

    if a.check:
        old = open(DOC, encoding="utf-8").read() if os.path.exists(DOC) else None
        if old != text:
            print("STALE: %s differs from a fresh generation" % os.path.relpath(DOC, REPO))
            return 1
        print("coverage report: up to date")
        return 0
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s  (library %d / custom-faceted %d / custom-box %d / missing %d of %d)" %
          (os.path.relpath(DOC, REPO), counts["library"], counts["custom-faceted"],
           counts["custom-box"], counts["missing"], n_fp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())