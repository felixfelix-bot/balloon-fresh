"""Measure JLCPCB manual-dimension quotes with verified option toggles.

Facts established by probing (2026-10-07):
  * quote page accepts MANUAL dimensions: input[name=stencilLength] (X), [name=stencilWidth] (Y)
  * no gerber upload and no login needed to render a price
  * each spec row is  div.main-btn-group > label(innerText startsWith heading) + button options
  * the current selection is the button carrying class 'cur'
  * element.click() is ignored by these Vue components -> real mouse click at bbox centre
  * options can be DISABLED (e.g. 0.6mm under hasl-with-lead) -> must skip + report
"""
import json, os, sys, time, datetime, re
sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto
from jlcpcb_client.selectors import QUOTE_URL

OUT = os.path.expanduser("~/quote-scratch/measurements")
os.makedirs(OUT, exist_ok=True)

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

KNOWN_ROWS = ["Base Material","Layers","PCB Qty","Product Type","Different Design","Delivery Format",
  "PCB Thickness","PCB Color","Silkscreen","Material Type","Surface Finish","Outer Copper Weight",
  "Inner Copper Weight","Via Covering","Via Plating Method","Min via hole size/diameter",
  "Board Outline Tolerance","Confirm Production file","Mark on PCB","Electrical Test",
  "Gold Fingers","Castellated Holes","Edge Plating","Blind Slots","UL Marking",
  "Humidity Indicator Card","High Precision PCB"]

SETQTY = r"""
(q) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
  let row=null;
  document.querySelectorAll('div.main-btn-group, div.formgroup').forEach(r=>{
    const lab=r.querySelector('label');
    if(lab && (lab.innerText||'').trim().startsWith('PCB Qty')) row=r;
  });
  if(!row) return {err:'no qty row'};
  const el = row.querySelector('input');
  if(!el) return {err:'no qty input'};
  el.focus(); setter.call(el, String(q));
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  el.dispatchEvent(new Event('blur',{bubbles:true})); el.blur();
  return {set: el.value};
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
            rec["took"] = True; rec["attempts"] = attempt+1
            return rec
    rec["took"] = False
    return rec

def read_quote(pg):
    t = pg.evaluate("document.body.innerText || ''")
    lines = [l.strip() for l in t.split("\n")]
    out = {}
    def val_after(lbl):
        for i,l in enumerate(lines):
            if l == lbl:
                for j in range(i+1, min(i+5, len(lines))):
                    if lines[j].startswith("$"): return lines[j]
        return None
    for key,lbl in [("engineering_fee","Engineering fee"),("board","Board"),
                    ("via_covering","Via Covering"),("surface_finish","Surface Finish"),
                    ("deburring_edge_rounding","Deburring"),("panel","Panel"),
                    ("pcb_build_time_2days","2 days")]:
        out[key] = val_after(lbl)
    for i,l in enumerate(lines):
        if l == "Calculated Price":
            for j in range(i+1, min(i+8, len(lines))):
                if lines[j].startswith("$"):
                    out["calculated_price"] = lines[j]; break
            else:
                out["calculated_price"] = None
        if l == "Shipping Estimate": out["shipping"] = lines[i+1] if i+1<len(lines) else None
        if l == "Weight":
            for j in range(i+1, min(i+4, len(lines))):
                if re.match(r"^[0-9.]+ ?kg", lines[j] or ""):
                    out["weight"] = lines[j]; break
    # build-time block
    bt = {}
    for i,l in enumerate(lines):
        if l in ("2 days","24 hours") or l.startswith("24 hours"):
            if i+1 < len(lines) and lines[i+1].startswith("$") and l not in bt:
                bt[l] = lines[i+1]
    out["build_time_lines"] = bt
    return out, t

def fresh_page(ctx):
    pg = ctx.new_page()
    pg.set_viewport_size({"width": 1500, "height": 1600})
    _goto(pg, QUOTE_URL, settle=18)
    time.sleep(2)
    return pg

def measure(ctx, name, x, y, opts, qty=5, surf=None, note=""):
    """opts: list of [heading, label] to set, in order."""
    pg = fresh_page(ctx)
    log = {"name": name, "dims_entered": [x, y], "qty": qty, "note": note,
           "at": datetime.datetime.now().isoformat(timespec="seconds"),
           "page_load": "FRESH navigation (new tab) -> isolated"}
    log["pristine_selected"] = selected_rows(pg)
    # PCB Qty is a PRESET dropdown widget (#QtyDom) that ignores synthetic input events.
    # It is therefore never mutated here: every measurement below is at the page default qty.
    try:
        log["qty_readback"] = pg.evaluate(r"""() => {
          const row=document.getElementById('QtyDom');
          return row ? (row.innerText||'').trim().replace(/\s+/g,' ') : null; }""")
    except Exception as e:
        log["qty_readback"] = f"ERR {str(e)[:60]}"
    time.sleep(4)
    if surf:
        log.setdefault("steps", []).append(set_option(pg, "Surface Finish", surf))
        time.sleep(3)
    # dimensions
    log["dim_x_set"] = pg.evaluate(SETIN, ["input[name=stencilLength]", x])
    time.sleep(1)
    log["dim_y_set"] = pg.evaluate(SETIN, ["input[name=stencilWidth]", y])
    time.sleep(3)
    for (h, l) in opts:
        log.setdefault("steps", []).append(set_option(pg, h, l))
        time.sleep(4)
    log["final_selected"] = selected_rows(pg)
    q, t = read_quote(pg)
    log["quote"] = q
    try:
        log["dims_input_readback"] = pg.evaluate(r"""() => {
            const xi=document.querySelector('input[name=stencilLength]');
            const yi=document.querySelector('input[name=stencilWidth]');
            return xi&&yi ? [xi.value, yi.value] : null; }""")
    except Exception as e:
        log["dims_input_readback"] = f"ERR {str(e)[:80]}"
    with open(f"{OUT}/{name}.txt","w") as fh: fh.write(t)
    with open(f"{OUT}/{name}.json","w") as fh: json.dump(log, fh, indent=2)
    print("=====", name)
    print(" dims_readback:", log["dims_input_readback"])
    print(" steps:", json.dumps(log.get("steps", [])))
    print(" final(sel):", json.dumps({k:v for k,v in log["final_selected"].items()
          if k in ("Layers","PCB Thickness","Surface Finish","Via Covering","PCB Qty","Different Design","Delivery Format")}))
    print(" quote:", json.dumps(log["quote"]))
    pg.close()
    return log

if __name__ == "__main__":
    cfgs = json.loads(sys.argv[1])
    with browser(headless=True) as pg0:
        ctx = pg0.context
        for c in cfgs:
            try:
                measure(ctx, c["name"], c["x"], c["y"], [list(o) for o in c["opts"]],
                        qty=c.get("qty",5), surf=c.get("surf"), note=c.get("note",""))
            except Exception as e:
                print("FAILED", c["name"], repr(e)[:200])
                try:
                    json.dump({"name": c["name"], "fatal": repr(e)[:300]},
                              open(f"{OUT}/{c['name']}.FATAL.json","w"), indent=2)
                except Exception:
                    pass
