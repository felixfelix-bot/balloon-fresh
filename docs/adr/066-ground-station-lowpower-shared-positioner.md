# ADR-066 — Ground station for the low-power LR2021 433 MHz downlink: share the *positioner*, not the *reflector*; LoRa carries the far link, FLRC does not

- **Status:** **Proposed** — the analysis is complete and cited; the *text* has not been
  accepted by a human.
- **Date:** 2026-10-08
- **Decision owner:** Felix (operator)
- **Author:** Hermes subagent (design analysis), per the operator's 2026-10-08 instruction
  that the 433 downlink uses the **LOW-POWER LR2021** (not the F33 / 2 W / 33 dBm) and that
  the ground station should "do the heavy lifting".
- **Related:** ADR-039 (licence-exempt 433 design point — power cap this ADR reconciles with),
  ADR-041 (RF front end, no balloon FEM), ADR-034 (433 TX / 2.4 GHz RX band split),
  ADR-037 (FEM omitted, reopened by ADR-041), ADR-029 (`LR2021` module), ADR-035 (TDM schedule).
- **Companion evidence:** `docs/analysis/ground-station-lowpower-link-and-shared-dish.md`
  (two-modulation gain table; every sensitivity/power is a datasheet value with a table
  number and a local citable PDF; research findings with URLs; consultant verdict recorded).
  Repro: `python3 docs/analysis/ground_station_lowpower_link_model.py`.
- **Consulted:** fleet visual consultant, served model **`gpt-6-astra`** — verdict
  **CONFIRM** (verbatim in the analysis §9). A visual consult is not a code review and does
  not satisfy the ADR-010 review gate.
- **Numbering note:** `066` taken explicitly. `scripts/adr_next_number.py` → `66`, exit 0,
  and no `docs/adr/066-*` file exists on any inspected branch (last allocated: `065`).
  Do not hand-pick; a later ADR re-runs the script.

---

## Context

The 433 MHz downlink no longer carries an F33 (2 W / +33 dBm). It carries the **low-power
LR2021**, whose sub-GHz PA delivers **+19…+22 dBm** (datasheet Table 3-22, `TXOPLF`;
programmable down 31.5 dB in 0.5 dB steps). The operator's intent is to buy margin with
**ground-station antenna gain** rather than balloon transmit power.

Two facts make this a decision worth recording, and both were **reconciled** rather than
assumed:

1. **The repo's committed −143 dBm figure is a *LoRa* number, not FLRC.** Confirmed three
   ways this session: `docs/inventory.md` ("SF12/62.5kHz Sub-GHz"), Semtech LR2021
   datasheet v2.2 **Table 3-17** (`LORA_SUB_62_SF12 = −143 dBm`), and the NiceRF LoRa2021
   Module Datasheet V1.3 ("−143 dBm @ BW=62.5 kHz, SF=12"). Sub-GHz **FLRC** is a
   completely different number: **−107 dBm at 650 kbps** (datasheet **Table 3-12**) —
   **≈ 36 dB worse**. Any budget that pairs an FLRC far-link plan with the −143 dBm figure
   is 36 dB optimistic.

2. **The licence-exempt cap sits below the chip's power class.** The committed design point
   (ADR-039 / ADR-041) caps the balloon 433 transmitter at **10 mW ERP with an integral
   antenna = +12.15 dBm EIRP**, which is **below** the operator's own +13 dBm low end. The
   +13…+22 dBm class is only realisable under the amateur licence. The conclusion below
   holds in **both** regimes.

The deciding calculation is `required_G_ground = S_dBm + FSPL − P_tx − G_balloon`, at
**650 km** (radio horizon from ~30 km), `FSPL(433.05 MHz) = 141.4 dB`, `G_balloon = 0 dBi`:

| Modulation | S (dBm) | req. ground gain @ +22 dBm | @ +13 dBm | antenna class implied |
|---|---:|---:|---:|---|
| LoRa SF12 / BW62.5 kHz | −143 | **−23.6** | −14.6 | **any** (omni closes, 14–24 dB margin) |
| LoRa SF12 / BW125 kHz | −141.5 | −22.1 | −13.1 | any (Yagi = 24–34 dB margin) |
| FLRC 650 kbps | −107 | **+12.4** | +21.4 | Yagi at chip max (0 margin); **dish** at low power |
| FLRC 1.04 Mbps | −105 | +14.4 | +23.4 | **dish** |
| FLRC 2.6 Mbps | −100.5 | **+18.9** | **+27.9** | **dish (and a 3 m dish only just, for the middle of the range)** |

**LoRa's required ground gain is *negative*** — an isotropic 433 antenna already closes the
650 km link with 12–28 dB margin. The ground antenna buys *fade margin*, not closure. FLRC
requires **positive** ground gain that a Yagi cannot supply except at the single best point.

---

## Decision

1. **The 433 downlink uses the low-power LR2021** (bare chip, ≤ +22 dBm sub-GHz, no
   external 2 W PA). Recorded as the operator's decision; consistent with the datasheet.

2. **The ground station shares ONE az/el positioner, not one reflector.** Two separate
   antennas ride the same positioner:
   * a **Ku-band offset dish** for the **2.4 GHz uplink** (over-qualified: ~22–27 dBi,
     surface accuracy with ≥5× margin, offset geometry that removes feed blockage;
     documented reuse path replaces the Ku LNB with a 2.4 GHz feed matched to the dish f/D);
   * a **separate 433 MHz antenna** (a 7-element Yagi, 12–15 dBi) **boresighted beside the
     dish aperture** — not across the 2.4 GHz beam.
   Blockage of a Yagi beside the aperture is ≈ 0.1 dB (area ratio); pointing is shared
   because the Yagi's ~40–50° beam is the forgiving element and the dish does the tight
   pointing.

3. **The 433 antenna is sized for the LoRa downlink, not for FLRC.** Its job is margin on
   the long link, not closure.

4. **LoRa is the far-link mode; FLRC is a close-range, high-rate mode.** This is now an
   explicit, recorded constraint (it already matched `docs/link-budget.md`: "FLRC @ 1.3 Mbps
   … ~25–30 km … perfekt fuer direkten Ueberflug"). **FLRC must not be required on the
   650 km link.**

5. **Rejected alternatives** (with the reason, not by preference):
   * a single **dual-band 5.5:1 feed** — no such product/build was found, and the physics
     forbids it (one feed cannot illuminate ±40–53° at 2.4 GHz and the much wider rim angle
     at 433 MHz simultaneously; a 2.4 GHz λ/2 element is only 0.09 λ at 433 MHz);
   * a **dichroic / FSS subreflector** — real technique, wrong scale (precision subreflector,
     dual foci);
   * reusing the **reflector** at 433 MHz — a Ku dish gives only ~0–12 dBi at 433 MHz, and a
     coarse 433 mesh (λ/10 = 69 mm) cannot also serve 2.4 GHz (λ/10 = 12.5 mm), so one
     reflector cannot serve both bands.

---

## Consequences

1. **No 433 MHz dish is built.** The Yagi is a fraction of the mass, wind load, and cost,
   and needs no second pointing system beyond boresight.
2. **The far link depends on LoRa.** If a future requirement demands **FLRC at 650 km** —
   any rate at **≤ +19 dBm**, or any rate **≥ 1 Mbps at any power** — this ADR is
   **reopened**, because the 433 antenna then needs **≈ +19 to +28 dBi** (a ~2.7–3.0 m dish
   or a large array). That is the single, named tripwire.
3. **Gain on the ground is preserved as margin**, not spent on closure: LoRa at 650 km
   closes with a 0 dBi balloon antenna and a 0 dBi ground antenna. The Yagi converts that
   into ~+24 to +40 dB of link margin against polarisation, pointing, and atmospheric loss.
4. **The +13…+22 dBm assumption is regulatory-bounded.** Under licence-exempt, the balloon
   is clamped to ≤ +12.15 dBm EIRP; the higher rows are amateur-licence-only. The decision
   is unchanged either way.
5. **No procurement follows from this record** — it is a design decision only.

---

## Open items (not assumed)

- **`TODO(unverified)`** 433 MHz-specific FLRC sensitivity row (915 MHz datasheet values
  used; the 36 dB LoRa/FLRC gap dwarfs any band-to-band difference).
- **`TODO(unverified)`** a documented/purchasable single 433/2400 dual-band feed — "not
  found" this session, not "proven not to exist".
- **`TODO(unverified)`** measured 433 feed-mismatch loss and RMS surface accuracy of the
  candidate Ku dish (inherited from `dualband-single-dish.md`).
- **`TODO(unverified)`** ADR-039 item (a): licence-exempt SRD **airborne**-use grey area.
- 650 km at ~30 km is slightly beyond the geometric horizon (618 km) but within the
  standard 4/3-Earth refraction horizon (~714 km); taken as given.

---

## Relation to other ADRs

- **ADR-039 / ADR-041** — this ADR consumes their power cap and link budget; it does not
  change them.
- **ADR-034 / ADR-035** — the band split and TDM schedule this ADR's two-antenna station
  serves.
- **ADR-029** — the LR2021 module; this ADR assumes the bare/low-power variant, not the F33.

---

## For future sessions

**One-line rule:** share the **positioner**, not the **reflector**; put the Ku dish on
2.4 GHz and a boresighted 433 Yagi beside it; make **LoRa the far-link mode** — if FLRC is
ever required at 650 km, the 433 antenna must become a ~2.7–3.0 m dish and this ADR reopens.

**Files:** analysis `docs/analysis/ground-station-lowpower-link-and-shared-dish.md`;
model `docs/analysis/ground_station_lowpower_link_model.py`; figure
`docs/analysis/render_lowpower_link_figure.py` → `docs/analysis/assets/lowpower-link-verdict.png`.

**Reproduce:** `python3 docs/analysis/ground_station_lowpower_link_model.py`.

**Do not re-derive the −143 dBm figure as FLRC.** It is LoRa SF12/BW62.5 kHz (Semtech
datasheet v2.2 Table 3-17; NiceRF V1.3). FLRC 650 kbps is −107 dBm (Table 3-12).
