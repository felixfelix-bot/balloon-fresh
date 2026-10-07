# REPORT — docs/regulatory-amateur

## What was done
Created `docs/REGULATORY-AMATEUR-LICENCE.md` on branch `docs/regulatory-amateur` based on the observed tip of `adr/radioband-tdm` (`8b46f6873f815425acb7203da1d22685e954d404`).

The document analyses the operator's German amateur-radio licence regime for the 2 W 433 MHz balloon telemetry payload, explicitly superseding the licence-exempt SRD analysis because the operator holds an amateur licence.

## Key findings
* **Power:** AFuV Anlage 1 permits 750 W PEP (Class A) / 75 W PEP (Class E) on 430–440 MHz. 2 W is well within.
* **Band plan:** wideband data may principally use 430.000–431.975 MHz (ALL MODES, no BW limit) per the IARU R1 VHF Handbook 10.03; 433.600–434.000/434.000–434.9875 MHz are also available. The 433.05–434.79 MHz range is shared with SRD; SRD devices must accept interference and cannot claim protection.
* **Secondary status:** 430–440 MHz amateur allocation in Germany is secondary; primary users include military applications and non-navigational radiodetermination. The amateur station must not cause harmful interference and cannot claim protection.
* **Identification:** callsign must be transmitted; ITU RR Article 19.17 requires identification at least hourly. The commonly cited 10-minute interval is operating practice, not found in German primary law. The telemetry frame must carry the callsign.
* **No encryption:** AFuV §16(7)–(8) prohibits encrypted/obscured amateur traffic (except control signals). Any planned encrypted telemetry conflicts with amateur rules.
* **Pecuniary interest:** amateur service must not be used commercially; hobby flight is unaffected.
* **Cross-border drift:** CEPT T/R 61-01 covers visiting licensees physically present in another country; whether it covers an unmanned airborne automatically transmitting station is **unsettled** — recorded as a pre-flight open item.
* **2.4 GHz option:** yes — 2400–2450 MHz is also an amateur band under the same licence (Class A 75 W PEP / Class E 5 W PEP, secondary).
* **Ballast drop:** out of scope — governed by aviation rules (LuftVO), not radio.

## Files created/modified
* `docs/REGULATORY-AMATEUR-LICENCE.md` (new)
* `PROGRESS.md` (new)
* `REPORT.md` (new)

## UNVERIFIED items
1. Whether a German amateur licence (via CEPT T/R 61-01) lawfully covers an unmanned, automatically transmitting balloon payload abroad.
2. Whether German primary law explicitly requires a 10-minute identification interval (ITU RR floor is hourly).

## Pushes
To be completed in this session; github first, then ngit.
