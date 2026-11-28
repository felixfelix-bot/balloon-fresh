# vnext MINIMAL — layer/area audit + keep/optional/remove annotation

Plan phases **2** (routing-demand audit, gate G3) and **3** (keep/optional/remove
annotation, gate G4) of `docs/fab/VNEXT-MINIMAL-PLAN.md`.

**Nothing here is a board edit, a fit result or an outline claim.** Every number is a
measurement of an EXISTING board file, named by SHA below.

## Artefacts

| file | what it is |
|---|---|
| `vnext_layer_audit.py` | read-only pcbnew census: outline bbox, per-layer track length / segments / vias, per-net segments, site-named copper, zone inventory, footprint bboxes. Self-checks S1–S5 must pass or it refuses to write. |
| `layer_audit.json` | census of `hub_board_v11_stage1.kicad_pcb` (v11 stage-1, the ADR-089 G3 reference board). |
| `layer_audit_v10.json` | same census of the canonical v10 board, for delta reference only. |
| `build_verdicts.py` → `verdicts.json` | 101 verdicts — 100 % of the FULL v11 netlist reference set. KEEP 93 / OPTIONAL 5 / REMOVE 2 / REPLACE 1. |
| `build_provenance.py` → `provenance.json` | SHA256 of every input artefact (ordered gerbers, v10 canonical board, stage-1 board), the site-D divergence finding, and the F33 identity conflict. |
| `render_verdict_plot.py` → `keep-optional-remove-plot.png` | reference placement disposition, top and bottom sides drawn in a common top-view XY. |
| `MINIMAL-NETLIST.md` | the removed-net list and the ref that consumed each net (plan Phase 0 exit criterion (a)). |

## What the numbers say (no mass-reduction claim)

Stage-1 board `09ae5819…` (72.0 × 80.0 mm bbox, nominal 1.6 mm, 49 footprints, 730 tracks,
52 vias, 5 zones):

- F.Cu 426.59 mm / 323 segments · B.Cu 482.18 mm / 361 segments
- In1.Cu 174.22 mm / 19 segments · In2.Cu 208.61 mm / 27 segments
- inner-layer share **382.83 / 1291.60 mm = 29.6 %**

Two different removal quantities — do not conflate them:

1. **Nets whose every pad consumer is in the REMOVE set** (`/U_C_BUSY`, `/U_C_CS_N`,
   `/U_C_IRQ`, `/U_C_RESET_N`): **0.00 mm, 0 segments, 0 vias.** On this board U_C's
   control pads are unrouted; the "19.81 mm" in ADR-145 is a PAD SPAN, not copper.
2. **Site-named copper** — nets named for a REMOVE-set site (`/E28_*` on stage-1, the
   site-D equivalent of `/LORA1280_*`): **39 segments, 280.30 mm, 13 vias**
   (F 6.37 · In1 86.81 · In2 91.95 · B 95.16 mm). Their only consumers are `U1` and the
   removed site, so that copper disappears with the site on a MINIMAL rebuild —
   **21.7 % of the board's routed track length**, 38 % of it already on inner layers.

That second line is the honest core of gate G3: a meaningful share of routing vanishes,
but it is *fanout to the removed module*, not the module's own network — so it does not
prove the board shrinks to any given outline. Zone copper is not attributed: GND (F 4733.87
mm², In1 5273.89 mm², B 69.77 mm²), `/VSCAP` (B 4764.17 mm²) and `+3V3` (B 6.47 mm²) are
shared rails.

## Reproduce

`pcbnew` is only importable from a KiCad-matching interpreter, not from `/usr/bin/python3`
on this host (`ModuleNotFoundError: No module named 'pcbnew'`; the distro package exists at
`/usr/lib/python3/dist-packages` but the venv python is 3.11):

```bash
~/venvs/kicad/bin/python docs/analysis/vnext-minimal-audit-20261125/vnext_layer_audit.py \
  "$PWD/tracker/hardware/hub_board_v11_stage1.kicad_pcb" \
  /tmp/layer_audit.json \
  --provenance docs/analysis/vnext-minimal-audit-20261125/provenance.json \
  --verify-hash 09ae5819fa76e3c338461b204d5f373f9e17df0de6a52aeef78bf6352b578309
```

Pass an **absolute** board path — a relative path resolves against the CWD, the loader
returns `None`, and the failure reads as `AttributeError: 'NoneType' object has no
attribute 'GetDrawings'`, which looks like a corrupt board but is a path error.

Re-verified 2026-11-27 with KiCad 9.0.9: `--verify-hash` passed, S1–S5 passed
(`footprints=49 nets=53 removed_nets=4 tracks=730 vias=52`), and the regenerated census is
**identical** to `layer_audit.json` outside `_meta` — the only differences are the absolute
paths recorded in `_meta`.

## Still open (do not read as done)

- Bare-PCB mass is `TODO(unverified)` — 27.05 g / 31.05 g are ASSEMBLY masses.
- F33 module identity is a COMPETING-EVIDENCE record (NiceRF page says LoRa2021F33-2G4,
  LCSC listing says LoRa1121F33-2G4); the operator's physical module is unmeasured. Gate G2.
- Any outline candidate (50 × 60 mm etc.) is a Phase-4 OUTPUT, not an input.
