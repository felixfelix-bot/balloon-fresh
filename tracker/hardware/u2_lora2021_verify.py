#!/usr/bin/env python3.14
"""Verification evidence for card t_f48320db: U2 = NiceRF LoRa2021 18-pin.

Produces the card's step-7 evidence, read from the FINAL board on disk:
  A. U2 footprint identity  (pad count / pitch / row span / net map)
  B. no RFM9xW geometry survives anywhere on the board
  C. RF_OUT trace width and the U2.pad9 -> ANT1.pad1 path
  D. computed microstrip Z0 for the before/after widths (JLCPCB 4-layer stackup)
Exit 0 only when every assertion holds.
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else "output/v8h_krt_u2_lora2021.kicad_pcb"
MM = 1_000_000
mm = lambda v: v / MM  # noqa: E731

PLAN_NETS = {
    "1": "+3V3", "2": "GND", "3": "SPI_MISO", "4": "SPI_MOSI", "5": "SPI_SCK",
    "6": "SPI_NSS", "7": "LR_BUSY", "8": "GND", "9": "RF_OUT", "11": "GND",
    "12": "GND", "14": "LR_RST", "15": "LR_IRQ", "18": "GND",
}
UNCONNECTED = ("10", "13", "16", "17")

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        fails.append(msg)


b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}")

# ---------------------------------------------------------------- A. U2 ----
print("\nA. U2 footprint identity")
u2 = [f for f in b.GetFootprints() if f.GetReference() == "U2"]
check(len(u2) == 1, f"exactly one U2 on the board (found {len(u2)})")
u2 = u2[0]
fpid = u2.GetFPID().GetLibItemName()
print(f"     U2 = '{fpid}'  value='{u2.GetValue()}'  rot={u2.GetOrientationDegrees():g} deg  "
      f"at ({mm(u2.GetPosition().x):.3f},{mm(u2.GetPosition().y):.3f})")
check(fpid == "LoRa2021_Castellated", "U2 lib id is LoRa2021_Castellated")

pads = list(u2.Pads())
check(len(pads) == 18, f"U2 pad count 18 (found {len(pads)})")

# pad geometry: two columns, 1.29 mm pitch, 19.81 mm apart
pos = sorted(((p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y),
               mm(p.GetSize().x), mm(p.GetSize().y)) for p in pads),
             key=lambda r: int(r[0]))
xs = sorted({round(r[1], 3) for r in pos})
rowspan = max(xs) - min(xs) if len(xs) == 2 else -1
print(f"     pad columns at x = {xs}  (row span {rowspan:.3f} mm)")
check(len(xs) == 2 and abs(rowspan - 19.81) < 0.02, "two pad rows 19.81 mm apart")
check(all(abs(r[3] - 2.0) < 0.01 and abs(r[4] - 0.7) < 0.01 for r in pos),
      "every pad is 2.0 x 0.7 mm")

for x in xs:
    col = sorted([r[2] for r in pos if round(r[1], 3) == x])
    gaps = [round(col[i + 1] - col[i], 4) for i in range(len(col) - 1)]
    ok = len(col) == 9 and all(abs(g - 1.29) < 0.01 for g in gaps)
    check(ok, f"column x={x}: 9 pads at 1.29 mm pitch (measured {set(gaps)})")

# net map
print("     pad -> net:")
bad = []
for num, x, y, sx, sy in pos:
    want = PLAN_NETS.get(num, "")
    got = b.FindFootprintByReference("U2").FindPadByNumber(num).GetNetname()
    mark = "ok" if got == want else "MISMATCH"
    if got != want:
        bad.append(num)
    print(f"       pad {num:>3s} -> {got or '(no net)':10s} (plan {want or '(none)':10s}) {mark}")
check(not bad, "all 18 pads match the plan-of-record net table")
check(all(b.FindFootprintByReference("U2").FindPadByNumber(n).GetNetname() == ""
          for n in UNCONNECTED),
      f"pads {UNCONNECTED} deliberately unconnected")

# ------------------------------------------------- B. no RFM9xW geometry ---
print("\nB. no RFM9xW geometry survives")
sig = []
for f in b.GetFootprints():
    fid = str(f.GetFPID().GetLibItemName())
    if "RFM9" in fid.upper() or "HOPERF" in fid.upper():
        sig.append(f"footprint {f.GetReference()}={fid}")
    for p in f.Pads():
        pn = p.GetNumber().upper()
        if pn in ("NSS", "RST", "BUSY", "DIO0"):
            sig.append(f"pad name {f.GetReference()}.{pn}")
netnames = {ni.GetNetname() for _c, ni in b.GetNetInfo().NetsByNetcode().items()}
for stale in ("LR_DIO0",):
    if stale in netnames:
        sig.append(f"net {stale}")
check(not sig, f"no RFM9xW signature on the board ({sig if sig else 'clean'})")
print(f"     board has {len(list(b.GetFootprints()))} footprints; "
      f"net named LR_IRQ present: {'LR_IRQ' in netnames}")

# ---------------------------------------------------------------- C. RF -----
print("\nC. RF_OUT path")
rf = [t for t in b.GetTracks() if t.GetNetname() == "RF_OUT"
      and t.Type() == pcbnew.PCB_TRACE_T]
widths = sorted({round(mm(t.GetWidth()), 4) for t in rf})
total = sum(math.hypot(mm(t.GetEnd().x - t.GetStart().x),
                       mm(t.GetEnd().y - t.GetStart().y)) for t in rf)
print(f"     {len(rf)} RF_OUT segments, total {total:.3f} mm, widths {widths} mm, "
      f"layers {sorted({b.GetLayerName(t.GetLayer()) for t in rf})}")
check(widths == [0.39], "all RF_OUT segments are 0.39 mm wide")
check(all(t.GetLayer() == pcbnew.F_Cu for t in rf), "RF_OUT is on F.Cu")

ant = [f for f in b.GetFootprints() if f.GetReference() == "ANT1"]
if ant:
    p1 = ant[0].FindPadByNumber("1")
    p9 = u2.FindPadByNumber("9")
    d = math.hypot(mm(p1.GetPosition().x - p9.GetPosition().x),
                   mm(p1.GetPosition().y - p9.GetPosition().y))
    print(f"     U2.9 {p9.GetNetname()} <-> ANT1.1 {p1.GetNetname()}  pad separation {d:.3f} mm")
    check(p1.GetNetname() == "RF_OUT", "ANT1.1 is on RF_OUT")

# ---------------------------------------------------------------- D. Z0 -----
print("\nD. microstrip Z0 (JLCPCB 4-layer, h=0.21 mm, Er=4.4, t=0.035 mm Cu)")


def z0(w, h=0.21, er=4.4, t=0.035):
    u = w / h
    if u <= 1:
        ee = (er + 1) / 2 + (er - 1) / 2 * (1 / math.sqrt(1 + 12 / u) + 0.04 * (1 - u) ** 2)
        z = 60 / math.sqrt(ee) * math.log(8 * h / w + w / (4 * h))
    else:
        ee = (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 / u)
        z = 120 * math.pi / (math.sqrt(ee) * (u + 1.393 + 0.667 * math.log(u + 1.444)))
    # first-order thickness correction
    return z - z * (t / h) * 0.28, ee


for w in (0.20, 0.34, 0.39):
    z, ee = z0(w)
    print(f"     w={w:.2f} mm -> Z0 ~ {z:5.1f} ohm (Eeff {ee:.2f})")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED"))
sys.exit(1 if fails else 0)
