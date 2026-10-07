# Progress — docs/regulatory-amateur

## Base
* Branch: `docs/regulatory-amateur`
* Base: `adr/radioband-tdm` tip observed at `8b46f6873f815425acb7203da1d22685e954d404` via `git ls-remote origin`.
* Worktree: `/home/c03rad0r/worktrees/bf-reg-amateur`

## Sources consulted
1. AFuV 2005 + Anlage 1 (gesetze-im-internet.de) — power table, secondary-service definition, no-encryption, automatic-station limits.
2. AFuG 1997 (gesetze-im-internet.de) — callsign use, commercial-use prohibition, definition of amateur.
3. IARU Region 1 VHF Handbook 10.03 (iaru-r1.org, VHF_Handbook_V10_03_final.pdf) — 70 cm band plan segments, wideband data / LoRa notes.
4. DARC 70 cm Bandplan May 2025 (darc.de) — national interpretation of the IARU plan.
5. BNetzA Frequenzplan 2026/08 (data.bundesnetzagentur.de, 202608_Frequenzplan.pdf) — 430–440 MHz and 2400–2450 MHz allocations, primary/secondary users, SRD/ISM note.
6. ERC/REC 70-03 (anrceti.md mirror) — SRD 433.050–434.790 MHz band and coexistence rules.
7. CEPT T/R 61-01 (portal.arrlx.pt mirror, edition 4 Oct 2011) — visiting-operator reciprocity.
8. ECC/REC/(05)06 (pc5e.nl mirror) — CEPT novice licence reciprocity.
9. ITU Radio Regulations Article 19 (docslib.org rendering) — identification interval.

## Deliverable produced
* `docs/REGULATORY-AMATEUR-LICENCE.md` — answers all nine brief items with quoted sources or explicit `UNVERIFIED` markers.

## Remaining open items
1. Cross-border status of an unmanned airborne automatic station under CEPT T/R 61-01 — flagged as unresolved pre-flight item.
2. Exact German statutory identification interval — ITU RR sets hourly floor; 10-minute interval is common practice, not found in AFuV/AFuG.

## Status
* Document written and staged.
