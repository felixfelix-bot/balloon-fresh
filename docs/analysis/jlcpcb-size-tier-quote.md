# JLCPCB size-tier quote analysis — 4-layer 103 x 103 mm v9 hub

**Status:** analysis only. **No order was placed.** This document informs a cost decision; it
does not make it, and it changes no board, schematic, placement or ADR decision.

**Type:** salvage of a background quoting run. A previous worker spent ~1 h driving the JLCPCB
online quote page and **timed out at 3600 s before writing its analysis**, but its raw
measurements survived on disk. This document is derived **entirely from those on-disk JSONs** —
**no browser session was re-driven to produce it** (the browser is what hung). See
§11 Provenance.

**Evidence location (outside the repo):** `~/quote-scratch/measurements/` — 36 per-config
JSONs plus `SUMMARY.json`; scripts (`measure2.py`, `probe*.py`, `batch*.json`, `batch*.log`) live in
`~/quote-scratch/`. **The raw JSONs are deliberately NOT committed here** (they live outside the
repo); a copy should be archived if this analysis is to be relied on long-term.

---

## 0. How to read the numbers in this document

Every figure below is tagged with its evidential status:

* **MEASURED** — read directly from a config JSON whose `quote` object carries a non-empty,
  non-zero price. These are the only numbers that may be quoted as fact.
* **INDICATIVE** — appears in `SUMMARY.json` or a residual-schema file but **not** in a valid
  config JSON; or a figure derived by arithmetic from MEASURED charge lines. Do not quote as a
  verified quote.
* **INVALID** — the config does not contain a usable quote (empty/zero price, or the requested
  option set failed to apply). Listed, never dropped, never presented as data.

Named option sets: unless a row says otherwise, a measurement is **4 layers / 1.6 mm /
HASL(with lead) / Via Plugged / Different Design 1 / Delivery "Single PCB" / qty 5 / FR-4 TG135 /
1 oz outer copper**. Deviations are visible in the table columns.

---

## 1. Isolation of the measurements

The task claim: *every config records `page_load` as a FRESH navigation (new tab) -> isolated.*

**Verified.** 35 of the 36 per-config JSONs carry the literal string
`"FRESH navigation (new tab) -> isolated"` in `page_load`; the only exception is `t1_103_4L_06`,
which has **no `page_load` field at all** (older probe schema) and is therefore excluded as
residual (§2). A fresh navigation per config means each figure was read from a freshly loaded page
with the default ("pristine") option set — the `pristine_selected` block in each JSON records that
start state — rather than carrying residual state between reads. **The claim holds for the valid
set.**

Note on `final_selected`: this document follows the in-force option set recorded in
`SUMMARY.json` (top-level `layers` / `thickness` / `surface_finish` / `via_covering` /
`different_design` / `delivery_format`) cross-checked against each JSON's `steps[]` `got`/`took`
fields. (In several per-config JSONs `final_selected` is captured as an empty object; the SUMMARY
fields and `steps[]` are the reliable record, and they agree.)

---

## 2. Valid measurements — full charge-line table

30 configs produced a usable quote. Each charge line is shown separately, alongside the
quoted total. All prices are USD **for the quoted quantity (qty 5)** and exclude shipping (shown
separately).

| config | dims entered (mm) | read-back | L | T | surface finish | via covering | DD | qty | Engineering fee | Board / Special Offer | Via Covering ($) | Surface Finish ($) | Panel ($) | Deburr/Edge ($) | 2-day build ($) | TOTAL | shipping | weight |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b_100_4L_08 | 100/100 | 100/100 | 4 | 0.8mm | LeadFree HASL | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $5.30 | — | — | — | $13.30 | $23.21 | 0.22kg |
| b_100_4L_16 | 100/100 | 100/100 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $0.00 | — | — | — | $8.00 | $23.21 | 0.29kg |
| b_101_4L_16 | 101/101 | 101/101 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $0.00 | — | — | — | $8.00 | $23.21 | 0.29kg |
| b_103_4L_08 | 103/103 | 103/103 | 4 | 0.8mm | LeadFree HASL | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $5.30 | — | — | — | $36.90 | $23.21 | 0.22kg |
| b_103_4L_16 | 103/103 | 103/103 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| b_89_4L_08 | 89/89 | 89/89 | 4 | 0.8mm | LeadFree HASL | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $5.20 | — | — | — | $13.20 | $23.21 | 0.20kg |
| b_89_4L_16 | 89/89 | 89/89 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $0.00 | — | — | — | $8.00 | $23.21 | 0.26kg |
| c_103_2L_06 | 103/103 | 103/103 | 2 | 1.6mm | HASL(with lead) | Tented | 1 | 5 | $4.00 | $5.20 (Board) | $0.00 | $0.00 | — | — | $0.00 | $9.20 | $23.21 | 0.30kg |
| g_100x106_4L_16 | 100/106 | 100/106 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| g_102_4L_16 | 102/102 | 102/102 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $0.00 | — | — | — | $8.00 | $23.21 | 0.30kg |
| g_102p5_4L_16 | 102.5/102.5 | 102.5/102.5 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.50 (Board) | $0.00 | $0.00 | — | — | — | $31.50 | $23.21 | 0.30kg |
| g_102p9_4L_16 | 102.9/102.9 | 102.9/102.9 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| g_103_4L_16_repeat | 103/103 | 103/103 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| g_106x100_4L_16 | 106/100 | 106/100 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| g_89_4L_16_repeat | 89/89 | 89/89 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $0.00 | — | — | — | $8.00 | $23.21 | 0.26kg |
| h_103_2L_16 | 103/103 | 103/103 | 2 | 1.6mm | HASL(with lead) | Tented | 1 | 5 | $4.00 | $5.20 (Board) | $0.00 | $0.00 | — | — | $0.00 | $9.20 | $23.21 | 0.30kg |
| i_103_2L_06_LF | 103/103 | 103/103 | 2 | 0.6mm | LeadFree HASL | Tented | 1 | 5 | $4.00 | $5.20 (Board) | $0.00 | $1.30 | — | — | — | $10.50 | $23.21 | 0.20kg |
| i_103_4L_04_ENIG | 103/103 | 103/103 | 4 | 1.6mm | ENIG | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $17.80 | — | — | — | $49.40 | $23.21 | 0.30kg |
| i_89_2L_06_LF | 89/89 | 89/89 | 2 | 0.6mm | LeadFree HASL | Tented | 1 | 5 | $4.00 | $3.90 (Board) | $0.00 | $1.30 | — | — | — | $9.20 | $23.21 | 0.18kg |
| j_103_4L_16_dd2 | 103/103 | 103/103 | 4 | 1.6mm | HASL(with lead) | Plugged | 2 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | $16.54 | — | — | $48.14 | $23.21 | 0.30kg |
| j_103_4L_16_repeat2 | 103/103 | 103/103 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.60 (Board) | $0.00 | $0.00 | — | — | — | $31.60 | $23.21 | 0.30kg |
| j_50_4L_04_ENIG | 50/50 | 50/50 | 4 | 1.6mm | ENIG | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $16.90 | — | — | — | $24.90 | $23.21 | 0.17kg |
| j_89_2L_16_repeat | 89/89 | 89/89 | 2 | 1.6mm | HASL(with lead) | Tented | 1 | 5 | — | $4.00 (Special Offer) | $0.00 | $0.00 | — | — | $0.00 | $4.00 | $23.21 | 0.26kg |
| j_89_4L_04_ENIG | 89/89 | 89/89 | 4 | 1.6mm | ENIG | Plugged | 1 | 5 | — | $8.00 (Special Offer) | $0.00 | $17.50 | — | — | — | $25.50 | $23.21 | 0.26kg |
| j_89_4L_16_dd2 | 89/89 | 89/89 | 4 | 1.6mm | HASL(with lead) | Plugged | 2 | 5 | $25.00 | $4.90 (Board) | $0.00 | $0.00 | $16.54 | — | — | $46.44 | $23.21 | 0.26kg |
| k_100x104_4L_16 | 100/104 | 100/104 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.50 (Board) | $0.00 | $0.00 | — | — | — | $31.50 | $23.21 | 0.30kg |
| k_104x100_4L_16 | 104/100 | 104/100 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $6.50 (Board) | $0.00 | $0.00 | — | — | — | $31.50 | $23.21 | 0.30kg |
| k_50x103_4L_16 | 50/103 | 50/103 | 4 | 1.6mm | HASL(with lead) | Plugged | 1 | 5 | $25.00 | $3.20 (Board) | $0.00 | $0.00 | — | — | — | $28.20 | $23.21 | 0.21kg |
| l_103_2L_04_ENIG | 103/103 | 103/103 | 2 | 0.4mm | ENIG | Tented | 1 | 5 | $33.00 | $5.20 (Board) | $0.00 | $17.80 | — | — | — | $56.00 | $23.21 | 0.18kg |
| l_89_2L_04_ENIG | 89/89 | 89/89 | 2 | 0.4mm | ENIG | Tented | 1 | 5 | $33.00 | $3.90 (Board) | $0.00 | $17.50 | — | — | — | $54.40 | $23.21 | 0.17kg |

### 2.1 Invalid / non-quote measurements (listed, not dropped)

| config | dims entered (mm) | read-back | L (final) | T (final) | price in config JSON | why it is NOT a valid quote |
|---|---|---|---|---|---|---|
| c_100_2L_06 | 100/100 | 100, 100 | 2 | 1.6mm | — | config JSON `quote.calculated_price` is EMPTY (""); the 0.6 mm thickness step returned DISABLED and was never applied. SUMMARY.json holds a `$4.00` figure but the config JSON does not -> not a valid quote (INDICATIVE at best). |
| c_89_2L_06 | 89/89 | 89, 89 | 2 | 1.6mm | — | config JSON `quote.calculated_price` is EMPTY (""); 0.6 mm DISABLED, never applied. SUMMARY.json holds `$4.00` -> not a valid quote. |
| h_100_2L_16 | 100/100 | 100, 100 | 2 | 1.6mm | — | config JSON `quote.calculated_price` is EMPTY ("") although the option set applied cleanly. SUMMARY.json holds `$4.00` -> not a valid quote. |
| h_89_2L_16 | 89/89 | 89, 89 | 2 | 1.6mm | — | config JSON `quote.calculated_price` is EMPTY ("") although the option set applied cleanly. SUMMARY.json holds `$4.00` -> not a valid quote. |
| i_89_4L_04_ENIG | 89/89 | 100, 100 | 2 | — | $0.00 | quote `calculated_price` = **$0.00**; the requested options did NOT apply (Layers stayed 2 not 4; ENIG stayed HASL(with lead); 0.4 mm DISABLED); dimension read-back is 100x100 for an 89x89 entry; shipping shows "Charge: Choose destination country first" and weight is unset. No usable quote. |
| t1_103_4L_06 | 103/103 | 103, 103 | 4 | 0.6mm | $31.60 | older probe schema (keys `click_layers`/`dims`/`selected_rows`), **no `page_load` field at all**, no pristine/final capture -> cannot be confirmed as an isolated FRESH navigation. Marked RESIDUAL. Records $31.60, which only corroborates the 103 mm headline (INDICATIVE). |

Two of these deserve a flag beyond "invalid":

* **The four empty-price 2-layer rows** (`c_100_2L_06`, `c_89_2L_06`, `h_100_2L_16`,
  `h_89_2L_16`): the per-config JSON has an **empty** price string, but `SUMMARY.json` records a
  complete `$4.00` "Special Offer" charge line for each. The two on-disk artifacts **disagree**.
  Because the config JSON — the primary per-measurement record — carries no price, these are
  **INDICATIVE at best ($4.00 plausible)**, not valid measurements, and they are excluded from the
  delta arithmetic. A re-run would resolve this cheaply.
* **`t1_103_4L_06`** is a residual-schema capture; its `$31.60` only corroborates the 103 mm
  headline and is **INDICATIVE**.

---

## 3. The cheap / expensive size-tier boundary

### 3.1 Location

**The boundary lies between 102 mm and 102.5 mm on the largest side.** Every valid 4-layer
1.6 mm measurement with a largest side <= 102 mm is priced as a flat promotional
"**Special Offer**"; every valid one with a largest side >= 102.5 mm is priced with an explicit
"**Engineering fee**" + "**Board**" charge.

Matched-option comparison (4L / 1.6 mm / HASL(with lead) / DD 1 / qty 5 / Single PCB):

| largest side | quoted total (qty 5) | configs |
|---|---|---|
| 89 mm | $8.00 | 2 config(s): b_89_4L_16, g_89_4L_16_repeat |
| 100 mm | $8.00 | 1 config(s): b_100_4L_16 |
| 101 mm | $8.00 | 1 config(s): b_101_4L_16 |
| 102 mm | $8.00 | 1 config(s): g_102_4L_16 |
| 102.5 mm | $31.50 | 1 config(s): g_102p5_4L_16 |
| 102.9 mm | $31.60 | 1 config(s): g_102p9_4L_16 |
| 103 mm | $31.60 | 3 config(s): b_103_4L_16, g_103_4L_16_repeat, j_103_4L_16_repeat2 |

Evidence pinning the boundary:

| largest side | class | total | config |
|---|---|---|---|
| 102 mm | CHEAP (Special Offer) | $8.00 | g_102_4L_16 |
| 102.5 mm | EXPENSIVE (Engineering fee $25.00 + Board $6.50) | $31.50 | g_102p5_4L_16 |
| 102.9 mm | EXPENSIVE (Engineering fee $25.00 + Board $6.60) | $31.60 | g_102p9_4L_16 |

### 3.2 What drives it — largest single dimension (NOT area, NOT perimeter)

**I agree with the task's reading: the driver is the largest single dimension.** The evidence is
strong enough to exclude area and perimeter outright:

| config | dims (mm) | area (mm²) | perimeter (mm) | class |
|---|---|---|---|---|
| g_102_4L_16 | 102 x 102 | 10404 | 408 | CHEAP |
| k_100x104_4L_16 | 100 x 104 | 10400 | 408 | EXPENSIVE |
| k_104x100_4L_16 | 104 x 100 | 10400 | 408 | EXPENSIVE |
| k_50x103_4L_16 | 50 x 103 | 5150 | 306 | EXPENSIVE |
| g_100x106_4L_16 | 100 x 106 | 10600 | 412 | EXPENSIVE |
| g_106x100_4L_16 | 106 x 100 | 10600 | 412 | EXPENSIVE |

* **Area is excluded:** `100 x 104` has area 10400 mm² — *smaller* than `102 x 102` (10404 mm²) —
  yet it is EXPENSIVE while `102 x 102` is CHEAP. A smaller board costing more rules out area.
  `50 x 103` (area 5150 mm², less than half) is also EXPENSIVE.
* **Perimeter is excluded:** `100 x 104` and `102 x 102` have the **same** perimeter (408 mm) but
  land in different tiers; and `50 x 103` (perimeter 306 mm, *smaller* than 408 mm) is EXPENSIVE.
* **Largest side explains every row:** cheap iff max(dims) <= 102 mm; expensive iff
  max(dims) >= 102.5 mm. `50 x 103` -> 103 -> expensive. `102 x 102` -> 102 -> cheap.
  `100 x 104` -> 104 -> expensive. All consistent.

**The mechanism is empirically located but NOT explained by the vendor.** The quote page's own
tooltip (captured in the `steps[]` of several JSONs) states only unrelated rules: 0.4 mm thickness
requires ENIG; 0.6 mm thickness is capped at 100 x 100 mm and unavailable for 1/4/6-layer; 0.8–1.0 mm
is capped at 300 x 300 mm. **Nothing on the page states a 102/102.5 mm tier rule.** The boundary is
therefore reported as an observed discontinuity; **no vendor-documented cause should be invented
for it.**

### 3.3 The boundary is not specific to 4 layers

The same split appears in the 2-layer set, and it is MEASURED at both ends:

| dims | layers | total | class | config |
|---|---|---|---|---|
| 89 x 89 | 2 | **$4.00** | CHEAP ("Special Offer") | j_89_2L_16_repeat (valid) |
| 100 x 100 | 2 | $4.00 | CHEAP ("Special Offer") | h_100_2L_16 (INDICATIVE — config price empty; $4.00 from SUMMARY.json) |
| 103 x 103 | 2 | **$9.20** | EXPENSIVE (Engineering fee $4.00 + Board $5.20) | h_103_2L_16 (valid) |
| 103 x 103 | 2 | $9.20 | EXPENSIVE (same lines) | c_103_2L_06 (valid; the 0.6 mm step failed so it reduced to the 1.6 mm build) |

So the tier rule is a property of the **size**, not of the layer count.

---

## 4. The delta at matched options

At the matched option set (4L / 1.6 mm / HASL(with lead) / Via Plugged / DD 1 / qty 5 /
Single PCB), comparing the top of the cheap class with the bottom of the expensive class:

| class | best representative | total | components |
|---|---|---|---|
| CHEAP | 89 / 100 / 101 / 102 x (same) mm | **$8.00** | single "Special Offer" line |
| EXPENSIVE | 103 x 103 mm | **$31.60** | Engineering fee $25.00 + Board $6.60 |
| EXPENSIVE | 102.5 x 102.5 mm | **$31.50** | Engineering fee $25.00 + Board $6.50 |

* **Absolute delta (102 -> 103 mm): $31.60 − $8.00 = $23.60** (MEASURED, both endpoints).
* **Percentage delta: +295.0%** of the cheap price (i.e. the expensive class is
  **3.95x** the cheap class). *INDICATIVE arithmetic on MEASURED endpoints.*
* At the nearest expensive point (102.5 mm) the delta is $23.50 (+293.8%).

**What the delta actually is:** crossing the boundary does not merely add a size premium — the
order **drops out of the promotional class**. The cheap class is a single flat "**Special Offer**"
line; the expensive class replaces it with an explicit **Engineering fee ($25.00 for 4-layer,
$4.00 for 2-layer)** plus a **Board** charge ($6.60 at 103 mm). **The $25.00 engineering fee is the
dominant term of the delta.** Caveat: that fee is a **per-order** charge, so the delta measured at
qty 5 will not scale proportionally to other quantities — **no other quantity was measured**, and
no extrapolation is offered.

For reference, the 2-layer matched delta is $9.20 − $4.00 = **$5.20 (+130%)** (h_103_2L_16 vs the
cheap-class 2-layer "Special Offer" $4.00, MEASURED at 89 x 89 in j_89_2L_16_repeat).

---

## 5. Reproducibility

The jump is **reproducible, not noise** — repeats landed on identical figures:

| config | dims | total |
|---|---|---|
| b_103_4L_16 | 103 x 103 | $31.60 |
| g_103_4L_16_repeat | 103 x 103 | $31.60 |
| j_103_4L_16_repeat2 | 103 x 103 | $31.60 |
| b_89_4L_16 | 89 x 89 | $8.00 |
| g_89_4L_16_repeat | 89 x 89 | $8.00 |
| h_103_2L_16 | 103 x 103 (2-layer) | $9.20 |
| c_103_2L_06 | 103 x 103 (2-layer) | $9.20 |

**task claim confirmed: repeats consistent -> YES.** 103 mm appears three times at $31.60 and
89 mm twice at $8.00, all under the same matched option set; the 2-layer 103 mm pair also agrees.

---

## 6. The `engineering_fee: null` reading in the cheap class

**Confirmed: this is NOT a parse failure.** In the cheap class the page genuinely does **not**
charge an engineering fee — it shows a **single line labelled "Special Offer"** instead of separate
"Engineering fee" + "Board" lines, which is why the parser's `engineering_fee` and `board` fields
are `null` there. Evidence:

* Every cheap-class record shows `"Special Offer"` as the first charge line in `SUMMARY.json`
  (e.g. `b_89_4L_16` -> `[['Special Offer','$8.00'], ['Via Covering','$0.00'], ['Surface Finish','$0.00'], ...]`),
  and its other charge lines parse normally (`via_covering` `$0.00`, `surface_finish` `$0.00`).
* Every expensive-class record shows an explicit `"Engineering fee"` line ($25.00 for 4-layer,
  $4.00 for 2-layer) and a `$6.60`/`$6.50`/`$5.20` `"Board"` line.
* Arithmetic closes: cheap `b_89_4L_16` = Special Offer $8.00 + $0.00 + $0.00 = $8.00 = its total;
  expensive `b_103_4L_16` = $25.00 + $6.60 + $0.00 = $31.60 = its total. Both reconcile exactly,
  so the `null` is a real absence of the line, not a scrape miss.

**Conclusion:** in the cheap class there is no engineering fee to find. The `null` is truthful.

---

## 7. Thickness / surface-finish confound — what CANNOT be separated

**A confound exists and must be stated:**

* Every **4-layer 0.8 mm** row came back with surface finish **LeadFree HASL**, and shows a
  non-zero Surface Finish charge ($5.20 at 89 mm; $5.30 at 100 mm and at 103 mm).
* Every **4-layer 1.6 mm** row came back with **HASL(with lead)**, Surface Finish charge **$0.00**.
* The 0.8 mm rows cost more: `89 x 89 4L 0.8 mm` = **$13.20** vs `89 x 89 4L 1.6 mm` = **$8.00**;
  `100 x 100 4L 0.8 mm` = $13.30 vs `100 x 100 4L 1.6 mm` = $8.00.

Because on this vendor the requested 0.8 mm thickness pulled the finish to LeadFree HASL, the
**thickness and surface-finish effects are entangled.** The $5.20–$5.30 difference on the 0.8 mm
rows contains *both* any thickness premium *and* the LeadFree HASL premium, and **this data set
cannot apportion them.**

* **What we can say (MEASURED):** choosing 0.8 mm instead of 1.6 mm costs about **+$5.20 to +$5.30**
  at matched size and layers, *and* changes the finish.
* **What we CANNOT say:** that 0.8 mm *alone* costs +$5.20–$5.30, or that LeadFree HASL *alone*
  costs that. **No thickness delta is reported, because it cannot be isolated from this data.**
* A partial, adjacent datum (still confounded): at 103 mm / 2 layers, the 0.6 mm + LeadFree HASL
  build (`i_103_2L_06_LF`) is $10.50 with a $1.30 Surface Finish line, versus $9.20 for the 1.6 mm
  build (`h_103_2L_16`) with a $0.00 finish line — here the whole $1.30 sits on the finish line at
  identical Engineering-fee and Board lines, hinting the LeadFree premium on 2-layer is small
  ($1.30). Note the conflicting `c_103_2L_06` record, whose finish line reads $0.00 despite a
  LeadFree HASL selection — so even this hint is inconsistent in the data.

---

## 8. "Different Design = 2" — two boards on one order

| config | dims | DD | delivery format | total | components |
|---|---|---|---|---|---|
| j_103_4L_16_dd2 | 103 x 103 | 2 | Panel by Customer | **$48.14** | Engineering fee $25.00 + Board $6.60 + **Panel $16.54** |
| j_89_4L_16_dd2 | 89 x 89 | 2 | Panel by Customer | **$46.44** | Engineering fee $25.00 + Board $4.90 + **Panel $16.54** |

**Implication (MEASURED charge lines, INDICATIVE interpretation):** setting Different Design = 2
forces the Delivery Format to "Panel by Customer" and adds a **$16.54 "Panel" charge**, and it
**pulls the smaller board out of the promotional class**: `89 x 89` at DD 1 is $8.00, but at DD 2 it
is $46.44 (Engineering fee $25.00 + Board $4.90 + Panel $16.54).

Combining the two boards into one order therefore costs **$48.14** (103 mm) — only **$16.54 more
than the 103 mm board alone** ($31.60). Against that:

* Two *separate* single-design orders would be $31.60 (103 mm) + $8.00 (89 mm) = **$39.60 in
  board/fees**, i.e. **$8.54 less** than the combined DD 2 order — *provided* the second board is
  <= 102 mm so it stays promotional.
* But **shipping is charged per order ($23.21 in every config)**: two orders ship twice
  (2 x $23.21 = $46.42) versus once for the combined order ($23.21). Landed, the combined DD 2
  order is ~$71.35 versus ~$86.02 for two separate orders.

**So the DD 2 route wins once shipping is counted, and loses if it is ignored.** These landed
figures are **INDICATIVE** (arithmetic over MEASURED charge lines, assuming shipping is per order
and unchanged). It also assumes the two designs are genuinely permitted on one order — an
ordering/eligibility question this data cannot answer.

---

## 9. Decision-relevant conclusion: the 1 mm trim (option, not decision)

### 9.1 The situation

The v9 hub is currently **103 x 103 mm**, which is **inside the expensive class**
(Engineering fee $25.00 + Board $6.60 = **$31.60** for qty 5, 4-layer / 1.6 mm / HASL(with lead)).
**102 x 102 mm is inside the cheap class** (flat "Special Offer" = **$8.00** at the same options).
A 1 mm trim per side is exactly the difference between those two classes.

### 9.2 What it saves (MEASURED endpoints, arithmetic)

* **$31.60 − $8.00 = $23.60 per 5-piece order** = **$4.72 per board** at this quantity.
* That is a **74.7% reduction** relative to the current 103 mm build — equivalently, the 103 mm
  build is **295% more expensive** than the 102 mm build (a **3.95x** multiplier).
* Almost all of the saving is the **$25.00 one-off engineering fee** that the cheap class does not
  charge; it is therefore **per order, not per board**, and the saving will not scale linearly with
  quantity (**only qty 5 was measured**).

### 9.3 What it costs in array area (arithmetic — INDICATIVE)

| outline | area (cm²) | vs 103 x 103 | vs the 106.1 cm² array requirement |
|---|---|---|---|
| **103 x 103** (current) | **106.09** | — | meets it (106.09 vs 106.1 = -0.01 cm²) |
| **102 x 102** (1 mm trim) | **104.04** | **−2.05 cm² (−1.9%)** | **-2.06 cm² (98.1% of requirement)** |
| 89 x 89 (the tempting shrink) | 79.21 | −26.88 cm² (−25.3%) | -26.89 cm² (74.7%) |

Read carefully:

* Relative to the **current 103 x 103 outline**, the trim to 102 x 102 costs **2.05 cm²
  ≈ 1.9% of board area**. That is the "roughly 2% area loss" figure — and it
  is the same *dollar* saving as shrinking to 89 mm, which costs **25.3%** of area.
  On a saving-per-square-centimetre basis the 1 mm trim is **~13x** better than the 89 mm shrink.
* **However, against the stated array requirement of 106.1 cm², 102 x 102 (104.04 cm²) is
  2.06 cm² (1.9%) SHORT.** The current 103 x 103
  outline (106.09 cm²) sits essentially exactly on that requirement. So the 1 mm trim is only
  viable **if the 106.1 cm² figure carries at least ~2% of slack, or the array can be re-optimised
  to fit in ~104 cm²** — a placement/layout question for whoever owns the array geometry.

### 9.4 Options, with a recommendation

| option | outline | build cost (qty 5) | area vs requirement | note |
|---|---|---|---|---|
| **A — keep as-is** | 103 x 103 | $31.60 | on requirement | no layout rework; pays the expensive class |
| **B — trim 1 mm/side** | 102 x 102 | **$8.00** | −1.94% (needs ~2% slack) | **−$23.60/order**; requires proving >= 2.05 cm² of placement slack |
| **C — shrink to 89 mm** | 89 x 89 | $8.00 | −24.9% | same saving as B for ~13x the area loss — **dominated by B** |

**Recommendation: pursue Option B, gated on a slack check.** Concretely — before committing to any
order, have the placement owner confirm whether the hub layout has **>= 2.05 cm² of usable slack**
that would let the outline go to 102 x 102 (or confirm the array can be re-optimised to ~104 cm²).
If it does, the 1 mm trim converts a $31.60 promotional-class-excluded build into an $8.00
promotional build — a **3.95x** reduction for a ~1.9% area cost. If it does not, **keep Option A**;
**Option C is dominated** and should be set aside: it buys the same saving for ~13x the area loss.

**This is not a decision made here.** The board outline and the array's area budget are the
operator's open duty choice (ADR-055 D3). This document quantifies the trade; it does not settle
it, and it changes no ADR, schematic, placement or board file. **No order was placed.**

---

## 10. Summary of the required output fields

| field | value |
|---|---|
| valid_measurements | 30 |
| invalid_measurements | 6 — c_100_2L_06, c_89_2L_06, h_100_2L_16, h_89_2L_16, i_89_4L_04_ENIG, t1_103_4L_06 (reasons in §2.1) |
| boundary_mm | between 102 mm and 102.5 mm on the largest side |
| boundary_driver | **largest single dimension** (area excluded by 100x104 < 102x102 in area yet priced higher; perimeter excluded by equal-perimeter 100x104 vs 102x102 in different tiers and smaller-perimeter 50x103 priced higher) |
| cheap_class_price | $8.00 (4-layer, 1.6 mm, qty 5 "Special Offer") |
| expensive_class_price | $31.60 (103 x 103 mm: $25.00 engineering fee + $6.60 board) |
| delta_absolute | $23.60 |
| delta_percent | +295.0% (expensive = 3.95x cheap) |
| repeats_consistent | **yes** — 103 mm -> $31.60 three times (b_103_4L_16, g_103_4L_16_repeat, j_103_4L_16_repeat2); 89 mm -> $8.00 twice (b_89_4L_16, g_89_4L_16_repeat); 2-layer 103 mm -> $9.20 twice (h_103_2L_16, c_103_2L_06) |
| engineering_fee_finding | `null` in the cheap class is truthful, not a parse failure — the class shows a single "Special Offer" line instead of Engineering fee + Board; arithmetic closes exactly |
| thickness_finish_confound | 0.8 mm rows returned LeadFree HASL (charged) and 1.6 mm rows HASL(with lead) (free); thickness and finish are therefore entangled — the +$5.20–$5.30 at 0.8 mm cannot be split between the two. No thickness-only delta is reported. |
| different_design_implication | DD=2 forces "Panel by Customer" + a $16.54 Panel charge and pulls the small board out of the promo class (89 mm: $8.00 -> $46.44). One combined DD=2 order (103 mm) = $48.14 vs $39.60 of board/fees for two separate orders; but shipping is per order ($23.21), so landed the combined order (~$71.35) beats two orders (~$86.02). |
| trim_1mm_saving | $23.60 per 5-piece order ($4.72/board) — the entire delta between the classes at qty 5 |
| trim_1mm_area_cost | −2.05 cm² (−1.9% of board area); against the 106.1 cm² requirement, 102 x 102 is 2.06 cm² (1.9%) short, so it needs ~2% slack in the array budget |
| recommendation | **Option B (trim to 102 x 102), gated on proving >= 2.05 cm² of placement slack**; else keep Option A (103 x 103). Option C (89 mm) is dominated (same saving, ~13x area loss). Operator's decision (ADR-055 D3). |
| salvage_provenance | salvage of a run that timed out at 3600 s before writing its analysis; all figures read from on-disk JSONs; no browser re-driven |
| raw_evidence_location | `~/quote-scratch/measurements/` (36 config JSONs + SUMMARY.json); scripts in `~/quote-scratch/` |
| adr_action | **none** — this document changes no ADR. It supplies evidence for ADR-055 D3, whose choice (array area) stays with the operator. |

---

## 11. Provenance and re-run note

* **What this is:** a salvage. A previous worker drove the JLCPCB quote page for ~1 h and was
  killed at the **3600 s** timeout **before writing its analysis**. Its 36 per-config
  JSONs and `SUMMARY.json` survived at **`~/quote-scratch/measurements/`**; the scripts that
  produced them (`measure2.py`, `probe*.py`, `batch*.json`, `batch*.log`) are in `~/quote-scratch/`.
* **What was done here:** read those JSONs, verified the isolation claim, located the tier boundary
  and its driver, tabulated every charge line, separated valid from invalid, and wrote this
  document. **No browser session was re-driven** (the browser is what hung).
* **Raw artefacts are NOT committed to the repo** — they live outside it and are referenced by
  path. Only this analysis document is committed.
* **Prices move. Re-run the quote before an actual order.** JLCPCB promos, engineering-fee levels
  and shipping change; the $8.00 / $31.60 figures are a 2026-10-07 snapshot. The four empty-price
  2-layer rows and the `t1` residual capture should also be re-taken to close the gaps in §2.1.
* **No order, cart, checkout, payment or account action was taken at any point.**

*Generated 2026-10-08 from the on-disk measurement JSONs.*
