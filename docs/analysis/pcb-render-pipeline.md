# PCB 3D render pipeline — balloon-fresh tracker boards

**Status:** pipeline fixed and verified. Renders committed under `tracker/hardware/renders/`.
**Method:** every claim below was re-run on this machine on 2026-10-10 with `kicad-cli 9.0.8`.
**Reproduce command:** `tracker/hardware/renders/render_pcb.sh`

---

## 1. TL;DR — what was actually wrong

The reported bug was:

> `KICAD9_3DMODEL_DIR` is unset and no KiCad 3D model library is installed, so PCB renders
> show only substrate + copper + silkscreen with NO component bodies.

**On the measurement machine, that diagnosis is wrong in its first two clauses and right in its
consequence.** Three separate facts were conflated. Measuring them apart:

| Claim | Measured result |
|---|---|
| "no 3D model library is installed" | **FALSE.** `kicad-packages3d 9.0.7-1` is installed: 105 `*.3dshapes` dirs, 14,043 `.step`/`.wrl` files, 4.6 GB at `/usr/share/kicad/3dmodels`. |
| "`KICAD9_3DMODEL_DIR` is unset ⟹ no component bodies" | **FALSE as a causal claim.** With the env var unset, the hub board render *did* contain component bodies (cylindrical electrolytic caps with cast shadows, SMD bodies). KiCad 9 supplies its own package default for `KICAD9_3DMODEL_DIR`, so the templates resolve even when the shell variable is empty. |
| "renders show no component bodies" | **TRUE — but for per-board, per-footprint reasons, not a missing library.** See §3. |

The genuinely broken parts of the pipeline were different, and two of them are worse than the
reported bug because they fail **silently**:

1. **`kicad-cli pcb render` never warns about a missing 3D model.** Exit code 0, clean log, no
   message — the model is just omitted. The prior note in `AGENTS.md` ("if a 3D model is missing
   it prints a warning and omits the model") is **false for kicad-cli 9.0.8**. This is the root
   defect: it makes a model-less render indistinguishable from a good one by any automated check.
2. **`wing_board_v9.kicad_pcb` has 0 of 12 footprints carrying a `(model …)` block** — so its
   render is genuinely copper-only, and no amount of installing packages can change that.
3. **`hub_board_v9.kicad_pcb` has 32 of 39 footprints modelled, but the single largest component
   — the LoRa2021 / F33 radio module — points at a model file that does not exist** in the
   shipped Debian package.

---

## 2. The fix

### 2.1 Env vars (required)

```bash
export KICAD9_3DMODEL_DIR=/usr/share/kicad/3dmodels
export KICAD8_3DMODEL_DIR=/usr/share/kicad/3dmodels   # hub board references ${KICAD8_3DMODEL_DIR} once
```

`KICAD9_3DMODEL_DIR` is **not** honoured merely by being exported — it must point at the real
`3dmodels` tree. Install/repair the library with:

```bash
sudo apt-get install -y kicad-packages3d      # 4.6 GB, provides /usr/share/kicad/3dmodels
```

`KICAD8_3DMODEL_DIR` is required *in addition to* `KICAD9_3DMODEL_DIR` because
`hub_board_v9.kicad_pcb` contains one `${KICAD8_3DMODEL_DIR}` reference (the LoRa2021 module).

KiCad 9 builds the variable name dynamically (`KICAD*_3DMODEL_DIR` is present as a format string
in `/usr/lib/x86_64-linux-gnu/libkicommon.so.9.0.8`) and falls back to its compiled-in package
path when the shell variable is unset. **Pin both variables anyway**: the fallback is an accident
of Debian packaging and will not survive a non-package install.

### 2.2 Working command line

```bash
export KICAD9_3DMODEL_DIR=/usr/share/kicad/3dmodels
export KICAD8_3DMODEL_DIR=/usr/share/kicad/3dmodels

kicad-cli pcb render \
  --output tracker/hardware/renders/hub_board_v9_top.png \
  --side top \
  --zoom 1 \
  --quality high \
  --width 1600 --height 1200 \
  tracker/hardware/hub_board_v9.kicad_pcb
```

Wrap-around script (does both boards, both sides, and runs the coverage check):

```bash
tracker/hardware/renders/render_pcb.sh                 # both boards, top + bottom
tracker/hardware/renders/render_pcb.sh hub_board_v9    # one board
WIDTH=3200 HEIGHT=2400 QUALITY=high tracker/hardware/renders/render_pcb.sh
```

Notes measured on 9.0.8:

* `--quality high` is required for the raytracer + shadows. `basic` still produces bodies but
  with no floor/shadows, which removes the strongest visual cue that geometry loaded.
* Output dimensions come back ~2 % smaller than requested (requested 1600×1200 → written
  1568×1176). Harmless; don't script against exact pixel dimensions.
* The raytracer **runs fine headless** — no display, X server or `xvfb` needed.
* Cost: hub top 121 s, hub bottom 60 s, wing top 59 s, wing bottom 34 s (1600×1200, high).

---

## 3. Per-board 3D model coverage (the real defect)

Static count of `(model …)` blocks per footprint, and the model files checked for existence:

| Board | Footprints | With `(model …)` | Render contains bodies? |
|---|---|---|---|
| `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` | 12 | **0** | **No — copper + silkscreen only** |
| `tracker/hardware/hub_board_v9.kicad_pcb` | 39 | **32** | **Yes, 32/39** |

### 3.1 Wing board — 0/12, flat by data

All 12 footprints come from the custom `WingV9:` library and none has a model assigned:

```
WingV9:SolarCell_52x19mm              x3
WingV9:WingTab_v9_4pin                x1
WingV9:MountingHole_2.2mm_NPTH        x3
WingV9:Fiducial_1mm_Mask2mm           x3
WingV9:FerriteBead_0402_V2provision   x1
WingV9:RF_ProvisionPad_v2only         x1
```

Part of this is physically correct — the wing is a solar panel, and mounting holes, fiducials and
a provision-only RF pad genuinely have no body. But three items *do* have real volume and are
simply unassigned:

* `WingV9:WingTab_v9_4pin` → stock `Connector_PinHeader_2.54mm.3dshapes/PinHeader_1x04_P2.54mm_Vertical.step` (present)
* `WingV9:FerriteBead_0402_V2provision` → stock `Inductor_SMD.3dshapes/L_0402_1005Metric.step` (present)
* `WingV9:SolarCell_52x19mm` ×3 → no stock KiCad model exists; needs a project-local thin-panel model referenced as `${KIPRJMOD}/…`

**Closing this is a board-data change, not a pipeline change, and it is deliberately NOT done in
this branch** (see §5).

### 3.2 Hub board — 32/39, with the biggest part unmodelled

Seven footprints have no model:

```
Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm   (no Jumper.3dshapes in the Debian package at all)
balloon_flight_v9:SX1280_QFN24                          (custom lib; no stock SX1280 model)
balloon_flight_v9:LoRa2021F33_2G4                       (references a model file that is absent)
Tracker_Mechanical:Wing_Tab_4P                          x4 (mechanical)
```

The `LoRa2021F33_2G4` footprint *does* carry a `(model "${KICAD8_3DMODEL_DIR}/RF_Module.3dshapes/NiceRF_LoRa2021.wrl")`
reference, but **that file does not exist**: `RF_Module.3dshapes/` ships 18 modules
(DWM1000, ESP-WROOM, ESP32-S3-WROOM, Raytac…) and a repo-wide search for `*lora*`, `*nicerf*`,
`*sx12*` across all 14,043 model files returns nothing. The reference is a dangling pointer.

This is visible in the artifact: in `tracker/hardware/renders/hub_board_v9_top.png` the large
central module footprint renders as bare pads with a gold centre pad and **no module can** — the
one place where the render would mislead a placement review. The copper under it is fine; the
part simply isn't drawn.

---

## 4. How to tell a real 3D render from a copper-only one

`kicad-cli` will **not** tell you. Measured on 9.0.8 with the hub board:

| Check | Real 3D render | Copper-only render |
|---|---|---|
| Exit code | `0` | `0` — identical |
| stderr / log warnings | **none** | **none** — identical |
| "Successfully created 3D render image" | printed | printed — identical |
| **Rendering time** | 121 s (hub top) / 60 s (wing top) | **1.9 s** |
| **PNG size** | 157 KB (hub top) | **22 KB** |
| Cast shadows under parts | present | absent |
| Component bodies | yes | no |

The 1.9 s / 22 KB row is from a controlled experiment: the hub board re-rendered with
`KICAD9_3DMODEL_DIR=/nonexistent-bad` finished in **1.87 s**, wrote 22,383 bytes, printed
*"Successfully created 3D render image"* and exited **0**. **A broken model path is
indistinguishable from success by exit code or log output.**

Practical checklist, cheapest first:

1. **Timing / file size.** A render that finishes in ~2 s and lands under ~50 KB loaded no
   component geometry. A real hub render is ~2 minutes and >150 KB. This is the fastest
   automated tripwire.
2. **Static coverage count** (deterministic, no render needed):
   ```bash
   python3 - <<'PY'
   import re
   p='tracker/hardware/hub_board_v9.kicad_pcb'
   s=open(p).read(); parts=re.split(r'\n[\t ]*\(footprint ', s)
   print(f"{sum(1 for b in parts[1:] if '(model ' in b)}/{len(parts)-1} footprints modelled")
   PY
   ```
3. **Model-file existence check.** Every `${…3DMODEL_DIR}/X/Y.step` reference must resolve to a
   real file under `$KICAD9_3DMODEL_DIR`. `hub_board_v9` fails this today for the LoRa2021 module.
4. **Visual.** Look for *cast shadows* and *occluding bodies*, not just colour. Silkscreen
   outlines and pad metallisation also look like "shapes" from directly above — a top-down
   render can fool both a human and a vision model, which is why checks 1–3 come first.

**Rule:** never infer component presence from a render alone, and never trust a vision
description of one as proof that the parts are there. Count `(model …)` blocks and resolve the
paths first.

---

## 5. What this branch does not do (deliberate, flagged)

Adding `(model …)` blocks to the wing board (and fixing the LoRa2021 reference) means **editing a
`.kicad_pcb` that is covered by a gate record**. `tracker/hardware/wing_board/wing_v9-GATE-RECORD.json`
stores `board_sha256`, and it currently matches the committed board exactly:

```
record  board_sha256: 8448d76b3a4e108f12016e1980bb954f068625d27522a1640a07ffc72fa3682c
actual  board sha256: 8448d76b3a4e108f12016e1980bb954f068625d27522a1640a07ffc72fa3682c   MATCH
```

Editing the board would silently invalidate that record — the exact stale-evidence defect class
called out in `AGENTS.md`. It would also desynchronise the committed board from its generator
(`tracker/hardware/wing_board/build_wing_v9.py`), which regenerates it and would drop the
hand-added model blocks.

So the correct follow-up, in order, is:

1. Add the model blocks in **`build_wing_v9.py`** (so the generator and the board agree), or add
   them to the board and fix the generator.
2. Ship a project-local model for the 52×19 mm solar cell (a thin panel), referenced as
   `${KIPRJMOD}/3dmodels/…`.
3. Re-run the DRC gate and **regenerate `wing_v9-GATE-RECORD.json`** with the new `board_sha256`,
   confirming the error/warning/unconnected counts are unchanged (adding a `(model …)` block
   cannot change copper, outline, DRC or gerbers — but the record must still be re-issued).
4. Re-render and confirm shadows appear on the wing board.

That is a board + generator + gate-record change and belongs in its own branch, not in a render
pipeline fix.

---

## 6. Committed artifacts

| File | What it is | Bodies? |
|---|---|---|
| `tracker/hardware/renders/hub_board_v9_top.png` | hub, top, `--quality high` | **yes — 32/39 parts** |
| `tracker/hardware/renders/hub_board_v9_bottom.png` | hub, bottom, `--quality high` | mostly flat (parts are top-side) |
| `tracker/hardware/renders/wing_board_v9_top.png` | wing, top | **no — 0/12 modelled; copper + silkscreen** |
| `tracker/hardware/renders/wing_board_v9_bottom.png` | wing, bottom | no — copper + silkscreen |
| `tracker/hardware/renders/render_pcb.sh` | reproducible render driver + coverage check | — |

## 7. Re-verification

```bash
cd <worktree>
export KICAD9_3DMODEL_DIR=/usr/share/kicad/3dmodels
export KICAD8_3DMODEL_DIR=/usr/share/kicad/3dmodels

# timing tripwire: a copper-only render finishes in ~2 s
time kicad-cli pcb render --output /tmp/t.png --side top --zoom 1 --quality high \
  --width 1600 --height 1200 tracker/hardware/hub_board_v9.kicad_pcb
ls -l /tmp/t.png     # expect ~150 KB; ~22 KB means no component geometry loaded
```
