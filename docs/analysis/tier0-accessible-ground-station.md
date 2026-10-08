# Tier 0 (ultra-low-cost) ground station, and a re-costed Tier A — now that the 2.4 GHz dish is unnecessary

> **STATUS: ANALYSIS — NOT A DECISION RECORD.** This is `docs/analysis/`; it authorises no
> order, no fab freeze, and no change to any board or BOM. The companion ADR
> (`docs/adr/069-*`) is **Proposed**.

| Field | Value |
|---|---|
| **Date** | 2026-10-08 |
| **Branch** | `design/tier0-accessible` |
| **Worktree** | `/home/c03rad0r/worktrees/bf-tier0` |
| **Base commit** | `09e1b69` (`github/main`) |
| **Author** | Hermes Agent (subagent), for the operator |
| **Repro command** | `python3 docs/analysis/tier0_accessible_model.py` (prints every numeric table below verbatim) |
| **Read first** | `docs/analysis/ground-station-lowpower-link-and-shared-dish.md` (433 required gain); `docs/analysis/positioner-lowcost-3dprinted.md` (right-sizing, EIRP-cancellation, positioner cost); `docs/analysis/ground-station-flrc-max-throughput.md` (F33 → dish size); `docs/analysis/ground-station-bom-candidates.md` (all **CONFIRMED** prices); `docs/analysis/ground-station-gain-per-dollar.md` (the two sweet spots, tracker menu P1/P2). |
| **Builds on, does not re-derive** | the two sweet spots and the positioner menu are the sibling `design/gain-per-dollar` (ADR-068); this document only adds the tier *below* the cheapest of them and removes the 2.4 GHz dish from it. |
| **Out of scope** | the ground *radio* (SDR/LR2021 breakout, host, software), and any order. Costs below are **antenna + positioner/mount + coax + connectors** — the same scope as the sibling documents, so the totals are comparable. |

Every number is **COMPUTED** (the script printed it), **CITED** (repo path §), or an explicit
**ESTIMATE** / **`TODO(unverified)`**. General web-search backends were captcha-gated again this
session (Brave 429, DuckDuckGo 202, Mojeek captcha, Ecosia 403) — so the *new* cheap items
carry `TODO(unverified)` rather than an invented figure, exactly as the sibling documents did.

---

## 0. Verdict first

### The EIRP-cap question, answered

> **Does ground uplink antenna gain above the minimum buy anything?**
>
> **No — above ~8 dB it buys literally nothing, and it cannot buy anything, because the ground
> 2.4 GHz transmitter is EIRP-capped.** Under the licence-exempt 100 mW / **20 dBm EIRP** ceiling,
> `EIRP = (P_tx + G_ground)` is fixed at the cap, so **`G_ground` cancels out of the uplink link
> equation**. Adding aperture gain forces an equal PA back-off; the received power at the balloon
> is unchanged (Table 1). The dish is not merely *unnecessary* — **13.4 of a 0.6 m dish's 21.4 dBi
> are inert** (Table 1b).

* **The useful range is 0 → 8 dBi.** The LR2021's own 2.4 GHz PA tops out at **+12 dBm**
  (datasheet Table 3-22 `TXOPHF`), so it takes exactly **20 − 12 = 8 dB** of ground gain to reach
  the legal EIRP. Everything above 8 dBi is dead weight.
* **The maximum compliant uplink margin is +17.4 dB @300 km and +10.7 dB @650 km** — and an
  **8 dBi panel reaches both exactly**. A 3 dBi omni still closes: **+12.4 dB @300 km, +5.7 dB
  @650 km** (Table 1).
* **What the dish was actually for** is *not* link closure and *not* margin beyond the cap — it is
  **interference rejection** in a crowded 2.4 GHz band, **polarisation purity**, and keeping the
  PA cheap. Those are real, but they are not worth 13–19 inert dB of dish, wind load and pointing.
* **The 433 side is the opposite case and must not be conflated.** There the *airborne* EIRP is
  what is capped, so the **ground's 433 receive gain is a real lever** (it is the only one). But
  for **LoRa the required 433 ground gain is negative** (−13.7 dBi @650 km), so even the 433
  Yagi is *margin only*, not closure (Table 2).

### The tiers

| Tier | What it is | Cost (parts) | Closes |
|---|---|---|---|
| **Tier 0a — no pointing at all** | **two omnis** on a fixed mast (2.4 GHz uplink + 433 LoRa downlink). No motors, no printing, no tracker. | **≈ €90–245** | Low-power LR2021 board: 433 **LoRa** downlink (+13.7 dB @650 km) and 2.4 GHz uplink (+5.7 dB @650 km). **Bit-rate limited.** |
| **Tier 0b — hand-aimed** | one **13.1 dBi 433 Yagi** (€69) + 2.4 GHz omni, on a **manual pan-tilt/tripod**. Still no motors. | **≈ €145–305** | Adds **F33 FLRC 2.6 Mbps to 650 km** (+5.2 dB) with a human pointing the Yagi. |
| **Tier A — re-costed** | same as before **minus the 2.4 GHz dish + feed** (€315), **plus** a cheap 8 dBi 2.4 GHz panel. | **≈ €545–685** (from ≈ €925–950 as originally line-itemed) | Everything Tier 0b does, **unattended**, + 433 margin (+6.9 dB @650 km on F33/2.6 Mbps). |

**The headline:** the 2.4 GHz dish was the single most expensive and most mechanically
consequential item in Tier A, and the EIRP cap makes it **inert above 8 dBi**. Removing it
**costs ~€30 (an 8 dBi panel)** and **saves ~€315** — and, more importantly, it removes the
**only element in the whole station that needed a tight beam**, which is what lets **Tier 0
exist at all** (Table 4).

---

## 1. The EIRP-cap question, with numbers

### 1.1 The link equation and the cancellation

For the **ground → balloon (uplink)** direction:

```
P_rx_balloon = P_tx_ground + G_ground + G_balloon_rx − FSPL          (dB)
EIRP         = P_tx_ground + G_ground        ≤ 20 dBm (licence-exempt cap)
⇒ P_rx_balloon = EIRP + G_balloon_rx − FSPL   —  G_ground has cancelled.
```

The ground antenna gain appears **only** through the EIRP term. Once the cap binds, every extra
dB of aperture is paid for with a dB of PA back-off, one-for-one.

### 1.2 Table 1 — uplink margin vs ground antenna gain (script output, verbatim)

Assumptions: balloon RX sensitivity **−137 dBm** (bare LR2021 SF12, 2.4 GHz, datasheet Table 3-18;
F33+LNA is −136, i.e. 1 dB better), balloon RX antenna **10 dBi** (ADR-037), ground PA max
**+12 dBm** (LR2021 `TXOPHF`), cap **20 dBm EIRP**. FSPL(2.4 GHz): 149.6 dB @300 km, 156.3 @650 km.

```
---- 300 km   FSPL = 149.6 dB ----
G_ground dBi  EIRP_eff dBm  margin dB                useful?
         0.0          12.0        9.4        gain fully useful
         3.0          15.0       12.4        gain fully useful
         6.0          18.0       15.4        gain fully useful
         8.0          20.0       17.4        gain fully useful
        10.0          20.0       17.4   gain INERT (EIRP capped)
        12.0          20.0       17.4   gain INERT (EIRP capped)
        21.0          20.0       17.4   gain INERT (EIRP capped)
        27.0          20.0       17.4   gain INERT (EIRP capped)

---- 650 km   FSPL = 156.3 dB ----
         0.0          12.0        2.7        gain fully useful
         3.0          15.0        5.7        gain fully useful
         6.0          18.0        8.7        gain fully useful
         8.0          20.0       10.7        gain fully useful
        10.0          20.0       10.7   gain INERT (EIRP capped)
        21.0          20.0       10.7   gain INERT (EIRP capped)
        27.0          20.0       10.7   gain INERT (EIRP capped)
```

**Table 1b — the dish, and how much of it is inert:**

| antenna | G dBi | EIRP_eff dBm | **inert dB** | margin @300 km | margin @650 km |
|---|---:|---:|---:|---:|---:|
| omni / rubber duck | 3.0 | 15.0 | 0.0 | +12.4 | +5.7 |
| small 8 dBi panel | 8.0 | 20.0 | 0.0 | **+17.4** | **+10.7** |
| 0.60 m dish (η 0.60) | 21.4 | 20.0 | **13.4** | +17.4 | +10.7 |
| 0.75 m dish (η 0.60) | 23.3 | 20.0 | **15.3** | +17.4 | +10.7 |
| 1.20 m dish (η 0.60) | 27.4 | 20.0 | **19.4** | +17.4 | +10.7 |

### 1.3 What this does to the design

* The **whole useful 2.4 GHz aperture is 8 dBi**. A **small 8 dBi panel** is link-equivalent to
  any dish and it is aimed to within ~±20° (its beam is ~30°).
* A 0.6–1.2 m dish is **13–19 dB of inert gain**: it does exactly what an 8 dBi panel does, but
  costs ~€95–387 + a €185–246 feed, presents 4–16× the swept area, and needs ~1–8° pointing
  precision — the very thing that forces a closed-loop positioner.
* **Honest counter-case (§6):** 2.4 GHz is a crowded band; a dish's narrow beam and clean
  polarisation *do* reject interference and neighbouring transmitters. If a site is
  interference-limited (not sensitivity-limited), a small dish or a **highly directional panel**
  can still be justified — but justified as an **RF-hygiene** choice, never as a link-closure or
  margin choice. That is the only honest reason left to buy one.

---

## 2. Tier 0 — the ultra-low-cost tier BELOW Tier A

**Definition.** Tier 0 exists **only because of the EIRP-cap finding**. Once the 2.4 GHz side
needs no gain, the 433 LoRa downlink also needs no gain (required −13.7 dBi @650 km), and **no
element left in the station has a beam tighter than ~40°** (Table 4) — so the tracker, the worm
reducers and the encoders all stop being load-bearing.

### 2.1 Tier 0a — "no pointing at all"

| line | low € | high € | source |
|---|---:|---:|---|
| 433 MHz omni / ground-plane (LoRa downlink) | 15 | 40 | `TODO(unverified)` — generic |
| 2.4 GHz omni / rubber-duck (uplink) | 5 | 25 | `TODO(unverified)` — generic |
| mast / tripod, no motors | 30 | 90 | `TODO(unverified)` — generic |
| coax + connectors | 40 | 90 | repo coax class (see §3) |
| **TOTAL** | **90** | **245** | |

**Handles:** the **low-power LR2021 board** in **LoRa** (the long-range mode), both directions,
with no pointing and no moving parts. Margins from Table 2: 433 LoRa **+13.7 dB @650 km**,
2.4 GHz uplink **+5.7 dB @650 km** (omni) or **+10.7 dB** (8 dBi panel).
**Does not handle:** any FLRC mode at range (see §2.3), and it is not a high-rate link.

### 2.2 Tier 0b — "hand-aimed Yagi" (adds F33 FLRC)

| line | low € | high € | source |
|---|---:|---:|---|
| Diamond A-430S10R, **13.1 dBi** 433 Yagi (0.82 m boom) | 69 | 69 | `bom-candidates` A4 **CONFIRMED** |
| 2.4 GHz omni / rubber-duck | 5 | 25 | `TODO(unverified)` |
| manual AZ/EL pan-tilt head + tripod | 30 | 120 | `TODO(unverified)` — consumer photo/video class |
| coax + connectors | 40 | 90 | repo coax class |
| **TOTAL** | **144** | **304** | |

**Handles:** everything Tier 0a does **plus F33 FLRC 2.6 Mbps to 650 km (+5.2 dB)** — with a
**human** pointing the Yagi (its beam is ~40°, i.e. a ±20° pointing tolerance, easily hand-held
for a pass). No motors, no controller, no firmware, no encoder, no anemometer.

### 2.3 The one thing Tier 0 cannot do, stated plainly

Tier 0 is a **LoRa + hand-aimed-F33** station. It **cannot** carry **low-power FLRC at range**:
without the F33, 433 FLRC 2.6 Mbps at 650 km needs **+18.9 dBi** (a ~2.6 m dish) and 650 kbps
needs **+12.4 dBi** — the whole reason the sibling `gain-per-dollar` analysis finds a dish
sweet-spot at all. So:

* **Low-power board → LoRa only** in Tier 0 (fully closed, no pointing).
* **F33 board → FLRC to 650 km** in Tier 0b (hand-aimed), and everywhere in Tier A (auto).

This is the same conclusion the `flrc-max` document reaches from the other direction:
**"pile the gain into the balloon (F33 = +20 dB, free), and the ground dish becomes margin"**
(`ground-station-flrc-max-throughput.md` §3.4).

---

## 3. Re-costed Tier A (no 2.4 GHz dish)

The original Tier A' line items carried a **0.75 m Ku dish (€94.90)** + a **2.4 GHz feed
(€231 incl. clamp)** = **€314.90** of hardware whose entire function is superseded by an
**8 dBi panel (~€15–60)**. Re-costed, line by line:

| line | original € | re-costed € | change | source |
|---|---:|---:|---|---|
| 433 Yagi | 74.50 (A-430S15R 14.8 dBi) | 74.50 | — | `bom-candidates` A5 **CONFIRMED** |
| 2.4 GHz antenna | 94.90 dish + 231 feed = **325.90** | **15–60** (8 dBi panel) | **−266 … −311** | B3 + C2/C6 CONFIRMED → panel `TODO(unverified)` |
| positioner | 429 (DIY P1 printed + NMRV40) | 429 | — | `gain-per-dollar` §1.6 **CONFIRMED** |
| coax 15 m Airborne 10 + N/SMA | 97.50 + 24 | 97.50 + 24 | — | `bom-candidates` §6 **CONFIRMED** |
| **TOTAL** | **≈ 926.90** | **≈ 616–661** | **−266 … −311** | |

**Two equivalent Tier-A builds:**

* **DIY tracker:** €616–685 → uses the sibling's **P1** (€429, NEMA23 3.0 N·m + **NMRV40 20:1
  self-locking worm**, holds 40 N·m).
* **Bought rotator:** €546–615 → a **Yaesu G-450CDC (€359, `bom-candidates` E2 CONFIRMED)** is
  now *more than sufficient*: with **no dish**, the moving wind area is a Yagi's thin lattice plus
  a small panel, far inside the G-450's 0.50 m² mast rating. Before, a dish on a mast needed the
  G-5500DC (€949) or bigger — that step is gone.

**Reconciliation with the previously-stated "~€700".** That figure was quoted for **antenna +
positioner only** (no coax/connectors, and with the cheap 2.4 GHz choice). On that same
antenna+positioner basis the re-cost is **≈ €440–495** (Yagi €74.50 + panel €15–60 + tracker
€429 ≈ €518 low / but with the **used-Ku-dish** path already removed). The *saving* is the same
either way and is the **dish + feed**, on the order of **€265–315**.

---

## 4. Capability table — what each tier actually buys

433 margins are `G_ground − reqG`; **bold** = the tier's limiting case.

| capability | Tier 0a (omnis) | Tier 0b (hand Yagi) | Tier A (auto) |
|---|---|---|---|
| 2.4 GHz uplink @650 km | **+5.7 dB** (omni) / +10.7 (panel) | same | +10.7 (8 dBi panel) |
| 433 LoRa @650 km (low-power, LE +12.15 dBm) | **+13.7 dB** | +26.8 | +28.5 |
| 433 LoRa @650 km (+22 dBm, amateur) | +23.6 | +36.7 | +38.4 |
| 433 FLRC **650 kbps** @650 km (F33) | +11.7 dB (13.1 dBi Yagi) | +11.7 | +13.4 |
| 433 FLRC **2.6 Mbps** @650 km (F33) | −7.9 (**fails**) | **+5.2** | **+6.9** |
| 433 FLRC 2.6 Mbps @650 km (low-power, no F33) | fails (−18.9) | fails (−5.8) | fails (−4.1) |
| unattended / automatic | yes (but LoRa only) | **no — human points** | yes |
| moving parts / firmware | none | none | motors + controller |
| **cost (parts)** | **€90–245** | **€145–305** | **€545–685** |

---

## 5. The lever that makes Tier 0 exist: no tight beam is left

**Table 4 — pointing budget (10 % of HPBW) by element** (script output):

```
element                          G dBi   HPBW deg  10% budget deg             tracker class
2.4 GHz omni                       3.0      360.0            36.0                    (none)
2.4 GHz 0.6 m dish                21.4       14.6             1.5           cheap/open-loop
433 omni                           0.0      360.0            36.0                    (none)
433 small Yagi 10 dBi             10.0       47.0             4.7           cheap/open-loop
433 Yagi 13.1 dBi                 13.1       40.0             4.0           cheap/open-loop
```

Before the EIRP-cap finding, the **0.6 m 2.4 GHz dish** set the station's pointing budget at
**1.5°** — which a printed drive's **0.5–2.0°** backlash cannot meet
(`positioner-lowcost-3dprinted.md` §8), forcing closed-loop encoders, and the dish's 4× swept
area forced a NEMA23+worn-class reducer. **Remove the dish and the tightest element left is the
433 Yagi at ~4°** — *twice as forgiving as the 0.6 m dish ever was* — and a human with a pan-tilt
head, or a €359 Yaesu, both clear it with margin. **The 2.4 GHz dish was the sole cause of the
positioner class.**

---

## 6. Honest gaps, limitations, and the counter-case

1. **The `TODO(unverified)` items are the weak point, and they are all cheap and generic:** the
   2.4 GHz omni/panel, the manual pan-tilt, and the plain mast. They are marked rather than
   guessed (search backends were captcha-gated this session — verified again: Brave 429,
   DuckDuckGo 202, Mojeek captcha, Ecosia 403, eBay 403, wimo/Reichelt search JS-gated). The
   **structure of the answer does not depend on their exact price**: even if the panel and mount
   together were €150, Tier 0a stays under €350 and Tier A under €750.
2. **Tier 0a assumes `G_balloon = 0 dBi`** — the same conservative assumption the repo's
   licence-exempt budget uses. If the balloon's 433 antenna is a poor/lossy whip or the balloon
   tumbles, the ground omni margin erodes; a Yagi (Tier 0b) is the hedge.
3. **Tier 0 needs *some* pointing knowledge even with omnis** — not for gain, but to know the
   balloon is up. That is a *link-budget* non-issue and an *operational* issue (a human, or a
   rotator, has to be watching). Tier 0's "automatic" column means "no pointing hardware", not
   "no operator".
4. **The counter-case to removing the 2.4 GHz dish is interference, not link.** In a
   congested/interference-limited 2.4 GHz site, a narrow dish beam and clean polarisation are
   genuine assets. If the site is interference-limited, a **directional panel or small dish is
   justified on RF-hygiene grounds only** — never on closure or margin (both are already met by
   an 8 dBi panel at the cap).
5. **The 433 FLRC-at-range capability still requires the F33** (+33 dBm, amateur-licence). This
   document does not resolve the licence/airborne-SRD question (`ADR-039` open item (a)) — it is
   inherited and remains the binding constraint on the "F33 to 650 km" rows.
6. **Nothing here is a purchase.** No part is ordered, no fab is touched, no BOM is changed.

---

## 7. Open items (every `TODO(unverified)` in one place)

1. `TODO(unverified)` — price/part-number of a **2.4 GHz 8 dBi panel** and a **2.4 GHz omni**
   (generic Wi-Fi/ISM class). Required to close Tier A's 2.4 GHz line and Tier 0a's uplink.
2. `TODO(unverified)` — a **manual AZ/EL pan-tilt head + tripod** with a stated load rating
   (Tier 0b). Consumer video-tripod class; rating must be checked against the Yagi's wind load.
3. `TODO(unverified)` — a **433 MHz omni / ground-plane** with a stated gain (Tier 0a). The
   licence-exempt LoRa margin is computed at 0 dBi; confirm the part meets it.
4. `TODO(unverified)` — the **exact ERC Rec 70-03 Annex 1 row** for 2400–2483.5 MHz (the 20 dBm
   EIRP cap) — inherited from `LINK-BUDGET-LICENCE-EXEMPT.md` §5.
5. `TODO(unverified)` — the **2.4 GHz FLRC sensitivity row** (would only matter if a high-rate
   2.4 GHz uplink were ever required; it is not — the uplink is LoRa-class, so this does **not**
   change any conclusion here).
6. **Not modelled:** the ground *radio* (LR2021 breakout / SDR front end, host, software) — out of
   scope in all the sibling documents and here, so the costs stay comparable.

---

## 8. Independent consultant verdict (verbatim, model named)

See §8.1 — the companion figure
`docs/analysis/figures/tier0-eirp-capped-uplink.png` was put to the fleet visual consultant
(`scripts/fleet/visual_consult.py`, pinned model `gpt-6-astra`) with `--emit-evidence`. The
verdict, the served model, and any refutation are recorded there **verbatim, not paraphrased**.

### 8.1 Verdict

*(filled in immediately after the consultation — see the transcript block at the end of this
section once the consultant returns.)*

---

## 9. Method / reproduction

```bash
python3 docs/analysis/tier0_accessible_model.py      # prints Tables 1, 1b, 2, 3, 4 verbatim
```

* **Sources.** Sensitivities and TX powers: Semtech LR2021 datasheet (repo copies, see
  `ground-station-lowpower-link-and-shared-dish.md` §1). F33 +33 dBm: `ADR-044` /
  `RANGE-THROUGHPUT-PLAN.md`. Regulatory caps and the ADR-037 balloon antenna:
  `LINK-BUDGET-LICENCE-EXEMPT.md` §0. Prices: `ground-station-bom-candidates.md` (**CONFIRMED**
  rows only). Positioner menu: `ground-station-gain-per-dollar.md` §1.6.
* **Supersedes:** nothing. **Relates to:** `design/positioner-lowcost` (ADR-067),
  `design/ground-station-flrc-max` (ADR-066), `design/gain-per-dollar` (ADR-068).
* **Companion ADR:** `docs/adr/069-*` (Proposed) — *do not treat as decided.*
