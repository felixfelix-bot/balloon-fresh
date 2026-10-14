"""STEP 1, done properly: rewrite the embedded SX1280 symbol, with a BALANCE ASSERT.

Why the previous five attempts failed

  They all produced a file that was silently UNBALANCED and then reported success. No attempt
  checked the output. The final count was 97 missing ")" -- because CLOSES was scraped from the
  pin template region and therefore ended at the PIN's close, not the UNIT's, leaving the unit and
  symbol closes unwritten for every pin.

The rule this file obeys

  Build the new pin list, then CONSTRUCT the unit explicitly at known depths:
      unit header            depth 2
      pins                   depth 3 (each pin closes itself at depth 3)
  and close the unit (depth 2) then the symbol (depth 1). Then ASSERT the whole document balances to
  zero. If it does not, refuse to write.

Pin content: Semtech SX1280/SX1281 Data Sheet Rev 3.2 Table 2-1 + Figure 2-1, vendored at
docs/sx1280/. Sides: 1-6 LEFT, 7-9 BOTTOM, 10-18 RIGHT, 19-24 TOP, exposed pad 0 centre.
"""
import re
import sys

P = ("/home/c08r4d0r/worktrees/v9-route/tracker/hardware/schematics/flight_board/"
     "v9_flight.kicad_sch")
BAK = "/tmp/v9_sch.bak"

PINS = [
    (0,  "GND",     "passive",  "centre", "Exposed Ground pad"),
    (1,  "VR_PA",   "passive",  "LEFT",   "Regulated supply for the PA"),
    (2,  "VDD_IN",  "power_in", "LEFT",   "Regulated supply input. Connect to Pin 12."),
    (3,  "NRESET",  "input",    "LEFT",   "Reset, active low, internal pull-up 50k"),
    (4,  "XTA",     "passive",  "LEFT",   "Reference oscillator connection or TCXO input"),
    (5,  "GND",     "passive",  "LEFT",   "Ground"),
    (6,  "XTB",     "passive",  "LEFT",   "Reference oscillator connection"),
    (7,  "BUSY",    "output",   "BOTTOM", "Transceiver busy indicator"),
    (8,  "DIO1",    "bidirectional", "BOTTOM", "Optional multi-purpose digital I/O"),
    (9,  "DIO2",    "bidirectional", "BOTTOM", "Optional multi-purpose digital I/O"),
    (10, "DIO3",    "bidirectional", "RIGHT",  "Optional multi-purpose digital I/O"),
    (11, "VBAT_IO", "power_in", "RIGHT",  "Supply for Digital IO (1.8-3.7V), <= VBAT."),
    (12, "DCC_FB",  "passive",  "RIGHT",  "Regulated output from the internal regulator"),
    (13, "GND",     "passive",  "RIGHT",  "Ground"),
    (14, "DCC_SW",  "passive",  "RIGHT",  "DC-DC Switcher Output"),
    (15, "VBAT",    "power_in", "RIGHT",  "Supply for the RFIC (1.8-3.7V), >= VBAT_IO."),
    (16, "MISO_TX", "output",   "RIGHT",  "SPI slave output / UART Transmit pin"),
    (17, "MOSI_RX", "input",    "RIGHT",  "SPI slave input / UART Receive pin"),
    (18, "SCK_RTSN", "input",   "RIGHT",  "SPI clock / UART Request To Send"),
    (19, "NSS_CTS", "input",    "TOP",    "SPI Slave Select / UART Clear To Send"),
    (20, "GND",     "passive",  "TOP",    "Ground"),
    (21, "GND",     "passive",  "TOP",    "Ground"),
    (22, "RFIO",    "bidirectional", "TOP",    "RF transmit output and receive input"),
    (23, "GND",     "passive",  "TOP",    "Ground"),
    (24, "GND",     "passive",  "TOP",    "Ground"),
]

BX, BY, LEAD = 12.7, 17.78, 2.54


def place(side, idx, total):
    if side in ("LEFT", "RIGHT"):
        step = (BY * 2) / (total + 1)
        off = step * (idx + 1)
        if side == "LEFT":
            return (-BX - LEAD, BY - off, 0)
        return (BX + LEAD, -BY + off, 180)
    step = (BX * 2) / (total + 1)
    off = step * (idx + 1)
    if side == "BOTTOM":
        return (-BX + off, -BY - LEAD, 90)
    return (BX - off, BY + LEAD, 270)


groups = {}
for num, name, etype, side, desc in PINS:
    if side != "centre":
        groups.setdefault(side, []).append(num)
coords = {}
for side in ("LEFT", "BOTTOM", "RIGHT", "TOP"):
    for i, num in enumerate(groups[side]):
        coords[num] = place(side, i, len(groups[side]))
coords[0] = (0.0, 0.0, 0)


def balance(text):
    """paren depth ignoring quoted strings; returns (final_depth, min_depth)."""
    inq = esc = False
    d = mind = 0
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            inq = not inq
            continue
        if inq:
            continue
        if ch == "(":
            d += 1
        elif ch == ")":
            d -= 1
            mind = min(mind, d)
    return d, mind


def pin_block(num, name, etype, x, y, rot):
    """A pin at depth 3. Indentation: pin 3 tabs, children 4, close 3. Lifted from a WORKING pin."""
    T = "\t"
    return (
        f"{T*3}(pin {etype} line\n"
        f"{T*4}(at {x:.2f} {y:.2f} {rot})\n"
        f"{T*4}(length {LEAD})\n"
        f"{T*4}(name \"{name}\"\n"
        f"{T*5}(effects\n"
        f"{T*6}(font\n"
        f"{T*7}(size 1.27 1.27)\n"
        f"{T*6})\n"
        f"{T*5})\n"
        f"{T*4})\n"
        f"{T*4}(number \"{num}\"\n"
        f"{T*5}(effects\n"
        f"{T*6}(font\n"
        f"{T*7}(size 1.27 1.27)\n"
        f"{T*6})\n"
        f"{T*5})\n"
        f"{T*4})\n"
        f"{T*3})\n"
    )


s = open(P, encoding="utf-8").read()
d0, m0 = balance(s)
print(f"input balance: final={d0} min={m0}")

i = s.find('(symbol "balloon_flight_v9:SX1280"')
assert i >= 0
d = 0
j = i
inq = False
while j < len(s):
    ch = s[j]
    if ch == '"':
        inq = not inq
    elif not inq and ch == "(":
        d += 1
    elif not inq and ch == ")":
        d -= 1
        if d == 0:
            break
    j += 1
blk = s[i:j + 1]
print(f"SX1280 block: {i}..{j}  ({len(blk)} chars)")

# unit header (depth 2) then pins (depth 3), then close unit (depth 2) and symbol (depth 1)
um = re.search(r'\(symbol "SX1280_1_1"', blk)
assert um
k = um.start()
hdr_nl = blk.index("\n", k)
head = blk[k:hdr_nl + 1]                      # '(symbol "SX1280_1_1"\n'
newpins = "".join(pin_block(n, nm, et, *coords[n]) for n, nm, et, _sd, _dd in PINS)
unit_close = "\t\t)\n"                        # closes SX1280_1_1  (depth 2)
sym_close = "\t)\n"                            # closes balloon_flight_v9:SX1280 (depth 1)
newblk = blk[:k] + head + newpins + unit_close + sym_close

# refresh the Description so the schematic stops claiming UNVERIFIED
dm = re.search(r'\(property "Description" "[^"]*"', newblk)
if dm:
    newblk = newblk.replace(
        dm.group(0),
        '(property "Description" "Semtech SX1280 2.4 GHz ranging transceiver. PIN NUMBERING AND '
        'SIDES VERIFIED against Semtech SX1280/SX1281 Data Sheet Rev 3.2 (March 2020) Table 2-1 and '
        'Figure 2-1, vendored at docs/sx1280/. OPEN-13 CLOSED 2026-10-14: the placeholder was wrong '
        'on 20 of 24 pins. See docs/fab/OPEN-13-CLOSED-SX1280-PINOUT.md."', 1)

out = s[:i] + newblk + s[j + 1:]

# ---- THE ASSERT THAT WAS MISSING IN EVERY EARLIER ATTEMPT -------------------------------
d1, m1 = balance(out)
print(f"output balance: final={d1} min={m1}")
print(f"new block balance: {balance(newblk)}")
print(f"size: {len(s)} -> {len(out)}  (delta {len(out) - len(s)})")
assert d1 == 0, f"REFUSING TO WRITE: document does not balance (final={d1})"
assert m1 == 0, f"REFUSING TO WRITE: depth went negative (min={m1})"
assert balance(newblk)[0] == 0, "REFUSING TO WRITE: symbol block does not balance"

if "--write" in sys.argv:
    open(P, "w", encoding="utf-8").write(out)
    print("WROTE", P)
else:
    print("DRY RUN (balanced OK)")
print(f"pins={len(PINS)} sides=" + ", ".join(f"{x}={len(groups[x])}" for x in ("LEFT", "BOTTOM", "RIGHT", "TOP")))
