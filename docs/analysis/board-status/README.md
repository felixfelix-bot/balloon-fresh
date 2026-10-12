# Board status — balloon-fresh v9 (machine-censused)

**Figure:** `board-status-v9.svg` (and `.png`, same geometry)
**Method:** `board_status_census.py` reads every board with the KiCad `pcbnew`
bindings and asks `kicad-cli pcb drc` for the unconnected count. Nothing in the
figure is hand-typed: every bar, badge and number is rendered from
`census.json`, and every drawn element carries a `data-*` attribute holding the
census value it represents.

## Reproduce

```bash
cd <repo root>
# 1. census — pcbnew only loads under /usr/bin/python3.14 (3.11 SEGFAULTS)
/usr/bin/python3.14 tracker/hardware/board_status_census.py \
  tracker/hardware/hub_board_v9.kicad_pcb \
  tracker/hardware/wing_board/wing_board_v9.kicad_pcb \
  tracker/hardware/auto_bootsel/auto-bootsel-interposer.kicad_pcb \
  tracker/hardware/output/v8g_krt_routed.kicad_pcb \
  > docs/analysis/board-status/census.json

# 2. render
python3 tracker/hardware/board_status_figure.py \
  docs/analysis/board-status/census.json \
  docs/analysis/board-status/board-status-v9.svg

# 3. verify — re-reads the SVG and asserts it against the census
python3 tracker/hardware/board_status_figure_check.py \
  docs/analysis/board-status/board-status-v9.svg \
  docs/analysis/board-status/census.json
# -> "checks run: 186 / PASS"
```

## Verdict rule

| verdict       | meaning                                                  |
|---------------|----------------------------------------------------------|
| `routed`      | copper present **and** DRC reports 0 unconnected items    |
| `partial`     | copper present, DRC reports unconnected items > 0         |
| `plane_only`  | zone(s) present, no tracks and no vias                    |
| `placed_only` | no copper at all (no tracks, no vias, no zones)           |

## Current state

| board | layers | fp | segments | vias | zones (filled) | DRC unconn. | verdict |
|---|---|---|---|---|---|---|---|
| `hub_board_v9` | 4 | 39 | 0 | 0 | 3 (3) | 101 | `plane_only` |
| `wing_board_v9` | 2 | 15 | 20 | 8 | 0 | 0 | `routed` |
| `auto-bootsel-interposer` | 2 | 14 | 9 | 0 | 1 (1) | 0 | `routed` |
| `v8g_krt_routed` (old gen) | 4 | 20 | 398 | 55 | 2 (2) | 0 | `routed` |

Per-layer copper:

| board | F.Cu | In1.Cu | In2.Cu | B.Cu |
|---|---|---|---|---|
| `hub_board_v9` | 1 zone | 1 zone | — | 1 zone |
| `wing_board_v9` | 10 seg / 218.00 mm | — | — | 10 seg / 218.00 mm |
| `auto-bootsel-interposer` | 9 seg / 36.92 mm | — | — | 1 zone |
| `v8g_krt_routed` | 302 seg / 600.99 mm | 54 seg / 91.53 mm + 1 zone | 15 seg / 9.89 mm + 1 zone | 27 seg / 118.68 mm |

Pads per mounting side: `hub` 210 front / 16 back / 16 through;
`wing` 16 front / 6 back / 3 NPTH; `bootsel` 8 front / 6 through / 4 NPTH;
`v8g` 92 front / 26 through.

**Vias are reported board-total only.** A via's `GetLayer()` is just its primary
layer, so a per-layer via count would misattribute it — it is deliberately not
drawn per layer.

## What this figure changed

`wing_board_v9` was **not** `routed` before this work: 8 F.Cu segments, 0 B.Cu
segments, 0 vias, DRC **12 unconnected** — the back-side series string was
electrically isolated on a board whose cells sit on B.Cu. After the fix
(ADR-065 addendum): **20 segments (10 F.Cu + 10 B.Cu), 8 vias, DRC 0 unconnected**.

`hub_board_v9` was `placed_only` (39 footprints, **0 copper of any kind**). After
ADR-067 it is `plane_only`: GND poured on In1.Cu + F.Cu + B.Cu, DRC unconnected
**157 → 101**, and all 56 fixed items are GND (66 → 10). It is still **not
routed** — there are no tracks and no vias, so the signal nets remain
unconnected. The figure says `plane_only` on purpose; calling it "routed" would
be false.

## Verification limits (stated, not hidden)

- The checker proves the figure is a **faithful rendering of the census**
  (186 assertions: every board, verdict, layer value, bar height vs the declared
  scale, pad-bar width, label presence, and zero text collisions). It does
  **not** judge aesthetics, and it cannot detect a census that was itself
  censused wrongly — that is what the `kicad-cli pcb drc` call and the pcbnew
  counts are for, and both are re-run by the reproduce command above.
- The checker is proven able to fail: `tests/test_board_status_figure.py`
  (`TestHarnessCanFail`) feeds it a tampered census, a dropped label and a wrong
  bar height, and asserts each is rejected.
