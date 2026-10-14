# RF REVIEW — the 433 MHz TX power is the binding RF issue, and it is ~21 dB over the licence-exempt cap

> **⚠ CORRECTED 2026-10-14 — see `RF-REVIEW-433-TX-POWER-CORRECTION.md`.**
> **§1's range table below is WRONG.** It claimed *"the 300 km design slant range is not
> reachable at 10 mW ERP — it becomes ~27 km."* **Measured with the repo's own
> `tools/link_budget.py`, the 300 km link at the lawful cap still closes with 27.3 dB of
> margin** (the 2 W design has 48.4 dB). My error was applying a flat dB-to-range factor,
> which is only valid for a **zero-margin** link, to a link with **48 dB of margin**.
> **The regulatory gap itself (§1's headline and §2–§6) is UNAFFECTED and still stands** —
> the design is 20.9 dB over the cap; what changes is that **the cap does not break the
> mission.**

**Date:** 2026-10-14 · **Status:** analysis. Operator decision required.
**Trigger:** the standing goal says *"Make sure the RF decisions make sense."* This is the
one that does not, and it is arithmetic rather than opinion.

---

## 1. The gap, computed

The repo's own **`docs/LINK-BUDGET-LICENCE-EXEMPT.md`** (companion to ADR-041) states the
cap, with its source:

> *"433.05–434.79 MHz licence-exempt ERP cap: **10 mW ERP** (integral antenna)"* —
> citing ERC Recommendation 70-03 (CEPT) Annex 1, re-verified 2026-10-07.

And the board transmits:

| | value |
|---|---|
| **Design 433 TX** (LoRa2021F33-2G4) | **+33 dBm = 2 W** |
| **Licence-exempt cap** | **+10 dBm ERP = +12.15 dBm EIRP** (10 mW ERP) |
| **GAP** | **20.9 dB** |

**A 20.9 dB reduction in transmit power shortens line-of-sight range by a factor of
0.0907** (since FSPL ∝ 20·log₁₀ d):

| design range | at the licence-exempt cap |
|---:|---:|
| **300 km** | **27.2 km** |
| 100 km | 9.1 km |
| 50 km | 4.5 km |
| 20 km | 1.8 km |

So **the 300 km design slant range is not reachable at 10 mW ERP** — it becomes ~27 km.
This is not a board defect; it is a **regulatory ceiling the design currently exceeds by
~21 dB**, and it is exactly the open item our own ADR-034 carries:

> *"Legality of 2 W on 433 MHz in DE. 433.05–434.79 MHz is licence-free only at very low
> ERP; higher power implies an amateur licence."* — ADR-034, open item

## 2. Why this matters MORE than board polish

Everything else in this campaign is a fab-readiness question. **This is a "can it fly
legally" question**, and it determines the power budget, the mass budget, and the
operating concept:

- If **2 W is only lawful under an amateur licence**, then the flight is either
  (a) an amateur-licence operation with its automatic/unattended rules, or
  (b) capped at **10 mW ERP**, which changes the mission from 300 km to ~27 km.
- If a **German general assignment does permit higher power at 433 MHz**, then the design
  stands and this item closes.

**Either way it is an operator decision, not a layout fix** — and it should be settled
**before an order**, because it may change the F33 population decision (the bare
LoRa2021 at +22 dBm vs the F33 at +33 dBm), which is one of the `U_CUT`-adjacent choices
still open.

## 3. A second, related check: the cap binds only the BALLOON's TX

The link budget is careful about this and it matters for the fix:

> *"The two link directions are computed **separately** because the licence-exempt cap
> binds the balloon's transmitter (433 MHz downlink), **not** the ground's transmitter
> (2.4 GHz uplink)."*

- **433 MHz is DOWNLINK** (balloon → ground) — **capped at 10 mW ERP**.
- **2.4 GHz is UPLINK** (ground → balloon) — capped at **100 mW EIRP (20 dBm)**, and the
  **ground station may use a large antenna and amplification** (ADR-034 D1: *"the ground
  station can afford amplification and a large antenna"*).

**So the asymmetry is the lever:** the ground end can be made as sensitive and as
high-gain as we like, because the cap does not bind it. **The balloon end is the
constrained side**, and that is where the link budget must be re-derived from.

## 4. What this does NOT change

- **Nothing about the routed board.** 48/48 nets, JLC-legal geometry, all unaffected.
- **Nothing about the band split** (ADR-034: 433 TX / 2.4 RX) — that remains sound.
- The **+3 dB argument** in ADR-034 (2 W only available on the sub-GHz port) is still true
  *as a capability*; the question is whether we may **use** it.

## 5. Recommendation

1. **Resolve the legality item FIRST** — it is the gate on the power budget. Research is in
   flight; the answer decides between "design stands" and "cap at 10 mW ERP / licence
   route".
2. **If the cap binds**, re-derive the link budget from the **capped** TX and lean on the
   **ground-side** gain, which is uncapped — and re-examine whether the F33 (2 W) is even
   worth populating versus the bare LoRa2021 (+22 dBm), since **neither is licence-free
   lawful at 433 MHz** and the F33 costs power, mass and board area for a capability we
   may not legally use.
3. **Do this before the order**, because it may change the radio population.

## 6. Sources / reproduce

- `docs/LINK-BUDGET-LICENCE-EXEMPT.md` §0 (the cap and its provenance), §1 (the
  direction-split warning).
- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — the open legality item, §213–227.
- `docs/adr/041-rf-frontend-licence-exempt.md` — the companion ADR.
- `docs/2G4-LINK-BUDGET-ANALYSIS.md`, `docs/link-budget.md`.
- Arithmetic: `10·log10(2000/10) = 23.0 dB` conducted-to-ERP comparison; the **20.9 dB**
  figure above is against the **+12.15 dBm EIRP** equivalent of 10 mW ERP, so it already
  credits a dipole-equivalent balloon antenna.
