# Multi-angle board render views (tooling)

Reproduce command (from repo root, ~50–70 s per view on a loaded box, budget
5–10 min for 8 views + contact sheet):

```bash
python3 scripts/render_board_views.py tracker/hardware/hub_board_v9.kicad_pcb
python3 scripts/render_board_views.py tracker/hardware/wing_board/wing_board_v9.kicad_pcb
```

Each run writes `<board>_<view>.png` for every view plus a single labelled
`<board>_contact_sheet.png` and a `<board>_manifest.json` (sha256 + byte size
per file) into a `renders/` dir beside the board (override: second positional
`OUTDIR` argument).

## Why

The operator asked to *"render the board from multiple different angles so
that it is easier to reason about."* A single top or isometric render is not
enough: what a human needs is several **fixed, comparable** angles and **one
contact sheet** to compare them at a glance. The true side elevation is the
view that exposes a part that is too tall.

## The fixed angle set

Eight views, always the same names and camera parameters, so any two boards
(or two revisions of one board) are directly comparable:

| View        | `--side` | `--rotate`  | What it shows                          |
|-------------|----------|-------------|----------------------------------------|
| `top`       | `top`    | —           | orthographic top-down                  |
| `bottom`    | `bottom` | —           | orthographic bottom-up                  |
| `iso_ne`    | `top`    | `30,0,45`   | isometric from NE corner (above)       |
| `iso_nw`    | `top`    | `30,0,315`  | isometric from NW corner (above)       |
| `iso_se`    | `top`    | `-30,0,45`  | isometric from SE corner (below)       |
| `iso_sw`    | `top`    | `-30,0,315` | isometric from SW corner (below)       |
| `side_e`    | `right`  | —           | **true side elevation** (board height) |
| `side_n`    | `front`  | —           | true side elevation, other axis        |

Option names are the real `kicad-cli pcb render` options (verified against
`kicad-cli pcb render --help`, KiCad 9.0.8): `--side`, `--rotate X,Y,Z`,
`--width/--height` (default 1800×1400), `--quality high`, `--background
opaque`.

## The `KICAD9_3DMODEL_DIR` requirement (fail-closed)

Footprints that reference library 3D models as `${KICAD9_3DMODEL_DIR}/...`
render **silently without bodies** when that variable is unset — no error,
just a hollow board that looks authoritative. The hub board references it 31
times. Therefore the script:

1. Exports `KICAD9_3DMODEL_DIR` itself (default `/usr/share/kicad/3dmodels`,
   override with `--models-dir DIR`; an existing environment variable wins
   over the default but loses to `--models-dir`).
2. **Fails closed (exit 2)** before rendering anything if the resolved
   directory does not exist, printing exactly what it checked. It never falls
   back silently: an explicit override pointing at a missing directory is a
   hard error, because the fallback could mask the mistake with a hollow
   render.

Prove it: `python3 scripts/render_board_views.py BOARD --models-dir /nope`
→ exit 2, no PNGs written.

## Contact sheet

Built with ImageMagick `montage` (`-label %f`, 4×2 tiles, dark background).
If `montage` (or `convert`) is missing from PATH the script **fails loudly**
(exit 3) rather than silently skipping the sheet.

## Determinism and what is committed

Re-running produces the **same file set** with the same names; pixel content
may vary slightly between runs (renderer non-determinism), so the verifiable
artifact is the **manifest** (`sha256` + bytes per file), not the pixels.

**Commit policy:** only the script, this doc, and the small contact sheets
are committed. The eight per-view PNGs per board are regenerable in minutes
and are deliberately NOT committed — `git add` the contact sheets by explicit
path only.

## Read-only guarantee

The script never modifies board, schematic, netlist, footprint or 3D model
data; it only writes into its output directory.
