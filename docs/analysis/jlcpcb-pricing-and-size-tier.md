# JLCPCB pricing and the 102 × 102 mm hub outline — size-tier boundary, measured

> **STATUS: ANALYSIS.** Evidence record for ADR-063 (`docs/adr/063-hub-outline-trim.md`). It
> changes no board, schematic, netlist, footprint or placement. It orders nothing.
> The one design decision it supports — the hub outline — is recorded as **ADR-063 (Proposed)**;
> the array-area question it *depends on* stays with **ADR-055 D3**.
>
> **Audience: future LLM sessions.** Written terse, command-bearing and path-bearing. Every price
> below traces to a JSON file committed under `docs/analysis/jlcpcb-quote-2026-10/`. No remembered
> or inferred number is presented as measured.

Generated 2026-10-08. Branch `docs/jlcpcb-pricing-and-outline-decision`.

---

## 0. How to read this document

Three evidential tags, used throughout:

| Tag | Meaning |
|---|---|
| **MEASURED** | The number is read directly from a committed config JSON whose `quote.calculated_price` is a non-empty `$` value **and** whose `final_selected` option set matches what is being claimed. Only these may be quoted as fact. |
| **INDICATIVE** | Derived by arithmetic from MEASURED endpoints, OR read from a config that is not a valid quote. Do not present as a verified quote. |
| **INVALID** | The config carries no usable quote, or the requested option set did not apply. Listed in §9, never quoted. |

Baseline option set for every price in this document unless a row says otherwise:
**4 layers · 1.6 mm · HASL(with lead) · Via Covering Plugged · Different Design 1 · Delivery
"Single PCB" · qty 5 · FR-4 TG135 · 1 oz outer copper.** Deviations are visible in the quote JSON
columns. Each config was read from a **fresh, isolated page load** (new tab); the field
`page_load = "FRESH navigation (new tab) -> isolated"` in each JSON records that.

---

## 1. The finding in one line

**On JLCPCB's online quote page, a board whose LARGEST single dimension is ≤ 102.0 mm falls in a
flat promotional class ($8.00 for qty 5, 4-layer, 1.6 mm); at ≥ 102.5 mm it falls in an expensive
class ($31.50–$31.60), and the step between them is $23.60.** The v9 hub at 103 × 103 mm sits one
millimetre on the wrong side of that step.

---

## 2. Method — how the numbers were obtained (and re-verified)

Method (the routine that produced every JSON in this tree):

1. Launch Chrome with the persistent JLC profile
   (`~/.hermes/profiles/manager/state/jlc-browser9`) via `jlcpcb_client.session.browser()`
   (`~/repos/jlcpcb-service`). **No gerber upload and no login are needed to render a price.**
2. Open the quote page in a **FRESH tab** (`_goto(QUOTE_URL, settle=18)`) — one fresh load per
   config, so no state carries between reads. The `pristine_selected` block in each JSON records
   the page's default option set at that load.
3. Set the two manual dimensions via `input[name=stencilLength]` (X) and `input[name=stencilWidth]`
   (Y) with real input/change/blur events.
4. Walk each spec row: `div.main-btn-group > label` + its `button` options; the current selection is
   the button with class `cur`. Vue ignores `element.click()`, so a **real mouse click at the
   bounding-box centre** is used; the applied value is read back from the `cur` button.
5. Parse the rendered quote text block ("Charge Details" → charge lines → "Calculated Price"),
   and record the **full** applied option set in `final_selected`.

The `quote` block in each JSON is the receipt: it prints `engineering_fee`, `board`,
`via_covering`, `surface_finish`, `calculated_price`, `shipping`, `weight`. A finding is only
accepted when `final_selected` confirms the option set the claim is about.

### 2.1 Re-verification — the single command

The in-repo re-runner (self-contained; reproduces one measurement on a fresh load):

```bash
python3.13 docs/analysis/jlcpcb-quote-2026-10/scripts/rerun_quote.py \
    --dims 102x102 --layers 4 --thickness 1.6mm
```

Expect: `"calculated_price": "$8.00"`, `final_selected` Layers `4` / PCB Thickness `1.6mm` /
Surface Finish `HASL(with lead)`, and `special_offer` `"$8.00"`. Any other combination is set with
`--dims WxH --layers N --thickness T [--finish F]`. Output JSON/TXT land in
`docs/analysis/jlcpcb-quote-2026-10/reruns/`. Comment in the script names the external
dependencies (playwright ≥1.60 under `python3.13`; the jlcpcb-service checkout; the JLC profile).

Re-derive the whole tier table (no browser needed) from the committed raw JSONs:

```bash
python3 -c "
import json,glob,os
for f in sorted(glob.glob('docs/analysis/jlcpcb-quote-2026-10/measurements/*.json')):
    if f.endswith('SUMMARY.json'): continue
    d=json.load(open(f)); q=d.get('quote',{}); fs=d.get('final_selected',{}) or d.get('selected_rows',{})
    print(f'{os.path.basename(f)[:-5]:24} {str(d.get(\"dims_entered\") or d.get(\"dims\")):12} L{fs.get(\"Layers\")} {fs.get(\"PCB Thickness\")} {fs.get(\"Surface Finish\"):16} {q.get(\"calculated_price\")}  eng={q.get(\"engineering_fee\")}')
"
```

### 2.2 False starts (recorded as part of the evidence, not just conclusions)

The run that produced this data cost ~1 hour and **timed out at 3600 s before writing anything up**;
the measurements survived. Within it, several approaches failed before the working routine:

- **`probe1.py` … `probe15.py`** (`docs/analysis/jlcpcb-quote-2026-10/scripts/`) — reconnaissance
  of auth state, form fields, and *when each thickness option is enabled*. `probe10.py` in
  particular produced a **self-inconsistent** availability matrix (its `after_surf`/`after_layers`
  re-read the pristine values, so its reads are unreliable) and is kept only as a **false start**;
  its one durable output is the captured vendor tooltip (see §7). **Do not cite `probe10_report.json`
  as a measurement.**
- **`t1_103_4L_06`** — an early capture under an older schema that **never had the fresh-load
  protocol** and whose thickness step never applied (see §10).
- **The `c_*` batch** — `c_89_2L_06`, `c_100_2L_06`, `c_103_2L_06` failed because **Surface Finish
  was set before the dimensions**, unlike the working `i_*` batch which set it after. The ordering
  bug is why they carry no price (see §9).

---

## 3. The two classes — the headline numbers (all qty 5, 4 layers, 1.6 mm, HASL-with-lead)

| dims (mm) | class | total | charge lines | config (all in `measurements/`) |
|---|---|---|---|---|
| 89 × 89 | CHEAP | **$8.00** | single "Special Offer" $8.00 | `b_89_4L_16`, `g_89_4L_16_repeat` |
| 100 × 100 | CHEAP | **$8.00** | single "Special Offer" $8.00 | `b_100_4L_16` |
| 101 × 101 | CHEAP | **$8.00** | single "Special Offer" $8.00 | `b_101_4L_16` |
| **102 × 102** | **CHEAP** | **$8.00** | single "Special Offer" $8.00 | `g_102_4L_16`, `res_102_4L_16` |
| 102.5 × 102.5 | EXPENSIVE | **$31.50** | Engineering fee $25.00 + Board $6.50 | `g_102p5_4L_16` |
| 102.9 × 102.9 | EXPENSIVE | **$31.60** | Engineering fee $25.00 + Board $6.60 | `g_102p9_4L_16` |
| 103 × 103 | EXPENSIVE | **$31.60** | Engineering fee $25.00 + Board $6.60 | `b_103_4L_16`, `g_103_4L_16_repeat`, `j_103_4L_16_repeat2`, `res_103_4L_16` |

**Boundary: empirically between 102.0 mm and 102.5 mm on the largest side.** The cheapest point of
the expensive class is 102.5 mm ($31.50, Board $6.50); the dearest point of the cheap class is
102.0 mm ($8.00).

**Delta between the two classes (MEASURED endpoints): $31.60 − $8.00 = $23.60 per qty-5 order**
(= **$4.72/board** at qty 5). The $25.00 **Engineering fee** that the cheap class omits is the
dominant term, and it is a **per-order** charge — **only qty 5 was measured, so do not extrapolate
the per-board saving to other quantities.**

---

## 4. What drives the class — the LARGEST SINGLE DIMENSION (not area, not perimeter)

| config | dims (mm) | area (mm²) | perimeter (mm) | max dim | class | total |
|---|---|---|---|---|---|---|
| `g_102_4L_16` | 102 × 102 | 10404 | 408 | 102 | CHEAP | $8.00 |
| `k_100x104_4L_16` | 100 × 104 | 10400 | 408 | **104** | EXPENSIVE | $31.50 |
| `k_104x100_4L_16` | 104 × 100 | 10400 | 408 | **104** | EXPENSIVE | $31.50 |
| `k_50x103_4L_16` | 50 × 103 | 5150 | 306 | **103** | EXPENSIVE | $28.20 |
| `g_100x106_4L_16` | 100 × 106 | 10600 | 412 | **106** | EXPENSIVE | $31.60 |
| `g_106x100_4L_16` | 106 × 100 | 10600 | 412 | **106** | EXPENSIVE | $31.60 |

- **Area is excluded:** `100 × 104` has area 10400 mm², *smaller* than `102 × 102` (10404 mm²), yet
  is EXPENSIVE while `102 × 102` is CHEAP. A smaller board costing more rules out area.
  `50 × 103` (5150 mm², less than half the area) is also EXPENSIVE.
- **Perimeter is excluded:** `100 × 104` and `102 × 102` share the *same* perimeter (408 mm) yet
  land in different classes; `50 × 103` (306 mm, smaller) is EXPENSIVE.
- **Largest side explains every row:** cheap iff `max(dims) ≤ 102.0`; expensive iff `max(dims) ≥ 102.5`.
  `50 × 103` → 103 → expensive. `102 × 102` → 102 → cheap. All consistent.

The same split holds at **2 layers**, so the tier is a property of the **size**, not the layer count
(`j_89_2L_16_repeat` 89 × 89 2L = $4.00; `h_103_2L_16` 103 × 103 2L = $9.20 =
Engineering fee $4.00 + Board $5.20).

### 4.1 ⚠ The mechanism is EMPIRICALLY LOCATED, NOT documented vendor policy

The quote page's own **tooltip does not state a 102/102.5 mm tier rule.** It documents only
thickness rules (§7). **No future session may present the 102/102.5 mm step as vendor-documented
policy.** It is an observed discontinuity, reproducible at the endpoints, with **no published
cause**; do not invent one.

---

## 5. The mechanism of the price jump: the Engineering-fee line appears / disappears

Crossing the boundary does not add a size premium — the order **drops out of a promotional class**:

| class | charge lines in `quote` | reconciles to |
|---|---|---|
| CHEAP (`g_102_4L_16`) | `Special Offer $8.00`, Via Covering $0.00, Surface Finish $0.00 — **no `engineering_fee`, no `board`** | **$8.00** ✓ |
| EXPENSIVE (`b_103_4L_16`) | `Engineering fee $25.00` + `Board $6.60` + Via Covering $0.00 — **no "Special Offer"** | **$31.60** ✓ |

In the cheap class, the parser's `engineering_fee` (and `board`) fields are `null` because **the
line is genuinely ABSENT** — the page renders a single "Special Offer" line instead. **The absence
IS the mechanism, not a parse failure.** Both totals reconcile exactly from their own charge lines
(§2.1 re-derivation prints them).

---

## 6. Reproducibility — the tier is not noise

| dims | total | configs |
|---|---|---|
| 103 × 103, 4L 1.6 mm | $31.60 ×4 | `b_103_4L_16`, `g_103_4L_16_repeat`, `j_103_4L_16_repeat2`, `res_103_4L_16` |
| 102 × 102, 4L 1.6 mm | $8.00 ×2 | `g_102_4L_16`, `res_102_4L_16` |
| 89 × 89, 4L 1.6 mm | $8.00 ×2 | `b_89_4L_16`, `g_89_4L_16_repeat` |

103 mm was measured **four separate times**, all $31.60; 102 mm **twice**, both $8.00; 89 mm
**twice**, both $8.00 — each on a fresh isolated load. **`repeats_consistent = YES`.** The
`res_*` configs are the 2026-10-08 closeout re-runs (§14).

---

## 7. The unresolved thickness / surface-finish CONFOUND

**On this vendor, PCB thickness and surface finish are coupled by the form.** Measured:

| config | dims | L | thickness | surface finish (applied) | Surface Finish charge | total |
|---|---|---|---|---|---|---|
| `b_89_4L_16` | 89 × 89 | 4 | 1.6 mm | HASL(with lead) | $0.00 | **$8.00** |
| `b_89_4L_08` | 89 × 89 | 4 | 0.8 mm | **LeadFree HASL** | $5.20 | **$13.20** |
| `b_100_4L_16` | 100 × 100 | 4 | 1.6 mm | HASL(with lead) | $0.00 | **$8.00** |
| `b_100_4L_08` | 100 × 100 | 4 | 0.8 mm | **LeadFree HASL** | $5.30 | **$13.30** |

Every 4-layer **0.8 mm** row came back **LeadFree HASL** with a non-zero Surface Finish charge
($5.20/$5.30); **every** 4-layer **1.6 mm** row came back **HASL(with lead)** with Surface Finish
$0.00. **The +$5.20–$5.30 at 0.8 mm therefore contains both any thickness premium AND the LeadFree
HASL premium, and this data set cannot apportion them.**

**State it plainly: a thickness price effect CANNOT be separated from a finish effect with the data
in hand. Do NOT assert a thickness price effect.** What may be said (MEASURED): choosing 0.8 mm
instead of 1.6 mm costs ≈ +$5.20–$5.30 at matched size and layers **and** changes the finish.
What may NOT be said: that 0.8 mm *alone*, or LeadFree HASL *alone*, costs that.

### 7.1 Vendor thickness policy (captured verbatim in our own measurement output)

Several JSONs captured the vendor's own thickness tooltip (e.g. `steps[].tip` in
`i_103_4L_04_ENIG`, `i_89_4L_04_ENIG`, `j_*_4L_04_ENIG`; also `logs/batchB.log`). Verbatim:

> "1. For boards with a 0.40 mm thickness, we only accept an ENIG finish. These cannot be made with
> a panel and are not available for 1-layer PCBs. 2. For boards with a 0.60 mm thickness, the
> maximum PCB size is 100 mm x 100 mm. This thickness is not available for 1-layer, 4-layer, or
> 6-layer PCBs. 3. For boards with a 0.8 mm to 1.0 mm thickness, the maximum PCB size is 300 mm x
> 300 mm."

This is **documented vendor policy, captured by us** (contrast §4.1 — the *size tier* is not).
Measured consequences available in this data:
- **0.4 mm at 2 layers + ENIG** is offered: `l_89_2L_04_ENIG` $54.40, `l_103_2L_04_ENIG` $56.00.
- **0.4 mm requested at 4 layers** → option **DISABLED** (`i_103_4L_04_ENIG`, `j_89_4L_04_ENIG`,
  `res_102_4L_04_ENIG` — the last at 102 mm, ENIG applied, 0.4 mm still DISABLED, final = 102 mm /
  4L / 1.6 mm / ENIG = **$25.80** = Special Offer $8.00 + Surface Finish $17.80, i.e. **still the
  cheap class at 102 mm with ENIG**).
- **0.6 mm requested at 4 layers** → option **DISABLED** (`res_103_4L_06`, §10).
- **0.6 mm at 2 layers + LeadFree HASL** applied: `i_89_2L_06_LF` $9.20, `i_103_2L_06_LF` $10.50
  (note: 103 mm at 0.6 mm applied in practice, which the tooltip's "max 100 × 100 mm" line would
  not predict — record the observation, do not resolve it here).

**Conservative reading for the hub:** if the hub is **4-layer**, the thin options (0.4 / 0.6 mm) are
**not offered**. This bears directly on ADR-055 D4 (0.4 mm board) and is carried as follow-up **(b)**
(§12) — it is not decided here.

---

## 8. The 1 mm trim — the decision this evidence supports

- **Current outline:** 103 × 103 mm → area **106.09 cm²**.
- **Proposed outline:** 102 × 102 mm → area **104.04 cm²**.
- **Area retained:** 10404 / 10609 = **98.07 %** (≈ −2.05 cm², −1.9 %).
- **Saving at qty 5, 4-layer:** **$23.60** (from $31.60 to $8.00). The board is currently exactly
  **one millimetre** outside the cheap tier.

**Rejected alternative — 89 × 89 mm.** It saves the *same* $23.60 (it is also in the cheap class)
but shrinks the area to 7921 mm² = **79.21 cm²**, forfeiting (106.09 − 79.21)/106.09 = **25.3 %** of
the array. On a saving-per-cm² basis the 1 mm trim is ~13× better. **It is dominated.**

---

## 9. Invalid / incomplete configurations (listed, never quoted)

These configs must **never** be cited as prices. (5 named in the task brief + the residual schema.)

| config | requested | what happened | price in JSON |
|---|---|---|---|
| `c_89_2L_06` | 2L, 0.6 mm, LeadFree HASL | finish set before dims; 0.6 mm step failed; final = 2L / **1.6 mm** | empty (`""`) |
| `c_100_2L_06` | 2L, 0.6 mm, LeadFree HASL | same ordering bug; final = 2L / **1.6 mm** | empty (`""`) |
| `h_89_2L_16` | 2L, 1.6 mm | options applied cleanly but the price string was not captured | empty (`""`) |
| `h_100_2L_16` | 2L, 1.6 mm | same | empty (`""`) |
| `i_89_4L_04_ENIG` | 4L, 0.4 mm, ENIG | options did **not** apply (Layers stayed 2, finish stayed HASL-with-lead, 0.4 mm DISABLED); dims read back 100 × 100 for an 89 × 89 entry; shipping = "Choose destination country first" | `$0.00` |
| `t1_103_4L_06` | 103, 4L, 0.6 mm | residual schema; **no `page_load` field at all**; itemised in §10 | $31.60 (INDICATIVE only) |

Note: `SUMMARY.json` records `$4.00` for the four empty-price 2-layer rows, disagreeing with their
per-config JSONs. **The per-config JSON is the primary record and it carries no price**, so those
rows are **not** valid quotes.

---

## 10. The residual `t1_103_4L_06` — CLOSED 2026-10-08 (fresh load)

`t1_103_4L_06` claimed a 103 mm / 4-layer / **0.6 mm** price of $31.60 but was captured **without a
fresh page load** and, on inspection, its own `selected_rows` read back **PCB Thickness = 1.6 mm** —
i.e. its thickness step never applied, and $31.60 is simply the 103 × 103 / 4L / 1.6 mm price.
It was therefore flagged INDICATIVE, and the "our candidate 0.6 mm" measurement was missing.

**Closure (measured, fresh isolated load 2026-10-08):** `res_103_4L_06`
(`measurements/res_103_4L_06.json`) — Layers 4 applied; **PCB Thickness 0.6 mm → `err: DISABLED`**
(final thickness stayed 1.6 mm); quote $31.60 at 103 × 103 / 4L / 1.6 mm. Combined with §7.1:

> **There is no valid 103 mm / 4-layer / 0.6 mm quote, and there cannot be one: JLCPCB does not
> offer 0.6 mm on a 4-layer board** (vendor tooltip: "not available for 1-layer, 4-layer, or
> 6-layer PCBs"). `t1_103_4L_06` was a 1.6 mm measurement mislabelled by its intended-but-unapplied
> option. **The residual is closed as "configuration not offered", not as "measurement pending".**

This does **not** answer follow-up (b) for the hub at 2 layers; 0.6 mm / 2L is offered and measured
(`i_103_2L_06_LF` $10.50), but 103 mm 2L is in the expensive class and 102 mm 2L 0.6 mm was not
measured.

---

## 11. Dependency — this is a PRICING-driven outline; the array area is owned elsewhere

**This finding is a cost fact. It is not an array-sizing input.**

- The array area needed for **full hub-only duty** is **106.1 cm²** (ADR-051 §1.4 / ADR-055 D3),
  which is exactly the 103 × 103 mm outline (103² = 106.09 cm² ≈ 106.1 cm²).
- Harvestable day-mean energy scales **linearly with installed area** (ADR-055 D3). A trim to
  102 mm yields 104.04 cm² = **98.07 % of 106.1 cm²**, so it can hold **≈ 98.1 % of the full-design
  sustained duty** (equivalently, the full 0.388 W design is **~1.9 % short**).
- **ADR-055 D3 owns the final area decision** (the operator's sustained-duty choice: full / ≈75 % /
  ≈50 %, i.e. ≈106 / ≈80 / ≈53 cm²). **This pricing record must not silently redefine that
  requirement.** If the required duty needs the full 106.1 cm², then **102 mm and the cheap tier are
  mutually exclusive** — pick the area, pay the class. **Stated explicitly: the two cannot both be
  satisfied at full duty; the area requirement wins if the operator chooses full duty.**

---

## 12. Outstanding measurements / follow-ups

| # | Item | Owner |
|---|---|---|
| **(a)** | **DONE** — the missing 103 mm 0.6 mm fresh measurement is closed as "not offered" (§10). No pending 103 mm 0.6 mm quote exists or can exist. | closed |
| **(b)** | **Is 102 × 102 mm also valid at 0.4 mm / 0.6 mm thickness, given the finish coupling?** Measured: 0.6 mm/4L and 0.4 mm/4L are **not offered** (0.4 mm DISABLED at 102 mm 4L too — `res_102_4L_04_ENIG`); 0.4 mm requires ENIG and works at 2 layers. So the thin options exist only at **2 layers**, and no 102 mm **2-layer** quote was taken. Needs a fresh 102 mm 2L run **and** a hub layer-count decision (ADR-048 §5 item 5). | array/hub design |
| **(c)** | **Does the hub-plate stiffness/deflection work change the thickness answer?** Branch `analysis/hub-thickness-deflection` (committed analysis `docs/analysis/hub-thickness-deflection.md`) is the input; if it rules out 0.4/0.6 mm for stiffness, the vendor availability in §7.1 becomes moot for the hub. | hub mechanics |
| **(d)** | **RE-PLACE.** The 1 mm trim **re-opens hub placement** — the board was placed and frozen at 103 mm. ADR-063 requires a **re-place** (re-run the ADR-030 deterministic placement gate against 102 × 102 mm); the frozen placement hash does not carry. | PCB layout |

---

## 13. Provenance

- **What this is:** a salvage. A previous worker drove the JLCPCB quote page for ~1 hour and was
  killed at the 3600 s timeout **before writing its analysis**; the raw JSONs survived on disk.
- **Raw evidence, committed here** under `docs/analysis/jlcpcb-quote-2026-10/`:
  - `measurements/` — 40 per-config `.json` + `.txt` (the page text) + `SUMMARY.json`.
  - `logs/` — `batch*.log` (the per-config print-outs), `batch*.json` (config lists),
    `probe10.log`, `probe10_report.json`, `closeout.log`.
  - `scripts/` — `measure.py`, `measure2.py` (the routine), `parse_measurements.py`, `probe*.py`
    (false starts), `rerun_quote.py` (the in-repo re-verifier), `closeout.py`.
  - **These are SALVAGED RAW EVIDENCE, committed for durability and reviewability. They are NOT a
    re-derivation.** The `measurements/` JSONs were produced by the timed-out worker (except
    `res_*`, produced 2026-10-08 to close §10); the docs read them, not a fresh browser session.
- **Prices move.** The $8.00 / $31.50–$31.60 figures are a 2026-10-07/08 snapshot. Re-run the quote
  (§2.1) before any real order; promos, engineering-fee levels and shipping change.
- **No order, cart, checkout, payment or account action was taken at any point.**
- **Sibling record:** a separate salvage branch `analysis/jlcpcb-size-tier-quote-salvage` (NOT on
  `main`) carries `docs/analysis/jlcpcb-size-tier-quote.md`, a differently-scoped analysis of the
  same raw run that did **not** commit the raw JSONs and left the outline choice open. This document
  supersedes nothing of it; it is noted so a future session does not mistake one for the other.

---

## 14. Closeout re-runs — 2026-10-08 (fresh isolated page loads)

Four measurements were re-taken on 2026-10-08 to close the residual (§10) and re-confirm the
decision size. All four are committed under `measurements/res_*.json`; the routine was
`docs/analysis/jlcpcb-quote-2026-10/scripts/closeout.py` (same method as §2, via `measure2.measure`).

| config | dims | requested | applied (final_selected) | total | note |
|---|---|---|---|---|---|
| `res_103_4L_06` | 103 × 103 | 4L / 0.6 mm | 4L / **1.6 mm** — 0.6 mm `DISABLED` | $31.60 | **closes the residual**: 0.6 mm is not offered at 4 layers (§10) |
| `res_103_4L_16` | 103 × 103 | 4L / 1.6 mm | 4L / 1.6 mm / HASL(with lead) | $31.60 | 4th independent 103 mm repeat |
| `res_102_4L_16` | 102 × 102 | 4L / 1.6 mm | 4L / 1.6 mm / HASL(with lead) | **$8.00** | fresh re-confirm of the **decision size**; `engineering_fee` and `board` are `null`, a `Special Offer` line present |
| `res_102_4L_04_ENIG` | 102 × 102 | 4L / ENIG / 0.4 mm | 4L / **1.6 mm** / ENIG — 0.4 mm `DISABLED` | $25.80 | 0.4 mm also not offered at 4 layers; 102 mm + ENIG **stays in the cheap class** ($8.00 + $17.80 finish) |

`closeout.log` (in `logs/`) holds the raw print-outs. The re-runner to reproduce any of these:
`python3.13 docs/analysis/jlcpcb-quote-2026-10/scripts/rerun_quote.py --dims 103x103 --layers 4 --thickness 0.6mm`.
