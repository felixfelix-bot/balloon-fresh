# ADR-041 — v9 RF front end under the ≤ 10 mW licence-exempt regime: gain on the ground, F33 internal LNA in circuit, no balloon FEM

- Status: **Proposed** — the reopened decision is settled here with link-budget
  arithmetic from the repo's own tool; the *text* has not been accepted by a human.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-adr (Hermes agent), settling the reopened ADR-037 D2/D3 question
  under the operator's 2026-10-07 licence-exempt instruction.
- Related: **ADR-037** (`docs/adr/037-mcu-s3-no-fem.md`, branch `adr/mcu-s3-no-fem`,
  tip `144c8191` — **reopened in part here**, see §"Relationship to ADR-037"),
  ADR-005 (SKY66112 FEM, superseded in part), ADR-006 (supercap power, stale load
  list), ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, the 433-TX /
  2.4-RX band split — the per-direction structure this ADR uses), ADR-035 (TDM
  schedule, unaffected), **ADR-039** (licence-exempt 433 design point, being written
  concurrently), **ADR-040** (`docs/adr/040-v9-radio-site-optionality.md`, the
  radio-site optionality decision — interaction stated in §6, **not resolved for
  them**).
- Companion evidence: `docs/LINK-BUDGET-LICENCE-EXEMPT.md` (every number sourced,
  tool output quoted verbatim, TODOs listed).

> Numbering note: **041** taken explicitly. Next-free-number check run 2026-10-07 on
> `git log --all --name-only -- 'docs/adr/03[6-9]*' 'docs/adr/04[0-9]*'`: 036
> (`adr/energy-policy`), 037 (`adr/mcu-s3-no-fem`), 038 (`adr/wifi-bt-disabled`),
> 040 (`adr/v9-radio-site-optionality`) are claimed; **039 is being written
> concurrently by another worker** (licence-exempt 433 design point, per ADR-040's
> own numbering note) and **040 is claimed by the radio-site worker**. No `041-*`
> file exists on any branch inspected. 041 is free and taken here.

---

## Context

The operator has chosen to operate **licence-exempt at 433.05–434.79 MHz at
≤ 10 mW ERP**. That cap binds the **balloon's transmitter** — the 433 MHz downlink.
ADR-037 D2/D3 omitted the SKY66112 FEM partly on the strength of a 2 W-era link
margin ("+21.4 dB without an LNA") that existed only because the ground station
radiated 37 dBm EIRP. Removing that assumption **reopens the front-end question**,
and this ADR settles it **per direction and per band**, because the two directions
are not symmetric:

- The **10 mW ERP cap binds only the balloon's 433 MHz TX**. Ground-station receive
  gain (10–15 dBi 433 Yagi) and ground receive LNAs are **unregulated and add no
  balloon mass**.
- The **2.4 GHz uplink is transmitted from the ground**, where licence-exempt allows
  **100 mW EIRP** (20 dBm) — *not* 10 mW. It therefore does **not** take the same
  27 dB hit the 433 downlink takes.

All arithmetic below is `tools/link_budget.py` output, quoted verbatim in
`docs/LINK-BUDGET-LICENCE-EXEMPT.md`; sensitivities are the module datasheet figures
already cited in ADR-029/037 (−136/−124 dBm at 2.4 GHz; −143 dBm sub-GHz).

---

## Decision

### D1 — WHICH direction binds: the 2.4 GHz uplink, not the 433 downlink

**433 MHz downlink (balloon→ground), 10 mW ERP.** Tool output
(`--freq 433 --sf 12 --bw 125 --tx 10 --tx-ant 0 --rx-ant 12 --cable-loss 0 --dist 300`):

```
  EIRP:           10.0 dBm
  FSPL:           134.7 dB
  RX Power:       -112.7 dBm
  Link Margin:    24.3 dB OK        (tool LoRa table, SF12/BW125 = -137 dBm)
```

Against the bare LR2021's sub-GHz sensitivity **−143 dBm** (`docs/inventory.md`):
margin = **+30.3 dB**. The 23 dB TX cut (33 → 10 dBm) is more than recovered by the
**14.9 dB lower path loss at 433 vs 2.4 GHz** (134.7 vs 149.6 dB) plus **12 dBi of
ground Yagi gain**. A 15 dBi Yagi gives +27.3 dB. **The 433 downlink closes with
large margin at 10 mW ERP — it is not the binding direction.**

**2.4 GHz uplink (ground→balloon), 100 mW EIRP (20 dBm), balloon RX 10 dBi.** Tool
output (`--freq 2400 … --tx 20 --tx-ant 0 --rx-ant 10 --cable-loss 0`):

```
  EIRP:           20.0 dBm
  FSPL:           149.6 dB
  RX Power:       -119.6 dBm
  Link Margin:    17.4 dB OK        (tool, -137)
```

Against the module sensitivities:

| Balloon RX front end | Sensitivity | Margin | Verdict |
|---|---|---|---|
| F33 internal LNA in circuit (DIO5 HIGH) | −136 dBm | **+16.4 dB** | comfortable |
| F33 internal LNA bypassed (DIO5 LOW) | −124 dBm | **+4.4 dB** | **thin** |
| Same, 6 dBi balloon antenna (no LNA) | −124 dBm | **+0.4 dB** | **effectively fails** |

**The 2.4 GHz uplink is the binding direction**, and it binds only through the
balloon's *receiver* sensitivity, not through any balloon transmitter cap.

### D2 — The external SKY66112 FEM stays OFF the balloon (ADR-037 D2 stands)

The SKY66112-11 is **not** fitted on v9, under the licence-exempt regime, for either
direction:

- **433 downlink:** no balloon-side amplification is needed at all — the link closes
  at +24.3/+30.3 dB with ground gain alone (D1). The F33's PA is throttled to
  ≤ 10 mW ERP, so its 2 W capability is unusable in this regime (consistent with
  ADR-040 D2 item 3, "the HP leg is dead weight under the licence-exempt regime").
- **2.4 GHz uplink:** the external SKY66112 LNA (+14 dB / 1.8 dB NF, ADR-005) is
  **not needed on top of the F33's internal LNA** — the same reasoning ADR-037 D3
  used at 2 W: an external LNA in front of an already-low-NF module front end cannot
  improve a system already at its own floor. The internal LNA's −136 dBm is the
  citable figure; the external LNA's incremental benefit is `TODO(unverified)` and
  is not needed to close the link.

**Mass consequence: 0 g** — no FEM, no extra LNA, no extra passives, no TX_EN/RX_EN
GPIOs. The front-end decision adds **no mass** to v9 under this regime.

### D3 — What IS required: the F33's internal 2.4 GHz LNA in circuit (DIO5 HIGH)

The one front-end requirement that survives is a **firmware/arbiter policy**, not a
part: **the F33's internal 2.4 GHz LNA must be in circuit (DIO5 HIGH) whenever the
2.4 GHz RX window is armed.** Without it the uplink margin is **+4.4 dB** (10 dBi
balloon antenna) or **+0.4 dB** (6 dBi) — below any sane fade margin for a 300 km
slant path. With it, +16.4 dB.

- This makes ADR-029 D2's "`DIO5` is the 2.4 GHz LNA control and must default HIGH"
  a **link-budget requirement under licence-exempt**, not merely an energy trade
  (DIO5 LOW saves 33 mA of RX current but costs 12 dB — the 12 dB is now load-bearing).
- ADR-035's arbiter owns DIO5 state (its D4 invariant: any radio not in its slot is
  *disabled*); this ADR adds: **DIO5 LOW during the RX slot is a link-budget bug**,
  not just an energy optimisation. `TODO(unverified)`: a bench measurement of the
  2.4 GHz RX floor with DIO5 LOW vs HIGH at 300 km-equivalent attenuation would pin
  the real margin split.

### D4 — Ground-station requirements (the other half of the decision)

The licence-exempt regime moves the RF burden to the ground, so the decision is only
half-recorded without naming the ground side:

| Ground asset | Requirement | Source of number |
|---|---|---|
| 433 RX antenna | 10–15 dBi Yagi (12 dBi assumed; 15 dBi shown) | Brief 10 / ADR-034; `TODO(unverified)`: named part datasheet |
| 433 RX LNA | Optional — margin already +24.3 dB without one; a ground LNA adds fade robustness, not feasibility | this ADR's arithmetic |
| 2.4 GHz TX | **≤ 100 mW EIRP total** — the ground may NOT combine a 27 dBm radio with a 12 dBi Yagi (37 dBm EIRP) as ADR-037's baseline assumed; TX power must back off so TX + ant − cable ≤ 20 dBm | ERC/EU SRD 2.4 GHz cap (Brief 10); `TODO(unverified)`: exact Annex 1 row |
| 2.4 GHz TX antenna | High-gain **is** allowed at 2.4 GHz as long as EIRP ≤ 20 dBm — but it buys nothing on the uplink margin unless TX power backs off to compensate; the binding term is EIRP, not antenna gain | arithmetic above |

**The ADR-037 baseline configuration (27 dBm + 12 dBi = 37 dBm EIRP) is not
legal licence-exempt.** The ground station must be re-programmed to ≤ 20 dBm EIRP,
and the balloon's internal LNA (D3) is what pays for that 17 dB.

### D5 — Corrections to the brief's framing (recorded, not silently propagated)

The seed brief stated: *"Dropping EIRP to 10 dBm costs 27 dB → +6.4 dB with LNA,
−5.6 dB without, i.e. the no-LNA case FAILS."* Verified and **corrected**:

- The +6.4 / −5.6 dB figures **are** reproducible (§1d of the companion table: RX
  power −129.6 dBm vs −136/−124 dBm) — **but only under a 10 dBm EIRP assumption**,
  which mis-applies the 433 MHz 10 mW ERP cap to the 2.4 GHz uplink.
- The 2.4 GHz uplink is ground-transmitted and capped at **100 mW EIRP (20 dBm)**;
  the correct drop is **17 dB** (37 → 20 dBm), giving **+16.4 dB with the internal
  LNA / +4.4 dB without** — the no-LNA case **does not fail**, it becomes **thin**.
- The case that genuinely fails is **6 dBi balloon antenna + LNA bypass:
  +0.4 dB** (§1c) — which is why D3 (LNA in circuit) is the surviving requirement.

---

## Consequences

1. **ADR-037 D2 stands; D3's verdict is revised, not reversed.** See
   §"Relationship to ADR-037" — the FEM stays omitted, but the justification changes
   from "+21.4 dB of slack" to "+16.4 dB *with the internal LNA in circuit*, and
   the LNA is now required".
2. **Ground-station change required.** The 2.4 GHz ground TX must be reduced from the
   ADR-037 baseline 37 dBm EIRP to ≤ 20 dBm EIRP (D4). This is a ground-station
   configuration change, not a balloon change.
3. **Firmware policy change (normative).** DIO5 must be HIGH in the 2.4 GHz RX slot
   (D3); the arbiter (ADR-035 D4) owns it. Driving DIO5 LOW for energy saving during
   an armed RX window is a link-budget regression.
4. **No mass, no BOM, no schematic change to v9.** The decision is satisfied by
   module choice + ground configuration + firmware policy.
5. **ADR-006's stale SKY66112 reference remains stale** (recorded in ADR-037
   consequence 3; not re-edited here — another worker is adding pointers to ADR-006
   right now).
6. **The 2 W PA leg of ADR-040's Site-A variant is dead weight in this regime**
   (see §6), consistent with ADR-040 D2 item 3's own statement.

---

## Relationship to ADR-037 (reopened in part, settled here)

ADR-037 D3 computed one direction (2.4 GHz RX) at one EIRP (37 dBm) and concluded
"adequate without the FEM" with +21.4 dB of no-LNA slack. Under the licence-exempt
regime the 37 dBm EIRP baseline is illegal and the slack shrinks by 17 dB. This ADR:

- **Keeps** D2 (FEM omitted) — confirmed on both directions (D2 above).
- **Revises** D3's *justification*: the margin without the LNA is **+4.4 dB, not
  +21.4 dB**; the comfortable margin requires the F33's **internal** LNA in circuit.
- **Does not touch** D1 (MCU = ESP32-S3) — unaffected by the power regime.
- **Pending-pointer conflict:** another worker is concurrently adding pointers to
  `docs/adr/037-mcu-s3-no-fem.md` and `docs/adr/006-supercapacitor-power.md`; this
  ADR deliberately contains its relation-to-ADR-037 text **here only** and does not
  edit those files. When the pointer work lands, ADR-037's own "Related" line should
  gain a back-reference to ADR-041 (the 37 dBm baseline it quotes is superseded for
  licence-exempt flight by this ADR's 20 dBm EIRP cap).

---

## Interaction with ADR-040 (radio-site optionality) — stated, not resolved

ADR-040 gives v9 two back-side radio sites: **Site A** accepts either the bare LP
`LoRa2021` or the HP `LoRa2021F33-2G4` (mutually exclusive); **Site B** is LP-only;
default population is **LP at both sites**. This ADR's front-end decision interacts
with ADR-040 in three specific ways:

1. **A 2.4 GHz FEM/LNA concerns the RX path; the site slots concern which module is
   fitted.** This ADR requires *a 2.4 GHz RX front end at −136 dBm-class
   sensitivity* on the balloon. ADR-040's Site-A choice determines **which module
   provides it**: the F33 (internal LNA, DIO5-controlled, −136 dBm) or a bare
   `LoRa2021` (−137 dBm per `docs/inventory.md`, no DIO5 LNA control). Both meet the
   requirement — so **the front-end decision does not constrain ADR-040's Site-A
   choice**, and ADR-040's choice does not reopen this ADR.
2. **The DIO5 policy (D3 here) is F33-specific.** If Site A is populated LP (ADR-040
   D2's default), D3's DIO5 rule is void: the bare `LoRa2021` exposes DIO7/8/9 on
   pins 15–17 (`docs/inventory.md`) and its pin 18 is IRQ — the DIO5 RF-switch/LNA
   control that carries the −136 vs −124 dBm split is an **F33 internal routing**
   (ADR-029 D2 "`DIO5` is the 2.4 GHz LNA control"; ADR-040 D2 item 1 "a 2.4 GHz LNA
   enable on DIO5 … LOW costs 12 dB"), not a bare-module feature. The bare module's
   −137 dBm stands on its own, margin **+17.4 dB** (tool) at 10 dBi. If Site A is
   populated HP (F33), D3 applies verbatim. **The arbiter must know which part is
   fitted** — which is exactly ADR-040's matrix's job
   (`docs/V9-RADIO-SITE-MATRIX.md`), not this ADR's.
3. **The HP leg's 2 W PA is unusable under this regime** (10 mW ERP cap), matching
   ADR-040 D2 item 3. This ADR adds the *quantitative* statement: the 2 W → 10 mW
   cut costs 23 dB of downlink margin, and the link still closes at +24.3 dB — so
   **dropping the HP leg costs nothing on the 433 downlink** under licence-exempt.
   ADR-040 keeps the HP option for licensed/ground use; that use is outside this
   ADR's regime and is not assessed here.

**Not resolved for ADR-040:** whether Site A is populated LP or HP for a given
flight board, and what `docs/V9-RADIO-SITE-MATRIX.md` should say per configuration —
those remain ADR-040's decisions. This ADR only states the RX-path requirement the
fitted module must meet (−136 dBm-class at 2.4 GHz) and the F33-specific DIO5 rule.

---

## What would falsify this

- A sourced ERC Rec 70-03 Annex 1 row showing the 2.4 GHz wideband-data cap is
  **below 100 mW EIRP** for this modulation/duty class — would reduce the uplink
  margin accordingly and could push the no-internal-LNA case negative.
- A bench measurement showing the F33's DIO5-HIGH sensitivity is materially worse
  than the datasheet −136 dBm at the flight temperature (−44…−60 °C crystal-drift
  risk is recorded in `docs/LR2021-LESSONS-2026-09.md` for plain modules).
- A determination that the balloon's 433 antenna cannot be ≈0 dBi (e.g. a structural
  constraint forcing a lossy feed) — would eat into the +24.3 dB downlink margin.
- ADR-039's licence-exempt design point landing with a **different 2.4 GHz cap**
  than Brief 10's 100 mW EIRP — this ADR's §1b/§1c margins would need recomputation.

---

## Next-free-number check (recorded)

```
git log --all --oneline --name-only -- 'docs/adr/03[6-9]*' 'docs/adr/04[0-9]*'
  → 036 (adr/energy-policy), 037 (adr/mcu-s3-no-fem), 038 (adr/wifi-bt-disabled),
    040 (adr/v9-radio-site-optionality) claimed; 039 concurrent (per ADR-040's
    numbering note); no 041-* file on any branch inspected.
```

041 is free on every branch inspected and is taken here.
