#!/usr/bin/env python3
"""rerun_quote.py — re-measure one JLCPCB PCB quote, fresh isolated page load.

This is the durable, in-repo re-verification tool for
docs/analysis/jlcpcb-pricing-and-size-tier.md and docs/adr/063-hub-outline-trim.md.

It is a self-contained re-implementation of the ~/quote-scratch/measure2.py routine
(the exact routine that produced every JSON in the sibling raw-evidence tree). It
drives the live JLCPCB online quote page (no gerber upload, no login needed to see a
price) and prints one line plus a full JSON of the observed quote.

REQUIRES (external to this repo):
  * playwright (>=1.60) under python3.13  —  /home/c03rad0r/.local/bin/python3.13
  * a Chrome + the persistent JLC profile at
      ~/.hermes/profiles/manager/state/jlc-browser9
    via  /home/c03rad0r/repos/jlcpcb-service/jlcpcb_client  (session.py: browser())

USAGE (the single command):
  python3.13 docs/analysis/jlcpcb-quote-2026-10/scripts/rerun_quote.py \
      --dims 102x102 --layers 4 --thickness 1.6mm

Defaults reproduce the ADR-063 decision point (102 x 102, 4 layers, 1.6 mm,
HASL-with-lead, qty 5, Single PCB). Compare the printed `calculated_price` with the
salvaged JSON named by --name (default: repro_<W>x<H>_<L>L_<T>).

Every run loads a FRESH page (new tab) so it is isolated, exactly as the original
batch did; `page_load` in the output JSON records that.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time

JLC_SERVICE = "/home/c03rad0r/repos/jlcpcb-service"
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reruns")

# --- JS from measure2.py (the routine that produced the salvaged JSONs) ---------

SETIN = r"""
([sel, v]) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  const el = document.querySelector(sel);
  if(!el) return 'MISSING';
  el.focus(); setter.call(el, String(v));
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('blur',{bubbles:true}));
  el.blur();
  return el.value;
}
"""

FINDRECT = r"""
([h, l]) => {
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith(h)) row=r;
  });
  if(!row) return {err:'no row'};
  const btns=[...row.querySelectorAll('button')];
  const norm=b=>(b.innerText||'').trim().replace(/\s+/g,' ');
  const t=btns.find(b=>norm(b)===l);
  if(!t) return {err:'no option', have:btns.map(norm)};
  if(t.disabled) return {err:'DISABLED', heading:h, option:l,
                        tip:(row.querySelector('label .pcb-faq-content')||{}).innerText||''};
  const bb=t.getBoundingClientRect();
  return {x: bb.x+bb.width/2, y: bb.y+bb.height/2, cls:t.className};
}
"""

READCUR = r"""
(h) => {
  let row=null;
  document.querySelectorAll('div.main-btn-group').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith(h)) row=r;
  });
  const cur = row ? row.querySelector('button.cur') : null;
  return cur ? cur.innerText.trim().replace(/\s+/g,' ') : null;
}
"""


def selected_rows(pg):
    return pg.evaluate(r"""
    () => { const res={};
      document.querySelectorAll('div.main-btn-group').forEach(r=>{
        const lab=r.querySelector('label'); if(!lab) return;
        const h=(lab.innerText||'').trim().split('\n')[0];
        const cur=r.querySelector('button.cur'); if(cur) res[h]=cur.innerText.trim().replace(/\s+/g,' ');
      }); return res; }""")


def set_option(pg, heading, label, tries=3):
    rec = {"heading": heading, "want": label}
    for attempt in range(tries):
        r = pg.evaluate(FINDRECT, [heading, label])
        if "err" in r:
            rec.update(r); rec["took"] = False; return rec
        pg.mouse.click(r["x"], r["y"])
        time.sleep(3)
        got = pg.evaluate(READCUR, heading)
        rec["got"] = got
        if got == label:
            rec["took"] = True; rec["attempts"] = attempt + 1
            return rec
    rec["took"] = False
    return rec


def read_quote(pg):
    t = pg.evaluate("document.body.innerText || ''")
    lines = [l.strip() for l in t.split("\n")]
    out = {}

    def val_after(lbl):
        for i, l in enumerate(lines):
            if l == lbl:
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].startswith("$"):
                        return lines[j]
        return None

    for key, lbl in [("engineering_fee", "Engineering fee"), ("board", "Board"),
                     ("via_covering", "Via Covering"), ("surface_finish", "Surface Finish"),
                     ("deburring_edge_rounding", "Deburring"), ("panel", "Panel"),
                     ("pcb_build_time_2days", "2 days")]:
        out[key] = val_after(lbl)
    for i, l in enumerate(lines):
        if l == "Calculated Price":
            for j in range(i + 1, min(i + 8, len(lines))):
                if lines[j].startswith("$"):
                    out["calculated_price"] = lines[j]; break
            else:
                out["calculated_price"] = None
        if l == "Shipping Estimate":
            out["shipping"] = lines[i + 1] if i + 1 < len(lines) else None
        if l == "Weight":
            for j in range(i + 1, min(i + 4, len(lines))):
                if re.match(r"^[0-9.]+ ?kg", lines[j] or ""):
                    out["weight"] = lines[j]; break
    bt = {}
    for i, l in enumerate(lines):
        if l in ("2 days", "24 hours") or l.startswith("24 hours"):
            if i + 1 < len(lines) and lines[i + 1].startswith("$") and l not in bt:
                bt[l] = lines[i + 1]
    out["build_time_lines"] = bt
    # special-offer class marker
    out["special_offer"] = None
    for i, l in enumerate(lines):
        if l == "Special Offer" and i + 1 < len(lines) and lines[i + 1].startswith("$"):
            out["special_offer"] = lines[i + 1]
    return out, t


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dims", default="102x102", help="WxH mm, e.g. 102x102 or 100x104")
    ap.add_argument("--layers", default="4")
    ap.add_argument("--thickness", default="1.6mm")
    ap.add_argument("--finish", default=None, help="e.g. 'ENIG' or 'LeadFree HASL'")
    ap.add_argument("--qty", default="5")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    m = re.match(r"^([0-9.]+)x([0-9.]+)$", args.dims)
    if not m:
        ap.error("--dims must be WxH, e.g. 102x102")
    x, y = m.group(1), m.group(2)
    name = args.name or f"repro_{x}x{y}_{args.layers}L_{args.thickness}"
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    sys.path.insert(0, JLC_SERVICE)
    from jlcpcb_client.session import browser, _goto
    from jlcpcb_client.selectors import QUOTE_URL

    with browser(headless=True) as pg0:
        # FRESH page in a new tab -> isolated, per the original batch method
        pg = pg0.context.new_page()
        pg.set_viewport_size({"width": 1500, "height": 1600})
        _goto(pg, QUOTE_URL, settle=18)
        time.sleep(2)

        log = {"name": name, "dims_entered": [x, y], "qty": args.qty,
               "at": datetime.datetime.now().isoformat(timespec="seconds"),
               "page_load": "FRESH navigation (new tab) -> isolated",
               "pristine_selected": selected_rows(pg)}
        steps = []
        log["dim_x_set"] = pg.evaluate(SETIN, ["input[name=stencilLength]", x])
        time.sleep(1)
        log["dim_y_set"] = pg.evaluate(SETIN, ["input[name=stencilWidth]", y])
        time.sleep(3)
        if args.finish:
            steps.append(set_option(pg, "Surface Finish", args.finish)); time.sleep(3)
        steps.append(set_option(pg, "Layers", args.layers)); time.sleep(4)
        steps.append(set_option(pg, "PCB Thickness", args.thickness)); time.sleep(4)
        log["steps"] = steps
        log["final_selected"] = selected_rows(pg)
        q, t = read_quote(pg)
        log["quote"] = q
        log["dims_input_readback"] = pg.evaluate(
            "() => { const xi=document.querySelector('input[name=stencilLength]');"
            " const yi=document.querySelector('input[name=stencilWidth]');"
            " return xi&&yi ? [xi.value, yi.value] : null; }")

    with open(os.path.join(out_dir, name + ".json"), "w") as fh:
        json.dump(log, fh, indent=2)
    with open(os.path.join(out_dir, name + ".txt"), "w") as fh:
        fh.write(t)
    sel = {k: v for k, v in log["final_selected"].items()
           if k in ("Layers", "PCB Thickness", "Surface Finish", "PCB Qty",
                    "Different Design", "Delivery Format")}
    print("=====", name)
    print(" dims_readback:", log["dims_input_readback"])
    print(" steps:", json.dumps(steps))
    print(" final(sel):", json.dumps(sel))
    print(" quote:", json.dumps(q))
    print(" wrote:", os.path.join(out_dir, name + ".json"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
