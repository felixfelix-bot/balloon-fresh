#!/usr/bin/env python3
"""Deterministic multi-angle KiCad board renderer.

Renders a fixed, documented set of comparable views from any .kicad_pcb via
`kicad-cli pcb render`, then composites them into a single labelled contact
sheet with ImageMagick `montage`.

WHY: single top/iso renders are not enough to reason about a physical board.
A human needs (a) several fixed, comparable angles and (b) one contact sheet
to compare them at a glance. The true side elevation in particular is what
exposes a part that is too tall.

ANGLE SET (fixed, comparable):
    top       --side top                    (orthographic top-down)
    bottom    --side bottom                 (orthographic bottom-up)
    iso_ne    --side top  --rotate 30,0,45   (isometric, NE corner)
    iso_nw    --side top  --rotate 30,0,315  (isometric, NW corner)
    iso_se    --side top  --rotate -30,0,45  (isometric, SE corner, from below)
    iso_sw    --side top  --rotate -30,0,315 (isometric, SW corner, from below)
    side_e    --side right                  (TRUE side elevation: shows height)
    side_n    --side front                  (true side elevation, other axis)

ENV VAR / FAIL-CLOSED BEHAVIOUR (the point of this script):
    Footprints that reference library 3D models via
    `${KICAD9_3DMODEL_DIR}/...` render SILENTLY WITHOUT BODIES if that
    variable is unset — no error, just a hollow-looking board. A render with
    vanished models is worse than no render because it looks authoritative.
    Therefore this script:
      1. Exports KICAD9_3DMODEL_DIR itself (default /usr/share/kicad/3dmodels,
         override with --models-dir or the incoming environment).
      2. FAILS CLOSED (exit code 2) if the resolved directory does not exist,
         printing exactly what it checked. It never renders a hollow board.

CONTACT SHEET:
    Built with ImageMagick `montage` (labels via `-label`). If `montage`
    (or `convert`, which some montage builds shell out to) is missing from
    PATH, the script FAILS LOUDLY (exit code 3) — it never silently skips
    the contact sheet.

DETERMINISM:
    Re-running produces the SAME file set with the SAME names. Pixel content
    may vary slightly between runs (renderer non-determinism in ray tracing);
    the MANIFEST (sha256 + byte size per file, written to manifest.json and
    printed to stdout) is the verifiable artifact, not the pixels.

READ-ONLY: this script never modifies board, schematic, netlist, footprint,
or 3D model data. It only writes into the output directory.

Usage:
    python3 scripts/render_board_views.py BOARD.kicad_pcb [OUTDIR]
        [--models-dir DIR] [--width N] [--height N] [--quality Q]
        [--no-contact-sheet]

Exit codes: 0 ok; 1 render failure; 2 models dir missing; 3 montage missing.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

DEFAULT_MODELS_DIR = "/usr/share/kicad/3dmodels"
DEFAULT_WIDTH = 1800
DEFAULT_HEIGHT = 1400
DEFAULT_QUALITY = "high"

# The fixed angle set. Each entry: (view_name, {"side": ..., "rotate": ...}).
# `rotate` omitted for pure elevations. Values are the REAL kicad-cli pcb
# render options --side / --rotate "X,Y,Z" (verified against kicad-cli 9.0.8
# `pcb render --help`).
ANGLE_SET = [
    ("top",     {"side": "top"}),
    ("bottom",  {"side": "bottom"}),
    ("iso_ne",  {"side": "top", "rotate": "30,0,45"}),
    ("iso_nw",  {"side": "top", "rotate": "30,0,315"}),
    ("iso_se",  {"side": "top", "rotate": "-30,0,45"}),
    ("iso_sw",  {"side": "top", "rotate": "-30,0,315"}),
    ("side_e",  {"side": "right"}),
    ("side_n",  {"side": "front"}),
]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_models_dir(cli_value: str) -> str:
    """Resolve KICAD9_3DMODEL_DIR, FAIL CLOSED if the resolved dir is missing.

    Precedence: --models-dir > existing env var > default. Whichever wins is
    FINAL: if it does not exist, exit 2 — never silently fall back, because a
    fallback could mask a broken explicit override with a hollow render.
    Prints exactly what was checked so the failure is self-explanatory.
    """
    if cli_value:
        source, path = "cmd line", os.path.abspath(cli_value)
    elif os.environ.get("KICAD9_3DMODEL_DIR"):
        source, path = "environment", os.path.abspath(os.environ["KICAD9_3DMODEL_DIR"])
    else:
        source, path = "default", DEFAULT_MODELS_DIR

    if os.path.isdir(path):
        print(f"[models] using {source} KICAD9_3DMODEL_DIR={path}", flush=True)
        return path

    print("FATAL: KiCad 3D model directory missing — refusing to render.", file=sys.stderr, flush=True)
    print("  A render without the model library shows substrate/copper only:", file=sys.stderr, flush=True)
    print("  component bodies silently vanish. Fail-closed by design.", file=sys.stderr, flush=True)
    print(f"  checked ({source}): {path} -> isdir={os.path.isdir(path)}", file=sys.stderr, flush=True)
    sys.exit(2)


def build_cmd(board: str, out_png: str, view: dict, width: int, height: int, quality: str) -> list:
    cmd = [
        "kicad-cli", "pcb", "render",
        "--output", out_png,
        "--width", str(width),
        "--height", str(height),
        "--quality", quality,
        "--background", "opaque",
        "--side", view["side"],
    ]
    if view.get("rotate"):
        cmd += ["--rotate", view["rotate"]]
    cmd.append(board)
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("board", help="path to the .kicad_pcb file")
    ap.add_argument("outdir", nargs="?", default=None,
                    help="output dir (default: renders/ beside the board)")
    ap.add_argument("--models-dir", default=None,
                    help=f"KiCad 3D models dir (default: {DEFAULT_MODELS_DIR})")
    ap.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    ap.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    ap.add_argument("--quality", default=DEFAULT_QUALITY,
                    choices=["basic", "high", "user", "job_settings"])
    ap.add_argument("--no-contact-sheet", action="store_true",
                    help="skip the montage contact sheet (still writes views)")
    args = ap.parse_args()

    board = os.path.abspath(args.board)
    if not os.path.isfile(board):
        print(f"FATAL: board not found: {board}", file=sys.stderr)
        return 1

    # Fail closed on the models dir BEFORE any rendering.
    models_dir = resolve_models_dir(args.models_dir)
    os.environ["KICAD9_3DMODEL_DIR"] = models_dir

    board_stem = os.path.splitext(os.path.basename(board))[0]
    outdir = os.path.abspath(args.outdir or os.path.join(os.path.dirname(board), "renders"))
    os.makedirs(outdir, exist_ok=True)

    manifest = {
        "board": board,
        "board_stem": board_stem,
        "kicad_3dmodel_dir": models_dir,
        "width": args.width,
        "height": args.height,
        "quality": args.quality,
        "files": [],
    }

    written = []
    for view_name, view in ANGLE_SET:
        out_png = os.path.join(outdir, f"{board_stem}_{view_name}.png")
        cmd = build_cmd(board, out_png, view, args.width, args.height, args.quality)
        print(f"[render] {view_name}: {' '.join(cmd[5:])}")
        proc = subprocess.run(cmd, env=os.environ.copy(),
                              capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.isfile(out_png):
            print(f"FATAL: render failed for {view_name} (rc={proc.returncode})", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 1
        entry = {
            "view": view_name,
            "file": out_png,
            "sha256": sha256_of(out_png),
            "bytes": os.path.getsize(out_png),
        }
        manifest["files"].append(entry)
        written.append(out_png)
        print(f"[ok] {out_png}  sha256={entry['sha256']}  {entry['bytes']} bytes")

    # ---- Contact sheet ----
    contact_path = os.path.join(outdir, f"{board_stem}_contact_sheet.png")
    if not args.no_contact_sheet:
        missing = [t for t in ("montage", "convert") if shutil.which(t) is None]
        if missing:
            print(f"FATAL: ImageMagick tool(s) {missing} not found in PATH — "
                  f"cannot build contact sheet. Fail loudly, not silently.", file=sys.stderr)
            return 3
        cmd = [
            "montage",
            "-label", "%f",        # label each tile with its filename
            *written,
            "-tile", "4x2",
            "-geometry", "+8+8",
            "-background", "#202020",
            "-fill", "white",
            "-pointsize", "28",
            contact_path,
        ]
        print(f"[contact] {' '.join(cmd[:2])} ... {contact_path}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.isfile(contact_path):
            print(f"FATAL: montage failed (rc={proc.returncode})", file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 3
        entry = {
            "view": "contact_sheet",
            "file": contact_path,
            "sha256": sha256_of(contact_path),
            "bytes": os.path.getsize(contact_path),
        }
        manifest["files"].append(entry)
        print(f"[ok] {contact_path}  sha256={entry['sha256']}  {entry['bytes']} bytes")

    manifest_path = os.path.join(outdir, f"{board_stem}_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"[manifest] {manifest_path}")

    # Print the manifest block for verification.
    print("\n===== MANIFEST =====")
    for e in manifest["files"]:
        print(f"{e['file']}\t{e['sha256']}\t{e['bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
