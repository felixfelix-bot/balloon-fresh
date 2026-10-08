# Plan review — independent consultant challenge of the ground-station plan

**Status:** recorded 2026-10-08. **Branch:** `design/adr-set-groundstation`
(off `github/main` @ `09e1b69`; review commit `c1cbb60`).
**Question to the consultant (operator's words):** *"please work with the consultants to check if
our current plan makes sense."*
**Consult lane:** `/home/c03rad0r/hermes-orchestration/scripts/fleet/visual_consult.py`
(`--timeout 900 --max-tokens 20000 --json`), against the local router
(`http://127.0.0.1:9099`), model read back from the response (see below).
**Artifact reviewed:** `docs/analysis/assets/ground-station-plan-summary.png`
(rendered by `docs/analysis/render_ground_station_plan_summary.py`).

---

## 1. Plan summary (what the consultant was asked to challenge)

### 1.1 Architecture — a full-duplex Internet gateway through a bent-pipe balloon

```
  ground users ── WiFi/captive portal ──▶ GROUND STATION (full-duplex Internet gateway)
                                              │
                        2.45 GHz UPLINK  ▲   │   433 MHz DOWNLINK  ▼   FLRC-max
                        (ground→balloon) │   │   (balloon→ground)        RX = binding direction
                                              ▼
                                     BALLOON — bent pipe
                        F33 @433 TX (+33 dBm)  — HIGH-POWER variant, amateur band
                        or bare LR2021 @433 TX (<= +12.15 dBm EIRP) — LOW-POWER variant, licence-exempt
                        LR2021 @2.4 GHz RX
                                              │
                                              ▼
                                           Internet
```

- **Full duplex is required** because the station is an access gateway serving TCP/IP; a
  half-duplex T/R relay/switch is **ruled out**. The LR2021 transceiver is half-duplex, so the
  **balloon carries two separate radio chips** for simultaneity.
- **Ground RECEIVE = 433 MHz, ground TRANSMIT = 2450 MHz** (mirror of the balloon-side split in
  ADR-034). The bands are **5.65× apart**.
- **Duplexing is by BAND SEPARATION: two separate band antennas, NO circulator.** Composite
  TX→RX isolation ≈ **68 dB** (20 dB spacing/pattern + 3 dB own-antenna mismatch + 45 dB RX
  band-pass rejection). A **433 MHz BPF sits before the LNA**; a PIN limiter is optional.
- **The uplink is attenuated, not amplified**: under the ISM EIRP/PSD ceiling an 11.1 dBi ground
  antenna leaves only ≈ **+3.2 dBm** conducted at FLRC-max bandwidth, so a digital step
  attenuator (not a PA) controls it.
- **One az/el positioner** carries both band antennas, boresighted.

### 1.2 The locked decisions (now ADR-071 … ADR-082)

| # | decision | ADR |
|---|---|---|
| 1 | 433 downlink = **FLRC at maximum throughput**; **LoRa rejected** as too slow. **Two flight boards** are built — F33 high-power (amateur band) and low-power LR2021 (licence-exempt) — so others can fly without a licence. | 073, 074 |
| 2 | The **F33 (~USD 8) is the cheapest dB** in the system (~0.40 USD/dB) and multiplies every ground candidate's range **3.55×**; low-power + max-FLRC-at-650 km is **not affordable** (it implies a 2.6–7.4 m dish). | 075 |
| 3 | The ground station is a **full-duplex Internet gateway** via the balloon as a bent pipe (full duplex rules out a half-duplex T/R relay). | 071 |
| 4 | **Band-split duplex**: 433 RX / 2.45 GHz TX, duplexed by **band separation** (separate antennas and/or a diplexer) — **the circulator is not needed at all**. | 072 |
| 5 | **Stow-on-wind** policy: size for 10–15 m/s operation, park for the storm, anemometer cutoff + **mechanical latch**. | 076 |
| 6 | **Print the structure, buy the gearing** — printed plastic gears strip; a **self-locking worm reducer is mandatory**; metal for the load path, printed for covers. | 077 |
| 7 | **Small dish / wide beam over big dish / narrow beam** — the cliff is the **rotator class (~1.0 m² wind area)**; mesh (λ/10 = 69 mm at 433 MHz) moves it (solid 2.40 m = 1.88× the rating → infeasible; same dish as 6 mm mesh = 0.50× → fine). | 078 |
| 8 | **Amplifier-led receive chain** with the **owned TQP3M9037 LNA**, accepting the **~4–5 dB** noise-temperature penalty of a wide beam. | 079 |
| 9 | The **XR-613 divider is resistive** (DC–5 GHz ⇒ 6 dB, **no array gain**) — a **bench tool**, not an array combiner. | 080 |
| 10 | **Tier ladder** + **recommended option B**: Diamond A-430S15R + DIY tracker P2, **≈ EUR 735**, **150 km @ 2.6 Mbps** low-power / **532 km with the F33**. | 081 |
| 11 | **Rate adaptation** — size the antenna for the **minimum useful rate at maximum range**, not the maximum rate. | 082 |

### 1.3 The tier ladder (cost NAMES its tier)

| tier | cost (EUR) | capability |
|---|---:|---|
| **Tier 0a** — two omnis, no motors, no firmware | **90–245** | LoRa-class; 433 downlink +13.7 dB @650 km |
| **Tier 0b** — hand-aimed Yagi | **144–304** | F33 FLRC 2.6 Mbps to 650 km, human points ~40° |
| **Tier A** — auto, 2.4 GHz dish removed | **546–685** | automatic pointing; LoRa-class uplink |
| **option B (RECOMMENDED)** — A-430S15R + DIY tracker P2 | **≈ 735** | **150 km @2.6 Mbps** low-power / **532 km** with F33 |
| **Tier B / dish tiers** | **2,166 … 10,100** | pre-cliff 4-bay array (2,166) / post-cliff dish build (5,900–10,100) |

Two invariants sit under the ladder: **above ~8 dBi the 2.4 GHz ground gain is INERT**
(`EIRP = P_tx + G_ground` is capped, so extra ground gain is cancelled by PA back-off), and the
**2.4 GHz dish is the sole cause of the positioner class** (remove it and the tightest element is
the 433 Yagi at ~4°, twice as forgiving).

### 1.4 The challenge questions put to the consultant

Q1 duplex architecture soundness; Q2 tier-ladder internal consistency under **two competing legal
ceilings** (flat **20 dBm EIRP** vs **≈14.26 dBm EIRP** under the 10 dBm/MHz PSD rule at FLRC-max
bandwidth, ~6 dB apart); Q3 the **TQP3M9037 band edge** (operator: 0.1 MHz–6 GHz; vendor figure
captured in-repo: **0.7–6 GHz**, which would exclude 433 MHz); Q4 **array-vs-single-Yagi**
contradiction between two sibling analyses; Q5 what is missing or self-contradictory; Q6 verdict.

---

## 2. Consultant verdict (VERBATIM)

**Was the consultant engaged?** **YES — on the first attempt** (a retry loop of up to 14 attempts
was armed for the known 503 flakiness; 1 was used).

**Served model, read back from the response (`served`), NOT from the alias sent:**

```
served:   "gpt-6-astra"
model:    "gpt-6-astra"
status:   200
files:    ["docs/analysis/assets/ground-station-plan-summary.png"]
```

> `gpt-6-astra` is served even though it **does not appear in the router's `/v1/models` list** — that
> endpoint is not evidence about this lane, and the served id here is read back from the response
> body, not assumed from the request.

> **Which line is the model's opinion.** This call used `--json`, which emits **no** `visual_review:`
> token at all. (`visual_consult.py --emit-evidence` prints `visual_review: APPROVED` **by default**
> from `--verdict`; that token is **the CLI's default, not the model's opinion**, and it is not used
> here.) The model's own verdict is the **final line of its answer body**, reproduced below.

**Artifacts of record (verbatim):**

- `docs/analysis/assets/consult-verdict-plan-review.txt`
- `docs/analysis/assets/consult-verdict-plan-review.json`

### 2.1 The model's own final line

```
independent VERDICT: QUALIFY
```

**In one sentence:** the plan makes sense as a **system architecture** but **not yet as a validated
performance or procurement plan** — the ranges depend on unresolved legal-ceiling and power-baseline
assumptions, and the receive chain depends on an unconfirmed LNA band edge.

### 2.2 Full answer, verbatim

```text
## Q1. Duplex architecture

**The topology is sound in principle, but the evidence for its RF performance is not yet sufficient.**

Two independent transceiver chains, two antennas, and frequency separation do solve the LR2021 half-duplex limitation. A circulator is neither required nor appropriate for routing 433 MHz and 2.45 GHz when the paths are already separated by band.

However, “two antennas, no circulator” does **not automatically establish full-duplex operation**. The system must demonstrate simultaneous:

- 2.45 GHz ground transmission at the legal EIRP/PSD limit;
- 433 MHz reception at the required FLRC sensitivity;
- no LNA compression;
- no receiver desensitisation;
- no packet-error-rate degradation.

The quoted isolation arithmetic,

> 20 dB antenna/pattern + 3 dB mismatch + 45 dB filter rejection = 68 dB,

is plausible as a first-order estimate, but it is not a credible design value until measured in the installed geometry. The 20 dB term is especially weak: antenna-pattern isolation, near-field coupling, mast coupling, cable coupling, polarisation leakage, and positioner/metalwork reflections can easily differ from the nominal far-field pattern.

At 20 dBm EIRP, 68 dB isolation leaves approximately **−48 dBm** at the receive input before cable and geometry corrections. That may be tolerable, or it may overload or desensitise the LNA, depending on its input P1dB, blocker response, and gain distribution. At other power assumptions, the residual changes correspondingly.

A 433 MHz band-pass filter **before the LNA is mandatory and directionally correct**, but “45 dB rejection” alone is not enough. The design needs:

1. measured rejection at the actual 2.45 GHz transmit frequency and harmonics;
2. insertion loss at 433 MHz, included in the noise figure;
3. LNA input P1dB and blocker tolerance;
4. intermodulation assessment;
5. a transmit-on/receive-on desense test;
6. a PIN limiter only if its added loss and noise penalty are acceptable.

The limiter is not a substitute for isolation. The correct acceptance criterion should be measured packet error rate and receiver sensitivity with the 2.45 GHz transmitter operating at maximum permitted output.

**Conclusion:** architecture valid; 68 dB is a design hypothesis, not a demonstrated margin.

---

## Q2. Tier ladder and the two 2.4 GHz legal ceilings

The ladder is **not internally consistent until one legal ceiling is selected**.

The two stated limits are:

- flat limit: **20 dBm EIRP**;
- PSD limit: approximately **14.26 dBm EIRP** at maximum FLRC bandwidth under a **10 dBm/MHz** rule.

That is a difference of:

\[
20 - 14.26 = 5.74\ \mathrm{dB}
\]

For a free-space, power-limited link, 5.74 dB reduces range by roughly:

\[
10^{5.74/20} \approx 1.94
\]

So a claimed **150 km** link could become approximately **77 km**, and a claimed **532 km** link approximately **274 km**, if the 2.4 GHz uplink is the limiting direction and the published distances were calculated using 20 dBm EIRP.

Those exact reductions do not necessarily apply if the 433 MHz downlink is the bottleneck. That is the problem: the plan does not show an auditable bidirectional link budget proving which direction limits each rung.

The maximum-rate rung is particularly exposed. Under a PSD rule, reducing the occupied bandwidth from the maximum FLRC bandwidth changes the permitted total EIRP. Therefore the claimed:

- 2.6 Mbps;
- 1.3 Mbps;
- 650 kbps

rungs cannot simply be treated as one fixed-power ladder. Each needs its own:

- occupied bandwidth;
- PSD calculation;
- total EIRP;
- receiver sensitivity;
- link margin;
- range.

The statement that ground antenna gain above approximately **8 dBi is inert** is only valid after applying the correct regulatory constraint. Under a flat EIRP limit, extra gain requires reduced conducted power. Under a PSD-limited rule, the same general conclusion may apply, but the permitted total power depends on bandwidth and the exact regulatory definition of PSD.

There is also a major power inconsistency in the ladder:

- the low-power board is described as **≤ +12.15 dBm EIRP**;
- the figure labels it **“+22 dBm chip”**;
- the claimed F33 range multiplier is **3.55×**, which corresponds to roughly **11 dB**, or approximately +22 to +33 dBm;
- +33 dBm versus +12.15 dBm is **20.85 dB**, corresponding to about **11× range**, not 3.55×.

Thus the displayed **150 km / 532 km** numbers appear to use a +22 dBm low-power baseline, not the stated +12.15 dBm legal EIRP baseline.

**Survival assessment:**

- Tier 0a and Tier 0b may survive, but their range claims must be recalculated.
- Option B at **150 km low-power / 532 km F33** does not survive as a quantitative claim until the ceiling and baseline power are resolved.
- The 2.6 Mbps rung is the most vulnerable to the 14.26 dBm PSD interpretation.
- The 1.3 and 0.65 Mbps rungs may recover some power under PSD rules, but only after recalculating their actual occupied bandwidths.
- All upper tiers are presently costed against an uncertain performance target.

---

## Q3. TQP3M9037 frequency coverage

If the authoritative vendor specification is **0.7–6 GHz**, the amplifier-led 433 MHz receive chain does **not stand**.

The plan cannot simultaneously rely on:

- a TQP3M9037 as the 433 MHz masthead LNA; and
- a datasheet that excludes 433 MHz.

The fact that an operator statement says **0.1–6 GHz** is not enough. This could be a part-number variant, an old revision, a distributor error, or a misunderstanding of the operating range. At 433 MHz, the design needs verified values for:

- gain;
- noise figure;
- input and output return loss;
- P1dB;
- stability;
- supply conditions.

If the real lower limit is 0.7 GHz, the choices are:

1. replace it with a verified 433 MHz LNA;
2. use a separate 433 MHz gain block;
3. omit the LNA and accept the calculated sensitivity/range penalty;
4. obtain manufacturer confirmation for the exact owned part.

Until that is resolved, decision 7 is conditional and should not be called locked.

---

## Q4. Single Yagi versus array or dish

The array/dish discussion is **not entirely moot**, but it is premature.

A single **14.8 dBi Diamond A-430S15R** may be sufficient for the claimed Option B tier. Compared with a nominal 20 dBi four-bay array, it gives up about:

\[
20 - 14.8 = 5.2\ \mathrm{dB}
\]

If the link is power-limited and all else is equal, that corresponds to roughly a **1.82× range difference**. That is not trivial. A 14.8 dBi Yagi is therefore not automatically equivalent to the proposed array.

On the other hand, the array brings real penalties:

- narrower beamwidth;
- more difficult pointing;
- higher wind moment;
- more complex phasing and feed distribution;
- additional loss and construction uncertainty;
- potentially worse polarisation and phase consistency;
- greater mechanical load on the tracker.

With the **F33 locked**, the array is not automatically justified. The F33 adds approximately 11 dB relative to a +22 dBm baseline, which is already comparable to or greater than the array’s gain advantage. If the low-power baseline is really +12.15 dBm, however, the F33 advantage is approximately 20.85 dB and the claimed performance picture changes completely.

The correct decision is therefore:

- retain the single Yagi as the baseline;
- prove the 150 km and 532 km figures with measured antenna gain, tracking error, sensitivity, and the correct legal power;
- add an array only if the validated link budget shows a specific shortfall.

The large dish is clearly unattractive for the stated mechanical concept. A solid 2.4 m reflector being **1.88×** the strongest rotator rating is a structural rejection, not a minor optimisation issue. A coarse mesh reflector may reduce wind load, but it still requires validated gain, stiffness, mesh geometry, and wind-moment calculations.

---

## Q5. Missing or self-contradictory elements

### Specific contradictions

1. **Low-power output contradiction**

   The plan states both:

   - **≤ +12.15 dBm EIRP**, and
   - **+22 dBm chip**.

   These are not interchangeable. A +22 dBm conducted transmitter with even modest antenna gain cannot be described as +12.15 dBm EIRP unless there is substantial attenuation.

2. **F33 multiplier contradiction**

   The claimed **3.55×** range multiplier corresponds to approximately 11 dB of additional transmit power, i.e. roughly +22 to +33 dBm.

   It does not correspond to +12.15 to +33 dBm, which would produce approximately **11× range** in a free-space power-limited case.

3. **Legal ceiling contradiction**

   The ladder uses an unstated mixture of the **20 dBm EIRP** and **14.26 dBm PSD-limited** assumptions.

4. **“Every ground candidate” claim**

   The F33 does not necessarily multiply the range of every antenna by 3.55×. That is only true where the 433 MHz balloon downlink is the limiting link and the rest of the system remains linear. If the 2.45 GHz uplink, tracking, regulatory ceiling, or receiver sensitivity is limiting, the range gain is smaller or zero.

5. **LNA specification contradiction**

   The TQP3M9037 is described as covering 0.1–6 GHz, while the captured vendor figure says 0.7–6 GHz. This directly affects a locked receive-chain decision.

6. **“Maximum FLRC throughput” versus tier adaptation**

   The plan calls 2.6 Mbps the maximum FLRC mode but then sizes the antenna for 1.3 and 0.65 Mbps. That is reasonable engineering, but the regulatory bandwidth, sensitivity, and EIRP must be recalculated per mode rather than treated as one radio setting.

### Important omissions

- Complete bidirectional link budgets at 2.6, 1.3, and 0.65 Mbps.
- Receiver sensitivity figures at those rates.
- Actual occupied bandwidth for each mode.
- Polarisation losses and antenna feed losses.
- Pointing-error and tracking-error budgets.
- Balloon altitude, horizon geometry, Fresnel clearance, and Earth-curvature treatment.
- Measured 433/2450 isolation in the assembled station.
- LNA blocker, P1dB, and intermodulation tests.
- Regulatory treatment by jurisdiction, including 433 MHz amateur/ISM status, duty cycle, bandwidth, spectral mask, and unattended Internet-gateway restrictions.
- Proof that the F33 board’s +33 dBm is legal for the intended operator and antenna configuration.
- Mechanical calculations for wind moment, latch loads, cable torque, centre of gravity, and stow survival.
- A clear definition of what “full duplex” means at the network and MAC layers. Two RF paths do not automatically provide a usable bidirectional Internet gateway.

### Highest-risk gap

The highest-risk gap is **the absence of one consistent, legally valid, measured end-to-end link budget**.

The +12.15 dBm versus +22 dBm conflict, the 3.55× multiplier, and the 20 dBm versus 14.26 dBm ceiling are not bookkeeping defects. They can change the claimed ranges by factors of approximately **2**, **3**, or **11**, depending on which assumption is used. That undermines the tier prices and the mechanical choices built around them.

---

## Q6. Verdict and one most important change

The plan makes sense as a **system architecture**, but not yet as a validated performance or procurement plan.

The one change that would most improve it is:

> **Freeze one jurisdiction, one legal power/PSD interpretation, one bandwidth per rate, and one verified radio/LNA configuration; then recalculate and bench-test the complete two-way link budget before buying the expensive tracker, array, or dish hardware.**

That exercise should explicitly reconcile:

- +12.15 dBm versus +22 dBm;
- the 3.55× F33 multiplier;
- 20 dBm versus 14.26 dBm EIRP;
- TQP3M9037 coverage at 433 MHz;
- 433 MHz downlink and 2.45 GHz uplink margins independently;
- simultaneous-transmit isolation and desense.

Until then, Option B should be treated as a promising prototype tier, not a demonstrated **150 km / 532 km** service tier.

independent VERDICT: QUALIFY
```

---

## 3. Disposition of the consultant's findings

**Summary: 8 findings, 8 accepted, 0 disputed.** Two of them (the 2.4 GHz legal-ceiling defect and
the TQP3M9037 band edge) the plan had **already self-flagged**; the consultant's contribution is to
make them **hard conditions rather than open notes**. The consultant **did not** dispute the mesh
rule, the rotator-class cliff, the stow + mechanical-latch policy, the print/buy gearing split, the
XR-613 resistive-divider finding, or the F33-cheapest-dB arithmetic. Three records were **changed**
in response (ADR-075, ADR-079, ADR-081); four more were clarified (ADR-071, ADR-072, ADR-078,
ADR-082).

| # | finding (Q) | assessment | action taken |
|---|---|---|---|
| **F1** | Duplex topology is sound *in principle*, but **68 dB isolation is a design hypothesis, not a demonstrated margin**; the 20 dB pattern term is the weakest; a 433 BPF is mandatory but "45 dB rejection" is not enough; the acceptance criterion must be **measured PER / sensitivity with the 2.45 GHz TX at maximum permitted output** (Q1) | **ACCEPT.** No architecture change; the *evidence standard* rises. | **ADR-072**: the "not measured" note now carries the consultant's full **acceptance criterion** (measured S21 at installed geometry, BPF measured rejection **and** in-band insertion loss, LNA P1dB/blocker, end-to-end desense test). |
| **F2** | The ladder is **not internally consistent until ONE legal ceiling is chosen**; 20 dBm EIRP vs ≈14.26 dBm (PSD) is **5.74 dB ≈ 1.94× range** (so 150 km → ~77 km, 532 km → ~274 km if the uplink limits) (Q2) | **ACCEPT.** Already a **flagged DEFECT** in ADR-072/ADR-081 (a contradiction that names no winner); the consultant **quantifies** it. | **ADR-081 D3a** now states the ceiling disagreement as a range-affecting blocker; **ADR-082** requires the ladder be recomputed once the ceiling is frozen. |
| **F3** | **Power-baseline contradiction:** the plan says ≤ +12.15 dBm EIRP *and* +22 dBm chip; the **3.55×** multiplier corresponds to **+11 dB** (+22→+33 dBm), **not** to +12.15→+33 dBm, which would be **≈11×**. The "150 km / 532 km" pair therefore sits on the **+22 dBm baseline**, not on the licence-exempt footing. Also: "every ground candidate ×3.55×" is only true where the **433 downlink limits** (Q2/Q5) | **ACCEPT — the strongest finding. It was a real ambiguity in the consolidated set, and it is now fixed.** | **ADR-075**: new **baseline table** (3.55× on +22 dBm / ≈11× on +12.15 dBm EIRP) and D3 qualified to "where the 433 downlink is the limiting link". **ADR-081 D3a (new, binding)**: every range claim **must name its power baseline**; 150/532 km are a **prototype target, not a demonstrated service tier**. |
| **F4** | If the vendor spec is **0.7–6 GHz**, the amplifier-led 433 receive chain **does not stand**; decision 7 must not be called locked (Q3) | **ACCEPT.** Already flagged in ADR-079; the consultant makes it a **condition**. | **ADR-079 status** downgraded to **"Accepted by operator — but CONDITIONAL, not 'locked'"**, reopening if 0.7–6 GHz is authoritative. |
| **F5** | The array/dish discussion is **not moot but premature**: retain the **single Yagi as baseline**; the array's 20 vs 14.8 dBi is **5.2 dB ≈ 1.82× range**, not trivial; add an array only if a **validated** budget shows a specific shortfall; the solid 2.4 m dish is a **structural rejection** (Q4) | **ACCEPT.** Matches ADR-078 D5 / ADR-081 D3; the consultant supplies the **quantification**. | **ADR-078**: the 5.2 dB ≈ 1.82× advantage is now recorded, with the explicit "array returns if a validated budget shows that shortfall" clause. |
| **F6** | **Missing artifacts:** a per-rate **two-way** link budget (occupied bandwidth, PSD, EIRP, sensitivity, margin per rung); polarisation/feed losses; horizon/Fresnel geometry; measured isolation; LNA blocker/intermod tests; jurisdiction and duty-cycle/spectrum-mask treatment; F33 legality proof; mechanical wind/latch calculations; and **what "full duplex" means at the NETWORK/MAC layer** (Q5) | **ACCEPT.** Some items already exist in-repo (horizon geometry is treated in ADR-073; the pointing budget is in ADR-078; the wind/moment model is in ADR-078); the two genuinely absent ones are **added as open items**. | **ADR-082**: the **per-rate two-way budget** is now the top open item. **ADR-071**: the **network/MAC-layer full-duplex definition** is now an open item, with the note that two RF paths are necessary but not sufficient. |
| **F7** | The consultant's **−48 dBm** residual at the receive input (at 20 dBm EIRP / 68 dB isolation) may overload or desense the LNA depending on input P1dB and blocker response (Q1) | **ACCEPT with a scope note.** The in-repo model computes **−56 dBm** nominal at a *smaller* conducted power (+3.2 dBm into an 11.1 dBi antenna), so the two differ by the assumed TX power, not by method. **Both are far below the owned LNA's +20 dBm P1dB**, but the **blocker/intermod** question is unanswered. | Folded into **ADR-072**'s acceptance criterion (LNA P1dB + blocker tolerance + desense test) rather than stated as a new defect. |
| **F8** | **Verdict: QUALIFY.** The one change that would most improve the plan: **freeze one jurisdiction, one legal power/PSD interpretation, one bandwidth per rate, and one verified radio/LNA configuration; then recalculate and bench-test the complete two-way link budget BEFORE buying the expensive tracker, array or dish hardware** (Q6) | **ACCEPT — adopted as the plan's next milestone.** | Recorded below as **§3.1 Next milestone**. |

### 3.1 Next milestone (adopted from the consultant's Q6)

> **Freeze one jurisdiction + one legal power/PSD interpretation + one occupied bandwidth per rate +
> one verified radio/LNA configuration; then recompute and bench-test the complete two-way link
> budget before buying the tracker, array or dish.**

That exercise must explicitly reconcile: `+12.15 dBm EIRP` vs `+22 dBm chip`; the F33 multiplier
(3.55× vs ≈11×); `20 dBm` vs `≈14.26 dBm` EIRP; the TQP3M9037's coverage at 433 MHz; the **433
downlink and 2.45 GHz uplink margins independently**; and simultaneous-transmit isolation/desense.
Until then **option B is a promising prototype tier, not a demonstrated 150 km / 532 km service
tier** — which is exactly how ADR-081 D3a now reads.

### 3.2 What this review is not

A visual/plan consult is **not** a code review and does **not** satisfy the ADR-010 review gate; no
independent review of this ADR set as *code/markdown* has been performed here. The consultant is
also a **different family** from the author (OpenAI/Astra vs the authoring lane), and its verdict is
recorded verbatim rather than summarised in the records it touches.

---

## 4. Reproduction

```bash
/usr/bin/python3 docs/analysis/render_ground_station_plan_summary.py   # the reviewed figure
python3 /home/c03rad0r/hermes-orchestration/scripts/fleet/visual_consult.py \
    docs/analysis/assets/ground-station-plan-summary.png \
    --ask "$(cat <the plan summary + challenge questions>)" \
    --timeout 900 --max-tokens 20000 --json --out /tmp/consult_answer.json
```

> **Reading the CLI's output.** `visual_consult.py --emit-evidence` prints
> `visual_review: APPROVED` by **default** (`--verdict` default, `parse_args`), which is **the CLI's
> token, NOT the model's opinion**. This review used `--json` (which emits no such token) and reads
> the model's own verdict from the **end of the answer body**; the served model is read back from
> the response (`served`), never from the requested alias.
