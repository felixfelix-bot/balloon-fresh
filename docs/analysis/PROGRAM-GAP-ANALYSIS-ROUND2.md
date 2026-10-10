# Program gap analysis — ROUND 2 (the operator's seven questions)

**Date:** 2026-10-10 · **Author:** manager (balloon-hermes) · **Status:** DRAFT, consultant round-2 pending
**Base document:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md` (620 lines) — this **extends** it; it does not replace it.

## §0 Method and evidence base

Three independent evidence streams, deliberately kept separate so disagreements are visible:

| Stream | What it is | Provenance |
|---|---|---|
| **E1** | The existing repo analysis base: `PROGRAM-GAP-ANALYSIS.md` + ~60 model-backed docs in `docs/analysis/` | in-repo, each has a reproduce command |
| **E2** | My own arithmetic, computed for this round to CHECK the consultants | `state/consult/cw-independent-analysis.md` |
| **E3** | Independent consultant audit on a **different model family**, reading the repo itself | `state/consult/round1-astra.md` (OpenAI `gpt-6-astra`), `round1-kimi.md` (Moonshot) |

**Rule applied throughout:** the visual consultant *grades*, it does not *measure*. Every
geometric or numeric claim it makes is checked against E2 before being repeated here.
Where the consultant and my arithmetic disagree, both are reported.

**Critical caveat inherited from this repo's own `AGENTS.md` (measured):**
`KICAD9_3DMODEL_DIR` is unset and no 3D model library is installed, so `kicad-cli pcb render`
draws **substrate + copper + silkscreen only**. Therefore **no component bodies can be seen in a
render**, and a vision model describing "where the parts are" from a render is describing
*copper and courtyards*, not physical parts. This bounds what any 3D-render consult can prove.

---

## §1 Base station

**Verdict: DESIGNED but UNMERGED, and the single most expensive gap in the program.**
There is **no base-station board**, and **none of the ground-station design work is on `main`.**

- ~**16 ground-station `design/*` branches are UNMERGED** — 62 commits, 136 file-touches
  (measured E1 §2.1). ADRs **071…084** exist *only on branches*; `main` carries the flight-board
  ADR line only (to 065). *The design program is essentially not consolidated.*
- **No control/bias/telemetry board exists** on any ref. Kanban: `PCBPROG-BASE-1` is in **triage**,
  `PCBPROG-BASE-2` (fab-ready review + operator sign-off) is **todo**.
- BOM is the most complete artifact: 18 rows, **4 OWNED**, **TO-BUY €274.58** (€441.57 with the
  LiteVNA 62). **5 required rows have no price at all** — log detector AD8318 (7), ADC/MCU (8),
  **the 2.4 GHz PA/FEM (11)**, bias/rails (14), masthead enclosure (18). Those are the real holes.
- **The 2.4 GHz transmit PA is MISSING.** Without it the uplink depends entirely on ground-side
  gain. This is the one RF block with no part selected.
- **`TQP3M9037` 433 MHz coverage is DISPUTED** (E1 §2 row 2 / ADR-079 D5) — the LNA that the whole
  433 RX chain is built around may not actually cover 433 MHz. Nobody has measured it.
- **No RF bench instruments.** LiteVNA 62 is a *to-buy* row (€166.99); the Red Pitaya is
  **IF-only** (DC–60 MHz, ADR-080) and the XR-613 divider is resistive (≈6 dB, no array gain).
  So passives cannot currently be verified at either band.

**Gap:** the ground station is a *written design with a good BOM* and **zero fabricated hardware**,
parked on unmerged branches.

---

## §2 Balloon pre-stretching

**Verdict: protocol EXISTS, rig EXISTS (breadboard), the BOARD DOES NOT EXIST.**

- Written protocol: `docs/PRE-STRETCHING-PROTOCOL.md` (9-step Yokohama; **circumference is the
  control variable, not pressure**) and `docs/PRESSURE-TEST-PLAN.md`.
- Working firmware: `tools/balloon_pressure_test/` (ESP-IDF; BMP280 **or** MS5611 auto-detected at
  boot) + `plot_pressure.py` (leak rate + verdict). Thresholds <0.5 mbar/h very good, >5 reject.
- **Missing:** the board (no schematic/layout/BOM anywhere, on any ref); pump/valve driver and
  automation; **over-pressure protection / safety interlock** — and over-inflation is *the* failure
  mode the protocol itself names; enclosure + sealed pressure tap.
- **Sensor-class inconsistency:** the bench uses **BMP280 (300–1100 mbar, ground only)** while the
  flight board carries **MS5611 (10–1200 mbar)**. A bench rig that cannot span the flight range
  cannot transfer its calibration. **Bench should use the part that flies.**
- Kanban: `t_c561ea2d` (ESP32 pre-stretch/test rig board) is **blocked**;
  `PCBPROG-PRE-1/2/3` (spec → route → fab pack) are all **todo**.
- **`PCBPROG-0a` — the ADR-063 `S_crack` coupon test — is `scheduled` and is HUMAN/BENCH. It is
  NOT DONE.** Per ADR-063 §D4: support a 78.55 × 38.90 × 0.21 mm cell at its two ends over a gap
  S, load to 1 g / 2 g, increase S until it cracks, record `S_crack`, repeat cold-soaked at ≈ −55 °C,
  and require `pitch ≤ S_crack`. **Until `S_crack` is measured, the wing rib pitch is unjustified**
  and the conservative-hub decision rests on an unmeasured number.

---

## §3 Antennas, amplifiers, analogue

**Verdict: the LINK CLOSES EASILY. Power is not the binding constraint — mass is.**

My arithmetic (E2), FSPL = 32.44 + 20log10(f_MHz) + 20log10(d_km):

| Link | FSPL @300 km |
|---|---|
| 433 MHz | **134.7 dB** |
| 2400 MHz | **149.6 dB** |

The 14.9 dB band difference is the single biggest lever in the whole budget.

Sensitivity for 2.6 Mbit in a 2 MHz channel:
`-174 + 10log10(2e6) + NF + SNR_req` = `-101.0 + NF` → **-99.5 dBm** at NF 1.5 dB
(ZX60-P103LN+ 0.5 dB + ~1 dB feed/mix). Shannon floor is 1.65 dB SNR; carry 10 dB in-channel.

Solving `Ptx + Gtx + Grx ≥ 35.2 dB` (433) / `50.1 dB` (2.4):
- Balloon→ground 433 with a 20 dBi ground Yagi: **Ptx = 15.2 dBm = 33 mW.**
- Ground→balloon 2.4 with 100 W + a 24 dBi dish into a 0 dBi payload antenna:
  **Prx = −75.6 dBm vs −99.5 required → 24 dB margin.**

**⇒ The cheapest dB is always on the GROUND. The balloon should not carry power it doesn't need.**
This also makes the amateur 750 W / 75 W limits largely irrelevant to closing the link — they
become a *ceiling*, not a requirement.

### 3.1 NEW FINDING — 2 MHz FLRC does not fit in the 433 MHz band

The European 433 allocation is **433.05–434.79 MHz = 1.74 MHz wide**. An FLRC mode with **2 MHz
occupied bandwidth cannot fit inside it** — the signal spills outside the allocation.

**Consequences that follow from band edges, not from the radio:**
1. The **2.6 Mbit payload rate must ride the 2.4 GHz link** (83.5 MHz of spectrum there).
2. On 433 the widest defensible FLRC setting is **1.3 MHz** (or 0.65 MHz), which fits inside
   1.74 MHz with filter roll-off.
3. The 433 link therefore carries a **lower rate** (uplink / command path), which is consistent
   with the stated intent that the two bands not interfere.

**This must be settled before the duplexer/filter design is frozen.** If the current plan has
2.6 Mbit FLRC on 433, it is illegal and will not work as designed.
TODO(unverified): exact ERC/REC 70-03 duty-cycle/power limits and the airborne-use question —
consultant round-2 to cite a source.

### 3.2 Duplexing

Full duplex in one aperture needs the relay to reject its own transmitter. The repo's position is
**band-split duplexing (no circulator)** — correct for a two-band bent pipe, and cheaper than a
circulator. A €3 relay T/R switch remains **disallowed**. Open: the actual filter isolation
achievable at the 1.74 MHz-wide 433 band edge, and whether a **shared dual-band dish**
(`docs/analysis/dualband-single-dish.md`) beats two separate apertures for cost/mass.

---

## §4 High-power and low-power version of the balloon

**Verdict: the two versions are a LEGAL distinction, not an RF one — and the LOW-power
(unlicensed) version is the harder engineering problem.**

From §3 the link closes with **33 mW** at the balloon on 433. So "high power" buys *margin and
robustness*, never *reach*. Two things follow:

- **The licensed version** (German Class A) may use far more power, but **flight mass and the
  onboard power budget bound it long before the licence does.** 750 W PEP on a pico balloon is
  not a design option. Realistically "high power" here means **tens to hundreds of mW**, chosen for
  fade margin at low elevation angles — exactly where the 300 km path is weakest.
- **The unlicensed version** must live inside the generic 433 / 2.4 GHz rules — **≈10 mW ERP with a
  duty-cycle limit on 433**, and ≈100 mW EIRP on 2.4 GHz. That is *below* what the link wants for
  comfortable margin, so it needs the bigger ground antenna and possibly a narrower mode.

**The gap nobody has closed:** the phrase *"anyone can deploy without permission"* is in tension
with generic ISM rules, which **do not generally permit transmission from an airborne platform**.
An unlicensed balloon relaying between two ground stations is not the use case those rules were
written for. TODO(unverified) — consultant round-2 to cite the actual rule text.

Mass is common to both: every gram spent on radio hardware is a gram not spent on envelope or
battery. **The correct split is: identical airborne RF, different ground-side power.** That keeps
one flight build and one flight qualification.

---

## §5 Bang for the buck — cost and performance

**Verdict: the money is in the right place (ground), but a third of the budget is unknown.**

- **Directing rule from §3: the cheapest decibel is always on the ground.** Balloon mass is the
  expensive commodity (it costs envelope volume, helium, and battery), ground gain costs only euros.
  So every € should buy ground aperture and low ground NF.
- **Known BOM:** 18 rows, 4 OWNED, **€274.58 TO-BUY** (€441.57 incl. LiteVNA 62). The single
  largest line is the **VNA at €166.99 = 38% of the BOM** — and it is *justified*, because without
  it **not one passive can be verified at either band** (§1). Buying it is buying the ability to
  verify, not a component.
- **5 required rows carry NO PRICE** (log detector, ADC/MCU, **2.4 GHz PA**, bias/rails,
  enclosure). The PA is the only *missing RF block*. **The budget is therefore not actually known**
  — €274.58 is a floor, not an estimate.
- **The cliff:** `docs/analysis/gain-per-dollar-cliff.md` and `gain_per_dollar_cliff_model.py`
  exist precisely because gain-per-euro falls off a cliff past a certain aperture. That model is the
  right instrument for this decision and should be run for the **two-aperture vs shared-dish** choice.
- **Where money is likely wasted:** two separate apertures (Yagi + log-periodic) that must be
  boresighted and separately mounted, when `dualband-single-dish.md` already explores one dish for
  both bands. One mount, one positioner, one wind load beats two of everything.

---

## §6 3D design for the antenna tracker — can it be part of the base station?

**Verdict: YES — and it must be. But it is an assembly in TWO enclosures, not one.**

**The tracking requirement is trivial; the mechanical requirement is not.** My arithmetic (E2):

```
balloon at 300 km, ground speed 50 km/h (14 m/s)
angular rate = 14 / 300000 = 4.7e-5 rad/s = 0.0027 deg/s
```

A full sweep of the sky takes hours. **Tracking is not a servo problem.** What actually matters:

- **Pointing accuracy and backlash** — 0.1° of error is ~500 m of miss at 300 km, which is fine;
  but backlash after a direction reversal is the thing that eats margin over a pass.
- **Wind load.** A 20 dBi Yagi at 433 MHz is **~4 m long with a ~2 m boom** — a large wind sail.
  The positioner spec is therefore **stiffness and holding torque, not speed.** (E1
  `positioner-lowcost-3dprinted.md` + `positioner_lowcost_model.py` exist but are **UNMERGED** —
  ADRs 076/077/078.)

**What must co-locate, and the conflict that decides the architecture:**

| Must sit together | Why |
|---|---|
| dish/Yagi + positioner + mast | pointing |
| **masthead LNA** | feedline loss **degrades NF 1:1**; 0.76 dB/10 m at 433 (LMR-400 class) — put the LNA at the antenna, not in the shack |
| band-split duplexer | one aperture, two bands |
| weatherproofing, grounding, lightning path | survivability |

**The conflict this exposes:** a masthead LNA, a DSA, a log detector, an ADC/MCU and a bias network
(§1 rows 3,5,6,7,8,14) all want to be **at the masthead**, while the control PC wants to be indoors.
**That is an argument for splitting the "base-station board" into a MASTHEAD RF/bias/telemetry board
plus a SHACK controller board** — a decision the current single-board framing does not express, and
one that must be made before the board is designed. Cable strain over the rotation range (loop or
slip ring), and boresighting two apertures if the single-dish route is not taken, are the other two
mechanical gaps.

---

## §7 What else is being overlooked (reliability and success)

Ordered by my judgement of severity. Items marked **[NEW]** were not in the base document.

1. **[NEW] The ground-station design is unmerged and unarchived.** ~16 `design/*` branches, 62
   commits, 136 files, ADRs 071…084 — **none on `main`**. A branch is not a design of record. This
   will rot, and future sessions will re-derive work that already exists. **Highest severity.**
2. **[NEW] A vision review of a PCB render proves less than it appears to.** `KICAD9_3DMODEL_DIR`
   is unset and no 3D library is installed, so `kicad-cli pcb render` emits **substrate + copper +
   silkscreen only — no component bodies**. Any "the parts look well placed" judgement made from a
   render is really a judgement about **copper and courtyards**. The repo's own `AGENTS.md` says
   *never infer component bodies from a render, and never trust a vision description of one*.
   Independent confirmation cost nothing: it is a config fact, not an opinion.
3. **`S_crack` is unmeasured** (`PCBPROG-0a`, HUMAN/BENCH, `scheduled`). The wing rib pitch and the
   conservative-hub decision both rest on a number nobody has taken. ADR-063 §D4 defines the test.
4. **No 2.4 GHz PA selected** — the single missing RF block (§5).
5. **[NEW] The pre-stretch rig has no over-pressure interlock.** The protocol names over-inflation
   as the destructive failure mode; the rig is a breadboard with no relief, no interlock, no
   soft-start. A bench rig that can destroy an envelope is a reliability risk *on the ground*.
6. **Sensor-class mismatch** — bench BMP280 (300–1100 mbar, ground only) vs flight MS5611
   (10–1200 mbar). The bench cannot span the flight range, so its calibration does not transfer.
7. **[NEW] The wing board has 0 of 12 footprints with courtyards** (measured). Without courtyards,
   "0 overlap violations" is **not evidence** — clearance is unverifiable by construction. The hub
   v9 board by contrast has 39/39 and 0 overlaps, so the hub is genuinely clean. This asymmetry is
   a real per-board gap, not a cosmetic one.
8. **Nothing is RF-measured.** No VNA until the €166.99 LiteVNA is bought; the Red Pitaya is
   IF-only. Passives, filter rejection and duplexer isolation are all currently **unverified claims**.
9. **[NEW] Redundancy is asserted as a design principle but not implemented in the link.** The
   operator's rule is *"include sufficient redundancy… carry more panels than we need"*. Panels
   aside, there is **one radio, one MCU, one battery, no second path**. For a relay whose whole
   purpose is availability, the absence of any fallback (e.g. a low-rate beacon or a second band
   path) is a structural gap.
10. **Legal: airborne unlicensed operation and cross-border coordination remain open** (§4).
11. **Descent, termination and recovery** — not evidenced in what I read; needs its own audit.
    A pico balloon that cannot be terminated is a liability, and one that cannot be found is a
    lost payload.

---

## §8 Prioritised gap list

| # | Gap | Severity | State |
|---:|---|---|---|
| 1 | Ground-station design unmerged (~16 branches, ADRs 071–084) | **critical** | open |
| 2 | No base-station board at all (BASE-1 triage, BASE-2 todo) | **critical** | open |
| 3 | 2 MHz FLRC cannot fit the 1.74 MHz-wide 433 band | **critical** | **[NEW]**, settlement needed before filter freeze |
| 4 | No 2.4 GHz PA/FEM selected → uplink block missing | high | open, unpriced |
| 5 | `S_crack` unmeasured → rib pitch unjustified | high | scheduled, HUMAN/BENCH |
| 6 | Pre-stretch board absent; no over-pressure interlock | high | planned only |
| 7 | Board split masthead vs shack not decided | high | **[NEW]** |
| 8 | No RF verification hardware (LiteVNA unbought) | high | to-buy |
| 9 | Wing board 0/12 courtyards → clearance unverifiable | medium | **[NEW]**, measured |
| 10 | Tracker positioner design unmerged (ADRs 076–078) | medium | open |
| 11 | Bench/flight sensor class mismatch (BMP280 vs MS5611) | medium | undecided |
| 12 | Airborne unlicensed legality + cross-border | medium | TODO(unverified) |
| 13 | No link redundancy / second path | medium | **[NEW]** |
| 14 | Descent, termination, recovery not evidenced | medium | audit needed |

## §9 The five things most likely to make this project fail

1. **The design never consolidates.** 16 unmerged branches holding the entire ground-station
   design is how a project dies of success — every session re-derives, nothing is authoritative,
   and a fabricated board is built from a branch nobody reviewed.
2. **Fabricating a board against an unsettled band plan.** If 2 MHz FLRC on 433 is baked into the
   duplexer/filter design, the hardware is wrong at the fab stage and the money is spent.
3. **The envelope is destroyed on the bench.** No over-pressure interlock on a rig whose stated
   failure mode is over-inflation, with a control variable (circumference) that is easy to overshoot.
4. **`S_crack` never gets measured**, so the mechanical design is frozen on an assumption and the
   first flight is the test — which is the most expensive possible way to measure it.
5. **The unlicensed version is not actually legal to fly.** Building a mass-market version on a
   premise (generic ISM rules permit airborne relay) that nobody has verified against the rule text.

## §10 What I could not verify (honest limits)

- Exact **ERC/REC 70-03** duty-cycle/power figures and the airborne-use clause → `TODO(unverified)`.
- German **AFuV** 750 W / 75 W Class-A figures are carried as *believed*; not cited to a primary
  source in this round.
- Whether the current design actually places **2.6 Mbit FLRC on 433** — if it does, §3.1 is a live
  defect; if the downlink is already 2.4 GHz, §3.1 is only a documented constraint.
- **No 3D render was used as evidence in this document.** Per §7.2 a render cannot show component
  bodies in this environment, so a spatial review of one would have been unfounded.
- Consultant round-2 (`round1-astra.md`, `round1-kimi.md`) was still running when this was written;
  its findings are to be appended as §11 rather than paraphrased into the sections above.

## §11 Consultant audit round 1 — PARTIAL (both killed by the wall-clock ceiling)

**Honest status: the consultant audit did NOT complete.** Two independent consultants were given the
mission brief and read access to the repo:

| Consultant | Family | Model served | Outcome |
|---|---|---|---|
| astra-consultant | **OpenAI** (spatial/visual lane) | `gpt-6-astra` (probe HTTP 200) | **killed at 1500 s**, no final report |
| kimi-consultant | **Moonshot** (cross-family) | kimi | **killed at 1500 s**, no final report |

Raw transcripts: `state/consult/round1-astra.md` (11.7 kB), `round1-kimi.md` (187 kB, tool trace only).
**Neither produced a verdict, a structured gap list, or its top-5 failure list.** What exists is
astra's *interim* narration, which contained three concrete, independently checkable findings.

### 11.1 Claims raised by the OpenAI consultant (TO VERIFY — not accepted)

1. **The flight schedule separates transmit and receive windows, contradicting the full-duplex
   requirement.** If true, the timing plan cannot deliver a bent pipe as specified — a bent pipe is
   simultaneous by definition. **Severity: high.** Verify: read the flight-schedule document and the
   duplexer/band-plan section together and check whether TX and RX are time-shared.
2. **Long-range uplink link budgets use LoRa sensitivity while the mission calls for high-rate
   relay service.** This is the most dangerous class of error: LoRa sensitivity at SF12 / 125 kHz is
   on the order of **−137 dBm**, whereas a **2 MHz high-rate** receiver needs **−99.5 dBm** (§3).
   Mixing the two inflates a budget by **tens of dB** and makes an impossible link look comfortable.
   **Severity: high.** Verify: grep every link budget for the sensitivity figure used and confirm it
   matches the *mode actually flown*.
3. **A sign error in the leak-test temperature compensation.** Actionable and specific; lands in the
   pre-stretch tooling. **Severity: medium.** Verify: read the compensation term in
   `tools/balloon_pressure_test/` and check the sign against the ideal-gas relation.

**None of these is accepted into §1–§8 as a finding.** They are recorded because each is specific
enough to be settled by reading one file, and each would change a design decision if true. Per the
standing rule, the consultant *grades*; the manager must *measure*. Verification of all three is
listed as immediate follow-up work.

### 11.2 Lesson recorded

A **1500 s ceiling is too short for a whole-program audit** — both consultants died mid-investigation
after spending their budget reading. The audit must be **scoped into narrower per-area consults**
(base station / prestretch / RF / mechanical / legal), each small enough to finish. Re-running as
five focused consults is the correct next step; one monolithic consult wastes the whole window.
The six delegate sweeps that fed this document had the same failure mode (they did not return).

## Appendix — reproduce

```bash
# horizon / FSPL / sensitivity arithmetic
python3 -c "import math;print(4.12*math.sqrt(12000), 32.44+20*math.log10(433)+20*math.log10(300))"
# board truth
kicad-cli pcb drc --format json board.kicad_pcb        # referee
python3 scripts/pcb_floorplan.py grade board.kicad_pcb --intent intent.json
# unmerged design branches
git -C ~/repos/balloon-fresh for-each-ref --format='%(refname:short)' refs/heads refs/remotes | grep 'design/'
```
