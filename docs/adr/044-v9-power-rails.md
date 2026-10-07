# ADR-044 — v9 power rails: the F33 5 V rail (resolves ADR-029 item O5)

- Status: **Proposed** — the *text* has **NOT** been accepted by a human. The
  recommendation below is put to the operator; until a human accepts it, this record
  does not say Accepted and no schematic/placement/routing may treat it as frozen
  (ADR-first rule, ADR-029 §Context).
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-adr (Hermes agent), resolving open item **O5** of ADR-029.
- Related: ADR-006 (`docs/adr/006-supercapacitor-power.md`, **Accepted** — the power
  architecture of record), ADR-029 (`docs/adr/029-dual-band-flight-board.md`, **Proposed**
  — O5 is the item this ADR answers; D8's selectable pin-1 rail is what option (a)
  implements), ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, which carries O5
  forward), ADR-036 (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`, the
  burst-sized-storage / daylight-only-TX policy this rail must obey),
  ADR-037 (`docs/adr/037-mcu-s3-no-fem.md`, MCU and no-FEM), ADR-032 (simulation evidence),
  ADR-035 (TDM radio schedule).
- Related artefacts: `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf`,
  `docs/F33-MODULE-PLAN.md`, `docs/POWER-BUDGET-V9-D2BE.md`,
  `tracker/hardware/tools/bom_part_allowlist.py`.

---

## 1. The question, stated exactly

ADR-029 **O5**:

> *"the 5 V rail: BLOCKED pending evidence. The four-radio rail sum is recorded in
> `docs/POWER-BUDGET-V9-D2BE.md`. It requires a specified 5 V chain demonstrated at
> >=1.2 A load-step capability, a 3.3 V rail at >=0.60 A transient capacity, and cold
> supercap/regulator evidence. Keep the 5 V option selectable in the schematic, but do not
> freeze the BOM or approve flight on an unmeasured chain; if the evidence fails, operate
> the F33 at 3.3 V with reduced output rather than claim +30 dBm."*

ADR-034 carries it forward as an explicit **open conflict**: a board built exactly to
ADR-006 (a single 3.3 V rail) cannot simultaneously meet ADR-034's 5 V / ~1200 mA TX, so
the two records do not reconcile by themselves.

**This ADR answers the topology half of O5 (which rail, built how). It does not answer
the evidence half** (§7 below). O5 stays open until the bench evidence exists.

### What is already fixed and is not re-opened here

| Fact | Authority |
|---|---|
| 4 wings × 3 cells = 12 cells, all wings in series → **6.0 V / 400 mA / 2.4 W peak** | ADR-006 (Accepted) |
| **2× AVX SCC 3.3 F 2.7 V in series → 1.65 F @ 5.4 V**, + 2× 10 kΩ balancing resistors | ADR-006 (Accepted) |
| Schottky (BAT54) from the array into the bank — reverse-current protection | ADR-006 (Accepted) |
| **TPS7A02 3.3 V LDO, I<sub>Q</sub> = 25 nA** on the 3.3 V side | ADR-006 (Accepted) |
| Storage sized to **one burst**, TX **daylight-only**, night deep sleep mandatory | ADR-036 (operator) |
| v9 RF complement: `LoRa2021F33-2G4` + `SX1280` + `MAX-M10S`, MCU `ESP32-S3-WROOM-1U-N8R8`, no FEM | ADR-029 D2b/D8, ADR-034, ADR-037 |
| **The F33's pin 1 VCC must be a *selectable* rail** (5 V for the F33, 3.3 V for the nested bare `LoRa2021`) — a solder jumper or DNP regulator, described as a **design requirement, not a suggestion** | ADR-029 **D8** (operator-ratified 2026-10-05) |
| 433 MHz TX / 2.4 GHz RX split; TDM schedule serializes the radios | ADR-034, ADR-035 |

D8 is load-bearing for this ADR: **the selectable pin-1 rail already has to exist for a
reason independent of O5.** Any option below must be judged by what it adds *on top of
that*, not as if it were inventing a new rail from nothing.

---

## 2. The datasheet fact that decides option (c) — read, not guessed

Provenance: **text extraction** (`pdftotext -layout
docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf /tmp/f33.txt`), Rev 1.1. A vision
model was **not** used, and must not be used for this: a hallucinated voltage maximum is
exactly the kind of error that costs a board.

Verbatim from §6 *Electrical Characteristics*:

```
   Parameters                       Test condition             Min.        Typ.     Max    Unit
  Voltage Range                                                3.0           5      5.5     V
```

and §6 *Current Consumption*:

```
  Transmit Current             @433MHz, 5V, 2W                            < 1200          mA
                               @868/915MHz,5V,1W                           < 800          mA
                               @2.4GHz,5V, 1W TxPower=5                    < 900          mA
                       Receive Current   @Sub-GHz                         <8            mA
                                         @2.4G bypass ON                 <9            mA
                                         @2.4G bypass OFF                <42           mA
        Sleep Current                                                        <20           uA
```

and §8 *Voltage vs Power Table* (the whole point of this ADR — output **falls with rail
voltage**):

| VCC | 433/470 MHz | 868/915 MHz | 1.9–2.5 GHz |
|---|---|---|---|
| 3.3 V | 28.9 dBm / 770 mA | 26.2 dBm / 540 mA | 26.4 dBm / 590 mA |
| 3.6 V | 30.3 / 903 | 27.2 / 576 | 27.3 / 650 |
| 4.0 V | 31.2 / 994 | 28.2 / 626 | 28.3 / 730 |
| 4.5 V | 31.8 / 1008 | 29.0 / 669 | 29.5 / 820 |
| **5.0 V** | **33.0 / 1100** | **29.7 / 711** | **30.0 / 840** |
| 5.5 V | 33.3 / 1118 | 30.4 / 759 | 30.2 / 860 |

**Finding — stated plainly, because it changes the answer:**

1. The datasheet's stated **VCC maximum is 5.5 V**. The supercap string's top is
   **5.4 V** (2× 2.7 V). **5.4 V < 5.5 V**, so the F33 sits *inside* its stated operating
   voltage range at full charge.
2. Therefore **option (c) is NOT mandatory on the trigger written into the task**
   ("if the datasheet max is below 5.4 V"). It is not below 5.4 V. Saying otherwise would
   be inventing a requirement.
3. **But Rev 1.1 publishes no "Absolute Maximum Ratings" table at all.** The section list
   is: 1 Descriptions, 2 Features, 3 Applications, 4 Block Diagram, 5 Typical Schematic
   Circuit, 6 Electrical Characteristics, 7 Pin definition, 8 Performance Indicators,
   9 Mechanism Dimension, Appendix 1 (demo board), Appendix 2 (SMD reflow).
   `grep -iE "absolut|rating|stress"` over the extracted text returns only the
   operating-temperature row and the §8 note-2 PA warning. So 5.5 V is a *maximum
   operating* figure with **0.1 V (1.8 %) margin** to our rail, and the level at which the
   part is actually damaged is **not published in this revision**.
4. The rail is **not inherently limited to 5.4 V by the module**. It is limited to the cap
   string's rating *if the balancing resistors do their job*, and otherwise by whatever the
   12-cell array pushes through the BAT54. The array's **open-circuit** voltage is above its
   6.0 V nominal working figure (a Si cell's V<sub>OC</sub> exceeds its V<sub>MPP</sub>), and
   the cells are operated near −60 °C. That is the real over-voltage path.

**TODO(unverified) — the exact open question:** *the 12-cell array's open-circuit voltage
at −60 °C is not in this repository, so the maximum the BAT54 can present to the cap
string's top node is unknown. Until it is measured, no claim can be made that the cap
string's top never exceeds the F33's stated 5.5 V maximum. Consequence: the clamp in
option (c) is recommended as insurance (see §4), but is not required by the datasheet's
stated maximum and must not be described as mandatory.*

---

## 3. Options, with cost/mass and re-freeze impact

### Option (a) — direct tap of the supercap rail into D8's selector (no converter)

**Change required.** The F33's pin 1 is fed from the **supercap node** (post-BAT54,
pre-LDO) through the pin-1 selector that ADR-029 **D8 already mandates**. The 3.3 V
position of that selector is the existing TPS7A02 output (for the nested bare
`LoRa2021`); the 5 V position is the raw cap rail. Add a **local low-ESR bulk capacitor at
the module** to hold the burst (§5 shows why one is needed and how small it can be). No
new active part, no inductor, no switcher.

**Cost / mass.** **€0 of new parts** — two jumper positions on a selector D8 already
requires, plus one bulk cap whose exact value is not yet selected (**TODO(unverified)**;
order of 100 µF–1 mF, ~0.1–0.3 g). No new BOM line beyond the cap.

**Forces a re-freeze?** **No.** It lands inside the v9 pre-freeze window, adds nothing to
the frozen v8h rule set (`jlcpcb-s1-frozen.kicad_dru` is untouched and v9 is a different
board), and invalidates no earlier v9 budget line — no v9 document has ever carried a 5 V
converter line.

**Cost accepted, stated plainly.** The rail is **the cap voltage**, so it **sags from
5.4 V to about 3.0 V** over the discharge. By the §8 table that means the F33 reaches full
**+30 dBm only near full charge**: at 4.0 V it is 28.2 dBm/868 and 28.3 dBm/2.4 GHz; at
3.3 V it is 26.2/868 and 26.4/2.4 GHz — i.e. **~3.5 dB below the 5 V figures**. This is a
*link-budget* cost, not a hardware cost, and it is compatible with ADR-036 (burst storage,
daylight-only TX): bursts are already gated on stored energy, and TX happens in daylight,
which is when the bank is fullest. The rail also **presents a falling VCC to the module
across a burst**; §5 bounds that.

### Option (b) — boost converter holding 5 V

**Change required.** Add a boost regulator (e.g. `TPS61099` or `LTC3525`, both named in
`docs/F33-MODULE-PLAN.md`) between the supercap node and the F33's pin 1, holding 5 V until
the bank can no longer support it. The TPS7A02 stays on the 3.3 V side.

**Cost / mass.** Roughly **€1.50–4.00** plus an inductor and reservoir caps — order of
**0.5–1.5 g** (part selection not made; **TODO(unverified)**). Adds a **quiescent draw** on
a bank whose night budget is already the constraint (ADR-036: the deep-sleep current in µA
is the deciding quantity for whether the night log survives; a switcher's I<sub>Q</sub> is
part-dependent and not yet selected).

**Forces a re-freeze?** **Yes — three of them, and they are not optional once the part is
in:**
- the **BOM** gains active parts before it can freeze;
- the **placement gate** (ADR-030) gains a switching node that needs a keep-out from the
  2.4 GHz (`ANT-2G4`/SX1280) front end and from the GNSS L1 feed;
- the **simulation evidence** (ADR-032) must now cover switcher harmonics and conducted/
  radiated paths into a −136 dBm receiver, and ADR-029 §5 tests 1 and 3 (2.4 GHz noise
  floor rise **< 3 dB**; GNSS C/N0 drop **< 1 dB**) become the acceptance numbers for a
  part that is *intrinsically* a noise source **2 mm from the victim**.

**Why it is not the recommendation.** It buys ~3.5 dB of link at the bottom of the
discharge at the price of mass, quiescent current, and an EMI fight next to a 2.4 GHz
receiver — on a board ADR-029 already calls the tightest it has been. It is the right
answer **only if a bench measurement shows the sag actually breaks the link**, which is
not established and is not asserted here.

### Option (c) — clamp / limit the rail at the F33's VCC maximum

**Change required.** Clamp the F33's VCC node (e.g. a low-capacitance TVS/zener or a
crowbar/OV-monitored switch) so the module never sees more than its stated maximum.

**Cost / mass.** **~€0.05–0.30**, **< 0.1 g** — the cheapest thing in this ADR.

**Forces a re-freeze?** **No** (one passive part on an existing net), though it is a BOM
line that must be present before the freeze.

**Is it mandatory?** **No — not on the stated trigger.** The datasheet maximum is 5.5 V,
which is *not* below the 5.4 V rail top (§2). It is **recommended anyway**, for the two
reasons §2 gives: the margin is 0.1 V (1.8 %), and the point at which the part is actually
damaged is not published in Rev 1.1 while the array's open-circuit voltage is unmeasured.
A €0.05 part that converts an unpublished damage threshold into a defined one is worth
its BOM line; a claim that the record *requires* it would be false.

---

## 4. Recommendation

> **Recommend option (a): tap the supercap rail directly into the pin-1 selector that
> ADR-029 D8 already mandates. Recommend option (c) as cheap insurance, while stating
> plainly that the datasheet does NOT make it mandatory (stated maximum 5.5 V ≥ 5.4 V
> rail top). Do NOT adopt option (b) unless a bench measurement shows the sag breaks the
> link.**

Grounds, in priority order:

1. **It is the only option that costs nothing and forces no re-freeze**, and it
   *implements* D8's already-ratified selectable pin-1 rail rather than adding a second
   rail problem on top of it.
2. **It is compatible with ADR-036's energy policy by construction.** Burst storage plus
   daylight-only TX is exactly the regime where a slowly-sagging cap rail is acceptable:
   TX is already energy-gated, and the bank is fullest in daylight when TX is permitted.
3. **It keeps the option open.** A tap is removable; a boost converter placed and routed
   is not. If the bench says the sag breaks the link, (b) can be added later with the
   measurement in hand — which is the evidence-driven order this project uses.
4. **It does not add a noise source 2 mm from a −136 dBm receiver** on the tightest board
   in the project.

**What the recommendation explicitly does *not* claim:** it does not claim the rail is
measured, does not claim +30 dBm at any state of charge below ~4.5 V, and does not claim
O5 is closed (§7).

---

## 5. Energy arithmetic

Bank: **C = 1.65 F** (2× 3.3 F in series), top voltage **5.4 V** (ADR-006, Accepted).

$$E = \tfrac{1}{2} C V^2$$

| Quantity | Value |
|---|---|
| Fully charged: ½ · 1.65 F · (5.4 V)² | **24.06 J** |
| At the module's minimum VCC (3.0 V, §6 table): ½ · 1.65 · (3.0)² | 7.43 J |
| **Usable to the module's minimum, 5.4 → 3.0 V** | **16.63 J** |
| At the in-repo LDO assumption V<sub>min</sub> = 3.5 V (`docs/POWER-BUDGET-V9-D2BE.md` §1): ½ · 1.65 · (3.5)² | 10.11 J |
| **Usable on the 3.3 V side, 5.4 → 3.5 V** | **13.95 J ≈ 14 J** (matches the budget doc's 13.9 J) |

**How long a 6 W DC TX burst can run on 16.63 J:** 16.63 J ÷ 6 W = **2.77 s**.
On the 13.95 J LDO-bound figure: 13.95 ÷ 6 = **2.33 s**.

The 6 W figure is the datasheet's own worst case: at 5 V, 433/470 MHz, 2 W the module
draws **< 1200 mA** → 5.0 V × 1.2 A = **6.0 W** (§6 table). At 868/915 MHz it is
< 800 mA → **4.0 W**; at 2.4 GHz < 900 mA → **4.5 W**. So 6 W is the 433 MHz case, which
ADR-034 makes the TX band — the correct number to size against.

**Cross-check against ADR-036's own packet arithmetic** (which this ADR does not restate,
only uses): a LoRa SF12/BW125 packet is ≈ 4 J, and a 100-byte FLRC burst at 2.6 Mbps is
≈ 2 mJ. So one full bank holds **≈ 4 SF12 packets** (16.63 ÷ 4 ≈ 4.2) or ~8000 FLRC
bursts, before any recharge. The array (2.4 W peak, ADR-006) refills 24.06 J in ≈10 s of
direct sun — i.e. the bank is a burst buffer, exactly as ADR-036 intends, not a mission
tank.

**Burst sag on the shared rail — the one number that constrains the bulk cap.**

$$\Delta V = \frac{I \cdot t}{C}$$

| Burst | ΔV on a 1.65 F bank alone |
|---|---|
| 1.2 A for 0.65 s (SF12 packet) | 1.2 × 0.65 ÷ 1.65 = **0.47 V** |
| 1.2 A for 0.31 ms (100-byte FLRC @ 2.6 Mbps) | **≈ 2.3 × 10⁻⁴ V** (negligible) |

So the **bank alone can source the long-slow packet** (0.47 V of sag is inside the 5.4 →
3.0 V window), and the FLRC burst is a rounding error against it. The local bulk cap at
the module is therefore about **suppressing the fast component** (ESR/inductance of the
run to the cap string), not about supplying the burst — which is why it may be small.
Its exact value is a **TODO(unverified)** for the schematic card, to be set from a
measured load step (ADR-029 §5 test 4: rail dip **< 20 mV**).

---

## 6. Consequences

- **Positive.** O5's topology half is decided with the cheapest, lightest, remove-able
  option; D8's pin-1 selector gains a defined 5 V source; no re-freeze; no new noise
  source; ADR-006/036 arithmetic shows the bank holds a full burst with margin.
- **Accepted cost — link budget at the bottom of the discharge.** ~3.5 dB down at 3.3 V.
  Mitigation is *policy*, not copper: ADR-036 already gates TX on stored energy, so the
  system can require near-full charge before a full-power burst (ADR-006 already says
  firmware aborts TX below 3.0 V).
- **Accepted risk — a shared rail.** The F33's TX current (up to 1.2 A) rides the same
  node as the 3.3 V LDO's input. ADR-029 §2(f) already requires per-radio ferrite + bulk
  decoupling and star returns; ADR-029 §5 test 4 (< 20 mV dip) is the acceptance number.
  **This ADR adds no relaxation of that test.**
- **Still open — cold.** The chosen buffer and this rail must be characterised at −60 °C;
  ADR-036 records that as **not done**, and it is not done here either.
- **Still open — the O5 evidence.** §7.

---

## 7. What this ADR does NOT close (O5 stays open)

O5 is resolved **at the topology level only**. The following remain **open**, and the
BOM freeze stays gated on them plus ADR-029 **O0**:

- a **5 V chain demonstrated at ≥ 1.2 A load-step capability** — not measured;
- a **3.3 V rail at ≥ 0.60 A transient** — not measured;
- **cold supercap / regulator evidence** at −60 °C — not measured (ADR-036 open item);
- the **array open-circuit voltage at −60 °C** — not in repo (**TODO(unverified)**, §2);
- the **bulk-cap value** — to be set from the measured load step (§5);
- **ADR-029 §5 test 4** (rail dip < 20 mV during a worst-case burst) — not run.

Per ADR-029 O5's own instruction, if that evidence fails the fallback is **to operate the
F33 at 3.3 V with reduced output rather than claim +30 dBm** — which option (a) *is*,
since a 3.3 V rail is exactly what the sagged cap rail becomes. Option (a) therefore
fails safe: its failure mode is a weaker link, not an unbuildable board.

---

## 8. What would falsify this

- A bench measurement showing the sagged rail breaks the link at the ranges the mission
  needs → option (b) returns, with the measurement as its justification.
- A measurement showing the cap string's top node can exceed the F33's stated 5.5 V
  maximum → option (c) becomes **mandatory**, not insurance, and this record must be
  amended to say so.
- A −60 °C characterisation showing the bank cannot deliver one burst → the rail question
  is moot until the buffer is fixed.
- An operator preference for a regulated 5 V rail for reasons outside link budget (e.g.
  wanting a state-of-charge-independent output power) → option (b), accepted with its
  mass and EMI costs on the record.

---

## 9. Ordering trap (adjacent, recorded because it is in the same money path)

The rail feeds a module whose **name is one character away from a different chip**:
`LoRa2021F33-2G4` (SEMTECH **LR2021**, ours, per ADR-029 D2) vs `LoRa1121F33-2G4`
(SEMTECH **LR1121**, a different module) — the LCSC/JLC listing
`LoRa1121F33-2G4-868MHz`. ADR-029 D2 states the wrong part **must not be ordered**.
`tracker/hardware/tools/bom_part_allowlist.py` is the mechanical gate for that trap and
is intended to run against the BOM and the board files before any JLCPCB order.
