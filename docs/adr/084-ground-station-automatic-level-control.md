# ADR-084 — Automatic level control at the gateway: AGC on the 433 receive chain, telemetry-driven attenuation on the 2.4 GHz uplink

- **Status:** **Accepted by operator** (Felix, 2026-10-08) — the operator decided *"yes this is what
  we want"* to *"an AGC loop (VGA + detector) on receive, and telemetry-driven level control on
  transmit"*, and separately valued *"manual/commanded gain per flight phase gets you most of the
  benefit for none of the complexity"*. The *text* is agent-drafted. Level-control automation is an
  **enhancement**: the **manual/commanded mode is the baseline** and a first flight does not depend on
  the loop.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent, branch `design/level-control-architecture` (base `github/main` @ `09e1b69`)
- **Related (stable references):** ADR-071 (gateway design basis, full duplex), **ADR-072** (band-split
  duplex; BPF before the LNA; attenuate-don't-amplify the uplink), ADR-073 (433 downlink is the binding
  direction), ADR-075 (F33), ADR-079 (owned TQP3M9037 LNA, CONDITIONAL on its band edge), ADR-080
  (XR-613), ADR-081 (EIRP-cap invariant), ADR-082 (rate ladder), `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`.
- **Evidence:** `docs/analysis/ground-station-level-control-design.md` +
  `docs/analysis/level_control_model.py` (every numeric table) +
  `docs/analysis/render_level_control_figures.py` (figures in `docs/analysis/assets/level-control/`).
  Extends `docs/analysis/rf-shopping-list-and-duplex-architecture.md` (source branch
  `design/rf-shopping-list` @ `eea1cbc00702`) and `docs/BASE-STATION-BOARD-CHECKLIST.md`.
  Reproduce: `python3 docs/analysis/level_control_model.py`.
- **Independent review:** the two figures + the plan were submitted to `scripts/fleet/visual_consult.py`
  (`--timeout 540 --json`), **served model `gpt-6-astra`** (read back from the response). The model's own
  verdict line was **`VERDICT: REFUTE`** (round 1, 2026-10-08): *"The conditional Friis arithmetic is
  sound, but contradictory gain windows, unproven loop dynamics, insufficient TX control range and
  missing full-duplex self-interference analysis invalidate the plan's claimed coverage and safety."*
  The structured `verdict` field returned `UNPARSED` (CONFIRM/REFUTE is not the parser's vocabulary —
  parser declining, not the model disagreeing). Twelve findings were accepted and acted on (F1–F12);
  the corrections are in D4 above, the design doc §9 and the checklist. Full record:
  `docs/analysis/assets/level-control/consult-verdict.txt`.

**Numbering and collision note.** Numbers **066–083 are claimed on sibling design branches**
(066: `design/ground-station-lowpower-link` + `design/ground-station-flrc-max`; 067:
`design/ground-station-flrc-max` + `design/positioner-lowcost`; 068: `design/gain-per-dollar` +
`design/gain-per-dollar-cliff` + `design/amplifier-substitution`; 069: `design/tier0-accessible`;
070: `design/amplifier-hypothesis-check` + `design/rf-shopping-list`; **071–082**:
`design/adr-set-groundstation`; **083**: `design/rf-gaps-harmonics-diy`). `scripts/adr_next_number.py`
prints 066 because it is **branch-blind**. This record takes the fresh number **084** — verified free
**prefix-anchored against every `github/*` branch** on 2026-10-08 (`git ls-remote --heads github` → no
branch carries a `docs/adr/08[3-9]-*` other than 083 on `design/rf-gaps-harmonics-diy`; the highest
number present anywhere is 110, and 100–110 belong to the mainline set). The full table and the reason
no rename is made are in **ADR-071 §Numbering and collision note**.

---

## Context

The gateway (ADR-071) receives **433 MHz** and transmits **2.45 GHz** on **two separate antennas**
(ADR-072), and the **433 downlink is the binding direction** (ADR-073). Across a flight the received
level moves a lot: with the F33 (+33 dBm, ADR-075) and the 14.8 dBi **Diamond A-430S15R** ground
antenna, the **1 → 650 km path-loss swing is 56.26 dB** (the brief's "~56 dB",
`level_control_model.py` §2), before any fade. A receiver chain with a **fixed** gain can be centred
on only one range, so one end of the flight is either compressed (close range, the **common** overhead
pass) or starved (far range). The operator decided to **automate level control** to remove that.

Three facts constrain the solution:

1. **A level-control element is needed, and it must reach negative dB.** The operator asked *"can we
   use something like this?"* about a controllable element that can **both attenuate and amplify**.
   Verified parts exist (§Evidence): **ADL5240** (100 MHz–4 GHz, +20.3/−12 dB, 6-bit DSA 0.5 dB step,
   NF 2.8 dB @450 MHz), **ADL5243** (same + ¼ W driver), **ADL5330** (10 MHz–3 GHz, **−35…+22 dB**,
   analog). All cover **both** 433 MHz and 2.45 GHz.
2. **The VGA must go after the LNA.** Friis: `F = F1 + (F2−1)/G1`. Behind the owned **TQP3M9037**
   (+20 dB, NF 0.4 dB — ADR-079), a VGA of NF 2.8–8 dB adds only **+0.04…+0.20 dB** to the system NF;
   ahead of the LNA the same VGA adds **+2.6…+7.7 dB** (`level_control_model.py` §1). The order is
   therefore fixed by noise figure, not preference.
3. **The uplink needs attenuation, not amplification** (ADR-072 D4/INV-4). Under the ISM ceiling the
   2.4 GHz uplink is EIRP/PSD-capped; the controllable element is a **DSA**, and its control input is
   the balloon's own GNSS **range**.

## Decision

**D1 — Adopt automatic level control, with MANUAL/COMMANDED gain as the baseline.** Three modes ship:
(1) **manual/commanded** (a fixed attenuation per flight phase — the **default** and sufficient for a
first flight), (2) **telemetry-driven** TX attenuation, (3) **autonomous receive AGC** (the
enhancement). Automation is **not a first-flight dependency**.

**D2 — Receive AGC chain order is fixed: `antenna → 433 MHz BPF → LNA (TQP3M9037) → VGA → receiver`.**
The VGA sits **after** the LNA (Friis, Context §2) and **after** the BPF (ADR-072 INV-3). The AGC lives
**entirely in the 433 MHz RX path**.

**D3 — The receive loop is a DIGITAL AGC by default** — VGA (or DSA) + **log detector** (AD8318,
1 MHz–8 GHz, 70 dB) + **ADC + MCU**, for **repeatability and loggability** (the gateway serves a
fleet). An **analog AGC loop** (VGA + detector + RC loop filter) is the accepted fallback when firmware
scope is the binding constraint. Either realisation must be **defeatable to the D1 manual mode at any
time**.

**D4 — The receive loop is ASYMMETRIC: FAST attack, SLOW decay.** Attack (overload protection) steps
the gain **down within one frame**; **decay** (level tracking) releases with **τ ≈ 10–100 ms**
(≈ 1.6–16 Hz) — **below** the ~72 Hz multipath fade rate (2v/λ at 433 MHz, v = 25 m/s) and **above**
the ~0.01–1 Hz range/geometry rate. A single slow time constant is **not** sufficient (a slow attack
leaves frames exposed to overload — independent review, `docs/analysis/assets/level-control/consult-verdict.txt`).
Digital loops carry a **deadband ≥ one step (≥ 0.5 dB) + hysteresis**; both realisations carry
**anti-windup / bounded gain**. **The AGC's detector input MUST be band-limited to 433 MHz** (its own
BPF/resonator at the tap): the AD8318 is broadband, and leaked 2.45 GHz TX energy would otherwise drive
the loop to reduce gain and desense the wanted downlink (blocker-driven gain reduction).

**D5 — Transmit level control is a PRECOMPUTED range→attenuation LOOKUP TABLE, not a control loop.**
The ground MCU maps the balloon's GNSS range to a **DSA attenuation** (PE43711-class, 0–31.75 dB,
0.25 dB step) so the level presented to the balloon's 2.4 GHz receiver is **roughly constant**. A table
keyed on a slow, known input **removes the TX stability question entirely**.

**D6 — Failure containment: the AGC must not endanger the band-split duplex (ADR-072), and must not
take the downlink down silently.** The AGC is a **433-RX-only** element, so no AGC fault can move the
TX level or violate ADR-072 INV-1…5. The dangerous failure is **latching at maximum attenuation**,
which can drop the binding 433 downlink; hence (a) manual bypass on demand, (b) bounded gain register +
anti-windup, (c) a **downlink-failure watchdog** that drops to the D1 fixed gain and reports, and
(d) the **TX LUT state independent of the RX-loop state** even if one MCU serves both.

**D7 — The level-control parts are added to the base-station board checklist**
(`docs/BASE-STATION-BOARD-CHECKLIST.md`) as row items; the checklist **extends** the sibling shopping
list rather than duplicating it. No PA is added to the ISM uplink (ADR-072 INV-4).

## Invariants

- **INV-1.** The receive AGC is a **433 MHz-RX-path-only** element; it must not touch the 2.45 GHz TX
  path and must not add a cross-band coupling path (ADR-072 INV-1).
- **INV-2.** The VGA/DVGA sits **after** the LNA and **after** the 433 BPF; the BPF-before-LNA order
  (ADR-072 INV-3) is never reversed (the loop's detector must be tapped **after** the BPF).
- **INV-3.** The receive loop's bandwidth is **below the fade rate** it cannot fix and **above** the
  geometry rate it must track; it never chases fades.
- **INV-4.** **Manual/commanded mode is always available** and returns the chain to a **known fixed
  gain** — not to the loop's last state.
- **INV-5.** The TX level is set by a **static range→attenuation table**; no feedback loop closes on
  the uplink, and no PA is placed there without a documented higher legal footing (ADR-072 INV-4).

## Consequences

### Positive
- The receiver's usable window is **recentred at every range**: acceptance span rises from the
  **35 dB** a fixed gain can centre on (≈ 49 % of the 71 dB mission) to **66.5 dB (93 %)** with a
  31.5 dB DSA and **92 dB (100 %)** with the 57 dB ADL5330. The **top FLRC rate** — worst sensitivity,
  first casualty — is preserved for as long as the antenna supports it (up to **4×** the bottom-rung
  rate at the far edge).
- The VGA-after-LNA order keeps the system NF penalty at **≤ 0.2 dB**, so level control does not eat
  the rate ladder's own 1–2 dB sensitivity steps.
- A **table** (D5) removes uplink instability; a **bounded, defeatable** RX loop (D4/D6) removes the
  availability risk.

### Costs / risks
- **The board gains a detector, an ADC/MCU and a DSA/VGA** (≈ €20–40 of parts, plus bias) — see the
  checklist rows 5–8. This is new complexity on the **binding** direction.
- **Under the ISM ceiling the transmit LUT sits near 0 dB for the whole flight** (the LR2021 HF PA is
  only +12 dBm and an 11.1 dBi antenna already over-shoots the 14.26 dBm EIRP ceiling by 8.8 dB,
  `level_control_model.py` §5–6). The TX table earns its keep only at **metres-range** or **with a PA
  on a higher legal footing** — recorded honestly rather than dressed up.
- **The dynamic-range percentages depend on the assumed 35 dB receiver window**, whose top (the
  LR2021 max-input) is `TODO(unverified)` (ADR-079 open item). The *shape* of the argument is robust;
  the exact percentage is not yet.
- **ADR-079 is CONDITIONAL** on the TQP3M9037 band edge (0.1 MHz vs 0.7 GHz). If the part does not
  cover 433 MHz, this record's D2 chain (and D3/D4) must be re-placed on a 433-capable LNA.

## Open items (not assumed)

- **`TODO(unverified)`** the **LR2021 maximum usable input level** (top of the receiver window W).
- **`TODO(unverified)`** the **433 MHZ FLRC sensitivity rows** (2.4 GHz rows used as proxy).
- **`TODO(unverified)`** the **AGC detector / ADC / MCU part numbers and prices** (checklist rows 7–8).
- **`TODO(unverified)`** whether the detector is **shared** with a transmit-power monitor.
- **`TODO(unverified)`** the ADL5243 price and the ADL5330 differential-balun cost.
- **Inherited, not re-opened:** the **2.4 GHz uplink legal ceiling** defect (flat 20 dBm vs ≈14.26 dBm
  PSD, ADR-072/ADR-081 Open items) and the **measured duplex isolation / desense acceptance**
  (ADR-072). Level control does **not** substitute for either.

## Relation to other ADRs

- **Extends** ADR-072 (band-split duplex) by adding a 433-RX-only level-control element and by using
  the already-chosen DSA on the uplink; it changes **none** of ADR-072's invariants.
- **Depends on** ADR-079 (the owned LNA's place and its CONDITIONAL band edge) and ADR-073 (which
  direction is binding).
- **Complements** ADR-082 (the rate ladder is the fade mechanism; the AGC is the level mechanism) and
  ADR-075/081 (TX power and the EIRP cap).
- **Supersedes nothing.** It is the first record to own the **level-control** question.

## For future sessions

- **One-line rule:** **VGA AFTER the LNA** (Friis), **AGC bandwidth below the fade rate** and above the
  geometry rate, **transmit level from a range→attenuation TABLE**, and **manual gain is the baseline**.
- **Check first:** the **TQP3M9037 band edge** (ADR-079 D5) — it decides whether this chain stands.
- **Reproduce:** `python3 docs/analysis/level_control_model.py`;
  figures `/opt/miniconda/bin/python3 docs/analysis/render_level_control_figures.py`.
