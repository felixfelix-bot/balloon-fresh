# RECOMMENDATIONS ON THE NINE OPEN DECISIONS — with reasons and evidence

**Date:** 2026-10-14 · **Purpose:** answer *"what are your recommendations for these things and
why?"* for every decision currently gating the order or the programme.

**Rule applied throughout:** recommend the option that **buys information or preserves optionality
for the least irreversible cost**, and say plainly where the evidence is thin.

---

## D1 — The audit-4 call: the hub board is missing 7 schematic-declared parts

**Facts.** The netlist declares **46** components; the shipped board carries **39**. Missing:
`U_CUT1–4`, `U_HUB_CVT`, `PVA1–2` — **all seven have an empty `Footprint` field**, so they cannot
be placed. `PART-DECISIONS.md` §0 shows why: `CUT_CHANNEL` is a **3-pin symbol** and the ADR
demands a **latched one-shot**, so **the part choice is downstream of a schematic change** (+4 nets,
~4–8 pads per channel).

### ✅ RECOMMENDATION: **Option A — order the board as-is (39 parts) and defer.**

**Why:**
1. **What's missing is three functions, not a defect in what's present.** RF, MCU, power, sensing
   and the wing-cut *interface nets* are all on the board and routed 48/48.
2. **Option B's cost is a full re-route.** Adding 4 channels × 4–8 pads changes the netlist, so
   place → route → DRC → export all redo, **invalidating the 48/48 JLC-legal board** and its
   audited package. That is the most expensive path available.
3. **The wing-cut driver is the least flight-critical item on the board.** It is a *recovery*
   mechanism; the balloon flies without it and the wing strings can be left whole.
4. **Option A buys flight data cheaply.** A first flight article that measures RF, thermal and
   power behaviour is worth far more than a board held for a cut circuit nobody has tested.
5. **Reversible in the right direction:** deferring costs one respin *later*, funded by flight
   data; doing B now costs the respin *regardless* plus the schedule.

**Risk I am accepting:** wings stay electrically attached in flight, so a cut-wing contingency is
unavailable on flight 1. **Mitigated** by keeping the wing strings whole (no cut needed) and by the
`CUT_W`/`CUT_SENSE` nets being present for a bench-only interposer if we want to test the concept.

**What would change my mind:** if a launched balloon *must* be able to sever wings to descend,
Option A is wrong and B is right. **That is a mission question, and it is yours.**

---

## D2 — How many base stations?

**Facts.** The pipe has **two ends**. Each station is a 433 RX AGC + telemetry board (AD8318,
RP2040, bias tee, TPS62162). JLC prices per unique board, and the marginal cost of extra units is
mostly parts, not setup.

### ✅ RECOMMENDATION: **design for one station PCB, order 3 boards.**

**Why:**
1. "Two ends" is a **topology** statement, not a quantity. A station may be needed at each end
   *plus* a spare — **3 covers two ends and one failure** without a second order cycle.
2. **The board is not routed yet**, so quantity can be fixed at no design cost. Waiting to decide
   until after routing would only delay.
3. **A spare is cheap insurance** against a bench fault at a fixed site, where a dead station
   means no telemetry until a re-order arrives — the same logic already applied to the hub
   ("1 spare board per 10").
4. **No extra setup fee** for 3 vs 1.

**Open with you:** whether both ends are truly remote/fixed (mast-mounted) or one end is a bench
station — that changes enclosure, not quantity.

---

## D3 — The U5/U6 conflict (GPS + baro populated in the old BOM vs DNP in the locked split)

**Facts.** The **LOCKED SPLIT** says: *"1 variant, platform populated on all 10 | **no baro; GPS as
DNP rows + 4 loose**."* An older BOM CSV has `U5` (MAX-M10S GPS) and `U6` (MS5611 baro) as
**populated** lines with LCSC numbers. **Both cannot be right.**

### ✅ RECOMMENDATION: **the LOCKED SPLIT wins — `U5` and `U6` DNP, 4 loose MAX-M10S.**

**Why:**
1. **The word "LOCKED" is doing real work.** The split was an explicit operator-agreed package
   decision; the old BOM CSV is a **derived artefact** that was never updated.
2. **The memory on this programme is that derived state drifts, not that locked decisions drift.**
   This campaign has caught **six** artefacts whose derived state disagreed with the truth — stale
   gerber ZIP, stale zone fill, malformed CSV, the stale 103×115 board file, wrong BOM header, and
   my own verification bugs. **The split is the primary; the CSV is the derivative.** So when they
   disagree, fix the CSV.
3. **The DNP rows are already set on the board** and the BOM is board-verified (0 missing, 0
   extra), so the package is currently self-consistent with the split.
4. **The flight rationale is sound:** cabin-pressurised thermal cycling makes a barometer's value
   low and its failure mode worse; GPS is wanted but only on 4 units (hand-soldered), which is what
   "4 loose" means.

**Action I took:** emitted the DNP rows **with the conflict recorded in the BOM comment** rather
than silently picking a side. **If you rule the other way, it is a one-line change.**

---

## D4 — Supercap DNP

**Facts.** `C_CAP1`/`C_CAP2` (±3.3 F) are **currently populated** in the CPL, but the
accepted-risks list says: *"**Supercap DNP:** no buffer for TX bursts at dawn/dusk → cold-start
untested (E-CS1…6 planned)."* **The accepted risk is written assuming they are NOT fitted.**

### ✅ RECOMMENDATION: **DNP them on flight 1.** Keep the sites.

**Why:**
1. **The risk register already assumes DNP.** Leaving them populated makes the register describe a
   different board than the one flying — precisely the drift class above.
2. **This is energy storage, not a passive part.** Populated supercaps are a **charged thermal and
   handling hazard**, and at dawn/dusk they change inrush, charge time and cold-start behaviour —
   **none of which is tested** (E-CS1…6 are *planned*).
3. **DNP preserves the option at zero cost** — the pads stay, so a later build can fit them with
   no respin, exactly the reasoning accepted for the F33 site (Option B).
4. **Flight 1 should be the simplest configuration that can answer flight questions.** Adding
   untested energy storage adds risk without adding a measurement.

**What would change my mind:** a measured cold-start failure at dawn/dusk that supercaps fix.

---

## D5 — `R_NTC1` / `TH_NTC1` (part selection, currently `TODO(unverified)`)

**Facts.** Both are **on the populated list** and both carry **no part number**. They sit in the
NTC sense chain whose **stated purpose is to MEASURE the cold**: the accepted-risks list says the
−40…−50 °C ambient is *"Accepted, to be **measured** in flight via the NTC sense lines."*

### ✅ RECOMMENDATION: **select an NTC + fixed resistor pair rated ≥ 150 °C-span, and treat this as the flight's thermal instrument — not a BOM cleanup.**

**Why:**
1. **These are the only means of verifying the biggest accepted risk.** The cold claim is
   *accepted because it will be measured* — so if the NTC chain is wrong or unpopulated, **the risk
   becomes unmeasured and the acceptance is void.**
2. **Selection criteria that actually matter:** resistance at −50 °C must stay within the RP2040
   ADC's measurement window with the chosen series resistor; the part must be **rated below
   −55 °C**; and it must be **physically small enough to sit on the board** (0402/0603).
3. **The failure mode to avoid:** an NTC whose −50 °C resistance is so high that the divider
   saturates — the sense line then reads "cold" for every temperature, which *looks* like data.
   **The series resistor must be chosen against the COLD end, not the 25 °C nominal.**

**What I need from you:** nothing to proceed — this is a part-selection task I can carry out and
bring back as a decision package, like `PART-DECISIONS.md`. **Flagged because it needs a
deliberate choice, not a default.**

---

## D6 — F33 population

**Facts.** `U2` (`LoRa2021F33_2G4`) = **1038.8 mm²**; `U3` (bare) = **440.6 mm²** → the F33 site
costs **598.3 mm² = 12.2 % of the 70×70 board**, plus a **VSCAP-fed pre-regulator branch**, a
1.1 A current path and PA-table support. And the **433 MHz legality decision** established that
**2 W / +33 dBm is not licence-free legal in Germany** (10 mW ERP ceiling, Vfg. 91/2025).

### ✅ RECOMMENDATION: **Option B — keep `U2` as a DNP site, do not populate. Buy 1–2 F33 modules, not 10. Confirm LCSC `C5913567`.**

**Why:**
1. **The F33's headline capability is now unlawful to use.** Its extra ~11 dB **buys nothing
   lawful while costing power, mass, board area and a pre-regulator branch.** The mission survives
   on **LoRa SF12** at the 10 mW ceiling (+32.4 dB margin at 300 km).
2. **Do not remove it (Option C) yet.** Removing + shrinking recovers 598 mm² but **requires a
   re-route**, which invalidates the 48/48 JLC-legal board — the same expensive path as D1-B.
   **The reason to keep the site is optionality:** a licensed route, or a different jurisdiction,
   could make the F33's power lawful later, and a DNP site costs nothing to keep.
3. **Buying 1–2 instead of 10 saves ~$64–72** on a part that cannot be lawfully driven at
   capability, while leaving one spare for bench work.
4. **`C5913567` is flagged `(check)` in our own docs** — an unverified part number must not go
   into a paid order. **This is a 10-minute verification, not a decision.**

---

## D7 — The Astra spatial-review lane

**Facts.** The `visual_review` predicate **exists** in `gate_engine.py` (line 952) but is **not in
the `code` tier's 11 required predicates**, and the router has **no openai-family model**
(`/v1/models` returns GLM/Kimi/MiniMax/DeepSeek). So the gate is **built, correct, UNWIRED and
UNFUNDED**. The goal statement requires an LLM with good spatial reasoning (like Astra) to review
before anything moves to `done`.

### ✅ RECOMMENDATION: **wire `visual_review` to a lane that exists, and pick the reviewer deliberately — do NOT silently substitute.**

**Why:**
1. **This is a gate-integrity question, not a tooling gap.** The whole point of the predicate is
   that a *different kind of reviewer* looks at the geometry. Accepting a weaker reviewer to make
   the gate green is **gate-gaming**, and it must be **your deliberate choice**, never mine.
2. **Two honest options:**
   - **(a)** restore an openai-family model on the router and add `visual_review` to the `code`
     tier — the intended design; or
   - **(b)** explicitly authorise a named substitute **and record that the reviewer changed**, so
     the audit trail shows the substitution.
3. **Meanwhile the gate is doing its job by blocking.** I have **not** marked any board `done`.
   That is the correct behaviour with the lane down: **a blocked gate is better than a gamed one.**

**My recommendation:** (a) if the lane can be restored cheaply, else (b) with the substitution
recorded. **What I will not do is pick an unapproved reviewer to clear the gate.**

---

## D8 — 4G go/no-go on R1–R7 + telco topology

**Facts.** Recommended, **not decided**: cellular **off** the v1 PCBA; an **adjacent box** fed from
`VIN_GS` (9–18 V, **not** the 5 V rail); **LTE Cat-4, not 5G**; **anchors only**; reachability is
an **overlay problem (CGNAT)**, not a baud problem; order G2/G3 before G1; relaying is our own
traffic.

### ✅ RECOMMENDATION: **GO on the architecture, but do NOT buy G1 until the two cheap services (G2/G3) are ordered and tested.**

**Why:**
1. **The architecture answers are already sound and cheap:** cellular off the PCBA (no host CPU on
   the D14 freeze) and fed from `VIN_GS` — this **leaves the D14-frozen 5 V network untouched**, so
   it cannot break the certified power section. **That is the decision with the best
   cost/risk ratio, and it is effectively free.**
2. **Cat-4 over 5G** because the link is latency- and reliability-shaped, not bandwidth-shaped —
   telemetry and SSH, not throughput. **5G costs more and adds nothing the mission needs.**
3. **Anchors-only** avoids needing a public IP or port-forward on a mobile network — the right
   response to CGNAT.
4. **Order G2/G3 before G1** because they are **cheap and test the assumption**; if the
   reachability overlay works on a small service, the expensive mast-mounted kit is a much safer
   purchase. **This is the "buy information first" rule.**

**Still yours:** whether a **mast-mounted** kit ($179 MikroTik LHG) or a **bench** kit (€169.90
Teltonika RUT241) is the v1 target. **That is a siting question, not an architecture one.**

---

## D9 — Which board is looping (S3 or C3)

**Facts.** ADR-029's design direction was **ratified by you on 2026-10-04**; **v9 is S3, decided.**
Only the identity of the *failing unit* is unknown.

### ✅ RECOMMENDATION: **this is a diagnostic, not a decision — and it does NOT gate anything.**

**Why:**
1. **The design is already decided**, so the looping unit's identity changes **nothing** about the
   board we are ordering.
2. **It matters only for the watchdogs:** a self-revive policy for a stuck board may need to know
   which MCU is resetting, so if a board is looping in the field, the fix differs. **That is an ops
   question with no bearing on this order.**
3. **Deliberately de-prioritised** so it stops appearing in the decision list as if it were
   blocking. **If you have a looping unit in hand, its silkscreen or `esptool` chip ID answers it
   in one command.**

---

## The two money items (both currently LOWER BOUNDS)

1. **Re-price at 0.8 mm, 4-layer.** The captured quote used a **~1.6 mm page default**, so every
   total is a **lower bound**. ✅ **Do this before any order** — it is a form change, not a design
   change.
2. **The JLC per-placement assembly fee is unmeasured.** ✅ **Measure it from JLC's public assembly
   pricing for our placement count (37 placements) before committing** — this is the last
   unidentified cost in the order.

**Neither is a decision.** Both are lookups, and I can do them.

---

## Summary table

| # | decision | recommendation | why, in one line |
|---|---|---|---|
| D1 | audit-4 | **A — order 39-part board, defer** | deferring costs one later respin; B costs the re-route *and* the schedule now |
| D2 | station count | **design 1, order 3** | two ends + one spare, no extra setup fee, quantity free pre-route |
| D3 | U5/U6 | **LOCKED SPLIT wins — DNP** | the split is primary, the BOM CSV is derived state that drifted |
| D4 | supercap | **DNP flight 1, keep sites** | the risk register already assumes DNP; pads preserve the option |
| D5 | R_NTC1/TH_NTC1 | **select as the flight's thermal instrument** | the cold risk is "accepted because measured" — no part, no measurement |
| D6 | F33 | **B — DNP, buy 1–2, confirm C5913567** | its power is now unlawful; C keeps optionality; C (removal) forces a re-route |
| D7 | Astra lane | **wire it, or authorise a substitute explicitly** | a blocked gate beats a gamed one; the choice must be yours |
| D8 | 4G | **GO architecture; G2/G3 before G1** | free architectural answers; cheap services test the assumption first |
| D9 | looping board | **not blocking — diagnostic only** | the design is already decided; only field ops care |

**Two not-decision lookups I can carry out now:** the 0.8 mm re-price and the per-placement fee.
