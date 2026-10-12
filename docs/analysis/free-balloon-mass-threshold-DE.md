# Free (unmanned) balloon mass thresholds — German law

**Purpose.** Determine, for a small unmanned free balloon ("pico balloon") payload designed
and launched in **Germany**, whether a mass threshold exists below which a launch needs no
permission, and — critically — **what quantity such a threshold counts**.

**Question under test.** The operator's working assumption is that a **total payload mass
under 20 g** means "we don't need permission to fly it". This document tests that assumption
against primary sources.

**Method / sources.** German federal statutes in their consolidated official form on
`gesetze-im-internet.de` (LuftVG, LuftVO, LuftVZO — full-act HTML, which carries the
*"zuletzt geändert durch …"* version line), the directly applicable EU instruments on
EUR-Lex (DVO (EU) Nr. 923/2012 "SERA", DVO (EU) 2019/947, VO (EU) 2018/1139), the German
state aviation authority's own service page and its official application form, the federal
service portal *verwaltung.bund.de*, the German ANSP (DFS) service pages, the Bundesnetzagentur's
current general assignment **Vfg. 91/2025** (PDF), and CEPT ERC/REC 70-03 as the harmonisation
basis behind it.

**Access date for every URL below: 2026-10-07.** Anything I could not confirm is marked
**`TODO(unverified)`**; the marker is used only for that meaning. Quoted German wording is
verbatim from the source named; translations are my own and marked as such.
This is private working notes, not legal advice.

---

## 1. At a glance

| # | Requirement | Instrument | Threshold that switches it on | **Applies at 20 g payload?** | Applies to a 20 g *whole-balloon* design? |
|---|---|---|---|---|---|
| 1 | **Aviation permission to launch** (*Erlaubnis*) | LuftVO § 20 Abs. 1 Nr. 6 (national) + SERA Anlage 2 Nr. 2.1 (EU) | **None — no de-minimis mass.** Any *unbemannter Freiballon* | **YES** | **YES** |
| 2 | **ATC clearance** (*Flugverkehrskontrollfreigabe*) | LuftVO § 21 Abs. 1 Nr. 4 | class *mittelschwer/schwer* = payload ≥ 4 kg; or class *leicht* **inside a Flugplatzkontrollzone** with **Gesamtmasse (Ballonhülle und Ballast) > 500 g** | **NO** (payload < 4 kg; and envelope+ballast ≤ 500 g) | **NO** (envelope+ballast ≤ 500 g) |
| 3 | **Advance notification to ATS (≥ 7 days) + post-launch reports** | SERA Anlage 2 Nr. 5.1.1, 5.2.1, 5.3.1, 6.5 | only *mittelschwere oder schwere* balloons (payload ≥ 4 kg) | **NO** | **NO** |
| 4 | **No-hazard-on-impact duty** | SERA Anlage 2 Nr. 2.5 | none | **YES** | **YES** |
| 5 | **Marking of a tow antenna** (if one is used) | SERA Anlage 2 Nr. 3.5 | tow line break-force > 230 N | likely **NO** at this scale | likely **NO** |
| 6 | **Owner name + address on the balloon** | LuftVZO § 19 Abs. 3 | *Startmasse* > 5 kg | **NO** | **NO** |
| 7 | **Liability insurance** | LuftVG § 43 (+ in practice demanded with the Erlaubnis application) | none stated | **YES** (as an application document) | **YES** |
| 8 | **Radio licence-exemption limits** | BNetzA Vfg. 91/2025 | 1 mW / 10 mW ERP @ 433 MHz; 10 mW / 100 mW EIRP @ 2.4 GHz, each with conditions | **YES — conditions apply** | **YES — conditions apply** |
| 9 | **Amateur-radio licence** (if transmitting on amateur bands, e.g. APRS) | amateur-radio law | none | only if amateur bands are used | only if amateur bands are used |

**The single decision-relevant sentence:** the 20 g figure is **not a legal threshold in
German law**. There is **no** mass below which launching an unmanned free balloon needs no
permission; the permission requirement in LuftVO § 20 Abs. 1 Nr. 6 has no de-minimis. The
"500 g / 0.5 kg" figure that *does* exist attaches to a **different** requirement (ATC
clearance inside a control zone) and counts a **different** quantity — *Ballonhülle und
Ballast* (envelope and ballast), not payload. A design built to a "20 g total" target is
therefore not designed to any threshold that exists, and would still need the permit.

---

## 2. Q1 — What authorisation is required, and under which instrument

### 2.1 A free balloon is an aircraft

Framework statute is the **Luftverkehrsgesetz (LuftVG)**:

> **§ 1 Abs. 2 LuftVG** — "Luftfahrzeuge sind … 6. Frei- und Fesselballone …"
> *(translation: aircraft are … 6. free and captive balloons …)*
> — https://www.gesetze-im-internet.de/luftvg/BJNR006810922.html

Airspace use is in principle free (§ 1 Abs. 1 LuftVG) *unless* restricted by the Act itself,
its implementing ordinances, applicable international law, or EU acts. The relevant restriction
is in the ordinance, below.

The permits for airspace use by balloons are expressly assigned to the **Länder** acting for
the Federation:

> **§ 31 Abs. 2 LuftVG, Nr. 16 lit. e** — "Die Länder führen nachstehende Aufgaben dieses
> Gesetzes im Auftrage des Bundes aus: … 16. die Erteilung der Erlaubnis zu besonderer
> Benutzung des Luftraums für … e) den Aufstieg von Frei- und Fesselballonen … mit Ausnahme
> der Erlaubnisse, die vom Bundesaufsichtsamt für Flugsicherung oder der Flugsicherungsorganisation
> erteilt werden;" — same URL as above.

### 2.2 The operative national provision: **LuftVO § 20 Abs. 1 Nr. 6**

> **§ 20 Abs. 1 LuftVO** — "Die folgenden Arten der Nutzung des Luftraums bedürfen der Erlaubnis:
> … **6. der Betrieb von unbemannten Freiballonen nach Anlage 2 der Durchführungsverordnung
> (EU) Nr. 923/2012 im Hoheitsgebiet der Bundesrepublik Deutschland.**"
>
> **§ 20 Abs. 2 LuftVO** — "Zuständige Behörde für die Erteilung der Erlaubnis nach Absatz 1
> ist die örtlich zuständige Luftfahrtbehörde des Landes."
>
> — https://www.gesetze-im-internet.de/luftvo_2015/BJNR189410015.html

*(translation: "The following kinds of airspace use require a permit: … 6. the operation of
unmanned free balloons under Annex 2 of Implementing Regulation (EU) No 923/2012 within the
territory of the Federal Republic of Germany." / "The competent authority for granting the
permit under paragraph 1 is the locally competent aviation authority of the Land.")*

The addressee therefore is the **Landesluftfahrtbehörde** (state aviation authority), not a
federal body. Confirmed by the authority's own documents, § 6 below.

### 2.3 Current versions in force (this is the "is it still in force?" receipt)

Read from the version lines of the consolidated acts on `gesetze-im-internet.de`
(access 2026-10-07):

| Act | Version line (verbatim) |
|---|---|
| LuftVG | "Luftverkehrsgesetz in der Fassung der Bekanntmachung vom 10. Mai 2007 (BGBl. I S. 698), das zuletzt durch Artikel 9 des Gesetzes vom 22. Juli 2026 (BGBl. 2026 I Nr. 224) geändert worden ist" |
| **LuftVO** | "Luftverkehrs-Ordnung vom 29. Oktober 2015 (BGBl. I S. 1894), die zuletzt durch Artikel 28 des Gesetzes vom 18. Dezember 2025 (BGBl. 2025 I Nr. 347) geändert worden ist" |
| LuftVZO | "Luftverkehrs-Zulassungs-Ordnung vom 19. Juni 1964 (BGBl. I S. 370), die zuletzt durch Artikel 28 der Verordnung vom 11. Dezember 2024 (BGBl. 2024 I Nr. 411) geändert worden ist" |

The balloon item **is** in the in-force text of § 20 Abs. 1 LuftVO as set out in § 2.2 — i.e.
it is not a repealed provision. Annex 2 of DVO (EU) 923/2012 (the classification in § 2.2 Nr. 1.1)
is likewise live EU law.

### 2.4 Correction to a premise in the brief: **do not cite LuftVO § 16**

In today's LuftVO, **§ 16 is "Luftraumordnung"** (airspace structure) and has nothing to do
with balloons or with the 2017 drone rules; the drone provisions are **§§ 21a–21k LuftVO**
("Abschnitt 5a — Betrieb von unbemannten Fluggeräten"). See the act's table of contents:
https://www.gesetze-im-internet.de/luftvo_2015/ (TOC) and the consolidated text above.

The historical § 16 was a *different* § 16: in the pre-2015 LuftVO it was titled
"**Erlaubnisbedürftige Nutzung des Luftraums**" (i.e. today's § 20 content) and it listed
kites, fireworks, tethered balloons, self-propelled unguided flying bodies, searchlights and
*unbemannte Luftfahrtsysteme* — **but not unmanned free balloons**:

> **§ 16 Abs. 1 LuftVO (old, as archived 2014-06-01)** — "Die folgenden Arten der Nutzung des
> Luftraums bedürfen im Übrigen der Erlaubnis: 1. der Aufstieg von Flugmodellen a) mit mehr
> als 5 Kilogramm Gesamtmasse, b) mit Raketenantrieb, sofern der Treibsatz mehr als 20 Gramm
> beträgt … 4. der Aufstieg von Fesselballonen, wenn sie mit einem Halteseil von mehr als
> 30 Metern Länge gehalten werden, … 7. der Aufstieg von unbemannten Luftfahrtsystemen."
> — https://web.archive.org/web/20140601000000/http://www.gesetze-im-internet.de/luftvo/__16.html
> (Wayback snapshot of the then-current consolidated text; access 2026-10-07)

Consequence: the **blanket permit requirement for unmanned free balloons is a creation of the
2015 LuftVO re-cast** (which implemented SERA), not of the 2017 drone amendment. Citing "§ 16
LuftVO" for balloons today is wrong in both directions: wrong section, and wrong era.

### 2.5 What does *not* govern it

* **Not the UAS rules.** Not DVO (EU) 2019/947, and not LuftVO §§ 21a–21k (see § 5).
* **Not the LuftVZO's Zulassung rules.** LuftVZO § 1 Abs. 1 (Musterzulassung) and § 6 Abs. 1
  (Verkehrszulassung) list "*bemannte* Ballone" — manned balloons only. Unmanned free balloons
  are therefore **not** subject to Luftfahrzeug-type/verkehrs certification. The repealed
  LuftVZO "Zweiter Abschnitt" (§§ 20 bis 37 *weggefallen*) is not relevant. The one LuftVZO
  rule that does touch unmanned balloons is the marking duty, § 19 Abs. 3 (see § 4.4).

---

## 3. Q2 — Is there a mass threshold below which no authorisation is needed?

**No.** In the in-force text of LuftVO § 20 Abs. 1 Nr. 6 the authorisation requirement for
"der Betrieb von unbemannten Freiballonen nach Anlage 2 der Durchführungsverordnung (EU)
Nr. 923/2012" carries **no mass qualifier, no class qualifier and no de-minimis exception**.
It is a blanket requirement, and the Authority states it as such in the present tense and
without qualification:

> **Niedersachsen, Luftfahrtbehörde** (strassenbau.niedersachsen.de) — "Der Betrieb von einem
> unbemannten Freiballon/Wetterballon bedarf gemäß §§ 19, 20 LuftVO **immer** einer Erlaubnis."
> — https://www.strassenbau.niedersachsen.de/startseite/aufgaben/luftverkehr/besondere_benutzung_des_luftraums/besondere-benutzung-des-luftraums-78492.html

> **verwaltung.bund.de** (the joint federal/state service directory), service "Unbemannter
> Freiballon; Beantragung einer Aufstiegserlaubnis" — "Für den Betrieb von unbemannten
> Freiballonen ('Wetterballon') ist eine Erlaubnis erforderlich."
> — https://verwaltung.bund.de/leistungsverzeichnis/de/leistung/99080107005001

> **Luftfahrtbehörde M-V**, official application form *Antrag auf Erteilung einer
> Aufstiegserlaubnis für den Aufstieg unbemannter Freiballone*, Rev. 1, Stand 15.6.2023 —
> "Hiermit beantrage ich die Erlaubnis für den Aufstieg eines unbemannten Freiballons" and,
> under "3. Angaben zum unbemannten Freiballon": "Klassifizierung gemäß SERA Anlage 2 Nr. 1.1
> der DVO (EU) 923/2012 – bitte ankreuzen ☐ leicht ☐ mittelschwer ☐ schwer".
> — https://www.regierung-mv.de/static/Regierungsportal/Ministerium%20f%C3%BCr%20Wirtschaft%2C%20Arbeit%20und%20Gesundheit/Dateien/Downloads/09_1_Antrag_auf_Erteilung_einer_Aufstiegserlaubnis_f%C3%BCr_den_Aufstieg_unbemannter_Freiballone.pdf

The form is decisive on the threshold question: the authority's own form requires the applicant
to self-classify as *leicht / mittelschwer / schwer* and then applies **one and the same**
procedure. A *leicht* balloon is a form of unmanned free balloon, so the *Erlaubnis* is
required for it too.

**Every mass figure that actually appears in the LuftVO** (exhaustive grep of the in-force
consolidated text, 2026-10-07) is listed below so that the absence of a balloon de-minimis is
a *documented* absence:

| Figure | § | Subject |
|---|---|---|
| 5 700 kg | § 8 Abs. 5, § 9 | start bans / occurrence reporting, commercial aircraft |
| 5 700 kg / 34 000 kg / … | § 26, § 9 | jet aircraft limits |
| **0,5 kg** | § 21 Abs. 1 Nr. 1 | parachute + ballast mass, ATC clearance |
| **500 g** | **§ 21 Abs. 1 Nr. 4 lit. b** | **light balloon, envelope + ballast, inside a control zone → ATC clearance** |
| 2 kg / 12 kg / **20 g** | § 21f Abs. 3 | model aircraft (≥2 kg knowledge, >12 kg permit, **>20 g rocket propellant → permit**) |
| 0,25 kg | § 21h Abs. 3 Nr. 7 lit. b | drone over residential property |
| 25 kg | § 21k Abs. 1 | drones operated by emergency authorities |

There is **no "20 g" balloon threshold** anywhere in the LuftVO. The only literal *"20 Gramm"*
in German aviation law is § 21f Abs. 3 Nr. 2 — the propellant charge of a **rocket-powered
model aircraft**, an unrelated subject, and the only candidate I found for the origin of the
misremembered figure (that it is the operator's source is **`TODO(unverified)`** — I have no
evidence for where his number came from).

---

## 4. Q3 — What do the thresholds count? (the critical detail)

Three different quantities are in play, and they are **not** interchangeable.

### 4.1 The class thresholds count **payload mass (*Nutzlast*) — not total mass**

DVO (EU) Nr. 923/2012 (**SERA**), **Anlage 2 "Unbemannte Freiballone", Nr. 1.1**, verbatim:

> "**1.1.** Unbemannte Freiballone sind zu klassifizieren als (siehe Abbildung AP2-1):
> **a) leicht:** ein unbemannter Freiballon mit einer **Nutzlast** von einem oder mehr Paketen
> mit einer **Gesamtmasse von weniger als 4 kg**, sofern er nicht gemäß Buchstabe c Nummer 2, 3
> oder 4 als schwerer Ballon einzustufen ist, oder
> **b) mittelschwer:** ein unbemannter Freiballon mit einer **Nutzlast** von zwei oder mehr
> Paketen mit einer **Gesamtmasse von 4 kg bis unter 6 kg**, sofern er nicht gemäß Buchstabe c
> Nummer 2, 3 oder 4 als schwerer Ballon einzustufen ist, oder
> **c) schwer:** ein unbemannter Freiballon mit einer Nutzlast:
> 1. mit einer Gesamtmasse von 6 kg oder mehr oder
> 2. mit einem Paket mit einer Masse von 3 kg oder mehr oder
> 3. mit einem Paket mit einer Masse von 2 kg oder mehr und einer **Flächendichte von mehr als
> 13 g je Quadratzentimeter** … oder
> 4. bei der ein Seil oder eine andere Vorrichtung zur Befestigung der Nutzlast verwendet wird,
> die für die Loslösung der angehängten Nutzlast vom Ballon eine **Zugkraft von 230 N** oder
> mehr erfordert."
> — https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32012R0923
> (fetched 2026-10-07 via the r.jina.ai reader proxy; EUR-Lex refused plain `curl` with HTTP 202/empty)

The associated figure in the same annex is captioned "**MERKMALE / MASSE DER NUTZLAST (kg)**"
and "SEIL oder ANDERE AUFHÄNGUNG / 230 N oder MEHR" — i.e. the axes are **payload mass** and
release force.

Answer to the question as asked: **the classification thresholds count payload ("Nutzlast"),
i.e. (a) — the packages the balloon carries, not the whole assembly.** The **envelope
(*Ballonhülle*), the lifting gas and any ballast are NOT part of the class number**; the film
and the gas appear nowhere in Nr. 1.1. Solar panels, antennae and electronics are part of the
payload *packages* if they are carried as payload, so they **do** count toward the *Nutzlast* —
but at 20 g design scale this is irrelevant, because 20 g ≪ 4 kg and the balloon is *leicht*
by an enormous margin.

Definition relied on for "Freiballon" (SERA, Artikel 2 Nr. 138):
> "**unbemannter Freiballon**: ein nicht angetriebenes, unbemanntes Luftfahrzeug leichter als
> Luft im freien Flug" — same URL.

### 4.2 The **500 g** figure counts **envelope + ballast**, not payload

**LuftVO § 21 Abs. 1 Nr. 4** verbatim:

> "Vor der Nutzung des kontrollierten Luftraums und des Luftraums über Flugplätzen mit
> Flugverkehrskontrollstelle ist bei der zuständigen Flugverkehrskontrollstelle eine
> Flugverkehrskontrollfreigabe einzuholen für … **4. Aufstiege von unbemannten Freiballonen,
> insbesondere Wetterballonen, folgender Klassen im Sinne von Anlage 2 Ziffer 1.1 der
> Durchführungsverordnung (EU) Nr. 923/2012: a) schwer und mittelschwer, b) leicht, sofern der
> Aufstiegsort innerhalb von Flugplatzkontrollzonen liegt und die Gesamtmasse (Ballonhülle und
> Ballast) mehr als 500 Gramm beträgt,**"
> — https://www.gesetze-im-internet.de/luftvo_2015/BJNR189410015.html

So the only "500 g"-style figure in German balloon law:

* is **not** an authorisation exemption — it is a de-minimis for the **additionally required
  ATC clearance** (§ 21), and only **inside a *Flugplatzkontrollzone*** (CTR);
* counts "**Gesamtmasse (Ballonhülle und Ballast)**" — literally *envelope and ballast*. It does
  **not** say "Nutzlast". On the ordinary reading of the words, the class-defining payload mass
  (§ 4.1) and this mass are **different quantities**, and this is the reading that makes the two
  provisions consistent (a balloon can be *leicht* — payload < 4 kg — while its envelope+ballast
  is under 500 g).
* The term **"Ballast"** is not defined in the LuftVO text I read. Whether it is intended to
  include the payload ("Gesamtmasse inkl. Nutzlast", as the M-V form calls a third, distinct
  field) is **`TODO(unverified)`** — see § 9. For a 20 g class design it changes nothing: any
  plausible reading keeps the whole assembly under 500 g, so no ATC clearance is triggered in a
  CTR either.

### 4.3 The authority's form shows the authority itself treats these as separate quantities

The official M-V form asks, in the same data block, for all of:

> "Gesamtmasse des Ballons: … **Gesamtmasse der Pakete (Anhang)**: … **Gesamtmasse inkl.
> Nutzlast**: … Steigrate [m/s]: … Sinkrate [m/s]: … Flächendichte [g/cm²]: … **Zugkraft, die
> für die Loslösung der Nutzlast gemäß SERA Anlage 2 Nr. 1.1 c) 4, erforderlich ist** ☐ < 230 N
> ☐ ≥ 230 N … Anzahl der Nutzlastpakete: … Material des Ballons: … Füllung des Ballons: …
> Durchmesser: …"
> — M-V form, page 2 (URL in § 3)

That the *Landesluftfahrtbehörde* separates "Gesamtmasse des Ballons", "Gesamtmasse der Pakete"
and "Gesamtmasse inkl. Nutzlast" is the practical confirmation that a single "balloon mass"
number does not exist: the classification uses payload, the CTR de-minimis uses
envelope+ballast, and the applicant has to give all of them.

### 4.4 The 5 kg figure counts **Startmasse** (whole launch mass)

> **§ 19 Abs. 3 LuftVZO** — "(3) Der Eigentümer eines unbemannten Ballons oder Drachens mit
> jeweils einer **Startmasse von mehr als 5 Kilogramm** sowie eines Flugkörpers mit Eigenantrieb
> muss vor dem erstmaligen Betrieb an sichtbarer Stelle seinen Namen und seine Anschrift in
> dauerhafter und feuerfester Beschriftung an dem Fluggerät anbringen."
> — https://www.gesetze-im-internet.de/luftvzo/BJNR003700964.html

Here the counted quantity is explicitly the **whole launch mass** (*Startmasse*), not payload —
and it is a **marking** duty, not an authorisation.

> **Bottom line for the design question:** a "20 g" figure, if it is a **payload** number, is
> compared against the *Nutzlast* thresholds (< 4 kg *leicht*) — trivially satisfied — and is
> **not** the number that decides authorisation, because authorisation has no mass threshold at
> all. If the 20 g were meant as a **whole-balloon** number, it is compared against the
> envelope+ballast 500 g CTR de-minimis — also trivially satisfied. Either way the 20 g target
> achieves nothing that a 400 g or 1 kg design would not also achieve, and neither of them
> removes the *Erlaubnis* requirement.

---

## 5. Q4 — EU level and international baseline

### 5.1 The UAS Regulation does **not** explicitly exclude balloons — it excludes them by definition

* DVO (EU) 2019/947 contains **no mention of balloons at all** (full-document check for
  "Ballon"/"Freiballon" in the German text: zero hits).
  https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32019R0947 (via reader proxy, 2026-10-07)
* Its scope is UAS: Art. 1 — "Diese Verordnung enthält detaillierte Bestimmungen für den Betrieb
  **unbemannter Luftfahrzeugsysteme** …".
* Its definition (Art. 2 Nr. 1) — "**'unbemanntes Luftfahrzeugsystem' (unmanned aircraft system,
  UAS): ein unbemanntes Luftfahrzeug sowie die Ausrüstung für dessen Fernsteuerung**" *(an
  unmanned aircraft **and the equipment for its remote control**)*.
* The parent definition in VO (EU) 2018/1139, Art. 3 — "'**unbemanntes Luftfahrzeug**' bezeichnet
  ein Luftfahrzeug, das ohne einen an Bord befindlichen Piloten **autonom oder ferngesteuert**
  betrieben wird oder dafür konstruiert ist" *(operated or designed to be operated autonomously
  or remotely piloted, without a pilot on board)*.
  https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32018R1139 (via reader proxy, 2026-10-07)

A free balloon carries **no equipment for its remote control** and is neither remotely piloted
nor "autonomous" in this sense: it drifts. It therefore falls outside the UAS definition, and
the EU instrument that actually governs it is the **SERA** regulation:

> **SERA (DVO (EU) Nr. 923/2012), Anlage 2, Nr. 2.1** — "Ein unbemannter Freiballon darf nur
> mit der Genehmigung des Staates betrieben werden, in dem der Aufstieg erfolgt."
>
> **ibid. Nr. 2.2** — "Ein unbemannter Freiballon, bei dem es sich nicht um einen leichten
> Ballon zur ausschließlichen Nutzung für meteorologische Zwecke in einer von der zuständigen
> Behörde vorgeschriebenen Weise handelt, darf über dem Hoheitsgebiet eines anderen Staates nur
> mit Genehmigung dieses betreffenden Staates betrieben werden."
>
> **SERA.3140** — "Ein unbemannter Freiballon ist so zu betreiben, dass Gefahren für Personen,
> Sachen oder andere Luftfahrzeuge so gering wie möglich sind, und es sind die in Anlage 2
> festgelegten Bedingungen einzuhalten."

Note carefully what Nr. 2.2 does and does not do: the exemption for a *light balloon used
exclusively for meteorological purposes* is a carve-out from **the overflown State's**
permission (Nr. 2.2 / 2.3) — it is **not** an exemption from the permission of the **launch
State** under Nr. 2.1. Germany's § 20 Abs. 1 Nr. 6 reproduces precisely the Nr. 2.1 duty.

**Caveat, stated as a caveat:** the *exclusion of free balloons from the UAS regime* is
established above **definitionally**, from the two definitions plus the absence of any balloon
mention. I did **not** find an official EASA sentence saying "free balloons are not UAS", and I
searched for one. Treat "there is no explicit exclusion clause; the exclusion is definitional"
as the finding. An explicit EASA/Commission statement on the point is **`TODO(unverified)`**.

### 5.2 Only balloon entry in the Basic Regulation: *manned* balloons

VO (EU) 2018/1139, Anhang I (aircraft excluded from that Regulation) contains:
> "Ballone und Luftschiffe mit einem oder zwei Plätzen und einem bauartbedingten maximalen
> Volumen von höchstens 1 200 m³ im Fall von Heißluft und 400 m³ im Fall anderer Traggase"
> — same URL as § 5.1. That is a *manned* balloon/item, and it is not the source of the German
> rule. Noted only to close off the search.

### 5.3 ICAO baseline

SERA's Anlage 2 is the EASA/EU transposition of the ICAO Annex 2 appendix on unmanned free
balloons: same class names (*light / medium / heavy*), same payload-mass boundaries (4 kg / 6 kg)
and the same 230 N release-force criterion. I did not open ICAO Annex 2 itself (not freely
available); the correspondence is **inference from the identical structure**, and the exact
ICAO paragraph numbers are **`TODO(unverified)`**. For German practice it is irrelevant — the
SERA text is directly applicable and is what LuftVO § 20 Abs. 1 Nr. 6 points to.

---

## 6. Q5 — Splitting "permission to fly" into the distinct requirements

The operator's phrase covers at least six separate legal requirements. They are separate
instruments, separate addressees and separate thresholds **`[separated]`**:

**(a) Aviation permission to launch (*Erlaubnis*, i.e. "permission to fly").**
LuftVO § 20 Abs. 1 Nr. 6 + SERA Anlage 2 Nr. 2.1. Addressee: **örtlich zuständige
Luftfahrtbehörde des Landes** (LuftVO § 20 Abs. 2). No mass threshold. Procedure and required
documents (per the M-V form and the LuftVO § 20 Abs. 3 discretion): ID copy; **proof of liability
insurance**; map/site plan with the launch site marked; **written consent of the landowner**;
where applicable the ATC clearance. The M-V form also records whether the balloon carries
**GPS position-determining and recording equipment** and whether the **name and address marking**
is present. **A 20 g payload does not avoid this.**

**(b) ATC clearance (*Flugverkehrskontrollfreigabe*).**
LuftVO § 21 Abs. 1 Nr. 4; addressee: the **zuständige Flugverkehrskontrollstelle**; the person
responsible for obtaining it is "**der Starter des unbemannten Freiballons**"
(§ 21 Abs. 2 Nr. 4). Trigger: *schwer/mittelschwer*, or *leicht* **inside a Flugplatzkontrollzone**
with envelope+ballast > 500 g. The M-V form flags it as "sofern erforderlich … **rechtzeitig vor
dem Start, nach Möglichkeit 14 Tage vor dem geplanten Starttermin** zu beantragen". **A 20 g
design satisfies the de-minimis here** — this is the *only* place a small mass helps, and only
inside a CTR.

**(c) Advance notification to ATS and in-flight reporting (SERA Anlage 2 Nr. 5–6).**
Nr. 5.1.1: "Die frühzeitige Anmeldung des geplanten Flugs eines **mittelschweren oder schweren**
unbemannten Freiballons ist bei der zuständigen Flugverkehrsdienststelle **mindestens sieben
Tage im Voraus** vorzunehmen." Plus Nr. 5.2.1 (report immediately after launch), 5.3.1
(cancellation), 6.5 (termination). All of these are limited to medium/heavy balloons, so a
*leicht* balloon (payload < 4 kg) has **no** notification duty under Anlage 2. **Applies at 20 g:
no.**

**(d) Airspace coordination / NOTAM.**
The German ANSP **DFS** operates a dedicated AIS-Portal service "**Unmanned free balloon**"
(alongside "Toy balloons" and "Air drones") and publishes a NOTAM-office contact; that is the
working channel for the clearance in (b) and for any publication of the flight.
— https://bnl.dfs.de/pilotservice/bnl/leisure/ufb/ufb_edit.jsp and
https://www.dfs.de/homepage/de/services/freizeitaktivitaeten-und-genehmigungen/
Whether a NOTAM is issued **mandatorily** for a *light* balloon (as opposed to the clearance
being recorded another way) I did not confirm — **`TODO(unverified)`**. Note separately that DFS
directs laser/high-power searchlight and sky-lantern matters to the Land authority, and states:
"Der Aufstieg von Himmelslaternen ist in Deutschland aus Brandschutzgründen verboten."

**(e) Insurance.**
LuftVG § 43: "(2) Der Halter eines Luftfahrzeugs ist verpflichtet, zur Deckung seiner Haftung
auf Schadensersatz nach diesem Unterabschnitt eine Haftpflichtversicherung in einer durch
Rechtsverordnung zu bestimmenden Höhe zu unterhalten"; § 37 Abs. 1 lit. a caps liability for
"Luftfahrzeuge unter 500 Kilogramm Höchstabflugmasse" at 750 000 Rechnungseinheiten.
Unmanned free balloons are **not** subject to Verkehrszulassung (LuftVZO § 1 / § 6 list only
"bemannte Ballone"), so whether the LuftVZO §§ 102 ff. minimum-amount table applies to them,
and what the minimum cover for a sub-500 g balloon actually is, is **`TODO(unverified)`** — but
the *practical* duty is not in doubt: the official application form requires a
"**Versicherungsnachweis der Haftpflichtversicherung**" as a mandatory attachment. **Applies at
20 g: yes** (as an application document).

**(f) Radio.** See § 7 — a general assignment (licence-exempt) *power* regime, plus, if amateur
bands are used, a personal amateur-radio licence. This is a **separate** regime from aviation
law; a balloon may be perfectly legal aviation-wise and still over the radio limit.

**(g) Other regimes that are neither.** Land nature-protection/landscape rules; municipal rules;
the sky-lantern prohibition (Landesrecht/fire protection, per DFS above); and — for drones only,
not balloons — the drone geo-zone and registration rules of LuftVO §§ 21h/21i and LuftVG § 66a
(the "**250 g**" registration figure and the "**0,25 kg**" geo-zone figure are **drone**
figures and do **not** apply to unmanned free balloons).

---

## 7. Q6 — Radio: licence-exempt limits in Germany

**The instrument in force is the Bundesnetzagentur's general assignment (Allgemeinzuteilung)
of frequencies for short-range devices, Vfg. 91/2025 (November 2025)** — the current consolidated
SRD assignment, which implements Commission Decision 2006/771/EC as last amended by Implementing
Decision (EU) 2025/105, and which **repeals** the former Vfg. 133/2019 (as amended by Vfg.
12/2020) and the separately-issued assignments, **including Amtsblattverfügung 128/2023 for
2400–2483.5 MHz WLAN**.
— https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf?__blob=publicationFile&v=3
(PDF, Bundesnetzagentur; PDF created 2025-11-03, modified 2025-11-18; listed on
https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/start.html
as the current SRD assignment). Under § 210 S. 3 TKG it is deemed notified two weeks after
publication.

### 7.1 433 MHz — **10 mW ERP is conditional, not the plain limit**

Verbatim from Tabelle 2 of Vfg. 91/2025 (the `*` marks a national deviation listed again in
Tabelle 3 as D44a/D44b/D45c):

| Band Nr. | Frequenzband | Kategorie | Max. Sendeleistung | Zusatzbedingung |
|---|---|---|---|---|
| **44a** | 433,05–434,79 MHz | "Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen" | **1 mW (ERP)** | *(none)* |
| **44b** | 433,05–434,79 MHz | same | **10 mW (ERP)** | **"Arbeitszyklus: ≤ 10 %"** |
| **45c** | 434,04–434,79 MHz | same | **10 mW (ERP)** | "Arbeitszyklus ≤ 100 % bei einer Bandbreite ≤ 25 kHz" |

Tabelle 3 lists the same at national level: "D44a / D44b / D45c — 433,05-434,79 MHz — 10 mW (ERP)"
with the "Sonstige Nutzungsbeschränkungen" column **empty** (i.e. no further restriction, and in
particular **no airborne restriction**).

**Verification of the design figure.** "433 MHz at ≤ 10 mW ERP" is **correct only if the
transmitter also meets the duty-cycle condition of entry 44b (≤ 10 %) — or operates within
434,04–434,79 MHz at ≤ 25 kHz bandwidth (45c)**. A transmitter that is on continuously
(telemetry beacon, or a packet burst that exceeds a 10 % long-term duty cycle) exceeds the
general assignment as 44b. The unconditional limit in the whole 433,05–434,79 MHz band is
**1 mW ERP (44a)**. Whether the specific design's duty cycle qualifies for 44b/45c is
**`TODO(unverified)`** — it is a property of the firmware, and if in doubt the compliant ceiling
is 1 mW ERP.

These figures match the harmonisation basis exactly: CEPT ERC/REC 70-03 Annex 1, entries
`f` = 433.050–434.790 MHz, 10 mW e.r.p., duty cycle < 10 % (note 1); `f1` = same band, 1 mW
e.r.p., no requirement; `f2` = 434.040–434.790 MHz, 10 mW e.r.p., no duty-cycle requirement, up
to 25 kHz spacing. (Copy consulted: https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf
— a national regulator's mirror of the CEPT recommendation; the binding German text is Vfg. 91/2025.)

### 7.2 2.4 GHz — 100 mW EIRP is for *broadband data* devices only

Verbatim from Vfg. 91/2025 Tabelle 2:

| Band Nr. | Frequenzband | Kategorie | Max. Sendeleistung | Zusatzbedingung |
|---|---|---|---|---|
| **57a** | 2 400–2 483,5 MHz | "Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen" | **10 mW (EIRP)** | — |
| **57b** | 2 400–2 483,5 MHz | Funkortungsgeräte | 25 mW (EIRP) | — |
| **57c\*** | 2 400–2 483,5 MHz | **Breitband-Datenübertragungsgeräte** | **100 mW (EIRP)** und Leistungsdichte 100 mW/100 kHz (EIRP) bei Frequenzsprungmodulation; 10 mW/MHz (EIRP) bei anderen Modulationsarten | "Es gelten Anforderungen an Frequenzzugangs- und Störungsminderungstechniken [7]." |

Tabelle 3 restates this nationally as "**D57c** — 2 400-2 483,5 MHz — **WLAN** — 100 mW (EIRP)
…" with the anti-jamming note ("Aussendungen, die absichtlich bestimmungsgemäße WLAN-Nutzungen
stören oder verhindern … sind nicht gestattet") and footnote **[7]** requiring frequency-access
and interference-mitigation techniques meeting at least the essential requirements of Directive
2014/53/EU (or the FuAG).

**Verification of the design figure.** "2.4 GHz at ≤ 100 mW EIRP" is **confirmed as the ceiling**
— but the 100 mW tier is a **broadband data transmission** (WLAN-type) category, carrying power
*density* limits and frequency-access obligations. A **narrowband low-rate telemetry link**
(frequency-hopping beacon, LoRa-like or proprietary FSK) is not a
"Breitband-Datenübertragungsgerät" and belongs in entry **57a (10 mW EIRP)**. Whether the design
qualifies for 57c/D57c is **`TODO(unverified)`** — it depends on bandwidth and modulation; if it
does not, the compliant ceiling is 10 mW EIRP.

Also relevant: ERC/REC 70-03 Annex 3 entry `a` = 2400.0–2483.5 MHz, 100 mW e.i.r.p., "For wide
band modulations other than FHSS, the maximum e.i.r.p. density is limited to 10 mW/MHz" — the
same shape as Vfg. 91/2025 entry 57c.

### 7.3 Airborne / mobile operation — different limit from ground use?

**In the German general assignment: no.** For both bands the "Sonstige Nutzungsbeschränkungen"
column of the entries actually concerned (44a/44b/45c; 57a/57c/D57c) contains **no airborne
restriction and no mobile-vs-fixed distinction**. The only airborne-specific material in
Vfg. 91/2025 is footnote **[d]**, which defines "**Modellsteuerungsgeräte**" as "eine besondere
Art funktechnischer Fernsteuerungs- und Fernmessgeräte, die zur Steuerung der Bewegung von
Modellen (vorwiegend Miniaturnachbildungen von Fahrzeugen bzw. **Flugzeugen**) **in der Luft**,
an Land sowie auf oder unter der Wasseroberfläche eingesetzt werden" — and footnote [d] is
attached (as a duty-cycle relaxation) to the **27 MHz** model-control entries, not to
433 MHz or 2.4 GHz. Footnote **[4]** (radio-astronomy / helicopter obstacle-radar protection
zones) is the only other aviation-related entry.

The harmonisation basis says the same, explicitly:

> CEPT ERC/REC 70-03, general text — "The CEPT has considered the use of SRD devices on board
> aircraft and it has concluded that, from the CEPT regulatory perspective, **such use is allowed
> under the same conditions provided in the relevant Annex** of Recommendation 70-03. **For
> aviation safety aspects, the CEPT is not the right body to address this matter** which remains
> the responsibility of aircraft manufacturers or aircraft owners who should consult with the
> relevant national or regional aviation bodies before the installation and use of such devices
> on board aircraft."

So the honest answer: **radio-wise, no separate airborne power limit was found for the 433 MHz
or 2.4 GHz licence-exempt bands; the same ERP/EIRP and duty-cycle/PSD conditions apply.** The
aviation-safety side of carrying a transmitter aloft is governed by aviation law (the items in
§ 6), not by the radio general assignment. Whether EFIS or the German Frequenzplan carry a
country-specific airborne note for these bands is **`TODO(unverified)`** — I searched Vfg. 91/2025
and ERC/REC 70-03 and found none, but I did not read the Frequenzplan's per-band
"Nutzungsbestimmungen".

---

## 8. Bottom line for a hobbyist

1. **Your 20 g number is not the law's number.** German law has **no** mass threshold below
   which flying an unmanned free balloon is permission-free. "So that we don't need permission"
   is not something any mass can achieve — the *Erlaubnis* under LuftVO § 20 Abs. 1 Nr. 6 is
   required for **any** unmanned free balloon, including a 20 g one, and the authority says
   "immer" (always).
2. **Designing to 20 g is designing to nothing.** The numbers that actually matter are:
   **4 kg payload** (light→medium class boundary), **500 g of envelope+ballast *inside a control
   zone*** (turns on the extra ATC clearance), **5 kg** (marking duty), **230 N** (heavy-class
   release force). Your 20 g payload is far below 4 kg, so the balloon is class **"leicht"**; the
   *class* only decides (i) whether you need an ATC clearance and (ii) whether you need to
   pre-notify ATS 7 days ahead. "Leicht" gets you **out of** both — you do not need the 7-day
   ATS notification and, outside a control zone, no clearance at all. It does **not** get you out
   of the *Erlaubnis*.
3. **What you actually have to do**: apply to **your Land's Luftfahrtbehörde** for an
   *Aufstiegserlaubnis* before launch, with ID, proof of liability insurance, a site map and the
   landowner's written consent; inside a control zone you are *below* the 500 g de-minimis, so no
   ATC clearance is needed there either. Tag the balloon with your name and address anyway
   (required > 5 kg, expected in practice, and asked on the official form).
4. **Radio is a separate question from aviation.** 433 MHz at 10 mW ERP is only licence-exempt
   with a ≤ 10 % duty cycle (or ≤ 25 kHz bandwidth inside 434.04–434.79 MHz); the plain
   unconditional ceiling is **1 mW ERP**. 2.4 GHz at 100 mW EIRP is only for *broadband data*
   devices with the required spectrum-access techniques; a plain narrowband telemetry link is
   **10 mW EIRP**. If you use the amateur bands (e.g. APRS) you need an amateur-radio licence.
5. **Do not design to a mass figure at all.** The mass figures do not buy permission; the only
   thing they buy is relief from ATC clearance/notification for a *leicht* balloon. If the design
   goal is "no paperwork", the answer is not 20 g — it is: stay under 4 kg payload (so *leicht*),
   stay under 500 g envelope+ballast (so no CTR clearance), and still file the *Erlaubnis*.

---

## 9. `TODO(unverified)` — every figure I could not confirm

1. **`TODO(unverified)` — the operator's source for "20 g".** No primary source states any 20 g
   balloon threshold. The only "20 Gramm" in the LuftVO is the model-aircraft rocket-propellant
   figure (§ 21f Abs. 3 Nr. 2). Whether that, a hobbyist convention, or something else produced
   the figure is unknown.
2. **`TODO(unverified)` — the meaning of "Ballast"/"Gesamtmasse" in LuftVO § 21 Abs. 1 Nr. 4
   lit. b.** The primary text gives no definition. Whether the Land authorities read
   "Gesamtmasse (Ballonhülle und Ballast)" as *envelope+ballast only* (my reading) or as the
   whole assembly *including payload* is not settled by any text I could open. **Ask the
   competent Landesluftfahrtbehörde in writing** for a launch inside a CTR.
3. **`TODO(unverified)` — the exact statutory basis and minimum sum for liability insurance of
   an *unmanned* free balloon.** Applying LuftVG § 43 to an unmanned free balloon is inference
   (it is a Luftfahrzeug; § 43 speaks of the "Halter eines Luftfahrzeugs"), but the LuftVZO
   § 102 ff. minimum-amount table is keyed to aircraft requiring Verkehrszulassung, which these
   are not. The *practical* requirement (insurance proof with the application) is documented;
   the *amount* is not.
4. **`TODO(unverified)` — whether a NOTAM is mandatory for a *light* balloon.** DFS operates the
   unmanned-free-balloon service and a NOTAM office; the mandatory-publication trigger is not in
   the texts I read.
5. **`TODO(unverified)` — an explicit EASA/Commission statement that free balloons are outside
   the UAS Regulation.** The exclusion follows from the definitions (VO (EU) 2018/1139 Art. 3;
   DVO (EU) 2019/947 Art. 2 Nr. 1) and from the absence of any balloon mention in 2019/947; no
   explicit "free balloons are not UAS" sentence was located.
6. **`TODO(unverified)` — the ICAO Annex 2 paragraph numbers** corresponding to SERA Anlage 2
   (the correspondence itself is inferred from identical structure; ICAO Annex 2 was not
   retrievable free of charge).
7. **`TODO(unverified)` — whether the specific 433 MHz design meets the ≤ 10 % duty cycle of
   entry 44b (or ≤ 25 kHz bandwidth for 45c).** A firmware property; if not met, the compliant
   ceiling is 1 mW ERP (44a).
8. **`TODO(unverified)` — whether the specific 2.4 GHz design qualifies as a
   "Breitband-Datenübertragungsgerät" (entry 57c/D57c, 100 mW EIRP).** Bandwidth/modulation
   dependent; if not, the ceiling is 10 mW EIRP (57a).
9. **`TODO(unverified)` — national airborne notes for 433 MHz / 2.4 GHz in the German
   Frequenzplan or EFIS.** Vfg. 91/2025 and ERC/REC 70-03 both show none; the Frequenzplan's
   per-band "Nutzungsbestimmungen" were not read.
10. **`TODO(unverified)` — competence split between the Landesluftfahrtbehörde and the
    Bundesaufsichtsamt für Flugsicherung / Flugsicherungsorganisation** for the *Erlaubnis*
    under LuftVO § 20 Abs. 1 (LuftVG § 31 Abs. 2 Nr. 16 lit. e ends with a carve-out for permits
    issued by the BAF or the FS organisation). All official service texts and the state
    application form point the applicant to the **Land** authority.
11. **`TODO(unverified)` — the exact Amtsblatt issue/page of Vfg. 91/2025.** The PDF's own
    header reads "Vfg. 91/2025, November 2025"; the Amtsblatt number/page was not read from the
    gazette itself.
12. **Excluded as a source:** the Rheinland-Pfalz service portal page (`service.rlp.de`) sits
    behind an ALTCHA bot wall; a search snippet of it reads "benötigen Sie **immer** eine
    Erlaubnis", but the page itself could not be opened, so it is not cited as authority —
    the same statement is carried by the three sources actually opened in § 3.

---

## 10. Sources

**Tier 1 — primary instruments (consolidated official texts; all accessed 2026-10-07)**

* Luftverkehrsgesetz (LuftVG), consolidated HTML incl. version line — https://www.gesetze-im-internet.de/luftvg/BJNR006810922.html
  (§ 1 Abs. 2 Nr. 6; § 31 Abs. 2 Nr. 16 lit. e; § 31c; § 37 Abs. 1 lit. a; § 43 Abs. 2)
* Luftverkehrs-Ordnung (LuftVO) v. 29.10.2015, consolidated HTML incl. version line — https://www.gesetze-im-internet.de/luftvo_2015/BJNR189410015.html
  (§ 19, § 20 Abs. 1 Nr. 6 / Abs. 2–5, § 21 Abs. 1 Nr. 4 + Abs. 2 Nr. 4, § 21f Abs. 3 Nr. 2, §§ 21a–21k; exhaustive mass-figure scan)
* Luftverkehrs-Ordnung, table of contents — https://www.gesetze-im-internet.de/luftvo_2015/
* Luftverkehrs-Zulassungs-Ordnung (LuftVZO), consolidated HTML incl. version line — https://www.gesetze-im-internet.de/luftvzo/BJNR003700964.html
  (§ 1 Abs. 1 list incl. "bemannte Ballone"; § 6 Abs. 1; § 19 Abs. 3; §§ 101–102a)
* DVO (EU) Nr. 923/2012 (**SERA**), German text — https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32012R0923
  (Art. 2 Nr. 138 definition; SERA.3140; **Anlage 2** Nr. 1.1, 2.1–2.6, 3.5, 5.1.1, 5.2.1, 5.3.1, 6.5)
  — plain `curl` answered HTTP 202 with an empty body; retrieved through the `r.jina.ai` reader proxy.
* VO (EU) 2018/1139, German text — https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32018R1139 (Art. 3 definition "unbemanntes Luftfahrzeug"; Anhang I balloon entry) — via reader proxy
* DVO (EU) 2019/947, German text — https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32019R0947 (Art. 1; Art. 2 Nr. 1; zero balloon mentions) — via reader proxy

**Tier 1b — Bundesnetzagentur general assignment (the radio instrument)**

* **Vfg. 91/2025** — "Allgemeinzuteilung von Frequenzen zur Nutzung durch Geräte geringer
  Reichweite (SRD)", November 2025 — https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf?__blob=publicationFile&v=3
  (Tabelle 2 entries 44a/44b/45c, 57a/57b/57c; Tabelle 3 D44a/D44b/D45c, D57c; footnotes [d], [4], [7])
* BNetzA "Allgemeinzuteilungen" index — https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/start.html (via reader proxy)

**Tier 3 — official guidance from the authorities that administer the rule**

* Luftfahrtbehörde des Landes Mecklenburg-Vorpommern — *Antrag auf Erteilung einer
  Aufstiegserlaubnis für den Aufstieg unbemannter Freiballone*, Rev. 1 / Stand 15.6.2023 —
  https://www.regierung-mv.de/static/Regierungsportal/Ministerium%20f%C3%BCr%20Wirtschaft%2C%20Arbeit%20und%20Gesundheit/Dateien/Downloads/09_1_Antrag_auf_Erteilung_einer_Aufstiegserlaubnis_f%C3%BCr_den_Aufstieg_unbemannter_Freiballone.pdf
* Niedersachsen, "Besondere Benutzung des Luftraums" (Luftfahrtbehörde) —
  https://www.strassenbau.niedersachsen.de/startseite/aufgaben/luftverkehr/besondere_benutzung_des_luftraums/besondere-benutzung-des-luftraums-78492.html (via reader proxy)
* verwaltung.bund.de, service "Unbemannter Freiballon; Beantragung einer Aufstiegserlaubnis"
  (Leistung 99080107005001) — https://verwaltung.bund.de/leistungsverzeichnis/de/leistung/99080107005001
* DFS Deutsche Flugsicherung, "Freizeitaktivitäten und Genehmigungen" —
  https://www.dfs.de/homepage/de/services/freizeitaktivitaeten-und-genehmigungen/
* DFS AIS-Portal, service "Unmanned free balloon" (and "Toy balloons", "Air drones"; NOTAM office
  contact) — https://bnl.dfs.de/pilotservice/bnl/leisure/ufb/ufb_edit.jsp

**Tier 2 / versioning (to answer "is this still in force?")**

* Wayback snapshot of the pre-2015 LuftVO § 16 (snapshot 2014-06-01) —
  https://web.archive.org/web/20140601000000/http://www.gesetze-im-internet.de/luftvo/__16.html
* CEPT ERC/REC 70-03 (harmonisation basis for the SRD assignment) — copy consulted:
  https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf
  (Annex 1 band f/f1/f2; Annex 3 entry a; general text on SRD on board aircraft)

**Not usable / excluded (recorded, not cited as authority)**

* `service.rlp.de` detail page for "Erlaubnis für Luftraumnutzung beantragen" — ALTCHA bot wall;
  search-snippet content only, therefore not relied on.
* `bnl.dfs.de/.../infoblatt_ballons_de.pdf` — the URL serves the portal shell, not the PDF; the
  infoblatt could not be read.
* `buzer.de/20_LuftVO.htm` — HTTP 403; the consolidated version history of § 20 LuftVO was
  therefore not read (not needed: the in-force consolidated text and its version line were
  sufficient to show Nr. 6 is live).

**Referral note.** Items 1–11 of § 9 are not answerable from the instruments alone. The competent
addressee for items 2, 3, 4 and 10 is the **Landesluftfahrtbehörde of the Land of launch**
(for M-V, `luftfahrtbehoerde@wm.mv-regierung.de`; each Land publishes its own contact), and for
items 7, 8 and 9 the **Bundesnetzagentur** (Frequenzmanagement) or the radio manufacturer's
CE/DoC documentation. A launch that is inside a control zone, or that will carry any amateur-band
transmitter, should be put to the authority in writing before the design is frozen.
