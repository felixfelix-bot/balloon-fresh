# PCB Session Learnings — 2026-08-05/06

## Root Causes Identified

### 1. Wrong Model Assignment (8h wasted)
- worker-layout configured for kimi-k3:cloud ($15/M output)
- kimi-k3:cloud went DOWN (503 quota exhausted)
- Workers silently failed or fell back to glm-5.2 (can't do spatial reasoning)
- Every board came back empty or broken
- FIX: kimi-k2.7-code ($4/M) is the spatial model. Available, cheaper, capable.

### 2. SaveBoard Bug (caused every "empty board")
- `b.Save(PATH)` silently drops tracks in KiCad 9 SWIG bindings
- `pcbnew.SaveBoard(PATH, b)` with 2 args works correctly
- 33+ board variants produced as empty files because of this
- FIX: Always use `pcbnew.SaveBoard(PATH, b)` — documented in all worker prompts

### 3. No Placement Gate (caused all routing shorts)
- Components placed overlapping each other
- Routing attempted on overlapping footprints
- 538 DRC violations from crossing pads that were physically on top of each other
- FIX: Gate 2.5 — verify 0 shorting_items BEFORE any routing begins

### 4. Schematic Was Script-Generated Garbage
- v_c3_flight.kicad_sch had 1/17 lib_symbols entries
- 55 placed symbols but symbol_instances only referenced 1
- Three fix attempts failed — file structurally broken
- FIX: Bypass schematic entirely, create PCB via pcbnew Python API

### 5. Timeout Config Not Applied
- `child_timeout_seconds: 3600` set in config.yaml
- `dialog_timeout_s: 1800` set
- Workers still timing out at 300s
- delegate_task may use a different timeout mechanism
- WORKAROUND: Split tasks into <300s chunks. Placement then routing then DRC.

## What Actually Works

### pcbnew Python API (KiCad 9)
```python
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Create/load
b = pcbnew.LoadBoard(PATH)

# Add footprint, track, via
b.Add(pcbnew.PCB_TRACK(b))

# Move footprint
fp.SetPosition(pcbnew.VECTOR2I(int(x_mm * 1e6), int(y_mm * 1e6)))

# SAVE (CRITICAL — 2 args, NOT b.Save())
pcbnew.SaveBoard(PATH, b)

# Zones
zones = list(b.Zones())
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(zones)
```

### Freerouting v2.2.4
- Runs headless with xvfb-run
- 3 passes on 57 nets: ~56 seconds
- BUT: won't write output files headless (known v2.2.4 bug)
- Output path `-do` flag silently ignored
- Manual Python routing is more reliable

### Model Selection
| Task | Model | Cost | Status |
|------|-------|------|--------|
| Schematic/netlist gen | GLM 5.2 | $4.40/M | WORKING |
| PCB placement (spatial) | kimi-k2.7-code | $4/M | WORKING |
| PCB routing (collision-aware) | kimi-k2.7-code | $4/M | WORKING |
| Visual board inspection | kimi-k2.7-code | $4/M | WORKING |
| kimi-k3:cloud | DEAD | $15/M | 503 DOWN |

## Current Pipeline State

### Board: v_c3_flight_final.kicad_pcb
- 20 footprints (real components)
- 0 tracks (routing in progress)
- 4 layers: F.Cu, In1(GND plane), In2(3V3 plane), B.Cu
- Board: 55x45mm, 0.6mm thickness
- DRC: 0 shorting_items (Gate 2.5 PASSED)

### Pipeline Phases
1. PLACEMENT: DONE (commit 4c713b3)
2. ROUTING: RUNNING (deleg_f8d83692, kimi-k2.7-code)
3. GERBERS: PENDING (after routing passes Gate 4)
4. REVIEW: PENDING (consultant sign-off)

### Quality Gates
- Gate 0: Model available (curl test)
- Gate 1: Schematic loads
- Gate 2: ERC < 10
- Gate 2.5: Placement 0 shorts (BEFORE routing)
- Gate 3: PCB > 10 footprints
- Gate 4: DRC < 20 violations, 0 shorting_items
- Gate 5: F_Cu.gtl > 1KB
- Gate 6: Thickness = 0.6mm
- Gate 7: All footprints inside board outline
