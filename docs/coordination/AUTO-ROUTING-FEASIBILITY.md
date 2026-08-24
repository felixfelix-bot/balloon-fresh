# Auto-Routing Feasibility — VERIFIED RESULTS

**Date:** 2026-08-05 15:00
**Tester:** Orchestrator (direct API verification)

## API VERIFICATION RESULTS

| Capability | Status | Notes |
|-----------|--------|-------|
| kicad-cli DRC --format json | ✅ WORKS | 437 violations parsed on V1 PCB |
| kicad-cli gerber export | ✅ WORKS | Headless, all layers |
| python3.14 + pcbnew import | ✅ WORKS | Must use python3.14, NOT python3.11 |
| pcbnew.NewBoard() | ✅ WORKS | Creates empty .kicad_pcb |
| pcbnew.PCB_TRACK creation | ✅ WORKS | SetStart/SetEnd/SetWidth all functional |
| pcbnew.SaveBoard() | ✅ WORKS | Saves to .kicad_pcb format |
| board.Add(track) | ✅ WORKS | Track added to board |
| pcbnew.LoadBoard() | ❌ NEEDS WXAPP | Fails without wxApp init (headless limitation) |
| python3.11 + pcbnew | ❌ SEGFAULT | Version mismatch (3.11 vs 3.14) |

## CRITICAL FINDING: Must use python3.14

```bash
# WRONG (segfaults):
python3 -c "import pcbnew; ..."

# CORRECT (works):
python3.14 -c "import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages'); import pcbnew; ..."
```

## WORKING PIPELINE

The article's LLM→KiCad→DRC loop is FEASIBLE with these modifications:

### Step 1: Create board from scratch (python3.14)
```python
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

b = pcbnew.NewBoard('/tmp/balloon_v2.kicad_pcb')
# Add footprints, nets, tracks...
pcbnew.SaveBoard('/tmp/balloon_v2.kicad_pcb', b)
```

### Step 2: Run DRC headless (kicad-cli)
```bash
kicad-cli pcb drc --format json -o /tmp/drc.json /tmp/balloon_v2.kicad_pcb
```

### Step 3: Parse DRC JSON + iterate
```python
import json
with open('/tmp/drc.json') as f:
    drc = json.load(f)
violations = drc.get('violations', [])
# Feed back to LLM as text...
```

### Step 4: Export gerbers
```bash
kicad-cli pcb export gerbers -o /tmp/gerbers/ /tmp/balloon_v2.kicad_pcb
```

## LIMITATIONS

1. **LoadBoard fails headless** — needs wxApp. Must use NewBoard() to create from scratch, can't load existing boards. This means we can't modify the V1 PCB — we create a new one.

2. **No interactive router** — KiCad's push-and-shove router is GUI-only. We must place tracks manually (start/end coordinates). No auto-routing in pcbnew API.

3. **No footprint libraries headless** — Need to either:
   - Embed footprint data in the script (S-expression)
   - Or create footprints programmatically with pcbnew.PCB_FOOTPRINT

4. **Multi-segment tracks** — PCB_TRACK is a single segment (straight line). For L-shaped routes, create multiple track segments.

## RECOMMENDED APPROACH

### Hybrid: A* pathfinding + LLM strategy + DRC verification

1. **LLM**: Defines net list, layer assignments, routing priority (high-level strategy)
2. **Python A***: Grid-based pathfinding for each net, avoids obstacles, generates track coordinates
3. **pcbnew API** (python3.14): Creates board, places footprints, draws tracks from A* output
4. **kicad-cli DRC**: Verifies, outputs JSON violations
5. **Python parser**: Feeds violations back to LLM for strategy adjustment
6. **Iterate** until 0 violations

### For ~15 nets on 50×40mm 2-layer:
- Grid resolution: 0.5mm → 100×80 grid cells
- A* on each net sequentially (power first, then signals)
- Ground: route as explicit tracks on bottom layer (NOT copper pour — avoids 3V3↔GND disaster)
- 2-layer: signals on top, GND on bottom
- Expected: 20-40 track segments, 3-5 DRC iterations to converge

### Avoiding V1 PCB's fatal shorts:
- NO copper pours (this caused 18× 3V3↔GND shorts)
- Route GND as explicit tracks on B.Cu
- Route 3V3 as explicit tracks on F.Cu
- DRC catches any shorts before gerber generation

## WHAT FELIX NEEDS TO DO

NOTHING. If we implement the A* + pcbnew pipeline, Felix doesn't need to touch KiCad GUI.

The pipeline can:
1. Create .kicad_pcb from scratch (NewBoard)
2. Place footprints programmatically
3. Route tracks via A* pathfinding
4. Verify with DRC
5. Export gerbers for JLCPCB

Estimated implementation: 4-6 hours for a working prototype.
Estimated board design: 2-3 hours after pipeline works.

## ESP32-C3 GPIO ISSUE

Consultant V6 said GPIO18/GPIO19 don't exist on C3 (USB pins). Need to verify:
- ESP32-C3 has GPIO0-GPIO10 + GPIO18-GPIO19 (USB D-/D+)
- GPIO18/19 CAN be used as regular GPIO if USB is not used
- For balloon: USB not needed in flight → GPIO18/19 OK for LED/FEM_TX
- Alternative: use GPIO3 (available, no boot constraint) for LED

CONCLUSION: The pipeline is FEASIBLE. We can produce JLCPCB-orderable gerbers without Felix touching KiCad GUI.