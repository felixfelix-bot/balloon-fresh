# `/SX1280_DIO1` fan-out — DIAGNOSIS and the measured resolution

**Date:** 2026-10-14 · **Status:** diagnosed; resolution MEASURED and recommended as a decision.

## 0. Headline

The last unrouted net on the hub (`/SX1280_DIO1`) **routes completely at
0.15 mm track / 0.125 mm clearance** — **48/48 nets, 0 escalations, 0 failures** — and
the delivered geometry is **entirely inside JLCPCB's real capability**:

| | delivered | JLCPCB floor | verdict |
|---|---:|---:|---|
| min track width | **0.150 mm** | 0.10 mm | **legal** |
| min via diameter | **0.450 mm** | 0.45 mm | **legal (exactly at floor)** |
| min via drill | **0.250 mm** | 0.20 mm | **legal** |

**The frozen ruleset (0.20/0.20 track/clearance) cannot fan out this QFN. JLCPCB can.**
That is the whole finding.

## 1. Why the frozen floor blocks it — the arithmetic

`U4` = SX1280, QFN-24 at (52.25, 27.25). Its lands are on a **0.50 mm pitch** with
**0.25 × 0.80 mm** pads:

```
adjacent land-edge gap = pitch - land width = 0.50 - 0.25 = 0.25 mm
```

At the **frozen** rules a track between two lands costs `track + 2 × clearance`:

| track | + 2 × clearance | total needed | fits the 0.25 mm gap? |
|---|---:|---:|---|
| 0.20 (frozen) @ 0.20 clr | +0.40 | **0.60** | **NO** |
| 0.15 @ 0.125 clr | +0.25 | **0.40** | **NO** |
| 0.10 (JLC) @ 0.10 (JLC) | +0.20 | **0.30** | **NO** |

**A track can never pass *between* these lands at any legal width** — so the escape must
route **outward** past the neighbouring pins, and that outward corridor is where the
other QFN escapes already live. The router's `boxed_in_static` verdict was therefore
**correct about the frozen geometry**, not a router failure.

## 2. The resolution I measured

Relaxing the *routing* constraints to **0.15 / 0.125 mm** (still **1.5× and 1.25×
JLCPCB's 0.10 / 0.10 floor**) lets the router complete the net:

```
route --track-width 0.15 --clearance 0.125 --via-size 0.45 --via-drill 0.25 --escalation off
  -> Single-ended 48/48 routed, Multi-point 69/69 pads, escalations 0, failed 0
  -> min delivered track 0.150 mm, via 0.450 mm, drill 0.250 mm
```

**All three are within JLCPCB's published capability**, so this board is
**manufacturable as routed.**

## 3. Why the DRC count then "explodes" — and why that is not a defect

Graded against the **frozen** ruleset, that same board reports **1420 violations**
(clearance 502, hole_clearance 203, track_width 199, via_diameter 171,
drill_out_of_range 171, …).

**Those are all the same statement:** *"you used 0.15 mm where the frozen file says
0.20."* The frozen ruleset is a **2× safety margin chosen by us** for power/ground and
general routing — a defensible choice, but **not a JLCPCB limit**. Applying a 2× margin
to a **0.50 mm-pitch QFN** is not conservative, it is **impossible**.

**So the 1420 number is an artifact of grading a JLC-legal board against our own stricter
baseline** — the mirror image of the earlier problem where a *stale* artifact made a
board look worse than it was. Both directions of drift are now recorded.

## 4. The DECISION this needs (scoped, like the edge rule)

Three options, in my recommended order:

1. **Adopt a scoped fan-out rule: 0.15 mm track / 0.125 mm clearance for the SX1280 QFN
   area only**, keeping **0.20/0.20 everywhere else.** Still 1.5× JLC's floor, still
   conservative, and it is the *same shape* as the approved wing-socket edge decision.
   **This is the engineering-correct answer, and it is measured to work.**
2. **Keep 0.20/0.20 and accept `/SX1280_DIO1` unrouted** — but first check in firmware
   whether `DIO1` is used at all. On the SX1280 it is an IRQ-capable output; if the
   design does not need it, the honest fix is a **declared no-connect**, not a dangling
   via.
3. **Move the pin plan** so SX1280 pin 10 carries nothing — a schematic change, most
   expensive.

**Refused, and worth saying plainly:** I did NOT narrow the router to 0.0889 mm to force
a "pass". That produces a board that satisfies a ruleset which already fails to describe
the design — the self-grading failure this campaign caught three times.

## 5. Reproduce

```
# the diagnosis
python3 -c "
import pcbnew,sys; sys.path.insert(0,'/usr/lib/python3/dist-packages')
b=pcbnew.LoadBoard('tracker/hardware/seed'); u4=b.FindFootprintByReference('U4')
print(sorted((pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetSize().x), p.GetNetname())
             for p in u4.Pads())[:12])
"

# the measured fix
cd /data/repos/KiCadRoutingTools
.venv/bin/python py_router/route.py <seed> /tmp/h_dio.kicad_pcb \
    --track-width 0.15 --clearance 0.125 --via-size 0.45 --via-drill 0.25 --escalation off
# then restore the frozen project/rules and DRC -- expect 1420 "violations", all of which
# say "0.15 mm where the frozen file says 0.20", i.e. our margin, not JLC's limit.
```
