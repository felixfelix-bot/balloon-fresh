# ADR-039 — Licence-Exempt 433 MHz Design Point

- **Status:** Proposed
- **Date:** 2026-10-07
- **Related:** ADR-034, ADR-035, ADR-036, ADR-037, ADR-041 (`adr/rf-frontend-licence-exempt` @ `a419e7d`), ADR-005
- **Supersedes:** nothing. **Corrects:** the operator's "below 1 W is compliance-free" premise.

## Context

The balloon payload must transmit. Two routes exist: operate under the operator's German
DE **amateur licence**, or operate **licence-exempt** in the 433.05–434.79 MHz SRD band.

The operator's original premise was that *"transmitting below 1 W is compliance-free."*
That premise is **wrong** for this band:

- The German licence-exempt cap at **433.05–434.79 MHz is ~10 mW ERP with an integral
  antenna**, not 1 W.
- **Germany ended licence-free 433 MHz remote-control use in 2008.**
- The **"1 W" figure is the US 915 MHz Part 15 rule** — different band, different
  jurisdiction.

In-repo secondary source: `docs/SOLAR-PIN-REGULATORY.md` on branch
`docs/solar-pin-regulatory` at commit `bc50dacd`. Primary source: **ERC/REC 70-03
Annex 1** — the exact Annex-1 table row is marked **`TODO(unverified)`** because it has
not been read in this session.

## Decision

Operate **licence-exempt at 433.05–434.79 MHz at ≤10 mW ERP with an integral antenna**,
instead of under the DE amateur licence.

Ground-side **receive** gain (a 10–15 dBi 433 Yagi) and receive-side LNAs are
**unregulated** and carry **no balloon mass**, so the downlink loss imposed by the ERP
cap is recovered on the ground. The **2.4 GHz uplink is ground-transmitted**, where
licence-exempt allows **100 mW EIRP**, so it does not suffer the same cap.

See `docs/licence-exempt-design-point.md` for the full per-band table, link-budget
arithmetic and duty-cycle discussion.

## Consequences

1. **ADR-037's "FEM omitted" decision is reopened and now settled by ADR-041** — the
   external FEM **stays off the balloon**. The 433 downlink closes at **+24.3 dB** with a
   12 dBi ground Yagi; the binding direction is the **2.4 GHz uplink** (ground-transmitted),
   not the 433 downlink.
2. **The F33 PA is unusable — over-limit.** The 2 W PA, and even the bare module's own
   22 dBm, exceed the 433 licence-exempt 10 mW ERP ceiling.
3. **A TX clamp + production test are required.** Firmware must clamp TX to ≤10 mW ERP,
   and a **production test must prove it** (conducted power = 10 mW minus antenna gain).
4. **Amateur duties are removed:** the callsign frame and the plain-telemetry /
   no-encryption duties no longer apply. `docs/regulatory-amateur` becomes the
   **rejected-alternative record** and is **kept**.
5. **Licence-exempt duties remain:** non-interference, no protection from interference,
   duty cycle (~1.7 %, 1 s per 60 s), and the antenna / ERP cap.
6. **Superseded framing:** the earlier "+6.4 dB with LNA / −5.6 dB without = the no-LNA
   link FAILS" analysis mis-applied the **433 10 mW cap to the 2.4 GHz uplink** and is
   **superseded**. The uplink is allowed 100 mW EIRP (20 dBm); the correct drop is
   **17 dB**, and no-LNA is **thin (+4.4 dB), not failed**.

## Open items (not assumed)

- **(a)** Licence-exempt SRD **airborne** use is a **grey area** — the framework targets
  short-range ground use. **National-regulation check required before flight.**
- **(b)** Whether a **balloon-side LNA** is still needed once the ground carries the gain.
- **(c)** **Sub-GHz FLRC availability on the F33** — unconfirmed.

## Relation to other ADRs

- **ADR-034 / ADR-035 / ADR-036** — upstream payload/radio architecture this design point
  sits on.
- **ADR-037** — "FEM omitted"; reopened by this ADR and settled by ADR-041: no external
  FEM on the balloon.
- **ADR-041** — the landed link budget (`adr/rf-frontend-licence-exempt` @ `a419e7d`)
  that the numbers here rest on.
- **ADR-005** — referenced band/link context.
