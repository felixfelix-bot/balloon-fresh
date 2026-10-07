# JLCPCB quote evidence tree — salvaged raw measurements (2026-10)

**This is SALVAGED RAW EVIDENCE, not a re-derivation.** A worker drove the live JLCPCB online quote
page for ~1 hour on 2026-10-07/08 and **timed out at 3600 s before writing anything up**; these
files survived on disk and are committed here so the numbers are **durable and reviewable in-repo**.
The analysis that reads them is `docs/analysis/jlcpcb-pricing-and-size-tier.md`; the decision record
is `docs/adr/063-hub-outline-trim.md`.

**Do not treat any file here as authority on its own.** The docs read *these* JSONs; they did not
re-drive the browser (the browser is what hung). The one exception: the four `res_*` configs were
produced on **2026-10-08** to close the `t1_103_4L_06` residual — same method, fresh page loads.

## Layout

```
measurements/  — 41 JSON (40 per-config + SUMMARY.json) + 40 .txt (the rendered page text)
logs/          — batch*.log (per-config print-outs), batch*.json (config lists),
                 probe10.log + probe10_report.json (a FALSE START — see below), closeout.log
scripts/       — measure.py, measure2.py (the routine), parse_measurements.py,
                 probe1..15.py (false starts), rerun_quote.py (in-repo re-verifier),
                 closeout.py (the 2026-10-08 residual-closure run)
```

## What each per-config JSON records

- `dims_entered` / `dims_input_readback` — the two manual dimensions (mm) and the values read back
  from the page inputs.
- `page_load` — `"FRESH navigation (new tab) -> isolated"`. One fresh load per config; the
  `pristine_selected` block records the page default at that load. (`t1_103_4L_06` has **no**
  `page_load` — older schema; excluded as residual.)
- `steps[]` — each spec-row attempt: `heading`, `want`, `got`, `took` (did it apply), `attempts`,
  and `tip` when an option was `DISABLED`.
- `final_selected` — the **full applied option set**; this is what a claim must match.
  (`t1_103_4L_06` uses the older key `selected_rows`.)
- `quote` — the receipt: `engineering_fee`, `board`, `via_covering`, `surface_finish`,
  `calculated_price`, `shipping`, `weight`, `build_time_lines`.

## Warning: false starts inside this tree

- **`logs/probe10_report.json` is NOT a measurement.** Its availability reads re-read the pristine
  values (`after_surf`/`after_layers`), so it is self-inconsistent. Its one durable output is the
  captured vendor thickness tooltip (quoted in the analysis doc §7.1).
- **`t1_103_4L_06`** is residual schema, no fresh-load marker, and its 0.6 mm step never applied
  (its own `selected_rows` read back 1.6 mm). Closed 2026-10-08 as *configuration not offered*
  (`measurements/res_103_4L_06.json`).
- The `c_*` configs failed because Surface Finish was set **before** the dimensions (ordering bug);
  they carry no price and are listed as INVALID in the analysis doc §9.

## Re-verification

```bash
# re-measure one point on a fresh load (the single command):
python3.13 docs/analysis/jlcpcb-quote-2026-10/scripts/rerun_quote.py --dims 102x102 --layers 4 --thickness 1.6mm

# re-derive the whole table with no browser:
python3 -c "import json,glob,os
for f in sorted(glob.glob('docs/analysis/jlcpcb-quote-2026-10/measurements/*.json')):
    if f.endswith('SUMMARY.json'): continue
    d=json.load(open(f)); q=d.get('quote',{}); fs=d.get('final_selected',{}) or d.get('selected_rows',{})
    print(os.path.basename(f)[:-5], d.get('dims_entered') or d.get('dims'), fs.get('Layers'), fs.get('PCB Thickness'), fs.get('Surface Finish'), q.get('calculated_price'))"
```

Prices are a **2026-10-07/08 snapshot**; re-run before any real order. **No order, cart, checkout or
account action was taken.**
