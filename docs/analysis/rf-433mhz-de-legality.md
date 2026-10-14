# 433 MHz in Germany — legal limits, and whether 2 W / +33 dBm is licence-free

**Private working notes. Prepared 2026-10-14 for the pico-balloon flight-board power decision.**

**Question decided:** is a +33 dBm / 2 W transmitter at 433 MHz lawful in Germany without an
amateur licence, or must the flight board be capped?

**Method.** Primary instruments only: the BNetzA general assignment for short-range devices
(**Vfg. 91/2025**), the German amateur-radio ordinance (**AFuV**) with its **Anlage 1**, the
Amateurfunkgesetz (**AFuG**), the **Frequenzplan** (August 2026), and the harmonised standard
**ETSI EN 300 220-2 V3.3.1 (2025-03)**. Everything below was downloaded and text-extracted on
**2026-10-14**; file hashes are in the Sources section so the exact documents can be re-verified.
Anything I could not verify is marked **UNVERIFIED** with the reason. Neither the BNetzA nor any
lawyer has confirmed the interpretation — see *Open risks*.

---

## HEADLINE ANSWER

> **2 W / +33 dBm at 433 MHz is NOT licence-free legal in Germany. There is no general assignment
> anywhere in Germany that permits it.**
>
> The licence-exempt ceiling on 433.05–434.79 MHz is **10 mW ERP = +10 dBm ERP = +12.15 dBm EIRP**,
> and it is unconditional under the national row **D44a/D44b/D45c** of Vfg. 91/2025.
>
> **The gap is 23.0 dB in ERP terms (33 dBm conducted vs +10 dBm ERP), or 20.85 dB if you compare
> the +33 dBm design against the EIRP ceiling (+12.15 dBm EIRP) it would actually have to meet.**
>
> 2 W is attainable only inside the **amateur radio service**, and the amateur route does **not**
> fit an unattended drifting balloon: AFuV **§ 13 Abs. 1** ties an automatically operating station
> to **the single location named in its callsign assignment**. That is a legal blocker, not an
> engineering one. Amateur power is also capped at **50 W ERP** for automatic terrestrial stations,
> and AFuG § 5 Abs. 4/5 bars the amateur service from carrying third-party traffic.

---

## Q1 — What Vfg. 91/2025 actually permits on 433 MHz

**Instrument:** *Allgemeinzuteilung von Frequenzen zur Nutzung durch Geräte geringer Reichweite
(SRD)*, **Vfg. 91/2025, November 2025** — the current SRD general assignment. It implements
Commission Decision 2006/771/EC as last amended by **(EU) 2025/105**, and **repeals** the previous
SRD assignment Amtsblattverfügung 133/2019 (as amended by Vfg. 12/2020) and the other separate
assignments listed in its preamble (including Amtsblattverfügung 128/2023, 2400–2483.5 MHz). It is
**valid until 31.12.2035** and takes effect two weeks after publication under § 210 TKG.

### The 433 MHz rows (verbatim)

**Tabelle 2 — harmonised conditions** (the `*` on the band number means Germany applies a deviation,
printed in Tabelle 3):

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung | Zusätzliche Parameter |
|---|---|---|---|---|
| **44a** | 433,05–434,79 MHz | Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen | **1 mW (ERP)** | — |
| **44b** | 433,05–434,79 MHz | (same) | **10 mW (ERP)** | **Arbeitszyklus: ≤ 10 %** |
| **45c** | 434,04–434,79 MHz | (same) | **10 mW (ERP)** | **Arbeitszyklus ≤ 100 % bei einer Bandbreite ≤ 25 kHz** |

**Tabelle 3 — national conditions** (`D`-prefixed rows; the assignment states these are *less
strict* alternatives that may be used **instead of** the Tabelle 2 conditions):

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung | Zusätzliche Parameter |
|---|---|---|---|---|
| **D44a / D44b / D45c** | 433,05–434,79 MHz | Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen | **10 mW (ERP)** | *(empty — no duty-cycle, no bandwidth condition)* |

**The two-footings rule, verbatim from the instrument:** SRD use in Germany is available
*"sowohl mit den harmonisierten technischen Bestimmungen gemäß Tabelle 2 als auch mit den weniger
strengen nationalen Bestimmungen gemäß Tabelle 3"* — with both the harmonised conditions of
Tabelle 2 **and** the less strict national conditions of Tabelle 3.

**So the operative answer for 433.05–434.79 MHz:**

- **Application class:** *nicht näher spezifizierte Anwendungen* (non-specific SRD) — telemetry,
  telecommand, alarms, general data transmission. A balloon telemetry beacon fits this category.
- **Max power:** **10 mW ERP**, unconditional. 1 mW ERP is the no-conditions variant of the
  harmonised row.
- **Duty cycle:** whichever condition you choose. Under **D44b** the ≤ 10 % duty cycle and the
  bandwidth condition are **waived entirely**; under **44b** you must keep duty ≤ 10 %; under **45c**
  (434.04–434.79 MHz) 100 % duty is allowed **at ≤ 25 kHz bandwidth**. For an airborne beacon
  transmitting at intervals, the duty cycle is the cheap lever: the assignment defines
  *Arbeitszyklus* as Σ(T_on)/T_obs with **T_obs = one hour** unless the tables say otherwise.
- **Legal footing:** § 210 TKG, non-exclusive, non-interfering, unprotected.

**Ceiling in every currency:** 10 mW ERP = **+10 dBm ERP = +12.15 dBm EIRP** (ERP is
dipole-referenced; EIRP = ERP + 2.15 dB).

### Two claims in circulation that this rules out

- **There is no "integral antenna" requirement on this band.** The only category in Vfg. 91/2025
  demanding built-in antennas is PMR446. If the design brief repeats that claim, it came from a
  secondary encyclopaedia source, not the instrument. *(Consistent with the existing note in the
  `authoritative-source-research` reference bank.)*
- **"433 MHz is an ISM band, so any power is free" is wrong.** ISM general assignment
  **Vfg. 76/2003** does allocate 433,05–434,79 MHz to the general public for ISM applications, but
  it defines these as *"alle Nutzungen elektromagnetischer Wellen durch Geräte oder Vorrichtungen
  für die Erzeugung und lokale Nutzung von Hochfrequenzenergie …"* — generation and **local** use of
  RF energy, explicitly **not data transmission**. It cannot legalise a telemetry transmitter.

**Q1 answer:** 433.05–434.79 MHz is licence-free at a hard **10 mW ERP**, with the duty-cycle and
bandwidth conditions optional under the German national row. No general assignment on this band
goes above 10 mW ERP.

---

## Q2 — What EN 300 220 says

**Current standard:** **ETSI EN 300 220-2 V3.3.1 (2025-03)**, *Short Range Devices (SRD) operating
in the frequency range 25 MHz to 1 000 MHz **with power levels ranging up to 500 mW e.r.p.**;
Part 2: Harmonised Standard for access to radio spectrum for **non specific** radio equipment*.

**Two things follow from the scope alone, and they are the important ones:**

1. **The standard's own ceiling is 500 mW e.r.p.** Its scope says the equipment types it covers
   *"are capable of transmitting up to 500 mW effective radiated power and operating indoor or
   outdoor"*, and its cross-reference annex repeats that equipment *"in the scope are also limited
   to low power not exceeding 500 mW."* **2 W = 2000 mW is 4× outside the standard's own envelope,
   by design.**
2. **The scope's 500 mW is not a permission.** It is the envelope of the harmonised standard —
   i.e. the type-approval footing. The actual operating limit in Germany is the national assignment
   of Q1 (10 mW ERP on this band). A harmonised standard gives presumption of conformity; it does
   not grant spectrum access.

### The applicable table rows (verbatim from the standard)

| Row | Band | Max e.r.p. | Duty cycle | Other |
|---|---|---|---|---|
| **H** (EC Decision band **44b**) | 433,050–434,790 MHz | **10 mW e.r.p.** | **10 %** | whole band |
| **I** (band **44a**) | 433,050–434,790 MHz | **1 mW e.r.p.**; −13 dBm/10 kHz PSD for bandwidth modulation larger than 250 kHz | no requirement | voice allowed with advanced mitigation; other audio/video excluded |
| **J** (band **45c**) | 434,040–434,790 MHz | **10 mW e.r.p.** | no requirement | max occupied bandwidth **25 kHz**; channel spacing 25 kHz |

These reproduce the German and EU rows exactly — **10 mW e.r.p. is the ceiling in the harmonised
standard too**. The standard adds nothing above 10 mW for this band; it only refines the conditions.

**Prior version, for the record:** EN 300 220-2 **V3.2.1 (2018-06)** had the same 10 mW / 1 mW
structure on 433 MHz. V3.3.1 is the one to cite now.

**Q2 answer:** EN 300 220-2 V3.3.1 (2025-03) — current version — gives 10 mW e.r.p. / 10 % duty
(44b), 1 mW e.r.p. (44a) and 10 mW e.r.p. / 25 kHz (45c) on 433 MHz, and its own scope caps out at
**500 mW e.r.p.** 2 W is not an SRD figure in any version.

---

## Q3 — Is there ANY German general assignment permitting ~2 W at 433 MHz?

**No.** I read the complete general-assignment index and downloaded the plausible candidates.

- The index lists **40 assignments**. **None** is about balloons, radiosondes, weather balloons,
  high-altitude platforms or airborne telemetry in the 433 MHz band. The only two aviation-flavoured
  assignments are **Vfg. 147/2018** (aeronautical mobile/flight-navigation radio for aviation
  personnel — 121.5, 123.1, 243, 406.1 MHz etc., **no 433 MHz**) and **Vfg. 1/2026** (MCA mobile
  services on board aircraft — 1710–2170 MHz, **no 433 MHz**).
- **Vfg. 120/2022** (model remote control) covers only 35.205–35.905 / 40.710–40.990 MHz — no 433.
- **Vfg. 50/2025** (in-company radio), **Vfg. 33/2020** (underground) — no 433 MHz.
- The SRD assignment (Q1) is the only general assignment touching 433.05–434.79 MHz at 10 mW ERP.

**One higher-power entry exists on the band, and it is not a general assignment.** The
**Frequenzplan** (Frequenzteilplan 247, entry 247005, Stand März 2022) records a **Betriebsfunk**
use of **433,0875–434,7625 MHz** for *"Übertragung von Datensignalen (Fernwirkfunk)"* at
**maximal zulässige äquivalente Strahlungsleistung 0,5 W ERP**, channel bandwidth 25/50/150 kHz,
channel raster 25 kHz. Notes:

- It is **0.5 W ERP = +24 dBm ERP = +26.15 dBm EIRP** — **6.85 dB short of 2 W / +33 dBm**, so it
  does not reach the design point either.
- **Betriebsfunk is a licensed land-mobile service, not a general assignment.** It requires an
  individual frequency assignment from the BNetzA. **UNVERIFIED:** whether an unattended drifting
  balloon could hold such an assignment, and on what terms — the Frequenzplan does not address
  airborne operation, and I did not find an eligibility rule. Treat as a question for the BNetzA,
  not as an available route.
- The Frequenzplan's own status for the 430–440 MHz entry (247004, SRD) matches Vfg. 91/2025:
  **10 mW ERP**, duty cycle 100 % at 25 kHz channel spacing.

**Q3 answer:** No German general assignment permits ~2 W (or anything above 10 mW ERP) at 433 MHz.
The nearest higher-power entry on the band is a 0.5 W ERP licensed *Fernwirkfunk* service, which is
still below 2 W and requires an individual assignment of unknown—likely poor—fit for a balloon.

---

## Q4 — Does 2 W require the amateur service, and would the amateur route work?

### Is 433 MHz in a German amateur band? Yes — the SRD window sits *inside* one.

**AFuV Anlage 1, row 18:** **430–440 MHz**, status **P** (amateur service is *primary*), Klasse A
**750 W PEP**, Klasse E **75 W PEP**, Klasse N **6.1 W ERP**, Zusatzbestimmungen **7, 13**.
So 433.05–434.79 MHz is simultaneously an SRD window *and* part of a primary amateur allocation.

### Licence classes

German amateur certificates come in **classes A, E and N** (AFuV § 12). On 70 cm, a **Class A**
holder (750 W PEP) or a **Class E** holder (75 W PEP) could reach 2 W PEP with enormous headroom.
There is also a newer **Class N** entry at **6.1 W ERP** on this band, which would also technically
cover 2 W. **So 2 W is not a power problem in the amateur service — it is 25.7 dB below the Class A
figure.**

### But the amateur service is the wrong tool for this flight. Three independent blockers:

**(1) An automatically operating station must be at one fixed, assigned location — this is the
blocker.**

> AFuV **§ 13 Abs. 1**: *"Der Betrieb einer fernbedienten oder automatisch arbeitenden
> Amateurfunkstelle bedarf einer gesonderten Rufzeichenzuteilung nach § 3 Abs. 3 Nr. 3 des
> Amateurfunkgesetzes. **Diese Amateurfunkstelle darf nur an dem in der Rufzeichenzuteilung
> aufgeführten Standort unter den dort festgelegten Rahmenbedingungen betrieben werden.**"*
> ("This amateur station may be operated **only at the location listed in the callsign assignment**,
> under the conditions specified there.")

§ 13 Abs. 2 requires a **site-specific compatibility assessment** (*standortbezogene
Verträglichkeitsuntersuchung*) before the callsign is issued. The ordinance's own definition of
*Funkbake* is *"eine automatisch arbeitende Amateurfunk-Sendeanlage (auch in Satelliten), die
selbsttätig regelmäßige Aussendungen zur Feldstärkebeobachtung oder zu Empfangsversuchen erzeugt"*
— note it contemplates **satellites** but grounds the terrestrial case at one **Standort**.
A drifting balloon crosses hundreds of kilometres in hours, so it cannot satisfy "only at the
listed location". **The amateur footing does not fit an unattended drifting beacon.**

**(2) The automatic-station power cap is 50 W ERP — lower than the band table's own class figure.**

> AFuV **Anlage 1 (1)**: *"Die maximal zulässige Strahlungsleistung für fernbediente oder
> automatisch arbeitende **terrestrische** Amateurfunkstellen beträgt oberhalb von 30 MHz **50 Watt
> ERP** (ausgenommen Remote-Betrieb)."*
> (*"The maximum permissible radiated power for remotely controlled or automatically operating
> **terrestrial** amateur stations above 30 MHz is **50 W ERP** (except remote operation)."*)

**UNVERIFIED:** whether the BNetzA applies "terrestrisch" to an airborne station. The ordinance does
not say. 50 W ERP = **+46.99 dBm ERP = +49.14 dBm EIRP**, so even on the pessimistic reading there
is 17 dB of headroom over 2 W — but the *location* rule in (1) is violated either way.

**(3) The amateur service may not carry the traffic this project wants to carry.**

> **AFuG § 5 Abs. 4/5**: an amateur station may **not** be operated *"zu gewerblich-wirtschaftlichen
> Zwecken"* or *"zum Zwecke des geschäftsmäßigen Erbringens von Telekommunikationsdiensten"*, and
> the operator *"darf Nachrichten, die nicht den Amateurfunkdienst betreffen, für und an Dritte
> nicht übermitteln."*

Any "bent pipe / internet gateway / relay carrying other people's traffic" design is in direct
tension with this. The amateur route buys 2 W at the cost of the service model.

**(4) Additional operational frictions:** amendment/callsign identification at least every 10
minutes (AFuV **§ 11 Abs. 1**); no simultaneous operation from two locations with one callsign
(**§ 11 Abs. 6** — a balloon 300 km away while the shack is on air is two locations and needs prior
BNetzA consent); and the callsign authorises operation **inside Germany** (§ 11 Abs. 1), so a
border-crossing balloon needs per-country permission.

**One genuine escape hatch, if the operator holds a licence and wants to pursue it:**
**AFuV § 16 Abs. 2** lets the BNetzA grant exceptions for *"besondere experimentelle und
technisch-wissenschaftliche Studien"*. This is an application to the authority, not a right.

**Q4 answer:** +33 dBm / 2 W is **not exclusively** an amateur figure — a Class N licence already
covers 6.1 W ERP on 70 cm — but in practice **the amateur service is the only footing where 2 W
exists at all**, and it is the *wrong* footing for this flight: § 13 Abs. 1 pins an automatic
station to one assigned location, which a drifting balloon cannot satisfy. 433 MHz is a genuine
German amateur band (430–440 MHz, status P), so this is not a spectrum problem — it is an
operating-model problem.

---

## Q5 — The lawful maximum without a licence, and what it costs the link budget

**Lawful maximum in Germany on 433.05–434.79 MHz, licence-free: 10 mW ERP.**

| Quantity | Value |
|---|---|
| Conducted design power | **+33.0 dBm** (2 W) |
| Licence-exempt ceiling (ERP) | **+10.0 dBm ERP** |
| **Reduction required, ERP basis** | **23.0 dB** |
| Licence-exempt ceiling (EIRP) | **+12.15 dBm EIRP** |
| **Reduction required, EIRP basis** | **20.85 dB** |

Use **20.85 dB** as the number that binds your transmitter, because the ceiling is enforced as an
**ERP** limit: with a 0 dBi (≈ −2.15 dBd) antenna, +10 dBm ERP means a conducted power of about
**+12.15 dBm**. (The repo's own `RF-REVIEW-433-TX-POWER.md` cites 20.9 dB — it is correct.)

### What it does to the link budget

**At constant margin** — range scales as `10^(−ΔP/20)` = **0.0907** at ΔP = 20.85 dB. The repo's
existing figures (300 km → 27.2 km, 100 → 9.1, 50 → 4.5, 20 → 1.8 km) are correct **for preserving
the original margin**, not for link closure.

**At link closure (0 dB margin), which is the more useful number.** Using the repo's own path-loss
constant (FSPL at 433.92 MHz = 85.19 + 20·log₁₀(d_km)), EIRP = +12.15 dBm and 12 dBi ground antenna:

| Mode | Sensitivity used | P_rx at 300 km | Margin at 300 km | Max range (0 dB margin) |
|---|---:|---:|---:|---:|
| FLRC 2.6 Mbit | −100.5 dBm | −110.59 dBm | **−10.1 dB (fails)** | ~43 km |
| FLRC 650 kbit | −107.0 dBm | −110.59 dBm | **−3.6 dB (fails)** | ~199 km |
| LoRa SF12 / BW62.5 kHz | ≈ −143 dBm | −110.59 dBm | **+32.4 dB (passes)** | horizon-limited |

*(Sensitivities and the 12 dBi ground antenna are from the repo's `433-2g4-bent-pipe-relay` worked
example; the LoRa SF12 sensitivity is the repo's figure and was **not** re-verified against a
Semtech datasheet in this session. The max-range column is **DERIVED** by me from
`EIRP + G_rx − FSPL = S` at zero margin; labels are explicit.)*

**The decision-relevant consequence, and it is not the one the existing analysis states:** the
20.85 dB cut **kills the high-rate FLRC downlink**, but it does **not** kill the 300 km link.
**LoRa SF12 at BW62.5 kHz still closes 300 km with ≈32 dB of margin at 10 mW ERP.** The design's
problem is therefore **data rate, not range**: the mission becomes a low-rate LoRa beacon, not a
2.6 Mbit FLRC downlink. (The repo note "300 km is not reachable at 10 mW ERP — it becomes ~27 km"
is true only for FLRC, and only at constant margin.)

**Duty cycle is a non-issue under the German national row.** Choosing the **D45c** footing
(bandwidth ≤ 25 kHz, ≤ 100 % duty) makes a LoRa connection with ~62.5 kHz occupied bandwidth the
wrong fit; **D44b** (10 mW ERP, no conditions) or **44b** (≤ 10 % duty, T_obs = 1 h) fits an
interval beacon comfortably — at SF12/BW125 airtime is on the order of 9 s per packet, so even a
10 % cap permits a packet roughly every 90 s.

---

## Q6 — Does balloon / high-altitude operation change the answer?

**Short answer: no rule I could find reduces the power limit for airborne use, and the radio-law
limits are the same in the air as on the ground — but two specific ceilings do interact with
altitude, and one of them is a real operational risk.**

**(a) The German SRD assignment carries no airborne provision, no altitude limit, no distance
limit.** The *Sonstige Nutzungsbeschränkungen* column is **empty** for the 433 MHz rows
(44a/44b/45c and D44a/D44b/D45c). There is no ground-to-air / air-to-ground distinction and no cap
on the radio horizon. The only airborne-adjacent material in the whole 32-page assignment is
footnote **[d]** (*Modellsteuerungsgeräte*), attached to the **27 MHz** model-control rows, and
footnote **[4]** (radio-astronomy protection zones) — neither touches 433 MHz.

**(b) The Frequenzplan's per-band rules for 430–440 MHz are likewise silent on airborne operation.**
Frequenzteilplan 247 entries 247001–247006 carry Nutzungsbestimmungen `D150 D282 5 10 31`; these
cover ISM, the amateur-satellite service, military coordination and general low-power sharing. None
mentions aircraft, balloons or altitude.

**(c) CEPT's position is that radio law permits airborne SRD operation under the same conditions,
and that aviation is a separate gate.** ERC/REC 70-03 states:

> *"The CEPT has considered the use of SRD devices on board aircraft and it has concluded that, from
> the CEPT regulatory perspective, such use is allowed under the same conditions provided in the
> relevant Annex of Recommendation 70-03. For aviation safety aspects, the CEPT is not the right
> body to address this matter which remains the responsibility of aircraft manufacturers or
> aircraft owners who should consult with the relevant national or regional aviation bodies before
> the installation and use of such devices on board aircraft."*

**Source caveat, stated plainly:** `docdb.cept.org` was **unreachable** (TLS/HTTP 000) and
`cept.org` served an HTML application shell instead of the PDF, so I could not read the current
edition. The quote above is from the **ARCEP-hosted copy of ERC/REC 70-03, February 2011 edition**
(the file's own creation date). It is directionally valid but **the edition is 15 years old — treat
as a secondary/dated source and re-fetch the current edition before relying on it.** The German
national texts above do not depend on it.

**(d) The larger radio horizon is NOT capped by any radio rule — but it is exactly why the design
needs the high power, so the two interact.** At 12 km altitude, the radio horizon grows to roughly
450 km against a ground station, and the existing analysis already shows that altitude is
essentially free in path-loss terms at 300 km (12 km of height on a 300 km slant adds 0.007 dB).
No instrument I read caps the achievable distance for airborne use. **So the 20.85 dB cut does not
create a distance-limit violation; it removes margin that the design was spending on rate.**

**(e) The real aviation-side risk is not power, it is interference and the balloon permit.**
Because an airborne transmitter at altitude illuminates a very large ground footprint, a high-power
beacon is an interference problem for every other 433 MHz user in that footprint — which is the
substantive reason the SRD ceiling is low, and why any exception would have to be argued rather
than assumed. Separately, and independently of radio law: **LuftVO § 20 Abs. 1 Nr. 6** requires a
permit from the *örtlich zuständige Luftfahrtbehörde des Landes* for the operation of an unmanned
free balloon under SERA Anlage 2, with no mass de-minimis. **Radio law and aviation law are
separate gates; clearing one does not clear the other.**

**Q6 answer:** No, balloon operation does not raise the permitted power; no German rule distinguishes
ground-to-air from air-to-ground or caps altitude/range for 433 MHz SRD. CEPT's (dated) position is
that airborne SRD use is allowed on the same conditions, with aviation safety left to aviation
bodies. The altitude advantage makes a low-power link *more* viable than it would be at ground
level — which is why the 10 mW ERP route is worth engineering rather than abandoning.

---

## Bottom line

| Question | Answer | Basis |
|---|---|---|
| Is 2 W licence-free legal in DE? | **NO** | Vfg. 91/2025 Tabelle 2 rows 44a/44b/45c + Tabelle 3 D44a/D44b/D45c |
| Lawful licence-free max at 433 MHz | **10 mW ERP** (+10 dBm ERP / +12.15 dBm EIRP) | same |
| Duty cycle | waived under D44b; ≤ 10 % under 44b; ≤ 100 % at ≤ 25 kHz under 45c/D45c | same |
| Gap from +33 dBm | **23.0 dB (ERP) / 20.85 dB (EIRP)** | derived, arithmetic |
| EN 300 220 ceiling | **10 mW e.r.p.** on this band; standard's own scope 500 mW e.r.p. | EN 300 220-2 V3.3.1 (2025-03), rows H/I/J |
| Any general assignment for 2 W? | **No** | full review of the 40-entry BNetzA assignment index |
| Amateur route viable? | **No for an unattended drifting balloon** — AFuV § 13 Abs. 1 pins an automatic station to one assigned location | AFuV § 13 Abs. 1 |
| 433 MHz a German amateur band? | Yes — **430–440 MHz, status P**; Kl. A 750 W PEP, Kl. E 75 W PEP, Kl. N 6.1 W ERP | AFuV Anlage 1 row 18 |
| Automatic-station power cap | **50 W ERP** (terrestrial, >30 MHz) | AFuV Anlage 1 (1) |
| Airborne-specific rule? | **None found** in Vfg. 91/2025 or the Frequenzplan | full-text search, both instruments |
| Effect on link budget | **20.85 dB**; FLRC dies, **LoRa SF12 still closes 300 km with ≈32 dB margin** | derived from repo path-loss/sensitivity figures |

**Plainly: the 2 W design as specified is not licence-free legal in Germany.** The flight board can
still fly legally at **10 mW ERP**, and the honest engineering consequence is a **change of mode
(FLRC → LoRa), not a change of mission** — the 300 km link closes at the legal cap with plenty of
margin (DERIVED; see the Q5 table). The mass and power budget consequences are therefore smaller
than the ADR-034 open item assumes: the 5 V / 1200 mA burst rail behind the F33's 2 W figure is
**not needed at all** for a licence-free design.

---

## Open risks / needs a human call

1. **The whole answer is a statutory reading, not an authority's confirmation.** Put the
   D44a/D44b/D45c reading to the BNetzA in writing. The favourable national row is *my* reading of
   Tabelle 3 (the rowspan cell prints 10 mW ERP with an empty parameter column); it is well
   supported by the instrument's own two-footings sentence, but it is still an interpretation.
2. **Class N on 70 cm.** I read **6.1 W ERP** for Klasse N from Anlage 1 row 18. If the operator
   holds a Class N licence, note the counter-intuitive result that the automatic-station cap
   (50 W ERP) is *higher* than the Class N band figure — but this is academic here, because § 13
   Abs. 1's location rule blocks the balloon regardless of class.
3. **AFuV § 13 Abs. 1 versus an airborne station — UNVERIFIED.** It is arguable that both the
   § 13 location rule and the *"terrestrisch"* qualifier in Anlage 1 (1) simply do not contemplate
   an airborne automatic station. That could cut either way: it may mean no rule applies, or that
   the BNetzA has no basis to authorise one. **Ask the authority.** Do not assume the amateur route
   is available because 70 cm is a primary amateur band.
4. **Current CEPT ERC/REC 70-03 edition not read** — `docdb.cept.org` unreachable, `cept.org`
   served an app shell. The airborne quote is from the **February 2011** ARCEP mirror. Re-fetch
   before citing.
5. **The 0.5 W ERP Betriebsfunk route (Frequenzplan 247005) is UNVERIFIED as to eligibility** for
   an airborne unattended transmitter. It is below 2 W anyway.
6. **Module EU Declaration of Conformity not checked.** NiceRF's product URLs returned 404/403.
   Vfg. 91/2025 Hinweis 2 requires equipment conforming to the FuAG, so the module's DoC must cover
   433 MHz at the power actually used. This is on the repo's own TODO list and remains open.
7. **LoRa SF12 sensitivity (−143 dBm) was taken from the repo, not re-verified** against a Semtech
   datasheet in this session. If it is optimistic by 5–10 dB the 300 km LoRa closure claim weakens
   but does not fail (32 dB margin).
8. **A second finding from the earlier 2026-10-10 analysis still stands and is not a radio issue:**
   AFuV Anlage 1 **Zusatzbestimmung 7** caps occupied bandwidth at **2 MHz** on 70 cm, which outlaws
   the intended FLRC 2.6 Mbit (2.666 MHz DSB) rate on the amateur footing. On the licence-exempt
   footing the binding constraint is 10 mW ERP. Either way FLRC at 2.6 Mbit is not the lawful mode.

---

## Sources

**Access date for all URLs: 2026-10-14.** Hashes are of the exact files read.

**Primary instruments**

1. Bundesnetzagentur, *Allgemeinzuteilung von Frequenzen zur Nutzung durch Geräte geringer
   Reichweite (SRD)*, **Vfg. 91/2025, November 2025** (32 pp.).
   https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf
   — `sha256 78155c01308262d9c47e7f29f9756fcbd1d9f36a80f0cb37c33bf7f7ade2e8f2`; PDF metadata:
   Title "Vfg 91/2025", Subject "Allgemeinzuteilung_SRD", Author "Bundesnetzagentur",
   created 2025-11-03, modified 2025-11-18. Rows read: Tabelle 2 lines for 44a/44b/45c; Tabelle 3
   for D44a/D44b/D45c; the two-footings sentence; the *Arbeitszyklus* definition; the Befristung.
2. Bundesnetzagentur, *Allgemeinzuteilungen* index (the 40-entry list from which Q3 was answered).
   https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/start.html
3. **AFuV** — *Verordnung zum Gesetz über den Amateurfunk (Amateurfunkverordnung)*, Fundstelle
   **BGBl. 2024 I Nr. 175**.
   https://www.gesetze-im-internet.de/afuv_2005/AFuV.pdf
   — `sha256 a384594c4ec77915aa9e354fa13b8d650eaf58148ad1a98d22d7496ec28d6f9d`. Sections read:
   § 2 Nr. 4/6 (§ 13 definition of *Funkbake*), § 11 Abs. 1 and 6, § 13 Abs. 1–3, § 16 Abs. 2,
   **Anlage 1 (1)** (the 50 W ERP automatic-station cap), Anlage 1 table row **18** (430–440 MHz),
   Zusatzbestimmungen **7** and **13**.
4. **AFuG** — *Gesetz über den Amateurfunk*.
   https://www.gesetze-im-internet.de/afug_1997/BJNR149400997.html — § 5 Abs. 4/5, § 6 Nr. 3.
5. Bundesnetzagentur, **Frequenzplan, August 2026** (753 pp., modified 2026-08-21).
   https://data.bundesnetzagentur.de/Bundesnetzagentur/SharedDocs/Downloads/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Frequenzen/202608_Frequenzplan.pdf
   — Frequenzteilplan 247: Eintrag 247004 (SRD, 10 mW ERP), **247005 (Betriebsfunk/Fernwirkfunk,
   0.5 W ERP)**, 247002 (Amateurfunkdienst 430–440 MHz), 247006 (amateur-satellite 435–438 MHz);
   Nutzungsbestimmungen 5, 10, 31, D150, D282.
6. Bundesnetzagentur, *Allgemeinzuteilung … für ISM-Anwendungen*, **Vfg. 76/2003**.
   https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/SonstigeFunkanwendungen/vfg76_2003.pdf
7. **LuftVO § 20** (aviation-side gate, quoted for context only).
   https://www.gesetze-im-internet.de/luftvo_2015/__20.html

**Harmonised standard**

8. **ETSI EN 300 220-2 V3.3.1 (2025-03)** — *Short Range Devices (SRD) operating in the frequency
   range 25 MHz to 1 000 MHz with power levels ranging up to 500 mW e.r.p.; Part 2: Harmonised
   Standard for access to radio spectrum for non specific radio equipment* (107 pp.).
   https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/03.03.01_60/en_30022002v030301p.pdf
   — `sha256 f7b46ac8b50e2befd976dc5fd76d2994c3f371a97f7b24303f6769deec064373`. Scope at clause 1;
   permitted-band table rows **H (44b)**, **I (44a)**, **J (45c)**.
9. **ETSI EN 300 220-2 V3.2.1 (2018-06)** — prior version, same 10 mW structure (read for the
   version history).
   https://www.etsi.org/deliver/etsi_en/300200_300299/30022002/03.02.01_60/en_30022002v030201p.pdf
10. **ETSI EN 300 220-1 V3.1.1 (2017-02)** — *Part 1: Technical characteristics and methods of
    measurement* (read to confirm the multi-part structure and that Part 1 carries no power limit).
    https://www.etsi.org/deliver/etsi_en/300200_300299/30022001/03.01.01_60/en_30022001v030101p.pdf

**Dated secondary source (flagged)**

11. **ERC/REC 70-03** (CEPT Recommendation), **February 2011 edition** per the file's own metadata —
    ARCEP-hosted copy, used only for the "SRD on board aircraft" wording, which is quoted verbatim and
    **flagged as dated**.
    https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf
    — **`docdb.cept.org` and `cept.org` were unreachable for the current edition (HTTP 000 / HTML
    app shell). Current edition UNVERIFIED.**

**Internal project records referenced**

12. `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` — the open item *"Legality of 2 W on 433 MHz in
    DE"* (in `worktrees/e80-lr2021-audit/` and `worktrees/v9-route/`).
13. `docs/analysis/RF-REVIEW-433-TX-POWER.md` — the existing 20.9 dB / 27 km analysis.
14. `~/.hermes/profiles/manager/skills/hardware/rf-link-budget/references/433-2g4-bent-pipe-relay-worked-example.md`
    — the path-loss constant, sensitivities, antenna gains and margin tables reused in Q5.
15. `~/.hermes/profiles/manager/skills/research/authoritative-source-research/references/`
    — `german-aviation-and-radio-law-sources.md` and `german-amateur-radio-afuv-limits.md`
    (the pre-existing knowledge bank this report re-verified against the live instruments).

---

## Referral

This is a statutory reading of German radio and amateur-radio law by a non-lawyer. Before flying,
put the specific operating point — 433.05–434.79 MHz, 10 mW ERP, the chosen duty cycle, the
intended bandwidth, and the fact that the transmitter is airborne and unattended — to the
**Bundesnetzagentur** in writing and keep the reply. If an amateur footing is contemplated at all,
the § 13 Abs. 1 location question should be asked explicitly and in the same letter.
