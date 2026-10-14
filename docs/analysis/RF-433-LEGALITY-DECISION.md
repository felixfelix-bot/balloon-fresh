# DECISION PACKAGE — 433 MHz legality: 2 W is NOT licence-free legal; the cost is DATA RATE, not range

**Date:** 2026-10-14 · **Status:** operator decision required. Closes ADR-034's open item.
**Source:** `~/RF-433MHZ-DE-LEGALITY.md` (498 lines, 6 explicit UNVERIFIED markers).
**Supersedes/corrects:** `RF-REVIEW-433-TX-POWER.md` §1 range table **and** its
`-CORRECTION` — see §3, the consultant gave the *right* framing which neither of mine had.

---

## 0. The headline

**2 W / +33 dBm on 433 MHz is NOT licence-free legal in Germany.** And the amateur route is
**blocked for an unattended drifting balloon** — *not by power, but by **location***.

**But the mission survives.** The 20.85 dB cut **kills the high-rate FLRC downlink** and
**does not kill the 300 km link**. LoRa SF12 still closes 300 km with **~32 dB margin** at
the lawful 10 mW ERP. **The design's problem is data rate, not range.**

## 1. The lawful ceiling, verbatim from the instrument

**Vfg. 91/2025** (Nov 2025), the current BNetzA SRD general assignment:

| | |
|---|---|
| Band | **433.05–434.79 MHz** |
| Class | *nicht näher spezifizierte Anwendungen* (**non-specific SRD** — a balloon telemetry beacon fits) |
| **Max power** | **10 mW ERP = +10 dBm ERP = +12.15 dBm EIRP** |
| Duty cycle | **optional** under the German national row **D44a/D44b/D45c** (Tabelle 3), which the assignment states may be used *"sowohl mit … Tabelle 2 als auch mit den weniger strengen nationalen Bestimmungen gemäß Tabelle 3"* — i.e. **≤ 10 % duty under 44b, or ≥ ≤ 100 % duty with no duty condition under the national row** |
| Footing | § 210 TKG — non-exclusive, non-interfering, unprotected |

**Two circulating claims it rules out:**

- **There is NO "integral antenna" requirement on this band.** Only PMR446 has that in this
  instrument. *(Our own `LINK-BUDGET-LICENCE-EXEMPT.md` cited "integral antenna" from a
  secondary source — that citation is wrong.)*
- **"433 MHz is ISM, so any power is free" is wrong.** ISM general assignment **Vfg.
  76/2003** allocates the band for **generation and LOCAL use of RF energy**, explicitly
  **not data transmission** — it cannot legalise a telemetry transmitter.

**25 general assignments reviewed; none permits ~2 W, and none mentions balloons or
radiosondes.** The nearest, Frequenzplan 247005 *Fernwirkfunk*, is **0.5 W ERP** — still
6.85 dB short — **and it is a licensed service, not a general assignment.**

**EN 300 220-2 V3.3.1 (2025-03)** caps at **500 mW e.r.p.** in its own scope — so 2 W is
**4× outside the standard** before the assignment is even consulted.

## 2. Why the amateur route does not rescue it

433 MHz **is** a genuine German amateur band (430–440 MHz), so this is **not a spectrum
problem — it is an operating-model problem.** Three independent blockers:

1. **AFuV § 13 Abs. 1** — a remotely-controlled or **automatically operating** amateur
   station may be operated **only at the location listed in its callsign assignment**.
   *"This amateur station may be operated only at the location listed in the callsign
   assignment."* A **drifting balloon cannot satisfy a fixed Standort.** **This is the legal
   blocker, and it is fatal.**
2. **AFuV § 13 Abs. 2** requires a **site-specific compatibility assessment**
   (*standortbezogene Verträglichkeitsuntersuchung*) — again location-bound.
3. **§ 11 Abs. 6** — no simultaneous operation from two locations on one callsign. A balloon
   300 km away while the shack is on air is *two locations*.

*(Amateur power itself would be fine: 50 W ERP allowed for automatic stations — 17 dB of
headroom over 2 W. But blocker 1 makes the power question moot.)*

## 3. What it costs — and the framing **both** of my analyses got wrong

| | |
|---|---|
| Conducted design power | +33.0 dBm (2 W) |
| Lawful ceiling | +10 dBm ERP = **+12.15 dBm EIRP** |
| **Reduction required** | **20.85 dB** (EIRP basis) / 23.0 dB (ERP basis) |

**My first document** claimed 300 km → 27 km. **My correction** (using `link_budget.py`)
said 300 km still closes at 27.3 dB margin. **Both were answering a different question from
the one that matters.** The consultant's framing is the correct one:

| mode | sensitivity | margin at 300 km | max range (0 dB margin) |
|---|---:|---:|---:|
| **FLRC 2.6 Mbit** | −100.5 dBm | **−10.1 dB — FAILS** | ~43 km |
| **FLRC 650 kbit** | −107.0 dBm | **−3.6 dB — FAILS** | ~199 km |
| **LoRa SF12 / BW62.5 kHz** | ≈ −143 dBm | **+32.4 dB — PASSES** | horizon-limited |

**The 20.85 dB cut kills the high-rate FLRC downlink and leaves the low-rate LoRa link with
32 dB of margin.** My "27 km" was true **for FLRC at constant margin**; my "it closes" was
true **for LoRa**. Neither alone was the answer. **The trade is data rate for legality.**

**Duty cycle is a non-issue** under the national row. At SF12/BW125, airtime is ~9 s per
packet, so even a 10 % cap permits **a packet roughly every 90 s** — ample for a beacon.

## 4. What this means for the board (and why it changes the ORDER decision)

**Nothing about the routed board changes** — the F33 site, the bare LoRa2021 site and the
routing are all unaffected; the power is a firmware/register setting.

**But it changes the radio-population argument decisively:**

- **The F33's headline +33 dBm (2 W) is unusable without an amateur licence we cannot hold
  for a drifting balloon.** Its *practical* lawful operating point is **≤ +12.15 dBm EIRP**
  — the same ceiling the bare LoRa2021 also exceeds (+22 dBm by ~10 dB). **Both parts must be
  backed off to the cap.**
- So the F33's extra 11 dB of capability **buys nothing lawful on 433 MHz** — while costing
  **power, mass, board area and a 5 V pre-regulator rail**.
- **This strengthens the case for the cheap radio**, and it should be settled **before the
  order** because it may change the population.

**Caveat, stated as the consultant did:** this is a **statutory reading**, not an authority
confirmation. The favourable national row is a table interpretation. **Put the operating
point to the BNetzA in writing before flying.**

## 5. Recommendation

1. **Design the 433 downlink around the 10 mW ERP ceiling** — plan the mission as a
   **low-rate LoRa beacon**, not a high-rate FLRC downlink. Range is not the constraint;
   **data rate is.**
2. **Use the German national row (D44b) footing** — 10 mW ERP with the duty/bandwidth
   conditions waived — so the beacon is not duty-limited.
3. **Re-decide the F33 population before ordering**: its 2 W capability is unusable for a
   licence-free drifting balloon, so weigh its **power/mass/area/pre-regulator cost** against
   a bare LoRa2021 that is also backed off to the same ceiling.
4. **Correct two repo citations**: `LINK-BUDGET-LICENCE-EXEMPT.md`'s "integral antenna"
   requirement does not exist on this band; and the 27 km figure applies to **FLRC at
   constant margin**, not to the LoRa link.
5. **Write to the BNetzA** to confirm the operating point before the first flight.
