#!/usr/bin/env python3
"""PCB footprints (robust: pair Reference->next Value) + render board & schematic."""
import re, subprocess, sys
from pathlib import Path

HW = Path("~/worktrees/fab-record-v8i/tracker/hardware").expanduser()
PCB = HW / "output" / "v8i_krt_gnss.kicad_pcb"
SCH = HW / "schematics/flight_board/v_c3_flight.kicad_sch"
OUT = Path("~/reports/balloon-board-state").expanduser()

s = PCB.read_text(errors="replace")
refs = [(m.start(), m.group(1)) for m in re.finditer(r'\(property "Reference" "([^"]+)"', s)]
vals = [(m.start(), m.group(1)) for m in re.finditer(r'\(property "Value" "([^"]+)"', s)]
print(f"raw: {len(refs)} reference props, {len(vals)} value props")
pairs = []
for pos, r in refs:
    nxt = [v for p, v in vals if p > pos]
    pairs.append((r, nxt[0] if nxt else "?"))

def key(r):
    m = re.match(r'([A-Za-z]+)(\d+)', r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)

print(f"=== PCB footprints: {len(pairs)} ===")
for r, v in sorted(pairs, key=lambda x: key(x[0])):
    print(f"  {r:8s} {v}")

# group by value to answer "what radios are on it"
print("\n=== grouped by value ===")
import collections
g = collections.Counter(v for _, v in pairs)
for v, n in g.most_common():
    print(f"  {n}x  {v}")

# --- renders -----------------------------------------------------------------
print("\n=== renders ===")
bpdf, spdf = "/tmp/v8i_board.pdf", "/tmp/v8i_sch.pdf"
cmds = [
    ["kicad-cli", "pcb", "export", "pdf", "-o", bpdf,
     "--layers", "F.Cu,In1.Cu,In2.Cu,B.Cu,F.SilkS,Edge.Cuts",
     "--black-and-white", "no", str(PCB)],
    ["kicad-cli", "sch", "export", "pdf", "-o", spdf, str(SCH)],
]
for c in cmds:
    r = subprocess.run(c, capture_output=True, text=True)
    print(f"  {' '.join(c[:4])} -> rc={r.returncode} {r.stdout.strip()[:80]}{r.stderr.strip()[:120]}")

for pdf, tag in ((bpdf, "board"), (spdf, "sch")):
    if Path(pdf).exists():
        r = subprocess.run(["pdftoppm", "-png", "-r", "130", pdf, f"{OUT}/v8i-{tag}"],
                           capture_output=True, text=True)
        print(f"  pdftoppm {tag}: rc={r.returncode} {r.stderr.strip()[:100]}")
    else:
        print(f"  MISSING {pdf}")
print()
for p in sorted(OUT.glob("v8i-board*.png")) + sorted(OUT.glob("v8i-sch*.png")):
    print(f"  {p.name}  {p.stat().st_size} bytes")
