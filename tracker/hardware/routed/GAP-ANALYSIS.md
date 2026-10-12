# Gap analysis — placement validation before routing (2026-10-09)

Question asked: *"Are you using geometric tools to place the parts in a reasonable
manner before you try to route them? There needs to be zero overlap between parts
before you start routing. Some clearance between pads and parts is important."*

**Short answer: overlap was genuinely zero, but the clearance claim was never verified,
and the placement gate was run *after* routing, not before. Two headline numbers in
`SCORECARD.md` were misattributed.**

## 1. What was actually verified — and when

The fleet has a deterministic placement gate:

```
pcb_zero_burn.py placement-gate board.kicad_pcb     # subcommand exists
```

**It was never run before routing.** It was run only during this analysis, on the
already-placed board. Result:

```
board            : in/hub_board_v1_placed.kicad_pcb
footprints       : 30   pads 93   traces 0   vias 0
pad-bbox overlaps (different footprints): 0  []
pad-bbox overlaps (SAME footprint):       20  (advisory)
courtyard check  : run via-audit/other tooling with POLYGON geometry —
                   bounding boxes false-positive on L-shaped courtyards
VERDICT          : PASS — placement can route
```

| question | answer | confidence |
|---|---|---|
| zero overlap between **parts**? | **YES — 0 cross-footprint pad-bbox overlaps** | verified |
| clearance between pads and parts? | **NOT VERIFIED** | see §2 |
| courtyards present and non-overlapping? | **UNVERIFIABLE — no courtyards exist** | see §2 |

## 2. The courtyard blind spot (the real gap)

**The board has 30 footprints and essentially no courtyard geometry:**

```
F.CrtYd occurrences: 1        B.CrtYd occurrences: 1       footprint blocks: 30
```

F.CrtYd is not even in the board's used-layer set. Therefore:

- KiCad's `courtyards_overlap` DRC **cannot fire** — not because placement is clean,
  but because there is nothing to check. **"Zero courtyard violations" is a FALSE CLEAN.**
- The gate's own help text says the courtyard check must be done elsewhere with
  **polygon** geometry (bboxes false-positive on L-shaped courtyards). **No such check
  was performed by anyone.**
- The board also has **no `rule_severities` block**, so KiCad defaults applied and the
  absence of a violation type carries no information about intent.

**So the user's second requirement — clearance between pads and parts — is exactly the
requirement that was never measured.** 30 `lib_footprint_issues` violations are consistent
with these being non-standard/hand-made footprints, which is also why courtyards are absent.

## 3. Per-class DRC, before vs after (the numbers that matter)

| class | baseline | routed | delta | attribution |
|---|---|---|---|---|
| clearance | 66 | 3 | −63 | **zone refill**, not routing |
| hole_clearance | 54 | 0 | −54 | **zone refill**, not routing |
| starved_thermal | 2 | 0 | −2 | zone refill |
| **unconnected (ratsnest)** | **53** | **0** | **−53** | **genuine routing** |
| lib_footprint_issues | 30 | 30 | 0 | **x280 env artifact** |
| shorting_items | 10 | 10 | 0 | intra-footprint defect |
| solder_mask_bridge | 24 | 24 | 0 | intra-footprint defect |
| text_height / text_thickness | 25 / 18 | 25 / 18 | 0 | cosmetic |
| silk_over_copper / silk_overlap | 10 / 9 | 10 / 9 | 0 | cosmetic |
| **TOTAL** | **248** | **129** | **−119** | |

**Correction to `SCORECARD.md`:** the headline `clearance 66 -> 3 (−95 %)` was presented as
routing quality. It is mostly **the baseline board having unfilled zones** — the
`zone clearance 0.5000 mm; actual 0.0000 mm` class. The only unambiguous contribution of
the router is **`unconnected 53 -> 0`** (plus 18 vias). The `hole_clearance 54 -> 0` swing
was not reported at all.

**Cross-host comparability problem:** 30 of the 129 residual violations
(`lib_footprint_issues`) are *missing footprint library tables on x280*, not board
defects. The same board scored on cobrador would report ~99. **Any before/after on
different hosts must filter environment artifacts.**

## 4. What the residual blockers actually are

- **10 `shorting_items`** — every one is **adjacent pins inside a single module
  footprint** (`3V3/GND`, `SPI0_SCK/SPI0_MOSI`, `LR2021_BUSY/LR2021_DIO9`, …), not
  two parts overlapping. **This is a footprint pad-pitch defect.** No placement or
  routing algorithm can fix it; it needs a corrected footprint or a netclass exception.
- **24 `solder_mask_bridge`** — same intra-footprint cause, 12 front / 12 rear.
- **3 residual `clearance`** — genuine, small.
- **30 `lib_footprint_issues`** — environment, fix by installing footprint libs.

**Consequence: the board cannot be made fab-ready by routing.** 34 of the residual
violations are upstream of routing entirely. They are inherited from the footprint set.

## 5. Gaps in the method, in priority order

1. **No placement gate before routing.** The gate exists and takes one command. Running
   it first is a process fix, not a tooling fix.
2. **Courtyard coverage is unverified and the gate does not implement it** (needs polygon
   geometry, not bbox). Either add courtyards to the footprints or implement the polygon
   check — right now the requirement is silently unchecked.
3. **Footprint integrity is not checked at all.** Pad-to-pad pitch vs the netclass
   clearance rule is precisely what produced the 10 shorts and 24 mask bridges. Nothing
   in the pipeline tests it.
4. **Aggregate totals were reported without per-class attribution**, which let a
   zone-refill artifact read as router quality.
5. **DRC run on a host lacking footprint libraries** injects 30 phantom violations into
   the scorecard.
6. **Cosmetic violations (53) were not separated from fab-blocking ones (34)** in the
   first report.

## 6. Corrected order of operations

```
1. footprint integrity  : pad pitch vs netclass clearance, and courtyard PRESENCE
2. courtyard overlap    : polygon check (not bbox)
3. placement gate       : cross-footprint pad-bbox overlaps == 0
4. route                : KRT (deterministic, $0)
5. refill zones         : explicit, not implicit
6. DRC per class        : on a host with libs installed; filter env artifacts
7. scorecard            : attribute every delta to a cause
```

## 7. Verdict — does the approach make sense?

**The zero-LLM doctrine holds and is confirmed:** `unconnected 53 -> 0` at $0.00 inference,
no quota, no worker, no 503. Routing needs no spatial reasoning.

**But the method has a real blind spot: it treats the board as given.** Placement and
footprint correctness are upstream inputs it never validates, so upstream defects are
inherited and then misattributed to the router. The correct reading of the first result is
not *"routing halved the violations"* but **"the baseline had unfilled zones, the router
closed the ratsnest, and a footprint defect caps the board below fab-ready regardless of
routing."**

**Next actions, cheapest first:**
1. Run `placement-gate` **before** every route (one command, already built).
2. Add courtyards to the 30 footprints (or implement the polygon check) — currently the
   second half of the user requirement is unmeasured.
3. Fix the intra-footprint pad pitch that causes the 10 shorts + 24 mask bridges.
4. Install footprint libraries on x280 so DRC scores are comparable across hosts.
