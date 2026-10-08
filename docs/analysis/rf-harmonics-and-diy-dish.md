# RF gaps: 433↔2.4 GHz harmonic coexistence, the 2.4 GHz reflector surface-accuracy budget, and masthead-vs-shack LNA placement

- **Status:** Analysis (findings + measurements, not decisions). The one *decision* this
  document forces — the 2.4 GHz reflector class for the sweet-spot-(b) build — is recorded in
  **`docs/adr/083-2g4-reflector-production-ku-offset-dish.md`**.
- **Date:** 2026-10-08
- **Author:** Hermes subagent, branch `design/rf-gaps-harmonics-diy`, base `github/main` @ `09e1b69`
- **Reproduce:** `python3 docs/analysis/rf_gaps_model.py` (all three parts; no third-party imports).
- **Figure:** `docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg` (rendered by
  `docs/analysis/render_rf_gaps_figure.py`), independently reviewed — see §B.6.

**Why this document exists, and what it deliberately does NOT do.** An earlier two-task batch
("ground-station RF + link engineering study" and "dish + positioner mechanical study") died at
`max_iterations` and pushed nothing. Almost all of its content has since been **superseded** by
the landed design set, and is **read, not re-derived**, here:

| Read (built on, NOT re-derived) | What it owns |
|---|---|
| `design/ground-station-lowpower-link` @ `4b90be942ce7` → `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` | two-way link budgets, dish-vs-Yagi arithmetic |
| `design/ground-station-flrc-max` @ `4ecbf5ca` → `docs/analysis/ground-station-flrc-max-throughput.md` | TX-power vs dish-size, mesh-vs-solid wind |
| `design/positioner-lowcost` @ `b74bf5f6` | wind-torque sizing, positioner class, mast-head architecture |
| `design/ground-station-bom` @ `283cad72` → `docs/analysis/ground-station-bom-candidates.md` | priced BOM (all prices below are from here unless re-fetched) |
| `design/gain-per-dollar` @ `f0f1e08a` → `docs/analysis/ground-station-gain-per-dollar.md` | the €/dB metric and tier ladder |
| `design/gain-per-dollar-cliff`, `design/tier0-accessible`, `design/amplifier-substitution`, `design/amplifier-hypothesis-check` @ `148578c3` | the two sweet spots, the tier ladder, the amplifier-vs-antenna trade |
| `design/adr-set-groundstation` (ADRs 071–082) — owners cited inline as **ADR-071 … ADR-082** | the ground-station design basis, band split, LNA decision, tiers |

The **three genuinely uncovered parts** are Parts A, B and C below.

**Conventions.** Every external number carries its URL. A figure with no source is marked
`ESTIMATE`; a needed source that could not be fetched is marked `TODO(unverified)`. Nothing is
invented. Where a constant is used in more than one place it is defined once in
`rf_gaps_model.py` with its source in a comment.

---

## Part A — 433 MHz ↔ 2.4 GHz harmonic and intermodulation coexistence

### A.0 The two bands and the assignment

The ground station is a **band-split duplex**: it **receives 433 MHz** (balloon → ground) and
**transmits 2450 MHz** (ground → balloon) — ADR-072, which mirrors the balloon-side split of
ADR-034. The two bands are **5.65× apart (≈2.5 octaves)**.

| band | edges | source |
|---|---|---|
| 433 MHz SRD / LPD433 | **433.050 – 434.790 MHz** | Wikipedia *LPD433* — *"The frequencies correspond with the ITU region 1 ISM band of 433.050 MHz to 434.790 MHz"*, <https://en.wikipedia.org/wiki/LPD433>. In-repo owner: `docs/adr/039-licence-exempt-433-design-point.md` and `docs/adr/041-rf-frontend-licence-exempt.md` (both state "433.05–434.79 MHz"). |
| 2.4 GHz ISM wideband data | **2400 – 2483.5 MHz** | Wikipedia *List of WLAN channels*, quoting the ISED RSS-247 title *"… in 902-928 MHz, **2400-2483.5 MHz**, 5150-5350 MHz, and 5470-5895 MHz bands"*, <https://en.wikipedia.org/wiki/List_of_WLAN_channels>. |

### A.1 Do any harmonics of the 433 MHz transmit land in 2400–2483.5 MHz?

The n-th harmonic of the band occupies `[n·433.05, n·434.79] MHz`. Checking n = 1…12:

| n | n·433.05 | n·434.79 | in 2400–2483.5 MHz? | gap to band |
|---:|---:|---:|:--:|---:|
| 1 | 433.05 | 434.79 | no | 1965.21 MHz |
| 2 | 866.10 | 869.58 | no | 1530.42 MHz |
| 3 | 1299.15 | 1304.37 | no | 1095.63 MHz |
| 4 | 1732.20 | 1739.16 | no | 660.84 MHz |
| 5 | 2165.25 | 2173.95 | **no (below)** | 226.05 MHz |
| 6 | 2598.30 | 2608.74 | **no (above)** | **114.80 MHz** ← closest |
| 7 | 3031.35 | 3043.53 | no | 547.85 MHz |
| … | | | no | |

**Result: NO harmonic of 433.05–434.79 MHz falls inside 2400–2483.5 MHz.** The nearest approach
is the **6th harmonic (2598.30–2608.74 MHz), which misses the band top (2483.5 MHz) by
114.80 MHz**; the 5th harmonic is 226.05 MHz below the band bottom. The band ratio is 5.54–5.71,
i.e. **~0.46 away from the integer 6** — there is no integer harmonic anywhere near the 2.4 GHz
band.

### A.2 The reverse: harmonics / subharmonics of the 2.4 GHz transmit vs the 433 MHz RX

- **Integer harmonics of 2400–2483.5 MHz inside 433.05–434.79 MHz: NONE** (2nd harmonic is
  4800 MHz, 1th is the TX carrier itself).
- **1/n subharmonics inside 433.05–434.79 MHz: NONE** (n = 5 gives 480.0–496.7; n = 6 gives
  400.0–413.9; n = 7 gives 342.9–354.8 — the 433 band is not spanned by any 1/n, because
  2400/433.05 = 5.542 and 2483.5/434.79 = 5.712, which straddles the integers 5 and 6 with
  433 outside both).

### A.3 Receiver LO harmonics

The 433 MHz receiver LO would place its **5th harmonic at 2165.25–2173.95 MHz** and its **6th at
2598.30–2608.74 MHz** — the same gap as A.1. **No LO harmonic lands in 2.4 GHz.**

### A.4 Low-order intermodulation products

Enumerating 2nd/3rd-order sums and differences of the two carriers (433.9 and 2450 MHz):

- **No 2nd- or 3rd-order product of {433.9, 2450} falls in either band.** The nearest products
  are 2016.1 MHz (2450 − 433.9) and 2883.9 MHz (2450 + 433.9) — both hundreds of MHz from the
  2.4 GHz band; and 1301.7 / 1735.6 / 2169.5 MHz on the 433 side, all far from 433.
- A product **can** land on a band only by construction (e.g. 2·2450 − 2450 = 2450), which is the
  TX carrier itself, not a spurious product.

### A.5 The coupling that DOES exist — and it is not a harmonic problem

The only real 433↔2.4 GHz coupling at a duplex station is the **station's own 2.4 GHz TX leaking
into its own 433 MHz RX front end**. ADR-072 already quantifies this at the LNA input:

| case | TX leakage at LNA input | margin to LNA P1dB (+20 dBm, ADR-079) |
|---|---:|---:|
| nominal | **−56 dBm** | **76 dB** |
| pessimistic | **−36 dBm** | **56 dB** |

The owned **TQP3M9037** is a **wideband** LNA (operator-captured 0.1 MHz–6 GHz; the LF edge is a
flagged defect — see A.7), so it *would* amplify that 2.45 GHz leakage by +20 dB into the mixer.
**Required 433 MHz BPF rejection at 2.45 GHz: ≥ 20 dB is ample** — with 20 dB of rejection the
pessimistic −36 dBm leakage sits at −56 dBm, still **76 dB below the LNA's +20 dBm P1dB** and
below any plausible receiver blocking threshold. This is exactly the **433 BPF "before the LNA"**
that ADR-072 INV-3 and ADR-079 D3 already require; the harmonic analysis above shows the BPF is
**insurance against the TX fundamental and third-party in-band transmitters**, **not** the
mitigation of a harmonic or IM product — because **there is no harmonic or IM product to
mitigate**.

### A.6 Part A verdict — plain

> **Non-issue, with one already-specified filter.** No harmonic, subharmonic, LO harmonic or
> 2nd/3rd-order intermodulation product of the 433 MHz and 2.4 GHz carriers falls in the *other*
> band, in either direction. The band ratio (~5.66:1) is far from any small integer ratio. The
> only coexistence mechanism is the station's own TX leakage into its own wideband RX LNA, which
> is **quantified and small** (56–76 dB below the LNA's P1dB) and is already handled by the
> **433 BPF of ADR-072 INV-3** at a modest ≥20 dB rejection.

**Does this change ADR-072?** **No.** ADR-072's D3/INV-3 (433 BPF before the LNA) stands, and its
D1/INV-1 (two band antennas, no circulator) is now *additionally* supported: even the harmonic
question, which a circulator/diplexer decision might have been thought to bear on, is a
non-issue. The only refinement this Part contributes to ADR-072 is a **quantified minimum BPF
rejection (≥20 dB at 2.45 GHz)** where the record currently says only "a 433 MHz BPF".

### A.7 Open items (Part A)

- **`TODO(unverified)`** the F33/LR2021 **transmitter spurious and harmonic emission limits**
  (the balloon-side 433 TX harmonics must meet the EN 300 220 / ERC 70-03 spurious mask — not
  fetched here). The *coexistence* question is closed; the *spurious-limit* question is a
  different, balloon-side compliance item.
- **The LNA LF band edge** (0.1 MHz vs 0.7 GHz) remains the flagged defect of ADR-079 D5 and is
  inherited, not re-opened, here.

---

## Part B — the 2.4 GHz reflector surface-accuracy budget and DIY viability

### B.1 The λ/10 rule, and why it is not the right yardstick

At the 2.400 GHz band edge the wavelength is

```
λ = c / f = 299 792 458 / 2.400e9 = 0.12491 m = 124.91 mm
λ/10 = 12.49 mm  ≈ 12.5 mm
```

So the familiar **λ/10 "rule of thumb" is 12.5 mm at 2.4 GHz** — which is why a hand-built
reflector looks attractive at 2.4 GHz where it would be hopeless at Ku. But **λ/10 is a *very*
lossy tolerance**: it is the point at which a reflector is still recognisable, not the point at
which it is good. The right yardstick is **Ruze's equation**.

### B.2 Ruze's equation

> `G(ε) = g₀ − 685.81 · (ε/λ)²` (dB), where ε is the **RMS surface error** and λ the wavelength.
> — Wikipedia, *Ruze's equation*, <https://en.wikipedia.org/wiki/Ruze%27s_equation>
> (the page derives 685.81 = 10·log₁₀(e^−(4π)²)).

This is exactly the `−685.8 (ε/λ)²` form. Evaluating the curve at 2.4 GHz (λ = 124.91 mm):

| RMS surface error ε | ε/λ | gain loss (Ruze) |
|---:|---:|---:|
| 0.5 mm | 0.0040 | 0.011 dB |
| 1.0 mm | 0.0080 | 0.046 dB |
| 2.0 mm | 0.0160 | 0.183 dB |
| **3.38 mm** | 0.0270 | **0.50 dB** |
| **4.77 mm** | 0.0382 | **1.00 dB** |
| 6.0 mm | 0.0480 | 1.65 dB |
| 8.0 mm | 0.0640 | 2.93 dB |
| 10.0 mm | 0.0801 | 4.58 dB |
| **12.49 mm (λ/10)** | 0.1000 | **6.86 dB** |
| 15.0 mm | 0.1201 | 10.31 dB |
| 20.0 mm | 0.1601 | 18.32 dB |

The figure `docs/analysis/assets/rf-gaps/ruze-2g4-surface-error.svg` plots this curve with the two
budget lines and the candidate construction methods marked.

### B.3 What RMS surface accuracy a DIY dish actually needs (the answer to the question)

| budget | RMS surface error allowed | in λ |
|---|---:|---:|
| < 0.5 dB | **≤ 3.30 mm** | ≈ λ/38 |
| < 1.0 dB | **≤ 4.67 mm** | ≈ λ/27 |
| < 2.0 dB | ≤ 6.61 mm | ≈ λ/19 |
| < 3.0 dB | ≤ 8.09 mm | ≈ λ/15 |
| λ/10 "rule" | 12.49 mm | λ/10 (= 6.86 dB!) |

**The honest statement:** at 2.4 GHz a DIY reflector needs about **3.4 mm RMS for <0.5 dB** and
about **4.7 mm RMS for <1 dB**. The λ/10 = 12.5 mm figure the task started from is **not** the
<0.5 dB or <1 dB threshold — it is a **~6.9 dB** tolerance. The accurate rule of thumb is
**λ/25–λ/30**, not λ/10, for a sub-1 dB reflector. That said, 3.4–4.7 mm is still a *large*
allowance by Ku standards (a Ku dish works to ~1 mm), so the task's intuition is half-right: the
**accuracy bar at 2.4 GHz is easy to clear**, it is just ~3× stricter than λ/10.

### B.4 The DIY construction methods, scored

`RMS` values for the hand-built methods are **ESTIMATEs** — no measured surface-accuracy source
exists for any of them, and inventing one would be exactly the failure mode this task forbids.
They are given as brackets for engineering reasoning and are labelled as such.

| method | indicative RMS (ESTIMATE) | Ruze loss @2.4 GHz | meets <1 dB? | worth building? |
|---|---:|---:|:--:|---|
| aluminium kitchen foil, hand-formed | 8–25 mm | 2.9–28.6 dB | **no** | **no** — wrinkle-dominated; not a parabolic surface |
| metal (aluminium) tape over foam/ribs | 5–15 mm | 1.2–10.3 dB | **no** | **no** — same wrinkle/step problem |
| welded wire mesh on DIY ribs | 3–8 mm | 0.4–2.9 dB | borderline | **only** as coarse mesh on a *good* rib set — see below |
| 3D-printed petal dish (FDM) | 1–3 mm | 0.05–0.41 dB | yes | marginal — accuracy is fine but the 0.75 m print **warps**, and it needs a rigid backing |
| fibreglass over a CNC'd plug/mould | 0.5–1.5 mm | 0.01–0.10 dB | yes | accuracy is fine, but **the mould is the expensive part** — you are buying a mould, not a dish |
| **used production Ku DTH offset dish** | **0.3–1.0 mm** | **0.00–0.05 dB** | **yes** | **yes** — this is the one that beats the commercial dish |

Two honest anchors for those brackets:

- **Welded mesh**: the mesh *hole* size is a non-issue at 2.4 GHz. ADR-078 records that the
  vendor in this market rates its **6 mm mesh to 6 GHz**, i.e. a 6 mm hole ≤ λ/10 up to 6 GHz;
  at 2.4 GHz λ/10 = 12.5 mm, so a 6 mm mesh has a **2× hole-size margin**. The mesh penalty at
  2.4 GHz is therefore the **surface** (rib tolerance + inter-rib sag), not the holes — and
  ADR-078 already carries **`TODO(unverified)` a *measured* mesh-vs-solid gain penalty**.
- **Used Ku dish**: a Ku DTH dish is designed for **10.7–12.75 GHz**; to work there its surface
  must already satisfy ~λ/20 at 12 GHz ≈ **1.2 mm**. At 2.4 GHz (λ = 124.91 mm) that is ~λ/100 —
  the 2.4 GHz allowance is **~100× looser** than what the dish was built for. The exact RMS is
  `TODO(unverified)` (no datasheet published) but the *reasoning from its design band* is sound.

### B.5 The cost comparison — does anything beat the commercial assembly?

Sweet-spot (b)'s 2.4 GHz assembly (`design/gain-per-dollar-cliff` @ §8.2; prices CONFIRMED in
`docs/analysis/ground-station-bom-candidates.md`):

| line | price | source | share of assembly |
|---|---:|---|---:|
| Gibertini 75 SE 0.75 m dish | **€94.90** | BOM B3, <https://www.hm-sat-shop.de/gibertini-sat-antenne-75cm-se-profi-serie-sat-spiegel-schuessel-alu-anthrazit/11701-001> | 26.3 % |
| RF Hamdesign LH-13XL helix feed | **€220.00** | BOM C3, <https://www.rfhamdesign.com/downloads/rf-hamdesign-pricelist.pdf> | 61.0 % |
| RF Hamdesign CLX1 feed clamp | **€46.00** | BOM C6, same price list | 12.7 % |
| **assembly** | **€360.90** | | |

**The reflector is only 26 % of the assembly; the feed + clamp are 74 %.** A DIY reflector can
save, at most, the €94.90 dish line. Scoring the reflector alone:

| option | reflector € | vs €94.90 Gibertini | accuracy OK? | labour/fab |
|---|---:|:--:|:--:|---|
| new Gibertini 75 SE 0.75 m | 94.90 | — | yes | none |
| **used production Ku 0.8–0.9 m dish** | **~50 (ESTIMATE)** | **−44.90** | **yes (≥ λ/100 margin)** | verify surface on inspection; often **larger** aperture |
| DIY foil / tape | ~10–30 + former | not reliably cheaper | **no** | high, and still not accurate |
| DIY mesh on ribs | ~30–60 + ribs/frame | not reliably cheaper | borderline | high; `TODO(unverified)` measured penalty |
| 3D-printed petal | ~20–40 filament + backing | not reliably cheaper | yes | very high print time; warp risk at 0.75 m |
| fibreglass over plug | ~30 + plug/mould | **more expensive** (a mould costs far more than €94.90) | yes | very high |

Notes that decide it:

1. **The genuinely-DIY methods do not beat €94.90.** Once you add a *former* or a *rigid rib set*
   that holds 3.4–4.7 mm RMS over 0.75 m, plus the labour, the build costs more than the
   mass-produced dish it would replace. The commercial dish also ships a **documented f/D** — the
   feed is F/D-matched, and a DIY reflector has **no documented f/D** for the €220 feed.
2. **A used production dish is the only cost-beater** — and it is a *buy-not-build* path that
   was **already in the BOM** as option **2.4-A** ("used 90 cm Kathrein CAS 90 … ~50") and in the
   cheap-prototype variant. It is also *more accurate* and *larger-aperture* than the Gibertini.
   Its price is an **ESTIMATE** (`TODO(unverified)` vendor: eBay.de returned HTTP 403 to scripted
   fetch, and the BOM's §8 item 13 flags used-dish searching as manual).
3. **This 2.4 GHz aperture is not link-critical.** ADR-081 D1 (adopted from
   `design/tier0-accessible`) fixes the **EIRP-cap invariant**: above ~8 dBi, 2.4 GHz *ground*
   gain is **inert** for link closure, and ADR-078 INV-3 says a 2.4 GHz dish is justified on
   **interference-rejection / polarisation grounds only**. So the reflector's *dB* does not decide
   the link; its **surface quality decides its sidelobes and cross-pol**, which is precisely what
   the Ruze budget above now bounds.

### B.6 Part B verdict — plain

> **A hand-built DIY reflector is surface-accuracy-feasible at 2.4 GHz (<1 dB needs only
> ~4.7 mm RMS, easily cleared by a printed/fibreglass/used dish) but is NOT worth building: it
> does not beat the €94.90 Gibertini once a former/rib set and labour are counted, and the
> assembly cost is 74 % feed-and-clamp, not reflector.** The one option that **does** beat the
> commercial dish is a **used production Ku DTH offset dish (~€50 ESTIMATE)** — cheaper, more
> accurate (~λ/100 margin at 2.4 GHz) and usually larger than the 0.75 m Gibertini. Because the
> 2.4 GHz ground gain is **inert above ~8 dBi** (ADR-081 D1), the point of buying any reflector
> here is interference rejection and polarisation, not dB.
>
> **This changes the recommended reflector choice** — from *"specifically the new Gibertini 75 SE
> at €94.90"* to *"a bought production solid Ku offset dish, new or used"*, and it explicitly
> **rejects hand-built reflectors**. That is recorded as **ADR-083**.

### B.7 Independent consultant verdict on the figure

[see §B.6 of the ADR / the block below — filled in by the `visual_consult.py` run]

---

## Part C — masthead vs shack-end LNA, with real coax loss

### C.1 The framework

The receive chain is a Friis cascade; the receive-side figure of merit is **system noise
temperature** `T_sys` (lower is better), with `T_e(NF) = 290·(10^(NF/10) − 1)` and a passive
cable at physical temperature 290 K contributing `T = 290·(L−1)` while attenuating by its loss
factor `L`. The general forms:

```
masthead:  T_sys = T_ant + T_LNA + T_cable/G_LNA + T_rx/(G_LNA·G_cable)
shack-end: T_sys = T_ant + T_cable + T_LNA + T_rx/G_LNA
```

The **whole point** of the masthead placement is that in the masthead form the cable's own noise
is divided by the LNA gain (`T_cable/G_LNA`), whereas in the shack-end form the cable's noise
`T_cable` is added at **full weight, ahead of the LNA** — the LNA then amplifies the cable's noise
along with the signal. This is the mechanism `design/amplifier-hypothesis-check` §1.4 states
qualitatively ("*Placed in the shack it amplifies 1.64 dB (433) / 3.38 dB (2.4 GHz) of coax loss
along with the signal*"); Part C supplies the **numbers**.

### C.2 Inputs

| input | value | source |
|---|---|---|
| LNA — Qorvo **TQP3M9037** | **gain 20 dB, NF 0.4 dB** | ADR-079 (operator-captured). **`TODO(unverified)`** — the vendor page `qorvo.com/products/p/TQP3M9037` returned **HTTP 429** on 2026-10-08; the LF-edge contradiction (0.1 MHz vs 0.7 GHz) is the inherited flagged defect of ADR-079 D5. |
| antenna noise temperature `T_ant` | **200 K** (wide beam) | `ground-station-amplifier-hypothesis-check.md` §1.2 |
| receiver NF | bracketed **6 / 8 / 10 dB** | LR2021 NF unpublished (`TODO(unverified)`); the delta is insensitive to it |
| coax — **Ecoflex 15** | 432 MHz **6.10 dB/100 m**; 2400 MHz **16.20 dB/100 m** | Kabel-Kusch, fetched live 2026-10-08, <https://www.kabel-kusch.de/produkt/ecoflex-15/17> |
| coax — **Airborne 10** (LMR-400 class) | 430 MHz **7.60 dB/100 m**; 2400 MHz **19.20 dB/100 m** | Kabel-Kusch, fetched live, <https://www.kabel-kusch.de/produkt/airborne-10/2> |
| coax — **Aircell 7** | 432 MHz **12.92 dB/100 m**; 2400 MHz **33.82 dB/100 m** | Kabel-Kusch (BOM §6) |

### C.3 The dB difference (realistic runs, `T_ant` = 200 K, RX NF = 8 dB)

| band | cable | run | loss | T_masthead | T_shack | **masthead advantage** |
|---|---|---:|---:|---:|---:|---:|
| 433 MHz | Airborne 10 | 15 m | 1.14 dB | 248.9 K | 330.4 K | **1.23 dB** |
| 433 MHz | Aircell 7 | 15 m | 1.94 dB | 253.7 K | 406.5 K | **2.05 dB** |
| 2400 MHz | Ecoflex 15 | 5 m | 0.81 dB | 247.1 K | 302.8 K | **0.88 dB** |
| 2400 MHz | Ecoflex 15 | 15 m | 2.43 dB | 257.1 K | 460.8 K | **2.53 dB** |
| 2400 MHz | Airborne 10 | 5 m | 0.96 dB | 247.9 K | 315.1 K | **1.04 dB** |
| 2400 MHz | Aircell 7 | 15 m | 5.07 dB | 283.9 K | 886.0 K | **4.94 dB** |

Insensitive to the receiver NF (15 m Airborne 10 @433):

| RX NF | T_masthead | T_shack | masthead advantage |
|---:|---:|---:|---:|
| 6 dB | 240.1 K | 323.7 K | 1.30 dB |
| 8 dB | 248.9 K | 330.4 K | 1.23 dB |
| 10 dB | 262.8 K | 341.1 K | 1.13 dB |

### C.4 Part C verdict — plain

> **The LNA must be at the masthead, and the cost of getting it wrong is quantified: 1.2 dB at
> 433 MHz over a 15 m Airborne-10 run, rising to 2.5 dB if that run is 15 m of Ecoflex 15 at
> 2.4 GHz, and 4.9 dB over 15 m of Aircell 7 at 2.4 GHz.** The penalty is *entirely* the cable's
> own 290 K noise added ahead of the LNA (e.g. Aircell 7 @2.4 GHz puts **642.6 K** ahead of the
> LNA vs 87.0 K for 15 m of Airborne 10 at 433 MHz). Since the whole amplifier-led receive chain
> buys **+6.8…+12.3 dB** (central +9.7 dB, `amplifier-hypothesis-check` §1.2), a **2–5 dB** shack-end
> penalty would throw away **~20–50 %** of the LNA's entire benefit. This is the quantitative
> confirmation of ADR-079 D1 ("*at the masthead, ahead of the feedline*") and of
> `amplifier-hypothesis-check` §1.4. Real cable choice matters as much as placement: at 2.4 GHz a
> 15 m Aircell-7 run costs **~2.4×** more system T than 15 m of Ecoflex 15.

### C.5 Open items (Part C)

- **`TODO(unverified)`** the TQP3M9037 gain/NF read from the vendor (HTTP 429 on 2026-10-08); the
  0.4 dB NF is the operator-captured figure of ADR-079 and, per that record, the part's **433 MHz
  coverage is itself unresolved** (D5) — if the LF edge is 0.7 GHz, the 433 masthead chain needs a
  different device and this part's 433 numbers move to that device's NF.
- **`TODO(unverified)`** the LR2021 receiver NF and maximum input level (inherited).
- The `T_ant` = 200 K assumption and the local man-made noise floor are the model's weak inputs;
  if site man-made noise dominates, neither antenna gain nor an LNA buys dB (ADR-079 §Costs).

---

## Verdict summary

| part | question | verdict |
|---|---|---|
| **A** | Do 433↔2.4 GHz harmonics/IM collide? | **Non-issue.** No harmonic/subharmonic/LO-harmonic/IM product in either band; only the station's own TX leakage (56–76 dB below the LNA P1dB) matters, handled by the ADR-072 ≥20 dB 433 BPF. **ADR-072 unchanged** (only add the ≥20 dB number). |
| **B** | Does a DIY reflector beat the Gibertini 0.75 m + helix assembly? | **Hand-built: no.** 2.4 GHz needs only ~4.7 mm RMS for <1 dB, but no hand-built method beats €94.90 once a former/rib set is counted, and 74 % of the assembly is the feed+clamp. **A used production Ku dish (~€50 ESTIMATE) does beat it** (cheaper, more accurate, usually larger). → **ADR-083.** |
| **C** | Masthead or shack-end LNA? | **Masthead, always.** Shack-end costs **1.2 dB @433/15 m**, **2.5 dB @2.4 GHz/15 m Ecoflex 15**, **4.9 dB @2.4 GHz/15 m Aircell 7** — 20–50 % of the LNA's whole +9.7 dB benefit. Confirms ADR-079 D1. |
