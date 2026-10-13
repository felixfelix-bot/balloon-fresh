# Licence-Exempt Design Point — 433 MHz Downlink vs 2.4 GHz Uplink

Status: **proposed / design point of record for the licence-exempt operating mode.**
Related ADRs: [ADR-039](adr/039-licence-exempt-433-design-point.md), ADR-034/035/036/037,
[ADR-041](adr/041-*.md) (RF front-end link budget, branch `adr/rf-frontend-licence-exempt`
at `a419e7d`), ADR-005.

## 1. Decision (authority — recorded, not re-litigated)

The balloon operates **licence-exempt** in the 433.05–434.79 MHz SRD band at
**≤10 mW ERP** with an **integral antenna**, instead of operating under the operator's
German DE amateur licence. This decision is taken as given; this document records its
consequences and does not re-open it.

## 2. Corrected premise (the operator's original premise was WRONG)

The operator's original premise was:

> "Transmitting below 1 W is compliance-free."

**This is wrong and is recorded here as corrected.**

- The German **licence-exempt cap at 433.05–434.79 MHz is ~10 mW ERP with an integral
  antenna**, not 1 W.
- Germany **ended licence-free 433 MHz remote-control use in 2008**; the band is now SRD
  (non-specific short-range device) use, not a free-for-all remote-control band.
- The **"1 W" figure is the US 915 MHz Part 15 rule**, a different band and a different
  jurisdiction. It does not apply here.

Any design that assumed 1 W headroom at 433 MHz is unsafe as a compliance basis. The
binding budget is ~10 mW ERP.

## 3. Per-band table

| Band | Permitted power | Duty-cycle allowance | Antenna condition | Citation |
|---|---|---|---|---|
| **433.05–434.79 MHz** | ~**10 mW ERP** | duty-cycle limited (see §7); the design uses ~1.7 % | **Integral antenna required** | ERC/REC 70-03 Annex 1 (primary); `docs/SOLAR-PIN-REGULATORY.md` @ `bc50dacd` (in-repo secondary) — **exact Annex-1 table row `TODO(unverified)`** |
| **2400–2483.5 MHz** | **100 mW EIRP** | no duty-cycle cap applied by this design | integral / non-integral per national implementation | ERC/REC 70-03 Annex 1 (primary); `docs/SOLAR-PIN-REGULATORY.md` @ `bc50dacd` — **exact row `TODO(unverified)`** |
| **868 MHz** | — | — | — | **Not used by this design.** Stated explicitly: the design uses 433 MHz (downlink) and 2.4 GHz (uplink) only. |

> **Provenance note.** Only the 433 = ~10 mW ERP / integral-antenna and 2.4 GHz =
> 100 mW EIRP figures are asserted here. The precise ERC/REC 70-03 Annex 1 table row
> text has **not** been read in this session and is marked `TODO(unverified)` until
> someone opens the recommendation and quotes the row. Do not cite the row text as
> verified until then.

## 4. Link budget — the binding direction is the 2.4 GHz UPLINK

Result already landed and verified as **ADR-041** (branch `adr/rf-frontend-licence-exempt`,
commit `a419e7d`):

- The **BINDING direction is the 2.4 GHz uplink (ground-transmitted)**, *not* the 433
  downlink.
- The **10 mW ERP cap binds only the balloon's 433 TRANSMITTER**.
- **433 downlink at 10 mW ERP closes at +24.3 dB** with a 12 dBi ground Yagi — ground gain
  covers it, **no balloon-side FEM needed**.
- **2.4 GHz uplink at 100 mW EIRP (20 dBm, not 10 mW)**:
  - **+16.4 dB with the F33 internal 2.4 GHz LNA (DIO5 HIGH)**
  - **+4.4 dB without the LNA**
  - **+0.4 dB with a 6 dBi antenna**

### 4.1 Superseded framing (explicitly corrected)

An earlier framing stated:

> "+6.4 dB with LNA / −5.6 dB without = the no-LNA link FAILS"

**This mis-applied the 433 10 mW cap to the 2.4 GHz uplink and is SUPERSEDED.** The 2.4 GHz
uplink is allowed 100 mW EIRP, i.e. **20 dBm, not 10 mW**. The correct drop on the uplink
is **17 dB**, and **no-LNA is thin (+4.4 dB), not failed**.

Cross-references: `docs/adr/037-*.md`, `docs/adr/005-*.md`.

## 5. Ground-gain recovery (the recommendation)

The ERP cap binds **only the balloon's transmitter**. Ground-side **receive gain**
(a 10–15 dBi 433 Yagi) and **receive-side LNAs are unregulated** and add **no balloon mass**.

Arithmetic for the 433 downlink at 10 mW ERP:

```
Balloon 433 TX, 10 mW ERP (cap)                 -> fixed ceiling
Ground RX antenna: 12 dBi Yagi                  -> +12 dB recovered on the ground
Ground RX LNA / feed improvement                -> additional margin, unregulated
------------------------------------------------
Observed 433 downlink margin (ADR-041)          -> +24.3 dB
```

That is: moving the downlink gain to the **ground** recovers the loss the ERP cap
imposes on the balloon, because only the transmit-side ERP is regulated. The **2.4 GHz
uplink is ground-transmitted**, where licence-exempt allows **100 mW EIRP**, so it does
**not** take the same hit — its binding constraint is the receiver, not the regulator.

## 6. Hard requirement — firmware clamp + production test

- Firmware **MUST clamp TX to ≤10 mW ERP**.
- There **MUST be a production test that proves it**: **conducted power = 10 mW minus
  antenna gain**.
- Note the consequences for the radio front end:
  - the **2 W F33 PA is over-limit** and unusable in licence-exempt mode;
  - the **bare module's own 22 dBm is also over-limit** for 433 (22 dBm ≈ 158 mW ≫ 10 mW ERP).

The clamp and its production test are not optional and are a gating requirement for flight
in licence-exempt mode.

## 7. Duty cycle

Actual beacon duty cycle is **~1.7 %** — **1 s per 60 s** — against the duty-cycle allowance
of the band. This stays comfortably inside a 1 %/10 %-class SRD duty-cycle allowance; the
exact allowance value is part of the `TODO(unverified)` Annex-1 row (§3).

## 8. What this decision REMOVES and what REMAINS

**Removed** (these were amateur-licence obligations, not licence-exempt obligations):

- the **callsign frame**;
- the **plain-telemetry / no-encryption duties**.

Cross-reference: `docs/regulatory-amateur` — this becomes the **REJECTED-ALTERNATIVE
record**. **Do NOT delete it.**

**Remains** (these are licence-exempt obligations):

- **non-interference** (must not cause harmful interference);
- **no protection from interference** (must accept interference from others);
- **duty cycle** (§7);
- the **antenna / ERP cap** (§3, §6).

## 9. Open items — flagged, never assumed

- **(a) Licence-exempt SRD AIRBORNE use is a grey area.** The ERC/REC 70-03 framework is
  written for **short-range ground use**; airborne use is not clearly addressed. This
  **needs a national-regulation check before flight.**
- **(b) Whether a balloon-side LNA is still needed** once the ground carries the
  receive gain (ADR-041 says the 433 downlink closes on ground gain alone; this does not
  by itself settle the 2.4 GHz uplink receive chain).
- **(c) Sub-GHz FLRC availability on the F33** — unconfirmed.

## 10. Citation policy used in this document

Only what was actually read is cited as verified. The ERC/REC 70-03 Annex 1 table **row
text is marked `TODO(unverified)`**; `docs/SOLAR-PIN-REGULATORY.md` @ `bc50dacd` is cited
as the in-repo secondary source, and ADR-041 @ `a419e7d` as the landed link-budget source.
