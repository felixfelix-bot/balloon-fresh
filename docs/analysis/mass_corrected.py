#!/usr/bin/env python3
"""Corrected mass budget with the REAL board facts now extracted.

VERIFIED FROM THE BOARD FILES (not assumed):
  hub:  115 x 103 mm, 0.8 mm (was 0.6 - not a JLC 4-layer option)
  wing: 25 x 184 mm,  0.6 mm 2-layer (JLC DOES offer 0.6 mm at 2 layers)
  wing cells: SC1..SC6 = SIX 52.07 x 19.65 x 0.21 mm cells PER WING
  tabs: J_W1..J_W4 = 4 wing tabs at the mid-point of each board edge
  mount holes: TH1 (9.425, 9.425), TH2 (9.425, 93.575) - both at x=9.425
"""
FR4 = 1.85          # g/cm3
FINISH = 1.15       # +15% for copper, mask, silk

def pcb_g(w_mm, h_mm, t_mm):
    return (w_mm/10) * (h_mm/10) * (t_mm/10) * FR4 * FINISH

hub_pcb = pcb_g(115, 103, 0.8)
wing_pcb_each = pcb_g(25, 184, 0.6)
wing_pcb = 2 * wing_pcb_each

COMPONENTS = {
    "ESP32-S3-WROOM-1U module":     3.20,
    "MAX-M10S avg over fleet (1.3 x 4/10)": 0.52,
    "SX1280 + LDO + diodes + passives":     0.60,
    "U.FL x4":                              0.48,
    "solder, all SMD":                      0.50,
}
comp = sum(COMPONENTS.values())

CELL_LO, CELL_HI = 0.8, 1.6      # g per 52x19mm encapsulated cell
CELLS_PER_WING = 6
cells_lo = 2 * CELLS_PER_WING * CELL_LO
cells_hi = 2 * CELLS_PER_WING * CELL_HI
HARNESS = 2.5                    # tabs, wires, thread, solder on tabs

hub_total = hub_pcb + comp
wing_lo = wing_pcb + cells_lo + HARNESS
wing_hi = wing_pcb + cells_hi + HARNESS
payload_lo = hub_total + wing_lo
payload_hi = hub_total + wing_hi

ENV_LO, ENV_HI = 60.0, 100.0
allup_lo = payload_lo + ENV_LO
allup_hi = payload_hi + ENV_HI

print(f"hub  PCB 115x103x0.8 : {hub_pcb:6.1f} g")
print(f"hub  components      : {comp:6.1f} g")
print(f"HUB  TOTAL           : {hub_total:6.1f} g")
print()
print(f"wing PCB 25x184x0.6 ea: {wing_pcb_each:6.1f} g  (x2 = {wing_pcb:.1f} g)")
print(f"cells 12 x {CELL_LO}-{CELL_HI} g    : {cells_lo:6.1f} - {cells_hi:.1f} g")
print(f"harness/tabs/holes   : {HARNESS:6.1f} g")
print(f"WINGS TOTAL          : {wing_lo:6.1f} - {wing_hi:.1f} g")
print()
print(f"PAYLOAD (hub+wings)  : {payload_lo:6.1f} - {payload_hi:.1f} g")
print(f"+ envelope {ENV_LO:.0f}-{ENV_HI:.0f} g : {ENV_LO:6.1f} - {ENV_HI:.1f} g")
print(f"ALL-UP MASS          : {allup_lo:6.1f} - {allup_hi:.1f} g")
print()
print("replaces the earlier ESTIMATE 108-154 g; the wing cell count (12 total)")
print("and the 0.6 mm wing thickness are now from the board files, not assumed.")
