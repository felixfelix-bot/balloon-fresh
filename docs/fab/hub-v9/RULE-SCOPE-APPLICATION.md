# RULE-SCOPE APPLICATION — CORRECTED TWICE. The real breakdown of the 68 edge items.

**Date:** 2026-10-14 · **Status:** Decision 2 applied ✅; Decision 1 **correctly diagnosed
but NOT fully applicable as written** — and one sub-class is a **real defect**. Operator input needed.

This file supersedes my two earlier claims, both of which were wrong. Recording the whole
sequence because the method matters.

---

## 1. Decision 2 — `min_through_hole_diameter` 0.3 → 0.2 mm: **APPLIED, measured** ✅

Recorded in `hub_board_v9.kicad_pro` **with the rationale in the file**.

**`drill_out_of_range`: 12 → 0.** All 12 were `PTH pad 41 of U1` — the ESP32-S3's
thermal/heatsink vias, **0.2 mm** in Espressif's own land pattern, equal to **JLCPCB's
mechanical drill floor**. The board's 0.3 mm was **stricter than the fab requires** for this
pad class. The S1 frozen via/hole floors are **unchanged** (see §4).

## 2. Decision 1 — three wrong turns, and what is actually true

### Wrong turn 1: "the carrier is wrong"
I claimed this KiCad's CLI **doesn't read** a sidecar `.kicad_dru`. **FALSE.**

**Decisive experiment** (`/tmp/drutest`, `/home/c08r4d0r/dru_test.sh`), a *global* rule
setting `edge_clearance` to 0.05 mm: **`copper_edge_clearance` 68 → 16.**

**So `kicad-cli` DOES read the `.kicad_dru` and DOES honour a custom `edge_clearance`
constraint.** The carrier was never the problem — **my scope expression was.**

### Wrong turn 2: I destroyed the frozen rule file
My first `apply_rule_scopes.py` **overwrote the whole** `jlcpcb-s1-frozen.kicad_dru`
(2542 → 1580 bytes), deleting the S1 frozen rule set whose **sha256 the campaign depends on
for comparability.** **Restored from git**, and the script now **APPENDS only**
(`git diff --stat` = **22 insertions, 0 deletions**). Verified with `grep -c 'S1 frozen'` = 5.

### Wrong turn 3: I treated a real defect as an exemption
With the scoped rule in place the tracks still fired, and the violation text named **my own
new rule**: `rule 'edge_clearance_default' clearance 0.5000 mm; actual 0.2182 mm`.

**Measured, via `measure_edge_tracks.py`: tracks run at `x = 0.50` with the board edge at
`x = −0.07`** — and the real violations are:

| item | actual | required |
|---|---:|---:|
| `Track [+3V3] on In2.Cu` | **0.218 mm** | 0.500 mm |
| `Track [+3V3] on In2.Cu` | **0.250 mm** | 0.500 mm |
| `Track [/F33_VCC] on F.Cu` | **0.400 mm** | 0.500 mm |
| `Track [/GNSS_VCC]`, `[/W1_SOLAR_N]` | — | 0.500 mm |

**These are REAL manufacturing risks — router tracks routed along the board edge inside the
keepout. They are NOT the ADR-046/048 wing interface and must NOT be waved through.**

## 3. The true structure of the 68 items

| sub-class | count | what it is | correct handling |
|---|---:|---|---|
| **A. Copper tracks near the edge** | **26** | `+3V3` @0.218, `F33_VCC` @0.400, `GNSS_VCC`, `W1_SOLAR_N` | **REAL DEFECT — fix by re-route, do NOT exempt** |
| **B. Outline measured against itself** | **31** | `Rectangle on Edge.Cuts` | **rule-applicability artifact** — not copper; the default rule should not apply |
| **C. Wing-socket Edge.Cuts segments** | **26** | `Segment of J_W1..J_W4 on Edge.Cuts` | **by design** (ADR-046/048) — but the segments are *drawings*, so a copper condition cannot reach them |
| **D. Wing-socket pads/vias** | **~11** | `Pad of J_W3`, `Via [GND]`, `Via [/CUT_SENSE_W*]` | **by design**; these ARE reachable by a copper scope |

**Measured outcome of the Pad/Reference scope alone: `copper_edge_clearance` 68 → 68** —
it changes nothing, because **classes B and C are Edge.Cuts graphics, not copper.**

## 4. What my current change does and does not do

**Does:** `drill_out_of_range` 12 → 0 (Decision 2, applied).
**Adds:** an **additive** wing-socket-land scope (reaches sub-class D only), with the S1
frozen rules **intact** and their comparability preserved.
**Does NOT:** resolve the 68 edge items — because 26 of them are real defects, 31 are a
rule-applicability artifact, and 26 are drawings the rule engine treats as geometry.

## 5. What I need from the operator

1. **Sub-class A (26 track items) — the real one.** These are power/signal tracks inside the
   0.5 mm edge keepout, worst case **0.218 mm**. **Fix by re-route** (the router should keep
   copper further from the edge) or **rule on whether 0.5 mm is the right board-setup
   value for this board** — JLCPCB's own copper-to-edge minimum is smaller, and 0.5 mm is a
   *board-setup default* rather than a recorded decision. **I am NOT exempting these.**
2. **Sub-class B (31 outline items)** — confirm you want the edge rule to stop applying to
   Edge.Cuts *graphics* (a rule-applicability fix), or accept them as a documented delta.
3. **Sub-class C (26 wing segments)** — these need either an item-type scope in the rule
   engine or a written waiver; the copper scope cannot reach a drawing segment.

## 6. The lesson, recorded plainly

**Three times this campaign I blamed an artifact when the fault was my own reasoning** — the
`U1` "footprint defect", the 300 km range claim, and now "the carrier is wrong". Each was
caught by a **measurement designed to falsify my claim**. The general guard:

> **When a tool "does not work", first test it with a case designed to SUCCEED.** The global
> 0.05 mm rule was that test, and it should have been the first thing I ran.

**And a second guard, learned here:** never *replace* a frozen artefact to add a scope —
**append**, and verify with `git diff --stat` that nothing was deleted.

## 7. Reproduce

```
bash /home/c08r4d0r/dru_test.sh          # 68 -> 16 proves the .kicad_dru IS honoured
cd tracker/hardware
python3 apply_rule_scopes.py             # additive scope; frozen rules intact
~/venvs/kicad/bin/python measure_edge_tracks.py fg_in_filled.kicad_pcb
git diff --stat tracker/hardware/jlcpcb-s1-frozen.kicad_dru   # 22 insertions, 0 deletions
```
