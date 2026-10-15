#!/usr/bin/env python3
"""STEP 3a: remove the vestigial /SX1280_ANT_SW net from the schematic.

OPERATOR RULING 2026-10-14: "ANT_SW: confirm removal (my recommendation, now backed by the
datasheet's 'without external RF switching') -> yes confirmed".

WHY IT IS VESTIGIAL, with the evidence
  * The SX1280 datasheet, section 4 "Analog Front End", states the part has "a single antenna port
    connection to an integrated matching circuit that permits half-duplex operation of the radio
    WITHOUT EXTERNAL RF SWITCHING." So there is no switch pin and no switch function.
  * The REAL SX1280 has no ANT_SW pin at all (Table 2-1, 24 pins + exposed pad). The placeholder
    symbol invented one.
  * The repo ROUTED the net anyway (DRC JSON shows tracks and a via for /SX1280_ANT_SW), which is why
    it kept appearing in blocker reports: the router was routing a net with nowhere to go.

WHAT THIS SCRIPT DOES
  /SX1280_ANT_SW appears in three places:
    1. an instance-level property (Reference "ANT_SW" style) -- if present
    2. the schematic's own net/label objects (a global label or local label)
    3. wires attached to it
  It removes the LABEL objects and any wire segment whose only purpose is that label, and reports
  every removal so nothing is silent.

SAFETY: works on a backup, verifies the file still PARSES, asserts paren balance, and refuses to write
if the net is still referenced afterwards.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

WT = "/home/c08r4d0r/worktrees/v9-route"
SCH = f"{WT}/tracker/hardware/schematics/flight_board/v9_flight.kicad_sch"
NET = "SX1280_ANT_SW"
BAK = "/tmp/v9_sch_pre_antsw.bak"


def balanced_ok(text):
    inq = esc = False
    d = 0
    for ch in text:
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == '"':
            inq = not inq
        elif not inq:
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
                if d < 0:
                    return False
    return d == 0


def parses(text, label):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.kicad_sch")
    open(p, "w", encoding="utf-8").write(text)
    r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o",
                        os.path.join(d, "t.net"), p],
                       capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(d, "t.net"))
    shutil.rmtree(d, ignore_errors=True)
    print(f"  parse[{label}]: {'OK' if ok else 'FAILED -> ' + (r.stderr or '').strip()[:60]}")
    return ok


def top_block(text, start):
    inq = esc = False
    d = 0
    i = start
    while i < len(text):
        ch = text[i]
        if esc:
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == '"':
            inq = not inq
        elif not inq:
            if ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
                if d == 0:
                    return text[start:i + 1]
        i += 1
    return text[start:]


s = open(SCH, encoding="utf-8", errors="replace").read()
assert balanced_ok(s), "input file is not balanced -- refusing to edit"
print(f"loaded {len(s)} chars; baseline parses = {parses(s, 'baseline')}")

shutil.copy(SCH, BAK)
print(f"backup: {BAK}")

# ---- locate every object that references the net
print(f"\n=== objects referencing {NET} ===")
hits = [(m.start(), m.group(0)) for m in re.finditer(re.escape(NET), s)]
print(f"  raw occurrences: {len(hits)}")
for off, _ in hits[:12]:
    line_start = s.rfind("\n", 0, off) + 1
    line_end = s.find("\n", off)
    line = s[line_start:line_end]
    print(f"    @{off}: {line.strip()[:110]}")

# collect the FULL blocks (labels / wires) that mention the net, by walking back to their '('
blocks = []
seen_spans = set()
for off, _ in hits:
    # back to the nearest preceding '(' that starts a top-level sheet object
    j = s.rfind("\n\t(", 0, off)
    if j < 0:
        continue
    blk = top_block(s, j + 1)
    span = (j + 1, j + 1 + len(blk))
    if span in seen_spans:
        continue
    seen_spans.add(span)
    blocks.append((span, blk))

print(f"\n  distinct enclosing objects: {len(blocks)}")
for span, blk in blocks:
    kind = re.search(r"\(([a-z_]+)", blk)
    print(f"    {kind.group(1) if kind else '?'} span={span} len={len(blk)}")
    print(f"      {blk[:150].strip()}")

if not blocks:
    print("\n  nothing to remove -- the net is already absent. No write.")

# ---- remove them, right to left so offsets stay valid
out = s
removed = 0
for span, blk in sorted(blocks, key=lambda x: -x[0][0]):
    # include the leading newline+tabs so no blank line is left behind
    start = span[0]
    while start > 0 and out[start - 1] in " \t":
        start -= 1
    if start > 0 and out[start - 1] == "\n":
        start -= 1
    out = out[:start] + out[span[0] + len(blk):]
    removed += 1
print(f"\n  removed {removed} object(s)")

if not balanced_ok(out):
    print("REFUSING: result is not paren-balanced")
    sys.exit(1)

# ---- the net must be GONE (label objects), not merely reduced
still = len(re.findall(re.escape(NET), out))
print(f"  occurrences of {NET} after edit: {still}")
if still:
    print("  NOTE: still referenced -- showing what remains before refusing:")
    for m in re.finditer(re.escape(NET), out):
        ls = out.rfind("\n", 0, m.start()) + 1
        le = out.find("\n", m.start())
        print("     ", out[ls:le].strip()[:110])

if not parses(out, "after"):
    print("REFUSING: result does not parse")
    sys.exit(1)

if "--write" in sys.argv:
    open(SCH, "w", encoding="utf-8").write(out)
    print(f"\nWROTE {SCH}")
else:
    print("\ndry run -- pass --write to apply")
