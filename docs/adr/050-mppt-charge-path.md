# ADR-050 — Charge-path converter between the solar array and the supercap bank

> Numbered **050** on 2026-10-07 by `scripts/adr_next_number.py` (`python3
> scripts/adr_next_number.py` → `50`; the `--path docs/adr/049-wing-architecture.md` failure path
> was also exercised and exits non-zero, so the allocator is doing what the index header says).
> The next free number was checked across all branches, not just this checkout:
> `git log --all --oneline --name-only -- 'docs/adr/*'` shows 044a and 100–110 allocated, and
> **no file anywhere claims 050**. `tests/test_adr_numbering.py` stays green (see §Rollout).

- Status: **Proposed** — the *text* has **NOT** been accepted by a human. The operator has
  **approved the converter as a design direction** (quoted in §0); the record below is put to him
  for acceptance, and until a human accepts it no schematic, placement, BOM freeze or fabrication
  may treat it as frozen (ADR-first rule, ADR-029 §Context). **A Proposed record does not, by
  itself, re-freeze an Accepted one** — see §2 for exactly what is superseded and how.
- Date: 2026-10-07
- Decision owner: Felix (operator). The direction was given 2026-10-07; the text is not accepted.
- Author: subagent (Hermes), branch `feat/mppt-charge-path`, worktree `~/worktrees/bf-mppt`.
- **Supersedes in part** ADR-006 (`docs/adr/006-supercapacitor-power.md`, **Accepted**) — the
  **direct-connection** element only, i.e. the unbroken block
  `Solarzellen → Schottky-Diode → Supercapacitor-Bank`. **Retains** ADR-006's **storage**
  decision (2× AVX SCC 3.3 F 2.7 V in series = 1.65 F @ 5.4 V, to be doubled to 3.3 F), its
  **solar-wing-count** decision (4 wings × 3 cells in series = 12 cells = 6.0 V nominal), and its
  **LDO** decision (TPS7A02 3.3 V, I_Q = 25 nA).
- Related records: ADR-029 (§5 tests 1–4 are the EMI/rail acceptance numbers; D8's selectable
  pin-1 rail), ADR-032 (simulation evidence for switcher harmonics), ADR-036 (burst storage,
  daylight-only TX, the 100 µW night anchor), ADR-044 (option (b) boost **refused for the radio
  rail**; option (c) clamp), ADR-046/ADR-048 (wing/hub interfaces, the per-wing bypass Schottky),
  ADR-047 (6.15 W maximum draw; VSCAP **is** the radio's VCC; the clamp as required insurance;
  the over-voltage path), ADR-049 (wing architecture; the clamp is a required rated part).
- Related artefacts: `docs/analysis/mppt-charge-path-specification.md` (**the computed evidence
  behind every number in this record**), `docs/analysis/array-power-architecture.md` (the
  break-even finding), `docs/analysis/wing-electrical.md` (§5.1, the cold open-circuit
  arithmetic), `docs/POWER-BUDGET-V9-D2BE.md`, `docs/analysis/wing-ladder.md` (the cut channel).

---

## 0. The operator decisions this record executes (given, quoted in substance)

1. **"Degrading performance is preferable to losing the vehicle."** Shedding panels and running at
   reduced power/throughput over time is **acceptable**.
2. **"Approved: a single MPPT charge-path converter between the array and the supercap bank,
   specifically so that ANY number of wings can be cut off without breaking charging."**

These are a **direction**, not an accepted text. This record does not upgrade its own status.

---

## 1. Context

ADR-006 (Accepted) wires the 12-cell array **directly** to the supercap bank through a BAT54. That
is optimal while the string voltage exceeds the bank voltage, and it fails the moment it does not:
with the four wings on one **series** string (ADR-046 §2.3), losing wings removes **string
voltage**, not just power. `docs/analysis/array-power-architecture.md` §3.2 computes it —
3 wings → a 4.20 V bank ceiling (mission continues at −1.56 dB), **2 wings → a 2.70 V ceiling,
below the radio's 3.0 V minimum: mission over.**

The operator has therefore approved a converter that decouples the array voltage from the bank
voltage, so that **any number of wings can be cut and charging continues**. The full computed
specification, the failure/operations analysis and the bench test plan are in
`docs/analysis/mppt-charge-path-specification.md`; this record fixes the decisions.

**The efficiency argument and the continuity argument are different, and the record says which one
binds.** CITED `docs/analysis/array-power-architecture.md` §5(b): at an **assumed** 85 %
conversion efficiency the MPPT breaks even against the direct connection at a bank voltage of

```
break-even = P_mppt / I_MPP = 6.12 W / 1.2 A = 5.10 V = 94.4 % of the 5.4 V bank top
MPPT gain at a 3.0 V bank = +70.0 % ; at a 5.4 V (full) bank = −5.6 %
```

ADR-036's policy deliberately keeps the bank **near its top** during daylight (TX is
daylight-only and energy-gated). **On energy alone this converter is therefore NOT justified at the
bank's normal operating point** — its 15 % conversion loss is paid all the time while its MPPT win
sits in the regime the design avoids. **The binding argument is MISSION CONTINUITY under panel
loss, not efficiency.** This record does **not** sell the converter as an efficiency gain, and the
efficiency number it depends on is `TODO(unverified)`.

---

## 2. Relationship to standing decisions — what is superseded and what is retained

| ADR-006 element | Status under this record |
|---|---|
| **Direct connection** `Solarzellen → Schottky → Supercapacitor-Bank` | **SUPERSEDED in part.** A converter now sits between the array and the bank. The BAT54's reverse-blocking role is taken over by the converter; whether a BAT54 is still fitted in series is a schematic detail this record leaves open. |
| **Storage** (2× AVX SCC 3.3 F 2.7 V series = 1.65 F @ 5.4 V, doubling to 3.3 F, 10 kΩ balancing) | **RETAINED, unchanged.** The converter's output regulation point is set to this bank's design top (§3.3). |
| **Solar-wing count** (4 wings × 3 cells in series = 12 cells, 6.0 V nominal) | **RETAINED, unchanged.** The converter removes the *voltage* constraint on the series count, but nothing in this record changes the count. |
| **LDO** (TPS7A02 3.3 V, I_Q = 25 nA) | **RETAINED, unchanged.** The logic rail and the bare-LoRa2021 VCC path are untouched. |

**ADR-044 §3 option (b) and ADR-047 §5 refused a boost converter — for the RADIO RAIL.** This
record does **not** overrule that refusal. It is a **different converter answering a different
question** (transferring energy *into* the bank, not holding the radio's pin-1 rail), and it
re-opens the same objection class (mass, quiescent, EMI) explicitly rather than by omission. The
EMI question is answered only by measurement (§7) and the distinction between the two converter
placements is **only partly real** — ADR-047 §2.1 makes VSCAP itself the radio's VCC, so the
conducted coupling path is shared. That is stated in the record, not hidden.

**ADR-044/047's mandatory shunt clamp:** see §3.5. It is **retained**.

---

## 3. Decision — the parameters this record fixes

### 3.1 Topology — **non-inverting buck-boost (or SEPIC); NOT a pure boost**

```
at V_in = 1.5 V : 5.4 / 1.5 = 3.60×   → step-UP required
at V_in = 4.5 V : 5.4 / 4.5 = 1.20×   → step-UP required
at V_in = 6.0 V : 5.4 / 6.0 = 0.90×   → step-DOWN required
```

A **pure boost cannot regulate 6.0 V in down to 5.4 V out**, so the topology must step both ways:
a **four-switch non-inverting buck-boost** (preferred: one inductor, one controller) or a **SEPIC**
(second choice: a coupling capacitor, more parts, non-inverting, fails safe). A pure boost is
**rejected** on this arithmetic. (A boost to a higher output with a downstream buck would be two
stages and is rejected on mass.)

### 3.2 Input voltage range — **1.50 V … 9.58 V, rating ≥ 12 V (prefer ≥ 16 V)**

```
V_MPP per wing = 3 cells × 0.50 V = 1.50 V
 1 wing = 1.50 V ; 2 wings = 3.00 V ; 3 wings = 4.50 V ; 4 wings = 6.00 V
absolute input maximum = array open-circuit voltage, 12 cells at −60 °C ≈ 9.5820 V
required rating  = 9.5820 V × 1.25 = 11.98 V → ≥ 12 V ; prefer ≥ 16 V
```

**A converter rated only to 6 V dies.** The unloaded input capacitor charges to the array's
open-circuit voltage, `9.5820 / 6.00 = 1.60×` the 6 V rating; an input switch in avalanche
typically fails **short**, which then presents the array's 9.58 V to the bank and radio. Plainly:
**a 6 V-rated part is destroyed, and its most likely failure shorts the array into the bank.**

**Requirement status, stated honestly.** A single-IC converter covering 1.50 V input **and**
9.58 V input **and** ~1.5 A of charge-path output **was not found** in the part survey read on
2026-10-07 (every ≤1.5 V-capable part tops out at 5.1–5.5 V input; every ≥12 V-capable part starts
at 2.42–2.5 V). The verified best fit, **TPS63060** (buck-boost, 2.5–12 V in, 2.25 A switch limit),
therefore sets the practical **operating floor at two wings (3.0 V)**, with comfortable margin at
three. **One wing (1.50 V) does not charge.** This is recorded as an open item, not papered over.

### 3.3 Output regulation point — **5.40 V** (the ADR-006 bank top), current-limited

The converter charges the bank to its rated design top, `2 × 2.7 V = 5.40 V`, current-limited to
the array's available power. This is a **CV charge** into a 3.3 F bank, so charging tapers into the
top naturally. The radio stays fed from the **bank node** as ADR-047 §2.1 already requires; the
regulation point changes the bank's **charge ceiling**, not the radio's topology. The F33's stated
VCC maximum (5.5 V, no absolute-maximum table) is respected by construction **only while the
converter regulates** — which is why the clamp stays (§3.5).

### 3.4 Capacitance — input ≥ 22 µF / ≥ 25 V X7R + 100 nF; output 100 µF + 100 nF + ferrite

```
C_in ≥ 22 µF, X7R/X5R, rated ≥ 25 V   (rating ≥ 2× the 12 V input spec, from the 9.58 V cold Voc)
   input slew at full array current: dV/dt = I/C = 1.2 A / 22 µF = 54.5 mV/µs
C_out(local) = 100 µF low-ESR + 100 nF   (the 100 µF value is CITED: ADR-047 §4.3 C_BULK)
plus a ≥ 1.5 A-class ferrite between the converter output and the VSCAP/radio node
```

The bank **is** the output bulk capacitance (3.3 F once doubled); the local output cap exists to
stabilise the converter's loop, and the ferrite exists to keep switched ripple off VSCAP, which
**is** the radio's supply.

### 3.5 The shunt clamp is **RETAINED** — and explicitly NOT replaced by the regulated output

The brief asks this directly because it changes the parts list. **The regulated output does NOT
replace the ADR-044/ADR-047 shunt clamp.** Three over-voltage paths survive the converter:

1. **The converter's own input node** sees the array's full 9.58 V — a path the bank-side clamp
   cannot cover. If the chosen part's input rating is below ~12 V, a **second** limiter is needed on
   the converter input.
2. **Converter failure pass-through** — a shorted high-side switch, a shorted inductor, or a loop
   that never closes presents the array's open-circuit voltage (up to `9.5820 / 5.40 = 1.77×` the
   bank rating, `9.5820 / 5.50 = 1.74×` the radio's stated maximum) **directly to the bank and the
   radio**, whose damage threshold is unpublished (ADR-047 §7).
3. **Start-up / fault transient** before the regulation loop closes.

**Decision: keep the clamp, and add a series fuse/PTC in the bank-to-converter path.** The
converter's regulation loop and the clamp do **different** jobs. ADR-049 clause 3's rated clamp
(must sink up to 1.2 A at 5.5 V) is unchanged.

### 3.6 Quiescent current budget — **I_Q ≤ 5 µA from the bank at 5.4 V; target ≤ 2 µA**

The converter sits on the raw VSCAP node, so its quiescent draw drains the bank **continuously**.
ADR-036's night anchor is 100 µW.

```
I_Q ≤ 5 µA  →  5 µA × 5.4 V = 27.0 µW = 27 % of the 100 µW anchor
I_Q ≤ 2 µA  →  2 µA × 5.4 V = 10.8 µW = 11 % of the anchor     (target)
for scale: a part drawing 30 µA × 5.4 V = 162 µW = 162 % of the anchor
```

**Requirement: firmware must disable/idle the converter at night**, and the disabled-state leakage
must also meet the bound. This is a hard constraint: a part whose I_Q is at the tens-of-µA scale
(for example the otherwise-suitable TPS63060 at 30 µA typ) is admissible **only** if it can be
disabled into a sub-µA state.

### 3.7 Mass estimate — **≈ 0.70–1.20 g; one active part**

```
controller IC                        0.02 g   (ADR-044 §3 option (b) order)
shielded inductor 4.7–10 µH, ≥3 A    0.20–0.50 g   (ESTIMATE, part not selected)
C_in 22 µF + 100 nF                  0.10 g
C_out 100 µF + 100 nF                0.10 g
ferrite (≥1.5 A)                     0.05 g
feedback / MPP divider               0.01 g
retained clamp                       0.05 g   (ADR-044 §3 option (c): < 0.1 g)
extra PCB area (~150 mm²)            0.19 g
TOTAL                          ≈ 0.70–1.20 g
```

Consistent with ADR-044 §3 option (b)'s "order of 0.5–1.5 g". On a payload on which **mass is the
binding constraint**, this is the price of the mission-continuity benefit; it is not free.

### 3.8 Control scheme — **fraction-of-Voc input regulation; true MPPT and firmware hill-climb are NOT required**

The load is a supercap bank that clamps the output, and the input is a directly-irradiated array
whose maximum-power voltage moves with **temperature** (`−2.1 mV/°C/cell`), far more than with
illumination. Therefore: true MPPT is unnecessary; a **fixed-fraction-of-Voc input-voltage
regulation** (as controllers such as the LTC3129-1 implement as "programmable maximum power point
control") is sufficient, and a firmware perturb-and-observe loop is **rejected** — it would add a
current-sense element, an ADC channel, and a dithering loss of ~1–2 % on a bank whose night budget
is at the 100 µW scale. **Sensing:** a µA-level resistor divider on the converter input.
**If the chosen part has no MPP pin:** a fixed setpoint is acceptable but will run off-MPP at the
cold end, which the bench plan measures.

### 3.9 Switching frequency and EMI posture — **f_sw 500 kHz–1 MHz with spread spectrum; verdict deferred to bench**

f_sw is chosen in the **500 kHz – 1 MHz** band with frequency dithering if available: high enough
to keep `L`/`C` (and mass) small, low enough that low-order harmonics stay well below the 433 MHz
TX and 2.4 GHz RX bands, with spread spectrum as the cheapest effective mitigation. Mitigations
specified: shielded inductor, winding axis parallel to the array plane and **≥ 15 mm** from the
2.4 GHz feed; input/output LC filtering (including the ≥1.5 A ferrite of §3.4); an RC snubber on
the switch node; a tight switched loop with a local ground plane. **The EMI verdict is
`TODO(unverified)` and is settled only by the bench plan in ADR-050 §7 (specification §2(e).4).**

### 3.10 Cut-energy budget — **≤ 10 % of the usable bank = ≤ 3.33 J per cut**

The cut channel (repo precedent: MOSFET + nichrome + nylon ≈ 0.5 g/channel,
`docs/balloon-test-results.md` line 253) is a resistive heater on the bank, and it can be powered
from the **bank node** (which is the converter's output node) so it works at night and with the
converter dead. A cut costs `E = V × I × t`:

```
at 5.4 V × 1.0 A × 3 s = 16.2 J = 49 % of the 33.264 J bank → only TWO cuts affordable
at 3.3 V × 0.5 A × 2 s =  3.3 J = 10 % of the bank         → ~10 cuts affordable
```

**Decision: budget each cut at ≤ 3.33 J (≤ 10 % of the 33.264 J usable bank), enforced by a
firmware maximum on-time and verified on the bench.** If the measured cut energy cannot be brought
under 3.33 J, the fix is a mechanical/spring release rather than a longer burn — which re-opens the
cut-mechanism trade, owned by the in-flight jettison study (cited, not duplicated here).

---

## 4. Failure modes — summarised (full analysis in specification §3)

- **Fails open:** no charge current, no damage; the bank gives 85.7 s at the 0.388 W average or
  5.41 s at the 6.15 W burst. Survivable; telemetry must flag it.
- **Fails shorted (input→output pass-through):** the array's 9.58 V reaches the bank and radio
  (1.77× the bank rating, 1.74× the radio's stated max). **This is why the clamp stays** (§3.5).
- **Fails shorted (output→GND):** 33.264 J dumped in ~seconds; contains with the series fuse/PTC.
- **Losing wings with the converter (floor 3.0 V):** 4→3→2 wings all still charge the bank to
  5.4 V and the mission continues; **1 wing → bank-only (~86 s of average duty); 0 wings → dark.**
  Against the accepted design (2 wings = mission over), this is the mission-continuity win —
  **not** a claim that any number of wings gives full power.

---

## 5. Consequences

### Positive

- **The single failure that ended the mission (two wings lost) becomes survivable**, and three
  wings lost still charges the bank — the operator's stated preference.
- The array voltage and the bank voltage are decoupled, so the series count no longer sets the
  charge ceiling.
- **One active part** and ≈0.70–1.20 g, with a fully computed specification and a bench gate.

### Costs (accepted)

- **Mass ≈ 0.70–1.20 g** on a mass-bound payload.
- **A continuous quiescent draw on the bank** (§3.6) — a new night-budget line, bounded to ≤ 5 µA.
- **A new failure point** (a wire cannot fail short into the bank; a converter can).
- **An EMI question next to a −136 dBm receiver**, unresolved until the bench plan runs.
- **The efficiency argument is negative at the bank's normal operating point** (§1); the converter
  is bought for continuity, not energy.
- **Re-freezes triggered** (ADR-044 §3 option (b)'s three): BOM (active part), the ADR-030
  placement keep-out (a switching node), and ADR-032 simulation of switcher harmonics with
  ADR-029 §5 tests 1 and 3 as the acceptance numbers.

### Still open

- Efficiency at 1.5 V and 6.0 V; a part covering the full 1.5–9.58 V window; cold open-circuit
  coefficients; the F33 damage threshold and hence the clamp set point; the converter's EMI; the
  cut channel's real energy. **All gathered in specification §Open items.**

---

## 6. Rollout (this is a decision record; no code lands with it)

1. **Operator accepts (or amends) this text.** This record is `Proposed`.
2. Convert specification §2(d).3's starting `L`/`C` values into the chosen part's datasheet design
   example (currently `TODO(unverified)`).
3. Run the bench plan (specification §4, items 4.1–4.10) — in particular the input-survival gate
   (4.5) and the EMI gate (4.7–4.8) — **before** any BOM freeze.
4. Patch ADR-006's header with the one-line supersede pointer (done on this branch, §2), and carry
   the schematic/placement changes through the normal ADR-first flow.
5. `python3 -m pytest tests/test_adr_numbering.py -q` must stay green (it does on this branch).

---

## 7. What would falsify this

- A bench measurement showing the converter's efficiency at 6.0 V is materially below 85 %, so the
  energy case is worse than the negative case already recorded — **does not falsify the continuity
  argument**, but strengthens the case for a threshold that keeps the converter off near the bank
  top.
- A part found that covers 1.50–9.58 V input at ~1.5 A output with a night-budget I_Q → the
  single-wing case comes back into scope.
- A bench measurement showing a cut costs more than ~3.33 J that cannot be reduced → the cut
  mechanism changes (mechanical release), and §3.10 must be amended with the measurement.
- A measurement showing the cap-string top node can exceed 5.5 V **through the converter** → the
  clamp becomes mandatory in a second location, and §3.5 must be amended to say so.
- A bench measurement showing the converter's switching noise breaks the receiver (ADR-029 §5 tests
  1 or 3 fail) → the charge-path placement does not buy the EMI immunity the radio-rail refusal
  feared it would not, and this record must be amended with the number.

---

## 8. Notes

- **Why this record does not restate the break-even arithmetic:** it is CITED, once, from
  `docs/analysis/array-power-architecture.md` §5(b), which owns it. Re-deriving it here would
  create a second copy that can drift.
- **Why the clamp question is answered twice** (§3.5 and §4): it is the one decision in this record
  that changes the parts list, and the brief asks for it explicitly.
- **Why the 1.5 V case is left open rather than declared met:** claiming it met would require
  inventing a part. The survey read on 2026-10-07 found none; that is stated.
- **In-flight work not duplicated:** the wing geometry/insolation studies, the progressive-shed
  ladder (`docs/analysis/wing-ladder.md`) and the single-cut whole-array jettison study
  (`analysis/wing-jettison`) are cited only.
