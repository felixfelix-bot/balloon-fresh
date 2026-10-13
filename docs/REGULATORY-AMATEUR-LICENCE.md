# Payload regulatory regime under the operator's German amateur radio licence

Operator statement, 2026-10-07 (verbatim): **"its legal, we have an amateur radio license"**. The operator is in Germany.
This document therefore analyses the payload under the **German amateur-service regime**, not under the licence-exempt short-range-device (SRD) regime. It supersedes any licence-exempt power analysis for this operator.

Scope: 2 W 433 MHz airborne balloon telemetry payload, LoRa/FLRC (hundreds of kHz occupied bandwidth).

---

## 1. Power — 2 W is inside the Class A/E limits on 70 cm

Source: AFuV Anlage 1, table entry 18 (430 – 440 MHz), as published on gesetze-im-internet.de (Fundstelle BGBl. 2024 I Nr. 175, S. 1–4).

| Class | 430 – 440 MHz limit |
|---|---|
| Klasse A | 750 W PEP |
| Klasse E | 75 W PEP |
| Klasse N | 6,1 W ERP |

Quoted from the table:
> „18 430 – 440 MHz P 750 W PEP 75 W PEP 6,1 W ERP 7 13“

Footnote 2 of the table defines: „PEP: Spitzenleistung … ERP: effektive Strahlungsleistung“.

**Verdict for 2 W (33 dBm):** well inside the 75 W PEP Class E limit and far below the 750 W PEP Class A limit. The 2 W F33 module is legal **by licence** on the 70 cm amateur band for a German Class A or Class E licensee.

Additional constraint for **automatic/remote terrestrial stations** above 30 MHz: AFuV Anlage 1 §1 limits such stations to **50 W ERP** (with exceptions for links and remote operation). 2 W ERP is comfortably below that ceiling.

---

## 2. Band plan — where a wideband data burst may transmit

Source: IARU Region 1 VHF Handbook 10.03, 70 cm band plan (430 – 440 MHz).

The IARU R1 plan lists several segments that can accommodate wideband data modes. For a LoRa/FLRC burst of hundreds of kHz, the relevant segments are:

| Segment | Status / bandwidth | Usage relevant to this payload |
|---|---|---|
| **430.000 – 431.975 MHz** | ALL MODES, **no bandwidth limit** | Sub-regional / national band planning. This is the principal segment for non-channelised wideband experiments. |
| 432.500 – 433.000 MHz | ALL MODES, no bandwidth limit | Includes APRS frequency 432.500 MHz; also contains repeater-input channels in some countries. |
| 433.600 – 434.000 MHz | ALL MODES, no bandwidth limit | IARU digital-communications channels; note (m) and LoRa experiments (note p). |
| 434.000 – 434.9875 MHz | ALL MODES, no bandwidth limit | Centre of digital experiments at 434.000 MHz; also ATV (note c). |

Quoted from the band plan table:
> „430.000 … No limit … ALL MODES … SUB-REGIONAL (national bandplanning)“

And for the digital-communications segment:
> „433.600 … ALL MODES … Digital communications channels (g) (h) (i)“  
> „434.000 … Centre frequency of digital experiments as defined on note (m) … LORA (p)“

Footnote (m):
> „Experiments using wide band digital modes may take place in the 435 MHz band by staying in the segment [around 434.000 MHz].“

Footnote (p):
> „125 kHz Max BW Data (such as LoRa etc)’ to enable experiments of other modes more easily.“

National interpretation (DARC 70 cm band plan, May 2025) marks 430.000–431.975 MHz as „Subregionale Bandplanung“ and the 433.050–434.775 MHz block as a shared SRD/amateur area.

### Shared-with-SRD sub-band: 433.05 – 434.79 MHz

The CEPT SRD recommendation ERC/REC 70-03 designates **433.050 – 434.790 MHz** for licence-exempt short-range devices. This band sits inside the German amateur 430 – 440 MHz allocation. The German frequency usage plan notes the band 433.05 – 434.79 MHz is an ISM/SRD range.

What this means for an amateur transmission:
* The amateur service in 430 – 440 MHz is **secondary** in Germany (see §3 below). Its protection claim is against **other amateur stations** (earlier assignment) and against other secondary services, not against primary services.
* SRDs are **not a radio service** under the ITU Radio Regulations; they operate under national general allocations and must accept interference from licensed radio services.
* Therefore the amateur licensee **does not have to protect SRD devices**, but the 2 W signal will locally deafen or interfere with SRD receivers in range. SRD operators have no regulatory basis to demand protection from a licensed amateur station.
* Conversely, the amateur station **must not cause harmful interference to the primary services** in the same 430 – 440 MHz range and **cannot claim protection** from them.

---

## 3. Secondary allocation — who the amateur station must protect

Source: BNetzA frequency usage plan (Frequenzplan), entries for 430 – 440 MHz, and AFuV Anlage 1 §3.

The German frequency usage plan shows the 430 – 440 MHz band shared by:
* **Amateurfunkdienst** (amateur service) — technical/operating conditions set by the AFuV;
* **Militärische Funkanwendungen** — single frequencies to be coordinated with BNetzA;
* **Nichtnavigatorischer Ortungsfunkdienst** (non-navigational radiodetermination service) — military radar applications to be coordinated with BNetzA.

AFuV Anlage 1 §3 defines secondary status:
> „Ein sekundärer Funkdienst ist ein Funkdienst, dessen Funkstellen weder Störungen bei den Funkstellen eines primären Funkdienstes verursachen dürfen noch Schutz vor Störungen durch solche Funkstellen verlangen können. Dies ist unabhängig davon, wann die Frequenzzuteilung an Funkstellen des primären Funkdienstes erfolgt.“

For this 2 W airborne payload:
* The station must be configured so that it does **not cause harmful interference** to military/radar primary users.
* It **cannot demand protection** from those primary services.
* A high-altitude balloon can be received over very long distances; care in antenna pattern, duty cycle and frequency choice should minimise the chance of interfering with primary users.

---

## 4. Identification — callsign is a firmware requirement

Source: AFuG 1997 §5(1); ITU Radio Regulations Article 19.

AFuG §5(1):
> „Der Funkamateur darf nur ein ihm von der Bundesnetzagentur … zugeteiltes Rufzeichen benutzen.“

ITU RR Article 19.4 / 19.17 (Identification of stations):
> „All transmissions in the following services should … carry identification signals: a) amateur service“  
> „For transmissions carrying identification signals, in order that stations may be readily identified, each station shall transmit its identification as frequently as practicable … identification signals shall be transmitted at least hourly, preferably within the period from five minutes before to five minutes after the hour (UTC) …“

The **binding international minimum is therefore hourly**. The commonly quoted 10-minute interval used by many amateurs is a conservative operating practice. I could not locate a German statutory provision that fixes the interval at 10 minutes, so the project should treat **hourly** as the legal floor and choose its internal interval as a stricter engineering margin.

**Firmware design consequence:** every telemetry downlink frame (or a regular beacon derived from it) must carry the operator's assigned German callsign in a form the ground station can decode without ambiguity. A practical implementation would:
* embed the callsign in ASCII in the LoRa/FLRC frame header;
* repeat it at least once per hour while airborne (and preferably more often, e.g. every 10 minutes, to aid frame-loss tolerance);
* include it in any decoded output displayed to the operator.

---

## 5. No encryption / no obscuring of content

Source: AFuV §16(7) and (8).

> „Der Amateurfunkverkehr ist in offener Sprache abzuwickeln. Der internationale Amateurschlüssel und die international gebräuchlichen Betriebsabkürzungen gelten als offene Sprache.“

> „Übertragungsverfahren müssen mit allgemein verfügbarer Technik oder mit entsprechenden Kenntnissen und Fertigkeiten eine Wiederherstellung übertragener Inhalte zulassen. Der Amateurfunkverkehr darf nicht zur Verschleierung des Inhalts kodiert oder verschlüsselt werden; ausgenommen sind Steuersignale für Erd- und Weltraumfunkstellen des Amateurfunkdienstes über Satelliten, ferner Steuersignale (einschließlich Remote-Betrieb) oder von anderen fernbedienten oder automatisch arbeitenden Stationen.“

**Firmware/design consequences:**
* The telemetry payload must **not encrypt user data** (position, sensors, status).
* The modulation, frame format and any error-correcting code must be **publicly documented** so that any third party with suitable equipment can recover the content.
* Standard LoRa/FLRC physical-layer settings are acceptable because the physical layer is publicly specified; the project must not add a proprietary cipher or scrambler intended to hide the payload.
* This is a **direct conflict** with any plan for encrypted telemetry. If encryption is wanted for operational reasons, it cannot be carried on the amateur link; it would have to use a separate non-amateur service.

---

## 6. Pecuniary / commercial interest

Source: AFuG 1997 §2 Nr. 1 and §5(4).

AFuG §2 Nr. 1 defines the amateur as someone who participates **„aus persönlicher Neigung und nicht aus gewerblich-wirtschaftlichem Interesse“**.

AFuG §5(4):
> „Eine Amateurfunkstelle darf 1. nicht zu gewerblich-wirtschaftlichen Zwecken und 2. nicht zum Zwecke des geschäftsmäßigen Erbringens von Telekommunikationsdiensten betrieben werden.“

**Verdict for a hobby balloon flight:** unaffected. A private, non-commercial telemetry payload is exactly the kind of experimental/self-training use the amateur service is intended for.

---

## 7. Cross-border drift — CEPT reciprocity for an unmanned airborne station

Sources: CEPT Recommendation T/R 61-01 (CEPT Radio Amateur Licence, edition 4 October 2011); ECC/REC/(05)06 (CEPT Novice Radio Amateur Licence).

What T/R 61-01 does:
* It allows a CEPT-licensed amateur visiting another CEPT country to operate an amateur station during a **short visit** without obtaining a separate temporary licence (Annex 1, §1).
* The visiting operator must use his **national call sign preceded by the call sign prefix of the visited country** (Annex 1, §2.3).
* The operator must observe the ITU Radio Regulations, T/R 61-01 and the **regulations of the visited country** (Annex 1, §2.2).
* The equivalence table in Annex 2 covers Germany (call-sign prefix DL in Germany; German amateurs use the visited country's prefix abroad).

What is **unclear / not obviously covered**:
* T/R 61-01 is written for a **person physically present** in the visited country and operating a station there. It is not designed for an **unmanned, airborne, automatically transmitting station** that crosses borders while the licensee remains in Germany.
* The payload will drift hundreds of kilometres and may transmit from Poland, Czechia, Austria, France, the Netherlands, Denmark, etc. In each country the local amateur regulations, band plans and power rules may differ.
* Some countries restrict airborne amateur transmitters, high-power automatic stations, or the 433.05 – 434.79 MHz SRD overlap differently.

**Verdict:** whether a German amateur licence (with or without the CEPT prefix) lawfully covers an **automatically transmitting, unmanned balloon payload abroad** is **not settled here**. This must be resolved with the national regulator(s) of the countries overflown, or by obtaining the appropriate permits, **before flight**. Recorded as an **open item**.

UNVERIFIED: whether any neighbouring country grants blanket CEPT reciprocity to airborne autonomous amateur transmitters, and whether BNetzA considers a cross-border high-altitude balloon to fall under T/R 61-01 or under a separate experimental/remote-station licence.

---

## 8. The 2.4 GHz option

Yes, the operator's licence also gives a **second licensed high-power option** at 2.4 GHz.

Source: BNetzA frequency usage plan, entries for 2400 – 2450 MHz; AFuV Anlage 1, table entry 23.

BNP shows the band 2400 – 2450 MHz allocated to:
* SRD (10 mW EIRP);
* WLAN / WAS (100 mW EIRP);
* demonstrations for educational institutions (5 W ERP);
* **Amateurfunkdienst** (amateur service);
* **Amateurfunkdienst über Satelliten** (amateur-satellite service, via footnote D282).

AFuV Anlage 1 entry 23:
> „23 2 400 – 2 450 MHz S 75 W PEP 5 W PEP 9 13 17“

Footnote 9 of the table: maximum occupied bandwidth 10 MHz (20 MHz for television). Footnote 13 concerns amateur-satellite service; footnote 17 allows link stations up to 1000 W ERP in specially justified cases.

So under an amateur licence:
* **Class A:** up to 75 W PEP in 2400 – 2450 MHz.
* **Class E:** up to 5 W PEP.
* Status: **secondary** (S), shared with SRD, WLAN, WAS and other services.

This is relevant because the v9 architecture has a 2.4 GHz receive path. A 2.4 GHz **transmit** path would also be feasible under the same amateur licence, although the band is much busier with unlicensed traffic and the propagation/limit characteristics differ from 70 cm.

---

## 9. Ballast drop is aviation, not radio

Dropping ballast or other objects from a high-altitude balloon is governed by **aviation law**, not by the amateur radio licence. In Germany this falls under the Luftverkehrs-Ordnung (LuftVO) and any applicable unmanned-balloon rules. It is **out of scope** for this regulatory radio analysis.

---

## Summary table

| Item | Finding | Source |
|---|---|---|
| 70 cm power limit | Class A 750 W PEP, Class E 75 W PEP | AFuV Anlage 1, entry 18 |
| 2 W 433 MHz verdict | Legal under the licence | AFuV Anlage 1 |
| Wideband data segment(s) | principally 430.000–431.975 MHz; also 433.600–434.000/434.000–434.9875 MHz | IARU R1 VHF Handbook 10.03 |
| SRD shared band | 433.05–434.79 MHz; SRD must accept interference, cannot claim protection | ERC/REC 70-03; BNetzA Frequenzplan note D150 |
| Secondary status | 430–440 MHz amateur is secondary; must protect military/radar primaries | BNetzA Frequenzplan 430–440 MHz; AFuV Anlage 1 §3 |
| Callsign interval | At least hourly (ITU RR); 10 min is common practice, not a German statute | ITU RR Art. 19.17; AFuG §5(1) |
| Encryption | Prohibited; modulation/encoding must be publicly recoverable | AFuV §16(7)–(8) |
| Commercial use | Prohibited; hobby flight unaffected | AFuG §2 Nr. 1, §5(4) |
| Cross-border CEPT | Unsettled for unmanned airborne automatic station; open pre-flight item | CEPT T/R 61-01 |
| 2.4 GHz option | Yes: 2400–2450 MHz, Class A 75 W PEP / Class E 5 W PEP, secondary | AFuV Anlage 1, entry 23; BNetzA Frequenzplan |

---

## Open items

1. **Cross-border operation:** confirm with BNetzA and/or the regulators of expected overflight countries whether a German amateur licence covers an unmanned, automatically transmitting balloon payload abroad, or whether a separate experimental/remote-station permit is required.
2. **Callsign interval:** decide project interval (recommend ≤10 minutes as engineering margin, with ≥1 per hour as the regulatory floor).
3. **Frequency choice:** select a specific centre frequency inside 430.000–431.975 MHz (or a sub-segment agreed nationally) for the wideband telemetry burst, ensuring the occupied bandwidth stays inside the chosen segment and clear of local repeater/satellite channels.
