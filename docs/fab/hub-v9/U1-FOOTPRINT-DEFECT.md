# U1 footprint — RETRACTION of the 2026-10-14 "defect" finding

**Date:** 2026-10-14 (retraction, same day) · **Status:** my earlier finding was WRONG.
**Supersedes:** the "U1 FOOTPRINT DEFECT" claim committed in `76f510b8`. That claim is
**withdrawn.** The file is replaced by this one; the commit message's claim stands only
as a record of a mistake that was caught and corrected.

---

## 0. Retraction, plainly

I reported: *"U1 has 62 pads but only 42 unique numbers; `pad 41` duplicated 13×; a
genuine footprint defect."*

**That was wrong.** `U1` is KiCad's **official** `RF_Module:ESP32-S3-WROOM-1U`
footprint, and both anomalies are **deliberate and correct**.

## 1. What the pads actually are

**The 13 pads numbered `41` are THERMAL/HEATSINK vias**, not duplicated signal pads:

- every one carries `(property pad_prop_heatsink)` and `(zone_connect 2)`
- **all 13 are at DISTINCT coordinates** — so my "if they are not co-located the
  footprint asserts a connection that does not exist" concern does not apply; they
  are a real 3×5 thermal grid
- they share the number **41** because **41 is the module's GND/thermal pad** — they
  are correctly ONE electrical node, stitched for thermal transfer

**The 9 unnamed pads are `0.9 × 0.9 mm` SMD pads interleaved with the vias** (same
3-column grid, offset 0.01 mm) — the standard KiCad idiom for **paste apertures** on a
thermal pad. Unnamed because they are not electrical pins.

## 2. The reasoning error (recorded, because it is the useful part)

I inferred **"62 pads / 42 numbers = broken"** from the **aggregate count alone**, and
published it as a defect **before inspecting what the pads were**. That is precisely
the failure mode I had been flagging in this campaign's artifacts all day — asserting
from a summary number instead of reading the artifact.

**The signal I should have weighted:** the footprint came from the installed KiCad
library at `/usr/share/kicad/footprints/RF_Module.pretty/`, not from this repo. An
official library footprint being broken is far less likely than my count-based test
being naive. **Check the provenance before publishing a defect against a dependency.**

## 3. What remains genuinely true (the real finding)

The 12 `drill_out_of_range` violations are **real**, but they are **not a footprint
defect** — they are a **rule-scope question**:

| | |
|---|---|
| Board setup | `min_through_hole_diameter = 0.3 mm` |
| Module thermal vias | **0.2 mm** (Espressif's own recommended land pattern) |
| JLCPCB mechanical floor | **0.20 mm** — so 0.2 mm **is manufacturable** |

So the **board's own rule is stricter than the fab requires** for this pad class. Two
legitimate resolutions, and this is an **operator call**:

- **(a)** set `min_through_hole_diameter = 0.2 mm` **with a recorded rationale** that
  the module's thermal vias are 0.2 mm by the vendor land pattern; or
- **(b)** keep 0.3 mm and carry **12 explicitly-waived** violations as a known delta.

**I do not recommend silently relaxing the floor** — that is the move refused earlier
in this campaign, and on a board whose point is a 2× JLCPCB margin, a relaxation must
be a *decision with a rationale*, not a side effect of chasing a zero.

## 4. Reproduce (the corrected audit)

```
python3 - <<'PY'
import re
from collections import Counter
p="/usr/share/kicad/footprints/RF_Module.pretty/ESP32-S3-WROOM-1U.kicad_mod"
txt=open(p).read()
blocks=re.findall(r'\(pad "([^"]*)" ([a-z_]+) [^\n]*\n(.*?)\n\t\)', txt, re.S)
c=Counter(n for n,*_ in blocks)
print("pads", len(blocks), "unique", len(c), "dupes", {n:k for n,k in c.items() if k>1})
for n,typ,body in blocks:
    if n=="41":
        print(re.search(r'\(at ([-\d.]+ [-\d.]+)\)', body).group(1),
              re.search(r'\(property (pad_prop_\w+)\)', body).group(1))
PY
```
Every `41` prints the same `pad_prop_heatsink`, at a distinct coordinate.

## 5. Effect on the remaining work

**Item (a) of the previous plan — "fix the U1 footprint" — is DELETED.** Nothing in
the repo needed fixing. The 12 violations move to the **rule-scope decision** in §3,
and the remaining work order becomes:

1. **decide §3(a) or §3(b)** (operator) → resolves `drill_out_of_range` 12
2. **silkscreen + copper-edge cleanup** → 143 silk + 68 edge of the 235
3. **`/SX1280_DIO1` fan-out by placement** → the last unrouted net
4. **4 GND pad-to-plane taps** where the safe stitcher refused a via for lack of room
