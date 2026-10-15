# HANDOVER — fit the wing bypass Schottky + design the keeper/slip-fit release

**Date:** 2026-10-14 · **Prepared by:** balloon-hermes (manager CW) · **For:** the CW that owns
`tracker/hardware/` (hub + wing boards)
**Operator intent:** *"Ich möchte den keeper + slipfit und bypass schottky verbauen."*
**Status:** nothing ordered, nothing flashed. Hub is **not yet orderable** (see §5).

**Read first, in this order:** `docs/analysis/wing-release-electrical-contacts.md` (why these two
changes), `docs/analysis/wing-jettison.md` §5b (cross-ref), then this document.

---

## 0. The two asks, and where each one actually stands

| Ask | Real state | The work |
|---|---|---|
| **Bypass Schottky** | **Already designed, placed and routed** — `D_BP1..D_BP4`, `Diode_SMD:D_SMA`, value **SS24**, correct polarity, traces present | **Decide + build as DNP→fitted.** No layout work needed. Verify the order form/paste aperture actually fits the parts. |
| **Keeper + slip-fit** | **Design only** — "Option 4" in the new analysis; no mechanism, no part, no schematic | **Full mechanical + electrical design.** See §4. This is the real work. |

**Do not re-derive either.** The Schottky question is *already decided in-repo* (§1) and the
keeper concept is *already argued* (§4). Re-deriving them wastes a context window and risks
producing a third contradicting number — the defect class this repo documents.

---

## 1. The bypass Schottky — the part is decided, and it is NOT the BAT54

**This is the single most important paragraph in this handover.** Three documents disagree, and
the winner is the newest:

| Document | Says | Status |
|---|---|---|
| `docs/WING-TO-HUB-SOCKET-SPEC.md` §5 | *"BAT54 family, SOD-323 or SMA"* | **STALE** |
| `docs/adr/046-wing-board-interface.md` §2.3 | *"bypass Schottky per wing slot"*, no part | mandates the *provision* only |
| `docs/adr/048-v9-hub-wing-interfaces.md` §2.3 | *"`D_BP1..D_BP4` (BAT54 family, SOD-323)"* | **STALE on the part** |
| **`docs/adr/049-wing-architecture.md` clause 1** + `docs/adr/051` §2.7 + **`docs/adr/053` §1.3** + `docs/analysis/array-power-architecture.md` | **≥ 2 A / 40 V Schottky — SS24 or PMEG4020ER class — and SOD-323 is *excluded* because it cannot carry 2 A** | **CURRENT** |

**Why the BAT54 is wrong:** the BAT54 family is **200 mA / 30 V**. The v9 array is a **1.2 A**
string (0.4 A before the large cell was chosen). That is **6× under-rated**. The board already
reflects the corrected decision — the placed footprint is `D_SMA` with value **SS24**. So the
board and the current ADRs agree; only the two older wrapper documents still say BAT54.

**Action:** leave `SS24` alone. **Patch the two stale documents** (socket spec §5, ADR-048 §2.3)
to cite the ADR-049/053 re-rating, so the next reader does not "fix" the board back to a BAT54.
That is a doc change, not a layout change.

### 1.1 What is already on the board (measured, not assumed)

```
D_BP1 | SS24 | Diode_SMD:D_SMA | nets: W1_SOLAR_P , W1_SOLAR_N
D_BP2 | SS24 | Diode_SMD:D_SMA | nets: W1_SOLAR_N , W2_SOLAR_N
D_BP3 | SS24 | Diode_SMD:D_SMA | nets: W2_SOLAR_N , W3_SOLAR_N
D_BP4 | SS24 | Diode_SMD:D_SMA | nets: W3_SOLAR_N , GND
```

Two things to understand before touching this:

1. **Polarity is correct in all four.** The odd-looking net pairs are *not* an error: ADR-048 §2.3
   records that each series node carries **two** spec land names (e.g. the node between wing 1 and
   wing 2 is both `W1_SOLAR_N` and `W2_SOLAR_P`). So `W1_SOLAR_P↔W1_SOLAR_N` is wing 1's own
   node, `W1_SOLAR_N↔W2_SOLAR_N` is the 1|2 junction, and so on. **Cathode sits toward the more
   positive end of each pair — verified.**
2. **`D_BP4` bridges `W3_SOLAR_N` to `GND`,** which is the same node as `W4_SOLAR_N` per the
   stack (`stack_bot = W4.SOLAR_N → system GND`). Not a mistake.

### 1.2 The DNP question — do NOT use KiCad's `dnp` attribute

**Recommendation: fit all four now, and do not mark them DNP in the file.**

- All four footprints currently carry **no `attr` field at all** — not DNP, not `exclude_from_bom`.
  They are "provisioned" by convention, documented in prose only.
- The reason not to use KiCad's `(attr dnp)`: it is a **file-level** attribute and this repo has a
  **measured defect class** where a board file is edited and silently loses content (the wing board
  lost all 20 segments and 8 vias in `ce5082ac`; the hub outline drifted off the 103×103 SSOT
  anchor). Marking DNP is a *second* edit to a file already flagged in `t_273cbf1a`/`t_b6eb2562`.
- **If the operator wants them DNP in the file anyway,** do it as `exclude_from_bom` (populate at
  hand-solder), not `dnp` (which also blanks the part in 3D/DRC contexts and can confuse the
  placement gate).

### 1.3 Why fitting them is the highest-leverage change available

From `docs/analysis/array-power-architecture.md`: fitting it *"is the difference between 'one lost
wing kills the array' and 'one lost wing costs −1.6 dB of TX power and the mission continues'"* —
and at four diodes it is **the cheapest change in the analysis**. It also covers three distinct
failure modes with the same part (open/cracked cell, shading, and the release-induced open).

### 1.4 Rating check at flight conditions

The cold open-circuit stack is **≈9.58 V** (ADR-053 §1.3), so a **40 V** part clears at −60 °C with
≈4.2× margin. A **2 A** part against a **1.2 A** string is 1.7× — acceptable for a *transient*
bypass path, but **record the duty-cycle assumption** (a bypassed wing carries the full string
current continuously while shaded). If a wing can be shaded for hours, re-check the thermal case:
`TODO(unverified)` — SS24 thermal derating at −60 °C under continuous 1.2 A.

### 1.5 Order/assembly consequences

- `D_SMA` (DO-214AC) is a **hand-solderable** package — no paste aperture or stencil change needed
  if the hub is assembled by hand. If JLCPCB assembles it, **verify the SMA lands exist in the
  paste layer** before the order goes in.
- Add 4× SS24 (or PMEG4020ER) to the parts order. `TODO(unverified)` — the exact LCSC part number
  for SS24 in SMA; the repo names the *class*, not a part.

---

## 2. What the bypass diode does and does not fix

**Fixes:** one wing open or shaded → the other three still deliver ≈4.5 V; the array survives.

**Does NOT fix:** the diode is across a *wing's own* `SOLAR_P`↔`SOLAR_N`. It cannot help if the
**release itself** removes a wing *and* the diode, or if the wing's tab physically leaves with the
contacts. That is why §4's slip-fit must keep the diode **on the hub**, not on the wing.

**Consequence for the release design:** the diode must be on the **hub side** of the slip-fit. It
already is (`D_BP` is on the hub). **Keep it there.**

---

## 3. The mechanical interface you must design the release around

From `docs/WING-TO-HUB-SOCKET-SPEC.md` §2/§7 and ADR-048 §2.2 — these are **cited, not to be
re-derived**:

| Item | Value |
|---|---|
| Interfaces | 4, at 90° |
| Lands per interface | 4 on **each** face (8 total) |
| Land size / pitch | **4.0 × 1.2 mm** / **1.8 mm** |
| Land order (1→4) | `W<n>_SOLAR_P`, `GND`, `W<n>_RF` (no net on v9), `W<n>_SOLAR_N` |
| Slot (Option A, implemented) | **0.9 mm × 6.0 mm**, ±0.10 mm |
| Insertion depth | **6.0 mm** |
| Land offset along insertion axis | near edge **1.0 mm** inboard; centre **3.0 mm**; spans 1.0…5.0 mm |
| Tab width | **9.0 mm** (ADR-046 §2.2 wins over the spec's 8 mm — see ADR-048 §3 D-2) |
| Component keep-out | **no component body/courtyard within 1.5 mm** of the land row, either face |
| Slot keep-out | slot outline **+1.0 mm**, no copper/via/courtyard/silk inside |

**The current joint is soldered** (4-pin tab soldered into the slot). A slip-fit replaces solder
with a **normal-force contact**, which means you must now specify a **contact resistance and a
normal force** — neither exists in the repo today. That is §4.3.

---

## 4. The keeper + slip-fit release — what has to be designed

### 4.1 The concept (already argued — do not re-derive)

`docs/analysis/wing-release-electrical-contacts.md` §3 option 4: the electrical path is a
**slip-fit that is only held closed by a mechanical keeper**. Release the keeper → the contacts
part passively. **No copper is ever cut.** This exists because the array is one series string
(`docs/adr/046-wing-board-interface.md` §2.3: *"without a bypass path the whole string's current
collapses"*), so a deliberate cut is indistinguishable from the mission-ending failure.

### 4.2 The design decisions the next CW must make (with the constraint on each)

| # | Decision | Constraint / trap |
|---|---|---|
| 1 | **Contact geometry** — what replaces the soldered tab? | Must fit the existing 4.0×1.2 mm lands at 1.8 mm pitch, 6.0 mm insertion, 9.0 mm tab. Do **not** invent a new land size; the hub is already routed. |
| 2 | **Normal force** | Must hold through ascent vibration and the assumed **10 g burst shock** (`wing-jettison.md` §2.1). Wing mass 3.2 g → 314 mN at 10 g. |
| 3 | **Contact resistance spec** | **Does not exist in the repo.** Must be measured/derived. At 400 mA a 100 mΩ contact costs 16 mW — compare against the 100 µW night budget. |
| 4 | **Keeper retention** | The keeper holds the slip-fit closed. Its release force must exceed the slip-fit's opening force **plus** margin — otherwise the wing falls out when the keeper is released *early* or not at all. |
| 5 | **Keeper actuation** | **Nichrome on nylon is the only in-repo precedent** (~0.5 g/channel, 2.59 J/cut, ADR-051 §2.5). A solenoid is rejected on power (2000–3500× the night budget). Use the nichrome channel that already exists (`U_CUT1–4`). |
| 6 | **Where the diode lives** | **Hub side.** The bypass `D_BP` must not leave with the wing (§2). |
| 7 | **Verify the release actually happened** | `wing-jettison.md` failure mode #2 is *"partially cut loop"* with **no telemetry**. A slip-fit gives you a new option: a continuity sense across the keeper, or a second contact that opens on release. **This is the one place the new design can be better than the nichrome study's baseline.** |

### 4.3 The two numbers that block the design

Both are `TODO(unverified)` and **must be measured before any layout**:

1. **Slip-fit pull-out force window.** Lower bound = ascent vibration + 10 g shock (must not open
   in flight). Upper bound = the keeper actuator must be able to open it. No in-repo measurement.
2. **Contact resistance of the chosen slip-fit** at 400 mA, cold (−55 °C).

**Bench plan:** a pull rig with a spring scale for (1); a 4-wire measurement at 400 mA in a freezer
for (2). Both are cheap and neither needs a flight.

### 4.4 What this design must NOT do

- **Do not cut or interrupt the copper** as a deliberate action (§1 of the analysis).
- **Do not put the bypass diode on the wing** — it must stay on the hub (§2).
- **Do not break the 4-pin land interface.** ADR-046 §2.1: the tab is the wing's **only** electrical
  connection, and `wing-jettison.md` §0 finding 3 warns that replacing it with flying leads turns a
  defined structural+electrical joint into a knotted one **plus** four flying leads per wing.
  A slip-fit must therefore **retain the 4-pin land row geometry**, not replace it with wires.
- **Do not arm before burst.** Descent-only arming is the study's recommendation; a premature fire
  is failure mode #1, severity 5.
- **Do not touch `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` casually** — it is currently
  at **0 segments / 0 vias** (`t_273cbf1a`); a GUI save already destroyed its routing once.

---

## 5. Blockers you inherit (check these before you plan)

| # | Blocker | Where |
|---|---|---|
| 1 | **Hub is NOT orderable.** A1 stackup 0.8 mm not selected, A2 not re-priced, A3 mass budget unreconciled, A4 per-placement fee unknown, A5 envelope not locked, A6 EN pull-up undecided | `docs/fab/hub-v9/PRE-ORDER-CHECKLIST.md` §A |
| 2 | **Wing board has 0 segments / 0 vias** — the copper is gone; gerbers regenerated from it are **also empty** | `t_273cbf1a` |
| 3 | **`tests/test_param_ssot.py::test_real_repo_is_clean` is RED** — hub outline vs the 103×103 SSOT anchor | `t_b6eb2562` |
| 4 | **`U_CUT1–4` symbol is 3-pin and cannot satisfy ADR-051** — the symbol must grow before the keeper actuator can be wired | `docs/fab/hub-v9/PART-DECISIONS.md` §0 |
| 5 | **Two stale docs** still say the bypass is a BAT54/SOD-323 (§1) | socket spec §5; ADR-048 §2.3 |

**Item 4 is the one that bites:** the keeper needs an actuator channel, and the existing cut
channel's symbol is architecturally incapable of the latched one-shot the ADR requires. **Resolve
the symbol before designing the keeper's drive.**

---

## 6. Suggested order of work

1. **Patch the two stale docs** (§1) — 15 minutes, prevents a future regression to BAT54.
2. **Decide DNP-vs-fitted for `D_BP`** (§1.2) and, if fitted, add the parts to the order.
3. **Measure the two blocking numbers** (§4.3) — pull-out force window, contact resistance.
4. **Design the keeper + slip-fit** against the fixed land geometry (§3), keeping the diode on the
   hub (§2).
5. **Resolve the `U_CUT` symbol** (§5 item 4) so the keeper has a drive.
6. **Only then** touch the hub layout, in a worktree, with a segment/via count taken **before and
   after** (the file has lost content this way twice).

---

## 7. Evidence commands (re-derive, do not trust this document)

```bash
# the placed bypass parts and their nets
git show origin/master:tracker/hardware/hub_board_v9.kicad_pcb | grep -A3 'D_BP1'

# the routed fab packet (537 segments, 173 vias) — the seed file has ZERO
git show origin/master:docs/fab/hub-v9/gerbers/hub_v9.kicad_pcb | grep -c '(segment'

# the re-rated diode decision
git show origin/master:docs/adr/053-per-cell-bypass-diodes.md | sed -n '160,175p'

# the release analysis this handover hands off
git show origin/master:docs/analysis/wing-release-electrical-contacts.md | sed -n '1,40p'
```

---

## 8. Open items carried forward (all explicit, none invented)

- `TODO(unverified)` — LCSC part number for SS24 in SMA.
- `TODO(unverified)` — SS24 continuous-current thermal derating at −60 °C.
- `TODO(unverified)` — slip-fit pull-out force window (§4.3).
- `TODO(unverified)` — slip-fit contact resistance at 400 mA, cold (§4.3).
- `TODO(unverified)` — keeper release-force margin over the slip-fit opening force.
- `TODO(unverified)` — whether a release-continuity sense is worth the extra conductor.
- `TODO(unverified)` — whether JLCPCB's paste layer carries the SMA lands (if machine-assembled).
