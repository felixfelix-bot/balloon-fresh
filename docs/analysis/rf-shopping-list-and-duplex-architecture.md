# RF shopping list and duplex architecture — pico-balloon ground-station **internet gateway**

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is a `docs/analysis/`
> findings document. It orders nothing, buys nothing, freezes no schematic and no BOM.
> The one *decision* it reaches (duplex / T-R architecture, §1) is carried into
> **ADR-070**, which is **Proposed** — an ADR marked Proposed is **not frozen** and must
> not be treated as decided. Every price below is a vendor page read this session, marked
> CONFIRMED, or an explicit `TODO(unverified)`.

| | |
|---|---|
| Date | 2026-10-08 |
| Branch | `design/rf-shopping-list` |
| Worktree | `/home/c03rad0r/worktrees/bf-shoplist` |
| Base commit | `github/main` @ `09e1b69` ("Merge PR #23 … e80-board-bind") |
| Author | Hermes agent (worker), for Felix (operator) |
| Lens | RF front end / duplex architecture / parts sourcing. **Not** re-deriving: the 433 downlink link budget, the positioner, the cost metric or the Tier model — those live on sibling branches (see *Read first*). |
| Repro | `python3 docs/analysis/rf_shopping_list_model.py` — prints every numeric table below |
| Access date | **2026-10-08** for every URL |

**Read first (sibling work this analysis consumes and does not re-derive):**

- `design/ground-station-flrc-max` @ `github/design/ground-station-flrc-max` —
  `docs/analysis/ground-station-flrc-max-throughput.md` + **ADR-067** (433 downlink fixed on
  FLRC-max; power on the balloon).
- `design/ground-station-lowpower-link` — `docs/analysis/ground-station-lowpower-link-and-shared-dish.md`
  + **ADR-066** (low-power LR2021 study).
- `design/gain-per-dollar` — `docs/analysis/ground-station-gain-per-dollar.md` + **ADR-068**
  (buy a Yagi before a dish).
- `design/positioner-lowcost` — **ADR-067-positioner-architecture**.
- `design/tier0-accessible` — **ADR-069** (Tier-0 accessible ground station).
- `design/ground-station-bom` @ `283cad72` — `docs/analysis/ground-station-bom-candidates.md`
  (**the antenna / coax / rotator prices reused in §5** — re-verified where noted).
- `docs/analysis/radio-legal-power-limits.md` + `docs/analysis/radio_power_limits_model.py`
  (the EIRP/PSD ceilings), `docs/2G4-LINK-BUDGET-ANALYSIS.md`,
  `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` (the band split),
  `docs/adr/041-rf-frontend-licence-exempt.md`, `docs/ssot/parameters.json`.

---

## 0. Bottom line (5 findings, answer first)

> **TASK 0, plain answer: DO NOT BUY A CIRCULATOR.** TX (2.4 GHz) and RX (433 MHz) are on
> different bands, so a **single-antenna circulator cannot be used at all** — a ferrite
> circulator is a narrowband (~10–20 %) device and a 2.4 GHz unit has no 433 MHz path. The
> correct duplexer is **two separate band antennas** (or, if one feedline is mandatory, a
> **band diplexer**). Two antennas give **≈ 68 dB** TX→RX isolation (model §0(a)); a 2.4 GHz
> circulator would give **≈ 20 dB at one band and nothing at the other**. This deletes a
> purchase.

1. **Full duplex with no switching, no circulator.** 433 MHz RX and 2.45 GHz TX on two
   separate antennas; the two bands are **5.65×** apart (2.5 octaves) — model §0.
2. **The residual problem is the ground's own 2.4 GHz TX leaking into its own 433 RX.**
   At +12 dBm conducted and ≈ 68 dB of rejection, the leakage at the LNA input is
   **−56 dBm** — **78 dB below** the owned TQP3M9037's +22 dBm CW input rating and **76 dB
   below** its +20 dBm P1dB. The fix is a **433 MHz band-pass filter *before* the LNA**
   (the LNA is wideband, 0.7–6 GHz, and would otherwise amplify the leak), plus an optional
   €5–10 PIN limiter. Model §0b.
3. **The 2.4 GHz uplink is EIRP-cap-limited, not PA-limited — so you need an *attenuator*,
   not a PA, for the recommended antenna.** Under the licence-exempt PSD rule
   (10 dBm/MHz EIRP, EN 300 328 / Vfg. 91/2025) the ceiling at FLRC-max bandwidth
   (2.666 MHz) is **14.26 dBm EIRP**. With the recommended 11.1 dBi ground antenna the
   conducted power needed is only **+3.2 dBm** — i.e. the LR2021's own +12 dBm HF PA must be
   turned **down ~9 dB**. A **0–31.75 dB digital step attenuator** (€19–26) delivers the
   closed-loop range the operator wants. A PA is only justified if the operator moves to a
   higher legal footing (amateur / fixed link) or a low-gain antenna.
4. **Capacity and range trade off almost neutrally here.** The EIRP ceiling *falls* as
   10·log₁₀(BW) as the FLRC rate rises, while sensitivity improves only ~1–2 dB per step →
   the uplink reaches **≈ 4–5 km at *every* FLRC rate** (model §2b). The gateway is a
   **~4.5 km-radius local service** under licence-exempt, not a long-haul backhaul.
5. **Red Pitaya: it can do neither job the operator hoped.** Its analog bandwidth is
   **DC–60 MHz** (125 MS/s), so it **cannot** confirm the XR-613 divider at 433 MHz or
   2.4 GHz (buy a **LiteVNA 62**, 50 kHz–6.3 GHz), and its DAC also stops at 60 MHz, so it
   **cannot generate FLRC at 2.4 GHz**. FLRC is **GMSK + proprietary convolutional FEC +
   interleaving** (LR2021 datasheet §18.1; not "fast chirp" — **the brief's premise is
   wrong**), with no public PHY reverse-engineering to compare with the gr-lora precedent.
   Verdict: **not economical**, a research project at best. Its valuable uses are **behind
   a downconverter** (IF receiver / waveform generator / spectrum monitor / logic analyser),
   never as a direct 433/2.4 GHz instrument. Model §3.

---

## 1. TASK 0 — the duplex / T-R architecture, and the circulator decision

### 1.1 The architecture, stated

The ground station is an **internet gateway** for the balloon **bent pipe**:

```
  ground user ──WiFi/Ethernet──►  GATEWAY  ──2.45 GHz TX──►  balloon (bent pipe) ──► user
                                 (this box)  ◄──433 MHz RX──  balloon
        ground STATION: RECEIVE 433 MHz (balloon→ground)  +  TRANSMIT 2450 MHz (ground→balloon)
        → full duplex, simultaneous, both directions always on.
```

Per `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` the band split is **433 MHz down /
2.4 GHz up**. At the **ground** end this means: **RX = 433 MHz**, **TX = 2.4 GHz**. A
half-duplex T/R switch is therefore **ruled out** (both directions run at once).

### 1.2 Isolation achievable per option (model §0)

| Option | Isolation mechanism | Isolation | Verdict |
|---|---|---:|---|
| **(a) two separate band antennas** ✅ | antenna separation + pattern + polarisation (20 dB) + 433 antenna feed mismatch at 2.4 GHz (3 dB) + 433 MHz BPF rejection at 2.4 GHz (45 dB) | **≈ 68 dB** | **RECOMMENDED** — no switching, no circulator, cheapest |
| (b) band diplexer on one dual-band feedline | 433 BPF rejection (45 dB) + diplexer port isolation (~15 dB) | ≈ 60 dB | only if ONE antenna must serve both bands |
| (c) single-band circulator | ferrite circulator isolation at *its* band | ≈ 20 dB | **NOT APPLICABLE** — a 2.4 GHz circulator has **no 433 MHz path**; bands differ |

**Why (c) is not just worse but impossible:** a circulator/isolator is a **narrowband
ferrite** device (typ. 10–20 % bandwidth). Routing two bands **2.5 octaves apart** through
one circulator is not a thing — it would need two circulators (one per band) and two
filters, i.e. it degenerates into (a)/(b) with extra loss and cost. The isolation figures
quoted for the model (20 dB, 0.4 dB IL) are the usual 2.4 GHz coaxial-circulator class and
are given only for the *conditional* case in §3.

**Residual problem and how filtering handles it.** The one real hazard is the ground's own
2.4 GHz TX coupling into the ground's own 433 MHz RX path — worsened because the owned LNA
(TQP3M9037) is **wideband (0.7–6 GHz)** and will happily amplify 2.4 GHz leakage. Two
mitigations, both in the parts list:

1. **Put a 433 MHz band-pass filter (BPF) *before* the LNA.** This is the real protection:
   a 2-cavity or SAW/LTCC BPF rejects 2.4 GHz by ~45 dB. The wideband LNA then only sees
   in-band 433 MHz, where the leakage does not exist.
2. **Optional input limiter** (PIN-diode, €4–10) as insurance against a *third-party*
   2.4 GHz transmitter at close range (a phone/hotspot at cm distance) — see §7.

**Computed leakage** (model §0b): +12 dBm conducted − 68 dB = **−56 dBm** nominal;
pessimistic (48 dB isolation) = **−36 dBm**. Even with a +30 dBm external PA the leakage is
**−38 dBm**. All are far below the TQP3M9037's +22 dBm CW input rating and +20 dBm P1dB.
**A limiter is therefore not required for this architecture** — but it is cheap insurance
and it is in the list.

**Verdict → BUY NO CIRCULATOR.** Spend the money instead on a 433 MHz BPF (~€10–24) and a
2.4 GHz BPF (~€18–28), which together are cheaper and more effective. This is the decision
carried into **ADR-070**.

---

## 2. TASK 1 — 2.4 GHz uplink PA with controllable gain

### 2.1 First, size it: what conducted power is actually needed?

Uplink link budget (`required_EIRP = S + FSPL(d) − G_balloon`, `G_balloon ≈ 0 dBi`),
sensitivities from the **LR2021 datasheet Rev 2.1, Table 3-13** ("FLRC 2.4 GHz 1% PER",
local copy `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`):

| FLRC rate | BW (MHz DSB) | sens (dBm) | req. EIRP @1 km | @5 km | @10 km | **legal ceiling** |
|---:|---:|---:|---:|---:|---:|---:|
| 2600 kbps (eff 1950) | 2.666 | −99.0 | +1.2 | +15.2 | +21.2 | **14.26 dBm** |
| 2080 | 2.222 | −100.0 | +0.2 | +14.2 | +20.2 | 13.47 |
| 1300 | 1.333 | −101.5 | −1.3 | +12.7 | +18.7 | 11.25 |
| 1040 | 1.333 | −102.5 | −2.3 | +11.7 | +17.7 | 11.25 |
| 650 | 0.740 | −104.0 | −3.8 | +10.2 | +16.2 | 8.69 |
| 520 | 0.571 | −105.0 | −4.8 | +9.2 | +15.2 | 7.57 |

Legal ceiling = `min(20 dBm, 10 dBm/MHz + 10·log₁₀(BW))`, from **EN 300 328 V2.2.2 / Vfg.
91/2025 57c** as worked out in `docs/analysis/radio-legal-power-limits.md`
(the 100 mW EIRP tier carries a **10 mW/MHz EIRP power-density condition**). Note the
disagreement with ADR-041's "100 mW EIRP" statement — the PSD condition is the binding one
(see §8).

**Conducted power needed at the antenna port** (model §1b):

| Ground antenna gain | Conducted needed to hit the 14.26 dBm ceiling | LR2021 HF PA (+12 dBm) must… |
|---:|---:|---|
| 2 dBi (omni) | +12.3 dBm | amplify 0.3 dB (a wash) |
| 8 dBi (small patch/Yagi) | +6.3 dBm | **attenuate 5.7 dB** |
| **11.1 dBi (reco. Sirio SLP-17)** | **+3.2 dBm** | **attenuate 8.8 dB** |
| 18 dBi | −3.7 dBm | attenuate 15.7 dB |
| 24 dBi (2.4 GHz dish) | −9.7 dBm | attenuate 21.7 dB |

> **So the answer to "can we buy a PA with controllable gain?" is: you need a
> *controllable-gain element*, and the operator's own LR2021 + a step attenuator is that
> element.** The radio's HF PA already gives +12 dBm with a 0.5 dB-step TX-power control;
> a DSA adds 0–31.75 dB in 0.25 dB steps for the closed loop. A PA is only needed if
> the operator (i) uses an omni antenna, (ii) operates on a **higher legal footing**
> (amateur 2400–2450 MHz or a fixed-link licence — `TODO(unverified)` exact German limits),
> or (iii) wants headroom the ISM cap forbids.

### 2.2 Closed-loop gain-control range required (model §1c)

- Path-loss swing from **0.5 km (balloon overhead) → 50 km**: **40 dB**
  (`20·log₁₀(50/0.5)`).
- Plus the fixed trim to sit exactly on the legal ceiling for the chosen antenna: 0–22 dB.
- **Total closed-loop range ≈ 40–45 dB.** A **0–31.75 dB / 0.25 dB-step DSA** plus the
  radio's own power control covers it. Drive the loop from the downlink RSSI (the 433
  downlink already carries telemetry) or GPS range, exactly as the operator proposed.

### 2.3 (a) 2.4 GHz PA/FEM modules **with a gain-control or PA-enable pin**

| Part | Type | Control | Gain-control evidence | Source / price |
|---|---|---|---|---|
| **Skyworks SKY66112-11** | 2.4 GHz FEM: PA + LNA + SPDT | pins **CTX / CRX / CSD / CHL / ANT_SEL** (GPIO, 1.6–3.6 V); **VCC2** sets saturated output | **G_SAT = 22 dB**; POUT **+21 dBm** (VCC2 3.0 V) → **+16 dBm** (1.8 V) → **+13 dBm** (1.2 V) = **~8 dB controllable output + on/off**; RX gain 11 dB, NF 2 dB, RX IP1dB −8…−14 dBm, bypass −2 dB | Datasheet via Wayback: `web.archive.org/web/20240404044111id_/https://www.skyworksinc.com/-/media/SkyWorks/Documents/Products/2201-2300/SKY66112-11_203225O.pdf` (CONFIRMED). Chips: AliExpress `[1005013010805755]` €1.99 ea / 5-for-€10.39 |
| **Nordic nRF21540** | 2.4 GHz FEM: PA (+21 dBm) + LNA (+13 dB) + SPDT | digital mode pins; **output power set by the radio drive level** | PA +21 dBm, LNA +13 dB **`TODO(unverified)`** — dealer listing only this session | AliExpress dev board `[1005013003570208]` €148.39 (board, not chip); chips `[1005009501695622]` €7.69/5 |
| **AT2401C / RFX2401C** | Chinese 2.4 GHz FEM (PA+LNA+SPDT) | TX_EN / RX_EN pins (on/off only) | **+20 dBm class; on/off only, no analog gain pin** `TODO(unverified)` | AliExpress `[1005012953391600]` €6.19/10 |

**Honest summary:** WiFi-class FEMs give you **on/off and mode switching** plus, in the
SKY66112-11's case, **~8 dB of analog output control via VCC2**. None of them gives a
wide, calibrated, programmable gain range. That is what the DSA in (b) is for.

### 2.4 (b) Discrete 2.4 GHz PA + digital step attenuator (the recommended architecture)

| Part | What | Key spec | Source / price |
|---|---|---|---|
| **RF2126 module** | 2.4 GHz PA board on a heatsink (RF2126 is the classic 400–2700 MHz ~1 W 2.4 GHz linear PA with an analog bias/control pin) | listing: **400–2700 MHz, 2.4 GHz, 1 W**, with heatsink. **Exact gain-control pin = `TODO(unverified)`** (Qorvo product/datasheet pages are 429-gated to the fleet and not on the Wayback CDX) | AliExpress `[1005011559280074]` **€7.69** (title CONFIRMED) |
| **DYKB 2.4 GHz 4 W bidirectional amp** | PA + LNA booster with an internal T/R switch (its *own* T/R — not a circulator) | listing: **36 dBm (4 W), 802.11b/g/n**, SMA. `TODO(unverified)` gain-control | AliExpress `[1005013140948905]` €41.39 |
| **WYDZ-PA-2.4–2.5 GHz-10 W** | bench PA | **40 dB gain, 10 W**, heatsink | AliExpress `[1005006850415450]` **€65.39** |
| **GCM2627** | 2.3–2.7 GHz 4 W bidirectional | `TODO(unverified)` | AliExpress `[1005012136940057]` €48.39 |
| **Digital step attenuator — pSemi PE43711** | **7-bit** UltraCMOS DSA | **9 kHz – 6 GHz**, **0.25 dB LSB → 31.75 dB**, glitch-less, 1.8 V control, 50 Ω. *(This is the correct part class for the closed loop.)* | Spec CONFIRMED: `psemi.com/products/digital-step-attenuators/pe43711`. Price `TODO(unverified)` (distributor pages JS-gated) |
| **DSA — ADI HMC425A** | 0.5 dB LSB 6-bit DSA | datasheet PDF fetched (`analog.com/media/en/technical-documentation/data-sheets/HMC425A.pdf`) | price `TODO(unverified)` |
| **DSA — ready-made SMA module** | **9 kHz–6 GHz, 0–31.75 dB** digital step attenuator (PE43711-class board) | listing CONFIRMED | AliExpress `[1005012321787574]` **€18.89** (alt. `[1005013206648600]` €25.79 for the "0.25 dB step" variant) |

**Recommended 2.4 GHz uplink chain:** `LR2021 HF PA (+12 dBm, 0.5 dB steps) → 2.4 GHz BPF →
PE43711 DSA (0–31.75 dB) → GCM2627/RF2126 PA *only if a higher legal footing* → 2.4 GHz BPF
→ SLP-17 antenna. The DSA is the controllable-gain element; the PA is optional.

### 2.5 (c) Integrated PA + circulator/isolator module

**Say plainly: none exists at this scale.** No maker-scale product integrates a 2.4 GHz PA
with a ferrite circulator in one module. What *looks* like one is a **bidirectional WiFi
booster** (§2.4), which contains a PA + an LNA + an **internal SPDT T/R switch** — a
switch, not a circulator. Integrated circulators live in **radar T/R modules** (much higher
cost/power) and in some historic 802.11b PA modules. **For this ground station none is
needed anyway** (§1: bands differ → no circulator). `TODO(unverified)`: a systematic survey
of radar T/R module vendors was out of scope.

---

## 3. TASK 2 — circulator recommendation (conditional; the operator should NOT buy one)

Kept because the brief asked, and in case the operator overrules §1. If a circulator *is*
ever wanted — e.g. for a same-band single-antenna TDD link elsewhere in the system —
these are real, purchasable 2.4 GHz parts:

| Product | Band | Connector | Price | Source |
|---|---|---|---|---|
| **WG2020X-1** microstrip isolator/circulator | **2400–2500 MHz** | (module, drop-in) | **€33.79** | AliExpress `[1005012379362316]` |
| Coaxial **ferrite circulator** | 1.8–3.8 GHz | SMA | €86.39 | AliExpress `[1005010142548438]` |
| Coaxial **isolator** | 2–4 GHz full-band | SMA | €89.99 | AliExpress `[1005012363780841]` |
| TZT **UIYBCC3234A** broadband circulator | 2.0–4.0 GHz | SMA / N | €115.99 / €116.99 | AliExpress `[1005009457620145]`, `[1005009456218286]` |
| 2400–2500 MHz microstrip isolator/circulator | 2.4 GHz | module | €81.69 | AliExpress `[1005007485613149]` |

**Typical specs to demand (cheap drop-in class):** isolation **18–22 dB**, insertion loss
**0.3–0.5 dB**, power handling **10–30 W CW**, SMA/N. *Verify isolation from the vendor's
spec sheet — the AliExpress listings above mostly do not print it, so the numbers are the
class norm and each part's isolation is `TODO(unverified)` until the listing/datasheet is
read.*

### 3.1 The key spec, stated as the task asked

> **isolation_dB must exceed (P_TX_conducted − LNA_max_input).**

Both numbers, for this design:

- **P_TX_conducted** = **+12 dBm** (LR2021 HF) baseline; **+30 to +33 dBm** only if a PA is
  added (and only on a non-ISM footing).
- **LNA_max_input** = **+22 dBm CW** for the owned **TQP3M9037** (Qorvo: *"High input power
  ruggedness, 22 dBm CW"*; OP1dB = **20 dBm** — an unusually rugged LNA).

Model §2 arithmetic:

| P_TX | −20 dB circulator → at LNA | TQP3M9037 (P1dB +20 dBm) | typical LNA (P1dB ≈ −10 dBm) |
|---:|---:|---|---|
| +12 dBm | −8 dBm | OK | **compressed / at risk** |
| +20 dBm | 0 dBm | OK | **compressed / at risk** |
| +30 dBm | +10 dBm | OK | **compressed / at risk** |
| +33 dBm | +13 dBm | OK | **compressed / at risk** |

> **A 20 dB circulator alone may NOT protect an LNA from a PA** — for any *typical* low-NF
> LNA (P1dB ≈ −10 dBm) the residual +0…+13 dBm overloads it badly. It only looks "OK" here
> because the TQP3M9037 is exceptionally rugged (+20 dBm P1dB, +22 dBm CW). Protection
> still needs a **limiter** (§7) and/or **TX blanking**, never a 20 dB circulator alone.

---

## 4. TASK 3 — Red Pitaya, answered honestly

**The Red Pitaya owned is a STEMlab 125-14 class board.** Verified specs
(`redpitaya.com/product/stemlab-125-14/`, CONFIRMED): ADC/DAC **125 MS/s, 14-bit**, RF
inputs **DC-coupled, bandwidth DC–60 MHz**, 1 MΩ / ±1 V, 2 ch in + 2 ch out; RF outputs
**DC–60 MHz, 50 Ω**. **Nyquist 62.5 MHz.**

### 4.1 (a) Can it CONFIRM the XR-613 power divider at 433 MHz / 2.4 GHz? — **No.**

- **Direct input bandwidth is DC–60 MHz.** 433.92 MHz is **7.2×** above the 60 MHz edge;
  2450 MHz is **40.8×** above it. The XR-613 is specified **DC–5 GHz**, so the Red Pitaya
  cannot even reach its upper edge (83× above DC–60 MHz). **It cannot confirm the divider
  at either band of interest.**
- What it *can* do: its **VNA app** can characterise the divider only **below ~60 MHz**
  (i.e. DC-5 GHz's bottom decade) and its spectrum/logic-analyzer roles are useful for
  baseband. Neither touches 433 MHz or 2.4 GHz.

**Recommend instead (purchasable, sourced this session):**

| Instrument | Range | Price | URL |
|---|---|---:|---|
| **NanoVNA-H4** | 10 kHz – 1.5 GHz — **covers 433 MHz, NOT 2.4 GHz** | **US$134.95** (with SOLT cal kit) | `nooelec.com/store/nanovna-h4.html` (CONFIRMED); AliExpress bare `[1005010741168289]` €56.69 |
| **LiteVNA 62** ✅ | **50 kHz – 6.3 GHz — covers BOTH 433 MHz and 2.4 GHz** | **€166.99** | AliExpress `[1005003536382606]` (CONFIRMED listing) |
| LiteVNA 64 | 50 kHz – 6.3 GHz, 4" screen | €196.99 | AliExpress `[1005011782598787]` |

**Answer: buy a LiteVNA 62 (or 64).** The NanoVNA-H4 is cheaper but stops at 1.5 GHz and
therefore **cannot** verify a 2.4 GHz port of the divider.

### 4.2 (b) Can it GENERATE FLRC directly, replacing the LR2021? — **No.**

Two independent blockers:

1. **Bandwidth.** The DACs are **DC–60 MHz**. FLRC at 2.4 GHz uses a **2.666 MHz** channel
   *centred at 2450 MHz*, and the sub-GHz FLRC sits at 433/868 MHz. The Red Pitaya cannot
   reach either carrier directly; it could only feed a **baseband/IF** into an external
   upconverter.
2. **Waveform.** The brief calls FLRC "Semtech fast chirp". **That premise is wrong.** The
   LR2021 datasheet §18.1 says verbatim:
   > *"The Fast Long Range Communication (FLRC) modem is designed for high-speed
   > communication, utilizing a combination of **GMSK (Gaussian Minimum Shift Keying) with
   > forward error correction and interleaving** techniques."*

   So the modulation is **GMSK** (a standard, well-understood CPM family) plus a
   **proprietary convolutional FEC + interleaver + packet format + sync word + whitening**.
   The datasheet defers the real detail to **AN1200.101** and every page is stamped
   **"Proprietary & Confidential"** (`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`).

**Reverse-engineering precedent.** LoRa's PHY (also Semtech-proprietary) *was* cracked by
the community over years — the `gr-lora` / Knight–Seeber line of work — because LoRa's
**chirp spread spectrum** leaks its parameters (chirp slope, sync up-chirps) that a
receiver can recover blind. FLRC is **GMSK**, i.e. far less structurally distinctive, and
its discriminating detail (the FEC polynomial, interleaver depth, whitening, CRC, packet
preamble/AGC timing) is exactly what is *withheld*. **No public FLRC PHY
reverse-engineering of comparable standing is known** `TODO(unverified)` (search engines
are bot-blocked from this fleet; this is stated as absence-of-evidence, not evidence of
absence). To *interop with a real LR2021* a Red Pitaya would have to reproduce that
proprietary stack bit-for-bit.

**Verdict:** **NOT ECONOMICAL.** It is a multi-month reverse-engineering + FPGA-SDR
research project, not a parts substitution — and its success criterion (a real LR2021
demodulating it) is exactly the part that is hardest to meet. Do **not** plan to replace
the LR2021.

**Valuable Red Pitaya uses in this project (honest list):**

| Use | Works? | Why |
|---|---|---|
| **IF receiver behind a downconverter** (433/2450 → 10–60 MHz) | ✅ | exactly its designed band; add a mixer (the operator owns one) + LO |
| **Waveform / IF generator** (GMSK baseband experiments) | ✅ | feeds an upconverter; useful for bench work |
| **Spectrum monitor** | ✅ but only **≤ 62.5 MHz** | cannot see 433/2.4 GHz |
| **LO source** | ⚠️ only **≤ 62.5 MHz** | DAC range honest limit — not 433/2450 MHz |
| **Logic analyser** (SPI/IRQ on the LR2021) | ✅ | already used this way in the repo (`docs/lr2021-dual-track-master-plan-2026-07-17.md`) |
| **Direct 2.4 GHz FLRC transmitter** | ❌ | DC–60 MHz DAC + proprietary PHY |
| **Direct 433/2.4 GHz VNA** | ❌ | DC–60 MHz input |

---

## 5. TASK 4 — antennas and coax for a full-duplex gateway

### 5.1 433 MHz receive antenna (recommended tier: Diamond A-430S15R class)

| # | Product | Gain | Conn. | Notes | Price | Source |
|---|---|---|---:|---|---:|---|
| A1 ✅ | **Diamond A-430S15R** | **14.8 dBi** (mfr) | **PL (SO-239)** | 430–440 MHz, 15 el, F/B >14 dB, 50 W, VSWR ≤1.4, 2245×370×73 mm, 970 g, wind 0.11 m², mast 25–47 mm | **€74.50** | `funktechnik-bielefeld.de/diamond-a-430s15r-uhf-15-element-richtantenne-70cm-band` (CONFIRMED) |
| A2 | Sirio WY 400-10N | 14 dBi | N-f | ~2.0 m boom, 150 W | €155.00 | sibling BOM (CONFIRMED) |
| A3 | FlexaYagi FX 7073 | 15.8 dBd (18.0 dBi) | — | 5.07 m boom, highest gain | €215.00 | sibling BOM (CONFIRMED) |
| A4 (cheap) | 2 m 14 dBi 433 MHz outdoor Yagi | 14 dBi | N | weatherproof | €62.99 | AliExpress `[1005011959700413]` |
| A5 (cheapest) | 433 MHz Yagi | — | N | base-station UHF | €38.39 | AliExpress `[1005012526543407]` |

> **Connector caveat:** the A-430S15R terminates in a **PL/SO-239**, so either terminate
> the coax with a PL plug or carry an **N→SO-239 adapter**. Flag this in the order.

### 5.2 2.4 GHz transmit antenna (small patch / Yagi class)

| # | Product | Gain | Conn. | Notes | Price | Source |
|---|---|---|---:|---|---:|---|
| B1 ✅ | **Sirio SLP-17** (log-periodic dipole array) | **11.1 dBi** | — | 1700–2500 MHz, directional, beamwidth 58°(H)/46°(E), F/B >24 dB, 345×135×73 mm, 400 g, mast 25–42 mm, ABS radome. DE ham shop → clean customs | **€59.00** | `funktechnik-bielefeld.de/sirio-slp-17-1800-2500-mhz-richtantenne` (CONFIRMED) |
| B2 | 2.4 GHz Yagi | 25 dBi | RP-SMA | 2400–2500 MHz | €22.39 | AliExpress `[1005012053064904]` |
| B3 | 2.4 GHz Yagi | 16–18 dBi | RP-SMA | 1.5 m | €17.29 | AliExpress `[1005012521972901]` |
| B4 | Sirio SMS-2.4×6-12 sector | 12 dBi (9.9 dBd) | N | 210 km/h wind, mast 30–62 mm | €119.00 | `funktechnik-bielefeld.de/zubehoer/antennen/wlan-antennen/` (CONFIRMED) |
| B5 | Diamond MG-200S 2400 MHz | 7 dBi | N | fibreglass omni — **not** directional | €69.00 | same category page (CONFIRMED) |

> RP-SMA on the AliExpress Yagis is a **caveat** — RP-SMA is a WiFi-standard reverse-polarity
> connector; you will need an **RP-SMA→SMA adapter** to mate with lab coax. Prefer B1 (ham
> connector) or B4 (N) for a built gateway.

### 5.3 Low-loss coax and connectors (dB per 10 m at both bands)

Attenuation from **Kabel-Kusch** product pages (CONFIRMED, their own dB/100 m tables):

| Cable | Ø | @433 MHz /10 m | @2.4 GHz /10 m | Price | Source |
|---|---:|---:|---:|---:|---|
| **Airborne 10** (LMR-400 class) ✅ | 10.3 mm | **0.76 dB** | **1.92 dB** | **€4.30/m** (page read this session; the sibling BOM recorded €6.50/m — see §8) | `kabel-kusch.de/produkt/airborne-10/2` |
| Ecoflex 10 | 10.3 mm | 0.85 dB | 2.24 dB | €6.70/m | `kabel-kusch.de/produkt/ecoflex-10/14` |
| Ecoflex 15 | 14.6 mm | 0.61 dB | 1.62 dB | €13.60/m | `kabel-kusch.de/produkt/ecoflex-15/17` |
| Aircell 7 | 7.3 mm | 1.29 dB | 3.38 dB | €4.06/m | sibling BOM (CONFIRMED) |

Connectors (sourced this session):

| Item | Price | Source |
|---|---:|---|
| N-male crimp for LMR-400/RG-213 (10 pcs) | €14.35 | AliExpress `[32875381213]` |
| N-male crimp crimp (5 pcs) | €4.69 | AliExpress `[1005003172618291]` |
| SMA-male crimp for RG-58/LMR-195 (5/20 pcs) | €10.79–11.59 | AliExpress `[1005009644016170]`, `[1005009699890601]` |
| PL-259/UHF→SMA adapter (for the A-430S15R) | €3.49 | AliExpress `[1005006143199910]` |

**Coax run guidance:** at 2.4 GHz a 10 m Airborne-10 run costs **1.92 dB** — small next to
the 68 dB of duplex isolation, so cable loss is not critical here; keep the run short and
terminate with N where the antenna allows.

---

## 6. TASK 5 — THE SHOPPING LIST (owned parts first)

**Status key:** **OWNED** = the operator already has it · **TO BUY** · **OPT** = optional /
only under a stated condition. Prices are vendor pages read 2026-10-08; AliExpress figures
are **"from"** prices from the German search listing (item page price is JS-rendered, so a
"from" price is labelled as such).

| # | Item | Qty | Status | Price (EUR) | Note / URL |
|---|---|---:|---|---:|---|
| 1 | **TQP3M9037** wideband LNA (0.7–6 GHz, 20 dB, NF 0.4, P1dB +20, +22 dBm CW) | 1 | **OWNED** | — | `qorvo.com/products/p/TQP3M9037` (Wayback) |
| 2 | **XR-613** power divider (DC–5 GHz) | 1 | **OWNED** | — | identity `TODO(unverified)` — not found in-repo or on AliExpress |
| 3 | Unmarked **RF/LO/IF mixer** module | 1 | **OWNED** | — | **specs `TODO(unverified)`** — model number unknown |
| 4 | **Red Pitaya** STEMlab 125-14 | 1 | **OWNED** | — | `redpitaya.com/product/stemlab-125-14/` (DC–60 MHz) |
| 5 | **433 MHz RX antenna** — Diamond A-430S15R (14.8 dBi, PL) | 1 | TO BUY | 74.50 | funktechnik-bielefeld.de (CONFIRMED) |
| 6 | **2.4 GHz TX antenna** — Sirio SLP-17 (11.1 dBi, dir.) | 1 | TO BUY | 59.00 | funktechnik-bielefeld.de (CONFIRMED) |
| 7 | **433 MHz band-pass filter** (BPF before the LNA) | 1 | TO BUY | 9.29–24.19 | AliExpress `[1005012493261239]` €24.19 (FBP-433s) / `[1005004047000536]` €9.29 |
| 8 | **2.4 GHz band-pass filter** (TX path) | 1 | TO BUY | 17.79–23.99 | AliExpress `[1005012653486194]` €17.79 / `[32820151286]` €23.99 |
| 9 | **LNA input limiter** (PIN-diode, 10 MHz–6 GHz) | 1 | TO BUY | 4.39–9.99 | AliExpress `[1005012328874838]` €4.39 / `[1005012056412109]` €9.99 (see §7) |
| 10 | **Digital step attenuator** 0–31.75 dB, 0.25 dB step (PE43711-class SMA module) | 1 | TO BUY | 18.89 | AliExpress `[1005012321787574]` (CONFIRMED title) — the closed-loop gain control |
| 11 | **2.4 GHz PA** — RF2126 module (400–2700 MHz, 1 W) | 1 | **OPT** | 7.69 | only on a non-ISM legal footing or with an omni antenna |
| 12 | **Coax** Airborne 10 (LMR-400 class) | 15 m | TO BUY | 64.50 | kabel-kusch.de @€4.30/m (CONFIRMED) |
| 13 | **N-male crimp connectors** (LMR-400) | 4 | TO BUY | 5.74 | AliExpress `[32875381213]` €14.35/10 ≈ €5.74/4 |
| 14 | **PL→SMA adapter** (for A-430S15R) | 1 | TO BUY | 3.49 | AliExpress `[1005006143199910]` |
| 15 | **TinySA Ultra** spectrum analyser (100 kHz–5.3 GHz) — bench verification of the gateway | 1 | **OPT** | 132.39 | AliExpress `[1005009969751915]` |
| 16 | **LiteVNA 62** (50 kHz–6.3 GHz) — verify XR-613 at 433 MHz **and** 2.4 GHz | 1 | TO BUY | 166.99 | AliExpress `[1005003536382606]` (CONFIRMED listing) |

**Roll-ups** (excluding owned items):

| Build | Items | Indicative total |
|---|---|---:|
| **(i) Cheapest working gateway** | 433 RX antenna (cheap AliExpress Yagi, €38.39) · 2.4 GHz Yagi (€17.29) · 433 BPF (€10.99) · 2.4 GHz BPF (€17.79) · limiter (€4.39) · DSA (€18.89) · 10 m Airborne-10 (€43.00) · connectors+adapter (€9.23) | **≈ €160** |
| **(ii) Recommended build** | A-430S15R (€74.50) · Sirio SLP-17 (€59.00) · 433 BPF FBP-433s (€24.19) · 2.4 GHz BPF (€17.79) · limiter (€9.99) · PE43711 DSA module (€18.89) · OPT RF2126 PA (€7.69) · 15 m Airborne-10 (€64.50) · N connectors (€5.74) · PL adapter (€3.49) · **LiteVNA 62 (€166.99)** | **≈ €453** |

> Both roll-ups are **indicative** (shipping, VAT, and the AliExpress "from" prices are not
> settled). The single biggest recommended-build line is the **LiteVNA 62** — it is what
> replaces the Red Pitaya for confirming the XR-613, and it is deliberately included.

---

## 7. TASK 6 — LNA protection for the owned TQP3M9037

**The LNA being protected:** Qorvo **TQP3M9037** — bandwidth **0.7–6 GHz** (Qorvo product
page; *the brief said 0.1 MHz–6 GHz — see §8*), gain 20 dB, NF 0.4 dB, **OP1dB = +20 dBm**,
**"+22 dBm CW" input-power ruggedness**, integrated shutdown control.

**Protection needed, from the numbers:**

- In **this** architecture the leakage into the LNA input is **−56 dBm nominal / −36 dBm
  pessimistic** (model §0b) — that is **56–78 dB below** the LNA's +20 dBm P1dB. **No
  limiter is strictly required.**
- **What IS required: a 433 MHz BPF *before* the LNA.** The LNA is wideband (0.7–6 GHz), so
  without a pre-filter it would amplify any 2.4 GHz leakage by +20 dB and pass it to the
  mixer. The filter — not the limiter — is the primary protection. **Put the BPF first.**
- **The limiter is cheap insurance** against a *third-party* 2.4 GHz transmitter at close
  range (a phone/hotspot at centimetres puts easily +10…+20 dBm on a nearby antenna), and
  it is required if the operator ever adds a co-located 2.4 GHz PA at the same antenna.

**Sourced limiters (all CONFIRMED listings, 10 MHz–6 GHz, SMA):**

| Product | Rating thresholds offered | Price |
|---|---|---:|
| Broadband PIN-diode RF limiter, SMA (0 dBm / 10 dBm / 20 dBm) | 0/10/20 dBm | **€4.39** — AliExpress `[1005012328874838]` |
| PIN-diode SMA limiter, 10 M–6 GHz (+10 / +20 / 0 dBm) | 0/10/20 dBm | €8.89–9.99 — `[1005012986456665]`, `[1005012056412109]` |
| PIN-diode limiter, small volume (0/10/20/30/36 dBm) | 0–36 dBm | €8.19 — `[1005002274310430]` |
| RF coaxial limiter, SMA, 1 MHz–1 GHz, LM-20s | 10 dBm | €24.39 — `[1005004093311795]` |
| DYKB RF limiter 100 M–12 GHz / 400 M–6 GHz, high-power CW | — | €39.99 — `[1005013159184538]` |

**Recommendation:** one **PIN-diode limiter in the 10–20 dBm threshold class** (~€5–10,
row 1 or 2 above) in series after the 433 BPF and before the LNA. Choose the threshold
just above the expected in-band 433 MHz signal so it does not clamp the wanted downlink.

---

## 8. Assumptions, corrections and open items

**Corrections to premises in the brief (stated, not quietly answered):**

1. **"FLRC (Semtech fast chirp)" — wrong.** FLRC = **GMSK + proprietary convolutional FEC +
   interleaving** (LR2021 datasheet §18.1, verbatim quoted in §4.2). This changes the
   reverse-engineering analysis entirely (§4.2).
2. **"TQP3M9037 … 0.1 MHz–6 GHz" — the vendor says 0.7–6 GHz.** Qorvo product page:
   *"0.7 - 6 GHz operational bandwidth"*. The brief's 0.1 MHz low edge is
   `TODO(unverified)` and differs by a decade; use 0.7 GHz until a datasheet confirms
   otherwise. It does not affect the 433 MHz use case.
3. **"2.4 GHz uplink allows 100 mW EIRP" (ADR-041)** vs **`radio-legal-power-limits.md`,
   which finds the 100 mW tier is *unreachable* because of the 10 mW/MHz PSD condition.**
   Both are in the repo. The PSD-limited ceiling (≤ ~14 dBm EIRP at FLRC-max BW) is the one
   this analysis uses; **flagging the disagreement** rather than picking a side is the
   repo's rule for a contradictory pair (`docs/ssot/parameters.json` doctrine).

**Assumptions (labelled):**

- `G_balloon = 0 dBi` (bare 2.4 GHz stub) — `TODO(unverified)`; a +5 dBi balloon patch
  extends the uplink range **1.78×** (model §2b).
- Duplex isolation composite: 20 dB spacing + 3 dB antenna mismatch + 45 dB BPF rejection
  = 68 dB. Each component is a *reasonable norm*, not a measured value on this hardware.
- Circulator reference: 20 dB isolation / 0.4 dB IL (2.4 GHz coaxial class) — used only in
  the conditional §3.
- The 2.4 GHz legal ceiling uses **EN 300 328 V2.2.2 · 20 dBm EIRP · 10 dBm/MHz EIRP PSD**
  as summarised in `radio-legal-power-limits.md`; the primary PDF was not re-fetched here.

**`TODO(unverified)` open items (numbered):**

1. **XR-613 identity** — no datasheet, vendor page, or AliExpress listing found; the
   analysis treats it as "a DC–5 GHz power divider/splitter". Confirms the Red Pitaya
   *cannot* test it at 433/2.4 GHz regardless of who makes it.
2. **The unmarked mixer module's specs** (LO/RF/IF range, conversion loss, drive level) —
   unknown; the Red Pitaya IF-receiver use in §4.2 depends on it.
3. **RF2126 gain-control pin** — Qorvo's product page and datasheet are 429-gated to this
   fleet and are not in the Wayback CDX; only the AliExpress module listing (title) was
   confirmed. Treat "analog bias/control pin" as unverified.
4. **nRF21540 gain/control figures** — dealer listing only; Nordic's datasheet not fetched.
5. **`Airborne 10` price discrepancy** — the page read this session shows **€4.30/m**; the
   sibling BOM (`design/ground-station-bom`) recorded **€6.50/m**. Re-check at order time.
6. **A-430S10R (€69, 13.1 dBi)** from the sibling BOM could not be re-verified (guessed URL
   404s); it is omitted from the recommended build in favour of the verified A-430S15R.
7. **AliExpress prices are "from" prices** from the German search listing; item pages are
   JS-rendered so the exact per-item price at checkout may differ.
8. **German amateur-radio power limits at 2400–2450 MHz** (the higher legal footing that
   would justify an actual PA) were not verified.
9. **Circulator isolation figures** on the cheap AliExpress parts are the class norm; the
   listings do not print them.

---

## 9. Method / reproduction

- **Fetches (browser UA, `curl --compressed`), 2026-10-08:** `funktechnik-bielefeld.de`
  (A-430S15R, SLP-17, WLAN-antenna category — Shopware `itemprop="price"`),
  `kabel-kusch.de` (Airborne 10 / Ecoflex 10 / Ecoflex 15 attenuation tables),
  `psemi.com` (PE43711), `analog.com` (HMC425A datasheet PDF),
  `skyworksinc.com` SKY66112-11 datasheet **via Wayback `id_`** (the live URL 404s),
  `qorvo.com/products/p/TQP3M9037` **via Wayback**, `redpitaya.com` (STEMlab 125-14 spec),
  `nooelec.com` (NanoVNA-H4 price), `aliexpress.com` search listings (German/EUR) and the
  Wayback **CDX** API for the gated vendor PDFs.
- **Blocked / gated this session:** Mouser and Digi-Key ("Access denied" / 403),
  Pasternack (212 B), Qorvo live (429), Skyworks live PDF paths (404), eBay (403). Wayback
  recovered the Skyworks and Qorvo pages. Every price taken from an AliExpress *search*
  listing is labelled a **"from"** price.
- **Reproduce every number:** `python3 docs/analysis/rf_shopping_list_model.py`.
  Inputs and their sources are inline constants in that file.
- **In-repo primary sources:** `docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf`
  (Tables 3-13, 3-22, 18-1, 18-2; §18.1), `docs/analysis/radio-legal-power-limits.md`,
  `docs/2G4-LINK-BUDGET-ANALYSIS.md`, `docs/adr/034-*`, `docs/adr/041-*`.

**This analysis orders nothing and buys nothing.**
