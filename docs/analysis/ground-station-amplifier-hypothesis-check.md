# Ground-station AMPLIFIER hypothesis — verification of the five operator questions

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is an analysis in
> `docs/analysis/`. It is **not** an ADR, **not** an operator decision, and it authorises
> no order, no fab freeze and no change to any board, BOM or schematic. The companion ADR
> (`docs/adr/069-ground-station-amplifier-hypothesis.md`) is **Proposed** and is only
> written because the analysis reaches a reachable decision (§0.6).
>
> **Design only.** Nothing is ordered. `AGENTS.md` untouched.

| Field | Value |
|---|---|
| **Date** | 2026-10-08 |
| **Branch** | `design/amplifier-hypothesis-check` |
| **Worktree** | `/home/c03rad0r/worktrees/bf-ampcheck` |
| **Base commit** | `09e1b69` (`github/main`) |
| **Author** | Hermes Agent (subagent), for the operator |
| **Repro command** | `python3 docs/analysis/ground_station_amplifier_hypothesis_model.py` — prints every numeric table below verbatim |
| **Lens** | RF system engineering: receive-chain noise temperature (Friis), array/combining theory, T/R isolation, band allocation, €/dB. I do **not** re-derive the antenna prices, reference constants, link-budget sensitivities, wind/torque model or positioner menu — I read them from the four prior branches below. |
| **Scope** | The **ground station** and the question of whether an amplifier-led design (the operator already owns a 2.4 GHz circulator and a 2.4 GHz amplifier) beats the F33-on-balloon route. |
| **Out of scope** | Procurement; the positioner mechanics; the 2.4 GHz feed detail; regulatory licensing (ADR-039/041). |
| **Read first (prior art — BUILT ON, not re-derived)** | `design/gain-per-dollar` (`0ea36b4`) → `docs/analysis/ground-station-gain-per-dollar.md` + ADR-068 (**the €/dB metric and the Yagi-beats-dish result**); `design/ground-station-flrc-max` (`4ecbf5c`) → `docs/analysis/ground-station-flrc-max-throughput.md` + ADR-067 (**the F33 trade, mesh/wind, the rate ladder**); `design/ground-station-bom` (`283cad72`) → `docs/analysis/ground-station-bom-candidates.md` (**every antenna/rotator/coax price + URL**); `design/positioner-lowcost` (`b74bf5f6`) → `docs/analysis/positioner-lowcost-3dprinted.md` (**DIY tracker, wind, beam budget**); `design/ground-station-lowpower-link` (`4b90be94`) → ADR-066 (**LoRa vs FLRC, the negative required uplink ground gain**). |

Every figure is **SOURCED** (vendor URL / repo path), **COMPUTED** (formula + script shown),
a labelled **ESTIMATE** (basis named), or an explicit **`TODO(unverified)`**. No price, part
number, gain or datasheet value in this document was invented. All external fetches used a
browser User-Agent + `curl --compressed`; search engines were captcha-gated after the first
attempt (measured: `html.duckduckgo.com` → HTTP 202), so **everything is from a direct
vendor/Wikipedia fetch**, as the repo's sourcing rule requires.

---

## 0. Answer first

### 0.1 The five answers, one line each

| # | The operator asked | Verdict | Number |
|---|---|---|---|
| **Q1** | *"An amplifier makes sense on the transmitter but NOT on the receiver, right?"* | **PREMISE WRONG** | An LNA buys **+6.8 … +12.3 dB** of system noise temperature (central case **+9.7 dB**) — not zero. What an LNA **cannot** buy is the **~4.0 dB** (433 MHz) / **~1.5–2.8 dB** (2.4 GHz) of *antenna* noise temperature that cold-sky directivity provides. They are **additive**, not alternatives. |
| **Q2** | *Yagi array: cost, bandwidth, coupling, beam, $/dB?* | **DO NOT ARRAY** | A practical 433 Yagi is a **2–3 % (≈9–13 MHz)** antenna (vendor bands: Diamond **2.30 %/10 MHz**, Sirio **16.09 %** claimed coverage). A 2-bay costs **€228.40 marginal for +3.0 dB = €76/dB**; a 4-bay **€562.40 for +6.0 dB = €94/dB**. A 2-bay narrows the stacked-plane beam **10 % (14 dBi element) to 32 % (3-el)**; a 4-bay **33 %**. |
| **Q3** | *"One cheap tracker per Yagi, combined"?* | **ADDS COVERAGE, NOT GAIN** | Incoherent power combining of N branches = **+0.00 dB** (N× signal **AND** N× noise). Coherent combining and MRC each give **+10·log₁₀N** (**+3.01 dB** N=2, **+6.02 dB** N=4) but both need **per-branch phase coherence** (and MRC needs **N complete receivers**). **Multi-sector coverage** = **0 dB gain**, and it is the *only* useful form of the operator's idea. |
| **Q4** | *Can external gain control fix balloon-RX overdrive?* | **MANAGEABLE — but not needed** | With a **+33 dBm** ground PA on a 12.4 dBi Yagi the balloon's LR2021-class RX compresses inside **≈14.5 m** and hard-overloads inside **≈1.4 m** (at the repo's **measured** saturation behaviour). A step attenuator (€24.50–39.00) is partial; a VGA + detector + MCU (€40–120 ESTIMATE) or a **downlink-RSSI closed loop works fully** — but the overdrive exists only because the PA is oversized **~36 dB** for its own link. |
| **Q5** | *Re-cost with the owned 2.4 GHz amp + circulator* | **DO-NOT-BUILD** | The owned hardware is in the **wrong band**: it can only amplify the **2.4 GHz uplink**, which already closes with **+23.1 dB** of surplus (omni at +20 dBm) and up to **+36.1 dB** with a +33 dBm PA. The circulator does **not** solve T/R for the committed 433/2.4 GHz split (different bands → a diplexer problem), and a single **~20 dB** circulator is **not enough** isolation for a same-band +33 dBm front end (+13.5 dBm still reaches the RX port). |

### 0.2 The verdict

> **DO-NOT-BUILD the amplifier-led ground station.**
>
> **BUILD** (consistent with the four prior studies): **(1)** the **F33 module on the balloon**
> (~USD 8, +20 dB, **0.40 USD/dB**) — the bar; **(2)** a **433 MHz masthead LNA** as the
> receive-side device it is — this is the *one* ground amplifier that does something, and it
> is a **receive** amplifier, worth **+9.7 dB of T_sys for €257 = €26.4 per needed dB**;
> **(3)** a **single Yagi** (not an array, not a dish) on the DIY tracker.
>
> **DO NOT**: amplify the 2.4 GHz uplink; expect the owned 2.4 GHz circulator to solve T/R;
> build a Yagi array for cheap gain (€76–€94/dB **and** a narrower beam); or expect
> "one tracker per Yagi, combined" to add gain.

### 0.3 The five findings that carry it

1. **The operator's Q1 premise inverts the truth, and the inversion is worth ~10 dB.**
   An LNA is the standard, cheapest way to buy receive sensitivity precisely *because* it
   sets the system noise figure (Friis cascade). Against the bracket in §1 it buys
   **+6.8 … +12.3 dB**, not zero. What it genuinely cannot buy is the **~4.0 dB** of lower
   *antenna* noise temperature that a cold-sky dish supplies — and that part is worth less
   than the LNA, so the premise is wrong in the direction that costs money.

2. **The 433 MHz LNA is the ONLY ground amplifier in this study that buys needed dB — and it
   is a RECEIVE amplifier.** The priced, fully-specified part is
   **SSB Electronic LNA ISM 433 MHz: 20 dB gain, 0.7 dB NF, OIP3 +32 dBm, €257.00**
   ([wimo.com/en/ssb-70cm-ism-lna](https://www.wimo.com/en/ssb-70cm-ism-lna)). Note it is
   **433–435 MHz only (0.46 %)** — narrower than the Yagi, so it *sets* the receive system
   bandwidth (§2.1).

3. **A Yagi array is ~€76–94 per dB and points worse.** A 2-way 430 MHz 2000 W splitter is
   **€61.40** and a 70 cm phase line **€63.00** ([WiMo power splitters/phasing harnesses](https://www.wimo.com/en/accessories/antenna-accessories/power-splitter-phasing-harnesses)),
   so the marginal cost of the second bay is the second antenna (€155) + harness, against a
   hard-won +3.0 dB. That is **2.9×–3.6×** the F33's per-dB cost, before the wind/torque
   consequence.

4. **"One cheap tracker per Yagi, combined" adds coverage, not gain.** The signal bookkeeping
   is unambiguous: incoherent power combining gives **N× signal and N× noise = +0.00 dB**.
   Only *coherent* combining (phased array or MRC) gives 10·log₁₀N, and both **require
   per-branch phase coherence** — which separate trackers guarantee you do *not* have.
   The useful reading of the operator's idea is **multi-sector coverage**: **0 dB gain**, but
   it **removes the precision-tracking requirement**.

5. **The owned 2.4 GHz amplifier and circulator are in the wrong band for the committed
   architecture.** The committed split is **433 balloon-TX / 2.4 GHz balloon-RX**
   (ADR-034; reproduced in `ground-station-gain-per-dollar.md` §1.3). A 2.4 GHz part can only
   serve the **ground→balloon uplink**, whose **required ground gain is NEGATIVE (−10.7 dBi
   at 650 km)**. There is no link-closure job for it. The one thing the band *does* offer is
   a hazard: **overdrive** (§4).

### 0.4 The €/dB ledger (one definition for every row)

> **Definition:** money per **dB of link-budget improvement in the direction that needs it.**
> For a receive device the "dB" is the **T_sys improvement** it delivers (computed in §1),
> **not** the device's own gain — otherwise any gain block looks free. This is the same
> definition ADR-068 fixes for the rig ("price gain AND the rig in the same unit").

| candidate | money | dB | per needed dB | note |
|---|---:|---:|---:|---|
| **F33 module on the balloon** (+12.15 → +33 dBm) | 8.00 **USD** | 20.0 | **0.40 USD/dB** | **the bar** ([task brief] + `flrc-max` REC-1) |
| F33, alternative reading (chip +22 → +33 dBm) | 8.00 USD | 11.0 | 0.73 USD/dB | the same USD 8 counted as 11 dB |
| F33 (same, in EUR @ 0.92 — FX is an ESTIMATE) | 7.36 EUR | 20.0 | 0.37 EUR/dB | |
| **SSB LNA ISM 433 MHz** as a SYSTEM dB | 257.00 EUR | 9.7 | **26.41 EUR/dB** | the priced, spec'd 433 LNA |
| bare MMIC LNA in the same role | `TODO(unverified)` | 9.7 | `TODO(unverified)` | no MMIC price sourced this session |
| DXpatrol 1 W 2.4 GHz PA | 69.00 EUR | 0.0 | **INF** | wrong direction; the uplink is in surplus |
| DXpatrol 12 W 2.4 GHz PA | 185.00 EUR | 0.0 | **INF** | same |
| **2-bay Yagi array** (marginal over one Yagi) | 228.40 EUR | 3.0 | **76.13 EUR/dB** | €155 2nd antenna + €61.40 splitter + €12 jumpers |
| **4-bay Yagi array** (marginal over one Yagi) | 562.40 EUR | 6.0 | **93.73 EUR/dB** | same harness |
| 1.9 m mesh dish + BIG-RAS, **gain only** | 2,297.00 EUR | 2.84 | **808.80 EUR/dB** | marginal over the Yagi rig (repo Table D) |
| same dish, **gain + cold-sky noise advantage** | 2,297.00 EUR | 6.64 | **345.93 EUR/dB** | +2.84 dB gain + the §1 ~3.8 dB T_ant term (honest upper bound) |

**Ranking on cost-per-needed-dB, best first:** **(1) F33 on the balloon 0.40 USD/dB** ← the
bar; (2) 433 ground LNA 26.4 EUR/dB; (3) 2-bay Yagi array 76.1 EUR/dB; (4) 4-bay array
93.7 EUR/dB; (5) dish + tracker 346–809 EUR/dB; (6) **2.4 GHz ground PA — infinite: it buys
zero needed dB.**

> **Honest note on the dish rows — and a definitional warning.** The repo's
> `ground-station-gain-per-dollar.md` Table D prints a "€/dB marg" of **136.4** for the
> 1.9 m dish. That column is `marginal € ÷ ABSOLUTE gain` (2,297.45 / 16.84 = 136.4), **not**
> `Δ€ ÷ ΔG`. Under this document's uniform definition the dish is **808.80 EUR/dB on gain
> alone**, or **345.93 EUR/dB** if the Q1 cold-sky noise term is credited. Both numbers are
> reproducible from the script; the discrepancy is a **definitional difference in the cited
> source, not an arithmetic error in it** — flagged so no future reader compares the 136.4
> and the 808.80 as if they were the same quantity.

### 0.5 What would change the verdict (stated honestly)

* **A ground receive chain that closes the 433 downlink without the balloon-side F33.** If the
  regulatory or mass position excludes the F33, the ground LNA becomes the *primary* gain
  device rather than a margin device, and its €26.4/dB is then buying a link that would
  otherwise fail — a different value proposition. The F33 is still 66× cheaper per dB.
* **A same-band (2.4 GHz bidirectional) architecture.** If the operator intends to run *both*
  directions at 2.4 GHz, the amplifier and circulator become architecturally relevant (though
  §5.2 shows a single circulator is still insufficient isolation), and a 2.4 GHz LNA becomes
  a real receive device. **That is an architecture change to ADR-034** and is not what the
  committed design does.
* **A purchased phase-shifter product for 433 MHz.** If a cheap per-element phase shifter
  existed, the coherent phased array (Q3a) would become buildable and the array verdict would
  have to be re-costed. None was found this session (`TODO(unverified)`).

### 0.6 ADR gate — is a decision reachable?

**Yes.** The Q1, Q3 and Q5 answers do not rest on any `TODO(unverified)`: the Friis
bookkeeping, the combining algebra, the band allocation and the uplink surplus are all
first-principles results from committed constants. The Q2 verdict rests on prices that **were**
sourced this session (WiMo). The Q4 verdict rests on the repo's own **measured** saturation
plus a conservative threshold. The only `TODO`s are the LR2021's exact NF and maximum input,
the exact 2.4 GHz circulator figures, and the 10/15-el beamwidths — **none of which is
load-bearing for BUILD/DO-NOT-BUILD** (brackets are shown for the NF and T_ant; the circulator
conclusion holds at any isolation below ~40 dB; the beamwidth conclusion is reported as a
range).

Therefore a **Proposed ADR is warranted** and is written as
`docs/adr/069-ground-station-amplifier-hypothesis.md`.

---

## 1. Q1 — "An amplifier makes sense on the transmitter but NOT on the receiver, right?"

### 1.1 The framework, and why the premise is wrong

The receive chain is a **Friis cascade**:

```
T_sys = T_ant + T_1 + T_2/G_1 + T_3/(G_1·G_2) + …        T_e(NF) = 290·(10^(NF/10) − 1)
G/T  [dB/K] = G_ant[dBi] − 10·log₁₀(T_sys[K])
```

Wikipedia's *Antenna noise temperature* states the governing facts verbatim:
`T_S = T_A + T_E`, and — the sentence that decides Q1 — *"an antenna does not have an
intrinsic 'antenna temperature' associated with it; rather the temperature depends on its
gain pattern, pointing direction, and the thermal environment"*
([en.wikipedia.org/wiki/Antenna_noise_temperature](https://en.wikipedia.org/wiki/Antenna_noise_temperature)).

So a receive chain has **two independent terms**: a **device** term (`T_e`, which an LNA
attacks) and an **antenna** term (`T_ant`, which only directivity attacks). The operator's
premise says the device term is not worth attacking. The arithmetic says it is worth
**6.8–12.3 dB**.

### 1.2 The numbers (433 MHz downlink, script output)

Feed = 15 m Airborne 10 (**1.14 dB**) + connectors (**0.5 dB**) = **1.640 dB**
([`bom-candidates.md`](docs/analysis/ground-station-bom-candidates.md) §F3, §6). LNA = SSB
LNA ISM 433 (NF 0.7 dB, gain 20 dB). Element antenna = Sirio WY 400-10N (14.0 dBi); directive
antenna = 3.5 m dish (22.15 dBi).

```
  RX NF  8.0 dB:   (a) wide-beam, no LNA       T_sys = 2579.3 K
                   (b) wide-beam + LNA         T_sys =  274.5 K   -> LNA buys  +9.73 dB
                   (c) directive + same LNA    T_sys =  114.5 K   -> directivity adds +3.80 dB
                   (d) directive, no LNA       T_sys = 2419.3 K   -> LNA buys +13.25 dB here
      IRREDUCIBLE FLOOR with a perfect (0 K) LNA at the feed: T_ant = 200 K wide / 40 K directive
```

The receiver NF is **not** published for the LR2021 and is not in-repo, so it is bracketed
(6/8/10 dB); `T_ant` is bracketed 150–290 K (wide-beam) because the exact value depends on
elevation and sidelobe spillover. The **sensitivity bracket** (the honest version of the
answer):

```
  dB of T_sys the LNA buys (SSB 433: NF 0.7 dB, gain 20 dB)
  T_ant[K]       NF6    NF8    NF10
  150             8.57 10.52 12.31
  200             7.80  9.73 11.54
  250             7.18  9.09 10.91
  290             6.77  8.65 10.46
```

**The conclusion is robust across the whole plausible box: the LNA is worth +6.8 … +12.3 dB
(central case +9.7 dB).** It is emphatically *not* useless.

### 1.3 What the LNA cannot buy

With the LNA **already fitted**, replacing the wide-beam antenna with a cold-sky dish removes
**only the `T_ant` term**:

```
  433 MHz:  +3.80 dB (RX NF 8 dB)   — and +4.03 dB at NF 6, +3.48 dB at NF 10
  2.4 GHz:  +2.82 dB (RX NF 6 dB), +2.06 (NF 8), +1.45 (NF 10)
```

That part is **directivity-only** and no amplifier can supply it. It is **smaller than the
LNA's own contribution** — which is the precise sense in which the premise is wrong. And a
dish *also* brings its own gain (22.15 − 14.0 = **+8.15 dB**), which is a third, separate
term.

Two honest carve-outs:

* **At 2.4 GHz the directivity-only term is small (1.5–2.8 dB) because the LNA is weak
  there.** The Mini-Circuits **ZX60-P103LN+** has only **10.0 dB of gain at 2000 MHz**
  (vs 20.3 dB at 500 MHz) with NF 0.6 dB
  ([ZX60-P103LN+ datasheet, Rev D](https://www.minicircuits.com/pdfs/ZX60-P103LN+.pdf)), so
  it does not fully suppress the downstream receiver noise and cannot realise the cold-sky
  advantage. A **higher-gain** 2.4 GHz LNA would. This is a real, computable design
  consequence and is why the number is band-dependent.
* **An LNA must be at the MASTHEAD.** Placed in the shack it amplifies 1.64 dB (433) /
  3.38 dB (2.4 GHz) of coax loss along with the signal. That is exactly what the priced
  masthead preamps exist for (§1.4).

### 1.4 The priced parts this rests on (all fetched this session, HTTP 200)

| part | band | gain | NF | other | price |
|---|---|---|---|---:|---:|
| **SSB Electronic LNA ISM 433 MHz** | **433–435 MHz** | **20 dB typ** | **0.7 dB** | OIP3 +32 dBm, IIP3 +12 dBm, 74×51×30 mm, 140 g, N-f, **RX only, no T/R** | **€257.00** |
| **Mini-Circuits ZX60-P103LN+** | 50–3000 MHz | 20.3 dB @500, **10.0 dB @2000** | 0.4 dB @500, 0.6 @2000 | P1dB +22.3/+23.2 dBm, in-max +21 dBm (≤2 GHz) / +26 (>2 GHz), 5 V 95 mA | `TODO(unverified)` |
| SSB Electronic LNA series 6m/2m/70cm | **430–440 MHz** (70 cm) | "high gain" | "super low-noise" | remote power via coax | €226.00 |
| SHF **Mini-xx** mast preamp | 2 m / 70 cm | **adjustable** | low | 150 W switched through — *"the gain is adjustable. This ensures that the receiver is not overdriven"* | €151.90 |
| SP-S mast preamp **with VOX RX/TX switch** | 6 m/2 m/70 cm | low-noise | — | T/R switching built in | €345.00 |

Sources: [ssb-70cm-ism-lna](https://www.wimo.com/en/ssb-70cm-ism-lna),
[ZX60-P103LN+](https://www.minicircuits.com/pdfs/ZX60-P103LN+.pdf),
[ssb-electronic-lna-preamp](https://www.wimo.com/en/ssb-electronic-lna-preamp),
[shf-mast-preamp-mini-vhf-uhf](https://www.wimo.com/en/shf-mast-preamp-mini-vhf-uhf),
[ssb-electronic-mast-preamp-sps](https://www.wimo.com/en/ssb-electronic-mast-preamp-sps).

> **`TODO(unverified)`** — the LR2021's own noise figure and maximum/blocking input level
> were not found in-repo and not fetched this session. The LR2021 NF is bracketed (6/8/10 dB)
> and the conclusion is insensitive to it across that bracket. The repo's only sourced LNA NF
> is the **SKY66112-11 (+14 dB / 1.8 dB NF**, ADR-005), used on the balloon side.

### 1.5 Q1 answer

**The premise is WRONG, by ~9.7 dB (bracket +6.8 … +12.3 dB).**

* An LNA is the *standard, cheapest* way to improve receive sensitivity, and the numbers say
  so. It sets the system noise figure.
* The LNA's **own gain** (20 dB) is **not** what it is worth. What it is worth is the T_sys
  improvement (~9.7 dB), because what it displaces is the receiver's own noise.
* The LNA **cannot** lower `T_ant`. With an LNA fitted, cold-sky directivity adds a further
  **~4.0 dB (433) / 1.5–2.8 dB (2.4 GHz)** that no amplifier can produce. That is the true
  half of the operator's intuition, and it is the *smaller* half.
* They are **additive**, not alternatives. The correct sentence is: *"an amplifier makes sense
  on the receiver too — and it costs 66× more per needed dB than the balloon-side PA does."*

---

## 2. Q2 — the Yagi array: bandwidth, coupling, beam, and €/dB

### 2.1 Real bandwidth of a practical 433 MHz Yagi

| source | stated band | fractional |
|---|---|---|
| Wikipedia, *Yagi–Uda antenna* | *"in its basic form has a narrow bandwidth, **2–3 percent** of the centre frequency"*; *"the bandwidth narrowing as more elements are used"* | **2–3 %** |
| → at 433.05 MHz | | **8.7–13.0 MHz** |
| Diamond A-430S10R / A-430S15R (vendor) | 430–440 MHz | **2.30 % / 10 MHz** |
| Sirio WY 400 family (vendor) | 400–470 MHz | **16.09 % / 70 MHz** |

([Wikipedia Yagi–Uda](https://en.wikipedia.org/wiki/Yagi%E2%80%93Uda_antenna);
bands from [`bom-candidates.md`](docs/analysis/ground-station-bom-candidates.md) §1.)

**Reading:** a practical 433 Yagi is a **9–13 MHz** antenna on the 2–3 % rule, and the
Diamond's own spec (10 MHz, 2.30 %) lands right inside it. The Sirio WY 400 family's claimed
400–470 MHz is a deliberately **de-tuned wideband design**, and its *"bis zu 14 dBi"* is the
**peak**, not a flat-band figure.

> **The interaction that actually matters, and it is about the LNA, not the array.**
> The priced 433 LNA is **narrower than the Yagi**: SSB LNA ISM 433 MHz is **433–435 MHz only
> = 2.0 MHz = 0.46 %**. An LNA ahead of the antenna **sets the receive system bandwidth**, so
> putting it in circuit **collapses a 2.30 % Yagi to a 0.46 % system**. That is fine for the
> 433.05–434.79 MHz ISM allocation (1.74 MHz, 0.40 %) but **forbids any operation outside
> it** — a frequency-agility constraint a future session must not discover the hard way.

### 2.2 Does arraying change element bandwidth, and what does mutual coupling do?

Arraying **costs bandwidth** and it costs it through **mutual coupling**. For a pair at
spacing d ≈ 0.5–0.7 λ the coupling is strong, and it does three things simultaneously:

1. **Pattern.** The pair's array factor multiplies the element pattern, but the coupling
   perturbs the element currents, so the achieved gain falls short of the ideal **+3.01 dB**
   and sidelobe levels rise. Practical 2-bay gain is **+2.5 … +2.7 dB**.
2. **Impedance / match.** Each element's input impedance shifts, so the SWR<1.5 window
   **narrows** relative to a single element.
3. **Bandwidth.** The stacked pair's match is narrowest at the design frequency.

Wikipedia's *Phased array* supplies the structural reason arrays are hard: *"the size of an
antenna array must extend many wavelengths to achieve the high gain needed for narrow
beamwidth"*, and grating lobes are the integer solutions of `k·d·sinθ = 2πm`, i.e. **d must
stay below ~1 λ** to keep a single main lobe
([en.wikipedia.org/wiki/Phased_array](https://en.wikipedia.org/wiki/Phased_array)).

### 2.3 The full cost of a 2-bay / 4-bay array

All prices fetched this session at WiMo
([power splitter & phasing harnesses](https://www.wimo.com/en/accessories/antenna-accessories/power-splitter-phasing-harnesses)):

* **Power splitter 430 MHz, 2000 W, for 2 or 4 antennas, N female — €61.40**
* 70 cm **phase line** with connectors — **€63.00**
* YU1CF 70 cm splitter/divider, 2…8 outputs — €103.00
* Diamond splitter 2- or 4-way — €124.90
* jumpers ≈ **€12.00 each** (**ESTIMATE** — no vendor price read)

```
  1-bay 10-el Sirio WY 400-10N: antennas EUR 155.00 + harness EUR  0.00 = EUR 155.00
  2-bay                        : antennas EUR 310.00 + harness EUR 73.40 = EUR 383.40
     marginal over ONE element : EUR 228.40 for +3.0 dB  =  76.1 EUR/dB
  4-bay                        : antennas EUR 620.00 + harness EUR 97.40 = EUR 717.40
     marginal over ONE element : EUR 562.40 for +6.0 dB  =  93.7 EUR/dB
```

The **+3.0 dB** is not my idealisation — it is the repo's own pairing:
**2 × Sirio WY 400-10N stacked = 17.0 dBi vs 14.0 dBi single** (`ground-station-gain-per-dollar.md`
Table A). And the array-ready claim is the vendor's: the Sirio WY 400 family page explicitly
lists *"Stacked and bayed array for more gain"*
([funktechnik-bielefeld.de, WY 400-3N](https://www.funktechnik-bielefeld.de/sirio-wy-400-3n-3-element-400-470-mhz)).

On top of the parts cost there is a **wind / torque** cost: stacking doubles the aperture and
the mast moment, which can cross a **positioner class boundary** — an **€80–€1,346** step in
the menu this repo prices (`ground-station-gain-per-dollar.md` §1.6/§2.7; ADR-068 §3).

### 2.4 Does arraying narrow the beam and therefore HURT the cheap-tracker strategy?

**Yes — and here is the honest, computed magnitude, which is more modest than the intuition.**

Element beamwidths from the beam-solid-angle relation **D = 41253/(θ_E·θ_H)** in deg²
([Wikipedia, *Directivity*](https://en.wikipedia.org/wiki/Directivity): `D = U_max/(P_tot/4π)`,
and 4π = 41253 deg²). The relation is **validated on this antenna family**: the vendor's 3-el
figures (7 dBi with 65° × 125°) give θ_E·θ_H = 8231 vs the vendor's 8125 — **1.3 % agreement**.
(That coefficient is also the `√10 ≈ π` trap the trade-study skill warns about: a ~1 % match
can hide a cancelled factor. Here the coefficient is **re-derived** from `D = 4π/Ω_A`, not
assumed.)

```
  7.0 dBi element (65.0 deg) N=2 d=0.5 lam ->  44.5 deg  (x0.69)
  7.0 dBi element (65.0 deg) N=2 d=0.7 lam ->  35.7 deg  (x0.55)
  7.0 dBi element (65.0 deg) N=4 d=0.5 lam ->  24.6 deg  (x0.38)
 14.0 dBi element (29.2 deg) N=2 d=0.5 lam ->  26.3 deg  (x0.90)
 14.0 dBi element (29.2 deg) N=2 d=0.7 lam ->  24.2 deg  (x0.83)
 14.0 dBi element (29.2 deg) N=4 d=0.5 lam ->  19.7 deg  (x0.68)
 18.0 dBi element (18.4 deg) N=2 d=0.5 lam ->  17.6 deg  (x0.96)
 18.0 dBi element (18.4 deg) N=4 d=0.5 lam ->  15.2 deg  (x0.83)
```

* For a **short, low-gain element** (3-el, 65°) a 2-bay stack narrows **65° → 44.5° = 32 %** —
  the penalty is real.
* For a **high-gain 10/15-el element (29°)** the *same* 2-bay stack narrows only
  **29.2° → 26.3° = 10 %**, because the array factor (60°) is already **broader** than the
  element, so pattern multiplication barely bites. A 4-bay narrows it to **19.7° (33 %)**.
* The **orthogonal plane is essentially unchanged** (a stack narrows only the stacking plane).

**So the beamwidth penalty is 10–32 % at 2-bay and 33 % at 4-bay — real, but not the main
cost. The main costs are the €76–94/dB and the doubled wind moment.**

The **strategic contradiction stands**: the amplifier-led/cheap-tracker proposition wants a
**wider** beam so a cheap tracker can afford to miss. A Yagi array (and a fortiori a dish)
buys its dB by making the beam **narrower**, i.e. by making the tracker's job **harder**.
Arraying and dish-building move the precision requirement *onto the tracker*, which is exactly
where the cheap-tracker strategy was trying not to spend.

> **`TODO(unverified)`** — the 10/15-el vendors publish gain and band but **not** the −3 dB
> beamwidths, so the absolute element figures above are ESTIMATEs from the validated
> beam-solid-angle relation. The **relative** narrowing (the quantity that answers this
> question) is computed rigorously from the array factor and does not depend on that estimate.

### 2.5 Q2 answer

**DO NOT ARRAY.** A practical 433 Yagi is a **2–3 % / 9–13 MHz** antenna. Arraying narrows the
match and the beam, and costs **€76.13/dB (2-bay)** / **€93.73/dB (4-bay)** — **2.9×–3.6× the
F33's 0.40 USD/dB** — plus a doubled wind moment that can step the positioner a class. The
final €/dB order is **F33 (0.40 USD/dB) ≪ 433 LNA (26.4 EUR/dB) < 2-bay array (76.1) < 4-bay
array (93.7) < dish+tracker (346–809)**.

---

## 3. Q3 — "Use a SEPARATE antenna tracker for each Yagi and COMBINE multiple Yagis"

### 3.1 The four things the sentence could mean, with the bookkeeping

For N equal branches, each with per-branch SNR `s = a²/σ²`:

**(a) COHERENT PHASED ARRAY** — phase-aligned sum into one receiver:
`y = Σ(a + nᵢ) = N·a + Σnᵢ` → `P_sig = N²a²`, `P_noise = Nσ²` → **`SNR = N·a²/σ²` →
GAIN = 10·log₁₀N** = **+3.01 dB (N=2)**, **+6.02 dB (N=4)**.
Requires **per-element phase coherence**. Wikipedia's *Phased array*: *"the transmitter is fed
to the radiating elements through devices called phase shifters, controlled by a computer
system, which can alter the phase or signal delay electronically"* — i.e. **one phase shifter
per element**, a coherent reference, **and continuous correction** because the balloon's
geometry changes every second.

**(b) INCOHERENT POWER COMBINING** — N outputs squashed together in one receiver, phases
random: `P_sig = N·a²`, `P_noise = N·σ²` → **`SNR = a²/σ²` → GAIN = 0.00 dB.**
**This is the case people hope works, and it does not: N× signal AND N× noise.**

**(c) MRC / diversity combining with N SEPARATE receivers** — each branch keeps its own
independent noise; MRC weights by SNR and sums → `SNR_out = Σ s = N·s` → **GAIN = 10·log₁₀N**,
**the same as (a)**. Wikipedia's *Diversity combining*: *"Maximal-ratio combining … The
resulting SNR yields Σ_{k=1}^{N} SNR_k"*; it is also called **"predetection combining"**, i.e.
**still coherent** ([en.wikipedia.org/wiki/Diversity_combining](https://en.wikipedia.org/wiki/Diversity_combining),
[en.wikipedia.org/wiki/Maximal-ratio_combining](https://en.wikipedia.org/wiki/Maximal-ratio_combining)).
Requires **N complete receivers** (N LR2021 + N LNAs + N feeds) **and per-branch co-phasing**.
Caveat: the 10·log₁₀N needs **independent** branch noise; closely spaced elements with
correlated `T_ant` noise give less.

> **Two different "diversity gains" must not be conflated.** The 10·log₁₀N above is an
> **AWGN** array gain with independent noise. The classic *fading* diversity gain is a
> different quantity: **selection combining** on N independent **Rayleigh** branches yields
> `Σ_{k=1}^{N} 1/k` → **+1.76 dB (N=2)**, **+3.19 dB (N=4)** (same Wikipedia source) — and it
> only exists **against fading**. An elevated balloon is a **near-LOS** path, so **there is
> little fading to harvest and this gain is mostly NOT available to us.**

**(d) MULTI-SECTOR COVERAGE** — N cheap, coarsely aimed antennas at **different sky sectors**,
pick the best → **GAIN over the best single = 0.00 dB** (there is one target). What it *does*
buy: the per-antenna pointing requirement **relaxes by about the sector width**, and a
tracker that misses costs **coverage**, not the link.

### 3.2 Cost check

| mechanism | hardware | price |
|---|---|---:|
| 2-way 430 MHz 2000 W splitter + jumpers (for (b)) | splitter + coax | **€73.40** |
| a second receive chain for (c) | LNA + a second LR2021 | **€257.00** + ~USD 20–30 (**ESTIMATE**) |
| a **phase shifter per element** for (a) | — | **`TODO(unverified)`** — no 433 MHz amateur phase-shifter product found this session |

### 3.3 Q3 answer — undiplomatic

* The operator's sentence, taken literally — *"one cheap tracker per Yagi, **combined**"* — is
  case (a)/(c) **only if the phases are aligned**. **Nothing about using a separate tracker per
  Yagi achieves that: separate trackers guarantee separate phase.**
* If the N Yagis point at the **same** target and their outputs are simply combined, that is
  case **(b) = +0.00 dB**. It adds cost and complexity and **no gain**.
* The only versions that **ADD GAIN** are **(a) coherent phased array** and **(c) MRC with N
  receivers**, worth **10·log₁₀N** (+3.01 dB N=2, +6.02 dB N=4) — and **both require
  per-branch phase coherence**, with (c) also needing **N radios**.
* The version that is actually **USEFUL to this project is (d) MULTI-SECTOR COVERAGE**: it adds
  **no gain**, but it **removes the precision-tracking requirement** — which is the real
  engineering problem for a cheap tracker. **Frame the operator's idea as (d) and it is sound;
  frame it as a gain scheme and it is not.**

---

## 4. Q4 — balloon-receiver overdrive: can external gain control solve it?

### 4.1 Where the overdrive comes from, and the repo's own measurement

The ground uplink leaves the ground at `P_tx` into a wide-beam antenna. With `G_tx = 12.4 dBi`
(FlexaYagi FX 7015V class), `G_balloon = 0 dBi` (conservative, per
`LINK-BUDGET-LICENCE-EXEMPT.md`), `L = 2.0 dB`, λ(2440 MHz) = 0.1229 m:

```
  P_rx_at_balloon(dBm) = P_tx + 12.4 − FSPL(d) − 2.0,   FSPL = 40.20 + 20·log₁₀(d_m)

  ground TX      10 m     100 m     20 km
  +20.0 dBm     -29.8    -49.8     -95.8
  +30.0 dBm     -19.8    -39.8     -85.8
  +33.0 dBm     -16.8    -36.8     -82.8
  +40.8 dBm      -9.0    -29.0     -75.0

  RANGE AT WHICH THE BALLOON RX COMPRESSES / OVERLOADS   (solve P_rx(d) = threshold)
  ground TX   -30 dBm   -20 dBm   -10 dBm    0 dBm
  +20.0 dBm    10.2 m     3.2 m     1.0 m     0.3 m
  +30.0 dBm    32.4 m    10.2 m     3.2 m     1.0 m
  +33.0 dBm    45.7 m    14.5 m     4.6 m     1.4 m
  +40.8 dBm   112.3 m    35.5 m    11.2 m     3.5 m
```

**The `−20 dBm` column is not a guess — it is the repo's own measured behaviour.** In
`docs/power-sweep-results-2026-07-24.md`: at 1–2 m the LR2021's RSSI read **−8.0 dBm at every
TX power from 0 to 12 dBm**, and the documented most-likely explanation is *"receiver
saturation at close range … AGC/LNA compresses, masking power differences."* The 433/2.4 GHz
AGC step structure is independently visible in `docs/analysis-flrc-rssi-cliff.md` (*"the ~21 dB
gap between peaks is consistent with one LNA gain-stage step in the LR2021's AGC table"*).

So: **a +33 dBm ground PA on a 12.4 dBi Yagi puts the balloon's receiver into compression
inside ≈14.5 m and hard-overloads it inside ≈1.4 m.** At the balloon's working range
(>20 km) the uplink sits at **−82.8 dBm** — ~53 dB above the −136 dBm sensitivity.

> **`TODO(unverified)`** — the LR2021's published maximum input / blocking level was not found
> in-repo and not fetched this session. −20 dBm is used as the **conservative** compression
> onset; the conclusion holds a fortiori at a higher threshold.

### 4.2 Evaluate the four candidate mechanisms

| mechanism | hardware | solves? | note |
|---|---|---:|---|
| **1. Step attenuator / VGA before the PA** | **€24.50–39.00** fixed; **€40–120 [ESTIMATE]** for VGA+detector+MCU | **partly / yes** | A **DAT-31R5A+** digital step attenuator gives **0–31.5 dB in 0.5 dB steps, DC–4.0 GHz, IP3 52 dBm** ([datasheet](https://www.minicircuits.com/pdfs/DAT-31R5A-PN+.pdf)), price `TODO(unverified)` (Mini-Circuits prices are AJAX-only). WiMo fixed attenuators: 1 W 3–20 dB SMA **€24.50**; 3–30 dB 2 W N **€39.00** ([WiMo attenuators](https://www.wimo.com/en/accessories/antenna-accessories/meters/dummyloads-attenuators)). A hand-set attenuator is a **one-off calibration, not a control loop**; 31.5 dB of range does not span the ~45 dB the geometry actually needs. |
| **2. AGC** | €0 | **NO** | The overdrive is in the **balloon's** receiver. **Ground-side AGC cannot help a receiver at the other end of the link.** This is the mechanism the question's framing most naturally suggests, and it is the one that cannot work. |
| **3. Closed-loop power control from the balloon's own telemetry (GNSS range)** | firmware | **yes** | `P_tx_required(d) = S + FSPL(d) + margin − G_balloon − G_ground + L`. Implementable — the F33 exposes a **CE / internal-LDO enable pin** for sleep control and the balloon has GNSS. Cost is **firmware, not hardware**. But this controls the **balloon's** 433 TX, i.e. the *downlink*, which is a different loop from the ground uplink PA. |
| **4. Closed-loop from the downlink RSSI as feedback** | firmware + detector | **yes (best)** | The ground listens to the 433 downlink RSSI and scales the 2.4 GHz uplink drive so the balloon sees a constant level; round-trip latency is one packet. The **DXpatrol 12 W amplifier already exports 0–4 V forward-power and SWR outputs** — *"outputs (0-4V) for SWR and power … allow precise control of the amplifier's operation"* ([wimo.com/en/qo100-amp12](https://www.wimo.com/en/qo100-amp12)). |

### 4.3 Q4 answer

**The catch is MANAGEABLE, not fatal — and, more importantly, it is a reason not to *need* it.**

* External gain control **can** solve the close-range case, and the **cheapest complete answer
  is mechanism 4** (downlink-RSSI closed loop), because it closes the loop through the actual
  channel rather than through a model. A step attenuator alone is only a calibration.
* **But note the direction of cause:** the overdrive exists **only because the ground PA is
  oversized by ~36 dB** for the link it serves (§5.1). Remove the surplus and the problem
  disappears; power control simply buys back the 30–40 dB the link never needed. The honest
  verdict is therefore **"not needed"**, not "solved".
* If the operator wants the amplifier anyway, **step attenuator + downlink-RSSI loop** is the
  correct, cheap, implementable answer. **Ground-side AGC (mechanism 2) is not.**

---

## 5. Q5 — re-cost the amplifier-led station with the owned circulator + amplifier

### 5.1 The band question decides everything else

The committed split (`docs/adr/034-*`, reproduced in `ground-station-gain-per-dollar.md` §1.3):

```
  balloon TX = 433 MHz (downlink)   <- the BINDING direction (sets ground gain)
  balloon RX = 2.4 GHz (uplink)     <- needs NEGATIVE ground gain
```

A circulator and an amplifier are **band-specific**. **A 2.4 GHz amplifier can only ever
amplify the ground→balloon uplink. It cannot add one dB to the 433 downlink, which is the
direction that sets ground gain.** This is the single most important sentence in this
document.

**How much does the uplink actually need?** Required ground gain at 650 km at +20 dBm EIRP is
**−10.7 dBi** (`ground-station-gain-per-dollar.md` §1.3; positioner study §3.1). Re-scaling for
a higher ground TX:

```
  ground TX +20.0 dBm -> required ground gain -10.7 dBi; a 12.4 dBi Yagi gives +23.1 dB SURPLUS
  ground TX +30.0 dBm -> required ground gain -20.7 dBi; a 12.4 dBi Yagi gives +33.1 dB SURPLUS
  ground TX +33.0 dBm -> required ground gain -23.7 dBi; a 12.4 dBi Yagi gives +36.1 dB SURPLUS
  ground TX +40.8 dBm -> required ground gain -31.5 dBi; a 12.4 dBi Yagi gives +43.9 dB SURPLUS
```

**The uplink closes with an OMNI at +20 dBm.** With a 12.4 dBi Yagi it has **+23.1 dB of
surplus before any amplifier**, and **+36.1 dB** with a +33 dBm PA. There is **no
link-closure job for the amplifier to do on this band.** A very high-power 2.4 GHz uplink also
collides with the **100 mW EIRP licence-exempt cap** (the +13…+33 dBm class is
amateur-licence-only — `LINK-BUDGET-LICENCE-EXEMPT.md`).

### 5.2 Does the circulator solve T/R isolation / self-desense?

> **`TODO(unverified)`** — no 2.4 GHz circulator datasheet was fetched this session (vendor
> pages returned **HTTP 404**; search engines were captcha-gated). The class figures used below
> are **ESTIMATEs** typical of a coaxial ferrite drop-in: **isolation ~18–25 dB, IL ~0.3–0.5 dB.**
> The *requirement* below is computed, not estimated, and does not depend on them.

**(A) Same-band, one shared 2.4 GHz antenna — the only case where a circulator helps:**
using the pessimistic end (isolation 20 dB, IL 0.5 dB, and a 10 dB 2.4 GHz LNA downstream):

```
  TX +30.0 dBm -> leakage at the RX port = +10.5 dBm -> chip sees +20.5 dBm  OVERLOADED
  TX +33.0 dBm -> leakage at the RX port = +13.5 dBm -> chip sees +23.5 dBm  OVERLOADED
  TX +40.8 dBm -> leakage at the RX port = +21.3 dBm -> chip sees +31.3 dBm  OVERLOADED
```

**A single circulator is NOT sufficient at +30…+40 dBm.** ~20 dB of isolation still leaves
+10…+20 dBm at the RX port and, after any receive gain, tens of dBm into the chip. You need
**isolation ≳ TX − (RX tolerance), i.e. ≈40–55 dB**, which means **circulator + T/R switch**,
or **circulator + a T/R amplifier/preamp that bypasses the LNA during TX** — **not a circulator
alone**. (The ZX60 survives on its own: max input **+26 dBm** at 2–3 GHz, P1dB **+23.2 dBm** —
but the receiver behind it does not.) Buyable things that *do* switch the LNA out:

| product | what it does | price |
|---|---|---:|
| **RT-2400-2** 2.4 GHz **TX+RX amplifier with internal switching** — 2417–2467 MHz, **TX gain 13 dB, RX gain 14 dB, NF 3.2 dB**, P_out ≤ 1 W | one box, does PA + LNA + T/R | **€355.00** |
| **SHF Mini-xx mast preamp**, **adjustable gain**, 150 W switched through | adjustable so the RX is not overdriven | **€151.90** |
| **SP-S mast preamp with VOX RX/TX switch** | preamp + T/R | **€345.00** |
| coax relay **SPDT 3× N (CX-600N)** | T/R switching | **€142.00** |

([wimo.com/en/rt-2400](https://www.wimo.com/en/rt-2400),
[shf-mast-preamp-mini-vhf-uhf](https://www.wimo.com/en/shf-mast-preamp-mini-vhf-uhf),
[ssb-electronic-mast-preamp-sps](https://www.wimo.com/en/ssb-electronic-mast-preamp-sps),
[WiMo coaxial relays](https://www.wimo.com/en/accessories/radio-accessories/coaxial-relays).)

Note the **structural** point from the same vendor pages: **13 cm (2.4 GHz) mast preamps with
integrated T/R are discontinued** — *"The preamplifiers for 13 cm … are unfortunately no longer
available."* Buying a 2.4 GHz LNA with T/R is therefore **harder** than at 433 MHz, and the
covered alternative (*LNA-5000 broadband*) *"does not have an integrated transmit and receive
switch."*

**(B) The committed 433/2.4 GHz split: the circulator is the WRONG COMPONENT.** With ground RX
at **433 MHz** and ground TX at **2.4 GHz** you do **not** need T/R isolation at all —
**different bands**, and the feed is a **diplexer/filter** problem, not a circulator problem.
A 2.4 GHz circulator can only serve a **same-band (2.4 GHz, both directions)** link, which the
repo does not currently run ([Wikipedia, *Circulator*](https://en.wikipedia.org/wiki/Circulator):
*"a signal applied to port 1 only comes out of port 2"* — it is band-selective by construction).

### 5.3 Marginal cost, achievable link dB, and €/dB

The operator owns the 2.4 GHz amplifier and circulator, so the **marginal hardware cost of the
amplification itself is €0.00**. The *real* marginal cost is what the amplifier forces you to
add so its output is usable:

```
  step attenuator (so the PA drive is settable)          EUR  25.00-40.00
  T/R switching that actually works at +33 dBm           EUR 142.00-355.00
  PSU + heatsink for 12 W (heat is NOT a constraint,
    but the metal is still bought)                       EUR  40.00-90.00  [ESTIMATE]
  -------------------------------------------------------
  marginal total (low / high)                            EUR 207.00 / 485.00
```

> **Ground-side ENERGY is not a constraint** (operator's rule) — so DC power and heat are
> deleted from the ranking. The **PSU/heatsink cost is still stated** because the metal is
> still bought: a 12 W 2.4 GHz PA draws ~1.1–1.7 A at 12–28 V (the DXpatrol 12 W needs **28 V
> for full output**, 5 W at 12 V) and needs a real heatsink.

**Link dB bought: 0.0 dB on the binding 433 downlink; 0 dB needed on the non-binding 2.4 GHz
uplink (already +23.1 … +36.1 dB in surplus). Therefore €/dB is UNDEFINED / infinite — you buy
no needed dB.**

**The trap to avoid:** if you compute €/dB on the *device's* gain the free amplifier looks like
**0.00 EUR/dB** and a bought RT-2400-2 looks like **27.31 EUR/dB** (€355 / 13 dB TX gain).
**But that dB is in the wrong direction. A dB is not fungible across bands** — which is
exactly why the ledger's definition (§0.4) is money per *needed* dB.

### 5.4 Q5 answer

**DO-NOT-BUILD the amplifier-led station.** The owned hardware is in the wrong band for the
committed architecture, the direction it *can* amplify has **23–36 dB of surplus already**, and
the circulator does not solve the T/R problem the operator hopes it solves — while introducing
a close-range overdrive hazard on the balloon's receiver.

**What the operator should build instead — and it is a BUILD, not a "do nothing":**

1. **F33 module on the balloon** — ~USD 8, **+20 dB**, **0.40 USD/dB**. 66× better per needed dB
   than anything on the ground. *(Gated: ADR-039 open item (a) and the
   `PAYLOAD-WEIGHT-ESTIMATES.md` §D "Ground Station Only" classification must both be settled
   first — inherited from `flrc-max` REC-6 and recorded in ADR-068 §Consequences.)*
2. **A 433 MHz masthead LNA** — **SSB Electronic LNA ISM 433 MHz, €257.00, 20 dB gain / 0.7 dB
   NF**, worth **+9.7 dB of T_sys = €26.4 per needed dB**. This is the *one* ground amplifier
   that buys needed dB, and it is a **receive** amplifier — the precise answer to Q1. Note its
   **0.46 % bandwidth** sets the receive system bandwidth (§2.1).
3. **A single Yagi** (not an array, not a dish) on the DIY tracker, per ADR-068.

---

## 6. Failure modes / risks of the recommendation

| # | risk | severity × likelihood | mitigation |
|---|---|---|---|
| F1 | The F33 is excluded (mass or licence) → the ground LNA becomes the primary gain device and its €26.4/dB must close a link that would otherwise fail | **High × Medium** | Settle ADR-039 open item (a) and the `PAYLOAD-WEIGHT-ESTIMATES.md` §D classification **before** committing; if excluded, re-run `ground_station_gain_per_dollar.md` with the LNA in the chain (that model does not currently model a receive LNA) |
| F2 | Narrowband LNA (433–435 MHz) collapses the receive system bandwidth | Medium × **High** (it is certain, just not harmful if the ISM band is all that is used) | Accept and record; do not plan frequency agility outside 433.05–434.79 MHz with this LNA |
| F3 | An LNA at the masthead is **destroyed by close-range TX leakage** on a shared 433 antenna | Medium × Medium | The SSB LNA ISM 433 page is explicit: *"does not feature transmit/receive switching … Excessive RF levels at either the input or output may damage the preamplifier."* Use a **T/R-switched** preamp (SP-S €345 / SHF €151.90) or a relay (CX-600N €142) if the same antenna transmits |
| F4 | The operator proceeds with the 2.4 GHz PA anyway and overdrives the balloon | **High × Medium** | Mechanism 4 (§4.2) — a downlink-RSSI closed loop — or simply a fixed attenuator sized for the closest expected range; **ground AGC cannot help** |
| F5 | Circulator isolation assumed sufficient at +33 dBm | **High × Low** (if the operator checks) | Require **≥40–55 dB** TX→RX isolation, i.e. add a T/R switch or use a T/R amplifier box; do not rely on a bare circulator |
| F6 | `TODO(unverified)` LR2021 NF / max input change the Q1/Q4 numbers | Low × Medium | Brackets are shown for both (NF 6/8/10 dB; −20 dBm threshold), and the verdicts hold across the whole bracket |

---

## 7. Open items / `TODO(unverified)`

1. **`TODO(unverified)`** the **LR2021's own noise figure** — not in-repo, not fetched. Bracketed
   6/8/10 dB; the Q1 conclusion is insensitive across the bracket.
2. **`TODO(unverified)`** the **LR2021's maximum/blocking input level** — the Q4 compression
   onset uses **−20 dBm** as a conservative proxy anchored on the repo's *measured* saturation.
3. **`TODO(unverified)`** **2.4 GHz circulator datasheet** (isolation, IL, power handling) — vendor
   pages 404'd, search engines captcha'd. Class ESTIMATEs used; the *required* isolation
   (~40–55 dB) is computed and does not depend on them.
4. **`TODO(unverified)`** **Mini-Circuits prices** (ZX60-P103LN+, DAT-31R5A-PN+, PGA-103+) — the
   WebStore price endpoints returned nothing (prices are AJAX-only). Specs are cited from the
   PDFs.
5. **`TODO(unverified)`** **exact −3 dB beamwidths of the 10/15-el Yagis** — the vendors publish
   gain and band only.
6. **`TODO(unverified)`** a **433 MHz per-element phase-shifter product** for a coherent array,
   and a **bare-MMIC LNA price** — neither sourced this session, so neither is scored.
7. **ESTIMATEs, not sourced:** `T_ant` brackets (200 K wide-beam / 40 K dish at 433; 290 K / 25 K
   at 2.4 GHz), `NF_RX` bracket, the FX 0.92 EUR/USD rate, the €12/jumper harness allowance, the
   €40–90 PSU/heatsink allowance, and the "PSU+heatsink" line.
8. **Repo defect flagged, not resolved (inherited):** SPX-06 €5,487 @ 716 N·m vs BIG-RAS €1,775
   @ 2,712 N·m brake — price and rating orderings disagree (ADR-068 §Consequences).
9. **Repo contradiction flagged, not resolved (inherited):** `docs/PAYLOAD-WEIGHT-ESTIMATES.md`
   §D classes the F33 board as *"Ground Station Only … not a pico balloon target"*, which
   contradicts the F33-on-balloon recommendation. Must be settled by an ADR before the F33 flies.
10. **Not modelled:** the receive-LNA option is not in `ground_station_gain_per_dollar_model.py`,
    so its €/dB cannot yet be compared on the repo's M2 metric — only on the dB ledger here.

---

## 8. Sources and reproduction

**Reproduce every numeric table:**

```bash
python3 docs/analysis/ground_station_amplifier_hypothesis_model.py
```

Every search, formula and price in the script carries an inline provenance comment. No
datasheet value or vendor URL in this document was invented; where a number could not be
sourced it is marked `TODO(unverified)` and no verdict depends on it.

**External sources fetched this session (all HTTP 200 via `curl -L --compressed` with a browser
User-Agent):**

* Wikipedia REST (full-page HTML): *Antenna noise temperature*, *Noise figure*, *Friis formulas
  for noise*, *Yagi–Uda antenna*, *Phased array*, *Maximal-ratio combining*, *Diversity
  combining*, *Directivity*, *Circulator*.
* Mini-Circuits datasheets: `ZX60-P103LN+.pdf` (Rev D, ECO-026542), `ZFL-1000LN+.pdf`,
  `DAT-31R5A-PN+.pdf`, `ZVE-8G+.pdf`, `ZHL-16W-43+.pdf` (PDFs fetched; two product URLs 404'd).
* WiMo (DE, static prices in HTML): `en/rt-2400`, `en/qo100-amp12`,
  `en/dxpatrol-qo100-amplifier-1w`, `en/ssb-70cm-ism-lna`, `en/ssb-electronic-lna-preamp`,
  `en/shf-mast-preamp-mini-vhf-uhf`, `en/ssb-electronic-mast-preamp-sps`,
  `en/shf-mast-vox-preamp-vhf-uhf`,
  `en/accessories/antenna-accessories/power-splitter-phasing-harnesses`,
  `en/accessories/antenna-accessories/meters/dummyloads-attenuators`,
  `en/accessories/radio-accessories/coaxial-relays`.
* Funktechnik Bielefeld: Sirio WY 400-3N (published 65°/125° beamwidths), WY 400-10N,
  Diamond A-430S10R, A-430S15R, FlexaYagi FX 7073.

**Blocked / gated this session → no value invented:** `html.duckduckgo.com` (HTTP 202
challenge), `fairviewmicrowave.com` and `everythingrf.com` circulator categories (404),
`kuhne-electronic.de` / `ssb-electronic.de` (connection failure / 000),
`reichelt.de` search (404), `minicircuits.com` WebStore price AJAX endpoints (empty).

**Prior art read (not re-derived):** as listed in the header table — `design/gain-per-dollar`
(`0ea36b4`), `design/ground-station-flrc-max` (`4ecbf5c`), `design/ground-station-bom`
(`283cad72`), `design/positioner-lowcost` (`b74bf5f6`), `design/ground-station-lowpower-link`
(`4b90be94`).

---

## 9. Independent consultation (visual consultant)

**Consultant route:** `/home/c03rad0r/hermes-orchestration/scripts/fleet/visual_consult.py`,
per the `visual-consultant` skill. The figure consulted is
`docs/analysis/assets/amplifier-hypothesis-ebar.png` (the beamwidth-narrowing +
cost-per-needed-dB panel).

**PITFALL RECORDED (per the skill, and re-confirmed here):** the CLI prints
`visual_review: APPROVED` from its own `--verdict` **default**; **that token is NOT the
model's opinion.** Only the model's own `VERDICT:` line, read from the end of the answer
body, counts. Both lines are quoted below with an explicit statement of which is which,
so this record is not repeatable as a false approval.

**Engagement status / served model / verdict / verbatim answer:** _(recorded in §9.1 below
after the consult completes; if the lane cannot be reached, the failure is recorded verbatim
and no verdict is claimed.)_

### 9.1 Consult record

_(pending)_

---

*End of analysis.*
