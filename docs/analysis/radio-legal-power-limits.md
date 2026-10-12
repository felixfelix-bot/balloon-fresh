# Radio legal power limits — 433 MHz downlink and 2.4 GHz uplink

**Status: ANALYSIS — this is not an ADR and orders nothing.** It records what the
German/EU radio instruments actually require, what this design can claim, and what the
link-budget consequence is if it cannot claim it. It consumes **no ADR number** (ADR-052
is already taken by `docs/adr/052-cell-mounting-end-only.md`, merged on `main`). No design
file is modified by this analysis; no decision is taken here.

- **Branch:** `analysis/radio-legal-power-limits`
- **Date:** 2026-10-07 · **Access date for every URL below: 2026-10-07**
- **Companion model (reproduces every number in this document):**
  `docs/analysis/radio_power_limits_model.py`
- **Reads:** `docs/analysis/free-balloon-mass-threshold-DE.md` (the sibling legal analysis —
  § 7 and its `TODO(unverified)` items 7/8/9, which this document answers in part),
  `docs/adr/009-antenna-strategy-v1-v2.md` (the link budget),
  `docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md` (raw 2-byte-opcode LR2021 /
  LoRa / FLRC), `docs/adr/034-…`, `docs/adr/035-…`, `docs/adr/036-…`,
  `docs/adr/039-licence-exempt-433-design-point.md`, `docs/adr/041-rf-frontend-licence-exempt.md`,
  `docs/LINK-BUDGET-LICENCE-EXEMPT.md`, `docs/licence-exempt-design-point.md`,
  `docs/bw-code-table.md`, `docs/airtime_calc.py`, `docs/inventory.md`, `tools/link_budget.py`.

**Provenance policy.** Every regulatory statement below is quoted from a **primary source
opened at first hand** (the BNetzA assignment PDF, EUR-Lex, the CEPT recommendation, the
ETSI harmonised standard) — never from a hobbyist blog or Wikipedia. German wording is
verbatim; translations are mine and marked. Anything I could not confirm is marked
**`TODO(unverified)`** and is never silently assumed. Where this document corrects an
existing in-repo claim, the correction is stated as a correction and the evidence is given.

---

## 0. The two questions, answered in one screen

| Link | Operator's plan | What the instruments actually allow | Verdict |
|---|---|---|---|
| **433 MHz, balloon→ground** | 10 mW **ERP** | 10 mW ERP is available on **three** distinct regulatory footings (see § 2), two of which carry a condition (≤ 10 % duty cycle, or ≤ 25 kHz bandwidth inside 434.04–434.79 MHz) and one of which — the German national deviation — is printed **without** any additional parameter. The unconditional ceiling in the whole band is **1 mW ERP**. | **10 mW ERP is claimable but must be earned or documented** — it is *not* automatic. What is needed: a beacon schedule ≤ 10 % duty (easy for this design, but **not** for the ADR-041 baseline config — see § 5.1), or ≤ 25 kHz occupied bandwidth, or reliance on the printed national deviation with written confirmation. |
| **2.4 GHz, ground→balloon** | 100 mW **EIRP** on the ground transmitter | The 100 mW EIRP tier (57c / D57c "WLAN") carries a **power-density** condition: *10 mW/MHz EIRP for every modulation other than frequency hopping*. A LoRa (chirp spread spectrum) or FLRC link with ≤ 1 MHz occupied bandwidth therefore **cannot** radiate 100 mW — its density cap is ≤ ~10 mW EIRP. The applicable entry is **57a / CEPT Annex 1 h = 10 mW EIRP**. | **100 mW EIRP is NOT claimable by this radio.** The lawful ceiling for the 2.4 GHz LoRa uplink is **10 mW EIRP** — a **10 dB** loss against the assumption in ADR-041, which **turns the uplink margin negative without the F33 internal LNA**. This is the finding that matters (§ 5.2, § 6). |

**Net:** the 433 MHz side of the plan is achievable. The **2.4 GHz side is not**, and
ADR-041's falsification criterion ("a sourced ERC Rec 70-03 Annex 1 row showing the 2.4 GHz
wideband-data cap is below 100 mW EIRP for this modulation/duty class … could push the
no-internal-LNA case negative") is **triggered** — the cap is not below 100 mW in the
absolute, but the density condition makes 100 mW unreachable for this modulation
(§ 3.3, § 5.2).

---

## 1. The instruments, and how they interlock

Four documents, in descending order of authority for a German operator:

| # | Instrument | What it is | Why it matters here |
|---|---|---|---|
| 1 | **Commission Decision 2006/771/EC**, as amended by **Implementing Decision (EU) 2025/105** of 22 January 2025 | The EU harmonisation decision. Its Annex Table 2 fixes the *harmonised* conditions per band/category and the date each becomes applicable. | Art. 3(3) lets a member state permit **less strict** conditions. The German national deviations are exactly that. |
| 2 | **BNetzA Vfg. 91/2025**, *Allgemeinzuteilung von Frequenzen zur Nutzung durch Geräte geringer Reichweite (SRD)*, November 2025 | The **German general assignment** — the instrument that actually authorises the operator. Implements Decision 2006/771/EC. Supersedes Vfg. 133/2019 (as amended by Vfg. 12/2020) and the separate assignments, **including Amtsblattverfügung 128/2023 for 2400–2483.5 MHz WLAN**. | Its Tabelle 2 = the harmonised rows; its **Tabelle 3 = the German national (less strict) rows**. Both are usable — the assignment says so in terms. |
| 3 | **CEPT ERC/REC 70-03** | The CEPT recommendation that is the harmonisation **basis** behind Decision 2006/771/EC. Not binding by itself. | Its Annex 1 / Annex 3 rows are what the EU and German rows reproduce, and its general text is the only place the CEPT speaks about **use on board aircraft**. |
| 4 | **ETSI EN 300 328 V2.2.2 (2019-07)** | The **harmonised standard** for 2.4 GHz wideband data transmission, listed in ERC/REC 70-03 Annex 3 and therefore the technical content behind Vfg. 91/2025 footnote **[7]**. | It supplies the numbers (20 dBm EIRP, 10 dBm/MHz PSD) that make the 57c density condition operatively checkable. |

**Vfg. 91/2025 — verified identity** (PDF metadata read at first hand):
`Title: Vfg 91/2025`; `Subject: Allgemeinzuteilung_SRD`; `Author: Bundesnetzagentur`;
`CreationDate: 2025-11-03`; `ModDate: 2025-11-18`; 32 pages.
URL: <https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf?__blob=publicationFile&v=3>
(listed as the current SRD assignment on the BNetzA *Allgemeinzuteilungen* index,
<https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/start.html>).
It says of itself: *"Gemäß § 210 Satz 3 TKG gilt diese Allgemeinzuteilung zwei Wochen nach
dieser Bekanntmachung als bekannt gegeben"* — deemed notified two weeks after publication.
**Befristung:** *"Diese Allgemeinzuteilung ist bis zum 31.12.2035 befristet."*
`TODO(unverified)`: the **Amtsblatt** issue and page number (the PDF's own header reads only
"Vfg. 91/2025, November 2025"); carried forward from the sibling analysis § 9 item 11.

**The interlock that matters.** Vfg. 91/2025 states, verbatim:

> *"Gemäß Artikel 3 Absatz 3 der Entscheidung der Kommission (2006/771/EG) … dürfen die
> Mitgliedsstaaten die Nutzung der Frequenzbänder unter weniger strengen Bedingungen
> gestatten. Frequenzbänder mit solchen in Deutschland gemäß dieser Allgemeinzuteilung
> geltenden Abweichungen sind in Tabelle 2 in der Spalte 'Band Nr.' mit (\*) markiert und
> werden in Tabelle 3 gesondert mit 'D' vor der Band Nr. aufgeführt. **Die Frequenznutzung
> von Geräten mit geringer Reichweite ist in Deutschland sowohl mit den harmonisierten
> technischen Bestimmungen gemäß Tabelle 2 als auch mit den weniger strengen nationalen
> Bestimmungen gemäß Tabelle 3** (z.B. größeres Frequenzband, höhere Sendeleistung oder
> zusätzliche Kategorie von Geräten mit geringer Reichweite) **nutzbar.**"*

*(translation: "Under Article 3(3) … member states may permit use of the bands under less
strict conditions. Bands with such deviations applicable in Germany are marked with (\*) in
the 'Band Nr.' column of Table 2 and are listed separately in Table 3 with a 'D' before the
band number. In Germany, SRD use is possible **both** under the harmonised technical
conditions of Table 2 **and** under the less strict national conditions of Table 3 (e.g. a
larger frequency band, higher transmit power, or an additional SRD category).")*

The corresponding EU-level permission is equally explicit (Decision 2006/771/EC as amended,
Annex, footnote to Table 2):

> *"—Die Mitgliedstaaten dürfen ausschließlich die in Tabelle 2 angegebenen zusätzlichen
> Parameter (Vorschriften für Kanalbildung und/oder Kanalzugang und -belegung) vorschreiben
> und keine weiteren Parameter oder Frequenzzugangs- und Störungsminderungsanforderungen
> hinzufügen. Da weniger strenge Bedingungen gemäß Artikel 3 Absatz 3 festgelegt werden
> können, **dürfen die Mitgliedstaaten in einer bestimmten Zelle ganz auf solche zusätzlichen
> Parameter verzichten oder höhere Werte gestatten**, sofern die jeweilige Umgebung für eine
> gemeinsame Nutzung des harmonisierten Frequenzbands dadurch nicht beeinträchtigt wird."*

*(translation: "Member states may prescribe only the additional parameters given in Table 2
and no others. Because less strict conditions may be set under Article 3(3), member states
**may waive such additional parameters entirely in a given cell, or permit higher values**,
provided sharing of the harmonised band is not impaired.")*

Decision URL (retrieved through the `r.jina.ai` reader proxy — EUR-Lex answers plain `curl`
with HTTP 202 and an empty body, the same obstacle the sibling analysis hit):
<https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32025D0105>

> **Consequence for reading the rest of this document.** For any given band/category there
> can be **two valid German footings**: the harmonised one (Tabelle 2) and the national one
> (Tabelle 3). They are alternatives, not layers. A claim of "10 mW ERP at 433 MHz" is
> therefore a claim about **which footing** is being relied on. § 2 works both out.

---

## 2. 433 MHz — exactly what the 1 mW vs 10 mW distinction requires

### 2.1 The harmonised rows (Vfg. 91/2025 Tabelle 2 = EU Decision Table 2)

Verbatim from Tabelle 2 of Vfg. 91/2025 (the `*` = a band number carrying a German
deviation, restated in Tabelle 3). The right-hand columns are the *only* additional
requirements that may exist (Decision footnote above):

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung | Zusätzliche Parameter |
|---|---|---|---|---|
| **44a\*** | 433,05–434,79 MHz | Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen | **1 mW (ERP)** | *(none)* |
| **44b\*** | 433,05–434,79 MHz | same | **10 mW (ERP)** | **Arbeitszyklus: ≤ 10 %** |
| **45c\*** | **434,04–434,79 MHz** | same | **10 mW (ERP)** | **Arbeitszyklus ≤ 100 % bei einer Bandbreite ≤ 25 kHz** |

The EU harmonised Decision's Annex Table 2 carries **the same three rows verbatim**, with
applicability dates, which is why 45c is *not* a German invention:

> *"44a 433,05-434,79 MHz Geräte mit geringer Reichweite für nicht näher spezifizierte
> Anwendungen **1 mW (ERP)** 1.Juli 2025"*
> *"44b 433,05-434,79 MHz … **10 mW (ERP)** **Arbeitszyklus: ≤ 10%** 1.Januar 2020"*
> *"45c 434,04-434,79 MHz … **10 mW (ERP)** **Arbeitszyklus ≤100% bei einer Bandbreite ≤ 25 kHz**
> 1.Juli 2025"*

*(translation: 44a/44b = 1 mW / 10 mW e.r.p. with no condition / ≤ 10 % duty cycle;
45c = 10 mW e.r.p. in the upper 750 kHz of the band with ≤ 100 % duty cycle **provided the
bandwidth is ≤ 25 kHz**.)*

CEPT ERC/REC 70-03 Annex 1 encodes the same three rows as entries `f`, `f1`, `f2`
(copy consulted: an ARCEP (French regulator) mirror of the recommendation,
<https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf>,
"Version of 9 February 2011", Edition of February 2011 — **the edition is flagged**, see
§ 8 item 2):

| CEPT entry | Band | Power | Spectrum access | Channel spacing | Notes |
|---|---|---|---|---|---|
| `f` | 433.050–434.790 MHz | 10 mW e.r.p. | **< 10 % (note 1)** | No spacing | (note 4) |
| `f1` | 433.050–434.790 MHz | **1 mW e.r.p.** | **No requirement** | No spacing | (note 4bis); *"Power density limited to -13 dBm/10 kHz for wideband modulation with a bandwidth greater than 250 kHz"* |
| `f2` | 434.040–434.790 MHz | 10 mW e.r.p. | **No requirement** | **Up to 25 kHz** | (note 4bis) |

Annex 1 **Note 1** (the definition of what "a duty cycle applies" means):

> *"When either a duty cycle, Listen Before Talk (LBT) or equivalent technique applies then
> it shall not be user dependent/adjustable and shall be guaranteed by appropriate technical
> means. For LBT devices without Adaptive Frequency Agility (AFA), or equivalent techniques,
> the duty cycle limit applies. For any type of frequency agile device the duty cycle limit
> applies to the total transmission unless LBT or equivalent technique is used."*

> ⚠️ **Sub-band vs bandwidth — a trap, and a divergence between the two texts.** In CEPT
> Annex 1 the 25 kHz of entry `f2` reads as **channel spacing** ("Up to 25 kHz"). In the
> German text of 45c — and in the EU Decision's German text — it is **"Bandbreite"**, i.e.
> **occupied bandwidth**. The German/EU wording is the operative one for a German operator,
> and it is the reason § 5.1 can offer a "narrow your modulation instead of your duty cycle"
> route. `TODO(unverified)`: whether the English-language EU text also says "bandwidth"
> rather than "channel spacing" (only the German texts were read).

### 2.2 The German national deviation row (Vfg. 91/2025 Tabelle 3)

Verbatim, as laid out in the PDF (page 27) — the three band numbers **share one row with
vertically merged cells**; the layout was confirmed by rendering the page and reading it,
not by text extraction alone:

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung | Zusätzliche Parameter | Sonstige Nutzungsbeschränkungen |
|---|---|---|---|---|---|
| **D44a / D44b / D45c** | 433,05–434,79 MHz | Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen | **10 mW (ERP)** | *(leer / empty)* | **-** |

*(translation: "10 mW ERP, no additional parameter, no other restriction.")*

**This is the German less-strict deviation, and it is what Art. 3(3) / the Vfg. footnote
above authorise.** Read on its face it says: for all three band numbers 44a, 44b and 45c,
Germany permits **10 mW ERP with no duty-cycle condition and no bandwidth condition**. That
is a *waiver* of the additional parameters, which the EU footnote expressly permits
("*ganz auf solche zusätzlichen Parameter verzichten*"), and it is how the row is drawn: the
"Zusätzliche Parameter" cell is **empty**, not "as in Table 2".

> **Honesty statement on this finding.** This reading is textually well supported (the Vfg.'s
> own "sowohl … als auch" sentence + the merged Tabelle 3 row + the EU footnote licensing a
> waiver), but it is a **reading of a table**, and it is *favourable*, so it should not be
> load-bearing without a second opinion. **This document therefore treats the harmonised
> Tabelle 2 conditions of § 2.1 as the conservative baseline for the design (§ 5.1) and
> records the national deviation as an additional, documented route** — recommending written
> confirmation from the Bundesnetzagentur before a flight plan depends on it (§ 7 route **D**).
> Carrying forward as `TODO(unverified)`: **Bundesnetzagentur (Referat 221) written
> confirmation that Tabelle 3's D44a/D44b/D45c waives the ≤ 10 % duty-cycle / ≤ 25 kHz
> bandwidth parameters of Tabelle 2 rows 44b/45c.** No primary German text resolves it beyond
> the table itself; a German-language commentary or the Amtsblatt version might.

### 2.3 What "duty cycle" (Arbeitszyklus) means — the definition to do arithmetic against

Vfg. 91/2025 defines it in terms, immediately before the tables:

> *"‚Arbeitszyklus' ist das in Prozent ausgedrückte Verhältnis von Σ(Ton)/(Tobs), wobei ‚Ton'
> die ‚Ein-Zeit' eines einzelnen Sendegeräts und ‚Tobs' der Beobachtungszeitraum ist. Ton
> wird in einem Beobachtungsfrequenzband (Fobs) gemessen. **Sofern in den Tabellen 2 und 3
> nicht anders bestimmt, ist Tobs ein fortlaufender Zeitraum von einer Stunde** und Fobs das
> zutreffende Frequenzband in dieser Tabelle."*

*(translation: "duty cycle is the ratio, in per cent, of Σ(T_on)/(T_obs), where T_on is the
'on' time of a single transmitting device and T_obs is the observation period … Unless the
tables say otherwise, **T_obs is a continuous period of one hour** and F_obs is the relevant
frequency band of this table.")*

CEPT ERC/REC 70-03 says the same thing in English, in its "Duty cycle categories" section:

> *"For the purposes of this Recommendation the duty cycle is defined as the ratio, expressed
> as a percentage, of the **maximum transmitter 'on' time on one carrier frequency**,
> relative to a **one hour period** unless otherwise mentioned in the relevant Annex."*

CEPT then adds a per-burst advisory table for the four duty-cycle classes — relevant because
it bounds *burst length*, not just the average:

| Class | Transmitting time / full cycle | Max transmitter "on" time | Min transmitter "off" time |
|---|---|---|---|
| 1 Very Low | < 0.1 % | 0.72 s | 0.72 s |
| 2 Low | < 1.0 % | 3.6 s | 1.8 s |
| **3 High** | **< 10 %** | **36 s** | **3.6 s** |
| 4 Very High | up to 100 % | — | — |

The recommendation calls these *"advisory with a view to facilitating sharing between systems
in the same frequency band"*, and they are framed for *"pre-programmed devices"*. **The
binding German rule is the average** (ΣT_on / 1 h), with no per-burst on-time limit stated in
Vfg. 91/2025. Both are used in § 5.1: the average is the legal test, the 36 s figure is a
sanity bound on any single burst.

### 2.4 ERP vs EIRP, and the practical consequence for the TX clamp

ERP is referenced to a half-wave dipole (0 dBd); **EIRP = ERP + 2.15 dB**. So:

| Limit | ERP | EIRP |
|---|---|---|
| 44a / `f1` | 1 mW = **0 dBm ERP** | 1.64 mW = **+2.15 dBm EIRP** |
| 44b, 45c / `f`, `f2` | 10 mW = **+10 dBm ERP** | 15.85 mW = **+12.15 dBm EIRP** |

Conducted-power requirement for the firmware clamp and the production test (ADR-039
consequence 3 / ADR-041 D2 / `docs/licence-exempt-design-point.md` § 6):
`conducted power + antenna gain in dBd ≤ +10 dBm`.
With the ADR-041 assumption of a **0 dBi** balloon antenna (which is **−2.15 dBd**), the
conducted ceiling is **+12.15 dBm**; with a half-wave dipole (0 dBd) it is **+10 dBm**.
Note that ADR-041's headline case is therefore *conservative by 2.15 dB*: it computes a
**10 dBm EIRP** downlink, whereas 10 mW **ERP** into a 0 dBi antenna actually licenses
**12.15 dBm EIRP** (ADR-041 §2b's 12.2 dBm case). That 2.15 dB is real and is counted in § 6.

### 2.5 Correction — there is **no** "integral antenna" condition at 433 MHz

`docs/licence-exempt-design-point.md` § 3 states the 433 MHz permission as *"~10 mW ERP
with an **integral antenna**"*, citing ERC/REC 70-03 Annex 1 (which that document itself
marks `TODO(unverified)`) plus an in-repo secondary source that `docs/LINK-BUDGET-LICENCE-EXEMPT.md`
§ 0 records as derived from the **Wikipedia LPD433 article**. **Neither primary source
supports that condition for this band:**

- **Vfg. 91/2025**, entries 44a/44b/45c (Tabelle 2) and D44a/D44b/D45c (Tabelle 3): the
  only requirement column is the duty-cycle / bandwidth condition; there is **no antenna
  condition**, and no reference to footnote **[8]** ("Antennenanforderungen"). The only
  category in Vfg. 91/2025 that requires *"nur eingebaute Antennen"* is **PMR446**
  (Tabelle 1), a different category and band.
- **ERC/REC 70-03 Annex 1 enter `f`**: *"433.050-434.790 MHz — 10 mW e.r.p. — < 10 %
  (note 1) — No spacing"*. No antenna condition. (Entry `f`'s note 4 covers *audio and
  video applications*, not antennas.)

Practically the correction is **harmless**: ERP is stated relative to a dipole, so antenna
gain is already inside the limit — a gain antenna simply subtracts from the permitted
conducted power, exactly as the clamp arithmetic in § 2.4 assumes. The design's balloon
433 antenna is ≈ 0–2 dBi (ADR-041 §0), so nothing changes. Recorded so the myth is not
propagated: **do not cite "integral antenna" as a 433 MHz condition.**
`TODO(unverified)`: whether the *repealed* Vfg. 133/2019 or the pre-2019 German LPD
assignment carried such a condition — not read.

### 2.6 The 433 MHz answer in one line

> **1 mW ERP (44a / `f1`) is the unconditional ceiling.** **10 mW ERP is available only by
> satisfying *one of*: ≤ 10 % duty cycle (44b / `f`), ≤ 25 kHz bandwidth inside
> 434.04–434.79 MHz (45c / `f2`), or the printed German national deviation
> D44a/D44b/D45c — which as printed imposes no additional parameter at all.**

---

## 3. 2.4 GHz — exactly what the 100 mW EIRP tier requires

### 3.1 The rows

Verbatim from Vfg. 91/2025 Tabelle 2 (57a and 57b are unstarred → no German deviation;
57c carries `*` → German deviation D57c in Tabelle 3). The EU Decision's Annex Table 2
carries the identical three rows with dates (57a 1 July 2014, 57b 1 July 2014,
57c 1 July 2014):

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung / Leistungsdichte | Zusätzliche Parameter |
|---|---|---|---|---|
| **57a** | 2 400–2 483,5 MHz | Geräte mit geringer Reichweite für nicht näher spezifizierte Anwendungen | **10 mW (EIRP)** | *(none)* |
| **57b** | 2 400–2 483,5 MHz | **Funkortungsgeräte** | **25 mW (EIRP)** | *(none)* |
| **57c\*** | 2 400–2 483,5 MHz | **Breitband-Datenübertragungsgeräte** | **100 mW (EIRP) und Leistungsdichte von 100 mW/100 kHz (EIRP) bei Frequenzsprungmodulation; Leistungsdichte von 10 mW/MHz (EIRP) bei anderen Modulationsarten** | *"Es gelten Anforderungen an Frequenzzugangs- und Störungsminderungstechniken [7]."* |

And the German national row (Tabelle 3, page 27, confirmed by rendering the page), which
relabels the category explicitly:

| Band Nr. | Frequenzband | Kategorie | Maximale Sendeleistung / Leistungsdichte | Zusätzliche Parameter | Sonstige Nutzungsbeschränkungen |
|---|---|---|---|---|---|
| **D57c** | 2 400–2 483,5 MHz | **WLAN** | 100 mW (EIRP) und Leistungsdichte von 100 mW/100 kHz (EIRP) bei Frequenzsprungmodulation; Leistungsdichte von 10 mW/MHz (EIRP) bei anderen Modulationsarten | *"Es gelten Anforderungen an Frequenzzugangs- und Störungsminderungstechniken [7]."* | *"Aussendungen, die absichtlich bestimmungsgemäße WLAN-Nutzungen stören oder verhindern … sind nicht gestattet."* |

*(translation of the key cell: "100 mW EIRP **and** a power density of 100 mW/100 kHz (EIRP)
for frequency-hopping modulation; a power density of 10 mW/MHz (EIRP) for other modulation
types.")*

> **Asymmetry to note: Germany did not deviate on 57a.** 57a is unstarred, so there is **no**
> German national route to more than **10 mW EIRP** for a non-specific SRD in 2.4 GHz. The
> only 2.4 GHz deviation is D57c, and it does not exceed the harmonised 100 mW EIRP. The
> 433 MHz side of this design has a national escape hatch (§ 2.2); the 2.4 GHz side does not.

### 3.2 What qualifies a device as a "Breitband-Datenübertragungsgerät"

**Category definition, Vfg. 91/2025 Tabelle 1, verbatim:**

> *"**Breitband-Datenübertragungsgeräte** — Diese Kategorie umfasst Funkgeräte, die
> **Breitbandmodulationstechniken für den Frequenzzugang** nutzen. Übliche Verwendungen sind
> **drahtlose Zugangssysteme wie lokale Funknetze (WAS/Funk-LAN)** oder Breitband-Geräte mit
> geringer Reichweite in **Datennetzen**."*

*(translation: "This category covers radio equipment that uses **broadband modulation
techniques for spectrum access**. Usual uses are wireless access systems such as local radio
networks (WAS/Wireless LAN) or broadband SRDs in **data networks**.")*

**The spectrum-access footnote [7], Vfg. 91/2025, verbatim:**

> *"[7] Es sind **Frequenzzugangs- und Störungsminderungstechniken** einzusetzen, deren
> Leistungsniveau **mindestens den wesentlichen Anforderungen der Richtlinie 2014/53/EU bzw.
> des FuAG** entspricht. Werden einschlägige Techniken in harmonisierten Normen, deren
> Fundstellen gemäß der Richtlinie 2014/53/EU im Amtsblatt der Europäischen Union
> veröffentlicht worden sind, oder deren Teilen beschrieben, ist eine Leistung zu
> gewährleisten, die mindestens diesen Techniken entspricht."*

*(translation: "Frequency-access and interference-mitigation techniques must be used whose
performance is at least that of the essential requirements of Directive 2014/53/EU or the
FuAG. Where relevant techniques are described in harmonised standards whose references have
been published in the OJEU, performance at least equal to those techniques must be
guaranteed.")*

**Which harmonised standard that is** — ERC/REC 70-03 Annex 3 ("Wideband Data Transmission
Systems and Wireless Access Systems including RLANs within the band 2400–2483.5 MHz"):

> `a   2400.0–2483.5 MHz   100 mW e.i.r.p.   See note 1   No spacing   ERC/DEC/(01)07
>     For wide band modulations other than FHSS, the maximum e.i.r.p. density is limited to
>     10 mW/MHz`
>
> `Note 1: The equipment shall implement an adequate spectrum sharing mechanism in order to
> facilitate sharing between the various technologies and applications covered by this annex 3.`
>
> `Harmonised Standards — EN 300 328  sub-band a)`

So footnote [7] resolves, for this band, to **EN 300 328**. Its operative numbers
(ETSI EN 300 328 V2.2.2 (2019-07), <https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf>):

| EN 300 328 V2.2.2 clause | Requirement | Verbatim |
|---|---|---|
| §4.3.2.2.3 | RF output power, non-FHSS | *"The RF output power for non-FHSS equipment shall be equal to or less than 20 dBm."* |
| §4.3.2.3.3 | Power Spectral Density, non-FHSS | *"The maximum Power Spectral Density for non-FHSS equipment is 10 dBm per MHz."* |
| §4.3.2.5.3 | Medium Utilisation, non-adaptive non-FHSS | *"The maximum Medium Utilization factor for non-adaptive non-FHSS equipment shall be 10 %."* (`MU = (Pout/100 mW) × DC`) |
| §4.3.2.7.3 | Occupied Channel Bandwidth | *"… for non-adaptive non-FHSS equipment with e.i.r.p. greater than 10 dBm, the Occupied Channel Bandwidth shall be equal to or less than 20 MHz."* |
| §4.3.2.6 | Adaptivity (non-FHSS) | adaptive non-FHSS equipment must implement **DAA** or **LBT** (CCA ≥ 18 µs, channel occupancy < 13 ms, energy-detect threshold ≤ −70 dBm/MHz for a 20 dBm transmitter) |
| §4.3.1.2.3 (FHSS) | RF output power, FHSS | *"The RF output power for FHSS equipment shall be equal to or less than 20 dBm."* |
| definitions | *wideband data transmission equipment* | *"equipment using modulation or spreading techniques resulting in a **wideband** signal. NOTE: Examples of such techniques include **FHSS, DSSS, OFDM**, etc."* |
| Introduction | examples | *"Examples of Wideband Data Transmission equipment are equipments such as **IEEE 802.11™ RLANs**, Bluetooth® wireless technologies, Zigbee™, etc."* |

### 3.3 The density condition is decisive — and it excludes this radio

The 57c/D57c ceiling has **two** parts joined by "und" ("and"): an **absolute** 100 mW EIRP,
and a **density**. For every modulation that is *not* frequency hopping the density is
**10 mW/MHz EIRP** — the same number EN 300 328 §4.3.2.3.3 states as 10 dBm/MHz. Arithmetic:

| Occupied bandwidth | Max EIRP under the 10 mW/MHz density rule | Which tier binds |
|---|---|---|
| 0.203 MHz (LR2021 2.4 GHz LoRa `BW_203`) | **~2.0 mW EIRP** | 57c density (worse than 57a) |
| 0.406 MHz (`BW_406`) | ~4.1 mW EIRP | 57c density |
| 0.812 MHz (`BW_812`) | ~8.1 mW EIRP | 57c density (worse than 57a) |
| 1.0 MHz (`BW_1000`) | ~10 mW EIRP | 57c density = 57a |
| **≥ 10 MHz** | **100 mW EIRP** | 57c absolute ceiling reachable |
| FHSS, 100 mW/100 kHz density | 100 mW EIRP (per hopping channel) | 57c, other arm |

**Therefore:** to radiate 100 mW EIRP in 2 400–2 483.5 MHz you need **either** a frequency-
hopping modulation (density allowance 100 mW/100 kHz) **or** a non-FHSS modulation with an
occupied bandwidth of **≥ 10 MHz** (which in practice means 802.11-class WLAN, and which
EN 300 328 then additionally requires to be capable of DAA or LBT; for the non-adaptive case
it caps the OCB at 20 MHz).

The design's 2.4 GHz radio is an **LR2021 using raw 2-byte-opcode SPI** (ADR-020) in
**LoRa** or **FLRC** — chirp spread spectrum / coded FSK. Per `docs/adr/020-…` the LR2021's
supported modulations on this hardware are FLRC, LoRa and GFSK; **there is no 802.11 mode and
no FHSS mode**. Per `docs/bw-code-table.md` the widest 2.4 GHz LoRa bandwidth is
**812 kHz** (code `0x0F`, driver constant 812 000 Hz), with `BW_1000` (code `0x07`) marked
*"verify vs datasheet before on-air use"*. FLRC at 2 600 kbps occupies roughly its symbol
rate (a few MHz at most), not 10 MHz.

> **Finding (this is the one that changes a budget).** **A LoRa or FLRC 2.4 GHz link on this
> hardware cannot lawfully claim entry 57c/D57c. Its lawful ceiling in 2 400–2 483.5 MHz is
> entry 57a / CEPT Annex 1 `h`: 10 mW EIRP — and 57a carries no spectrum-access condition, so
> that is the *simple* compliant design point.** ADR-041's assumption of a **20 dBm (100 mW)
> EIRP ground transmitter is not supportable** as a licence-exempt claim for this modulation.
> ADR-041 §"What would falsify this" anticipated exactly this test; the test is now answered
> against the 100 mW assumption.

### 3.4 A possible +4 dB, if the design wants to argue for it

Entry **57b** gives **25 mW EIRP** to *"Funkortungsgeräte"* (radiodetermination equipment) —
+4 dB over 57a. The German category definition, however, closes one door:

> *"**Funkortungsgeräte** — Diese Kategorie umfasst Funkgeräte, die zur Ermittlung der
> Position, der Geschwindigkeit und/oder anderer Eigenschaften eines Objekts … eingesetzt
> werden. … **Nicht zu den Funkortungsgeräten gehören alle Arten der Punkt-zu-Punkt- oder
> Punkt-zu-Mehrpunkt-Funkkommunikation.**"*

*(translation: "… **Point-to-point or point-to-multipoint radio communication of any kind is
not radiodetermination equipment.**")*

The SX1280 ranging link is a two-way (point-to-point) exchange — so claiming 57b for it is
**contestable**, and this document does not assume it. Recorded because it is a real +4 dB
on the table: `TODO(unverified)`: a written BNetzA determination on whether a two-way-ranging
SRD is "Funkortung" (57b, 25 mW EIRP) or non-specific SRD (57a, 10 mW EIRP).

**Everything the balloon transmits in 2.4 GHz is bound by this.** Under ADR-034/035 the
balloon's 2.4 GHz transmitter is the **SX1280 ranging radio**; the balloon's 2.4 GHz
*receiver* (bare LR2021) transmits nothing, so it is not regulated at all. ADR-009's
"+22 dBm FEM into a 2 dBi omnidirectional antenna" design point is **+24 dBm ≈ 251 mW EIRP**
(`docs/adr/009-antenna-strategy-v1-v2.md`, link-budget table row 1) — **25× over the 10 mW
EIRP ceiling** and already superseded on the licence-exempt route. But the SX1280's ranging
power must be clamped to the same ceiling, and that requirement does not appear in
ADR-034/035/041.

### 3.5 Sanity check — the general-purpose limits that also apply

- **Non-interference / no protection**: Vfg. 91/2025 — *"Die Frequenzbänder für Geräte mit
  geringer Reichweite … stehen nicht-exklusiv, nichtstörend und ungeschützt zur Verfügung …
  keine schädliche Störung bei einem Funkdienst verursacht werden darf und kein Anspruch auf
  Schutz gegen funktechnische Störungen … besteht."*
- **Equipment conformity**: Hinweis 2 — *"Eine Nutzung zugeteilter Frequenzen darf nur mit
  Funkanlagen erfolgen, die dem Funkanlagengesetz (FuAG) entsprechen (§ 99 Abs. 6 TKG)."*
  `TODO(unverified)`: whether the **LoRa2021F33-2G4 module's EU declaration of conformity /
  CE marking covers operation at 433.05–434.79 MHz**, and at what power — the in-repo
  `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` is a datasheet, not a DoC. This is
  the obligation behind the "TX clamp + production test" of ADR-039 §6 and matters because
  operating a module outside its declared conditions is the placer's responsibility.
- **The user is responsible**: Hinweis 5 — *"Der Frequenznutzer ist für die Einhaltung der
  Zuteilungsbestimmungen und für die Folgen von Verstößen … verantwortlich."*

---

## 4. Does airborne / mobile operation change any of it? — No

**CEPT, primary text** (ERC/REC 70-03, general text, verbatim):

> *"The CEPT has considered the use of SRD devices **on board aircraft** and it has concluded
> that, from the CEPT regulatory perspective, **such use is allowed under the same conditions
> provided in the relevant Annex** of Recommendation 70-03. **For aviation safety aspects,
> the CEPT is not the right body to address this matter** which remains the responsibility of
> **aircraft manufacturers or aircraft owners** who should consult with the **relevant
> national or regional aviation bodies** before the installation and use of such devices on
> board aircraft."*

**Vfg. 91/2025: nothing to add, and nothing to subtract.** The "Sonstige
Nutzungsbeschränkungen" and "Zusätzliche Parameter" cells of the entries this design actually
touches (44a/44b/45c; D44a/D44b/D45c; 57a; 57c/D57c) contain **no airborne condition and no
mobile-vs-fixed distinction**. A full-text search of the assignment for aircraft vocabulary
returns exactly one hit, and it is not applicable:

- footnote **[d]** — *"‚Modellsteuerungsgeräte' sind … zur Steuerung der Bewegung von Modellen
  (vorwiegend Miniaturnachbildungen von Fahrzeugen bzw. **Flugzeugen**) **in der Luft** …"* —
  and footnote [d] is attached to the **27 MHz model-control** entries, not to 433 MHz or
  2.4 GHz.
- footnote **[4]** — radio-astronomy protection zones / *"Systeme zur Hinderniserkennung zur
  Verwendung in Drehflüglern"* (helicopter obstacle-detection radar), Tabelle 4a/4b — a
  different application, different bands.

**So:** radio-wise, **nothing changes aloft**; the same ERP/EIRP and duty-cycle/PSD
conditions apply at 12 km as at ground level. The aviation-safety side of carrying a
transmitter aloft is a **separate regime** (aviation law), which the sibling analysis
`docs/analysis/free-balloon-mass-threshold-DE.md` § 6 covers — it does not touch the radio
power limits, and this document does not re-derive it. This confirms the sibling analysis's
§ 7.3 and closes its `TODO(unverified)` item 9 **in part**:

`TODO(unverified)` (carried forward): the German **Frequenzplan**'s per-band
"Nutzungsbestimmungen" were not read, so a country-specific airborne note *outside* Vfg.
91/2025 cannot be positively excluded.

---

## 5. What **this** design can actually claim

### 5.1 The 433 MHz downlink

**The intended mode.** ADR-034 D2 puts the balloon's TX on the `LoRa2021F33-2G4` sub-GHz
port; ADR-020 mandates the raw 2-byte-opcode SPI path, with LoRa, FLRC and GFSK available.
ADR-041's own 433 arithmetic is computed at **LoRa SF12 / BW 125 kHz / 255 B payload**
(`tools/link_budget.py --freq 433 --sf 12 --bw 125 …`) — i.e. the design's baseline 433
configuration is a **125 kHz-wide LoRa signal at SF12**.

**Airtime** (formula: Semtech AN1200.13, identical to the in-repo `docs/airtime_calc.py`;
CR 4/5, 8-symbol preamble, hardware CRC on; sub-GHz bandwidth codes per
`docs/bw-code-table.md`). Reproduce with `python3 docs/analysis/radio_power_limits_model.py`:

| SF / BW | 32 B | 64 B | 255 B | LDRO |
|---|---|---|---|---|
| SF7 / 62.5 kHz | 0.145 s | 0.238 s | 0.806 s | no |
| SF7 / 125 kHz | 0.072 s | 0.118 s | 0.400 s | no |
| SF8 / 125 kHz | 0.134 s | 0.216 s | 0.707 s | no |
| SF9 / 125 kHz | 0.247 s | 0.390 s | 1.250 s | no |
| SF10 / 125 kHz | 0.453 s | 0.698 s | 2.296 s | no |
| SF11 / 125 kHz | 0.987 s | 1.561 s | 5.001 s | **yes** |
| **SF12 / 125 kHz** | **1.810 s** | **2.793 s** | **9.019 s** | **yes** |
| SF12 / 250 kHz | 0.905 s | 1.397 s | 4.510 s | yes |

**Duty-cycle arithmetic — the answer to "what schedule keeps him legal at 10 mW".**
T_obs = 1 continuous hour (Vfg. definition, § 2.3); cap 10 % (entry 44b / CEPT `f`).

| Configuration (255 B) | T_air | **Interval needed for ≤ 10 %** | 1 pkt / 60 s | 1 pkt / 120 s | 1 pkt / 300 s |
|---|---|---|---|---|---|
| SF7 / 125 kHz | 0.400 s | **4.0 s** | 0.67 % ✔ | 0.33 % ✔ | 0.13 % ✔ |
| SF9 / 125 kHz | 1.250 s | **12.5 s** | 2.08 % ✔ | 1.04 % ✔ | 0.42 % ✔ |
| SF10 / 125 kHz | 2.296 s | **23.0 s** | 3.83 % ✔ | 1.91 % ✔ | 0.77 % ✔ |
| SF11 / 125 kHz | 5.001 s | **50.0 s** | 8.34 % ✔ | 4.17 % ✔ | 1.67 % ✔ |
| **SF12 / 125 kHz** *(ADR-041 baseline)* | **9.019 s** | **90.2 s** | **15.03 % ✘** | 7.52 % ✔ | 3.01 % ✔ |
| SF12 / 62.5 kHz | 18.184 s | **181.8 s** | **30.31 % ✘** | **15.15 % ✘** | 6.06 % ✔ |

Read the two rulings straight off the **SF12 / 125 kHz** baseline row (the configuration
ADR-041 actually computes):

> - **1 packet / 60 s → 15.03 % duty → the design is OUTSIDE entry 44b.** A plain
>   "beacon every minute" on the ADR-041 433 configuration is **not** lawful at 10 mW ERP on
>   the harmonised footing. The lawful ceiling for *that* schedule is **1 mW ERP (44a)**.
> - **The fix is a schedule change, not a power change**: the same packet at **1 per 120 s**
>   gives **7.52 %** ✔, and the exact threshold is an interval of **≥ 90.2 s** (it takes
>   39 packets/hour to hit the 10 % ceiling). No design change, no mass, no BOM change —
>   one constant in the beacon scheduler.
> - Nothing here violates the CEPT per-burst advisory either: a 9.02 s burst is well inside
>   the 36 s maximum "on" time of the "< 10 %" class.

> ⚠️ **Internal inconsistency found in the repo.** `docs/licence-exempt-design-point.md` § 7
> asserts *"Actual beacon duty cycle is ~1.7 % — 1 s per 60 s"*. **1 s of airtime per 60 s
> is 1.67 % and is lawful — but it is not the configuration ADR-041's link budget uses.**
> 1 s of LoRa airtime at the ADR-041 baseline modulation corresponds to a payload of only
> **~6–10 bytes** (SF12/BW125: 991 ms at 6/8/10 B, 1.81 s at 32 B, **9.02 s at 255 B**, per
> `docs/analysis/radio_power_limits_model.py`). The duty figure and the link-budget
> configuration cannot both be the design of record. **Whichever is right, the duty figure
> must be computed from the same SF/BW/payload/interval the link budget uses** — that is the
> single most important correction this analysis makes to the repo's regulatory arithmetic.

**The three lawful routes to 10 mW ERP at 433, ranked by how much they cost the design:**

| Route | What it requires | Cost / caveat |
|---|---|---|
| **A. Duty cycle (entry 44b)** | beacon interval ≥ T_air / 0.10. At the ADR-041 baseline: **≥ 90.2 s**. At SF9/BW125/255 B: ≥ 12.5 s. | **Cheapest.** One scheduler constant. Costs position-refresh cadence (≈ 450 m of climb between beacons at 5 m/s and 90 s — negligible for a pico balloon). Requires firmware enforcement + a production/qualification test proving the average (ADR-039 §6 discipline). |
| **B. Bandwidth (entry 45c)** | operate in **434.04–434.79 MHz** with **occupied bandwidth ≤ 25 kHz**, duty cycle then may be 100 %. LR2021 LoRa codes `BW_7` (7.8125 kHz), `BW_10` (10.417 kHz), `BW_15` (15.625 kHz) and `BW_20` (20.833 kHz) are all ≤ 25 kHz (`docs/bw-code-table.md`). | Costs airtime/spreading: SF12/BW20.833 kHz/255 B = **54.1 s**, i.e. **×6 airtime** vs 125 kHz — but with no duty-cycle cap that is still legal, and the whole band's duty budget is unconstrained. Also *narrows* the spectrum to the upper 750 kHz of the band (antenna/trim implications) and needs the ground receiver on the same BW. |
| **C. Accept 1 mW ERP (entry 44a)** | nothing — it is the unconditional ceiling. | **10 dB of downlink margin** (§ 6): +24.3 dB → **+14.3 dB** (tool sensitivity) / +30.3 → **+20.3 dB** (module −143 dBm). The link *still closes* at 300 km, but 10 dB of fade margin is gone (see § 6 for what that means). Partially offset by the **+2.15 dB ERP→EIRP correction** in § 2.4 if the antenna is 0 dBi. |
| **D. National deviation (Tabelle 3 D44a/D44b/D45c)** | rely on the printed German row: 10 mW ERP, no additional parameter. | **Best value and highest interpretation risk.** Zero engineering cost. Requires an honest reading of the table (§ 2.2) and, before a flight plan depends on it, **written confirmation from BNetzA Referat 221** (`221.Postfach@bnetza.de`, the contact block on the assignment itself). |

**Does the design meet ≤ 25 kHz (route B)?** Not at its current configuration: the 433
baseline is **BW 125 kHz** — 5× too wide. Route B is a *change* of mode, not a tweak.
**Does it meet ≤ 10 % duty (route A)?** Yes, **if and only if** the beacon interval is
≥ `T_air / 0.10` for the actual SF/BW/payload — 60 s at the ADR-041 baseline is **not**
enough (§ table above).

**If the design does neither A nor B and does not rely on D, the lawful ceiling is
1 mW ERP.** Stated plainly because the task asks for it plainly.

### 5.2 The 2.4 GHz uplink

**The intended mode.** Ground transmits at 2.4 GHz; the balloon receives on a bare LR2021
(ADR-034 D1/D3). ADR-041 computes it at **100 mW EIRP (20 dBm)** — which, per § 3.3, the
LR2021's LoRa/FLRC modulation **cannot claim**.

**What the design would have to be to claim 100 mW EIRP (57c/D57c):**

1. **Be a "Breitband-Datenübertragungsgerät"** — a broadband modulation technique for
   spectrum access, in a data network / WAS-RLAN-like use (§ 3.2). A LoRa telemetry link is
   not that, and the German national row names the category outright: **"WLAN"**.
2. **Satisfy footnote [7]** — frequency-access and interference-mitigation techniques at
   least at the level of Directive 2014/53/EU's essential requirements, i.e. **EN 300 328
   §4.3.2.6** adaptivity: DAA **or** LBT (CCA ≥ 18 µs, channel occupancy < 13 ms,
   energy-detect threshold ≤ −70 dBm/MHz for a 20 dBm transmitter). A chirp-spread-spectrum
   beacon has none of this — it has no CCA and no frequency-avoidance behaviour at all.
3. **Respect the density arm of the same cell** — **10 mW/MHz EIRP for non-FHSS**
   (EN 300 328 §4.3.2.3.3: 10 dBm per MHz). ⇒ **≥ 10 MHz occupied bandwidth** to reach
   100 mW.

**What it is limited to otherwise:** **entry 57a / CEPT Annex 1 `h` = 10 mW EIRP.** And note
the practical upside of the lower tier: **57a has no additional parameter** — no adaptivity,
no density, no duty cycle. A 10 mW EIRP LoRa beacon at 2.4 GHz is a *simple*, unconditionally
compliant design point, whereas 100 mW EIRP would drag the link into EN 300 328 adaptivity
territory.

It is worth writing down what a genuinely 57c-compliant ground transmitter would look like,
because it is a design fork, not a firmware flag: **802.11 (≥ 10 MHz OCB) or an FHSS
transmitter**, either way with the balloon carrying the matching radio. The LR2021 cannot be
that radio.

---

## 6. Link-budget consequence

All deltas below are **−10 dB per direction**, because both fallbacks are the same 10:1
power ratio: 10 mW → 1 mW ERP at 433 (44b/45c/national → 44a), and 100 mW → 10 mW EIRP at
2.4 GHz (57c → 57a). Sources: `docs/adr/009-antenna-strategy-v1-v2.md` (the ±300 km
balloon-to-ground design point), `docs/adr/041-rf-frontend-licence-exempt.md` and
`docs/LINK-BUDGET-LICENCE-EXEMPT.md` (the licence-exempt per-direction arithmetic),
`docs/inventory.md` (module sensitivities), `tools/link_budget.py` (FSPL + LoRa table).
Reproduce with `python3 docs/analysis/radio_power_limits_model.py`.

### 6.1 The numbers

| Direction | Assumption | Margin now | After the 10 dB fallback | Verdict |
|---|---|---|---|---|
| **433 downlink**, ground 12 dBi Yagi, tool sens −137 dBm | 10 mW ERP (10 dBm EIRP) | **+24.3 dB** | **+14.3 dB** | still closes |
| **433 downlink**, ground 12 dBi Yagi, module −143 dBm | *"* | **+30.3 dB** | **+20.3 dB** | still closes |
| **433 downlink**, ground 15 dBi Yagi, tool sens | *"* | **+27.3 dB** | **+17.3 dB** | still closes |
| **2.4 GHz uplink**, balloon 10 dBi, F33 internal LNA (−136 dBm) | 100 mW EIRP (20 dBm) | **+16.4 dB** | **+6.4 dB** | closes, marginal |
| **2.4 GHz uplink**, balloon 10 dBi, LNA bypassed (−124 dBm) | *"* | **+4.4 dB** | **−5.6 dB** | **FAILS** |
| **2.4 GHz uplink**, balloon 6 dBi, LNA in circuit | *"* | **+12.4 dB** | **+2.4 dB** | thin → effectively fails |
| **2.4 GHz uplink**, balloon 6 dBi, LNA bypassed | *"* | **+0.4 dB** | **−9.6 dB** | **FAILS** |

### 6.2 In plain terms

- **In dB: 10 dB on each link.** Not 17, not 27 — the 100 mW→10 mW step and the 10 mW→1 mW
  step are the same ratio.
- **Range.** Free-space loss goes as 20·log₁₀(d), so 10 dB buys back a factor
  `10^(−10/20) = 0.316`. **A 300 km link becomes a ~95 km link at the same margin**
  (or, keeping 300 km, the same link is 10 dB closer to its noise floor — i.e. ~0.3× the
  tolerable path/pointing/fade loss).
- **Rate.** With the `tools/link_budget.py` LoRa sensitivity ladder (−123 / −126 / −129 /
  −132 / −134.5 / −137 dBm for SF7→SF12 at 125 kHz), **10 dB ≈ 3–4 spreading-factor steps**,
  and each step up doubles the airtime. So 10 dB ≈ **×8 lower data rate at equal range**
  (SF12→SF9), or equivalently halving the bandwidth three times.
- **The penalty is asymmetric, and that is the whole finding.**
  - **433 MHz absorbs it.** The downlink's generous margin comes from two things the
    regulator cannot touch: a ground receive antenna with 12–15 dBi of gain, and a path loss
    14.9 dB lower than 2.4 GHz at the same distance (134.7 vs 149.6 dB at 300 km). Losing
    10 dB still leaves **+14.3 dB** (tool) / **+20.3 dB** (module). **The 433 downlink is not
    the link that breaks.** The practical risk is not closure, it is **fade robustness**:
    14 dB of margin on a 300 km slant path with a rotating, tumbling balloon is much less
    comfortable than 24 dB, and it is the margin that absorbs polarisation mismatch,
    balloon-attitude nulls, rain/ice on the antenna and the ground operator's pointing error.
  - **2.4 GHz does not.** The uplink is already the **binding direction** in ADR-041
    (+4.4 dB without the F33 internal LNA). Another 10 dB on top of that turns
    **+4.4 dB into −5.6 dB** — the link stops closing. This is exactly the arithmetic
    ADR-041 dismissed as *"an artefact of mis-applying the 433 cap to the 2.4 GHz
    direction"*: **the framing was wrong (the 433 cap does not apply), but the number is
    right for a different reason (57a's 10 mW EIRP is the correct 2.4 GHz ceiling for this
    modulation).** ADR-041's `−5.6 dB → FAILS` conclusion must be re-opened on the correct
    grounds.
- **Ordering matters.** If the 2.4 GHz ground transmitter must be 10 mW EIRP *and* the
  balloon-side receive chain is the thin part, then the surviving requirements are:
  the **F33 internal 2.4 GHz LNA in circuit (DIO5 HIGH)** — already ADR-041 D3, now
  load-bearing rather than comfortable — **plus** one of: a higher-gain balloon 2.4 GHz RX
  antenna, an external LNA, or a lower-rate/lower-SF-threshold uplink mode (each SF step
  returns ~2.5–3 dB of sensitivity). None of those is a regulator problem; all are mass,
  or rate, or firmware.

---

## 7. What to do about it — the lawful routes and their trade

Ordered by cost, cheapest first. **Nothing here is ordered or decided by this document.**

**433 MHz — keep 10 mW ERP:**

| Route | Action | Trade |
|---|---|---|
| **A. Constrain duty cycle** (entry 44b) | Set the beacon interval ≥ T_air/0.10 for the *actual* SF/BW/payload (≥ 90.2 s at the ADR-041 baseline; ≥ 12.5 s at SF9/BW125/255 B). Enforce in firmware; prove the average in the qualification test. | Position-refresh cadence. Cheapest by far; no mass, no BOM. **Recommended default.** |
| **B. Constrain bandwidth** (entry 45c) | Move to ≤ 25 kHz occupied bandwidth inside **434.04–434.79 MHz** (LR2021 `BW_20` = 20.833 kHz, or narrower codes). Duty cycle then unconstrained. | ×6 airtime at SF12 (54 s/packet) and = 5× narrower than the current 125 kHz; the band shrinks to its upper 750 kHz. Buys an *unlimited* duty-cycle budget, which may be worth it if ranging/telemetry grows. |
| **D. Document the national deviation** | Rely on Tabelle 3 D44a/D44b/D45c (10 mW ERP, no additional parameter) and **get it in writing from BNetzA Referat 221**. | Zero engineering cost, non-zero legal-interpretation risk (§ 2.2). Do **not** let a flight plan depend on it before the written answer arrives. |
| **C. Accept 1 mW ERP** (entry 44a) | Clamp to 0 dBm ERP. Optional +2.15 dB from the ERP→EIRP correction (§ 2.4) if the balloon antenna is 0 dBi. | −10 dB: 300 km → ~95 km at equal margin, or ~0.3× the tolerable fade. Survivable, but it eats the fade robustness that matters most on a tumbling balloon. |

**2.4 GHz — what can be recovered, and how:**

| Route | Action | Trade |
|---|---|---|
| **E. Accept 10 mW EIRP (57a)** and pay for the 10 dB on the balloon's receive chain | F33 internal LNA in circuit (DIO5 HIGH; ADR-041 D3, mandatory); consider a higher-gain balloon 2.4 GHz RX antenna; or drop one or two SF steps on the uplink (≈ 2.5–3 dB each). | 10 dB EIRP must be recovered as balloon-side RX gain, which is **unregulated** (the balloon does not transmit on 2.4 GHz except ranging) but costs **mass** and buys **rotation sensitivity** — which is precisely why ADR-009 chose omnidirectional antennas in the first place. |
| **F. Narrow/adapt the air interface** | Lower the uplink rate or bandwidth until the recovered sensitivity covers the 10 dB (roughly 3–4 SF steps). | Directly costs uplink throughput — and ADR-009's whole V1/V2 argument was that omni antennas on the balloon are only viable because the *ground* carries the gain. |
| **G. Make the ground transmitter genuinely 57c-compliant** | Replace the ground LoRa transmitter with a **WLAN (≥ 10 MHz OCB) or FHSS** transmitter that meets EN 300 328 adaptivity, and put the matching radio on the balloon. | A **design fork**, not a firmware flag: the LR2021 has no 802.11 and no FHSS mode (ADR-020). Buys the full 20 dBm EIRP back, at the cost of a different radio on both ends. |
| **H. Argue 57b (Funkortung, 25 mW EIRP)** for the ranging link only | Ask BNetzA whether two-way ranging qualifies as *Funkortung*. | +4 dB, and it does **not** help the LoRa uplink (that is not ranging). The category definition's exclusion of point-to-point communication makes the claim contestable (§ 3.4). |
| **I. Move the burden to a licensed service (the operator's amateur licence)** | The operator holds a German DE amateur licence (ADR-039 explicitly rejected this route for the balloon). A ground-station transmitter under the amateur service is not bound by Vfg. 91/2025's EIRP caps. | Removes the 10 dB on the *ground* side, but reintroduces **amateur obligations** (callsign, no-encryption/plain-telemetry, "no pecuniary interest", station control) that ADR-039 removed, and couples a commercial-ish project to a personal licence. `TODO(unverified)`: the German 13 cm amateur power limit and whether the exact 2 400–2 483.5 MHz range is covered (amateur allocation begins at 2 320 MHz) — not read. |
| **J. Move band** | The 868 MHz ISM band has sub-bands with far more power: the repo's own `docs/frequency-plan-868.md` records 869.4–869.65 MHz at **500 mW ERP with ≤ 10 % duty** and 865.2–867.5 MHz at +14 dBm with no duty cycle (CEPT ERC/REC 70-03 Annex 1 `g` sub-bands). | **Blocked as designed**: ADR-034 D3 forbids 433-TX/868-RX because 2 × 433 = 866 MHz lands inside the 868 receive band — a self-inflicted harmonic collision. It is a *whole-link redesign*, and the 868 bands carry their own duty-cycle/LBT conditions that must be re-derived for whatever schedule is chosen. |

**Cross-cutting, and independent of which route is taken:**

1. **Compute the duty cycle from the configuration the link budget uses.** The repo currently
   asserts ~1.7 % and computes the link at SF12/BW125/255 B (9.02 s) — those are different
   radios (§ 5.1). Whichever is real, the number that goes in a compliance case must come
   from the same SF/BW/payload/interval.
2. **Clamp and prove.** The TX clamp + production test of ADR-039 §6 / ADR-041 D2 must be
   **per band and per modulation**: ≤ +12.15 dBm EIRP at 433 for the 10 mW ERP claim
   (≤ +2.15 dBm EIRP for the 1 mW ERP claim), and ≤ **+10 dBm EIRP at 2.4 GHz** for every
   2.4 GHz transmitter on the board *including the SX1280 ranging radio*.
3. **The 2.4 GHz ceiling is the finding to act on.** Everything else in this document is a
   condition the design can meet. The 10 mW EIRP 2.4 GHz ceiling is a limit on what the link
   *is*, and it belongs in ADR-041's record — the ADR's own falsification list calls for it.

---

## 8. `TODO(unverified)` — everything I could not confirm

1. **`TODO(unverified)` — whether Tabelle 3's D44a/D44b/D45c waives the ≤ 10 % duty-cycle and
   ≤ 25 kHz bandwidth parameters.** The row is printed as 10 mW ERP with an empty
   "Zusätzliche Parameter" cell and "–" for other restrictions, and the Vfg. says Tabelle 3's
   less-strict conditions are usable alongside Tabelle 2's; the EU footnote permits a member
   state to waive additional parameters entirely. **A written statement from BNetzA Referat
   221 is required before the design relies on it.** (This is the single largest open item in
   this document.)
2. **`TODO(unverified)` — the exact edition of ERC/REC 70-03.** The copy read is a national
   regulator's mirror of the **February 2011** edition ("Version of 9 February 2011"),
   <https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf>. The
   current edition could not be fetched from this host: `docdb.cept.org` failed TLS
   verification and returned no route (`curl` exit 60 / connection failure). The 433 and
   2.4 GHz rows quoted here match Vfg. 91/2025 and Decision (EU) 2025/105 exactly, so the
   substance is corroborated across three independent sources — but **the annex numbering and
   any wording changes between 2011 and today are unverified**, and a CEPT row should not be
   cited alone.
3. **`TODO(unverified)` — the German Frequenzplan's per-band "Nutzungsbestimmungen"** for
   433.05–434.79 MHz and 2400–2483.5 MHz (carried forward from the sibling analysis § 9 item
   9). Vfg. 91/2025 and ERC/REC 70-03 both show no airborne note; that is not proof the
   Frequenzplan has none.
4. **`TODO(unverified)` — the EU Decision's English wording for 45c** ("bandwidth" vs "channel
   spacing"). Only the German texts were read; both say *Bandbreite*.
5. **`TODO(unverified)` — whether two-way ranging qualifies as "Funkortung" (57b, 25 mW
   EIRP)** or as excluded point-to-point communication (→ 57a, 10 mW EIRP).
6. **`TODO(unverified)` — whether the `LoRa2021F33-2G4` module's EU declaration of conformity
   / CE marking covers 433.05–434.79 MHz operation and at what power** (Vfg. 91/2025 Hinweis
   2 / FuAG). The in-repo datasheet is not a DoC.
7. **`TODO(unverified)` — the Amtsblatt issue and page of Vfg. 91/2025** (carried forward from
   the sibling analysis § 9 item 11).
8. **`TODO(unverified)` — the German 13 cm amateur power limit** and the exact amateur frequency
   range (route I), if that route is ever considered.
9. **`TODO(unverified)` — whether the balloon's actual 433 antenna gain** (assumed 0 dBi /
   2.15 dBi, ADR-041 §0) is confirmed by a datasheet, and whether the ground 433 Yagi's
   12 dBi / 15 dBi is (the repo flags both). Both feed § 6's margins directly.

---

## 9. Sources

**Tier 1 — primary instruments (opened at first hand, 2026-10-07)**

- **BNetzA, *Allgemeinzuteilung von Frequenzen zur Nutzung durch Geräte geringer Reichweite
  (SRD)*, Vfg. 91/2025, November 2025** (PDF, 32 pp.; metadata: Title "Vfg 91/2025",
  Subject "Allgemeinzuteilung_SRD", Author "Bundesnetzagentur", created 2025-11-03,
  modified 2025-11-18) —
  <https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf?__blob=publicationFile&v=3>
  Quoted: Tabelle 1 (category definitions: *Breitband-Datenübertragungsgeräte*,
  *Funkortungsgeräte*, non-specific SRD); the Art. 3(3) deviation footnote and the
  "sowohl … als auch" sentence; the *Arbeitszyklus* definition (T_obs = 1 h); Tabelle 2
  entries 44a/44b/45c and 57a/57b/57c; Tabelle 3 entries D44a/D44b/D45c and D57c (p. 27,
  verified by rendering the page); footnotes [d], [4], [7]; Hinweise 1/2/5; *Befristung*.
- **BNetzA *Allgemeinzuteilungen* index** —
  <https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/start.html>
  (the page that lists vfg91_2025.pdf as the current SRD assignment).
- **Commission Decision 2006/771/EC, as amended by Implementing Decision (EU) 2025/105 of
  22 January 2025**, German text, Annex Table 2 —
  <https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32025D0105>
  (retrieved through the `r.jina.ai` reader proxy; EUR-Lex answers plain `curl` with
  HTTP 202 / empty body). Quoted: rows 44a/44b/45c and 57a/57b/57c with applicability dates,
  and the footnote permitting member states to waive additional parameters or permit higher
  values.
- **CEPT ERC/REC 70-03** (copy consulted: ARCEP mirror of the **February 2011** edition) —
  <https://www.arcep.fr/fileadmin/reprise/dossiers/frequences/ERC-REC-70-03E.pdf>
  Quoted: Annex 1 entries `f`, `f1`, `f2`, `h`; Annex 1 Note 1; Annex 1 Notes 4/4bis;
  Annex 3 entry `a` + Note 1 + "EN 300 328 sub-band a)"; the general text on SRD use on
  board aircraft; the "Duty cycle categories" definition and class table.
- **ETSI EN 300 328 V2.2.2 (2019-07)**, *Wideband transmission systems; Data transmission
  equipment operating in the 2,4 GHz band* —
  <https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf>
  Quoted: §4.3.2.2.3 (20 dBm, non-FHSS), §4.3.2.3.3 (10 dBm/MHz PSD), §4.3.2.5.3 (MU ≤ 10 %),
  §4.3.2.6 (adaptivity, DAA/LBT), §4.3.2.7.3 (OCB), §4.3.1.2.3 (20 dBm, FHSS), and the
  definitions of *wideband data transmission equipment*, *FHSS equipment*, *integral antenna*.

**Tier 1b — German statute referenced only via the sibling analysis** (not re-opened here;
the aviation side is out of scope for this document):
`docs/analysis/free-balloon-mass-threshold-DE.md` § 2–6 (LuftVG, LuftVO, LuftVZO, SERA).

**Tier 2 — repo sources used for the design and the link budget**

- `docs/analysis/free-balloon-mass-threshold-DE.md` — the sibling legal analysis (§ 7 radio
  entries; § 7.3 airborne; § 9 items 7/8/9/11 carried forward here).
- `docs/adr/009-antenna-strategy-v1-v2.md` — the 300 km balloon-to-ground design point and
  the V1 omnidirectional antenna decision.
- `docs/adr/020-deprecate-radiolib-adopt-raw-lr2021-spi.md` — raw 2-byte-opcode LR2021 SPI;
  LoRa / FLRC / GFSK only (no 802.11, no FHSS).
- `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`,
  `docs/adr/035-tdm-radio-schedule.md`,
  `docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md` — the band split, the TDM
  slot schedule (SX1280 ranging is the balloon's 2.4 GHz transmitter), and the daylight-only
  TX policy.
- `docs/adr/039-licence-exempt-433-design-point.md`,
  `docs/adr/041-rf-frontend-licence-exempt.md`,
  `docs/LINK-BUDGET-LICENCE-EXEMPT.md`, `docs/licence-exempt-design-point.md` — the
  licence-exempt design point, the per-direction link budget (433 +24.3 dB; 2.4 GHz +16.4 /
  +4.4 dB), the TX-clamp requirement, and the ~1.7 % duty-cycle claim corrected in § 5.1.
- `docs/bw-code-table.md` — LR2021 LoRa bandwidth codes and Hz constants (sub-GHz 62.5/125/
  250 kHz; narrow codes 7.8125/10.417/15.625/20.833 kHz; 2.4 GHz up to 812 kHz / 1 MHz).
- `docs/airtime_calc.py`, `docs/lr2021-lora-modulation-params-encoding.md` — the LoRa air-time
  formula (Semtech AN1200.13) and the SET_LORA_MODULATION_PARAMS encoding.
- `docs/inventory.md`, `docs/F33-MODULE-PLAN.md`, `tools/link_budget.py` — module
  sensitivities (−143 dBm sub-GHz; −136/−124 dBm at 2.4 GHz; tool LoRa table −137 dBm at
  SF12/BW125) and the FSPL arithmetic (134.7 dB @ 433, 149.6 dB @ 2400, 300 km).
- `docs/frequency-plan-868.md` — the 868 MHz sub-band power/duty-cycle alternatives
  (route J), which are that document's sourced findings, not re-derived here.
- `docs/analysis/radio_power_limits_model.py` — the companion model for this document;
  every table in § 5.1 and § 6 is its output.

**Corrected in this document (recorded, not silently changed elsewhere):**

- `docs/licence-exempt-design-point.md` § 3 — the **"integral antenna required"** condition at
  433 MHz is **not** in Vfg. 91/2025 (44a/44b/45c; D44a/D44b/D45c) or in ERC/REC 70-03
  Annex 1 entry `f` (§ 2.5).
- `docs/licence-exempt-design-point.md` § 7 vs `docs/adr/041-…` — the **~1.7 % duty-cycle
  claim and the SF12/BW125/255 B link-budget configuration are not the same radio** (§ 5.1).
- `docs/adr/041-…` D1/D4 and its falsification list — the **100 mW EIRP ground-transmitter
  assumption is not supportable for this modulation**; the ceiling is 10 mW EIRP (57a),
  which returns the "−5.6 dB, no LNA" case on correct grounds (§ 3.3, § 6.2).
