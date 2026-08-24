# V1 PCB GPIO Fix Plan

## Problem
Two GPIO collisions found by consultant review. Firmware already fixed
(LED→GPIO18, FEM_TX→GPIO19). Schematic and gerbers must match.

## Collisions Found

| Pin | Old Assignment | New Assignment | Reason |
|-----|---------------|----------------|--------|
| GPIO10 | LED + LR2021 NSS | LR2021 NSS only | SPI chip-select must be exclusive |
| GPIO1 | GPS UART RX + FEM_TX | GPS UART RX only | UART RX needs dedicated pin |
| GPIO18 | (unused) | LED | Moved from GPIO10 |
| GPIO19 | (unused) | FEM_TX | Moved from GPIO1 |

## Schematic Changes Required

### Find KiCad project
```bash
# Search for KiCad files in repo
find ~/repos/balloon-fresh/ -name "*.kicad_sch" -o -name "*.kicad_pcb" -o -name "*.kicad_pro"
# Expected: pcb/v1/ or hardware/ or similar
```

### Changes to make

1. **LED circuit:**
   - Find LED component (likely D1 or similar) and its current-limiting resistor
   - Change the net label from GPIO10 to GPIO18
   - Move the component symbol to GPIO18 pin on the MCU

2. **FEM_TX control line:**
   - Find FEM_TX net (connected to GPIO1)
   - Change net label from GPIO1 to GPIO19
   - Move to GPIO19 pin on MCU

3. **LR2021 NSS:**
   - Verify NSS stays on GPIO10 (no change needed)
   - Remove any LED-related components from GPIO10 net

4. **GPS UART RX:**
   - Verify GPS UART RX stays on GPIO1 (no change needed)
   - Remove FEM_TX from GPIO1 net

### Pin Assignment Table (after fix)

| GPIO | Function | Component |
|------|----------|-----------|
| 1 | GPS UART RX | GPS module |
| 2 | SPI MISO | LR2021 |
| 3 | LR2021 RST | LR2021 |
| 4 | LR2021 BUSY | LR2021 |
| 5 | LR2021 DIO9 (IRQ) | LR2021 |
| 6 | SPI SCK | LR2021 |
| 7 | SPI MOSI | LR2021 |
| 10 | LR2021 NSS (CS) | LR2021 |
| 18 | Status LED | LED + resistor |
| 19 | FEM TX control | FEM module |

## Gerber Regeneration

### Check for KiCad CLI
```bash
which kicad-cli 2>/dev/null
# If available, regenerate gerbers:
kicad-cli pcb export gerbers -o gerbers/ pcb/v1/*.kicad_pcb --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts
kicad-cli pcb export drill -o gerbers/ pcb/v1/*.kicad_pcb
```

### If no KiCad CLI
- Open .kicad_pcb in KiCad GUI
- Make pin assignment changes in schematic
- Run PCB layout update (re-route moved nets)
- Export gerbers via File → Plot
- Export drill file
- Verify BOM and CPL (pick-and-place) files are current

## JLCPCB Order Checklist

- [ ] Gerber files (ZIP with .gbr, .drl, .GKO)
- [ ] BOM file (.csv with part numbers, quantities)
- [ ] CPL file (pick-and-place, .csv)
- [ ] Board specs confirmed:
  - Layer count: 2 (or 4 if V1 spec)
  - Board thickness: 1.6mm (standard)
  - Copper weight: 1oz (standard)
  - Surface finish: HASL or ENIG
  - Solder mask color: (check existing spec)
  - Silkscreen color: (check existing spec)
- [ ] DRC (Design Rule Check) passes
- [ ] No remaining GPIO collisions
- [ ] All nets properly routed

## Current Status

- Gerbers exist (from previous work, pre-fix)
- BOM and CPL exist (from previous work)
- 0 electrical shorts verified (but with old pin assignments)
- KiCad CLI status: unknown (need to check)

## Risk Assessment

- **Low risk:** Only 2 net label changes, no major re-routing
- **Medium risk:** If GPIO18/GPIO19 have existing traces, may need re-route
- **Order delay:** If gerbers need full KiCad GUI work, add 1 day to prep

## Estimated time: 2 hours (with KiCad GUI) or 30 min (with kicad-cli)