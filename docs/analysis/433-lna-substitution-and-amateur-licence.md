# 433 MHz LNA substitution and the German amateur-radio footing

> **STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** This is a `docs/analysis/`
> findings document. It **orders nothing, buys nothing and freezes no schematic**. The two
> *decisions* it reaches — (1) **substitute a 433-specific masthead LNA for the owned
> wideband TQP3M9037** and (2) **operate the station on the amateur-radio footing** — are
> carried into **ADR-085**, which is **Proposed**, and into the resolution of **ADR-079**.
> An ADR marked Proposed is **not** frozen and must not be treated as decided.

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Branch | `design/433-lna-and-licence` |
| Worktree | `/home/c03rad0r/worktrees/bf-433lna` |
| Base commit | `09e1b69` (`github/main`, "Merge PR #23 … e80-board-bind") |
| Author | Hermes Agent (subagent), for the operator |
| Lens | RF front-end part selection + German radio-regulation reading. **Not** re-deriving: the 433 link budget, the €/dB metric, the antenna/rotator menu, the level-control design or the positioner mechanics — those live on the sibling branches below. |
| Repro command | `python3 docs/analysis/433_lna_licence_model.py` — prints **every** numeric table below verbatim |
| Access date | **2026-10-08** for every URL |
| Out of scope | Procurement; the balloon-side radio; the positioner; the level-control chain (ADR-084); the 2.4 GHz reflector (ADR-083); the aviation permit for launching the balloon (sibling `analysis/free-balloon-mass-threshold`). |

**Read first (prior art — BUILT ON, not re-derived):**

- `design/amplifier-hypothesis-check` @ `148578c` → `docs/analysis/ground-station-amplifier-hypothesis-check.md`
  — the Friis/noise-temperature ledger, the **+9.7 dB T_sys** result, the **SSB Electronic LNA ISM 433**
  pricing, the array €/dB ledger and the **beam-narrowing 10–32 %** figure.
- `design/adr-set-groundstation` @ `c07bd868776a` → **ADR-079** (the CONDITIONAL amplifier-led receive chain
  with the owned TQP3M9037 — the record this document RESOLVES), ADR-080 (XR-613 resistive divider),
  ADR-072 (band-split duplex, BPF-before-LNA).
- `design/rf-shopping-list` @ `eea1cbc00702` → `docs/analysis/rf-shopping-list-and-duplex-architecture.md`
  (the shopping list this document amends).
- `design/level-control-architecture` @ `35683a5` → `docs/BASE-STATION-BOARD-CHECKLIST.md` (the checklist
  this document amends) + ADR-084.
- `design/rf-gaps-harmonics-diy` @ `3dbcdb8c0224` → ADR-083 + Part C's mast-head-vs-shack coax-loss finding.
- `docs/analysis/radio-legal-power-limits.md` + `docs/adr/041-rf-frontend-licence-exempt.md` (the
  **licence-exempt** (ISM) footing this document supersedes for this station).
- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, `docs/adr/073-433-downlink-flrc-max-lora-rejected.md`.

**Provenance discipline.** Every price, noise figure, gain and legal limit below is **CITED** (URL or
repo path + §), **COMPUTED** (formula + the script that prints it), a labelled **ESTIMATE** (basis
named), or an explicit **`TODO(unverified)`**. No part number, spec or price was invented. Where a
vendor was unreachable the block is named and the figure is left open rather than guessed.

---

## 0. Answer first

### 0.1 The four answers, one line each

| # | The question | Verdict | The number |
|---|---|---|---|
| **Q1** | Is the owned TQP3M9037 usable on the 433 receive path? | **NO — the dispute resolves AGAINST it** | Qorvo's own product page gives **Frequency Min 0.7 GHz** (three snapshots agree). The downlink is **433.92 MHz = 0.4339 GHz**, i.e. **266 MHz below** the part's LF edge. |
| **Q2** | Which 433-specific LNA? | **RECOMMEND: SSB Electronic LNA ISM 433 MHz** | **433–435 MHz, gain typ 20 dB, NF 0.7 dB, OIP3 +32 dBm, N-f, €257.00** → **+9.73 dB** of system noise temperature = **€26.41 per needed dB**. |
| **Q3** | German amateur power + airborne rules? | **No airborne restriction exists in the German instruments; bandwidth and station-class do bite** | 70 cm **750 W PEP (Kl. A) / 75 W PEP (Kl. E) / 6.1 W ERP (Kl. N)**; 13 cm **75 W PEP (A) / 5 W PEP (E)**; **max occupied bandwidth 2 MHz on 70 cm** → **FLRC-max (2.666 MHz) is NOT legal**; ceiling on the uplink moves from **~4.5 km to ~220 km (Kl. E) / ~854 km (Kl. A)**. |
| **Q4** | The 2-bay combiner? | **A commercial 430 MHz Wilkinson splitter, NOT the owned XR-613** | WiMo **"Power splitters 430 MHz, 2000W" €61.40** (N-f, 2- or 4-way). Net stack gain **+2.51 dB** after the 0.5 dB harness allowance. The owned **XR-613 is resistive (−6 dB/port) and cancels the array gain exactly** (ADR-080). |

### 0.2 The verdict

> **SUBSTITUTE.** The 433 receive path gets a **433-specific masthead LNA with a published noise
> figure**: the **SSB Electronic LNA ISM 433 MHz** (€257.00, NF 0.7 dB). The owned wideband
> **TQP3M9037 moves off the 433 path entirely** — its vendor band is **0.7–6 GHz** and it does not
> cover 433.92 MHz. **ADR-079 is SUPERSEDED by ADR-085.**
>
> The station is now on the **amateur-radio footing** (operator answer: *"amateur radio license"*).
> That removes the **10 dBm/MHz ISM PSD ceiling** and with it the **~4–5 km uplink radius** — but it
> substitutes a set of amateur obligations (callsign, station class, **2 MHz occupied bandwidth on
> 70 cm**) that the current link budget has **not** been re-run against.
>
> The **2-bay upgrade path stays open**: buy the **€61.40 commercial 430 MHz Wilkinson splitter**, keep
> the **XR-613 out of the link** (bench tool only), and expect **+2.51 dB net** for **€147.90** of
> marginal hardware.

### 0.3 The five findings that carry it

1. **The ADR-079 defect closes, and it closes against the record.** Qorvo's product page — read
   this session from **three independent snapshots** (2017-08-03, 2023-01-27, and the **live-domain
   `cn.qorvo.com` 2026-01-13** capture), all via the Wayback Machine — states
   **`Frequency Min (GHz) 0.7`, `Frequency Max (GHz) 6`**, plus the prose *"The TQP3M9037 covers the
   **0.7-4 GHz** frequency band"*, and a table `Gain 20 dB, NF 0.4 dB, OP1dB 20 dBm, OIP3 35 dBm,
   5 V / 70 mA, DFN 2×2×0.85 mm`. There is **no 0.1 MHz reading anywhere** on the vendor's page.
   The operator's module label (*0.1 MHz–6 GHz*) is contradicted by the manufacturer. **The part
   does not cover the 433 MHz downlink**, so D5's condition ("if 0.7–6 GHz is authoritative, the
   amplifier-led 433 receive chain does not stand") is met and the record must be reopened — as the
   consultant had required.

2. **A 433-specific LNA with a published NF is what "better suited for our frequency range" means,
   and it exists at three prices.** The headline recommendation is **SSB Electronic LNA ISM 433
   MHz**: **433–435 MHz, gain typ. 20 dB, noise figure 0.7 dB, OIP3 +32 dBm, IIP3 +12 dBm, 8–14 V @
   110 mA, 74×51×30 mm, ~140 g, N-female in and out, €257.00** ([wimo.com/en/ssb-70cm-ism-lna](https://www.wimo.com/en/ssb-70cm-ism-lna)).
   It carries an **output band-pass filter** and it is **receive-only, no T/R switching** — exactly
   right for the 433 receive path of the band-split duplex (ADR-072), where the ground only ever
   **receives** on 433. The Friis cascade says it buys **+9.73 dB** of system noise temperature
   (T_sys 2579.3 K → 274.5 K at the sibling study's central `T_ant` = 200 K, receiver NF 8 dB).
   It is worth **€26.41 per *needed* dB** — **not** €12.85 per dB of its own gain. That distinction
   (INV-3 of ADR-079, retained in ADR-085) is the whole reason a 20 dB gain block does not look free.

3. **The German amateur instruments contain NO airborne or balloon-specific restriction — that is a
   documented negative, not an assumption.** A full-text search of the **AFuV** (all §§ 1–19,
   Anlage 1, plus the repealed Anlage 2) and of the **AFuG** returns exactly one airborne context:
   **AFuG § 6 Nr. 3**, which empowers the ministry to make rules *"für den Betrieb von
   Amateurfunkstellen auf Wasser- und in Luftfahrzeugen"* — an **enabling** provision — and
   **AFuV § 16 Abs. 9**, which forbids *using maritime/aeronautical distress signals*. **The current
   AFuV contains no operative provision on operation aboard aircraft at all.** So the constraint on
   the balloon is **not** an airborne radio rule; it is (a) the **station class** the balloon sits in,
   (b) the **bandwidth** rule, and (c) the **territorial** rule. See §2.

4. **The bandwidth rule is the one that changes the design, and it is not the one the operator
   expected to hear.** AFuV **Anlage 1, Band Nr. 18 (430–440 MHz)** attaches **Zusatzbestimmung 7**:
   *"Maximal zulässige belegte Bandbreite einer Amateurfunk-Aussendung: **2 MHz**"*. The operator
   answered *"the maximum"* for bandwidth-per-rate, and the repo's committed FLRC-max mode is
   **2600 kbps / 2.666 MHz DSB**. **2.666 MHz > 2 MHz** → FLRC-max is **not legal on 70 cm in
   Germany**; the highest German-legal FLRC rate on the 433 downlink is **1300 kbps (1.333 MHz)**.
   The **2.4 GHz uplink** is under **note 9 (10 MHz)** and passes at every rate. *(The 2 MHz cap is
   a German/EU legal limit; the DARC band plan's "25 kHz max" channel spacing in 433.050–434.775 is
   a voluntary convention layered on top.)*

5. **The amateur footing removes the ~4–5 km uplink ceiling, and that is a large, computable
   change.** The ceiling the sibling studies kept tripping over was the **ISM PSD arm**
   `min(20 dBm, 10 dBm/MHz + 10·log10 BW)` = **14.26 dBm EIRP** at FLRC-max. Amateur operation puts a
   **Klasse E** station at **5 W PEP (+36.99 dBm)** and a **Klasse A** station at **75 W PEP
   (+48.75 dBm)** on 2400–2450 MHz. With the recommended 11.1 dBi ground antenna, the same chain
   reaches **~220 km (Kl. E)** or **~854 km (Kl. A)** at FLRC-max, and further at lower rates — an
   upper bound (0 dBi balloon RX, no fade margin), but a **~50×–190×** range change. **Consequence:
   the old "~4.5 km local service" framing is dead and the whole tier/antenna/positioner stack has to
   be re-costed against the new ceiling.**

### 0.4 The LNA ledger — one definition for every row

> **Definition** (unchanged from ADR-075/ADR-079 INV-3): money per **dB of link-budget improvement in
> the direction that needs it**. For a receive device the "dB" is its **T_sys improvement**, not its
> own gain — otherwise any gain block looks free.

| Candidate | Band | NF (dB) | Gain (dB) | Price (EUR) | T_sys (K) | T_sys benefit | **€ / needed dB** |
|---|---|---|---:|---:|---:|---:|---:|---:|
| **SSB Electronic LNA ISM 433** ← **RECOMMENDED** | 433–435 MHz | **0.7** | 20 | **257.00** | 274.5 | **+9.73 dB** | **26.41** |
| I0JXX **PRE432JXX** (BEST SPEC) | 430–435 MHz | **0.45** | >23 | 550.00 | 243.6 | +10.25 dB | 53.66 |
| Kuhne **MKU LNA 432 A** (spec best, **vendor gone**) | 432.2 ±2 MHz | 0.4 | >20 | `TODO(unverified)` | 251.8 | +10.10 dB | `TODO(unverified)` |
| Mini-Circuits **ZX60-P103LN+** (CHEAPEST WORKABLE) | 50–3000 MHz | 0.5 | 20.3 | **€109.91** (USD 119.47 @ 0.92 ESTIMATE) | 257.6 | +10.01 dB | 10.98 |
| SSB Electronic **LNA series 70 cm** | 430–440 MHz | **`TODO(unverified)`** | "high" | 226.00 | — | — | — |
| *(rejected)* owned **TQP3M9037** | **0.7–6 GHz** | 0.4 (≥0.7 GHz) | 20 | owned | — | **does not cover 433** | **n/a** |

All rows are the script's printed output (§0.3 finding 2 shows the worked example). The three
ranked slots the brief asked for:

- **BEST SPEC — I0JXX PRE432JXX**, 430–435 MHz, gain >23 dB, **NF <0.45 dB**, **€550.00**
  ([wimo.com/en/i0jxx-vhf-uhf-preamplifiers](https://www.wimo.com/en/i0jxx-vhf-uhf-preamplifiers)).
  It is a genuine mast preamp designed to sit with a sequencer in a T/R system
  (*"All preamplifiers must be used with a sequencer to ensure safe operation in combination with
  transmit/receive systems"*), so on a **receive-only** 433 path the sequencer is optional.
  **It is DOMINATED on the metric the repo uses:** the extra **0.25 dB** of NF costs
  **€293 → ~€564 per extra needed dB**. It is the right answer only if the operator wants the last
  fraction of a dB and does not care about 2× the price.
- **BEST VALUE — SSB Electronic LNA ISM 433 MHz, €257.00.** The recommendation. See §0.3 finding 2.
- **CHEAPEST WORKABLE — Mini-Circuits ZX60-P103LN+**, *"Connectorized SMA, Low Noise, Medium Power,
  Linear Amplifier, **50 MHz to 3000 MHz**"*, *"Ultra-low noise figure, **0.5 dB**"*, *"High IP3,
  +39.4 dBm"*, **USD 119.47** at 1–4 pieces (USD 95.56 at 10–24)
  ([minicircuits.com WebStore dashboard, ZX60-P103LN+](https://www.minicircuits.com/WebStore/dashboard.html?model=ZX60-P103LN%2B)).
  **It is wideband, so it repeats the TQP3M9037's problem** — it needs the 433 BPF in front of it
  (already row 2 of the checklist) and it needs a box, a feed-through and a bias tee because it is a
  bare SMA module, not a mast-head housing. Cheap per dB, more work per dB.

### 0.5 What would change the verdict (stated honestly)

- **If the operator were willing to buy a noise-figure measurement setup, no substitution would be
  needed** — the TQP3M9037 could simply be swept. The operator explicitly declined that, which is
  why substitution is the chosen resolution. (The substitution also does not depend on the sweep
  ever happening: the vendor band alone disqualifies the part.)
- **If the downlink moved to the 2.4 GHz band** (a same-band architecture), the TQP3M9037 becomes
  relevant again — it *is* designed for 0.7–4 GHz. That is an ADR-034 architecture change and is out
  of scope here.
- **If a Klasse-N-only licence is what the operator holds, the ceilings move again** — 70 cm drops to
  **6.1 W ERP** and the 2.4 GHz band is **not allocated to Klasse N at all** (Anlage 1, Bänder 22/23
  show "–" for Klasse N). That would kill the 2.4 GHz uplink outright on an amateur footing, but the
  **433 receive path and the LNA choice are unaffected** (the ground only *receives* on 433, and a
  receive-only installation needs no transmit authorisation at all).
- **If the operator is not the licence holder for the balloon's transmitter**, §3.4 applies.

---

## 1. The LNA substitution

### 1.1 Why the owned part is out — the ADR-079 D5 dispute, settled

ADR-079 D5 flagged a contradiction: the operator's module label read **0.1 MHz–6 GHz**; a sibling
branch had captured **0.7–6 GHz** from the Qorvo page. The record said plainly *"No winner is named;
the item is flagged as a defect to close from the datasheet … the decision is conditional on one
datasheet read."*

**The read is done.** Qorvo's product page, fetched this session from the Wayback Machine at three
snapshots — `20170803135122`, `20230127082808`, and `20260113155802` (the live-domain
`cn.qorvo.com` capture) — is consistent across all three:

```
Frequency Min (GHz) 0.7      Frequency Max (GHz) 6
Gain (dB) 20   NF (dB) 0.4   OP1dB (dBm) 20   OIP3 (dBm) 35
Voltage (V) 5  Current (mA) 70   Package DFN 2 x 2 x 0.85
"The TQP3M9037 covers the 0.7-4 GHz frequency band and is targeted for wireless infrastructure."
```

Bare `curl` to `qorvo.com/products/p/TQP3M9037` still returns **HTTP 429** (the block the sibling
session hit); the retrieval path used is
`https://web.archive.org/web/<timestamp>id_/https://www.qorvo.com/products/p/TQP3M9037`. A Qorvo
support-forum thread (*"TQP3M9037 Noise Data"*, 2025-04-02/03) corroborates that the *noise*
parameters are only characterised at the **5 V** datasheet bias — i.e. the datasheet band is the only
band Qorvo stands behind.

**Result: 433.92 MHz is 266.08 MHz below the vendor's LF edge.** The operator's label is a
mis-reading (or a vendor packaging change that is not reflected on the product page); it is **not
supported by the manufacturer**. Per ADR-079's own condition, the amplifier-led 433 receive chain
"does not stand" with this part.

### 1.2 The shortlist, per slot

| Slot | Part | Freq | **NF** | Gain | P1dB / linearity | Supply / bias | Connector / package | Price | Mast-mountability & bias tee |
|---|---|---|---|---|---|---:|---|
| **RECOMMENDED** | **SSB Electronic LNA ISM 433 MHz** | 433–435 MHz | **0.7 dB** | 20 dB typ | OIP3 **+32 dBm**, IIP3 **+12 dBm** | 8–14 V, ~110 mA | **N female** in/out, 74×51×30 mm, ~140 g | **€257.00** | **Ready mast-head box.** Can be powered **locally via +12 V** *or* **remotely through the coax output line with a bias tee** (or directly from a receiver that feeds LNA power at its antenna input). Output BPF built in. **RX only.** |
| BEST SPEC | I0JXX **PRE432JXX** | 430–435 MHz | **<0.45 dB** | >23 dB | — (`TODO(unverified)`) | `TODO(unverified)` | N (mast preamp) | €550.00 | Mast preamp; **needs a sequencer if T/R** (not needed on an RX-only 433 path). |
| CHEAPEST WORKABLE | Mini-Circuits **ZX60-P103LN+** | 50–3000 MHz | **0.5 dB** (headline) | 20.3 dB @500 MHz | **P1dB +22.3/+23.2 dBm**; IP3 **+39.4 dBm** | **5 V, 95 mA** | **SMA** in/out, case GC957 | USD **119.47** | A bare connectorised module, **not** a mast box: needs an enclosure, feed-throughs and a **bias tee**. Wideband → the 433 BPF must precede it. |
| priced, NF open | SSB Electronic **LNA series 70 cm** | 430–440 MHz | **`TODO(unverified)`** | "high gain" | "high IP3" | remote power via coax | N female | €226.00 | Weatherproof series (IP44 on the TV variant); the WiMo page publishes **no NF** for the 70 cm SKU — the linked datasheet is the **LNA 200 MA** which is the **144–146 MHz** member (**NF 0.5 dB, gain 22 dB, max input 20 dBm**). **Do not read the 2 m number across to 70 cm.** |
| spec best, vendor gone | Kuhne **MKU LNA 432 A** | 432.2 ±2 MHz | **0.4 dB ±0.05** | >20 dB typ | OIP3 typ **+27 dBm** | 12–14 V, 60 mA | **N male** in / **N female** out, 50×30×22 mm, ~100 g, milled alu | **`TODO(unverified)`** | Archived catalogue only. See §1.3. |

Sources: [ssb-70cm-ism-lna](https://www.wimo.com/en/ssb-70cm-ism-lna),
[i0jxx-vhf-uhf-preamplifiers](https://www.wimo.com/en/i0jxx-vhf-uhf-preamplifiers),
[ssb-electronic-lna-preamp](https://www.wimo.com/en/ssb-electronic-lna-preamp),
[ZX60-P103LN+ dashboard](https://www.minicircuits.com/WebStore/dashboard.html?model=ZX60-P103LN%2B),
`web.archive.org/…/kuhne_english_preamp.pdf` (see §1.3).

### 1.3 Kuhne Electronic — a named block, not a guess

Kuhne Electronic's two historical domains are **gone**: `www.ku-electronic.de` now serves a
web.de parking frameset (`<frame src="https://homepage-verwaltung.web.de/maildomainhostingfrontend/homepage-parken">`),
`kuhne-electronic.de` does not resolve, and `shop.ku-electronic.de` fails TLS. Every product path
returns 404 and the Wayback CDX API holds only a single 302 for the modern domain. Their 2007
**archived** preamp catalogue *does* survive and yields the real part and real specs:

> **MKU LNA 432 A** — centre frequency **432.2 MHz ±2**, **noise figure 0.4 dB ±0.05 @18 °C**,
> gain **typ. 20 dB**, input RL typ 5 dB, output RL min 15 dB, **OIP3 typ +27 dBm**, +12…14 V DC,
> typ. 60 mA, **N-male in / N-female out**, milled aluminium 50×30×22 mm, ~100 g; *"Helical filter
> (432 MHz) for good selectivity"*, *"The preamplifiers do not contain built-in coaxial relays!"*
> (`web.archive.org/web/20071023012640id_/http://www.kuhne-electronic.de/english/downloadcatalog/kuhne_english_preamp.pdf`, p. 5–6)

It is **the best published NF of any part in this survey (0.4 dB)** — but a **2007** catalogue, a
**dead vendor**, and **no current price**. It is therefore listed as a spec datum, **not** as a
purchasable option: **`TODO(unverified)` availability and price.** If the operator wants the last
0.3 dB and can find remaining stock, this is the part; nothing in the current market reached under
0.45 dB with a live vendor.

### 1.4 What "what should I look for" actually means, as a checklist

The operator asked *"what should I look for?"* — so state it as a buy-filter, with the reason each
line exists:

1. **A published noise figure at the band you use**, with a stated temperature. **NF ≤ 1.0 dB**;
   **≤ 0.7 dB** is what the market offers at a sane price. A number quoted only "typical @25 °C, 2 GHz"
   on a wideband part says nothing about 433.
2. **The band must \*contain\* 433.05–434.79 MHz**, not merely be near it. Verify the LF edge, not the
   headline. (This is exactly the failure mode that killed the TQP3M9037.)
3. **Gain ~20 dB** — enough to suppress the downstream receiver's noise, not a spec to maximise
   (per ADR-079 INV-3, an LNA is worth its NF delta, not its gain).
4. **Linear enough for the site:** OIP3 ≥ +30 dBm, IIP3 ≥ +10 dBm. A mast-head LNA with 433-only
   selectivity and good IP3 survives nearby cell/LTE-Band-8 transmissions; the SSB part's
   **+32 dBm OIP3** is quoted to that end.
5. **N connectors and a weatherproof housing** — mast-head means mast-head; a bare SMA module in a
   ziplock is not mast-head.
6. **How it is powered:** local +12 V **or** remote via the coax with a bias tee. Remote power is
   what makes a mast-head LNA practical, because it removes a DC run up the mast.
7. **RX-only is fine and cheaper.** The 433 path never transmits (band-split duplex, ADR-072), so
   pay nothing for a T/R relay or a VOX; a part *with* T/R costs more and adds a failure mode.

### 1.5 Assembly: JLCPCB is not needed for this purchase

The operator asked where JLCPCB pre-soldered assembly is/isn't needed. **For the LNA: not needed.**

- The **SSB Electronic LNA ISM 433 MHz** is a **finished, connectorised mast-head box** (N-female in
  and out, 74×51×30 mm, 8–14 V @ 110 mA). There is **no board to design, no parts to place and no
  assembly service to buy** — it hangs on the mast with two N connectors and a DC feed (or a bias tee).
- The **ZX60-P103LN+** is also connectorised (SMA), but needs **an enclosure, feed-throughs and a
  bias tee** — still **hand-solder/hand-wire**, not JLCPCB.
- JLCPCB assembly *is* the right answer for a **later, integrated** front end: the level-control
  chain of ADR-084 (ADL5240 VGA, PE43711 DSA, AD8318 detector, the MCU) is an SMD board and is the
  natural JLCPCB pre-soldered candidate. **Do not put the LNA on it** unless the operator wants to
  build an RF board with a shield can — the whole point of the €257 part is that it is already a
  weatherproof mast box.
- **Which choices keep the 2-bay upgrade open:** the recommended part has **N-female in/out**, which
  is the same interface class as the commercial 430 MHz Wilkinson splitter (§3), so a second bay
  bolts on without an adapter chain. A **SMA** LNA (the ZX60) forces an SMA↔N chain into every future
  reconfiguration.

---

## 2. The German amateur rules that now govern this station

**Method.** Two primary instruments were read in full this session: the **Amateurfunkverordnung
(AFuV)** — fetched as `AFuV.pdf` (24 pp.) from `gesetze-im-internet.de`, which carries **§§ 1–19,
Anlage 1 and the repealed Anlage 2**, with the fundstelle **BGBl. 2024 I Nr. 175, S. 1–4** — and the
**Amateurfunkgesetz (AFuG 1997)** paragraphs. Both were full-text searched for
`Luftfahrzeug|Ballon|Flug|Schiff|mobil|Fahrzeug`. The **DARC band plans** (VHF/UHF referat, 70 cm
stand **Mai 2025**, 13 cm stand **Juni 2015**) were read as the band-plan layer (voluntary, on top of
the law). Anything that could not be read from a citable source is marked `UNVERIFIED` with the scope
of the search that produced the gap.

### 2.1 Power limits (AFuV Anlage 1, tabellarische Übersicht)

| Band (Lfd. Nr.) | Status | Klasse A | Klasse E | Klasse N | Zusatzbestimmungen |
|---|---|---|---|---|---|
| **430–440 MHz** (18) | **P** | **750 W PEP** | **75 W PEP** | **6.1 W ERP** | **7** (max occupied BW **2 MHz**; AM-TV 7 MHz), **13** |
| 2320–2400 MHz (22) | S | 75 W PEP | 5 W PEP | – | 9 (BW 10 MHz; TV 20 MHz), 17 |
| **2400–2450 MHz** (23) | **S** | **75 W PEP** | **5 W PEP** | **–** | **9** (max occupied BW **10 MHz**), 13, 17 |

`P` = the amateur service is the **primary** service; `S` = **secondary** (may claim no protection
from, and must not cause interference to, primary users). Footnotes: `PEP` = Spitzenleistung (§ 2
Nr. 7); `ERP` = effektive Strahlungsleistung (§ 2 Nr. 8).

**Claims keyed to the operator's actual bands:**

- The **433.05–434.79 MHz** ISM band the operator uses sits **inside 430–440 MHz** — the **primary**
  German amateur allocation, `Klasse A 750 W PEP / Klasse E 75 W PEP`. (Band-plan layer: the DARC
  70 cm plan marks **433.000–435.000 MHz "alle Sendearten"**, so 433.92 MHz is band-plan-clean.)
- **13 cm is 2320–2450 MHz, not 2300–2450 MHz.** The DARC 13 cm band plan is titled
  **"Bandplan 13cm, 2320 - 2450 MHz"** and gives **2400.000–2450.000 MHz** as *"Satelliten"*
  territory. **2300–2320 MHz is not an amateur allocation in Germany**; a plan written as
  "2300–2450" overshoots by 20 MHz at the bottom.
- **2.4 GHz is SECONDARY** (`S`) **and not available to Klasse N at all.** The uplink is therefore
  the *regulated* direction on the amateur footing — the exact inverse of the ISM footing, where the
  uplink was the *capped* direction and the balloon's 433 TX was the capped one.

### 2.2 The specific sub-bands that apply, and the bandwidth that bites

| Segment | Applies to | Binding limit | Source |
|---|---|---|---|
| 433.05–434.79 MHz | the 433 downlink | 430–440 MHz row: **Kl. A 750 W PEP / Kl. E 75 W PEP**; **max occupied BW 2 MHz** | AFuV Anlage 1, Lfd. Nr. 18 + note 7 |
| 435–438 MHz | (not used) | also amateur-satellite, secondary | AFuV Anlage 1 note 13 |
| 2400–2450 MHz | the 2.4 GHz uplink | **Kl. A 75 W PEP / Kl. E 5 W PEP**; **max occupied BW 10 MHz**; secondary | AFuV Anlage 1, Lfd. Nr. 23 + note 9 |

**The 2 MHz figure is the finding the operator needs most.** AFuV **Anlage 1, Zusatzbestimmung 7**:
*"Maximal zulässige belegte Bandbreite einer Amateurfunk-Aussendung: 2 MHz; bei amplitudenmodulierten
Fernsehaussendungen: 7 MHz."* Against the repo's FLRC ladder (DSB bandwidths from the LR2021
datasheet table used by `ground-station-flrc-max-throughput.md`):

| FLRC mode | BW DSB | Legal on 70 cm (≤ 2 MHz)? |
|---|---:|---|
| **2600 kbps** (FLRC-max, the committed mode) | **2.666 MHz** | **NO** |
| 2080 kbps | 2.222 MHz | **NO** |
| **1300 kbps** | 1.333 MHz | **YES** ← highest legal rate |
| 1040 kbps | 1.333 MHz | YES |
| 650 kbps | 0.740 MHz | YES |
| 520 kbps | 0.571 MHz | YES |

So the operator's answer *"bandwidth per rate = the maximum"* is **not available on the 433
downlink under the German amateur rules**: the maximum is **1.333 MHz → FLRC 1300 kbps**. On the
**2.4 GHz uplink** the 10 MHz note leaves every FLRC rate legal. This is a **rate/airtime
consequence**, not merely a paperwork one, and it must be re-run through the link budget.

### 2.3 Airborne / balloon-specific restrictions — what exists and what does not

**Read the negative carefully, because it is the answer to the brief's "crucial" item.**

- **No airborne or balloon-specific restriction exists in the AFuV.** A full-text search of the
  AFuV PDF (all §§ 1–19 + Anlage 1 + the repealed Anlage 2, 794 extracted lines) for
  `Luftfahrzeug|Ballon|Flug|flieg|beweglich|ortsver|mobil|Fahrzeug|Schiff` returns **two hits, both
  irrelevant to airborne amateur operation**: the § 16 Abs. 9 prohibition on *using* maritime and
  aeronautical distress signals, and nothing else. **There is no provision restricting amateur
  operation from an aircraft or a balloon.**
- **The AFuG contemplates it and delegates it.** **AFuG § 6 Nr. 3** empowers the ministry to make
  technical/operational rules for the amateur service, *"insbesondere für … den Betrieb von
  Amateurfunkstellen auf Wasser- und in Luftfahrzeugen"*. So flight operation is an expressly
  contemplated subject — **and the operative ordinance does not currently contain one.** (Scope of
  the negative: the AFuV as consolidated to BGBl. 2024 I Nr. 175, plus AFuG §§ 1–13; **not**
  read: the BNetzA `Frequenzplan`'s per-band *Nutzungsbestimmungen*, whose portal is 404 to this
  fleet — so a country-specific airborne note **outside** the AFuV **cannot be positively
  excluded**, and is marked `UNVERIFIED`.)
- **The comparison case shows this is a real legislative choice, not an oversight.**
  **47 CFR § 97.11** (US) is an explicit airborne rule — *"(a) The installation and operation of an
  amateur station on a ship or aircraft must be approved by the master of the ship or pilot in
  command of the aircraft"*, *"(c) … shall not be operated while the aircraft is operating under
  Instrument Flight Rules"*. **Germany has no equivalent.** The honest statement is: *"no
  airborne-specific restriction was found in the German instruments; the scope of the search is
  named; the unread document is named."*

**So what DOES constrain the balloon?** Three things, and none of them is "balloons are banned":

1. **Station class — § 13 AFuV + Anlage 1 Abs. 1.** A drifting balloon is an **automatically
   operating amateur station** (§ 13 Abs. 1/2) and needs its own assigned callsign; **Anlage 1
   Abs. 1** caps *"fernbediente oder automatisch arbeitende **terrestrische** Amateurfunkstellen"*
   above 30 MHz at **50 W ERP** (*"ausgenommen Remote-Betrieb"*), and the BNetzA may order a further
   reduction on interference. A balloon is not obviously "terrestrisch", so **which cap applies to an
   airborne automatic station is `UNVERIFIED`** — and it must be put to the BNetzA in writing
   before the station is built to a power target. Note the enabling route that exists:
   **§ 16 Abs. 2 AFuV** lets the BNetzA grant **temporary exceptions for experimental and
   technical-scientific studies**, possibly with an extra callsign — the natural instrument for a
   balloon experiment.
2. **One callsign, one location — § 11 Abs. 6 AFuV.** *"Mit einem Rufzeichen darf nicht zeitgleich
   von verschiedenen Standorten aus am Amateurfunkdienst teilgenommen werden. Ausnahmen sind
   zulässig, bedürfen jedoch der vorherigen Zustimmung durch die Bundesnetzagentur."* A balloon
   drifting 300 km away while the shack is on the air is **two locations on one callsign** →
   **BNetzA prior consent required.** § 11 Abs. 1 also fixes the identification duty: a
   Germany-valid callsign, **sent at the start and end of every contact and at least every 10
   minutes during traffic**.
3. **Territory — § 11 Abs. 1 AFuV + the ITU territorial principle.** *"Im Geltungsbereich dieser
   Verordnung darf eine Amateurfunkstelle nur unter Verwendung einer in Deutschland gültigen
   Amateurfunk-Rufzeichenzuteilung genutzt oder betrieben werden."* A German callsign authorises
   operation **inside** that scope. **A free balloon crosses borders**, so once it is over a foreign
   state it is transmitting from foreign territory without that state's authorisation. **That is a
   real constraint here** and it is a design input: either accept a flight path that stays in
   German airspace, or obtain per-country authorisation, or **gate the transmitter on a GNSS
   border test**. (The German aviation-law side of the same drift — SERA Anlage 2 Nr. 2.1 requires
   the launch state's permission and exempts only *meteorological* light balloons from the
   **overflown** state's permission — is already documented in sibling
   `analysis/free-balloon-mass-threshold`; it is **a different gate** from the radio one.)

**Also flagged, because it is the sharpest legal risk to the *architecture* and nobody has
addressed it:** **AFuG § 5 Abs. 4 and Abs. 5.**

> § 5(4): *"Eine Amateurfunkstelle darf 1. nicht zu gewerblich-wirtschaftlichen Zwecken und 2. nicht
> zum Zwecke des geschäftsmäßigen Erbringens von Telekommunikationsdiensten betrieben werden."*
> § 5(5): *"Der Funkamateur darf nur mit anderen Amateurfunkstellen Funkverkehr abwickeln. Der
> Funkamateur darf Nachrichten, die nicht den Amateurfunkdienst betreffen, für und an Dritte nicht
> übermitteln. Satz 2 gilt nicht in Not- und Katastrophenfällen."*

The station in this repo is described as an **"internet gateway" / "bent pipe"** that **carries
third-party user traffic to the internet**. Under § 5(5) a licensee may conduct traffic **only with
other amateur stations** and **may not pass messages for third parties** that do not concern the
amateur service; under § 5(4) the station may not serve commercial-economic purposes or be used to
commercially provide telecommunication services. It also runs against the **AFuG § 2 Nr. 1**
definition of `Funkamateur` (*"aus persönlicher Neigung und nicht aus gewerblich-wirtschaftlichem
Interesse"*). **On the amateur footing the gateway's service function is the problem, not its
hardware.** Whether a hobby, non-commercial gateway is defensible is a **legal** question, not an
engineering one: **`UNVERIFIED — ask the BNetzA / a lawyer`**. The engineering consequence is stated
here only so it is not discovered after the build: **the amateur footing buys uplink power at the
cost of the service model.** If the gateway must carry third-party traffic commercially, the amateur
footing is the wrong footing and the licence-exempt (or a fixed-link) footing is the right one —
which re-instates the PSD cap and the ~4–5 km radius.

### 2.4 What the operator must DO to comply (the actionable list)

1. **Hold a valid German amateur licence** of a class that includes the bands used. (Klasse A covers
   everything here. Klasse E covers 70 cm at 75 W PEP and 2.4 GHz at 5 W PEP. **Klasse N does not
   cover 2400–2450 MHz at all**, and caps 70 cm at 6.1 W ERP.) Verify the class on the operator's
   own `Amateurfunkzeugnis`; the bands per class are the Anlage-1 table above.
2. **Use only a BNetzA-assigned callsign** (AFuG § 5 Abs. 1) and identify per AFuV § 11 Abs. 1
   (start, end, and at least every 10 minutes).
3. **Separate callsign for the balloon station, and BNetzA consent for simultaneous multi-location
   use** (AFuV § 11 Abs. 6 / § 13 / § 10 Abs. 2 — the agency assigns additional callsigns for
   automatically operating stations).
4. **Put the balloon station's class and power to the BNetzA in writing** before building to a power
   target — the terrestrial/airborne reading of Anlage 1 Abs. 1 (50 W ERP) is `UNVERIFIED` and the
   route to a clean answer is **§ 16 Abs. 2 AFuV** (temporary exception for experimental studies).
   *(For reference, the intended 433 TX is 10 mW class — far below any of these caps — so the power
   question is not the binding one; the **station class** and the **callsign/location** items are.)*
5. **Cap the 433 downlink at 2 MHz occupied bandwidth** → FLRC **1300 kbps** maximum (§ 2.2).
6. **Notify the aviation authority** — a separate gate (LuftVO § 20 Abs. 1 Nr. 6; SERA Anlage 2);
   see the sibling free-balloon study. Do not conflate it with the radio licence.
7. **Site the antenna and keep the log** so that BNetzA can co-operate on interference
   investigations (AFuV § 16 Abs. 5, § 17): be ready to produce technical documents and an antenna
   siting sketch on request, and note the agency's power to order frequency blocks or power
   reduction (§ 17 Abs. 2).
8. **Keep telemetry un-encrypted in content** — AFuV § 16 Abs. 8 forbids encoding/encryption to
   conceal content, but **expressly exempts control signals** *"von anderen fernbedienten oder
   automatisch arbeitenden Stationen"*, which is what a balloon telemetry link is. So no
   content-encryption is needed and none is permitted for content; the control-signal exemption
   covers the link.

### 2.5 The consequence for the link budget, and the one number that changed most

The sibling studies kept colliding with the **ISM PSD arm**: on the licence-exempt footing the
ground uplink ceiling is `min(20 dBm, 10 dBm/MHz + 10·log10 BW)` = **14.26 dBm EIRP** at FLRC-max,
which is what produced the **~4–5 km** gateway radius. **On the amateur footing that cap does not
exist**: 2400–2450 MHz gives **Klasse E 5 W PEP** and **Klasse A 75 W PEP**. FLRC is
**constant-envelope** (GMSK + FEC), so PEP ≈ average, and the two are directly comparable. With the
recommended 11.1 dBi ground antenna and a ~0 dBi balloon RX:

| FLRC mode | sens | req. EIRP @1 km | **d_max, Klasse E (5 W PEP)** | **d_max, Klasse A (75 W PEP)** |
|---|---:|---:|---:|---:|
| 2600 kbps | −99.0 dBm | +1.2 dBm | **220 km** | **854 km** |
| 1300 kbps | −101.5 dBm | −1.3 dBm | **294 km** | **1139 km** |
| 650 kbps | −104.0 dBm | −3.8 dBm | **392 km** | **1518 km** |

*(Upper bound: `G_balloon = 0 dBi`, no fade margin, no implementation loss. And note that on 70 cm
the downlink may no longer use 2600 kbps — § 2.2.)*

**The single sentence to carry forward:** *the ~4.5 km uplink ceiling was an ISM PSD artefact and is
gone; the amateur ceiling is set by licence class, not by spectrum density. Every tier price, antenna
choice and positioner class that was justified by "~4.5 km" must be re-costed against the new
ceiling.* This is the same conclusion the plan review reached in
`references/freeze-the-legal-basis-before-quoting-magnitudes.md` — the legal basis was the blocking
dependency, and it has now moved rather than closed.

---

## 3. The 2-bay combiner (keeping the Yagi upgrade path open)

### 3.1 Why the owned XR-613 cannot do this

The operator owns an **XR-613 resistive power divider (DC–5 GHz)**. A resistive divider is **−6 dB
per port** and, used as a combiner, **cancels the +3.01 dB coherent array gain exactly** — net
0 dB. This is already recorded as **ADR-080**; it is restated here because it is the reason a
**Wilkinson** (a reactive/hybrid combiner, not a resistive one) is the required part.

### 3.2 The two routes

**(a) DIY λ/4 coax Wilkinson.** At 433.92 MHz:

- **λ₀ = 300 / 433.92 = 0.6914 m → λ/4 (free space) = 17.28 cm.**
- Two **λ/4 sections of Z = √2 × 50 = 70.7 Ω**; the isolation resistor across the two outputs is
  **2 × 50 = 100 Ω**.

| Coax | VF | λ/4 physical |
|---|---:|---:|
| RG-213 / URM-67 | 0.66 | **11.41 cm** |
| RG-58 | 0.66 | 11.41 cm |
| Airborne 10 / LMR-400 | 0.85 | 14.69 cm |
| Ecoflex 10 | 0.84 | 14.52 cm |
| RG-11 (75 Ω) | 0.66 | 11.41 cm |

*Materials & cost:* two **N or PL tee/adapters**, two 11.4 cm RG-58/RG-213 stubs, one **100 Ω
non-inductive resistor** (or two 200 Ω in parallel), and a small die-cast box. Using **RG-11 (75 Ω)**
for the λ/4 sections is the usual shortcut — **6 % off 70.7 Ω**, worth a fraction of a dB of
return loss. **Cost: ~€10–20 in parts** (N tees and adapters dominate), all hand-solderable; **no
JLCPCB assembly**. Expected insertion loss ≈ **0.2–0.3 dB**, i.e. it does **not** eat the +3.01 dB —
that is the whole point versus the XR-613.

**(b) Commercial 430 MHz Wilkinson-class splitter** — the recommended route, because it is
characterised, weatherproof and cheaper than the labour:

| Part | Spec as printed | Price (incl. VAT / net) | URL |
|---|---|---:|---|
| **WiMo "Power splitters 430 MHz, 2000W"** ← **RECOMMENDED** | for **2 or 4 antennas**, **N connectors (female)**, 2000 W, "In stock, shipped in 1 to 2 days" | **€61.40 / €51.60** | [wimo.com/en/antenna-splitter-430mhz](https://www.wimo.com/en/antenna-splitter-430mhz) |
| YU1CF power splitter/divider **70 cm**, **1/2 or 1/4 λ** | 2 to 8 outputs | €103.00 / €86.55 | [WiMo power splitter, phasing harnesses](https://www.wimo.com/en/accessories/antenna-accessories/power-splitter-phasing-harnesses) |
| 70 cm **phase line** for X-Quad (with connectors) | phase harness for circular polarisation / crossed Yagi | €63.00 / €52.94 | same page |
| *(not a combiner)* owned **XR-613** resistive divider | DC–5 GHz, **~ −6 dB/port, no gain** | owned | ADR-080 |

**Note on the WiMo page text:** the 430 MHz product's *description line* reads "Power splitters
**144 MHz**, for 2 or 4 antennas, N connectors (female)" — a copy-paste on the vendor's page. The
**product name, the SKU `pm_wimo_splitter_70cm`, the URL `/en/antenna-splitter-430mhz` and the
schema.org offer all say 430 MHz**; treat the body text as a vendor typo. *(Flagged so a future
reader does not think the wrong part was bought.)*

### 3.3 What the 2-bay actually buys, and what it costs

- **Gain: +10·log10(2) = +3.01 dB** coherent (§0.4 of the sibling hypothesis study: coherent
  combining gives `10·log₁₀N`; **incoherent** combining gives **+0.00 dB** — the operator's
  "one tracker per Yagi, combined" idea adds *coverage*, not gain).
- **Harness / phasing loss: −0.5 dB** — an **ESTIMATE** in this document, not a vendor figure
  (the sibling ledger carries a **€12 jumper-harness allowance** but no loss figure): ~0.2–0.3 dB
  Wilkinson insertion loss + ~0.2–0.3 dB of jumpers and connectors. **Net stack gain ≈ +2.51 dB.**
  Verify by measurement once built (the LiteVNA 62 on the checklist, row 13).
- **Beamwidth cost: a 2-bay narrows the stacked-plane beam by 10 % (14 dBi element) to 32 % (3-el
  element)** — [CITED `design/amplifier-hypothesis-check` @ `148578c`,
  `docs/analysis/ground-station-amplifier-hypothesis-check.md` §0.1 Q2 row].
- **Cost: second bay + combiner + harness jumpers = €74.50 (Diamond A-430S15R) + €61.40 (splitter) +
  €12.00 (jumper allowance) = €147.90** for **+2.51 dB** = **€58.92 per dB**. (The sibling priced the
  same move at **€228.40 / +3.0 dB = €76.13 per dB** using the €155 Sirio WY 400-10N as the second
  bay. The difference is the second antenna chosen, not the combiner.)
- **Mechanical consequence to carry:** a second bay doubles the wind area on the same positioner and
  the same mast, and the narrower beam tightens the pointing/tracker requirement (ADR-076/077/078).

### 3.4 Which choices keep the upgrade path open

The operator asked to be able to add a second Yagi **and more amplification later**. Three concrete
choices preserve that:

1. **Buy the LNA with N-female in/out** (the SSB part does; the ZX60 does not) — the same interface
   as the 430 MHz splitter, so no adapter chain.
2. **Buy a 2-or-4-way splitter, not a fixed 2-way** — the WiMo 430 MHz part is sold for **2 or 4
   antennas** in one SKU, so the 4-bay step needs no new combiner.
3. **Buy the LNA as a separate mast-head box rather than putting it on the level-control board** —
   a second bay then needs only the splitter and a jumper, not a board respin.

---

## 4. Assumptions, corrections and open items

**Corrections to premises offered in the brief (stated plainly, per the repo's rule):**

1. **"the 433 mast-head LNA is the ONE ground amplifier worth buying (+9.7 dB T_sys …)"** — confirmed
   and reproduced (**+9.73 dB**). The number stands; the *part* does not. The sibling priced the
   **SSB Electronic LNA ISM 433**; this document confirms it and **adds the reason the owned
   alternative is not merely "disputed" but excluded** (0.7 GHz LF edge).
2. **"the ISM PSD ceiling (10 dBm/MHz) does NOT apply to this station"** — correct on the amateur
   footing, **but the amateur instruments bring their own ceilings**, and one of them (the **2 MHz
   occupied-bandwidth cap on 70 cm**) is *tighter in the way that matters* than the PSD cap ever was
   on the downlink. The brief's framing ("the PSD cap removal is unambiguously good news") is
   **half right**.
3. **"the ~4–5 km uplink ceiling that was threatening the bent-pipe gateway"** — the ceiling is
   indeed removed (§ 2.5), but the bent-pipe **service model** is the thing AFuG § 5(4)/(5) puts at
   risk. Removing one constraint surfaced a different one.

**Assumptions (with basis):**

| Assumption | Value | Basis |
|---|---|---|
| `T_ant` (wide-beam ground antenna, 433) | 200 K | sibling §1.2 bracket 150–290 K — **ESTIMATE** |
| receiver noise figure (LR2021) | 8 dB | sibling bracket 6/8/10 dB — **`TODO(unverified)`** |
| feedline loss before/after LNA | 1.14 dB coax + 0.5 dB connectors = 1.64 dB | `ground-station-bom-candidates.md` §F3/§6 — **CITED** |
| USD→EUR | 0.92 | sibling §9 — **ESTIMATE** |
| harness/phasing loss, 2-bay | 0.5 dB | physical estimate, § 3.3 — **ESTIMATE** |
| balloon RX antenna gain | ~0 dBi | repo convention — **ESTIMATE** |
| FLRC is constant-envelope → PEP ≈ average | assumed | GMSK+FEC (LR2021 §18.1, sibling rf-duplexer reference) |

**Open items (`TODO(unverified)`) — gathered in one place:**

1. **Kuhne MKU LNA 432 A availability and price** — vendor domains parked; 2007 archived catalogue
   only. Best published NF in the survey (0.4 dB) and **not purchasable as verified**.
2. **SSB Electronic LNA series 70 cm NF** — the WiMo page publishes none; the linked datasheet is
   the 2 m `LNA 200 MA` (NF 0.5 dB). **Do not read across.**
3. **I0JXX PRE432JXX** supply voltage, current, P1dB, and whether the 430–435 MHz lower edge covers
   433.92 with margin.
4. **The BNetzA `Frequenzplan` per-band *Nutzungsbestimmungen*** — portal 404 to this fleet; a
   country-specific airborne note outside the AFuV **cannot be positively excluded**.
5. **Which cap applies to an airborne *automatic* amateur station** (Anlage 1 Abs. 1 says
   "terrestrische … 50 W ERP"). **Route: written enquiry to the BNetzA, or § 16 Abs. 2 AFuV.**
6. **AFuG § 5(4)/(5) applicability to the gateway service model** — `UNVERIFIED — ask the BNetzA / a
   lawyer`.
7. **The 2.4 GHz BPF rejection and the DSA range at the amateur power levels** — inherited from
   ADR-072/ADR-084.
8. **The exact −3 dB beamwidths of the 10/15-el Yagis** (inherited; the vendors publish gain and band
   only).
9. **Local man-made noise floor at the chosen site** (inherited; if man-made noise dominates, neither
   antenna gain nor an LNA buys dB).

---

## 5. Recommendation

1. **Buy the SSB Electronic LNA ISM 433 MHz (€257.00)** as the 433 mast-head LNA. **Mount it at the
   mast-head**, ahead of the feedline (ADR-079 INV-1, retained as INV-1 in ADR-085), and keep the
   **433 BPF in front of it** (ADR-072 INV-3, retained as INV-2).
2. **Retire the TQP3M9037 from the 433 receive path.** Its vendor band is **0.7–6 GHz**; it cannot
   serve 433.92 MHz. Keep it as a **2.4 GHz-band spare** (where it is in-band) or as a bench item —
   but **not** as the 433 chain's LNA. **ADR-079 → SUPERSEDED by ADR-085.**
3. **Add the WiMo 430 MHz power splitter (€61.40)** to the 2-bay upgrade kit, and record that the
   **XR-613 stays a bench tool** (ADR-080 unchanged).
4. **Re-run the link budget on the amateur footing before any hardware is bought**, against
   **Klasse E / Klasse A** ceilings and the **FLRC 1300 kbps (2 MHz)** downlink cap. The
   "~4.5 km local service" tier model is retired.
5. **Put two questions to the BNetzA in writing** (§ 2.4 items 4 and 6): the station class of an
   airborne automatically-operating amateur station, and the AFuG § 5(4)/(5) position on a
   non-commercial gateway. Both are cheap to ask and both are `UNVERIFIED` here.

*Explicitly NOT done by this document:* no part ordered; no schematic or board changed; no figure
fabricated; no ADR marked Accepted except through **ADR-085 (Proposed)** and the **Superseded** status
written onto ADR-079; `AGENTS.md` and `.hermes/AGENTS.md` untouched.
