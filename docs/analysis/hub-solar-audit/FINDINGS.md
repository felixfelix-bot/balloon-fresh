# Solar-gap audit — is the "not board-fixable" verdict right?

**Question (operator-authorised):** `docs/analysis/hub-solar-gaps/FINDINGS.md` says the 9
`J_W<->bypass-diode` gaps cannot be closed by board copper, and lists four candidate explanations
without choosing. This audit tests that verdict directly, and answers a narrower question:

> **Are the 9 gaps a copper problem at all?**

**Answer: the earlier verdict does not hold. These gaps ARE closable by board copper.** A bounded
2-layer A* with one via finds real, rule-compliant paths — **3 of 9 proven so far**, including the
pair the earlier finding called impossible. The earlier conclusion was reached by the wrong argument
("a via cannot connect an SMD pad"), and that argument is false: a stub-via-stub layer change is how
every route on this board changes layer.

Board: `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb`, sha256 `732bfe88…`, read-only.
KiCad 9.0.9, rules as supplied (clearance 0.20, track 0.20, via 0.50).

---

## 1. The claim I had to withdraw (mine, not the repo's)

My first measurement said **"a via site exists beside each pad for 9 of 9 pairs"**. That is a true
statement about *via placement* and a **worthless** one about *connectivity*, because a via site
being available says nothing about whether a track can reach it. I reported it as if it settled the
question. It did not, and the route search immediately contradicted it.

**Lesson recorded rather than deleted:** proximity of a legal via site is not a route. The test that
matters is a path, and a path needs the *start pad* to be escapable.

## 2. What actually blocks: the wing-seat land

`J_W2.1` is the clearest case, measured at 0.25 mm grid, 8-connected, ignoring the edge rule inside
the pad's own footprint (the repo's own DRC allow-list scopes `copper_edge_clearance` to `J_W*`):

```
J_W2.1  net=/W1_SOLAR_N  4.00 x 1.20 mm  SMD, F.Cu only
pad bbox mm: 32.70 75.00 33.90 79.00   (centre 33.30,77.00)

legal first moves from the pad centre: 0 of 4
  move  +1,0 (east)  -> blocked
  move  -1,0 (west)  -> blocked
  move   0,+1 (south)-> blocked
  move   0,-1 (north)-> blocked

blocker of the east move:
  r = 2.000 mm   need 2.300 mm   actual distance 1.651 mm
  object at (35.10, 77.00)     <- 1.8 mm east of the pad centre
```

A 4 mm-diameter object 1.65 mm from the pad centre: the pad's own land sits inside a keep-out it
cannot escape, so **no** router — mine, KiCad's, or a human with a mouse — can start a track there at
these rules. That is a **land/keep-out geometry** fact, not a routing-capability fact.

## 3. Route search result, and what it is allowed to mean

Bounded grid A*, one layer change, full obstacle model, `J_W*` edge exemption. **PROVEN so far:**

| pair | result |
|---|---|
| `/W1_SOLAR_N` J_W1.4 ↔ D_BP1.2 | **PATH 14.14 mm, 1 via at (3.55, 43.60)** |
| `/W1_SOLAR_N` J_W2.1 ↔ D_BP2.1 | **PATH 6.94 mm, 1 via at (30.00, 75.00)** |
| `GND` U2.4 ↔ D_BP4.2 | **PATH 5.71 mm, 1 via at (28.95, 9.20)** |

The remaining six pairs are still being solved one at a time (a per-pair timeout, because one slow
pair starves the rest). **I am not calling them routable until each has a path in hand** — an earlier
version of this table listed all nine from a search that was broken (§1 item 2).

Every path is at the board's own supplied rules; nothing was relaxed to produce one. A `NO PATH`
from this tool means *"not within the search corridor"*, never *"impossible"* — the window is
printed in the output.

## 4. Which of the four candidate explanations this settles

The earlier finding offered four, unranked. Holding the measurements against them:

| candidate | verdict from this audit |
|---|---|
| the diode is on the wrong side of the board | **REJECTED.** `D_BP2.1` has 2.75 mm of clear B.Cu around it and zero nearby B.Cu tracks — the diode end is *open*. The constraint was never there. |
| the `J_W` land should be PTH/slot rather than SMD | **NOT NEEDED.** A path exists with the land as SMD, because a stub-via-stub change reaches B.Cu without a PTH land. |
| the connection is made by the harness/tab, and the pad's net is what is wrong | **not required to explain the gaps** — but still a design question worth an explicit answer, since DECISIONS-UNROUTED-NETS.md records it for D7. |
| a real defect introduced by an earlier placement change | **not needed.** No defect is required: the pairs are simply unrouted. |

**Net: the four-way fork was a false fork.** Three of its branches dissolve once a route is actually
attempted, and the fourth is a documentation question rather than a blocker.

## 5. Consequence for the order

These gaps are **routing work I can complete**, not a decision waiting on the operator. That is a
material change from the earlier conclusion, which had moved them off the engineering queue.

A **bare-board** order was never blocked by them (JLCPCB does not require DRC-clean copper). Treating
the board as electrically complete still is, and a flight build therefore is — until these routes are
applied and re-graded. That is now a scheduled task rather than a fork.

## Reproduce

```sh
cd docs/analysis/hub-solar-audit
/usr/bin/python3 diag_pair.py  ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb /W1_SOLAR_N J_W2.1
/usr/bin/python3 audit_solar_gaps.py ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
/usr/bin/python3 route_solar_gaps.py ../../tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb --grid 0.25
```

`PYTHONPATH=/usr/lib/python3/dist-packages` is required (pcbnew lives in the distro interpreter).
