# ADR-140 — Placement is approved on legality, never on routability; that is the defect

> Numbered **140** on 2026-10-26. Next free after 139.

**Status:** **Accepted** — process change, effective immediately.
**Relates:** ADR-120 R3 (no routing before gate sign-off), AGENTS.md §24 (silk before routing),
ADR-139 (LoRa1280 site), `docs/analysis/LORA1280-ESCAPE-CORRIDOR-STUDY.md`
**Consultant:** `gpt-6-astra` (SERVED model recorded by `ask_astra.py`), 2026-10-26

---

## 1. The question the operator asked

After I placed the LoRa1280 site at the **worst of eight** orientations:

> "Was this mistake made for other parts as well? Could it be that the deterministic placement
> logic was wrong? Please look into this with the consultants and surface a recommendation."

## 2. What the audit found — it is not one bad part, and it is not a logic bug

**There is no deterministic placement logic to be wrong.** `build_hub_board_v10.py` takes
hand-approved literal constants ("GATE-LOG round 1, operator-approved"). An earlier solver,
`solve_v10_placement.py`, searched every 0.5 mm position × 4 rotations — with acceptance criteria
of **legality only**: no shorts, no courtyard collision, fits the outline. Crossings were never
scored, before or after.

Board-wide audit (`tracker/hardware/tmp_probes/audit_lane_crossings.py`), every footprint with
≥ 4 non-rail nets, normalised by n(n−1)/2:

| ref | nets | crossings | ratio |
|---|---|---|---|
| `U_LORA1280` | 9 | 23 | **0.64** |
| `U2` | 8 | 17 | **0.61** |
| `U_C` | 4 | 3 | 0.50 |
| `U3` | 8 | 10 | 0.36 |
| `U1` | 29 | 126 | 0.31 |
| `U5` | 4 | 1 | 0.17 |

mean 0.37 · worst 0.64

**So yes — the same defect exists on other parts.** `U2`, an LR2021 radio module already on the
board, scores 0.61, essentially the same as the new site.

## 3. A measurement I got wrong, recorded so it is not reused

The eight-orientation sweep counted crossings using **actual destination pads**; the board-wide
audit uses **net centroids**. Those are different quantities: the best orientation scored
**10** in the sweep and **23** in the audit. Astra caught this.

**Consequence: the audit is valid only for RANKING parts against each other. It must never be
compared with the sweep's numbers, and never used as an absolute threshold.** Centroid-based
figures distort any multi-terminal net.

## 4. The consultant's verdict (gpt-6-astra, verbatim opening)

> "The process defect is approving legality without evidence of routability — not failing to
> minimise crossings."

And on the metric:

> "Crossings are a legitimate secondary placement objective, not a routability test. They flag
> inconvenient pin ordering, especially between two facing pad banks. They ignore obstacles,
> escape geometry, available routing layers, vias, detours and return paths. … There is no
> universal '0.6 is acceptable' threshold."

## 5. Decisions

### D1 — A comparative placement report precedes human approval
Not a threshold, not an automatic optimiser. Before a placement is signed off, the approved
arrangement is shown **against the legal rotation/side alternatives**, with crossings and
connection lengths, and any dominated choice is flagged for explicit justification.
Human-approved constants are not exempt from engineering checks.

### D2 — Crossings enter the solver later, as a LOW-WEIGHT term
Only once the metric is made consistent (actual pads, not centroids) and validated. **Not** as a
new acceptance criterion, and not before.

### D3 — New blocking gate: ROUTE-COMPLETION TRIAL before placement sign-off
On **a copy of the real board**, all connections in the changed interface must be routed with
real clearances, usable layers and existing obstacles, with connectivity checked **by the PCB
tool itself** and no new DRC violations. For the LoRa1280 interface that means **9/9, not one
successful escape**.

A failed trial, or a trial that cannot run, means **"routability unproven — approval blocked"**.
It does **not** mean "placement impossible". This distinction is the one this session had
backwards for two turns.

Because the current router is itself suspect (0/9 at the best orientation), the trial may be run
with an independent router or by hand; the evidence required is copper, not the router's opinion.

#### D3 CLOSED — 2026-10-30, evidence from live copper

The LoRa1280 interface is **9/9 routed and the board carries no rule-breaking copper**. Evidence,
all measured on the merged board `tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb` at the
original design rules (0.20 clearance / 0.20 track / 0.50 via), nothing relaxed:

| check | result |
|---|---|
| unconnected items naming a **pad of `U_LORA1280`** | 3, all power/ground **plane joins** — none is an interface net |
| the 9 interface nets connected **at the module** | 9 / 9 |
| `clearance` | **0** |
| `shorting_items` | **0** |
| `solder_mask_bridge` | **0** |

Seven nets were routed by the rip-up router, two by the operator in the KiCad interactive router.
The trial therefore passed with **two different tools**, which is stronger evidence than D3 asked
for: a single router succeeding could have been luck, and this session already measured that this
repo's own router fails 0/9 on the very same board where both an independent router and a human
succeed.

Two measurement traps this closure had to survive, both recorded because they produced confident
wrong answers first:

1. **A net-name match is not a connectivity test.** `/SPI1_SCK`, `/SPI1_MOSI` and `/SPI1_MISO` also
   run to `U3` and `U_C`, which are unrouted, so their names appear in the unconnected list while
   the module end is perfect. The test that holds is whether an unconnected item names a **pad uuid
   belonging to `U_LORA1280`**.
2. **A stale zone pour invents violations.** The operator's first saved board read 136 violations
   with 46 clearance; the second read 77 with 3. Refilling zones first gave 79 and 74 respectively —
   in both cases the real count was unchanged and the "new" violations were the old GND pour sitting
   where new tracks now run. Refill before DRC, always.

D3 closes the **placement** gate. It does not make the board orderable: 40 violations remain from
other classes (16 `copper_edge_clearance`, 19 `lib_footprint_*`, 3 silk, 2 starved thermal) and 86
items remain unconnected elsewhere on the hub.

### D4 — `U2` is NOT moved on the strength of its score
> "Do not move U2 merely because it scores 0.61. If it is completely routed, DRC-clean and
> electrically sound, actual copper beats the proxy. If partially routed, judge the remaining
> connections — not the ratio."

Action: check its **remaining unrouted connections**, not its crossing ratio. If its copper is
complete and clean, leave it alone and record that the score is a known, accepted property.

## 6. Why this is the right gate and not "optimise harder"

The project's real risk is shipping a board that cannot be routed. A crossing report improves
decisions; **verified copper is the release evidence**. D3 produces exactly that evidence and
D1 makes the choice visible. Neither requires the metric to be perfect, which matters because
§3 shows it is not.

## 7. Consequences

- ADR-120 R3's "no routing before gate sign-off" is **narrowed**: a *trial* route on a copy is now
  required evidence for the gate, not a violation of it. The real board still receives no routing
  before sign-off.
- Any placement change in this repo now owes a 9/9 (or N/N) trial result, not a legality argument.
- The audit probe is retained in `tmp_probes/` with its centroid caveat in the docstring.

## 8. Reproduce

```bash
# eight-orientation sweep (actual destination pads)
/usr/bin/python3 tracker/hardware/tmp_probes/scan_lora1280_orientation.py

# board-wide ranking (CENTROIDS — ranking only, never an absolute)
/usr/bin/python3 tracker/hardware/tmp_probes/audit_lane_crossings.py
```

## 9. For future sessions

**The one-line rule:** *a placement is approved when a trial route on a copy completes 100 % of
the changed interface with tool-verified connectivity — never because it is merely legal.*
