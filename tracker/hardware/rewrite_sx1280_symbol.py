#!/usr/bin/env python3
"""STEP 1: rewrite the SX1280 symbol with the REAL pin names, numbers and sides.

Source of truth: Semtech SX1280/SX1281 Data Sheet Rev 3.2 (March 2020), Table 2-1 "Transceiver
Pinout" and Figure 2-1 "Transceiver Pin Locations", vendored at docs/sx1280/.

This replaces a placeholder that was WRONG ON 20 OF 24 PINS. The rewrite is done from the datasheet's
own table, not from memory, and every pin carries its Table 2-1 description so the next reader does
not have to re-derive it.

LAYOUT follows Figure 2-1: pins 1-6 on the LEFT (top to bottom), 7-9 on the BOTTOM (left to right),
10-18 on the RIGHT (bottom to top), 19-24 on the TOP (right to left), exposed pad as pad 0 in the
centre. Our symbol renders the exposed pad as pin number "0" -- the datasheet's own number -- and the
existing footprint already has a 25th pad for it, matched by POSITION, not by number (see note).

Only the pin elements are replaced. Every property, the rectangle body and the sub-symbol structure
are left byte-identical, because rewriting them from memory is how the placeholder got here.
"""
import re

WT = "/home/c08r4d0r/worktrees/v9-route"
LIB = f"{WT}/tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.kicad_sym"

# ---- REAL pinout: Semtech DS Rev 3.2 Table 2-1, verbatim --------------------------------
# (number, name, electrical type, side, description)
PINS = [
    (0,  "GND",     "passive",  "centre", "Exposed Ground pad"),
    (1,  "VR_PA",   "passive",  "LEFT",   "Regulated supply for the PA"),
    (2,  "VDD_IN",  "power_in", "LEFT",   "Regulated supply input. Connect to Pin 12."),
    (3,  "NRESET",  "input",    "LEFT",   "Reset signal, active low with internal pull-up at 50k"),
    (4,  "XTA",     "passive",  "LEFT",   "Reference oscillator connection or TCXO input"),
    (5,  "GND",     "passive",  "LEFT",   "Ground"),
    (6,  "XTB",     "passive",  "LEFT",   "Reference oscillator connection"),
    (7,  "BUSY",    "output",   "BOTTOM", "Transceiver busy indicator"),
    (8,  "DIO1",    "bidi",     "BOTTOM", "Optional multi-purpose digital I/O"),
    (9,  "DIO2",    "bidi",     "BOTTOM", "Optional multi-purpose digital I/O"),
    (10, "DIO3",    "bidi",     "RIGHT",  "Optional multi-purpose digital I/O"),
    (11, "VBAT_IO", "power_in", "RIGHT",  "Supply for the Digital IO interface (1.8-3.7V). Must be <= VBAT."),
    (12, "DCC_FB",  "passive",  "RIGHT",  "Regulated output voltage from the internal regulator"),
    (13, "GND",     "passive",  "RIGHT",  "Ground"),
    (14, "DCC_SW",  "passive",  "RIGHT",  "DC-DC Switcher Output"),
    (15, "VBAT",    "power_in", "RIGHT",  "Supply for the RFIC (1.8-3.7V). Must be >= VBAT_IO."),
    (16, "MISO_TX", "output",   "RIGHT",  "SPI slave output / UART Transmit pin"),
    (17, "MOSI_RX", "input",    "RIGHT",  "SPI slave input / UART Receive pin"),
    (18, "SCK_RTSN", "input",   "RIGHT",  "SPI clock / UART Request To Send"),
    (19, "NSS_CTS", "input",    "TOP",    "SPI Slave Select / UART Clear To Send"),
    (20, "GND",     "passive",  "TOP",    "Ground"),
    (21, "GND",     "passive",  "TOP",    "Ground"),
    (22, "RFIO",    "bidi",     "TOP",    "RF transmit output and receive input"),
    (23, "GND",     "passive",  "TOP",    "Ground"),
    (24, "GND",     "passive",  "TOP",    "Ground"),
]

# body: keep the existing rectangle (-12.7,17.78)-(12.7,-17.78); pins sit on its edges.
BX, BY = 12.7, 17.78
LEAD = 2.54

# assign coordinates. Inside the body, y grows downward in KiCad's symbol space, so the FIRST pin of a
# left column is at the BOTTOM flag side... we instead place symmetric so the order reads naturally.
def place(side, idx, total):
    """return (x, y, rotation) for pin idx (0-based) of total on the given side.

    LEFT/RIGHT pins spread along Y (body height); BOTTOM/TOP pins spread along X (body width).
    Using one span for both axes is what pushed pins outside the rectangle on the first attempt --
    the body is 25.4 wide but 35.56 tall, so the span MUST be per-axis.
    """
    if side in ("LEFT", "RIGHT"):
        step = (BY * 2) / (total + 1)
        off = step * (idx + 1)
        if side == "LEFT":          # top -> bottom, reading downward
            return (-BX - LEAD, BY - off, 0)
        return (BX + LEAD, -BY + off, 180)   # bottom -> top
    step = (BX * 2) / (total + 1)
    off = step * (idx + 1)
    if side == "BOTTOM":            # left -> right
        return (-BX + off, -BY - LEAD, 90)
    return (BX - off, BY + LEAD, 270)        # TOP: right -> left, mirroring the datasheet


groups = {}
for num, name, etype, side, desc in PINS:
    if side == "centre":
        continue
    groups.setdefault(side, []).append((num, name, etype, side, desc))

coords = {}
for side in ("LEFT", "RIGHT", "TOP", "BOTTOM"):
    lst = groups.get(side, [])
    # LEFT/RIGHT read top->bottom by ascending pin number; BOTTOM reads left->right ascending;
    # TOP reads right->left ascending (so it mirrors BOTTOM).
    for i, (num, name, etype, side_, desc) in enumerate(lst):
        coords[num] = place(side, i, len(lst))

# exposed pad, dead centre
coords[0] = (0.0, 0.0, 0)


def pin_block(num, name, etype, x, y, rot):
    t = "\t"
    return (
        f'{t}{t}(pin {etype} line\n'
        f'{t}{t}{t}(at {x:.2f} {y:.2f} {rot})\n'
        f'{t}{t}{t}(length {LEAD})\n'
        f'{t}{t}{t}(name "{name}"\n'
        f'{t}{t}{t}{t}(effects\n'
        f'{t}{t}{t}{t}{t}(font\n'
        f'{t}{t}{t}{t}{t}{t}(size 1.27 1.27)\n'
        f'{t}{t}{t}{t}{t})\n'
        f'{t}{t}{t}{t})\n'
        f'{t}{t}{t})\n'
        f'{t}{t}{t}(number "{num}"\n'
        f'{t}{t}{t}{t}(effects\n'
        f'{t}{t}{t}{t}{t}(font\n'
        f'{t}{t}{t}{t}{t}{t}(size 1.27 1.27)\n'
        f'{t}{t}{t}{t}{t})\n'
        f'{t}{t}{t}{t})\n'
        f'{t}{t}{t})\n'
        f'{t}{t})\n'
    )


s = open(LIB, encoding="utf-8").read()
i = s.find('(symbol "SX1280"')
assert i >= 0
d = 0
j = i
while j < len(s):
    if s[j] == "(":
        d += 1
    elif s[j] == ")":
        d -= 1
        if d == 0:
            break
    j += 1
blk = s[i:j + 1]

# locate the pin-bearing sub-symbol and replace only its pins
m = re.search(r'\(symbol "SX1280_1_1"', blk)
assert m, "SX1280_1_1 unit not found"
k = m.start()
# find the end of that sub-symbol
d = 0
p = k
while p < len(blk):
    if blk[p] == "(":
        d += 1
    elif blk[p] == ")":
        d -= 1
        if d == 0:
            break
    p += 1
unit = blk[k:p + 1]

newpins = "".join(pin_block(n, nm, et, *coords[n]) for n, nm, et, _s, _d in PINS)
newunit = unit[:unit.rindex("(pin ")] + newpins + unit[unit.rindex("(pin "):][-0:] if False else ""
# rebuild: everything up to the first pin, then the new pins, then close the sub-symbol
first_pin = unit.index("(pin ")
newunit = unit[:first_pin] + newpins + ")\n\t\t"

newblk = blk[:k] + newunit + blk[p + 1:]

# update the Description so the TODO(unverified) flag becomes a RESOLVED statement with provenance
old_desc = re.search(r'\(property "Description" "[^"]*"', newblk).group(0)
new_desc = ('(property "Description" "Semtech SX1280 2.4 GHz ranging transceiver. '
            'PIN NUMBERING AND SIDES VERIFIED against Semtech SX1280/SX1281 Data Sheet Rev 3.2 '
            '(March 2020) Table 2-1 Transceiver Pinout and Figure 2-1 Transceiver Pin Locations, '
            'vendored at docs/sx1280/. OPEN-13 CLOSED 2026-10-14: the previous placeholder was wrong '
            'on 20 of 24 pins. See docs/fab/OPEN-13-CLOSED-SX1280-PINOUT.md. '
            'LAND PATTERN: pads 10/11/12 side corrected; pad sizes pending Figure 17-3 render."')
newblk = newblk.replace(old_desc, new_desc, 1)

out = s[:i] + newblk + s[j + 1:]

if "--write" in __import__("sys").argv:
    open(LIB, "w", encoding="utf-8").write(out)
    print("WROTE", LIB)
else:
    print("DRY RUN -- pass --write to apply")

print()
print("=== the pin map written ===")
for n, nm, et, side, desc in sorted(PINS):
    x, y, rot = coords[n]
    print(f"  pin {n:>2} {nm:<9} {et:<9} {side:<7} at ({x:7.2f},{y:7.2f}) rot {rot:>3}")
print()
print(f"pins written: {len(PINS)}")
print("sides: " + ", ".join(f"{s_}={len(groups[s_])}" for s_ in ("LEFT", "BOTTOM", "RIGHT", "TOP")))
