# RF REVIEW 2 — both links close at lawful power; two stale RF assumptions found

**Date:** 2026-10-14 · **Status:** analysis + two corrections required in ADR-035.
**Continues:** `RF-REVIEW-433-TX-POWER.md` and its `-CORRECTION`.

---

## 1. BOTH directions close at 300 km, within the caps — measured

Using the repo's own `tools/link_budget.py`, SF12 / BW125, 1 dB cable:

**433 MHz DOWNLINK** (balloon → ground), at the **licence-exempt cap** (+12 dBm EIRP,
balloon +2 dBi, ground **12 dBi** Yagi):

| distance | margin |
|---:|---:|
| 50 km | 42.8 dB |
| 100 km | 36.8 dB |
| **300 km** | **27.3 dB** ✅ |

**2.4 GHz UPLINK** (ground → balloon), at the **cap** (+20 dBm EIRP, ground **12 dBi**,
balloon **6 dBi** PCB Yagi):

| distance | margin |
|---:|---:|
| 50 km | 40.0 dB |
| 100 km | 33.9 dB |
| **300 km** | **24.4 dB** ✅ |

**So the RF links are sound at lawful power in both directions** — 27.3 dB down, 24.4 dB up
at the 300 km design point. **The regulatory question is purely legal, not physical.**

## 2. FINDING A — ADR-035's isolation figure is tied to a board size we no longer have

ADR-035 is the TDM radio schedule, and it states its central safety assumption **in terms
of a board dimension**:

> *"On a ~45 × 55 mm board with U.FL pigtails, antenna-to-antenna isolation is roughly
> **15–25 dB**, so a +30 dBm (1 W) or +33 dBm (2 W) transmitter presents tens of dB above a
> neighbour receiver's noise floor."*

**And line 33: *"the schedule that lets them coexist on one ~55 × 45 mm board"*.**

**The v9 outline is now 70 × 70 mm (ADR-068 as revised).** ADR-035's isolation estimate was
derived for a board with **2475 mm²** of area; we now have **4900 mm²** — **~2× the area**,
so the antennas can be roughly **√2 × further apart** across the diagonal.

**This is not automatically good news and it must not be assumed either way:**

- **Might help:** more separation → more isolation → the schedule might relax. Isolation at
  U.FL pigtail distances does improve with separation.
- **Might not help at all:** at these distances the dominant coupling is often **not**
  free-space separation but **shared ground/power plane coupling, chassis/ground return
  currents and the pigtail routing** — none of which improves merely because the board grew.
- **Might be worse:** the board grew to **70 mm** and now carries **five** RF-relevant
  interfaces (F33 433, bare LR2021 2.4, SX1280 2.4, GNSS L1, plus the wing-tab 433
  interfaces) — **more aggressors and victims on a plane that is a shared antenna.**

**ADR-035 already names this as a falsifier:** *"A bench measurement showing
antenna-to-antenna isolation on the routed board is ≥ 40 dB (not the assumed 15–25 dB),
which would relax the one-transmitter-at-a-time [rule]."* **So the measurement is already
specified — it just has not been taken.**

**Action:** the 15–25 dB figure and the *"55 × 45 mm"* framing in ADR-035 are **stale by
dimension**. The schedule is **conservative** (one transmitter at a time), so a stale
*low* isolation estimate errs on the safe side — **but the ADR should carry the new
outline and the measurement it already calls for.**

## 3. FINDING B — TWO radios now share 2.4 GHz, and the schedule must say so

ADR-034 split the bands across **two chips** (F33 for 433 TX, bare LR2021 for 2.4 RX) and
did it correctly — it supersedes ADR-029's single-core arbiter with the right reason:

> *"The LR2021 is **half-duplex**: it cannot TX on one port while RX-ing on the other… ADR-029
> itself admits this in §3 R2: 'the two ports belong to one transceiver core, so the two
> links are mutually exclusive in time'."*

**But the board now carries THREE radios plus GNSS, and TWO of them are 2.4 GHz:**

| radio | band | role |
|---|---|---|
| `LoRa2021F33-2G4` (U2) | **433 MHz** | downlink TX |
| bare `LoRa2021` (U3) | **2.4 GHz** | uplink RX |
| `SX1280` (U4) | **2.4 GHz** | ranging |
| `MAX-M10S` | **1.575 GHz** | GNSS |

**Two 2.4 GHz radios on one board is a different coexistence problem from the one ADR-034
solved.** ADR-034's win was *"simultaneous TX and RX on separated bands"* — and that is
true for **433 vs 2.4**. It is **not** addressed for **2.4 RX vs 2.4 ranging**, where both
sit in the *same* band on the *same* board. ADR-035 does schedule ranging into dedicated
windows, so this is **probably covered** — but the ADR should state the **2.4↔2.4**
exclusivity explicitly rather than leaving it implied by a schedule table.

## 4. Recommendation

1. **The RF links are sound.** Both directions close at 300 km at lawful power. No physics
   problem; the open item is **legality**.
2. **Update ADR-035** to carry the **70 × 70 mm** outline and state that the 15–25 dB
   isolation figure was derived for the superseded 55 × 45 mm board — **stale by
   dimension**, and to be replaced by the bench measurement ADR-035 already specifies
   (falsifier: ≥ 40 dB relaxes the rule).
3. **State the 2.4 GHz ↔ 2.4 GHz exclusivity explicitly** (bare LR2021 RX vs SX1280
   ranging) rather than leaving it implied — it is a *different* coexistence case from the
   433/2.4 split ADR-034 resolved.
4. **Do not assume the bigger board helps isolation.** Plane/chassis coupling often
   dominates over free-space separation at these distances; the measurement decides.

## 5. Reproduce

```
python3 tools/link_budget.py --freq 433  --sf 12 --bw 125 --tx 12 --tx-ant 2  --rx-ant 12 --cable-loss 1 --dist 300
python3 tools/link_budget.py --freq 2400 --sf 12 --bw 125 --tx 20 --tx-ant 12 --rx-ant 6  --cable-loss 1 --dist 300
# both report OK with the margins in §1
```
