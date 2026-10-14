# U1 footprint DEFECT — 62 pads, 42 unique numbers; `pad 41` duplicated 13×

**Date:** 2026-10-14 · **Status:** DEFECT, measured. Blocks a clean DRC on the hub.
**Found by:** chasing 12 `drill_out_of_range` violations that all named the *same*
item — `PTH pad 41 [GND] of U1`. Twelve identical violations for one pad number is
itself the tell.

---

## 1. The defect, measured

`U1` = `ESP32-S3-WROOM-1U`. `pcbnew` reports:

| | |
|---|---|
| **Total pads** | **62** |
| **Unique pad numbers** | **42** |
| Drilled pads | 12 |
| `pad 41` occurrences | **13** |
| Unnamed (`""`) pad occurrences | **9** |

Every `pad 41` is **identical: 0.200 mm drill, 0.600 mm pad, attribute 0.** The
module has exactly **41 signal pads** in nature, so a pad numbered 41 is the *last*
signal pad — it is **not** a mounting hole. Twelve extra copies of it, stacked at
whatever positions the footprint file gives them, is a broken footprint.

**Consequence in DRC:** the board's `min_through_hole_diameter = 0.3 mm` (board
setup) is applied to each of the 13 copies, producing **12 `drill_out_of_range`
violations** — one per duplicate. The channel count wrong; the board is being graded
against a footprint that does not describe the part.

## 2. Why this matters beyond the violation count

- **A duplicated pad number is ambiguous in the netlist.** Pads sharing a number on
  one footprint are electrically one node. If those 13 pads are not at the same
  coordinate, the footprint asserts a connection that does not exist on the real
  module — and the router will happily "route" it.
- **The 9 unnamed pads are worse.** A pad with no number has no net and no
  mechanical meaning on a 41-pad module.
- **The ESP32-S3-WROOM-1U does have 3 or 4 mechanical/mounting features** (the
  module's castellations plus its body locating marks), so *some* non-signal pads
  are legitimate — but they must be **uniquely identified and correctly drilled**,
  not 13 copies of `41`.

## 3. What must NOT be done (the tempting wrong fix)

**Do not raise the board's `min_through_hole_diameter` down to 0.2 mm to silence the
violations.** That would paper over a footprint defect with a fab-floor relaxation,
on a board whose whole point is to hold a 2× JLCPCB margin. The violations are
*correct* — they are catching a real footprint fault.

## 4. The correct fix

1. **Open the `U1` footprint source** and audit every pad: each must have a unique
   number (or a deliberate, unique mechanically-named feature), and the 13 `41`s
   must collapse to **one** pad.
2. **Establish the mounting feature from Espressif's own footprint** for
   `ESP32-S3-WROOM-1U` rather than inventing it — the module's mechanical holes are
   specified in the datasheet's recommended-land-pattern drawing.
3. **Re-check the netlist after the fix**: pad count and unique-number count must
   agree, and the 12 `drill_out_of_range` items must disappear *because the duplicate
   pads no longer exist* — not because a rule was relaxed.
4. This is a **footprint-library** fix, so it also affects any other board using the
   same `U1` definition. Grep the library before fixing one board.

## 5. Reproduce

```
python3 -c "
import pcbnew,sys; sys.path.insert(0,'/usr/lib/python3/dist-packages')
b=pcbnew.LoadBoard('<board>.kicad_pcb')
u1=b.FindFootprintByReference('U1')
from collections import Counter
c=Counter(p.GetNumber() for p in u1.Pads())
print('total pads', len(list(u1.Pads())), 'unique', len(c))
print({n:k for n,k in c.items() if k>1})
"
```

## 6. Related

- The other two remaining classes are **not** this defect:
  `starved_thermal` (1 — `Pad 2 [GND] of U7`, one thermal spoke instead of two, a
  layout/zone item) and `via_dangling` (2 — `/SX1280_BUSY` and `/SX1280_DIO1`
  vias connected on one layer only, the honest failure of the boxed-in fan-out).
- The 5 remaining unconnected items include **one on `/SX1280_DIO1`**
  (`Via (65.9,11.6)` ↔ `Pad 10 of U4 (52.5,29.2)`) — the same net whose fan-out was
  boxed in. The other four are `GND` pad-to-plane taps on `C_MON`, `J_W1` (F↔B),
  `J_W3` (F↔B) and `C_HF` — i.e. pads where the v2 stitcher correctly **rejected**
  a 0.60 mm via for lack of room.
